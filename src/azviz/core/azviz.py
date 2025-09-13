"""Main AzViz class for generating Azure resource topology diagrams."""

import logging
from typing import List, Optional, Union, Set, Dict, Any
from pathlib import Path

from ..azure import AzureClient
from ..visualization import GraphBuilder, DOTGenerator, GraphRenderer
from ..icons import IconManager
from .models import (
    VisualizationConfig, Theme, OutputFormat, LabelVerbosity, 
    Direction, Splines, AzureResource, NetworkTopology
)

logger = logging.getLogger(__name__)


class AzViz:
    """Main class for Azure resource topology visualization."""
    
    def __init__(
        self, 
        subscription_identifier: Optional[str] = None,
        credential: Optional[Any] = None,
        icon_directory: Optional[Union[str, Path]] = None
    ):
        """Initialize AzViz instance.
        
        Args:
            subscription_identifier: Azure subscription ID or name. If None, uses first available.
            credential: Azure credential object. If None, uses DefaultAzureCredential.
            icon_directory: Path to Azure service icons. If None, uses package icons.
        """
        self.azure_client = AzureClient(subscription_identifier, credential)
        self.icon_manager = IconManager(icon_directory)
        
        # Verify Azure authentication
        if not self.azure_client.test_authentication():
            raise RuntimeError("Azure authentication failed. Please run 'az login' or configure credentials.")
        
        logger.info("AzViz initialized successfully")
    
    def export_diagram(
        self,
        resource_group: Union[str, List[str]],
        output_file: str,
        theme: Theme = Theme.LIGHT,
        output_format: OutputFormat = OutputFormat.PNG,
        label_verbosity: LabelVerbosity = LabelVerbosity.STANDARD,
        category_depth: int = 2,
        direction: Direction = Direction.LEFT_TO_RIGHT,
        splines: Splines = Splines.POLYLINE,
        exclude_types: Optional[Set[str]] = None,
        show_legends: bool = True,
        show_power_state: bool = True,
        save_dot: bool = False
    ) -> Path:
        """Export Azure resource topology diagram.
        
        Args:
            resource_group: Resource group name(s) to visualize. If empty list or None, 
                          visualizes all resource groups in subscription.
            output_file: Output file path.
            theme: Visual theme (light, dark, neon).
            output_format: Output format (PNG, SVG).
            label_verbosity: Label detail level (1-3).
            category_depth: Resource categorization depth (1-3).
            direction: Graph layout direction.
            splines: Edge appearance.
            exclude_types: Resource types to exclude (supports wildcards).
            show_legends: Whether to include legend.
            show_power_state: Whether to show VM power state visualization.
            save_dot: Whether to save DOT source file.
            
        Returns:
            Path to generated diagram file.
        """
        # Normalize resource groups to list
        if isinstance(resource_group, str):
            resource_groups = [resource_group]
        elif resource_group is None or len(resource_group) == 0:
            # Use all resource groups in subscription
            logger.info("No resource groups specified, using all in subscription")
            all_rgs = self.get_available_resource_groups()
            if not all_rgs:
                raise ValueError("No resource groups found in subscription")
            resource_groups = [rg['name'] for rg in all_rgs]
            logger.info(f"Found {len(resource_groups)} resource groups to visualize")
        else:
            resource_groups = list(resource_group)
        
        # Create configuration
        config = VisualizationConfig(
            resource_groups=resource_groups,
            label_verbosity=label_verbosity,
            category_depth=category_depth,
            theme=theme,
            output_format=output_format,
            direction=direction,
            splines=splines,
            exclude_types=exclude_types or set(),
            show_legends=show_legends,
            show_power_state=show_power_state,
            output_file=output_file
        )
        
        logger.info(f"Starting diagram export for resource groups: {resource_groups}")
        
        # Discover resources and network topology
        all_resources = []
        combined_topology = NetworkTopology()
        
        for rg_name in resource_groups:
            logger.info(f"Discovering resources in resource group: {rg_name}")
            
            # Get resources
            resources = self.azure_client.get_resources_in_group(rg_name, config.show_power_state)
            all_resources.extend(resources)
            
            # Get network topology
            if resources:
                # Use location from first resource
                location = resources[0].location
                topology = self.azure_client.get_network_topology(rg_name, location)
                
                # Combine topologies
                combined_topology.virtual_networks.extend(topology.virtual_networks)
                combined_topology.subnets.extend(topology.subnets)
                combined_topology.network_interfaces.extend(topology.network_interfaces)
                combined_topology.public_ips.extend(topology.public_ips)
                combined_topology.load_balancers.extend(topology.load_balancers)
                combined_topology.network_security_groups.extend(topology.network_security_groups)
                combined_topology.associations.extend(topology.associations)
        
        if not all_resources:
            raise ValueError(f"No resources found in resource groups: {resource_groups}")
        
        logger.info(f"Found {len(all_resources)} total resources across {len(resource_groups)} resource groups")
        
        # Post-process cross-resource-group relationships (like DNS zones)
        self.azure_client._discover_dns_zone_relationships(all_resources)
        
        # Build graph
        graph_builder = GraphBuilder(config)
        graph = graph_builder.build_graph(all_resources, combined_topology)
        
        # Generate DOT language
        dot_generator = DOTGenerator(config)
        dot_content = dot_generator.generate_dot(
            graph, 
            graph_builder.subgraphs,
            subscription_name=self.azure_client.subscription_name,
            subscription_id=self.azure_client.subscription_id
        )
        
        # Save DOT file if requested
        if save_dot:
            dot_file = Path(output_file).with_suffix('.dot')
            renderer = GraphRenderer()
            renderer.save_dot_file(dot_content, str(dot_file))
            logger.info(f"DOT file saved: {dot_file}")
        
        # Validate output file extension matches format
        output_path_obj = Path(output_file)
        format_extensions = {
            OutputFormat.PNG: '.png',
            OutputFormat.SVG: '.svg', 
            OutputFormat.HTML: '.html'
        }
        
        expected_extension = format_extensions[output_format]
        actual_extension = output_path_obj.suffix.lower()
        
        # If no extension provided, add the correct one
        if not actual_extension:
            final_output_file = str(output_path_obj.with_suffix(expected_extension))
            logger.info(f"Added extension for format: {output_file} -> {final_output_file}")
        elif actual_extension != expected_extension:
            # Extension mismatch - fail with clear error
            raise ValueError(
                f"Output file extension '{actual_extension}' does not match format '{output_format.value}'. "
                f"Expected extension: '{expected_extension}'. "
                f"Please use '{output_path_obj.stem}{expected_extension}' or change the format."
            )
        else:
            # Extension is correct
            final_output_file = output_file
        
        # Render diagram
        renderer = GraphRenderer()
        output_path = renderer.render(dot_content, final_output_file, output_format)
        
        logger.info(f"Diagram exported successfully: {output_path}")
        return output_path
    
    def get_available_resource_groups(self) -> List[Dict[str, Any]]:
        """Get list of available resource groups in subscription.
        
        Returns:
            List of resource group information dictionaries.
        """
        return self.azure_client.get_resource_groups()
    
    def preview_resources(self, resource_group: str) -> List[AzureResource]:
        """Preview resources in a resource group without generating diagram.
        
        Args:
            resource_group: Resource group name.
            
        Returns:
            List of Azure resources.
        """
        return self.azure_client.get_resources_in_group(resource_group, True)
    
    def validate_prerequisites(self) -> Dict[str, bool]:
        """Validate all prerequisites for diagram generation.
        
        Returns:
            Dictionary with validation results.
        """
        results = {}
        
        # Check Azure authentication
        results['azure_auth'] = self.azure_client.test_authentication()
        
        # Check Graphviz installation
        try:
            renderer = GraphRenderer()
            results['graphviz'] = True
        except RuntimeError:
            results['graphviz'] = False
        
        # Check icon directory
        results['icons'] = self.icon_manager.icon_directory.exists()
        
        return results
    
    def get_supported_themes(self) -> List[str]:
        """Get list of supported visual themes.
        
        Returns:
            List of theme names.
        """
        return [theme.value for theme in Theme]
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats.
        
        Returns:
            List of format names.
        """
        return [fmt.value for fmt in OutputFormat]
    
    def get_icon_mappings(self) -> Dict[str, str]:
        """Get available Azure resource icon mappings.
        
        Returns:
            Dictionary mapping resource types to icon filenames.
        """
        return self.icon_manager.get_available_icons()