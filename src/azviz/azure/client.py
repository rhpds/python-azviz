"""Azure client for resource discovery and authentication."""

import logging
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential, ManagedIdentityCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.core.exceptions import AzureError

from ..core.models import AzureResource, NetworkTopology

logger = logging.getLogger(__name__)


class AzureClient:
    """Azure Management API client for resource discovery."""
    
    def __init__(self, subscription_id: Optional[str] = None, credential: Optional[Any] = None):
        """Initialize Azure client.
        
        Args:
            subscription_id: Azure subscription ID. If None, will use first available.
            credential: Azure credential object. If None, will use DefaultAzureCredential.
        """
        self.credential = credential or self._get_default_credential()
        self.subscription_id = subscription_id or self._get_subscription_id()
        
        # Initialize management clients
        self.resource_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )
        self.network_client = NetworkManagementClient(
            credential=self.credential, 
            subscription_id=self.subscription_id
        )
        self.compute_client = ComputeManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )
        
        logger.info(f"Initialized Azure client for subscription: {self.subscription_id}")
    
    def _get_default_credential(self) -> ChainedTokenCredential:
        """Get default Azure credential chain."""
        return ChainedTokenCredential(
            AzureCliCredential(),
            ManagedIdentityCredential(),
            DefaultAzureCredential()
        )
    
    def _get_subscription_id(self) -> str:
        """Get first available subscription ID."""
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions = list(subscription_client.subscriptions.list())
            if not subscriptions:
                raise ValueError("No Azure subscriptions found")
            return subscriptions[0].subscription_id
        except AzureError as e:
            raise ValueError(f"Failed to get Azure subscription: {e}") from e
    
    def test_authentication(self) -> bool:
        """Test Azure authentication and permissions.
        
        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            # Test by listing resource groups
            list(self.resource_client.resource_groups.list())
            logger.info("Azure authentication test successful")
            return True
        except AzureError as e:
            logger.error(f"Azure authentication failed: {e}")
            return False
    
    def get_resource_groups(self) -> List[Dict[str, Any]]:
        """Get all resource groups in subscription.
        
        Returns:
            List of resource group dictionaries.
        """
        try:
            resource_groups = []
            for rg in self.resource_client.resource_groups.list():
                resource_groups.append({
                    'name': rg.name,
                    'location': rg.location,
                    'tags': rg.tags or {},
                    'properties': rg.properties
                })
            return resource_groups
        except AzureError as e:
            logger.error(f"Failed to get resource groups: {e}")
            raise
    
    def get_resources_in_group(self, resource_group_name: str) -> List[AzureResource]:
        """Get all resources in a resource group.
        
        Args:
            resource_group_name: Name of the resource group.
            
        Returns:
            List of AzureResource objects.
        """
        try:
            resources = []
            for resource in self.resource_client.resources.list_by_resource_group(resource_group_name):
                # Get additional properties for VMs (including power state)
                properties = resource.properties or {}
                if resource.type == 'Microsoft.Compute/virtualMachines':
                    vm_power_state = self._get_vm_power_state(resource_group_name, resource.name)
                    if vm_power_state:
                        properties['power_state'] = vm_power_state
                
                azure_resource = AzureResource(
                    name=resource.name,
                    resource_type=resource.type,
                    category=self._extract_category(resource.type),
                    location=resource.location,
                    resource_group=resource_group_name,
                    subscription_id=self.subscription_id,
                    properties=properties,
                    tags=resource.tags or {}
                )
                resources.append(azure_resource)
            
            logger.info(f"Found {len(resources)} resources in group '{resource_group_name}'")
            return resources
        except AzureError as e:
            logger.error(f"Failed to get resources for group '{resource_group_name}': {e}")
            raise
    
    def get_network_topology(self, resource_group_name: str, location: str) -> NetworkTopology:
        """Get network topology for a resource group using Network Watcher.
        
        Args:
            resource_group_name: Target resource group name.
            location: Azure region location.
            
        Returns:
            NetworkTopology object with network resources and relationships.
        """
        try:
            # Find Network Watcher in the region
            network_watcher = self._find_network_watcher(location)
            if not network_watcher:
                logger.debug(f"No Network Watcher found for location '{location}', skipping network topology")
                return NetworkTopology()
            
            # Get topology information
            topology = self.network_client.network_watchers.get_topology(
                resource_group_name=network_watcher['resource_group'],
                network_watcher_name=network_watcher['name'],
                parameters={
                    'target_resource_group_name': resource_group_name
                }
            )
            
            return self._parse_network_topology(topology)
            
        except AzureError as e:
            logger.error(f"Failed to get network topology: {e}")
            # Return empty topology instead of failing
            return NetworkTopology()
    
    def _find_network_watcher(self, location: str) -> Optional[Dict[str, str]]:
        """Find Network Watcher instance for a location.
        
        Args:
            location: Azure region location.
            
        Returns:
            Dictionary with network watcher info or None if not found.
        """
        try:
            for nw in self.network_client.network_watchers.list_all():
                if nw.location.replace(' ', '').lower() == location.replace(' ', '').lower():
                    return {
                        'name': nw.name,
                        'resource_group': nw.id.split('/')[4],  # Extract RG from resource ID
                        'location': nw.location
                    }
            return None
        except AzureError as e:
            logger.error(f"Failed to find Network Watcher: {e}")
            return None
    
    def _parse_network_topology(self, topology: Any) -> NetworkTopology:
        """Parse Network Watcher topology response.
        
        Args:
            topology: Network Watcher topology response.
            
        Returns:
            NetworkTopology object.
        """
        network_topology = NetworkTopology()
        
        if not topology or not topology.resources:
            return network_topology
        
        # Parse resources by type
        for resource in topology.resources:
            # Safely extract resource type - handle different API response formats
            resource_type = ""
            try:
                if hasattr(resource, 'type') and resource.type:
                    resource_type = resource.type.lower()
                elif hasattr(resource, 'resource_type') and resource.resource_type:
                    resource_type = resource.resource_type.lower()
            except AttributeError:
                logger.debug(f"Could not determine resource type for resource: {resource}")
                continue
            
            resource_dict = {
                'id': getattr(resource, 'id', ''),
                'name': getattr(resource, 'name', ''),
                'type': getattr(resource, 'type', getattr(resource, 'resource_type', '')),
                'location': getattr(resource, 'location', ''),
                'associations': getattr(resource, 'associations', []) or []
            }
            
            if 'virtualnetworks' in resource_type:
                network_topology.virtual_networks.append(resource_dict)
            elif 'networkinterfaces' in resource_type:
                network_topology.network_interfaces.append(resource_dict)
            elif 'publicipaddresses' in resource_type:
                network_topology.public_ips.append(resource_dict)
            elif 'loadbalancers' in resource_type:
                network_topology.load_balancers.append(resource_dict)
            elif 'networksecuritygroups' in resource_type:
                network_topology.network_security_groups.append(resource_dict)
        
        # Parse associations for all resources
        for resource in topology.resources:
            associations = getattr(resource, 'associations', []) or []
            if associations:
                for assoc in associations:
                    try:
                        network_topology.associations.append({
                            'source_id': getattr(resource, 'id', ''),
                            'target_id': getattr(assoc, 'resource_id', ''),
                            'association_type': getattr(assoc, 'association_type', ''),
                            'name': getattr(assoc, 'name', '')
                        })
                    except AttributeError as e:
                        logger.debug(f"Could not parse association: {e}")
                        continue
        
        return network_topology
    
    def _get_vm_power_state(self, resource_group_name: str, vm_name: str) -> Optional[str]:
        """Get VM power state.
        
        Args:
            resource_group_name: Resource group name.
            vm_name: Virtual machine name.
            
        Returns:
            VM power state string or None if unavailable.
        """
        try:
            vm_instance_view = self.compute_client.virtual_machines.instance_view(
                resource_group_name=resource_group_name,
                vm_name=vm_name
            )
            
            # Look for power state in statuses
            if vm_instance_view.statuses:
                for status in vm_instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        # Extract power state (e.g., "PowerState/running" -> "running")
                        return status.code.split('/')[-1]
            
            return None
        except AzureError as e:
            logger.debug(f"Could not get power state for VM '{vm_name}': {e}")
            return None
    
    def _extract_category(self, resource_type: str) -> str:
        """Extract category from Azure resource type.
        
        Args:
            resource_type: Full Azure resource type (e.g., Microsoft.Compute/virtualMachines).
            
        Returns:
            Resource category (e.g., Compute).
        """
        if not resource_type:
            return "Unknown"
        
        parts = resource_type.split('/')
        if len(parts) >= 2:
            provider = parts[0].replace('Microsoft.', '')
            return provider.title()
        return "Unknown"