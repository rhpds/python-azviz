#!/usr/bin/env python3
"""Basic usage examples for Python AzViz."""

from azviz import AzViz, Theme, OutputFormat, LabelVerbosity

def main():
    """Demonstrate basic AzViz usage."""
    
    # Initialize AzViz (uses default Azure credentials)
    viz = AzViz()
    
    # Example 1: Diagram all resource groups in subscription
    print("Generating diagram for all resource groups...")
    viz.export_diagram(
        resource_group=[],  # Empty list = all RGs
        output_file="all-resources-diagram.png"
    )
    
    # Example 2: Basic diagram for specific resource group
    print("Generating basic diagram for specific RG...")
    viz.export_diagram(
        resource_group="my-resource-group",
        output_file="basic-diagram.png"
    )
    
    # Example 3: Dark theme SVG diagram  
    print("Generating dark theme SVG...")
    viz.export_diagram(
        resource_group="my-resource-group",
        output_file="dark-diagram.svg",
        theme=Theme.DARK,
        output_format=OutputFormat.SVG
    )
    
    # Example 4: Multiple resource groups with detailed labels
    print("Generating multi-RG diagram...")
    viz.export_diagram(
        resource_group=["rg1", "rg2", "rg3"],
        output_file="multi-rg-diagram.png",
        label_verbosity=LabelVerbosity.DETAILED,
        theme=Theme.NEON
    )
    
    # Example 5: Exclude certain resource types
    print("Generating filtered diagram...")
    viz.export_diagram(
        resource_group="production-rg",
        output_file="filtered-diagram.png",
        exclude_types={"*subnets*", "Microsoft.Network/routeTables"},
        save_dot=True  # Also save the DOT source file
    )
    
    # Example 6: Preview resources before generating diagram
    print("Previewing resources in specific resource group...")
    resources = viz.preview_resources("my-resource-group")
    print(f"Found {len(resources)} resources:")
    for resource in resources[:5]:  # Show first 5
        print(f"  - {resource.name} ({resource.resource_type})")
    
    # Example 7: List available resource groups
    print("Available resource groups:")
    rgs = viz.get_available_resource_groups()
    for rg in rgs[:3]:  # Show first 3
        print(f"  - {rg['name']} in {rg['location']}")
    
    print("All examples completed!")


if __name__ == "__main__":
    main()