"""DOT language generation for Graphviz rendering."""

import logging
from typing import Any, Dict, Optional

import networkx as nx

from ..core.models import Direction, Theme, ThemeConfig, VisualizationConfig

logger = logging.getLogger(__name__)


class DOTGenerator:
    """Generates DOT language files from NetworkX graphs."""

    # Theme configurations
    THEMES = {
        Theme.LIGHT: ThemeConfig(
            background_color="white",
            node_color="lightblue",
            edge_color="black",
            font_color="black",
            font_name="Arial",
        ),
        Theme.DARK: ThemeConfig(
            background_color="black",
            node_color="darkgray",
            edge_color="white",
            font_color="black",
            font_name="Arial",
        ),
        Theme.NEON: ThemeConfig(
            background_color="black",
            node_color="cyan",
            edge_color="magenta",
            font_color="yellow",
            font_name="Arial",
        ),
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
        subscription_id: Optional[str] = None,
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
        subscription_title = self._generate_subscription_title(
            subscription_name,
            subscription_id,
        )

        # Generate subgraphs wrapped in a master container
        subgraph_content = self._generate_subgraphs_with_container(graph, subgraphs)

        # Generate standalone nodes (not in subgraphs)
        standalone_nodes = self._generate_standalone_nodes(graph, subgraphs)

        # Generate edges
        edges = self._generate_edges(graph)

        # Generate legend if enabled
        legend = self._generate_legend(graph) if self.config.show_legends else ""

        # Position subscription title above master container (direct connection)
        subscription_positioning = ""
        if subscription_title.strip():
            # Find any node within the master container to connect to
            anchor_node = None
            if 'title_' in subgraph_content:
                import re
                title_matches = re.findall(r'"(title_[^"]+)"', subgraph_content)
                if title_matches:
                    anchor_node = title_matches[0]  # Resource group title

            # If no title, find any resource node
            if not anchor_node and subgraph_content.strip():
                resource_matches = re.findall(r'"([^"]*_[^"]*_[^"]+)"', subgraph_content)
                if resource_matches:
                    anchor_node = resource_matches[0]

            # If no nodes found, find Internet node
            if not anchor_node and 'internet_internet_gateway' in standalone_nodes:
                anchor_node = 'internet_internet_gateway'

            connection_edge = ""
            if anchor_node:
                connection_edge = f'\n    "subscription_title" -> "{anchor_node}" [style=invis, weight=100, minlen=1];'

            subscription_positioning = f'''
    // Position subscription title above master container
    {{rank=min; "subscription_title";}}{connection_edge}
'''

        # Combine all parts with master container
        dot_content = f"""
{header}
{graph_attrs}
{node_defaults}
{edge_defaults}

{subscription_title}

    // Master container encompassing all content
    subgraph cluster_master {{
        label="";
        style="solid";
        color="lightgray";
        margin="10";

{self._indent_content(subgraph_content, 2)}
{self._indent_content(standalone_nodes, 2)}
    }}

{edges}
{subscription_positioning}
{legend}
}}
""".strip()

        logger.info("DOT language generation completed")
        return dot_content

    def _indent_content(self, content: str, spaces: int) -> str:
        """Indent content by the specified number of spaces.

        Args:
            content: Content to indent.
            spaces: Number of spaces to indent.

        Returns:
            Indented content.
        """
        if not content.strip():
            return content

        indent = ' ' * spaces
        lines = content.split('\n')
        indented_lines = []

        for line in lines:
            if line.strip():  # Only indent non-empty lines
                indented_lines.append(indent + line)
            else:
                indented_lines.append(line)  # Keep empty lines as-is

        return '\n'.join(indented_lines)
    def _generate_header(self) -> str:
        """Generate DOT file header."""
        direction_map = {
            Direction.LEFT_TO_RIGHT: "LR",
            Direction.TOP_TO_BOTTOM: "TB",
        }

        rankdir = direction_map.get(self.config.direction, "LR")
        splines = self.config.splines.value

        return "digraph AzureTopology {"

    def _generate_graph_attributes(self) -> str:
        """Generate graph-level attributes."""
        # Use left-to-right for resource group arrangement, vertical stacking handled by invisible edges
        rankdir = "LR"  # Keep RGs horizontal, use invisible edges for vertical stacking within RGs
        splines = self.config.splines.value

        return f"""    // Graph attributes
    rankdir="{rankdir}";
    splines="{splines}";
    bgcolor="{self.theme.background_color}";
    fontname="{self.theme.font_name}";
    fontsize="{self.theme.font_size}";
    fontcolor="{self.theme.font_color}";
    dpi="300";
    concentrate=false;
    compound=true;
    newrank=true;
    ordering="out";
    esep="+15";
    sep="+10";
    nodesep="0.5";
    ranksep="0.4";
    size="12,8!";
    ratio="compress";
    pack="true";
    packmode="clust";"""

    def _generate_node_defaults(self) -> str:
        """Generate default node attributes."""
        return f"""    // Default node attributes
    node [
        shape=box,
        style=filled,
        fillcolor="{self.theme.node_color}",
        fontname="{self.theme.font_name}",
        fontsize="{self.theme.font_size}",
        fontcolor="{self.theme.font_color}",
        color="{self.theme.edge_color}",
        height="1.2",
        width="1.8",
        margin="0.1"
    ];"""
    def _generate_edge_defaults(self) -> str:
        """Generate default edge attributes."""
        return f"""    // Default edge attributes
    edge [
        fontname="{self.theme.font_name}",
        fontsize="8",
        fontcolor="{self.theme.font_color}",
        color="{self.theme.edge_color}"
    ];"""

    def _generate_subscription_title(
        self,
        subscription_name: Optional[str],
        subscription_id: Optional[str],
    ) -> str:
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

        # Use background color to blend subscription box with background
        title_fillcolor = self.theme.background_color  # Match background color
        title_fontcolor = self.theme.font_color

        return f"""    // Subscription Title (compact, minimal padding, background color)
    "subscription_title" [
        label="{title_text}",
        shape="box",
        style="filled",
        fillcolor="{title_fillcolor}",
        fontname="{self.theme.font_name}",
        fontsize="10",
        fontcolor="{title_fontcolor}",
        color="{title_fillcolor}",
        penwidth="0",
        height="0.4",
        width="4.0",
        margin="0.02",
        labeljust="l",
        labelloc="t"
    ];

"""

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
            content.append('        rankdir="LR";')  # Force left-to-right within this subgraph for priority ordering
            content.append('')
            
            # Add nodes in this subgraph with priority ordering
            # Define resource type priority (left to right)
            priority_order = {
                # Column 1: Public connectivity (leftmost)
                'microsoft.network/publicipaddresses': 1,

                # Column 2: Network security groups (after Public IPs)
                'microsoft.network/networksecuritygroups': 2,

                # Column 3: Network interfaces (after NSGs)
                'microsoft.network/networkinterfaces': 3,

                # Column 4: Subnets
                'microsoft.network/virtualnetworks/subnets': 4,

                # Column 5: Virtual Networks (to the right of subnets)
                'microsoft.network/virtualnetworks': 5,

                # Column 6: Compute resources
                'microsoft.compute/virtualmachines': 6,
                'microsoft.compute/virtualmachinescalesets': 6,
                'microsoft.containerservice/managedclusters': 6,
                'microsoft.redhatopenshift/openshiftclusters': 6,

                # Column 7: Storage resources (aligned with their VMs)
                'microsoft.compute/disks': 7,
                'microsoft.storage/storageaccounts': 7,

                # Column 8: Supporting resources
                'microsoft.compute/sshpublickeys': 8,
                'microsoft.managedidentity/userassignedidentities': 8,

                # Column 8: Other resources
                'microsoft.compute/galleries': 8,
                'microsoft.compute/galleries/images': 8,
                'microsoft.compute/galleries/images/versions': 8,
            }

            # Group nodes by priority and sort within each group
            priority_groups = {}
            for node_id in nodes:
                if node_id in graph.nodes:
                    node_data = graph.nodes[node_id]
                    resource_type = node_data.get('resource_type', '').lower()
                    priority = priority_order.get(resource_type, 99)  # Default to end

                    if priority not in priority_groups:
                        priority_groups[priority] = []
                    priority_groups[priority].append((node_id, node_data))

            # Add nodes grouped by priority with rank constraints
            for priority in sorted(priority_groups.keys()):
                group_nodes = priority_groups[priority]

                # Add rank constraint comment
                if len(group_nodes) > 1:
                    content.append(f'        // Priority {priority} resources')

                # Add node definitions
                for node_id, node_data in group_nodes:
                    node_def = self._format_node(node_id, node_data)
                    content.append(f'        {node_def}')

                # Add rank constraint for this priority group (vertical alignment in LR layout)
                if len(group_nodes) > 1:
                    node_ids = [node_id for node_id, _ in group_nodes]
                    content.append(f'        {{rank=same; {"; ".join(f'"{node_id}"' for node_id in node_ids)};}}')
                    content.append('')
            
            content.append('    }')
            content.append('')
            
            subgraph_content.append('\n'.join(content))

        return '\n'.join(subgraph_content)

    def _generate_subgraphs_with_container(
        self,
        graph: nx.DiGraph,
        subgraphs: Dict[str, Dict[str, Any]],
    ) -> str:
        """Generate subgraphs wrapped in a master container for size constraint.

        Args:
            graph: NetworkX directed graph.
            subgraphs: Dictionary of subgraph definitions.

        Returns:
            DOT subgraph definitions wrapped in a master container.
        """
        if not subgraphs:
            return ""

        container_content = [
            "    subgraph cluster_main {",
            '        label="Azure Resources";',
            '        style="dashed";',  # Dashed border container for layout constraint
            '        color="gray";',
            '        margin="2";',
            ''
        ]

        # Generate all the resource group subgraphs inside the container
        for subgraph_name, subgraph_data in subgraphs.items():
            nodes = subgraph_data["nodes"]
            label = subgraph_data.get("label", subgraph_name)
            style = subgraph_data.get("style", "filled")
            fillcolor = subgraph_data.get("fillcolor", "lightgray")

            # Remove "cluster_" prefix if already present to avoid double prefixes
            clean_subgraph_name = subgraph_name.replace("cluster_", "")

            # Create external title node outside the resource group (left-justified)
            title_node_id = f'title_{clean_subgraph_name}'
            container_content.extend([
                f'        // Resource group title (external, left-justified)',
                f'        "{title_node_id}" [',
                f'            label="{label}",',
                f'            shape="plaintext",',
                f'            fontsize="10",',
                f'            fontcolor="{self.theme.font_color}",',
                f'            height="0.3",',
                f'            width="3.0",',
                f'            margin="0",',
                f'            labeljust="l"',
                f'        ];',
                ''
            ])

            container_content.extend([
                f'        subgraph "cluster_{clean_subgraph_name}" {{',
                f'            label="";',  # No label needed since title is external
                f'            style="{style}";',
                f'            fillcolor="{fillcolor}";',
                f'            fontcolor="{self.theme.font_color}";',
                '            rankdir="LR";',
                '            margin="1";',  # Minimal margin since no internal title
                ''
            ])

            # Add nodes in this subgraph with priority ordering
            # Define resource type priority (left to right)
            priority_order = {
                # Column 1: Public connectivity (leftmost)
                'microsoft.network/publicipaddresses': 1,

                # Column 2: Network security groups (after Public IPs)
                'microsoft.network/networksecuritygroups': 2,

                # Column 3: Network interfaces (after NSGs)
                'microsoft.network/networkinterfaces': 3,

                # Column 4: Subnets
                'microsoft.network/virtualnetworks/subnets': 4,

                # Column 5: Virtual Networks (to the right of subnets)
                'microsoft.network/virtualnetworks': 5,

                # Column 6: Compute resources
                'microsoft.compute/virtualmachines': 6,
                'microsoft.compute/virtualmachinescalesets': 6,
                'microsoft.containerservice/managedclusters': 6,
                'microsoft.redhatopenshift/openshiftclusters': 6,

                # Column 7: Storage resources (aligned with their VMs)
                'microsoft.compute/disks': 7,
                'microsoft.storage/storageaccounts': 7,

                # Column 8: Supporting resources
                'microsoft.compute/sshpublickeys': 8,
                'microsoft.managedidentity/userassignedidentities': 8,

                # Column 8: Other resources
                'microsoft.compute/galleries': 8,
                'microsoft.compute/galleries/images': 8,
                'microsoft.compute/galleries/images/versions': 8,
            }

            # Group nodes by priority and sort within each group
            priority_groups = {}
            for node_id in nodes:
                if node_id in graph.nodes:
                    node_data = graph.nodes[node_id]
                    resource_type = node_data.get('resource_type', '').lower()
                    priority = priority_order.get(resource_type, 99)  # Default to end

                    if priority not in priority_groups:
                        priority_groups[priority] = []
                    priority_groups[priority].append((node_id, node_data))

            # Add nodes grouped by priority with rank constraints
            for priority in sorted(priority_groups.keys()):
                group_nodes = priority_groups[priority]

                # Add rank constraint comment for all groups
                container_content.append(f'            // Priority {priority} resources')

                # Add node definitions
                for node_id, node_data in group_nodes:
                    node_def = self._format_node(node_id, node_data)
                    container_content.append(f"            {node_def}")

                # Add rank constraint for this priority group (same rank = same column in LR layout)
                # Skip storage resources as they will be aligned with VMs later
                node_ids = []
                for node_id, node_data in group_nodes:
                    resource_type = node_data.get('resource_type', '').lower()
                    if resource_type not in ['microsoft.compute/disks', 'microsoft.storage/storageaccounts']:
                        node_ids.append(node_id)

                if node_ids:
                    container_content.append(f'            {{rank=same; {"; ".join(f'"{node_id}"' for node_id in node_ids)};}}')
                container_content.append('')

            # Add invisible ordering edges to force left-to-right layout within resource groups
            all_priority_groups = []
            for priority in sorted(priority_groups.keys()):
                group_nodes = priority_groups[priority]
                if group_nodes:
                    # Use the first node from each priority group as representative
                    all_priority_groups.append((priority, group_nodes[0][0]))

            # Position external title to the left and above the resource group
            # This happens outside the subgraph, so we'll handle it after closing the subgraph

            # Create invisible edges between priority groups to enforce left-to-right ordering
            if len(all_priority_groups) > 1:
                container_content.append('')
                container_content.append('            // Invisible ordering edges to force left-to-right layout')
                for i in range(len(all_priority_groups) - 1):
                    current_priority, current_node = all_priority_groups[i]
                    next_priority, next_node = all_priority_groups[i + 1]
                    container_content.append(f'            "{current_node}" -> "{next_node}" [style=invis, weight=100];')

            # Add VM followed immediately by their storage (horizontal alignment)
            container_content.append('')
            container_content.append('            // VM-Storage inline horizontal placement')

            # Find VMs and their corresponding storage resources for alignment
            vm_nodes = []
            storage_nodes = []
            vm_storage_pairs = []

            for priority in sorted(priority_groups.keys()):
                group_nodes = priority_groups[priority]
                for node_id, node_data in group_nodes:
                    resource_type = node_data.get('resource_type', '').lower()
                    if resource_type == 'microsoft.compute/virtualmachines':
                        vm_nodes.append((node_id, node_data))
                    elif resource_type in ['microsoft.compute/disks', 'microsoft.storage/storageaccounts']:
                        storage_nodes.append((node_id, node_data))

            # Create VM -> Storage inline ordering for horizontal alignment
            for vm_node_id, vm_data in vm_nodes:
                vm_name = vm_data.get('name', '').lower()
                aligned_storage = []

                for storage_node_id, storage_data in storage_nodes:
                    storage_name = storage_data.get('name', '').lower()
                    storage_type = storage_data.get('resource_type', '').lower()

                    # Check if storage belongs to this VM
                    vm_clean = vm_name.replace('-', '').replace('_', '').lower()
                    storage_clean = storage_name.replace('-', '').replace('_', '').lower()

                    if (vm_name == storage_name or  # Exact match (RHEL-ansible == RHEL-ansible)
                        vm_clean == storage_clean or  # Clean match (win-ansible == winansible)
                        vm_clean in storage_clean or  # VM name in storage (winansible in winansible8298)
                        storage_clean.startswith(vm_clean) or  # Storage starts with VM name
                        (len(vm_clean) >= 4 and vm_clean[:4] in storage_clean)):  # First 4+ chars match
                        aligned_storage.append(storage_node_id)

                # Create invisible edges to place storage immediately after VM
                if aligned_storage:
                    for storage_node_id in aligned_storage:
                        container_content.append(f'            "{vm_node_id}" -> "{storage_node_id}" [style=invis, weight=1000, minlen=1];')
                    vm_storage_pairs.append((vm_node_id, aligned_storage))

            container_content.extend(['        }', ''])

        # Position all external resource group titles
        container_content.append('')
        container_content.append('        // Position external resource group titles')

        # Collect all title nodes and their associated first resource nodes for positioning
        title_positioning = []
        for subgraph_name, subgraph_data in subgraphs.items():
            clean_subgraph_name = subgraph_name.replace("cluster_", "")
            title_node_id = f'title_{clean_subgraph_name}'

            # Find the first resource in this subgraph for positioning reference
            nodes = subgraph_data['nodes']
            if nodes:
                first_resource_id = None
                for node_id in nodes:
                    if node_id in graph.nodes:
                        # Use same node ID generation logic as elsewhere
                        node_data = graph.nodes[node_id]
                        resource_type_suffix = node_data.get('resource_type', '').split('/')[-1].lower() if '/' in node_data.get('resource_type', '') else node_data.get('resource_type', '').lower()
                        formatted_node_id = f"{node_data.get('category', '').lower()}_{node_data.get('name', '').lower()}_{resource_type_suffix}".replace(' ', '_').replace('-', '_').replace('.', '_')
                        first_resource_id = formatted_node_id
                        break

                if first_resource_id:
                    title_positioning.append((title_node_id, first_resource_id))

        # Add positioning constraints for external titles (left-justified)
        if title_positioning:
            # Group all resource group titles to the left
            title_node_ids = [title_node_id for title_node_id, _ in title_positioning]
            if len(title_node_ids) > 1:
                container_content.append(f'        {{rank=same; {"; ".join(f'"{node_id}"' for node_id in title_node_ids)};}}')

            for title_node_id, first_resource_id in title_positioning:
                # Position title to the left of the resource group with left justification
                container_content.append(f'        "{title_node_id}" -> "{first_resource_id}" [style=invis, weight=100, minlen=1];')

        container_content.append('    }')

        return "\n".join(container_content)

    def _generate_standalone_nodes(
        self,
        graph: nx.DiGraph,
        subgraphs: Dict[str, Dict[str, Any]],
    ) -> str:
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
            subgraph_nodes.update(subgraph_data["nodes"])

        # Generate standalone nodes
        standalone_content = []
        internet_nodes = []

        for node_id, node_data in graph.nodes(data=True):
            if node_id not in subgraph_nodes:
                node_def = self._format_node(node_id, node_data)

                # Special handling for Internet nodes - position them at far left
                if node_data.get('resource_type') == 'Internet/Gateway':
                    internet_nodes.append(f'    {node_def}')
                else:
                    standalone_content.append(f'    {node_def}')

        # Add positioning constraints for Internet nodes (far left, independent)
        result = []
        if internet_nodes:
            result.extend(internet_nodes)
            # Add rank constraint to position Internet nodes at the far left
            internet_node_ids = [node_id for node_id, node_data in graph.nodes(data=True)
                               if node_id not in subgraph_nodes and node_data.get('resource_type') == 'Internet/Gateway']
            if internet_node_ids:
                result.append(f'    // Position Internet nodes at far left (below subscription)')
                result.append(f'    {{rank=same; {"; ".join(f'"{node_id}"' for node_id in internet_node_ids)};}}')

        result.extend(standalone_content)
        return '\n'.join(result)
    def _format_node(self, node_id: str, node_data: Dict[str, Any]) -> str:
        """Format a single node definition with icon support.

        Args:
            node_id: Node identifier.
            node_data: Node attributes.

        Returns:
            DOT node definition with HTML table label containing icon.
        """
        name = node_data.get("name", node_id)
        resource_type = node_data.get("resource_type", "")

        # Check if this is a VM and get power state
        is_vm = resource_type == "Microsoft.Compute/virtualMachines"
        power_state = None
        if is_vm:
            # Power state comes from the node attributes passed from graph builder
            for attr, value in node_data.items():
                if attr == "power_state":
                    power_state = value
                    break

        # Get icon path from icon manager
        from ..icons.icon_manager import IconManager

        icon_manager = IconManager()
        icon_path = icon_manager.get_icon_path(resource_type)

        # Debug logging
        logger.debug(
            f"Node: {name}, Type: {resource_type}, Icon path: {icon_path}, Exists: {icon_path.exists() if icon_path else False}",
        )

        if icon_path and icon_path.exists():
            # Create HTML table label with icon (similar to PowerShell Get-ImageNode)
            escaped_name = (
                name.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            )

            # Format resource type display and power state
            type_display_parts = []
            if self.config.label_verbosity.value >= 2 and resource_type:
                # Check if this resource should hide provider info
                hide_provider = False
                if node_data.get("prop_hide_provider"):
                    hide_provider = True

                if not hide_provider:
                    provider_parts = resource_type.split("/")
                    if len(provider_parts) >= 2:
                        provider = provider_parts[0].replace("Microsoft.", "")
                        type_name = provider_parts[1]
                        type_display_parts.extend(
                            [
                                f'<TR><TD align="right"><FONT POINT-SIZE="9">Provider:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{provider}</FONT></TD></TR>',
                                f'<TR><TD align="right"><FONT POINT-SIZE="9">Type:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{type_name}</FONT></TD></TR>',
                            ],
                        )
                    else:
                        type_display_parts.append(
                            f'<TR><TD align="right"><FONT POINT-SIZE="9">Type:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{resource_type}</FONT></TD></TR>',
                        )
                # If hiding provider, show nothing additional

            # Add power state for VMs (if enabled and available)
            if is_vm and power_state and self.config.show_power_state:
                # Color code the power state
                state_color = "green" if power_state == "running" else "red" if power_state in ["stopped", "deallocated"] else "orange"
                type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">State:</FONT></TD><TD align="left"><FONT POINT-SIZE="9" COLOR="{state_color}"><B>{power_state.upper()}</B></FONT></TD></TR>')

            # Add detailed VM information if available and verbosity is high enough
            if is_vm and self.config.label_verbosity.value >= 2:
                if 'prop_vm_size' in node_data:
                    vm_size = str(node_data['prop_vm_size']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Size:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{vm_size}</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_os_type' in node_data:
                        os_type = str(node_data['prop_os_type']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">OS:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{os_type}</FONT></TD></TR>')
                    if 'prop_os_sku' in node_data:
                        os_sku = str(node_data['prop_os_sku']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">SKU:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{os_sku}</FONT></TD></TR>')
                    if 'prop_os_disk_size_gb' in node_data:
                        disk_size = str(node_data['prop_os_disk_size_gb']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">OS Disk:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{disk_size}GB</FONT></TD></TR>')

            # Add detailed disk information if available and verbosity is high enough
            if resource_type == 'Microsoft.Compute/disks' and self.config.label_verbosity.value >= 2:
                if 'prop_disk_size_gb' in node_data:
                    disk_size = str(node_data['prop_disk_size_gb']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Size:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{disk_size}GB</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_sku' in node_data:
                        sku = str(node_data['prop_sku']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">SKU:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{sku}</FONT></TD></TR>')
                    if 'prop_disk_state' in node_data:
                        disk_state = str(node_data['prop_disk_state']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">State:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{disk_state}</FONT></TD></TR>')

            # Add detailed storage account information if available and verbosity is high enough
            if resource_type == 'Microsoft.Storage/storageAccounts' and self.config.label_verbosity.value >= 2:
                if 'prop_sku' in node_data:
                    sku = str(node_data['prop_sku']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">SKU:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{sku}</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_kind' in node_data:
                        kind = str(node_data['prop_kind']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Kind:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{kind}</FONT></TD></TR>')
                    if 'prop_access_tier' in node_data:
                        access_tier = str(node_data['prop_access_tier']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Tier:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{access_tier}</FONT></TD></TR>')

            # Add detailed network interface information if available and verbosity is high enough
            if resource_type == 'Microsoft.Network/networkInterfaces' and self.config.label_verbosity.value >= 2:
                if 'prop_private_ip' in node_data:
                    private_ip = str(node_data['prop_private_ip']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Private IP:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{private_ip}</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_public_ip_name' in node_data:
                        public_ip_name = str(node_data['prop_public_ip_name']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Public IP:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{public_ip_name}</FONT></TD></TR>')
                    if 'prop_subnet_name' in node_data:
                        subnet_name = str(node_data['prop_subnet_name']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Subnet:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{subnet_name}</FONT></TD></TR>')

            # Add detailed public IP information if available and verbosity is high enough
            if resource_type == 'Microsoft.Network/publicIPAddresses' and self.config.label_verbosity.value >= 2:
                if 'prop_ip_address' in node_data:
                    ip_address = str(node_data['prop_ip_address']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">IP Address:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{ip_address}</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_allocation_method' in node_data:
                        allocation = str(node_data['prop_allocation_method']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Allocation:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{allocation}</FONT></TD></TR>')
                    if 'prop_sku' in node_data:
                        sku = str(node_data['prop_sku']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">SKU:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{sku}</FONT></TD></TR>')

            # Add detailed virtual network information if available and verbosity is high enough
            if resource_type == 'Microsoft.Network/virtualNetworks' and self.config.label_verbosity.value >= 2:
                if 'prop_address_space' in node_data:
                    address_space = str(node_data['prop_address_space']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                    type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Address Space:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{address_space}</FONT></TD></TR>')

                if self.config.label_verbosity.value >= 3:  # DETAILED verbosity
                    if 'prop_subnet_count' in node_data:
                        subnet_count = str(node_data['prop_subnet_count']).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                        type_display_parts.append(f'<TR><TD align="right"><FONT POINT-SIZE="9">Subnets:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{subnet_count}</FONT></TD></TR>')

            # Add detailed NSG information if available and verbosity is high enough
            if resource_type == 'Microsoft.Network/networkSecurityGroups' and self.config.label_verbosity.value >= 2:
                # NSGs could show rule count or associated resources, but we'll keep it simple for now
                pass
            # Add subnet information for private endpoints
            if resource_type == "Microsoft.Network/privateEndpoints":
                # Get subnet information from stored properties
                if "prop_subnet_name" in node_data:
                    subnet_name = (
                        str(node_data["prop_subnet_name"])
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                    )
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Subnet:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{subnet_name}</FONT></TD></TR>',
                    )

                # Show external PLS connections if available
                if "prop_external_pls_connections" in node_data:
                    # Parse the string representation back to list
                    import ast

                    try:
                        ext_connections = ast.literal_eval(
                            node_data["prop_external_pls_connections"],
                        )
                        if isinstance(ext_connections, list):
                            for ext_conn in ext_connections:
                                if isinstance(ext_conn, dict):
                                    ext_name = (
                                        str(ext_conn.get("name", "unknown"))
                                        .replace("<", "&lt;")
                                        .replace(">", "&gt;")
                                        .replace('"', "&quot;")
                                    )
                                    ext_rg = (
                                        str(ext_conn.get("resource_group", "unknown"))
                                        .replace("<", "&lt;")
                                        .replace(">", "&gt;")
                                        .replace('"', "&quot;")
                                    )
                                    type_display_parts.append(
                                        f'<TR><TD align="right"><FONT POINT-SIZE="9">→ PLS:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{ext_name} ({ext_rg})</FONT></TD></TR>',
                                    )
                    except (ValueError, SyntaxError):
                        # If parsing fails, skip external connections display
                        pass

            # Add special information for placeholder resources
            if (
                "prop_is_placeholder" in node_data
                and str(node_data["prop_is_placeholder"]).lower() == "true"
            ):
                is_cross_tenant = (
                    str(node_data.get("prop_is_cross_tenant", "")).lower() == "true"
                )

                # Add access note
                if "prop_access_note" in node_data:
                    access_note = (
                        str(node_data["prop_access_note"])
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                    )
                    note_color = "red" if is_cross_tenant else "orange"
                    type_display_parts.append(
                        f'<TR><TD align="center" colspan="2"><FONT POINT-SIZE="8" COLOR="{note_color}"><I>{access_note}</I></FONT></TD></TR>',
                    )

                # Add tenant-specific note for cross-tenant resources
                if is_cross_tenant and "prop_tenant_note" in node_data:
                    tenant_note = (
                        str(node_data["prop_tenant_note"])
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                    )
                    # Truncate long notes for display
                    if len(tenant_note) > 60:
                        tenant_note = tenant_note[:57] + "..."
                    type_display_parts.append(
                        f'<TR><TD align="center" colspan="2"><FONT POINT-SIZE="7" COLOR="red"><I>{tenant_note}</I></FONT></TD></TR>',
                    )

            # Add address prefix information for subnets
            if resource_type == "Microsoft.Network/virtualNetworks/subnets":
                # Get address prefix from stored properties
                if "prop_address_prefix" in node_data:
                    address_prefix = (
                        str(node_data["prop_address_prefix"])
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                    )
                    if address_prefix != "unknown":
                        type_display_parts.append(
                            f'<TR><TD align="right"><FONT POINT-SIZE="9">CIDR:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{address_prefix}</FONT></TD></TR>',
                        )

            # Add enhanced information for our new features
            # Properties are stored with 'prop_' prefix in node_data

            # Enhanced VM information (size, OS, image)
            if resource_type == "Microsoft.Compute/virtualMachines":
                vm_size = node_data.get("prop_vm_size")
                if vm_size:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Size:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{vm_size}</FONT></TD></TR>',
                    )

                os_type = node_data.get("prop_os_type")
                if os_type:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">OS:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{os_type}</FONT></TD></TR>',
                    )

                # Build image info
                image_offer = node_data.get("prop_image_offer")
                image_sku = node_data.get("prop_image_sku")
                if image_offer and image_sku:
                    if "ubuntu" in image_offer.lower():
                        image_info = f"Ubuntu {image_sku.replace('-LTS', '')}"
                    elif "windows" in image_offer.lower():
                        image_info = f"Windows {image_sku}"
                    else:
                        image_info = f"{image_offer} {image_sku}"

                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Image:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{image_info}</FONT></TD></TR>',
                    )

            # Enhanced disk information (size, SKU, state)
            if resource_type == "Microsoft.Compute/disks":
                disk_size = node_data.get("prop_disk_size_gb")
                sku_name = node_data.get("prop_sku_name")
                if disk_size:
                    size_display = f"{disk_size}GB"
                    if sku_name:
                        # Simplify SKU for display
                        sku_simple = (
                            sku_name.replace("_LRS", "")
                            .replace("Standard", "Std")
                            .replace("Premium", "Prem")
                        )
                        size_display += f" {sku_simple}"
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Size:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{size_display}</FONT></TD></TR>',
                    )

                disk_state = node_data.get("prop_disk_state")
                if disk_state and disk_state != "Unattached":
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">State:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{disk_state}</FONT></TD></TR>',
                    )

                os_type = node_data.get("prop_os_type")
                if os_type:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">OS Type:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{os_type}</FONT></TD></TR>',
                    )

            # Enhanced storage account information (SKU, kind, tier)
            if resource_type == "Microsoft.Storage/storageAccounts":
                sku_name = node_data.get("prop_sku_name")
                if sku_name:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">SKU:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{sku_name}</FONT></TD></TR>',
                    )

                kind = node_data.get("prop_kind")
                if kind and kind != "StorageV2":
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Kind:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{kind}</FONT></TD></TR>',
                    )

                access_tier = node_data.get("prop_access_tier")
                if access_tier:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">Tier:</FONT></TD><TD align="left"><FONT POINT-SIZE="9">{access_tier}</FONT></TD></TR>',
                    )

            # Enhanced public IP information (show IP address)
            if resource_type == "Microsoft.Network/publicIPAddresses":
                ip_address = node_data.get("prop_ipAddress")
                if ip_address:
                    type_display_parts.append(
                        f'<TR><TD align="right"><FONT POINT-SIZE="9">IP:</FONT></TD><TD align="left"><FONT POINT-SIZE="9"><B>{ip_address}</B></FONT></TD></TR>',
                    )

            type_display = "".join(type_display_parts)

            # Use appropriate background color based on theme and cross-tenant status
            is_cross_tenant = (
                str(node_data.get("prop_is_cross_tenant", "")).lower() == "true"
            )
            is_placeholder = (
                str(node_data.get("prop_is_placeholder", "")).lower() == "true"
            )

            if is_cross_tenant and is_placeholder:
                # Special styling for cross-tenant placeholders - subtle but visible colors
                node_fillcolor = (
                    "#ffe6e6" if self.config.theme == Theme.LIGHT else "#4d1a1a"
                )  # Light red/dark red
                penwidth = "2"
                style = "dashed"
                border_color = "red"
            elif is_placeholder:
                # General external placeholder styling - subtle but visible colors
                node_fillcolor = (
                    "#fff2e6" if self.config.theme == Theme.LIGHT else "#4d2d1a"
                )  # Light orange/dark orange
                penwidth = "2"
                style = "dotted"
                border_color = "orange"
            else:
                # Normal styling
                node_fillcolor = (
                    "white" if self.config.theme == Theme.LIGHT else "darkgray"
                )
                penwidth = "1"
                style = "filled"
                border_color = self.theme.edge_color

            # Create HTML table label with minimal padding for compact layout
            html_label = f'<<TABLE border="0" cellborder="0" cellpadding="1" cellspacing="0" BGCOLOR="{node_fillcolor}"><TR><TD ALIGN="center" colspan="2" height="32" width="64"><img src="{icon_path}"/></TD></TR><TR><TD align="center" colspan="2"><B><FONT POINT-SIZE="11">{escaped_name}</FONT></B></TD></TR>{type_display}</TABLE>>'
            # For HTML table labels, we need to use a different approach to show borders
            # Use shape="box" with HTML label for better border control
            attributes = [
                f"label={html_label}",
                f'fillcolor="{node_fillcolor}"',
                'shape="box"',
                f'penwidth="{penwidth}"',
                f'style="{style}"',
                f'color="{border_color}"',  # Border color
                f'fontname="{self.theme.font_name}"',
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
                f'fontcolor="{self.theme.font_color}"',
            ]

        # Add custom attributes (excluding processed ones)
        for attr, value in node_data.items():
            if attr not in [
                "label",
                "shape",
                "style",
                "name",
                "category",
                "resource_type",
                "fillcolor",
                "fontname",
                "fontcolor",
            ]:
                if isinstance(value, str):
                    attributes.append(f'{attr}="{value}"')
                else:
                    attributes.append(f"{attr}={value}")

        attr_string = ", ".join(attributes)
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
            edge_content.append(f"    {edge_def}")

        return "\n".join(edge_content)

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
        if edge_data.get("label"):
            label = edge_data["label"].replace('"', '\\"')
            attributes.append(f'label="{label}"')

        # Let edges participate in layout naturally

        # Add style based on edge type
        edge_type = edge_data.get("edge_type", "association")
        if edge_type == "dependency":
            attributes.append('style="dashed"')
            attributes.append('color="red"')
        else:
            attributes.append('style="solid"')

        # Add custom attributes
        for attr, value in edge_data.items():
            if attr not in ["label", "edge_type"]:
                if isinstance(value, str):
                    attributes.append(f'{attr}="{value}"')
                else:
                    attributes.append(f"{attr}={value}")

        if attributes:
            attr_string = " [" + ", ".join(attributes) + "]"
        else:
            attr_string = ""

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
            data.get("edge_type") == "association"
            for _, _, data in graph.edges(data=True)
        )
        has_dependencies = any(
            data.get("edge_type") == "dependency"
            for _, _, data in graph.edges(data=True)
        )

        if not has_associations and not has_dependencies:
            return ""

        # Use appropriate legend background based on theme
        legend_fillcolor = "white" if self.config.theme == Theme.LIGHT else "gray"
        legend_content = [
            "    // Legend",
            '    subgraph "cluster_legend" {',
            '        label="Legend";',
            '        style="filled";',
            f'        fillcolor="{legend_fillcolor}";',
            f'        fontcolor="{self.theme.font_color}";',
            "",
        ]

        if has_associations:
            legend_content.extend(
                [
                    '        "legend_assoc_src" [label="Resource A", shape=box];',
                    '        "legend_assoc_dst" [label="Resource B", shape=box];',
                    '        "legend_assoc_src" -> "legend_assoc_dst" [label="Associated", style=solid];',
                    "",
                ],
            )

        if has_dependencies:
            legend_content.extend(
                [
                    '        "legend_dep_src" [label="Resource C", shape=box];',
                    '        "legend_dep_dst" [label="Resource D", shape=box];',
                    '        "legend_dep_src" -> "legend_dep_dst" [label="Depends On", style=dashed, color=red];',
                ],
            )

        legend_content.append("    }")

        return "\n".join(legend_content)
