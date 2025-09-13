"""DOT language generation for Graphviz rendering."""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

import networkx as nx
from jinja2 import Template

from ..core.models import ThemeConfig, Theme, Direction, Splines, VisualizationConfig

logger = logging.getLogger(__name__)


class DOTGenerator:
    """Generates DOT language files from NetworkX graphs."""
    
    # Theme configurations
    THEMES = {
        Theme.LIGHT: ThemeConfig(
            background_color='white',
            node_color='lightblue',
            edge_color='black',
            font_color='black',
            font_name='Arial'
        ),
        Theme.DARK: ThemeConfig(
            background_color='black',
            node_color='darkgray',
            edge_color='white',
            font_color='black',
            font_name='Arial'
        ),
        Theme.NEON: ThemeConfig(
            background_color='black',
            node_color='cyan',
            edge_color='magenta',
            font_color='yellow',
            font_name='Arial'
        )
    }
    
    def __init__(self, config: VisualizationConfig):
        """Initialize DOT generator with configuration.
        
        Args:
            config: Visualization configuration.
        """
        self.config = config
        self.theme = self.THEMES[config.theme]
        
    def generate_dot(
        self, 
        graph: nx.DiGraph, 
        subgraphs: Dict[str, Dict[str, Any]], 
        subscription_name: Optional[str] = None,
        subscription_id: Optional[str] = None
    ) -> str:
        """Generate DOT language string from NetworkX graph.
        
        Args:
            graph: NetworkX directed graph.
            subgraphs: Dictionary of subgraph definitions.
            subscription_name: Azure subscription display name.
            subscription_id: Azure subscription ID.
            
        Returns:
            DOT language string.
        """
        logger.info("Generating DOT language from graph")
        
        # Build DOT components
        header = self._generate_header()
        graph_attrs = self._generate_graph_attributes()
        node_defaults = self._generate_node_defaults()
        edge_defaults = self._generate_edge_defaults()
        
        # Generate subscription title
        subscription_title = self._generate_subscription_title(subscription_name, subscription_id)
        
        # Generate subgraphs
        subgraph_content = self._generate_subgraphs(graph, subgraphs)
        
        # Generate standalone nodes (not in subgraphs)
        standalone_nodes = self._generate_standalone_nodes(graph, subgraphs)
        
        # Generate edges
        edges = self._generate_edges(graph)
        
        # Generate legend if enabled
        legend = self._generate_legend(graph) if self.config.show_legends else ""
        
        # Combine all parts
        dot_content = f"""
{header}
{graph_attrs}
{node_defaults}
{edge_defaults}

{subscription_title}
{subgraph_content}
{standalone_nodes}
{edges}
{legend}
}}
""".strip()
        
        logger.info("DOT language generation completed")
        return dot_content
    
    def _generate_header(self) -> str:
        """Generate DOT file header."""
        direction_map = {
            Direction.LEFT_TO_RIGHT: 'LR',
            Direction.TOP_TO_BOTTOM: 'TB'
        }
        
        rankdir = direction_map.get(self.config.direction, 'LR')
        splines = self.config.splines.value
        
        return f'digraph AzureTopology {{'
    
    def _generate_graph_attributes(self) -> str:
        """Generate graph-level attributes."""
        # Use left-to-right for resource group arrangement, vertical stacking handled by invisible edges
        rankdir = 'LR'  # Keep RGs horizontal, use invisible edges for vertical stacking within RGs
        splines = self.config.splines.value
        
        return f'''    // Graph attributes
    rankdir="{rankdir}";
    splines="{splines}";
    bgcolor="{self.theme.background_color}";
    fontname="{self.theme.font_name}";
    fontsize="{self.theme.font_size}";
    fontcolor="{self.theme.font_color}";
    concentrate=false;
    compound=true;
    newrank=true;
    esep="+25";
    sep="+20";
    nodesep="1.0";
    ranksep="1.5";'''
    
    def _generate_node_defaults(self) -> str:
        """Generate default node attributes."""
        return f'''    // Default node attributes
    node [
        shape=box,
        style=filled,
        fillcolor="{self.theme.node_color}",
        fontname="{self.theme.font_name}",
        fontsize="{self.theme.font_size}",
        fontcolor="{self.theme.font_color}",
        color="{self.theme.edge_color}"
    ];'''
    
    def _generate_edge_defaults(self) -> str:
        """Generate default edge attributes."""
        return f'''    // Default edge attributes
    edge [
        fontname="{self.theme.font_name}",
        fontsize="8",
        fontcolor="{self.theme.font_color}",
        color="{self.theme.edge_color}"
    ];'''
    
    def _generate_subscription_title(self, subscription_name: Optional[str], subscription_id: Optional[str]) -> str:
        """Generate subscription title at the top of the diagram.
        
        Args:
            subscription_name: Azure subscription display name.
            subscription_id: Azure subscription ID.
            
        Returns:
            DOT subscription title definition.
        """
        if not subscription_name and not subscription_id:
            return ""
        
        # Create title text with proper labels
        if subscription_name and subscription_id:
            title_text = f"Subscription Name: {subscription_name}\\nSubscription ID: {subscription_id}"
        elif subscription_name:
            title_text = f"Subscription Name: {subscription_name}"
        else:
            title_text = f"Subscription ID: {subscription_id}"
        
        # Escape special characters for DOT
        title_text = title_text.replace('"', '\\"')
        
        # Use appropriate colors based on theme
        title_fillcolor = "lightblue" if self.config.theme == Theme.LIGHT else "darkblue"
        title_fontcolor = self.theme.font_color
        
        return f'''    // Subscription Title
    "subscription_title" [
        label="{title_text}",
        shape="box",
        style="filled",
        fillcolor="{title_fillcolor}",
        fontname="{self.theme.font_name}",
        fontsize="16",
        fontcolor="{title_fontcolor}",
        color="{self.theme.edge_color}",
        penwidth="2",
        rank="min"
    ];
    
    // Force title to appear at the top
    {{rank="min"; "subscription_title";}}
'''
    
    def _generate_subgraphs(self, graph: nx.DiGraph, subgraphs: Dict[str, Dict[str, Any]]) -> str:
        """Generate subgraph definitions with hybrid layout.
        
        Args:
            graph: NetworkX directed graph.
            subgraphs: Dictionary of subgraph definitions.
            
        Returns:
            DOT subgraph definitions with horizontal RGs and vertical resources.
        """
        subgraph_content = []
        
        for subgraph_name, subgraph_data in subgraphs.items():
            nodes = subgraph_data['nodes']
            label = subgraph_data.get('label', subgraph_name)
            style = subgraph_data.get('style', 'filled')
            fillcolor = subgraph_data.get('fillcolor', 'lightgray')
            
            content = [f'    subgraph "{subgraph_name}" {{']
            content.append(f'        label="{label}";')
            content.append(f'        style="{style}";')
            content.append(f'        fillcolor="{fillcolor}";')
            content.append(f'        fontcolor="{self.theme.font_color}";')
            content.append('        rankdir="TB";')  # Force top-to-bottom within this subgraph
            content.append('')
            
            # Add nodes in this subgraph
            for node_id in nodes:
                if node_id in graph.nodes:
                    node_data = graph.nodes[node_id]
                    node_def = self._format_node(node_id, node_data)
                    content.append(f'        {node_def}')
            
            content.append('    }')
            content.append('')
            
            subgraph_content.append('\n'.join(content))
        
        return '\n'.join(subgraph_content)
    
    def _generate_standalone_nodes(self, graph: nx.DiGraph, subgraphs: Dict[str, Dict[str, Any]]) -> str:
        """Generate nodes that are not part of any subgraph.
        
        Args:
            graph: NetworkX directed graph.
            subgraphs: Dictionary of subgraph definitions.
            
        Returns:
            DOT node definitions.
        """
        # Collect all nodes that are in subgraphs
        subgraph_nodes = set()
        for subgraph_data in subgraphs.values():
            subgraph_nodes.update(subgraph_data['nodes'])
        
        # Generate standalone nodes
        standalone_content = []
        for node_id, node_data in graph.nodes(data=True):
            if node_id not in subgraph_nodes:
                node_def = self._format_node(node_id, node_data)
                standalone_content.append(f'    {node_def}')
        
        return '\n'.join(standalone_content)
    
    def _format_node(self, node_id: str, node_data: Dict[str, Any]) -> str:
        """Format a single node definition with icon support.
        
        Args:
            node_id: Node identifier.
            node_data: Node attributes.
            
        Returns:
            DOT node definition with HTML table label containing icon.
        """
        name = node_data.get('name', node_id)
        resource_type = node_data.get('resource_type', '')
        
        # Check if this is a VM and get power state
        is_vm = resource_type == 'Microsoft.Compute/virtualMachines'
        power_state = None
        if is_vm:
            # Power state comes from the node attributes passed from graph builder
            for attr, value in node_data.items():
                if attr == 'power_state':
                    power_state = value
                    break
        
        # Get icon path from icon manager
        from ..icons.icon_manager import IconManager
        icon_manager = IconManager()
        icon_path = icon_manager.get_icon_path(resource_type)
        
        # Debug logging
        logger.debug(f"Node: {name}, Type: {resource_type}, Icon path: {icon_path}, Exists: {icon_path.exists() if icon_path else False}")
        
        if icon_path and icon_path.exists():
            # Create HTML table label with icon (similar to PowerShell Get-ImageNode)
            escaped_name = name.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Format resource type display and power state
            type_display_parts = []
            if self.config.label_verbosity.value >= 2 and resource_type:
                # Check if this resource should hide provider info
                hide_provider = False
                if 'prop_hide_provider' in node_data and node_data['prop_hide_provider']:
                    hide_provider = True
                
                if not hide_provider:
                    provider_parts = resource_type.split('/')
                    if len(provider_parts) >= 2:
                        provider = provider_parts[0].replace('Microsoft.', '')
                        type_name = provider_parts[1]
                        type_display_parts.extend([
                            f'<TR><TD align="right"><FONT POINT-SIZE="9">Provider:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{provider}</FONT></TD></TR>',
                            f'<TR><TD align="right"><FONT POINT-SIZE="9">Type:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{type_name}</FONT></TD></TR>'
                        ])
                    else:
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Type:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{resource_type}</FONT></TD></TR>')
                # If hiding provider, show nothing additional
            
            # Add power state for VMs (if enabled and available)
            if is_vm and power_state and self.config.show_power_state:
                # Color code the power state
                state_color = "green" if power_state == "running" else "red" if power_state in ["stopped", "deallocated"] else "orange"
                type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">State:</FONT></TD><TD align="left"><FONT POINT-SIZE="9" COLOR="{state_color}"><B>{power_state.upper()}</B></FONT></TD></TR>')
            
            # Add subnet information for private endpoints
            if resource_type == 'Microsoft.Network/privateEndpoints':
                # Get subnet information from stored properties
                if 'prop_subnet_name' in node_data:
                    subnet_name = str(node_data['prop_subnet_name']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Subnet:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{subnet_name}</FONT></TD></TR>')
                
                # Show external PLS connections if available
                if 'prop_external_pls_connections' in node_data:
                    # Parse the string representation back to list
                    import ast
                    try:
                        ext_connections = ast.literal_eval(node_data['prop_external_pls_connections'])
                        if isinstance(ext_connections, list):
                            for ext_conn in ext_connections:
                                if isinstance(ext_conn, dict):
                                    ext_name = str(ext_conn.get('name', 'unknown')).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                                    ext_rg = str(ext_conn.get('resource_group', 'unknown')).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">→ PLS:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{ext_name} ({ext_rg})</FONT></TD></TR>')
                    except (ValueError, SyntaxError):
                        # If parsing fails, skip external connections display
                        pass
            
            # Add special information for placeholder resources
            if 'prop_is_placeholder' in node_data and str(node_data['prop_is_placeholder']).lower() == 'true':
                is_cross_tenant = str(node_data.get('prop_is_cross_tenant', '')).lower() == 'true'
                
                # Add access note
                if 'prop_access_note' in node_data:
                    access_note = str(node_data['prop_access_note']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    note_color = "red" if is_cross_tenant else "orange"
                    type_display_parts.append(f'<TR><TD align="center" colspan="2"><FONT POINT-SIZE="8" COLOR="{note_color}"><I>{access_note}</I></FONT></TD></TR>')
                
                # Add tenant-specific note for cross-tenant resources
                if is_cross_tenant and 'prop_tenant_note' in node_data:
                    tenant_note = str(node_data['prop_tenant_note']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    # Truncate long notes for display
                    if len(tenant_note) > 60:
                        tenant_note = tenant_note[:57] + "..."
                    type_display_parts.append(f'<TR><TD align="center" colspan="2"><FONT POINT-SIZE="7" COLOR="red"><I>{tenant_note}</I></FONT></TD></TR>')
            
            # Add address prefix information for subnets
            if resource_type == 'Microsoft.Network/virtualNetworks/subnets':
                # Get address prefix from stored properties
                if 'prop_address_prefix' in node_data:
                    address_prefix = str(node_data['prop_address_prefix']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    if address_prefix != 'unknown':
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">CIDR:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{address_prefix}</FONT></TD></TR>')
            
            type_display = ''.join(type_display_parts)
            
            # Create HTML table label similar to PowerShell version
            html_label = f'<<TABLE border="0" cellborder="0" cellpadding="0"><TR><TD ALIGN="center" colspan="2"><img src="{icon_path}"/></TD></TR><TR><TD align="center" colspan="2"><B><FONT POINT-SIZE="11">{escaped_name}</FONT></B></TD></TR>{type_display}</TABLE>>'
            
            # Use appropriate background color based on theme and cross-tenant status
            is_cross_tenant = str(node_data.get('prop_is_cross_tenant', '')).lower() == 'true'
            is_placeholder = str(node_data.get('prop_is_placeholder', '')).lower() == 'true'
            
            if is_cross_tenant and is_placeholder:
                # Special styling for cross-tenant placeholders
                node_fillcolor = "#ffe6e6" if self.config.theme == Theme.LIGHT else "#4d1a1a"  # Light red/dark red
                penwidth = "2"
                style = "dashed"
                border_color = "red"
            elif is_placeholder:
                # General external placeholder styling
                node_fillcolor = "#fff2e6" if self.config.theme == Theme.LIGHT else "#4d2d1a"  # Light orange/dark orange
                penwidth = "2"
                style = "dotted"
                border_color = "orange"
            else:
                # Normal styling
                node_fillcolor = "white" if self.config.theme == Theme.LIGHT else "darkgray"
                penwidth = "1"
                style = "filled"
                border_color = self.theme.edge_color
            
            # For HTML table labels, we need to use a different approach to show borders
            # Use shape="box" with HTML label for better border control
            attributes = [
                f'label={html_label}',
                f'fillcolor="{node_fillcolor}"',
                'shape="box"',
                f'penwidth="{penwidth}"',
                f'style="{style}"',
                f'color="{border_color}"',  # Border color
                f'fontname="{self.theme.font_name}"'
            ]
        else:
            # Fallback to simple box node if no icon
            escaped_name = name.replace('"', '\\"')
            attributes = [
                f'label="{escaped_name}"',
                'shape="box"',
                'style="filled"',
                f'fillcolor="{self.theme.node_color}"',
                f'fontname="{self.theme.font_name}"',
                f'fontcolor="{self.theme.font_color}"'
            ]
        
        # Add custom attributes (excluding processed ones)
        for attr, value in node_data.items():
            if attr not in ['label', 'shape', 'style', 'name', 'category', 'resource_type', 'fillcolor', 'fontname', 'fontcolor']:
                if isinstance(value, str):
                    attributes.append(f'{attr}="{value}"')
                else:
                    attributes.append(f'{attr}={value}')
        
        attr_string = ', '.join(attributes)
        return f'"{node_id}" [{attr_string}];'
    
    def _generate_edges(self, graph: nx.DiGraph) -> str:
        """Generate edge definitions.
        
        Args:
            graph: NetworkX directed graph.
            
        Returns:
            DOT edge definitions.
        """
        edge_content = []
        
        for source, target, edge_data in graph.edges(data=True):
            edge_def = self._format_edge(source, target, edge_data)
            edge_content.append(f'    {edge_def}')
        
        return '\n'.join(edge_content)
    
    def _format_edge(self, source: str, target: str, edge_data: Dict[str, Any]) -> str:
        """Format a single edge definition.
        
        Args:
            source: Source node ID.
            target: Target node ID. 
            edge_data: Edge attributes.
            
        Returns:
            DOT edge definition.
        """
        attributes = []
        
        # Add label if present
        if 'label' in edge_data and edge_data['label']:
            label = edge_data['label'].replace('"', '\\"')
            attributes.append(f'label="{label}"')
        
        # Let edges participate in layout naturally
        
        # Add style based on edge type
        edge_type = edge_data.get('edge_type', 'association')
        if edge_type == 'dependency':
            attributes.append('style="dashed"')
            attributes.append('color="red"')
        else:
            attributes.append('style="solid"')
        
        # Add custom attributes
        for attr, value in edge_data.items():
            if attr not in ['label', 'edge_type']:
                if isinstance(value, str):
                    attributes.append(f'{attr}="{value}"')
                else:
                    attributes.append(f'{attr}={value}')
        
        if attributes:
            attr_string = ' [' + ', '.join(attributes) + ']'
        else:
            attr_string = ''
        
        return f'"{source}" -> "{target}"{attr_string};'
    
    def _generate_legend(self, graph: nx.DiGraph) -> str:
        """Generate legend for the diagram.
        
        Args:
            graph: NetworkX directed graph.
            
        Returns:
            DOT legend definition.
        """
        # Check if we have both association and dependency edges
        has_associations = any(
            data.get('edge_type') == 'association' 
            for _, _, data in graph.edges(data=True)
        )
        has_dependencies = any(
            data.get('edge_type') == 'dependency' 
            for _, _, data in graph.edges(data=True)
        )
        
        if not has_associations and not has_dependencies:
            return ""
        
        # Use appropriate legend background based on theme
        legend_fillcolor = "white" if self.config.theme == Theme.LIGHT else "gray"
        legend_content = [
            '    // Legend',
            '    subgraph "cluster_legend" {',
            '        label="Legend";',
            '        style="filled";',
            f'        fillcolor="{legend_fillcolor}";',
            f'        fontcolor="{self.theme.font_color}";',
            ''
        ]
        
        if has_associations:
            legend_content.extend([
                '        "legend_assoc_src" [label="Resource A", shape=box];',
                '        "legend_assoc_dst" [label="Resource B", shape=box];',
                '        "legend_assoc_src" -> "legend_assoc_dst" [label="Associated", style=solid];',
                ''
            ])
        
        if has_dependencies:
            legend_content.extend([
                '        "legend_dep_src" [label="Resource C", shape=box];',
                '        "legend_dep_dst" [label="Resource D", shape=box];',
                '        "legend_dep_src" -> "legend_dep_dst" [label="Depends On", style=dashed, color=red];',
            ])
        
        legend_content.append('    }')
        
        return '\n'.join(legend_content)