"""Azure service icon management system."""

import logging
from pathlib import Path
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class IconManager:
    """Manages Azure service icons with simple flat structure."""
    
    def __init__(self, icon_directory: Optional[Union[str, Path]] = None):
        """Initialize icon manager.
        
        Args:
            icon_directory: Path to directory containing Azure service icons.
                          If None, uses package icons directory.
        """
        if icon_directory:
            self.icon_directory = Path(icon_directory)
        else:
            # Use package icons directory
            self.icon_directory = Path(__file__).parent / "azure_icons" / "General Service Icons"
        
        # Simple icon mappings based on available icons from original AzViz
        self.icon_mappings = {
            # Compute Services
            "microsoft.compute/virtualmachines": "virtualmachines.png",
            "microsoft.compute/virtualmachinescalesets": "virtualmachinescalesets.png",
            "microsoft.compute/availabilitysets": "AvailabilitySets.png",
            "microsoft.compute/disks": "Disks.png",
            "microsoft.compute/snapshots": "DiskSnapshots.png",
            "microsoft.compute/images": "VMImages.png",
            "microsoft.web/sites": "functions.png",
            "microsoft.servicefabric/clusters": "servicefabric.png",
            
            # Networking Services
            "microsoft.network/virtualnetworks": "virtualnetworks.png",
            "microsoft.network/virtualnetworkgateways": "virtualnetworkgateways.png",
            "microsoft.network/loadbalancers": "LoadBalancers.png",
            "microsoft.network/applicationgateways": "ApplicationGateway.png",
            "microsoft.network/networksecuritygroups": "networksecuritygroups.png",
            "microsoft.network/publicipaddresses": "publicip.png",
            "microsoft.network/routetables": "routetables.png",
            "microsoft.network/trafficmanagerprofiles": "trafficmanagerprofiles.png",
            "microsoft.network/frontdoors": "FrontDoors.png",
            "microsoft.network/connections": "Connections.png",
            "microsoft.network/networkinterfaces": "nic.png",
            "microsoft.network/networkwatchers": "NetworkWatcher.png",
            "microsoft.network/dnszones": "appservices.png",  # Use app services icon for DNS zones
            "microsoft.network/privateendpoints": "Connections.png",  # Private endpoints for connectivity
            "microsoft.network/privatelinkservices": "Connections.png",  # Private Link services for connectivity
            
            # Storage Services
            "microsoft.storage/storageaccounts": "storageaccounts.png",
            
            # Database Services
            "microsoft.sql/servers": "sqlservers.png",
            "microsoft.documentdb/databaseaccounts": "cosmosdb.png",
            "microsoft.cache/redis": "redis.png",
            
            # Container Services
            "microsoft.containerregistry/registries": "ContainerRegistries.png",
            "microsoft.containerinstance/containergroups": "containerinstances.png",
            "microsoft.containerservice/managedclusters": "KubernetesServices.png",
            "microsoft.redhatopenshift/openshiftclusters": "KubernetesServices.png",  # Azure Red Hat OpenShift
            
            # Analytics Services
            "microsoft.databricks/workspaces": "databricks.png",
            "microsoft.datafactory/factories": "DataFactories.png",
            "microsoft.eventhub/namespaces": "EventHubs.png",
            "microsoft.eventhub/clusters": "EventHubClusters.png",
            "microsoft.operationalinsights/workspaces": "LogAnalyticsWorkspaces.png",
            "microsoft.datalakeanalytics/accounts": "DataLakeAnalytics.png",
            
            # Security Services
            "microsoft.keyvault/vaults": "keyvaults.png",
            
            # Management and Governance
            "microsoft.automation/automationaccounts": "automation.png",
            "microsoft.resources/resourcegroups": "ResourceGroups.png",
            "microsoft.resources/subscriptions": "Subscriptions.png",
            
            # Web Services
            "microsoft.web/serverfarms": "appservices.png",
            "microsoft.cdn/profiles": "cdnprofiles.png",
            
            # Monitoring and Diagnostics
            "microsoft.insights/components": "applicationinsights.png",
            
            # Integration Services
            "microsoft.web/connections": "APIConnections.png",
            "microsoft.media/mediaservices": "mediaservices.png",
            "microsoft.appconfiguration/configurationstores": "appconfiguration.png",
            
            # Identity Services
            "microsoft.managedidentity/userassignedidentities": "managedidentities.png",
        }
        
        logger.info(f"IconManager initialized with {len(self.icon_mappings)} icon mappings")
    
    def get_icon_path(self, resource_type: str) -> Optional[Path]:
        """Get icon file path for Azure resource type.
        
        Args:
            resource_type: Azure resource type (e.g., 'Microsoft.Compute/virtualMachines').
            
        Returns:
            Path to icon file, or None if not found.
        """
        # Normalize resource type to lowercase
        normalized_type = resource_type.lower()
        
        # Look up icon filename
        icon_filename = self.icon_mappings.get(normalized_type)
        if not icon_filename:
            logger.debug(f"No icon mapping found for resource type: {resource_type}")
            return None
        
        # Construct full path
        icon_path = self.icon_directory / icon_filename
        
        if icon_path.exists():
            return icon_path
        else:
            logger.warning(f"Icon file not found: {icon_path}")
            return None
    
    def get_available_icons(self) -> Dict[str, str]:
        """Get all available icon mappings.
        
        Returns:
            Dictionary of resource type to icon filename mappings.
        """
        return self.icon_mappings.copy()
    
    def add_custom_mapping(self, resource_type: str, icon_filename: str):
        """Add custom icon mapping.
        
        Args:
            resource_type: Azure resource type.
            icon_filename: Icon filename.
        """
        self.icon_mappings[resource_type.lower()] = icon_filename
        logger.info(f"Added custom icon mapping: {resource_type} -> {icon_filename}")