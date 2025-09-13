"""Azure client for resource discovery and authentication."""

import logging
from typing import Any, Dict, List, Optional, Tuple

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
    
    def __init__(self, subscription_identifier: Optional[str] = None, credential: Optional[Any] = None):
        """Initialize Azure client.
        
        Args:
            subscription_identifier: Azure subscription ID or name. If None, will use first available.
            credential: Azure credential object. If None, will use DefaultAzureCredential.
        """
        self.credential = credential or self._get_default_credential()
        
        # Resolve subscription identifier to ID and name
        if not subscription_identifier:
            self.subscription_id, self.subscription_name = self._get_subscription_info()
        else:
            # Resolve the identifier (could be name or ID) to ID and name
            self.subscription_id, self.subscription_name = self._resolve_subscription_identifier(subscription_identifier)
        
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
        
        logger.info(f"Initialized Azure client for subscription: {self.subscription_name} ({self.subscription_id})")
    
    def _get_default_credential(self) -> ChainedTokenCredential:
        """Get default Azure credential chain."""
        return ChainedTokenCredential(
            AzureCliCredential(),
            ManagedIdentityCredential(),
            DefaultAzureCredential()
        )
    
    def _get_subscription_info(self) -> Tuple[str, str]:
        """Get first available subscription ID and name."""
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions = list(subscription_client.subscriptions.list())
            if not subscriptions:
                raise ValueError("No Azure subscriptions found")
            first_sub = subscriptions[0]
            return first_sub.subscription_id, first_sub.display_name
        except AzureError as e:
            raise ValueError(f"Failed to get Azure subscription: {e}") from e
    
    def _get_subscription_name(self, subscription_id: str) -> str:
        """Get subscription display name for a given subscription ID."""
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscription = subscription_client.subscriptions.get(subscription_id)
            return subscription.display_name
        except AzureError as e:
            logger.warning(f"Failed to get subscription name for {subscription_id}: {e}")
            return subscription_id  # Fallback to ID if name unavailable
    
    def _resolve_subscription_identifier(self, subscription_identifier: str) -> Tuple[str, str]:
        """Resolve subscription identifier (name or ID) to ID and name.
        
        Args:
            subscription_identifier: Subscription name or ID.
            
        Returns:
            Tuple of (subscription_id, subscription_name).
            
        Raises:
            ValueError: If subscription cannot be found or resolved.
        """
        try:
            subscription_client = SubscriptionClient(self.credential)
            subscriptions = list(subscription_client.subscriptions.list())
            
            if not subscriptions:
                raise ValueError("No Azure subscriptions found")
            
            # Check if it's a valid subscription ID (UUID format)
            import re
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
            
            if uuid_pattern.match(subscription_identifier):
                # It's likely a subscription ID, try to get it directly
                for sub in subscriptions:
                    if sub.subscription_id.lower() == subscription_identifier.lower():
                        return sub.subscription_id, sub.display_name
                raise ValueError(f"Subscription ID '{subscription_identifier}' not found")
            else:
                # It's likely a subscription name, search by display name
                for sub in subscriptions:
                    if sub.display_name.lower() == subscription_identifier.lower():
                        return sub.subscription_id, sub.display_name
                
                # If exact match not found, try partial match
                partial_matches = []
                for sub in subscriptions:
                    if subscription_identifier.lower() in sub.display_name.lower():
                        partial_matches.append((sub.subscription_id, sub.display_name))
                
                if len(partial_matches) == 1:
                    logger.info(f"Found partial match for subscription '{subscription_identifier}': {partial_matches[0][1]}")
                    return partial_matches[0]
                elif len(partial_matches) > 1:
                    matches_str = ", ".join([f"'{match[1]}'" for match in partial_matches])
                    raise ValueError(f"Multiple subscriptions match '{subscription_identifier}': {matches_str}. Please be more specific.")
                else:
                    available_subs = ", ".join([f"'{sub.display_name}'" for sub in subscriptions[:5]])  # Show first 5
                    raise ValueError(f"Subscription '{subscription_identifier}' not found. Available subscriptions: {available_subs}")
                    
        except AzureError as e:
            raise ValueError(f"Failed to resolve subscription '{subscription_identifier}': {e}") from e
    
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
    
    def get_resources_in_group(self, resource_group_name: str, show_power_state: bool = True) -> List[AzureResource]:
        """Get all resources in a resource group.
        
        Args:
            resource_group_name: Name of the resource group.
            show_power_state: Whether to fetch VM power state information.
            
        Returns:
            List of AzureResource objects.
        """
        try:
            resources = []
            for resource in self.resource_client.resources.list_by_resource_group(resource_group_name):
                # Get additional properties for VMs (including power state)
                properties = resource.properties or {}
                if show_power_state and resource.type == 'Microsoft.Compute/virtualMachines':
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
                    tags=resource.tags or {},
                    dependencies=[]
                )
                resources.append(azure_resource)
            
            # Discover VM-disk relationships
            self._discover_vm_disk_relationships(resources)
            
            # Discover VM-SSH public key relationships
            self._discover_vm_ssh_key_relationships(resources)
            
            # Discover gallery hierarchy relationships
            self._discover_gallery_relationships(resources)
            
            # Discover managed identity relationships
            self._discover_managed_identity_relationships(resources)
            
            # Discover Private DNS Zone relationships
            self._discover_private_dns_relationships(resources)
            
            # Discover NIC-to-private endpoint relationships
            self._discover_nic_private_endpoint_relationships(resources)
            
            # Discover private link service-to-load balancer relationships
            self._discover_private_link_service_relationships(resources)
            
            # Discover all subnets and create virtual subnet resources
            self._discover_all_subnets(resources)
            
            # Discover route table relationships (after subnets are discovered)
            self._discover_route_table_relationships(resources)
            
            # Note: DNS zone relationships are discovered later in post-processing 
            # to handle cross-resource-group relationships
            
            # Discover private endpoint-to-subnet relationships
            self._discover_private_endpoint_subnet_relationships(resources)
            
            # Discover NIC-to-subnet relationships
            self._discover_nic_subnet_relationships(resources)
            
            # Add internet resource for public IPs and discover NSG relationships
            self._add_internet_and_discover_nsg_relationships(resources)
            
            # Discover storage account relationships
            self._discover_storage_account_relationships(resources)
            
            # Discover OpenShift cluster relationships
            self._discover_openshift_cluster_relationships(resources)
            
            # Add VNets and establish proper network hierarchy
            self._add_vnets_and_establish_network_hierarchy(resources)
            
            # Discover and include cross-resource-group dependencies
            self._discover_cross_resource_group_dependencies(resources)
            
            logger.info(f"Found {len(resources)} resources in group '{resource_group_name}'")
            return resources
        except AzureError as e:
            logger.error(f"Failed to get resources for group '{resource_group_name}': {e}")
            raise
    
    def _discover_vm_disk_relationships(self, resources: List[AzureResource]):
        """Discover VM-disk relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find VMs and disks
        vms = [r for r in resources if r.resource_type == 'Microsoft.Compute/virtualMachines']
        disks = [r for r in resources if r.resource_type == 'Microsoft.Compute/disks']
        
        if not vms or not disks:
            return
        
        try:
            # For each VM, get its disk attachments
            for vm in vms:
                try:
                    vm_details = self.compute_client.virtual_machines.get(
                        vm.resource_group, 
                        vm.name,
                        expand='instanceView'
                    )
                    
                    # Get attached disks from storage profile
                    attached_disk_names = set()
                    
                    # OS disk
                    if vm_details.storage_profile and vm_details.storage_profile.os_disk:
                        os_disk = vm_details.storage_profile.os_disk
                        if os_disk.managed_disk and os_disk.managed_disk.id:
                            disk_name = self._extract_resource_name_from_id(os_disk.managed_disk.id)
                            attached_disk_names.add(disk_name)
                    
                    # Data disks
                    if vm_details.storage_profile and vm_details.storage_profile.data_disks:
                        for data_disk in vm_details.storage_profile.data_disks:
                            if data_disk.managed_disk and data_disk.managed_disk.id:
                                disk_name = self._extract_resource_name_from_id(data_disk.managed_disk.id)
                                attached_disk_names.add(disk_name)
                    
                    # Add dependencies for attached disks
                    for disk in disks:
                        if disk.name in attached_disk_names:
                            vm.dependencies.append(disk.name)
                            logger.debug(f"Added disk dependency: {vm.name} -> {disk.name}")
                            
                except Exception as e:
                    logger.warning(f"Could not get disk details for VM '{vm.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover VM-disk relationships: {e}")
    
    def _discover_vm_ssh_key_relationships(self, resources: List[AzureResource]):
        """Discover VM-SSH public key relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find VMs and SSH public keys
        vms = [r for r in resources if r.resource_type == 'Microsoft.Compute/virtualMachines']
        ssh_keys = [r for r in resources if r.resource_type == 'Microsoft.Compute/sshPublicKeys']
        
        if not vms or not ssh_keys:
            return
        
        try:
            # For each SSH public key, find VMs that use it
            for ssh_key in ssh_keys:
                try:
                    # Get SSH key details to extract the public key data
                    ssh_key_details = self.compute_client.ssh_public_keys.get(
                        ssh_key.resource_group,
                        ssh_key.name
                    )
                    
                    if not ssh_key_details.public_key:
                        continue
                    
                    # Get the public key data for comparison
                    ssh_public_key_data = ssh_key_details.public_key.strip()
                    
                    # Check each VM to see if it uses this SSH key
                    for vm in vms:
                        try:
                            vm_details = self.compute_client.virtual_machines.get(
                                vm.resource_group,
                                vm.name
                            )
                            
                            # Check Linux configuration for SSH keys
                            if (vm_details.os_profile and 
                                vm_details.os_profile.linux_configuration and 
                                vm_details.os_profile.linux_configuration.ssh and
                                vm_details.os_profile.linux_configuration.ssh.public_keys):
                                
                                for public_key_config in vm_details.os_profile.linux_configuration.ssh.public_keys:
                                    if (public_key_config.key_data and 
                                        public_key_config.key_data.strip() == ssh_public_key_data):
                                        # VM uses this SSH key - create dependency
                                        vm.dependencies.append(ssh_key.name)
                                        logger.debug(f"Added SSH key dependency: {vm.name} -> {ssh_key.name}")
                                        break
                                        
                        except Exception as e:
                            logger.warning(f"Could not get VM details for SSH key analysis '{vm.name}': {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Could not get SSH key details for '{ssh_key.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover VM-SSH key relationships: {e}")
    
    def _discover_gallery_relationships(self, resources: List[AzureResource]):
        """Discover Azure Compute Gallery hierarchy relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find gallery resources
        galleries = [r for r in resources if r.resource_type == 'Microsoft.Compute/galleries']
        gallery_images = [r for r in resources if r.resource_type == 'Microsoft.Compute/galleries/images']
        gallery_versions = [r for r in resources if r.resource_type == 'Microsoft.Compute/galleries/images/versions']
        
        if not galleries and not gallery_images and not gallery_versions:
            return
        
        try:
            # Create relationships for gallery images -> galleries
            for gallery_image in gallery_images:
                # Extract gallery name from the image resource name
                # Format: gallery_name/image_name
                if '/' in gallery_image.name:
                    gallery_name = gallery_image.name.split('/')[0]
                    
                    # Find the corresponding gallery
                    for gallery in galleries:
                        if gallery.name == gallery_name:
                            gallery_image.dependencies.append(gallery.name)
                            logger.debug(f"Added gallery dependency: {gallery_image.name} -> {gallery.name}")
                            break
            
            # Create relationships for gallery image versions -> gallery images
            for gallery_version in gallery_versions:
                # Extract gallery and image name from version resource name
                # Format: gallery_name/image_name/version
                name_parts = gallery_version.name.split('/')
                if len(name_parts) >= 3:
                    gallery_name = name_parts[0]
                    image_name = name_parts[1]
                    gallery_image_name = f"{gallery_name}/{image_name}"
                    
                    # Find the corresponding gallery image
                    for gallery_image in gallery_images:
                        if gallery_image.name == gallery_image_name:
                            gallery_version.dependencies.append(gallery_image.name)
                            logger.debug(f"Added gallery image dependency: {gallery_version.name} -> {gallery_image.name}")
                            break
                            
        except Exception as e:
            logger.warning(f"Failed to discover gallery relationships: {e}")
    
    def _discover_managed_identity_relationships(self, resources: List[AzureResource]):
        """Discover managed identity usage relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find managed identities and potential resources that use them
        managed_identities = [r for r in resources if r.resource_type == 'Microsoft.ManagedIdentity/userAssignedIdentities']
        potential_users = [r for r in resources if r.resource_type in [
            'Microsoft.Compute/virtualMachines',
            'Microsoft.Compute/virtualMachineScaleSets',
            'Microsoft.ContainerService/managedClusters',
            'Microsoft.RedHatOpenShift/OpenShiftClusters',
            'Microsoft.Web/sites',
            'Microsoft.Storage/storageAccounts'
        ]]
        
        if not managed_identities or not potential_users:
            return
        
        try:
            # For each potential user resource, check if it uses any managed identities
            for resource in potential_users:
                try:
                    resource_details = None
                    
                    # Get resource details based on type
                    if resource.resource_type == 'Microsoft.Compute/virtualMachines':
                        resource_details = self.compute_client.virtual_machines.get(
                            resource.resource_group,
                            resource.name
                        )
                    elif resource.resource_type == 'Microsoft.Compute/virtualMachineScaleSets':
                        resource_details = self.compute_client.virtual_machine_scale_sets.get(
                            resource.resource_group,
                            resource.name
                        )
                    
                    # Check for managed identity usage
                    if resource_details and hasattr(resource_details, 'identity') and resource_details.identity:
                        identity_obj = resource_details.identity
                        
                        # Check for user-assigned identities
                        if (hasattr(identity_obj, 'user_assigned_identities') and 
                            identity_obj.user_assigned_identities):
                            
                            for identity_id, identity_info in identity_obj.user_assigned_identities.items():
                                # Extract identity name from resource ID
                                identity_name = self._extract_resource_name_from_id(identity_id)
                                
                                # Find the corresponding managed identity resource
                                for managed_identity in managed_identities:
                                    if managed_identity.name == identity_name:
                                        resource.dependencies.append(managed_identity.name)
                                        logger.debug(f"Added managed identity dependency: {resource.name} -> {managed_identity.name}")
                                        break
                        
                        # Check for system-assigned identity (would be implicit, no explicit dependency)
                        if (hasattr(identity_obj, 'type') and 
                            identity_obj.type and 
                            'SystemAssigned' in str(identity_obj.type)):
                            logger.debug(f"Resource {resource.name} uses system-assigned managed identity")
                            
                except Exception as e:
                    logger.warning(f"Could not get managed identity details for '{resource.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover managed identity relationships: {e}")
    
    def _discover_private_dns_relationships(self, resources: List[AzureResource]):
        """Discover Private DNS Zone and VNet link relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find Private DNS resources
        private_dns_zones = [r for r in resources if r.resource_type == 'Microsoft.Network/privateDnsZones']
        vnet_links = [r for r in resources if r.resource_type == 'Microsoft.Network/privateDnsZones/virtualNetworkLinks']
        vnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks']
        
        if not private_dns_zones and not vnet_links:
            return
        
        try:
            # Create relationships for VNet links -> Private DNS Zones
            for vnet_link in vnet_links:
                # Extract DNS zone name from VNet link resource name
                # Format: zone_name/link_name
                if '/' in vnet_link.name:
                    dns_zone_name = vnet_link.name.split('/')[0]
                    
                    # Find the corresponding Private DNS Zone
                    for dns_zone in private_dns_zones:
                        if dns_zone.name == dns_zone_name:
                            vnet_link.dependencies.append(dns_zone.name)
                            logger.debug(f"Added Private DNS Zone dependency: {vnet_link.name} -> {dns_zone.name}")
                            break
            
            # Create relationships for VNet links -> Virtual Networks
            for vnet_link in vnet_links:
                try:
                    # Get VNet link details to find the connected VNet
                    dns_zone_name = vnet_link.name.split('/')[0] if '/' in vnet_link.name else vnet_link.name
                    link_name = vnet_link.name.split('/')[-1] if '/' in vnet_link.name else vnet_link.name
                    
                    # Try to use SDK first, fall back to Azure CLI if needed
                    try:
                        # Use the network management client to get virtual network links
                        # Note: This requires azure-mgmt-privatedns which might not be available
                        vnet_link_details = self.network_client.virtual_network_links.get(
                            vnet_link.resource_group,
                            dns_zone_name,
                            link_name
                        )
                        
                        if hasattr(vnet_link_details, 'virtual_network') and vnet_link_details.virtual_network:
                            vnet_id = vnet_link_details.virtual_network.id
                            vnet_name = self._extract_resource_name_from_id(vnet_id)
                            
                            # Find the corresponding VNet resource
                            for vnet in vnets:
                                if vnet.name == vnet_name:
                                    vnet_link.dependencies.append(vnet.name)
                                    logger.debug(f"Added VNet dependency: {vnet_link.name} -> {vnet.name}")
                                    break
                    except AttributeError:
                        # SDK doesn't have private DNS support, try Azure CLI with better error handling
                        import subprocess
                        import json
                        
                        result = subprocess.run([
                            'az', 'network', 'private-dns', 'link', 'vnet', 'show',
                            '--resource-group', vnet_link.resource_group,
                            '--zone-name', dns_zone_name,
                            '--name', link_name,
                            '--query', 'virtualNetwork.id',
                            '-o', 'json'
                        ], capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            vnet_id = json.loads(result.stdout)
                            if vnet_id:
                                # Extract VNet name from resource ID
                                vnet_name = self._extract_resource_name_from_id(vnet_id)
                                
                                # Find the corresponding VNet resource
                                for vnet in vnets:
                                    if vnet.name == vnet_name:
                                        vnet_link.dependencies.append(vnet.name)
                                        logger.debug(f"Added VNet dependency: {vnet_link.name} -> {vnet.name}")
                                        break
                        else:
                            # Log as debug instead of warning if it's a common access issue
                            if "ResourceNotFound" in result.stderr or "exit status 3" in str(result.stderr):
                                logger.debug(f"VNet link '{vnet_link.name}' not accessible or not found - skipping")
                            else:
                                logger.warning(f"Could not get VNet link details for '{vnet_link.name}': {result.stderr}")
                                
                except Exception as e:
                    logger.debug(f"Could not get VNet link details for '{vnet_link.name}': {e}")
                    continue
            
            # Create relationships from Private DNS Zones to VNets they serve (through VNet links)
            for private_dns_zone in private_dns_zones:
                # Find VNet links that belong to this DNS zone
                zone_vnet_links = [vl for vl in vnet_links if vl.name.startswith(f"{private_dns_zone.name}/")]
                
                for zone_vnet_link in zone_vnet_links:
                    # Get the VNets connected through this link
                    for dep_name in zone_vnet_link.dependencies:
                        # Find VNet resources in dependencies
                        for vnet in vnets:
                            if vnet.name == dep_name:
                                private_dns_zone.dependencies.append(vnet.name)
                                logger.debug(f"Added VNet dependency for DNS resolution: {private_dns_zone.name} -> {vnet.name}")
                                break
                                
        except Exception as e:
            logger.warning(f"Failed to discover Private DNS relationships: {e}")
    
    def _discover_route_table_relationships(self, resources: List[AzureResource]):
        """Discover route table to subnet relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find route tables and subnets
        route_tables = [r for r in resources if r.resource_type == 'Microsoft.Network/routeTables']
        subnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks/subnets']
        
        if not route_tables or not subnets:
            return
        
        try:
            # For each route table, find the subnets that use it
            for route_table in route_tables:
                try:
                    # Get route table details to find associated subnets
                    route_table_details = self.network_client.route_tables.get(
                        route_table.resource_group,
                        route_table.name
                    )
                    
                    # Check for subnet associations
                    if hasattr(route_table_details, 'subnets') and route_table_details.subnets:
                        for subnet_ref in route_table_details.subnets:
                            if subnet_ref.id:
                                # Extract subnet name from resource ID
                                # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
                                id_parts = subnet_ref.id.split('/')
                                if len(id_parts) >= 11 and 'subnets' in id_parts:
                                    vnet_index = id_parts.index('virtualNetworks')
                                    subnet_index = id_parts.index('subnets')
                                    if vnet_index + 1 < len(id_parts) and subnet_index + 1 < len(id_parts):
                                        vnet_name = id_parts[vnet_index + 1]
                                        subnet_name = id_parts[subnet_index + 1]
                                        full_subnet_name = f"{vnet_name}/{subnet_name}"
                                        
                                        # Find the corresponding subnet resource
                                        for subnet in subnets:
                                            if subnet.name == full_subnet_name:
                                                subnet.dependencies.append(route_table.name)
                                                logger.debug(f"Added route table dependency: {subnet.name} -> {route_table.name}")
                                                break
                                
                except Exception as e:
                    logger.warning(f"Could not get route table details for '{route_table.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover route table relationships: {e}")
    
    def _discover_dns_zone_relationships(self, resources: List[AzureResource]):
        """Discover DNS zone relationships with load balancers, public IPs, and cluster resources.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find DNS zones and potential related resources across ALL resource groups
        dns_zones = [r for r in resources if r.resource_type == 'Microsoft.Network/dnszones']
        
        if not dns_zones:
            return
        
        # For DNS zones, we need to look across ALL resource groups for related resources
        # Get all resources from the subscription to find cross-resource-group relationships
        try:
            all_load_balancers = []
            all_public_ips = []
            all_master_vms = []
            
            # First, get resources from the current list
            load_balancers = [r for r in resources if r.resource_type == 'Microsoft.Network/loadBalancers']
            public_ips = [r for r in resources if r.resource_type == 'Microsoft.Network/publicIPAddresses']
            master_vms = [r for r in resources if r.resource_type == 'Microsoft.Compute/virtualMachines' and 'master' in r.name.lower()]
            
            all_load_balancers.extend(load_balancers)
            all_public_ips.extend(public_ips)
            all_master_vms.extend(master_vms)
            
            # For each DNS zone, analyze its records to find relationships
            for dns_zone in dns_zones:
                try:
                    # Get DNS zone records to check for cluster relationships
                    import subprocess
                    import json
                    
                    # Get record sets with metadata
                    result = subprocess.run([
                        'az', 'network', 'dns', 'record-set', 'list',
                        '--resource-group', dns_zone.resource_group,
                        '--zone-name', dns_zone.name,
                        '--query', '[].{name:name, type:type, metadata:metadata}',
                        '-o', 'json'
                    ], capture_output=True, text=True, check=True)
                    
                    record_sets = json.loads(result.stdout)
                    
                    # Look for records with cluster metadata
                    cluster_names = set()
                    for record in record_sets:
                        if record.get('metadata'):
                            for key, value in record['metadata'].items():
                                if 'kubernetes.io_cluster.' in key and value == 'owned':
                                    # Extract cluster name from metadata key
                                    cluster_name = key.replace('kubernetes.io_cluster.', '')
                                    cluster_names.add(cluster_name)
                                    logger.debug(f"DNS zone '{dns_zone.name}' serves cluster '{cluster_name}'")
                    
                    # Connect DNS zone to related cluster resources
                    for cluster_name in cluster_names:
                        # Connect to load balancers with matching cluster name
                        for lb in all_load_balancers:
                            if cluster_name in lb.name.lower():
                                dns_zone.dependencies.append(lb.name)
                                logger.debug(f"Added DNS-LoadBalancer dependency: {dns_zone.name} -> {lb.name}")
                        
                        # Connect to public IPs with matching cluster name
                        for pip in all_public_ips:
                            if cluster_name in pip.name.lower():
                                dns_zone.dependencies.append(pip.name)
                                logger.debug(f"Added DNS-PublicIP dependency: {dns_zone.name} -> {pip.name}")
                        
                        # Connect to master VMs with matching cluster name (they serve the API)
                        for master_vm in all_master_vms:
                            if cluster_name in master_vm.name.lower():
                                dns_zone.dependencies.append(master_vm.name)
                                logger.debug(f"Added DNS-Master dependency: {dns_zone.name} -> {master_vm.name}")
                                
                except Exception as e:
                    logger.warning(f"Could not analyze DNS zone records for '{dns_zone.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover DNS zone relationships: {e}")
    
    def _discover_nic_private_endpoint_relationships(self, resources: List[AzureResource]):
        """Discover NIC-to-private endpoint and private link service relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find NICs, private endpoints, and private link services
        nics = [r for r in resources if r.resource_type == 'Microsoft.Network/networkInterfaces']
        private_endpoints = [r for r in resources if r.resource_type == 'Microsoft.Network/privateEndpoints']
        private_link_services = [r for r in resources if r.resource_type == 'Microsoft.Network/privateLinkServices']
        
        if not nics:
            return
        
        try:
            # For each NIC, check if it's attached to a private endpoint or private link service
            for nic in nics:
                try:
                    nic_details = self.network_client.network_interfaces.get(
                        nic.resource_group, 
                        nic.name
                    )
                    
                    # Check if this NIC belongs to a private endpoint
                    if hasattr(nic_details, 'private_endpoint') and nic_details.private_endpoint:
                        pe_resource_id = nic_details.private_endpoint.id
                        pe_name = self._extract_resource_name_from_id(pe_resource_id)
                        
                        # Find the corresponding private endpoint resource
                        for pe in private_endpoints:
                            if pe.name == pe_name:
                                pe.dependencies.append(nic.name)
                                logger.debug(f"Added NIC dependency: {pe.name} -> {nic.name}")
                                break
                    
                    # Check if this NIC belongs to a private link service
                    elif hasattr(nic_details, 'private_link_service') and nic_details.private_link_service:
                        pls_resource_id = nic_details.private_link_service.id
                        pls_name = self._extract_resource_name_from_id(pls_resource_id)
                        
                        # Find the corresponding private link service resource
                        for pls in private_link_services:
                            if pls.name == pls_name:
                                pls.dependencies.append(nic.name)
                                logger.debug(f"Added NIC dependency: {pls.name} -> {nic.name}")
                                break
                            
                except Exception as e:
                    logger.warning(f"Could not get NIC details for '{nic.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover NIC-private endpoint/private link service relationships: {e}")
    
    def _discover_private_link_service_relationships(self, resources: List[AzureResource]):
        """Discover private link service-to-load balancer relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find private link services and load balancers
        private_link_services = [r for r in resources if r.resource_type == 'Microsoft.Network/privateLinkServices']
        load_balancers = [r for r in resources if r.resource_type == 'Microsoft.Network/loadBalancers']
        
        if not private_link_services or not load_balancers:
            return
        
        try:
            # For each private link service, check its load balancer frontend configuration
            for pls in private_link_services:
                try:
                    pls_details = self.network_client.private_link_services.get(
                        pls.resource_group, 
                        pls.name
                    )
                    
                    # Check for load balancer frontend IP configurations
                    if hasattr(pls_details, 'load_balancer_frontend_ip_configurations') and pls_details.load_balancer_frontend_ip_configurations:
                        for frontend_config in pls_details.load_balancer_frontend_ip_configurations:
                            if frontend_config.id:
                                # Extract load balancer name from the frontend IP configuration ID
                                # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/loadBalancers/{lb_name}/frontendIPConfigurations/{config_name}
                                id_parts = frontend_config.id.split('/')
                                if len(id_parts) >= 9 and 'loadBalancers' in id_parts:
                                    lb_index = id_parts.index('loadBalancers')
                                    if lb_index + 1 < len(id_parts):
                                        lb_name = id_parts[lb_index + 1]
                                        
                                        # Find the corresponding load balancer resource
                                        for lb in load_balancers:
                                            if lb.name == lb_name:
                                                pls.dependencies.append(lb.name)
                                                logger.debug(f"Added load balancer dependency: {pls.name} -> {lb.name}")
                                                break
                            
                except Exception as e:
                    logger.warning(f"Could not get private link service details for '{pls.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover private link service-load balancer relationships: {e}")
    
    def _discover_all_subnets(self, resources: List[AzureResource]):
        """Discover all VNets and their subnets, creating virtual subnet resources.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        try:
            # Get all VNets in the subscription to find subnets
            vnets = []
            try:
                # Get all VNets in the subscription (not just the current resource group)
                for vnet in self.network_client.virtual_networks.list_all():
                    vnets.append(vnet)
                    logger.debug(f"Found VNet: {vnet.name} in RG: {vnet.id.split('/')[4] if '/' in vnet.id else 'unknown'}")
            except Exception as e:
                logger.warning(f"Could not list VNets: {e}")
                return
            
            # Process each VNet and its subnets
            for vnet in vnets:
                try:
                    vnet_name = vnet.name
                    vnet_rg = vnet.id.split('/')[4] if '/' in vnet.id else 'unknown'
                    
                    # Get detailed VNet information including subnets
                    vnet_details = self.network_client.virtual_networks.get(vnet_rg, vnet_name)
                    
                    if hasattr(vnet_details, 'subnets') and vnet_details.subnets:
                        for subnet in vnet_details.subnets:
                            subnet_name = subnet.name
                            subnet_full_name = f"{vnet_name}/{subnet_name}"
                            
                            # Check if we already have this subnet (from PE discovery)
                            subnet_exists = any(r.name == subnet_full_name for r in resources 
                                              if r.resource_type == 'Microsoft.Network/virtualNetworks/subnets')
                            
                            if not subnet_exists:
                                # Create virtual subnet resource
                                virtual_subnet = AzureResource(
                                    name=subnet_full_name,
                                    resource_type='Microsoft.Network/virtualNetworks/subnets',
                                    category='Network',
                                    location=vnet.location,
                                    resource_group=vnet_rg,
                                    subscription_id=self.subscription_id,
                                    properties={
                                        'vnet_name': vnet_name,
                                        'subnet_name': subnet_name,
                                        'address_prefix': getattr(subnet, 'address_prefix', 'unknown'),
                                        'is_virtual': True
                                    },
                                    tags={},
                                    dependencies=[]
                                )
                                resources.append(virtual_subnet)
                                logger.debug(f"Created virtual subnet resource: {subnet_full_name} (prefix: {getattr(subnet, 'address_prefix', 'unknown')})")
                
                except Exception as e:
                    logger.warning(f"Could not process VNet '{vnet.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover all subnets: {e}")
    
    def _discover_private_endpoint_subnet_relationships(self, resources: List[AzureResource]):
        """Discover private endpoint-to-subnet relationships, create virtual subnet resources, and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find private endpoints - we need to discover subnets from VNets
        private_endpoints = [r for r in resources if r.resource_type == 'Microsoft.Network/privateEndpoints']
        
        if not private_endpoints:
            return
        
        
        try:
            # For each private endpoint, get its subnet information
            for pe in private_endpoints:
                try:
                    pe_details = self.network_client.private_endpoints.get(
                        pe.resource_group, 
                        pe.name
                    )
                    
                    # Check for subnet configuration
                    if hasattr(pe_details, 'subnet') and pe_details.subnet and pe_details.subnet.id:
                        subnet_id = pe_details.subnet.id
                        # Extract VNet and subnet names from ID
                        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
                        id_parts = subnet_id.split('/')
                        if len(id_parts) >= 11 and 'virtualNetworks' in id_parts and 'subnets' in id_parts:
                            vnet_index = id_parts.index('virtualNetworks')
                            subnet_index = id_parts.index('subnets')
                            
                            if vnet_index + 1 < len(id_parts) and subnet_index + 1 < len(id_parts):
                                vnet_name = id_parts[vnet_index + 1]
                                subnet_name = id_parts[subnet_index + 1]
                                
                                # Store subnet information in PE properties for later visualization
                                pe.properties['subnet_name'] = subnet_name
                                pe.properties['vnet_name'] = vnet_name
                                pe.properties['subnet_id'] = subnet_id
                                
                                # Add dependency from PE to subnet (subnet should already exist from _discover_all_subnets)
                                subnet_full_name = f"{vnet_name}/{subnet_name}"
                                pe.dependencies.append(subnet_full_name)
                                logger.debug(f"Added subnet dependency: {pe.name} -> {subnet_full_name}")
                    
                    # Check for private link service connections (both automatic and manual)
                    pls_connections = []
                    
                    if hasattr(pe_details, 'private_link_service_connections') and pe_details.private_link_service_connections:
                        pls_connections.extend(pe_details.private_link_service_connections)
                    
                    if hasattr(pe_details, 'manual_private_link_service_connections') and pe_details.manual_private_link_service_connections:
                        pls_connections.extend(pe_details.manual_private_link_service_connections)
                    
                    # Store external PLS connection info
                    external_connections = []
                    for conn in pls_connections:
                        if hasattr(conn, 'private_link_service_id') and conn.private_link_service_id:
                            pls_id = conn.private_link_service_id
                            pls_name = self._extract_resource_name_from_id(pls_id)
                            
                            # Extract resource group from the PLS ID to determine if external
                            id_parts = pls_id.split('/')
                            if len(id_parts) >= 5:
                                pls_rg = id_parts[4]
                                pls_subscription = id_parts[2] if len(id_parts) >= 3 else None
                                
                                external_connections.append({
                                    'name': pls_name,
                                    'id': pls_id,
                                    'resource_group': pls_rg,
                                    'subscription': pls_subscription,
                                    'connection_name': getattr(conn, 'name', 'unknown')
                                })
                                
                                logger.debug(f"Added external PLS connection: {pe.name} -> {pls_name} (RG: {pls_rg})")
                    
                    if external_connections:
                        pe.properties['external_pls_connections'] = external_connections
                            
                except Exception as e:
                    logger.warning(f"Could not get private endpoint details for '{pe.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover private endpoint-subnet relationships: {e}")
    
    def _discover_nic_subnet_relationships(self, resources: List[AzureResource]):
        """Discover NIC-to-subnet relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find NICs
        nics = [r for r in resources if r.resource_type == 'Microsoft.Network/networkInterfaces']
        
        if not nics:
            return
        
        try:
            # For each NIC, get its subnet information
            for nic in nics:
                try:
                    nic_details = self.network_client.network_interfaces.get(
                        nic.resource_group, 
                        nic.name
                    )
                    
                    # Check IP configurations for subnet information
                    if hasattr(nic_details, 'ip_configurations') and nic_details.ip_configurations:
                        for ip_config in nic_details.ip_configurations:
                            if hasattr(ip_config, 'subnet') and ip_config.subnet and ip_config.subnet.id:
                                subnet_id = ip_config.subnet.id
                                # Extract VNet and subnet names from ID
                                id_parts = subnet_id.split('/')
                                if len(id_parts) >= 11 and 'virtualNetworks' in id_parts and 'subnets' in id_parts:
                                    vnet_index = id_parts.index('virtualNetworks')
                                    subnet_index = id_parts.index('subnets')
                                    
                                    if vnet_index + 1 < len(id_parts) and subnet_index + 1 < len(id_parts):
                                        vnet_name = id_parts[vnet_index + 1]
                                        subnet_name = id_parts[subnet_index + 1]
                                        subnet_full_name = f"{vnet_name}/{subnet_name}"
                                        
                                        # Add dependency from NIC to subnet
                                        nic.dependencies.append(subnet_full_name)
                                        logger.debug(f"Added subnet dependency: {nic.name} -> {subnet_full_name}")
                                        break  # Only need one subnet per NIC
                            
                except Exception as e:
                    logger.warning(f"Could not get NIC details for '{nic.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to discover NIC-subnet relationships: {e}")
    
    def _add_internet_and_discover_nsg_relationships(self, resources: List[AzureResource]):
        """Add internet resource for public IPs and discover NSG relationships.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        try:
            # Find public IPs and NSGs
            public_ips = [r for r in resources if r.resource_type == 'Microsoft.Network/publicIPAddresses']
            nsgs = [r for r in resources if r.resource_type == 'Microsoft.Network/networkSecurityGroups']
            subnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks/subnets']
            
            # Add internet resource if we have public IPs
            if public_ips:
                internet_resource = AzureResource(
                    name='Internet',
                    resource_type='Internet/Gateway',
                    category='Internet',
                    location='global',
                    resource_group='internet',
                    subscription_id=self.subscription_id,
                    properties={
                        'is_virtual': True,
                        'description': 'Internet Gateway',
                        'hide_provider': True  # Hide provider in display
                    },
                    tags={},
                    dependencies=[]
                )
                resources.append(internet_resource)
                logger.debug("Created virtual Internet resource")
                
                # Add dependencies from Internet to public IPs
                for pip in public_ips:
                    internet_resource.dependencies.append(pip.name)
                    logger.debug(f"Added public IP dependency: Internet -> {pip.name}")
            
            # Discover NSG-to-subnet relationships
            for nsg in nsgs:
                try:
                    nsg_details = self.network_client.network_security_groups.get(
                        nsg.resource_group, 
                        nsg.name
                    )
                    
                    # Check for subnet associations
                    if hasattr(nsg_details, 'subnets') and nsg_details.subnets:
                        for subnet_ref in nsg_details.subnets:
                            if subnet_ref.id:
                                # Extract VNet and subnet names from ID
                                id_parts = subnet_ref.id.split('/')
                                if len(id_parts) >= 11 and 'virtualNetworks' in id_parts and 'subnets' in id_parts:
                                    vnet_index = id_parts.index('virtualNetworks')
                                    subnet_index = id_parts.index('subnets')
                                    
                                    if vnet_index + 1 < len(id_parts) and subnet_index + 1 < len(id_parts):
                                        vnet_name = id_parts[vnet_index + 1].lower()
                                        subnet_name = id_parts[subnet_index + 1].lower()
                                        subnet_full_name = f"{vnet_name}/{subnet_name}"
                                        
                                        # Add dependency from NSG to subnet
                                        nsg.dependencies.append(subnet_full_name)
                                        logger.debug(f"Added subnet dependency: {nsg.name} -> {subnet_full_name}")
                
                except Exception as e:
                    logger.warning(f"Could not get NSG details for '{nsg.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to add internet resource and discover NSG relationships: {e}")
    
    def _discover_storage_account_relationships(self, resources: List[AzureResource]):
        """Discover storage account relationships with VMs and other resources.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        try:
            # Find storage accounts and VMs
            storage_accounts = [r for r in resources if r.resource_type == 'Microsoft.Storage/storageAccounts']
            vms = [r for r in resources if r.resource_type == 'Microsoft.Compute/virtualMachines']
            
            if not storage_accounts:
                return
            
            # For each VM, check if it uses any storage accounts
            for vm in vms:
                try:
                    vm_details = self.compute_client.virtual_machines.get(
                        vm.resource_group, 
                        vm.name
                    )
                    
                    # Check boot diagnostics storage
                    if (hasattr(vm_details, 'diagnostics_profile') and 
                        vm_details.diagnostics_profile and
                        hasattr(vm_details.diagnostics_profile, 'boot_diagnostics') and
                        vm_details.diagnostics_profile.boot_diagnostics and
                        hasattr(vm_details.diagnostics_profile.boot_diagnostics, 'storage_uri') and
                        vm_details.diagnostics_profile.boot_diagnostics.storage_uri):
                        
                        storage_uri = vm_details.diagnostics_profile.boot_diagnostics.storage_uri
                        # Extract storage account name from URI (format: https://storageaccount.blob.core.windows.net/)
                        if storage_uri:
                            storage_name = storage_uri.split('//')[1].split('.')[0] if '//' in storage_uri else None
                            if storage_name:
                                # Find the corresponding storage account
                                for sa in storage_accounts:
                                    if sa.name == storage_name:
                                        vm.dependencies.append(sa.name)
                                        logger.debug(f"Added storage dependency: {vm.name} -> {sa.name} (boot diagnostics)")
                                        break
                    
                    # Check for unmanaged disks (if any VMs still use them)
                    if (hasattr(vm_details, 'storage_profile') and 
                        vm_details.storage_profile and
                        hasattr(vm_details.storage_profile, 'os_disk') and
                        vm_details.storage_profile.os_disk and
                        hasattr(vm_details.storage_profile.os_disk, 'vhd') and
                        vm_details.storage_profile.os_disk.vhd and
                        hasattr(vm_details.storage_profile.os_disk.vhd, 'uri')):
                        
                        vhd_uri = vm_details.storage_profile.os_disk.vhd.uri
                        if vhd_uri:
                            storage_name = vhd_uri.split('//')[1].split('.')[0] if '//' in vhd_uri else None
                            if storage_name:
                                # Find the corresponding storage account
                                for sa in storage_accounts:
                                    if sa.name == storage_name:
                                        vm.dependencies.append(sa.name)
                                        logger.debug(f"Added storage dependency: {vm.name} -> {sa.name} (unmanaged disk)")
                                        break
                
                except Exception as e:
                    logger.warning(f"Could not get VM details for '{vm.name}': {e}")
                    continue
            
            # For ARO/OpenShift clusters, connect storage accounts to master nodes
            # as they typically manage cluster storage
            if storage_accounts and vms:
                # Look for storage accounts that appear to be cluster-related
                cluster_storage_accounts = []
                for sa in storage_accounts:
                    # Check if storage account name suggests cluster usage
                    sa_name_lower = sa.name.lower()
                    if any(keyword in sa_name_lower for keyword in ['cluster', 'registry', 'image']):
                        cluster_storage_accounts.append(sa)
                    else:
                        # Also check for naming patterns that include cluster/resource group names
                        # Extract potential cluster identifier from resource group or VM names
                        if vms:
                            # Look for common prefixes in VM names that might match storage account name
                            vm_prefixes = set()
                            for vm in vms:
                                if 'master' in vm.name.lower() or 'worker' in vm.name.lower():
                                    # Extract cluster name from VM name (e.g., "byoid-fp64f" from "byoid-fp64f-master-0")
                                    parts = vm.name.lower().split('-')
                                    if len(parts) >= 3:  # e.g., ["byoid", "fp64f", "master", "0"]
                                        potential_cluster_name = '-'.join(parts[:-2])  # "byoid-fp64f"
                                        # Remove hyphens for storage account name comparison
                                        cluster_name_no_hyphen = potential_cluster_name.replace('-', '')
                                        vm_prefixes.add(cluster_name_no_hyphen)
                            
                            # Check if storage account name contains any of these cluster prefixes
                            for prefix in vm_prefixes:
                                if prefix in sa_name_lower and len(prefix) > 3:  # Avoid short/common prefixes
                                    cluster_storage_accounts.append(sa)
                                    logger.debug(f"Storage account '{sa.name}' identified as cluster storage based on naming pattern '{prefix}'")
                                    break
                
                if cluster_storage_accounts:
                    # Connect cluster storage to master nodes (they manage cluster resources)
                    master_vms = [vm for vm in vms if 'master' in vm.name.lower()]
                    if master_vms:
                        # Connect to ALL master nodes since they all manage cluster resources
                        for master_vm in master_vms:
                            for sa in cluster_storage_accounts:
                                master_vm.dependencies.append(sa.name)
                                logger.debug(f"Added cluster storage dependency: {master_vm.name} -> {sa.name} (cluster storage)")
                    else:
                        # If no masters, connect to any VM that might be a controller
                        controller_vms = [vm for vm in vms if any(keyword in vm.name.lower() for keyword in ['control', 'manage'])]
                        if controller_vms:
                            # Connect to all controller VMs for consistency
                            for controller_vm in controller_vms:
                                for sa in cluster_storage_accounts:
                                    controller_vm.dependencies.append(sa.name)
                                    logger.debug(f"Added cluster storage dependency: {controller_vm.name} -> {sa.name} (cluster storage)")
            
        except Exception as e:
            logger.warning(f"Failed to discover storage account relationships: {e}")
    
    def _add_vnets_and_establish_network_hierarchy(self, resources: List[AzureResource]):
        """Add VNet resources and establish proper network hierarchy relationships.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        try:
            # Find existing subnets, private endpoints, and real VNets
            subnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks/subnets']
            private_endpoints = [r for r in resources if r.resource_type == 'Microsoft.Network/privateEndpoints']
            existing_vnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks']
            
            # Track VNets we've already created (including existing real VNets)
            created_vnets = {}
            
            # First, add existing real VNets to the tracking dictionary
            for vnet in existing_vnets:
                created_vnets[vnet.name] = vnet
                logger.debug(f"Found existing real VNet: {vnet.name}")
            
            # Create VNet resources based on subnets (only if not already existing)
            for subnet in subnets:
                if 'vnet_name' in subnet.properties:
                    vnet_name = subnet.properties['vnet_name']
                    
                    if vnet_name not in created_vnets:
                        # Create virtual VNet resource
                        virtual_vnet = AzureResource(
                            name=vnet_name,
                            resource_type='Microsoft.Network/virtualNetworks',
                            category='Network',
                            location=subnet.location,
                            resource_group=subnet.resource_group,
                            subscription_id=self.subscription_id,
                            properties={
                                'is_virtual': True,
                                'vnet_name': vnet_name
                            },
                            tags={},
                            dependencies=[]
                        )
                        resources.append(virtual_vnet)
                        created_vnets[vnet_name] = virtual_vnet
                        logger.debug(f"Created virtual VNet resource: {vnet_name}")
                    
                    # Add dependency from VNet to subnet
                    created_vnets[vnet_name].dependencies.append(subnet.name)
                    logger.debug(f"Added subnet dependency: {vnet_name} -> {subnet.name}")
            
            # Establish PE → VNet relationships (PE belongs to VNet, not directly to subnet)
            for pe in private_endpoints:
                if 'vnet_name' in pe.properties:
                    vnet_name = pe.properties['vnet_name']
                    if vnet_name in created_vnets:
                        # Add dependency from VNet to PE (VNet contains PE)
                        created_vnets[vnet_name].dependencies.append(pe.name)
                        logger.debug(f"Added PE dependency: {vnet_name} -> {pe.name}")
                        
                        # Remove direct PE → subnet dependency since PE now belongs to VNet
                        subnet_full_name = f"{vnet_name}/{pe.properties.get('subnet_name', '')}"
                        if subnet_full_name in pe.dependencies:
                            pe.dependencies.remove(subnet_full_name)
                            logger.debug(f"Removed direct subnet dependency: {pe.name} -/-> {subnet_full_name}")
                            
        except Exception as e:
            logger.warning(f"Failed to add VNets and establish network hierarchy: {e}")
    
    def _discover_openshift_cluster_relationships(self, resources: List[AzureResource]):
        """Discover OpenShift cluster relationships and add dependencies.
        
        Args:
            resources: List of Azure resources to analyze.
        """
        # Find OpenShift clusters  
        openshift_clusters = [r for r in resources if r.resource_type == 'Microsoft.RedHatOpenShift/OpenShiftClusters']
        
        if not openshift_clusters:
            return
        
        # Find related resources
        vnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks']
        subnets = [r for r in resources if r.resource_type == 'Microsoft.Network/virtualNetworks/subnets']
        storage_accounts = [r for r in resources if r.resource_type == 'Microsoft.Storage/storageAccounts']
        nics = [r for r in resources if r.resource_type == 'Microsoft.Network/networkInterfaces']
        vms = [r for r in resources if r.resource_type == 'Microsoft.Compute/virtualMachines']
        load_balancers = [r for r in resources if r.resource_type == 'Microsoft.Network/loadBalancers']
        
        try:
            for cluster in openshift_clusters:
                try:
                    logger.info(f"Discovering dependencies for OpenShift cluster: {cluster.name}")
                    
                    # Fetch OpenShift cluster details to extract DNS configuration
                    self._extract_openshift_dns_configuration(cluster)
                    
                    # OpenShift clusters often have resources in different resource groups
                    # Look for resources with the cluster name pattern across all resource groups
                    cluster_name_base = cluster.name.lower()
                    
                    # Find VNets that match the cluster name (often named vnet-{cluster-name})
                    for vnet in vnets:
                        vnet_name_lower = vnet.name.lower()
                        if (cluster_name_base in vnet_name_lower or 
                            vnet_name_lower.startswith('vnet-') and cluster_name_base in vnet_name_lower or
                            'openshift' in vnet_name_lower):
                            cluster.dependencies.append(vnet.name)
                            logger.info(f"Added VNet dependency: {cluster.name} -> {vnet.name}")
                    
                    # Find subnets that likely belong to this cluster
                    # Look for patterns like cluster-name, master, worker subnets
                    cluster_subnets = []
                    for subnet in subnets:
                        subnet_name_lower = subnet.name.lower()
                        if (cluster_name_base in subnet_name_lower or 
                            'master' in subnet_name_lower or 
                            'worker' in subnet_name_lower or
                            'openshift' in subnet_name_lower or
                            'aro' in subnet_name_lower):
                            cluster_subnets.append(subnet)
                            cluster.dependencies.append(subnet.name)
                            logger.info(f"Added subnet dependency: {cluster.name} -> {subnet.name}")
                    
                    # Find storage accounts that belong to this cluster
                    # Look for registry, cluster storage accounts
                    for sa in storage_accounts:
                        sa_name_lower = sa.name.lower()
                        if ('registry' in sa_name_lower or 
                            'cluster' in sa_name_lower or
                            cluster_name_base.replace('-', '') in sa_name_lower or
                            'openshift' in sa_name_lower or
                            'aro' in sa_name_lower):
                            cluster.dependencies.append(sa.name)
                            logger.info(f"Added storage dependency: {cluster.name} -> {sa.name}")
                    
                    # Find VMs that are part of this cluster (master and worker nodes)
                    cluster_vms = []
                    for vm in vms:
                        vm_name_lower = vm.name.lower()
                        # Look for VMs with cluster name pattern or master/worker patterns
                        if (cluster_name_base in vm_name_lower or 
                            ('master' in vm_name_lower and 'aro' in vm_name_lower) or
                            ('worker' in vm_name_lower and 'aro' in vm_name_lower) or
                            'openshift' in vm_name_lower):
                            cluster_vms.append(vm)
                            cluster.dependencies.append(vm.name)
                            logger.info(f"Added VM dependency: {cluster.name} -> {vm.name}")
                    
                    # Find NICs that belong to cluster VMs or infrastructure
                    for nic in nics:
                        nic_name_lower = nic.name.lower()
                        if (cluster_name_base in nic_name_lower or 
                            'master' in nic_name_lower or 
                            'worker' in nic_name_lower or
                            'openshift' in nic_name_lower or
                            'aro' in nic_name_lower):
                            cluster.dependencies.append(nic.name)
                            logger.info(f"Added NIC dependency: {cluster.name} -> {nic.name}")
                    
                    # Find load balancers that belong to this cluster
                    for lb in load_balancers:
                        lb_name_lower = lb.name.lower()
                        if (cluster_name_base in lb_name_lower or 
                            'openshift' in lb_name_lower or
                            'aro' in lb_name_lower):
                            cluster.dependencies.append(lb.name)
                            logger.info(f"Added load balancer dependency: {cluster.name} -> {lb.name}")
                    
                    # Set cluster properties for better visualization
                    if cluster.dependencies:
                        cluster.properties['has_dependencies'] = True
                        cluster.properties['dependency_count'] = len(cluster.dependencies)
                        logger.info(f"OpenShift cluster {cluster.name} now has {len(cluster.dependencies)} dependencies")
                    else:
                        logger.warning(f"No dependencies found for OpenShift cluster {cluster.name}")
                    
                except Exception as e:
                    logger.warning(f"Could not analyze OpenShift cluster '{cluster.name}': {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Failed to discover OpenShift cluster relationships: {e}")
    
    def _extract_resource_name_from_id(self, resource_id: str) -> str:
        """Extract resource name from Azure resource ID.
        
        Args:
            resource_id: Azure resource ID.
            
        Returns:
            Resource name.
        """
        if not resource_id:
            return ""
        
        # Azure resource ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
        parts = resource_id.split('/')
        if len(parts) >= 9:
            return parts[-1]  # Last part is the resource name
        
        return resource_id
    
    def _get_api_version_for_resource_type(self, resource_type: str) -> str:
        """Get the appropriate API version for a given resource type.
        
        Args:
            resource_type: Azure resource type (e.g., Microsoft.ContainerService/managedClusters).
            
        Returns:
            API version string.
        """
        # Map of resource types to their latest stable API versions
        api_versions = {
            # Container Service
            'Microsoft.ContainerService/managedClusters': '2024-09-01',
            'Microsoft.ContainerService/managedClusterSnapshots': '2024-09-01',
            'Microsoft.ContainerService/fleets': '2024-04-01',
            
            # Compute
            'Microsoft.Compute/virtualMachines': '2024-07-01',
            'Microsoft.Compute/virtualMachineScaleSets': '2024-07-01',
            'Microsoft.Compute/disks': '2024-03-02',
            'Microsoft.Compute/images': '2024-07-01',
            'Microsoft.Compute/galleries': '2023-07-03',
            'Microsoft.Compute/galleries/images': '2023-07-03',
            'Microsoft.Compute/galleries/images/versions': '2023-07-03',
            'Microsoft.Compute/sshPublicKeys': '2024-07-01',
            
            # Network
            'Microsoft.Network/virtualNetworks': '2024-01-01',
            'Microsoft.Network/networkInterfaces': '2024-01-01',
            'Microsoft.Network/publicIPAddresses': '2024-01-01',
            'Microsoft.Network/loadBalancers': '2024-01-01',
            'Microsoft.Network/networkSecurityGroups': '2024-01-01',
            'Microsoft.Network/routeTables': '2024-01-01',
            'Microsoft.Network/privateEndpoints': '2024-01-01',
            'Microsoft.Network/privateLinkServices': '2024-01-01',
            'Microsoft.Network/dnszones': '2018-05-01',
            'Microsoft.Network/privateDnsZones': '2020-06-01',
            'Microsoft.Network/privateDnsZones/virtualNetworkLinks': '2020-06-01',
            
            # Storage
            'Microsoft.Storage/storageAccounts': '2023-05-01',
            
            # Identity
            'Microsoft.ManagedIdentity/userAssignedIdentities': '2023-01-31',
            
            # Red Hat OpenShift
            'Microsoft.RedHatOpenShift/OpenShiftClusters': '2024-08-12-preview',
            
            # Web
            'Microsoft.Web/sites': '2023-12-01',
            'Microsoft.Web/serverfarms': '2023-12-01',
        }
        
        # Return specific API version if available, otherwise use a recent generic version
        return api_versions.get(resource_type.lower(), '2023-07-01')
    
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
        
        # Special case mappings for better logical categorization
        special_mappings = {
            'microsoft.redhatopenshift/openshiftclusters': 'Container',
            'microsoft.containerservice/managedclusters': 'Container',
            'microsoft.kubernetes/connectedclusters': 'Container',
        }
        
        resource_type_lower = resource_type.lower()
        if resource_type_lower in special_mappings:
            return special_mappings[resource_type_lower]
        
        parts = resource_type.split('/')
        if len(parts) >= 2:
            provider = parts[0].replace('Microsoft.', '')
            return provider.title()
        return "Unknown"
    
    def _discover_cross_resource_group_dependencies(self, resources: List[AzureResource]):
        """Discover and include resources from other resource groups that are dependencies.
        
        Args:
            resources: List of Azure resources to analyze and expand.
        """
        try:
            external_resource_ids = set()
            
            # Collect all external resource references
            for resource in resources:
                # Check for external private link service connections
                if 'external_pls_connections' in resource.properties:
                    logger.info(f"Processing external connections for {resource.name}: {len(resource.properties['external_pls_connections'])} connections")
                    for conn in resource.properties['external_pls_connections']:
                        external_resource_ids.add(conn['id'])
                        logger.info(f"Found external PLS dependency: {resource.name} -> {conn['name']} (RG: {conn['resource_group']})")
            
            logger.info(f"Total external resource IDs to process: {len(external_resource_ids)}")
            
            # Fetch and add external resources
            for resource_id in external_resource_ids:
                external_resource = self._fetch_external_resource(resource_id)
                if external_resource:
                    resources.append(external_resource)
                    logger.info(f"Added cross-RG dependency: {external_resource.name} from {external_resource.resource_group}")
                    
                    # Create dependencies from private endpoints to external resources
                    for resource in resources:
                        if 'external_pls_connections' in resource.properties:
                            for conn in resource.properties['external_pls_connections']:
                                if conn['id'] == resource_id:
                                    resource.dependencies.append(external_resource.name)
                                    logger.debug(f"Added dependency: {resource.name} -> {external_resource.name}")
                else:
                    # External resource fetch failed, check if it's a cross-tenant issue and create placeholder
                    is_cross_tenant = self._check_cross_tenant_resource(resource_id)
                    logger.info(f"External resource fetch failed for {resource_id}, creating placeholder (cross-tenant: {is_cross_tenant})")
                    
                    # Create a placeholder resource for visualization
                    placeholder_resource = self._create_placeholder_external_resource(resource_id, is_cross_tenant, "Could not access external resource")
                    if placeholder_resource:
                        resources.append(placeholder_resource)
                        logger.info(f"Added placeholder for external dependency: {placeholder_resource.name} from {placeholder_resource.resource_group} (cross-tenant: {is_cross_tenant})")
                        
                        # Create dependencies to placeholder
                        for resource in resources:
                            if 'external_pls_connections' in resource.properties:
                                for conn in resource.properties['external_pls_connections']:
                                    if conn['id'] == resource_id:
                                        resource.dependencies.append(placeholder_resource.name)
                                        logger.info(f"Added dependency to placeholder: {resource.name} -> {placeholder_resource.name}")
                    else:
                        logger.warning(f"Failed to create placeholder for {resource_id}")
                    
        except Exception as e:
            logger.warning(f"Failed to discover cross-resource-group dependencies: {e}")
    
    def _fetch_external_resource(self, resource_id: str) -> Optional[AzureResource]:
        """Fetch an external resource by its full resource ID.
        
        Args:
            resource_id: Full Azure resource ID.
            
        Returns:
            AzureResource object or None if not found.
        """
        try:
            # Parse resource ID to extract components
            # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
            id_parts = resource_id.split('/')
            if len(id_parts) < 9:
                logger.warning(f"Invalid resource ID format: {resource_id}")
                return None
            
            resource_group = id_parts[4]
            provider = id_parts[6]
            resource_type = id_parts[7]
            resource_name = id_parts[8]
            full_type = f"{provider}/{resource_type}"
            
            logger.debug(f"Fetching external resource: {resource_name} of type {full_type} from RG {resource_group}")
            
            # Use Resource Management API to get the resource details
            # Use appropriate API version based on resource type
            api_version = self._get_api_version_for_resource_type(full_type)
            resource = self.resource_client.resources.get_by_id(
                resource_id, 
                api_version=api_version
            )
            
            azure_resource = AzureResource(
                name=resource.name,
                resource_type=full_type,
                category=self._extract_category(full_type),
                location=resource.location,
                resource_group=resource_group,
                subscription_id=self.subscription_id,
                properties=resource.properties or {},
                tags=resource.tags or {},
                dependencies=[]
            )
            
            # Mark as external dependency for visualization
            azure_resource.properties['is_external_dependency'] = True
            azure_resource.properties['source_resource_id'] = resource_id
            
            return azure_resource
            
        except AzureError as e:
            # Provide more specific error messages for common issues
            error_msg = str(e)
            if "NoRegisteredProviderFound" in error_msg:
                logger.debug(f"External resource {resource_name} ({full_type}) not accessible due to provider registration - creating placeholder")
            elif "ResourceNotFound" in error_msg:
                logger.debug(f"External resource {resource_name} not found - may have been deleted")
            elif "Forbidden" in error_msg or "Unauthorized" in error_msg:
                logger.debug(f"External resource {resource_name} not accessible due to permissions")
            else:
                logger.warning(f"Could not fetch external resource {resource_name} ({full_type}): {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing external resource ID {resource_id}: {e}")
            return None
    
    def _is_cross_tenant_error(self, error_message: str) -> bool:
        """Check if an error message indicates a cross-tenant authentication issue.
        
        Args:
            error_message: The error message to analyze.
            
        Returns:
            True if this appears to be a cross-tenant authentication error.
        """
        cross_tenant_indicators = [
            "InvalidAuthenticationTokenTenant",
            "wrong issuer",
            "does not match the tenant",
            "transferred to another tenant"
        ]
        
        error_lower = error_message.lower()
        return any(indicator.lower() in error_lower for indicator in cross_tenant_indicators)
    
    def _check_cross_tenant_resource(self, resource_id: str) -> bool:
        """Check if a resource is likely in a different tenant by comparing subscription IDs.
        
        Args:
            resource_id: Full Azure resource ID.
            
        Returns:
            True if the resource appears to be in a different subscription (potential cross-tenant).
        """
        try:
            # Extract subscription ID from resource ID
            id_parts = resource_id.split('/')
            if len(id_parts) >= 3 and id_parts[1] == 'subscriptions':
                external_subscription_id = id_parts[2]
                # If the subscription ID is different from our current one, it might be cross-tenant
                return external_subscription_id != self.subscription_id
            return False
        except Exception:
            # If we can't parse the resource ID, assume it might be cross-tenant
            return True
    
    def _create_placeholder_external_resource(self, resource_id: str, is_cross_tenant: bool = False, error_message: str = "") -> Optional[AzureResource]:
        """Create a placeholder resource for external dependencies that can't be fetched.
        
        Args:
            resource_id: Full Azure resource ID.
            is_cross_tenant: Whether this appears to be a cross-tenant access issue.
            error_message: The original error message for debugging.
            
        Returns:
            AzureResource placeholder object or None if ID can't be parsed.
        """
        try:
            # Parse resource ID to extract components
            id_parts = resource_id.split('/')
            if len(id_parts) < 9:
                logger.warning(f"Invalid resource ID format for placeholder: {resource_id}")
                return None
            
            resource_group = id_parts[4]
            provider = id_parts[6]
            resource_type = id_parts[7]
            resource_name = id_parts[8]
            full_type = f"{provider}/{resource_type}"
            
            # Determine location and access note based on cross-tenant status
            if is_cross_tenant:
                location = "external-tenant"
                access_note = "External resource (outside tenant)"
                tenant_note = "This resource is in a different Azure tenant and cannot be accessed"
            else:
                location = "external"
                access_note = "External resource (limited access)"
                tenant_note = "This resource could not be accessed due to permissions"
            
            # Create placeholder resource
            placeholder_resource = AzureResource(
                name=resource_name,
                resource_type=full_type,
                category=self._extract_category(full_type),
                location=location,
                resource_group=resource_group,
                subscription_id=self.subscription_id,
                properties={
                    'is_external_dependency': True,
                    'is_placeholder': True,
                    'is_cross_tenant': is_cross_tenant,
                    'source_resource_id': resource_id,
                    'access_note': access_note,
                    'tenant_note': tenant_note,
                    'error_summary': error_message[:200] if error_message else ""  # Truncated error for reference
                },
                tags={
                    'external_dependency': 'true',
                    'cross_tenant': str(is_cross_tenant).lower(),
                    'access_status': 'placeholder'
                },
                dependencies=[]
            )
            
            return placeholder_resource
            
        except Exception as e:
            logger.warning(f"Error creating placeholder for resource ID {resource_id}: {e}")
            return None

    def _extract_openshift_dns_configuration(self, cluster: AzureResource):
        """Extract DNS configuration from OpenShift cluster and store it in properties.
        
        Args:
            cluster: OpenShift cluster resource to extract DNS configuration from.
        """
        try:
            # Get OpenShift cluster details using Azure CLI (most reliable method)
            import subprocess
            import json
            
            cluster_resource_id = f"/subscriptions/{self.subscription_id}/resourceGroups/{cluster.resource_group}/providers/Microsoft.RedHatOpenShift/OpenShiftClusters/{cluster.name}"
            
            result = subprocess.run([
                'az', 'resource', 'show', 
                '--ids', cluster_resource_id,
                '--query', 'properties',
                '-o', 'json'
            ], capture_output=True, text=True, check=True)
            
            cluster_properties = json.loads(result.stdout)
            
            # Extract DNS domains from cluster configuration
            dns_domains = []
            
            # From API server profile
            if 'apiserverProfile' in cluster_properties and 'url' in cluster_properties['apiserverProfile']:
                api_url = cluster_properties['apiserverProfile']['url']
                # Extract domain from URL: https://api.hypershift-mgmt-hyp01.eastus.aroapp.io:6443/
                if '://' in api_url:
                    domain_part = api_url.split('://')[1].split(':')[0].split('/')[0]
                    dns_domains.append(domain_part)
                    logger.info(f"Extracted API DNS domain for {cluster.name}: {domain_part}")
            
            # From console profile
            if 'consoleProfile' in cluster_properties and 'url' in cluster_properties['consoleProfile']:
                console_url = cluster_properties['consoleProfile']['url']
                # Extract domain from URL: https://console-openshift-console.apps.hypershift-mgmt-hyp01.eastus.aroapp.io/
                if '://' in console_url:
                    domain_part = console_url.split('://')[1].split('/')[0]
                    dns_domains.append(domain_part)
                    logger.info(f"Extracted console DNS domain for {cluster.name}: {domain_part}")
            
            # From cluster profile domain
            if 'clusterProfile' in cluster_properties and 'domain' in cluster_properties['clusterProfile']:
                cluster_domain = cluster_properties['clusterProfile']['domain']
                dns_domains.append(cluster_domain)
                logger.info(f"Extracted cluster domain for {cluster.name}: {cluster_domain}")
            
            # Check for any custom ingress domains or wildcard domains
            if 'ingressProfiles' in cluster_properties:
                for ingress_profile in cluster_properties['ingressProfiles']:
                    if 'domain' in ingress_profile:
                        custom_domain = ingress_profile['domain']
                        dns_domains.append(custom_domain)
                        logger.info(f"Found custom ingress domain for {cluster.name}: {custom_domain}")
                    
                    # Check for wildcard domains in ingress configuration
                    if 'wildcardPolicy' in ingress_profile:
                        logger.info(f"Ingress wildcard policy for {cluster.name}: {ingress_profile['wildcardPolicy']}")
            
            # Store extracted DNS domains in cluster properties
            if dns_domains:
                cluster.properties['openshift_dns_domains'] = list(set(dns_domains))  # Remove duplicates
                logger.info(f"Stored {len(set(dns_domains))} DNS domains for OpenShift cluster {cluster.name}: {list(set(dns_domains))}")
                
                # Also store the cluster's IP endpoints for DNS record matching
                cluster_ips = []
                if 'apiserverProfile' in cluster_properties and 'ip' in cluster_properties['apiserverProfile']:
                    cluster_ips.append(cluster_properties['apiserverProfile']['ip'])
                    
                if 'ingressProfiles' in cluster_properties:
                    for ingress_profile in cluster_properties['ingressProfiles']:
                        if 'ip' in ingress_profile:
                            cluster_ips.append(ingress_profile['ip'])
                            
                if cluster_ips:
                    cluster.properties['openshift_cluster_ips'] = list(set(cluster_ips))
                    logger.info(f"Stored cluster IPs for {cluster.name}: {cluster_ips}")
            else:
                logger.warning(f"No DNS domains found for OpenShift cluster {cluster.name}")
                
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to extract OpenShift DNS configuration for {cluster.name}: {e}")
        except Exception as e:
            logger.warning(f"Error extracting OpenShift DNS configuration for {cluster.name}: {e}")