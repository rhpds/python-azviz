"""Graph building and DOT language generation."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import networkx as nx

from ..core.models import (
    AzureResource,
    DependencyType,
    GraphEdge,
    GraphNode,
    LabelVerbosity,
    NetworkTopology,
    ResourceRanking,
    VisualizationConfig,
)

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds NetworkX graphs from Azure resources and network topology."""

    def __init__(self, config: VisualizationConfig):
        """Initialize graph builder with configuration.

        Args:
            config: Visualization configuration.
        """
        self.config = config
        self.graph: nx.DiGraph = nx.DiGraph()
        self.subgraphs: Dict[str, Any] = {}
        self.nodes: List[GraphNode] = []
        self.edges: List[GraphEdge] = []

    def build_graph(
        self,
        resources: List[AzureResource],
        network_topology: NetworkTopology,
    ) -> nx.DiGraph:
        """Build complete graph from resources and network topology.

        Args:
            resources: List of Azure resources.
            network_topology: Network topology information.

        Returns:
            NetworkX directed graph.
        """
        logger.info("Building graph from Azure resources and network topology")

        # Reset graph state
        self.graph.clear()
        self.nodes.clear()
        self.edges.clear()

        # Group resources by type and apply filters
        filtered_resources = self._filter_resources(resources)
        grouped_resources = self._group_resources(filtered_resources)

        # Create nodes for resources
        self._create_resource_nodes(grouped_resources)

        # Create edges from network topology
        self._create_network_edges(network_topology, filtered_resources)

        # Create dependency edges
        self._create_dependency_edges(filtered_resources)

        # Add nodes and edges to NetworkX graph
        self._populate_networkx_graph()

        # Create hierarchical subgraphs
        self._create_subgraphs(filtered_resources, network_topology)

        logger.info(
            f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges",
        )
        return self.graph

    def _filter_resources(self, resources: List[AzureResource]) -> List[AzureResource]:
        """Filter resources based on exclusion patterns and compute-only mode.

        Args:
            resources: List of Azure resources.

        Returns:
            Filtered list of resources.
        """
        # First apply compute-only filtering if enabled
        if self.config.compute_only:
            filtered = self._filter_compute_only(resources)
        else:
            filtered = resources

        # Then apply exclusion patterns
        if self.config.exclude_types:
            final_filtered = []
            for resource in filtered:
                excluded = False
                for exclude_pattern in self.config.exclude_types:
                    if self._matches_pattern(resource.resource_type, exclude_pattern):
                        excluded = True
                        break

                if not excluded:
                    final_filtered.append(resource)
            filtered = final_filtered

        logger.info(
            f"Filtered {len(resources)} resources to {len(filtered)} after filtering",
        )
        return filtered

    def _filter_compute_only(
        self,
        resources: List[AzureResource],
    ) -> List[AzureResource]:
        """Filter to show only compute resources and their directly related resources.

        Args:
            resources: List of Azure resources.

        Returns:
            Filtered list of compute and related resources.
        """
        logger.info("Applying compute-only filter")

        # Define compute resource types
        compute_resource_types = {
            "microsoft.compute/virtualmachines",
            "microsoft.compute/virtualmachinescalesets",
            "microsoft.compute/disks",
            "microsoft.compute/snapshots",
            "microsoft.compute/sshpublickeys",
            "microsoft.compute/galleries",
            "microsoft.compute/galleries/images",
            "microsoft.compute/galleries/images/versions",
            "microsoft.containerservice/managedclusters",  # AKS clusters
            "microsoft.redhatopenshift/openshiftclusters",  # OpenShift clusters
        }

        # Define directly related resource types (networking, storage, identity needed for compute)
        compute_related_types = {
            "microsoft.network/networkinterfaces",
            "microsoft.network/publicipaddresses",
            "microsoft.network/virtualnetworks",
            "microsoft.network/virtualnetworks/subnets",
            "microsoft.network/networksecuritygroups",
            "microsoft.network/loadbalancers",
            "microsoft.storage/storageaccounts",
            "microsoft.managedidentity/userassignedidentities",
        }

        # Collect compute resources
        compute_resources = []
        compute_resource_names = set()

        for resource in resources:
            if resource.resource_type.lower() in compute_resource_types:
                compute_resources.append(resource)
                compute_resource_names.add(resource.name)

        if not compute_resources:
            logger.warning("No compute resources found in resource groups")
            return []

        # Collect directly related resources
        related_resources = []
        related_resource_names = set()

        # Get resources that compute resources depend on
        for compute_resource in compute_resources:
            for dependency in compute_resource.get_dependency_names():
                for resource in resources:
                    if (
                        resource.name == dependency
                        and resource.resource_type.lower() in compute_related_types
                        and resource.name not in related_resource_names
                    ):
                        related_resources.append(resource)
                        related_resource_names.add(resource.name)

        # Get resources that depend on compute resources (reverse lookup)
        for resource in resources:
            if (
                resource.resource_type.lower() in compute_related_types
                and resource.name not in related_resource_names
            ):
                # Check if this resource depends on any compute resource
                for dependency in resource.get_dependency_names():
                    if dependency in compute_resource_names:
                        related_resources.append(resource)
                        related_resource_names.add(resource.name)
                        break

        # Also include network interfaces that are attached to compute resources
        for resource in resources:
            if (
                resource.resource_type.lower() == "microsoft.network/networkinterfaces"
                and resource.name not in related_resource_names
            ):
                # Check if any compute resource depends on this NIC
                for compute_resource in compute_resources:
                    for dependency in compute_resource.get_dependency_names():
                        if dependency == resource.name:
                            related_resources.append(resource)
                            related_resource_names.add(resource.name)
                            break

        # Include VNets and subnets that contain the related network interfaces
        for nic in related_resources:
            if nic.resource_type.lower() == "microsoft.network/networkinterfaces":
                for dependency in nic.get_dependency_names():
                    for resource in resources:
                        if (
                            resource.name == dependency
                            and resource.resource_type.lower()
                            in {
                                "microsoft.network/virtualnetworks",
                                "microsoft.network/virtualnetworks/subnets",
                            }
                            and resource.name not in related_resource_names
                        ):
                            related_resources.append(resource)
                            related_resource_names.add(resource.name)

        # Combine compute and related resources
        filtered_resources = compute_resources + related_resources

        logger.info(
            f"Compute-only filter: found {len(compute_resources)} compute resources and {len(related_resources)} related resources",
        )
        return filtered_resources

    def _matches_pattern(self, resource_type: str, pattern: str) -> bool:
        """Check if resource type matches exclusion pattern.

        Args:
            resource_type: Azure resource type.
            pattern: Exclusion pattern (supports wildcards).

        Returns:
            True if resource type matches pattern.
        """
        # Simple wildcard matching
        if "*" in pattern:
            pattern_parts = pattern.lower().split("*")
            resource_type_lower = resource_type.lower()

            if len(pattern_parts) == 1:
                return pattern_parts[0] in resource_type_lower

            # Check if starts with first part and ends with last part
            if len(pattern_parts) == 2:
                start, end = pattern_parts
                return resource_type_lower.startswith(
                    start,
                ) and resource_type_lower.endswith(end)

        return resource_type.lower() == pattern.lower()

    def _group_resources(
        self,
        resources: List[AzureResource],
    ) -> Dict[str, List[AzureResource]]:
        """Group resources by category or type.

        Args:
            resources: List of Azure resources.

        Returns:
            Dictionary of grouped resources.
        """
        grouped = defaultdict(list)

        for resource in resources:
            # Group by category if depth is 1, otherwise by full type
            if self.config.category_depth == 1:
                key = resource.category
            else:
                key = resource.resource_type

            grouped[key].append(resource)

        return dict(grouped)

    def _create_resource_nodes(
        self, grouped_resources: Dict[str, List[AzureResource]]
    ) -> None:
        """Create graph nodes from grouped resources.

        Args:
            grouped_resources: Dictionary of grouped resources.
        """
        for group_key, group_resources in grouped_resources.items():
            # Create a single node for the group if grouping by category
            if self.config.category_depth == 1 and len(group_resources) > 1:
                node = self._create_group_node(group_key, group_resources)
                self.nodes.append(node)
            else:
                # Create individual nodes for each resource
                for resource in group_resources:
                    node = self._create_resource_node(resource)
                    self.nodes.append(node)

    def _create_group_node(
        self,
        group_key: str,
        resources: List[AzureResource],
    ) -> GraphNode:
        """Create a group node representing multiple resources.

        Args:
            group_key: Group identifier.
            resources: List of resources in the group.

        Returns:
            GraphNode representing the group.
        """
        resource_names = [r.name for r in resources]
        label = self._build_node_label(
            group_key,
            resource_names,
            resources[0].category,
            group_key,
        )

        return GraphNode(
            id=f"group_{group_key.lower().replace('.', '_').replace('/', '_')}",
            name=group_key,
            label=label,
            category=resources[0].category,
            resource_type=group_key,
            attributes={
                "resource_count": len(resources),
                "resources": resource_names,
                "shape": "box",
                "style": "filled",
            },
        )

    def _create_resource_node(self, resource: AzureResource) -> GraphNode:
        """Create a graph node from an Azure resource.

        Args:
            resource: Azure resource.

        Returns:
            GraphNode representing the resource.
        """
        node_id = (
            f"{resource.category.lower()}_{resource.name.lower()}".replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
        )
        label = self._build_node_label(
            resource.name,
            [resource.name],
            resource.category,
            resource.resource_type,
        )

        # Include power state for VMs if available
        attributes = {
            "resource_group": resource.resource_group,
            "location": resource.location,
            "ranking": ResourceRanking.get_rank(resource.resource_type),
            "shape": "box",
            "style": "filled",
        }

        # Add power state for VMs
        if (
            resource.resource_type == "Microsoft.Compute/virtualMachines"
            and "power_state" in resource.properties
        ):
            attributes["power_state"] = resource.properties["power_state"]

        # Pass through safe properties for use in DOT generation
        if resource.properties:
            # Only pass simple properties that won't cause DOT syntax issues
            safe_props = {}
            for key, value in resource.properties.items():
                if isinstance(value, (str, int, float, bool)):
                    safe_props[key] = value
                elif isinstance(value, list) and all(
                    isinstance(item, dict) for item in value
                ):
                    # Handle list of dictionaries (like external_pls_connections)
                    safe_props[key] = str(value)  # Convert to string for safe handling
            attributes["properties"] = safe_props

        return GraphNode(
            id=node_id,
            name=resource.name,
            label=label,
            category=resource.category,
            resource_type=resource.resource_type,
            attributes=attributes,
        )

    def _build_node_label(
        self,
        name: str,
        resource_names: List[str],
        category: str,
        resource_type: Optional[str] = None,
    ) -> str:
        """Build node label based on verbosity settings.

        Args:
            name: Primary name for the node.
            resource_names: List of resource names.
            category: Resource category.
            resource_type: Optional resource type for specialized labeling.

        Returns:
            Formatted label string.
        """
        # Special handling for SSH public keys
        if resource_type and resource_type.lower() == "microsoft.compute/sshpublickeys":
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name}\\n(SSH Public Key)"
            # DETAILED
            return f"{name}\\n(SSH Public Key)\\nAuthentication Credential"

        # Special handling for Azure Compute Gallery resources
        if resource_type and resource_type.lower() == "microsoft.compute/galleries":
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name}\\n(Compute Gallery)"
            # DETAILED
            return f"{name}\\n(Compute Gallery)\\nImage Repository"

        if (
            resource_type
            and resource_type.lower() == "microsoft.compute/galleries/images"
        ):
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name.split("/")[-1]  # Show just the image name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name.split('/')[-1]}\\n(Gallery Image)"
            # DETAILED
            return f"{name.split('/')[-1]}\\n(Gallery Image)\\nImage Definition"

        if (
            resource_type
            and resource_type.lower() == "microsoft.compute/galleries/images/versions"
        ):
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name.split("/")[-1]  # Show just the version
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"v{name.split('/')[-1]}\\n(Image Version)"
            # DETAILED
            return f"v{name.split('/')[-1]}\\n(Image Version)\\nVersioned Image"

        # Special handling for Managed Identity resources
        if (
            resource_type
            and resource_type.lower()
            == "microsoft.managedidentity/userassignedidentities"
        ):
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name}\\n(Managed Identity)"
            # DETAILED
            return f"{name}\\n(Managed Identity)\\nAuthentication Service"

        # Special handling for Private DNS Zone resources
        if (
            resource_type
            and resource_type.lower() == "microsoft.network/privatednszones"
        ):
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name}\\n(Private DNS Zone)"
            # DETAILED
            return f"{name}\\n(Private DNS Zone)\\nInternal DNS Resolution"

        if (
            resource_type
            and resource_type.lower()
            == "microsoft.network/privatednszones/virtualnetworklinks"
        ):
            if self.config.label_verbosity == LabelVerbosity.MINIMAL:
                return name.split("/")[-1]  # Show just the link name
            if self.config.label_verbosity == LabelVerbosity.STANDARD:
                return f"{name.split('/')[-1]}\\n(VNet Link)"
            # DETAILED
            return f"{name.split('/')[-1]}\\n(VNet Link)\\nDNS-VNet Connection"

        # Standard labeling for other resources
        if self.config.label_verbosity == LabelVerbosity.MINIMAL:
            return name
        if self.config.label_verbosity == LabelVerbosity.STANDARD:
            return f"{name}\\n({category})"
        if len(resource_names) > 1:
            return f"{name}\\n({category})\\n{len(resource_names)} resources"
        return f"{name}\\n({category})"

    def _create_network_edges(
        self,
        network_topology: NetworkTopology,
        resources: List[AzureResource],
    ) -> None:
        """Create edges from network topology associations.

        Args:
            network_topology: Network topology information.
            resources: List of Azure resources.
        """
        resource_by_id = {r.name: r for r in resources}

        for association in network_topology.associations:
            source_name = self._extract_resource_name_from_id(association["source_id"])
            target_name = self._extract_resource_name_from_id(association["target_id"])

            # Only create edges for resources we have
            if source_name in resource_by_id and target_name in resource_by_id:
                source_resource = resource_by_id[source_name]
                target_resource = resource_by_id[target_name]

                edge = GraphEdge(
                    source=f"{source_resource.category.lower()}_{source_name.lower()}".replace(
                        " ",
                        "_",
                    )
                    .replace("-", "_")
                    .replace(".", "_"),
                    target=f"{target_resource.category.lower()}_{target_name.lower()}".replace(
                        " ",
                        "_",
                    )
                    .replace("-", "_")
                    .replace(".", "_"),
                    label=association.get("association_type", ""),
                    edge_type="association",
                    attributes={
                        "style": "solid",
                        "color": "blue",
                    },
                )
                self.edges.append(edge)

    def _create_dependency_edges(self, resources: List[AzureResource]) -> None:
        """Create edges for resource dependencies.

        Args:
            resources: List of Azure resources.
        """
        resource_by_name = {r.name: r for r in resources}

        # First, create DNS zone connections to infrastructure they serve
        self._create_dns_zone_connections(resources, resource_by_name)

        for resource in resources:
            for dependency in resource.dependencies:
                # Handle both old string format and new ResourceDependency format
                if isinstance(dependency, str):
                    dep_name = dependency
                    dependency_type = DependencyType.EXPLICIT
                    description = None
                else:
                    dep_name = dependency.target_name
                    dependency_type = dependency.dependency_type
                    description = dependency.description

                if dep_name in resource_by_name:
                    dep_resource = resource_by_name[dep_name]

                    # For VM-disk dependencies, create a stronger visual connection
                    if (
                        resource.resource_type == "Microsoft.Compute/virtualMachines"
                        and dep_resource.resource_type == "Microsoft.Compute/disks"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkgreen",
                            "penwidth": "2",
                            "weight": "10",  # Higher weight for stronger positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "attached"
                    # For private endpoint-NIC dependencies, create a connection to show attachment
                    elif (
                        resource.resource_type == "Microsoft.Network/privateEndpoints"
                        and dep_resource.resource_type
                        == "Microsoft.Network/networkInterfaces"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "purple",
                            "penwidth": "2",
                            "weight": "8",  # High weight for stronger positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses"
                    # For private link service-NIC dependencies, create a connection to show attachment
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/privateLinkServices"
                        and dep_resource.resource_type
                        == "Microsoft.Network/networkInterfaces"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "orange",
                            "penwidth": "2",
                            "weight": "8",  # High weight for stronger positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses"
                    # For private link service-load balancer dependencies, create a connection to show backend relationship
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/privateLinkServices"
                        and dep_resource.resource_type
                        == "Microsoft.Network/loadBalancers"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "blue",
                            "penwidth": "2",
                            "weight": "9",  # High weight for stronger positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "fronts"
                    # For private endpoint-subnet dependencies, create a connection to show placement
                    elif (
                        resource.resource_type == "Microsoft.Network/privateEndpoints"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "cyan",
                            "penwidth": "2",
                            "weight": "5",  # Medium weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "deployed in"
                    # For NIC-subnet dependencies, create a connection to show placement
                    elif (
                        resource.resource_type == "Microsoft.Network/networkInterfaces"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                    ):
                        # Use different edge routing to prevent overlapping connections
                        edge_attrs = {
                            "style": "dashed",
                            "color": "lime",
                            "penwidth": "2",
                            "weight": "3",  # Lower weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                            "constraint": "true",  # Keep hierarchical constraints
                        }
                        label = "in"
                    # For Internet-public IP dependencies, create a connection to show external access
                    elif (
                        resource.resource_type == "Internet/Gateway"
                        and dep_resource.resource_type
                        == "Microsoft.Network/publicIPAddresses"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "yellow",
                            "penwidth": "3",
                            "weight": "10",  # High weight for positioning at top
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "provides"
                    # For NSG-subnet dependencies, create a connection to show security application
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/networkSecurityGroups"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "red",
                            "penwidth": "2",
                            "weight": "7",  # High weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "secures"
                    # For VM-storage account dependencies, create a connection to show storage usage
                    elif (
                        resource.resource_type == "Microsoft.Compute/virtualMachines"
                        and dep_resource.resource_type
                        == "Microsoft.Storage/storageAccounts"
                    ):
                        # Check if this is a derived connection and style accordingly
                        if dependency_type == DependencyType.DERIVED:
                            edge_attrs = {
                                "style": "dotted",
                                "color": "orange",
                                "penwidth": "2",
                                "weight": "3",  # Lower weight for derived connections
                                "minlen": "1",
                            }
                            # Create a more descriptive label for derived connections
                            if description:
                                label = f"derived storage ({description})"
                            else:
                                label = "derived storage"
                        else:
                            edge_attrs = {
                                "style": "dashed",
                                "color": "brown",
                                "penwidth": "2",
                                "weight": "4",  # Medium weight for positioning
                                "minlen": "1",  # Minimum length for closer positioning
                            }
                            label = "stores data"
                    # For VNet-subnet dependencies, create a connection to show containment
                    elif (
                        resource.resource_type == "Microsoft.Network/virtualNetworks"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                    ) or (
                        resource.resource_type == "Microsoft.Network/virtualNetworks"
                        and dep_resource.resource_type
                        == "Microsoft.Network/privateEndpoints"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkblue",
                            "penwidth": "2",
                            "weight": "8",  # High weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "contains"
                    # For OpenShift cluster-subnet dependencies, create a connection to show deployment
                    elif (
                        resource.resource_type
                        == "Microsoft.RedHatOpenShift/OpenShiftClusters"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkred",
                            "penwidth": "3",
                            "weight": "9",  # High weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "deployed in"
                    # For OpenShift cluster-VNet dependencies, create a connection to show network usage
                    elif (
                        resource.resource_type
                        == "Microsoft.RedHatOpenShift/OpenShiftClusters"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkred",
                            "penwidth": "3",
                            "weight": "9",  # High weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses network"
                    # For OpenShift cluster-storage dependencies, create a connection to show storage usage
                    elif (
                        resource.resource_type
                        == "Microsoft.RedHatOpenShift/OpenShiftClusters"
                        and dep_resource.resource_type
                        == "Microsoft.Storage/storageAccounts"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkred",
                            "penwidth": "2",
                            "weight": "6",  # Medium-high weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses storage"
                    # For VM-SSH key dependencies, create a connection to show authentication
                    elif (
                        resource.resource_type == "Microsoft.Compute/virtualMachines"
                        and dep_resource.resource_type
                        == "Microsoft.Compute/sshPublicKeys"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "gold",
                            "penwidth": "2",
                            "weight": "7",  # High weight for positioning close to VMs
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "authenticates"
                    # For gallery hierarchy dependencies, create containment connections
                    elif (
                        resource.resource_type == "Microsoft.Compute/galleries/images"
                        and dep_resource.resource_type == "Microsoft.Compute/galleries"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "purple",
                            "penwidth": "2",
                            "weight": "8",  # High weight for hierarchical positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "contained in"
                    elif (
                        resource.resource_type
                        == "Microsoft.Compute/galleries/images/versions"
                        and dep_resource.resource_type
                        == "Microsoft.Compute/galleries/images"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "purple",
                            "penwidth": "2",
                            "weight": "8",  # High weight for hierarchical positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "version of"
                    # For managed identity dependencies, create identity connections
                    elif (
                        resource.resource_type
                        in [
                            "Microsoft.Compute/virtualMachines",
                            "Microsoft.Compute/virtualMachineScaleSets",
                            "Microsoft.ContainerService/managedClusters",
                            "Microsoft.RedHatOpenShift/OpenShiftClusters",
                            "Microsoft.Web/sites",
                        ]
                        and dep_resource.resource_type
                        == "Microsoft.ManagedIdentity/userAssignedIdentities"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "teal",
                            "penwidth": "2",
                            "weight": "6",  # Medium-high weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses identity"
                    # For Private DNS Zone dependencies, create DNS resolution connections
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/privateDnsZones/virtualNetworkLinks"
                        and dep_resource.resource_type
                        == "Microsoft.Network/privateDnsZones"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkgreen",
                            "penwidth": "2",
                            "weight": "8",  # High weight for hierarchical positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "links to"
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/privateDnsZones/virtualNetworkLinks"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "darkgreen",
                            "penwidth": "2",
                            "weight": "7",  # High weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "connects to"
                    elif (
                        resource.resource_type == "Microsoft.Network/privateDnsZones"
                        and dep_resource.resource_type
                        == "Microsoft.Network/virtualNetworks"
                    ):
                        edge_attrs = {
                            "style": "dashed",
                            "color": "darkgreen",
                            "penwidth": "2",
                            "weight": "5",  # Medium weight for positioning
                            "minlen": "2",  # Allow some distance for clarity
                        }
                        label = "provides DNS for"
                    # For route table dependencies, create routing control connections
                    elif (
                        resource.resource_type
                        == "Microsoft.Network/virtualNetworks/subnets"
                        and dep_resource.resource_type
                        == "Microsoft.Network/routeTables"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "orange",
                            "penwidth": "2",
                            "weight": "6",  # Medium-high weight for positioning
                            "minlen": "1",  # Minimum length for closer positioning
                        }
                        label = "uses routing"
                    # For DNS zone dependencies, create DNS resolution connections
                    elif (
                        resource.resource_type == "Microsoft.Network/dnszones"
                        and dep_resource.resource_type
                        == "Microsoft.Network/loadBalancers"
                    ) or (
                        resource.resource_type == "Microsoft.Network/dnszones"
                        and dep_resource.resource_type
                        == "Microsoft.Network/publicIPAddresses"
                    ):
                        edge_attrs = {
                            "style": "solid",
                            "color": "navy",
                            "penwidth": "2",
                            "weight": "5",  # Medium weight for DNS connections
                            "minlen": "2",  # Allow some distance for clarity
                        }
                        label = "resolves to"
                    elif (
                        resource.resource_type == "Microsoft.Network/dnszones"
                        and dep_resource.resource_type
                        == "Microsoft.Compute/virtualMachines"
                    ):
                        edge_attrs = {
                            "style": "dashed",
                            "color": "navy",
                            "penwidth": "2",
                            "weight": "4",  # Lower weight for VM connections
                            "minlen": "2",  # Allow some distance for clarity
                        }
                        label = "serves API for"
                    # Check if this is a derived dependency and style accordingly
                    elif dependency_type == DependencyType.DERIVED:
                        edge_attrs = {
                            "style": "dotted",
                            "color": "orange",
                            "penwidth": "1",
                        }
                        # Create a more descriptive label for derived connections
                        if description:
                            label = f"derived ({description})"
                        else:
                            label = "derived"
                    else:
                        edge_attrs = {
                            "style": "dashed",
                            "color": "red",
                        }
                        label = "depends on"

                    edge = GraphEdge(
                        source=f"{resource.category.lower()}_{resource.name.lower()}".replace(
                            " ",
                            "_",
                        )
                        .replace("-", "_")
                        .replace(".", "_"),
                        target=f"{dep_resource.category.lower()}_{dep_name.lower()}".replace(
                            " ",
                            "_",
                        )
                        .replace("-", "_")
                        .replace(".", "_"),
                        label=label,
                        edge_type="dependency",
                        attributes=edge_attrs,
                    )
                    self.edges.append(edge)

    def _create_dns_zone_connections(
        self,
        resources: List[AzureResource],
        resource_by_name: Dict[str, AzureResource],
    ) -> None:
        """Create connections from DNS zones to infrastructure they serve.

        Args:
            resources: List of Azure resources.
            resource_by_name: Dictionary mapping resource names to resources.
        """
        # Find DNS zones
        dns_zones = [
            r for r in resources if r.resource_type == "Microsoft.Network/dnszones"
        ]

        for dns_zone in dns_zones:
            # Extract the base name from DNS zone (e.g., "hj9nb" from "hj9nb.azure.redhatworkshops.io")
            zone_name_parts = dns_zone.name.split(".")
            if zone_name_parts:
                base_name = zone_name_parts[0]

                # Find resources that match this naming pattern or have DNS configuration
                matching_resources = []
                for resource in resources:
                    name_matches = False
                    is_pattern_match = False  # Track if this is a derived connection

                    # For OpenShift clusters, check actual DNS configuration and DNS records
                    if (
                        resource.resource_type
                        == "Microsoft.RedHatOpenShift/OpenShiftClusters"
                        and "openshift_dns_domains" in resource.properties
                    ):
                        dns_domains = resource.properties["openshift_dns_domains"]
                        for domain in dns_domains:
                            # Check if DNS zone domain is a parent domain for any cluster domain
                            # e.g., "redhatworkshops.io" would be parent of "hypershift-mgmt-hyp01.eastus.aroapp.io"
                            dns_zone_domain = ".".join(
                                dns_zone.name.split(".")[1:],
                            )  # Skip subdomain part
                            if dns_zone_domain and dns_zone_domain in domain:
                                name_matches = True
                                is_pattern_match = (
                                    False  # This is explicit DNS configuration
                                )
                                logger.info(
                                    f"DNS zone '{dns_zone.name}' serves OpenShift cluster '{resource.name}' domain '{domain}'",
                                )
                                break

                        # Also check if the DNS zone might have custom records pointing to OpenShift cluster IPs
                        if (
                            not name_matches
                            and "openshift_cluster_ips" in resource.properties
                        ):
                            cluster_ips = resource.properties["openshift_cluster_ips"]
                            # Note: We would need to fetch DNS records from the zone to check this
                            # This is a placeholder for future enhancement to check A/CNAME records
                            logger.debug(
                                f"Cluster IPs for potential DNS record matching: {cluster_ips}",
                            )
                    else:
                        # For other resources, use naming pattern matching
                        name_matches = (
                            base_name.lower() in resource.name.lower()
                            or
                            # Look for common patterns between DNS zone and resource names
                            any(
                                part in dns_zone.name.lower()
                                and part in resource.name.lower()
                                for part in ["hypershift", "mgmt"]
                                if len(part) > 3
                            )
                            or
                            # Extract any meaningful parts from DNS zone name and check if they appear in resource name
                            any(
                                part in resource.name.lower()
                                for part in dns_zone.name.lower()
                                .replace(".", " ")
                                .split()
                                if len(part) >= 4 and part.isalnum()
                            )
                        )
                        is_pattern_match = (
                            name_matches  # This is pattern-based matching
                        )

                    if (
                        resource != dns_zone
                        and name_matches
                        and resource.resource_type
                        in [
                            "Microsoft.Network/virtualNetworks",
                            "Microsoft.Compute/virtualMachines",
                            "Microsoft.Network/loadBalancers",
                            "Microsoft.RedHatOpenShift/OpenShiftClusters",
                            "Microsoft.ContainerService/managedClusters",
                        ]
                    ):
                        matching_resources.append((resource, is_pattern_match))

                # Create edges from DNS zone to matching infrastructure
                for resource, is_pattern_match in matching_resources:
                    # Style based on whether this is a pattern match (derived) or explicit configuration
                    if is_pattern_match:
                        edge_attrs = {
                            "style": "dotted",
                            "color": "orange",
                            "penwidth": "2",
                            "weight": "2",  # Lower weight to avoid interfering with main topology
                            "minlen": "2",  # Allow some distance
                        }
                        label = "provides DNS for (derived)"
                    else:
                        edge_attrs = {
                            "style": "dashed",
                            "color": "darkgreen",
                            "penwidth": "2",
                            "weight": "2",  # Lower weight to avoid interfering with main topology
                            "minlen": "2",  # Allow some distance
                        }
                        label = "provides DNS for"

                    edge = GraphEdge(
                        source=f"{dns_zone.category.lower()}_{dns_zone.name.lower()}".replace(
                            " ",
                            "_",
                        )
                        .replace("-", "_")
                        .replace(".", "_"),
                        target=f"{resource.category.lower()}_{resource.name.lower()}".replace(
                            " ",
                            "_",
                        )
                        .replace("-", "_")
                        .replace(".", "_"),
                        label=label,
                        edge_type="dns_service",
                        attributes=edge_attrs,
                    )
                    self.edges.append(edge)

    def _populate_networkx_graph(self) -> None:
        """Add nodes and edges to NetworkX graph."""
        # Add nodes
        for node in self.nodes:
            # Filter out complex objects that NetworkX can't handle
            safe_attributes = {}
            for key, value in node.attributes.items():
                if key != "properties" and not isinstance(value, (dict, list)):
                    safe_attributes[key] = value

            self.graph.add_node(
                node.id,
                **{
                    "label": node.label,
                    "name": node.name,
                    "category": node.category,
                    "resource_type": node.resource_type,
                    **safe_attributes,
                },
            )

            # Store only essential properties for DOT generation to avoid massive node declarations
            if "properties" in node.attributes and isinstance(
                node.attributes["properties"],
                dict,
            ):
                # Define which properties to include in DOT (keep it minimal to avoid huge canvas)
                essential_props = {
                    "is_external_dependency",
                    "is_placeholder",
                    "is_cross_tenant",
                    "access_note",
                    "tenant_note",
                    "hide_provider",
                }

                for prop_key, prop_value in node.attributes["properties"].items():
                    # Only include essential properties and exclude verbose ones
                    if prop_key in essential_props and isinstance(
                        prop_value,
                        (str, int, float, bool),
                    ):
                        self.graph.nodes[node.id][f"prop_{prop_key}"] = prop_value

        # Add edges
        for edge in self.edges:
            self.graph.add_edge(
                edge.source,
                edge.target,
                **{
                    "label": edge.label,
                    "edge_type": edge.edge_type,
                    **edge.attributes,
                },
            )

    def _create_subgraphs(
        self,
        resources: List[AzureResource],
        network_topology: NetworkTopology,
    ) -> None:
        """Create hierarchical subgraphs for layout.

        Args:
            resources: List of Azure resources.
            network_topology: Network topology information.
        """
        # Group by resource group
        rg_groups = defaultdict(list)
        for resource in resources:
            rg_groups[resource.resource_group].append(resource)

        # Create subgraphs for each resource group
        for rg_name, rg_resources in rg_groups.items():
            subgraph_nodes = []
            for resource in rg_resources:
                node_id = (
                    f"{resource.category.lower()}_{resource.name.lower()}".replace(
                        " ",
                        "_",
                    )
                    .replace("-", "_")
                    .replace(".", "_")
                )
                if node_id in self.graph:
                    subgraph_nodes.append(node_id)

            if subgraph_nodes:
                self.subgraphs[f"cluster_{rg_name}"] = {
                    "nodes": subgraph_nodes,
                    "label": rg_name,
                    "style": "filled",
                    "fillcolor": "lightgray",
                    "fontsize": "12",
                }

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
        parts = resource_id.split("/")
        if len(parts) >= 9:
            return parts[-1]  # Last part is the resource name

        return resource_id
