"""Graph building and DOT language generation."""

import logging
from typing import Any, Dict, List, Set, Tuple, Optional
from collections import defaultdict

import networkx as nx
from networkx.drawing.nx_agraph import write_dot

from ..core.models import (
    AzureResource, NetworkTopology, GraphNode, GraphEdge, 
    VisualizationConfig, ResourceRanking, LabelVerbosity
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
        self.graph = nx.DiGraph()
        self.subgraphs = {}
        self.nodes = []
        self.edges = []
        
    def build_graph(
        self, 
        resources: List[AzureResource], 
        network_topology: NetworkTopology
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
        
        logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
        return self.graph
    
    def _filter_resources(self, resources: List[AzureResource]) -> List[AzureResource]:
        """Filter resources based on exclusion patterns.
        
        Args:
            resources: List of Azure resources.
            
        Returns:
            Filtered list of resources.
        """
        if not self.config.exclude_types:
            return resources
        
        filtered = []
        for resource in resources:
            excluded = False
            for exclude_pattern in self.config.exclude_types:
                if self._matches_pattern(resource.resource_type, exclude_pattern):
                    excluded = True
                    break
            
            if not excluded:
                filtered.append(resource)
        
        logger.info(f"Filtered {len(resources)} resources to {len(filtered)} after exclusions")
        return filtered
    
    def _matches_pattern(self, resource_type: str, pattern: str) -> bool:
        """Check if resource type matches exclusion pattern.
        
        Args:
            resource_type: Azure resource type.
            pattern: Exclusion pattern (supports wildcards).
            
        Returns:
            True if resource type matches pattern.
        """
        # Simple wildcard matching
        if '*' in pattern:
            pattern_parts = pattern.lower().split('*')
            resource_type_lower = resource_type.lower()
            
            if len(pattern_parts) == 1:
                return pattern_parts[0] in resource_type_lower
            
            # Check if starts with first part and ends with last part
            if len(pattern_parts) == 2:
                start, end = pattern_parts
                return resource_type_lower.startswith(start) and resource_type_lower.endswith(end)
        
        return resource_type.lower() == pattern.lower()
    
    def _group_resources(self, resources: List[AzureResource]) -> Dict[str, List[AzureResource]]:
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
    
    def _create_resource_nodes(self, grouped_resources: Dict[str, List[AzureResource]]):
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
    
    def _create_group_node(self, group_key: str, resources: List[AzureResource]) -> GraphNode:
        """Create a group node representing multiple resources.
        
        Args:
            group_key: Group identifier.
            resources: List of resources in the group.
            
        Returns:
            GraphNode representing the group.
        """
        resource_names = [r.name for r in resources]
        label = self._build_node_label(group_key, resource_names, resources[0].category)
        
        return GraphNode(
            id=f"group_{group_key.lower().replace('.', '_').replace('/', '_')}",
            name=group_key,
            label=label,
            category=resources[0].category,
            resource_type=group_key,
            attributes={
                'resource_count': len(resources),
                'resources': resource_names,
                'shape': 'box',
                'style': 'filled'
            }
        )
    
    def _create_resource_node(self, resource: AzureResource) -> GraphNode:
        """Create a graph node from an Azure resource.
        
        Args:
            resource: Azure resource.
            
        Returns:
            GraphNode representing the resource.
        """
        node_id = f"{resource.category.lower()}_{resource.name.lower()}".replace(' ', '_').replace('-', '_')
        label = self._build_node_label(resource.name, [resource.name], resource.category)
        
        # Include power state for VMs if available
        attributes = {
            'resource_group': resource.resource_group,
            'location': resource.location,
            'ranking': ResourceRanking.get_rank(resource.resource_type),
            'shape': 'box',
            'style': 'filled'
        }
        
        # Add power state for VMs
        if resource.resource_type == 'Microsoft.Compute/virtualMachines' and 'power_state' in resource.properties:
            attributes['power_state'] = resource.properties['power_state']
        
        return GraphNode(
            id=node_id,
            name=resource.name,
            label=label,
            category=resource.category,
            resource_type=resource.resource_type,
            attributes=attributes
        )
    
    def _build_node_label(self, name: str, resource_names: List[str], category: str) -> str:
        """Build node label based on verbosity settings.
        
        Args:
            name: Primary name for the node.
            resource_names: List of resource names.
            category: Resource category.
            
        Returns:
            Formatted label string.
        """
        if self.config.label_verbosity == LabelVerbosity.MINIMAL:
            return name
        elif self.config.label_verbosity == LabelVerbosity.STANDARD:
            return f"{name}\\n({category})"
        else:  # DETAILED
            if len(resource_names) > 1:
                return f"{name}\\n({category})\\n{len(resource_names)} resources"
            else:
                return f"{name}\\n({category})"
    
    def _create_network_edges(self, network_topology: NetworkTopology, resources: List[AzureResource]):
        """Create edges from network topology associations.
        
        Args:
            network_topology: Network topology information.
            resources: List of Azure resources.
        """
        resource_by_id = {r.name: r for r in resources}
        
        for association in network_topology.associations:
            source_name = self._extract_resource_name_from_id(association['source_id'])
            target_name = self._extract_resource_name_from_id(association['target_id'])
            
            # Only create edges for resources we have
            if source_name in resource_by_id and target_name in resource_by_id:
                source_resource = resource_by_id[source_name]
                target_resource = resource_by_id[target_name]
                
                edge = GraphEdge(
                    source=f"{source_resource.category.lower()}_{source_name.lower()}".replace(' ', '_').replace('-', '_'),
                    target=f"{target_resource.category.lower()}_{target_name.lower()}".replace(' ', '_').replace('-', '_'),
                    label=association.get('association_type', ''),
                    edge_type='association',
                    attributes={
                        'style': 'solid',
                        'color': 'blue'
                    }
                )
                self.edges.append(edge)
    
    def _create_dependency_edges(self, resources: List[AzureResource]):
        """Create edges for resource dependencies.
        
        Args:
            resources: List of Azure resources.
        """
        resource_by_name = {r.name: r for r in resources}
        
        for resource in resources:
            for dep_name in resource.dependencies:
                if dep_name in resource_by_name:
                    dep_resource = resource_by_name[dep_name]
                    
                    edge = GraphEdge(
                        source=f"{resource.category.lower()}_{resource.name.lower()}".replace(' ', '_').replace('-', '_'),
                        target=f"{dep_resource.category.lower()}_{dep_name.lower()}".replace(' ', '_').replace('-', '_'),
                        label='depends on',
                        edge_type='dependency',
                        attributes={
                            'style': 'dashed',
                            'color': 'red'
                        }
                    )
                    self.edges.append(edge)
    
    def _populate_networkx_graph(self):
        """Add nodes and edges to NetworkX graph."""
        # Add nodes
        for node in self.nodes:
            self.graph.add_node(node.id, **{
                'label': node.label,
                'name': node.name,
                'category': node.category,
                'resource_type': node.resource_type,
                **node.attributes
            })
        
        # Add edges
        for edge in self.edges:
            self.graph.add_edge(edge.source, edge.target, **{
                'label': edge.label,
                'edge_type': edge.edge_type,
                **edge.attributes
            })
    
    def _create_subgraphs(self, resources: List[AzureResource], network_topology: NetworkTopology):
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
                node_id = f"{resource.category.lower()}_{resource.name.lower()}".replace(' ', '_').replace('-', '_')
                if node_id in self.graph:
                    subgraph_nodes.append(node_id)
            
            if subgraph_nodes:
                self.subgraphs[f"cluster_{rg_name}"] = {
                    'nodes': subgraph_nodes,
                    'label': rg_name,
                    'style': 'filled',
                    'fillcolor': 'lightgray',
                    'fontsize': '12'
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
        parts = resource_id.split('/')
        if len(parts) >= 9:
            return parts[-1]  # Last part is the resource name
        
        return resource_id