"""Command-line interface for Python AzViz."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .core import AzViz, Direction, LabelVerbosity, OutputFormat, Splines, Theme

# Setup rich console
console = Console()


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Setup logging with rich handler."""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    # Suppress noisy Azure SDK logging even in verbose mode
    if verbose:
        # Keep our application logs at INFO, but quiet Azure SDK HTTP logs
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
            logging.WARNING,
        )
        logging.getLogger("azure.identity").setLevel(logging.WARNING)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--subscription",
    "-s",
    help="Azure subscription ID or name. If not specified, uses the first available subscription from your Azure credentials.",
)
@click.version_option()
@click.pass_context
def cli(ctx: click.Context, verbose: bool, subscription: str | None) -> None:
    """Python AzViz - Azure resource topology visualization tool.

    Generate beautiful diagrams of your Azure infrastructure automatically.

    \b
    Authentication:
    - Uses Azure CLI credentials by default (az login)
    - Supports service principal and managed identity
    - Use --subscription to target specific subscription by ID or name

    \b
    Examples:
      python-azviz list-rg                    # List all resource groups
      python-azviz preview                    # Preview all resources
      python-azviz preview my-rg              # Preview specific RG
      python-azviz export                     # Diagram all resource groups
      python-azviz export -g my-rg --theme dark
      python-azviz export -g rg1 -g rg2 --subscription "12345678-1234-1234-1234-123456789012"
      python-azviz export -g rg1 -g rg2 --subscription "My Production Subscription"
    """
    setup_logging(verbose)

    # Store global options in context for commands to use
    ctx.ensure_object(dict)
    ctx.obj["subscription"] = subscription
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option(
    "--resource-group",
    "-g",
    multiple=True,
    required=False,
    help="Azure resource group name(s) to visualize. Can be specified multiple times. If not specified, visualizes all resource groups in subscription.",
)
@click.option(
    "--output",
    "-o",
    default="azure-topology.png",
    help="Output file path (default: azure-topology.png, will change extension based on format)",
)
@click.option(
    "--theme",
    "-t",
    type=click.Choice(["light", "dark", "neon"]),
    default="light",
    help="Visual theme (default: light)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["png", "svg", "html"]),
    default="png",
    help="Output format (default: png)",
)
@click.option(
    "--verbosity",
    type=click.IntRange(1, 3),
    default=2,
    help="Label verbosity level: 1=minimal, 2=standard, 3=detailed (default: 2)",
)
@click.option(
    "--depth",
    type=click.IntRange(1, 3),
    default=2,
    help="Resource categorization depth (default: 2)",
)
@click.option(
    "--direction",
    type=click.Choice(["left-to-right", "top-to-bottom"]),
    default="left-to-right",
    help="Graph layout direction (default: left-to-right)",
)
@click.option(
    "--splines",
    type=click.Choice(["polyline", "curved", "ortho", "line", "spline"]),
    default="polyline",
    help="Edge appearance (default: polyline)",
)
@click.option(
    "--exclude",
    multiple=True,
    help="Resource types to exclude (supports wildcards). Can be specified multiple times.",
)
@click.option(
    "--legend",
    is_flag=True,
    help="Enable legend in output (disabled by default)",
)
@click.option(
    "--no-power-state",
    is_flag=True,
    help="Disable VM power state visualization (enabled by default)",
)
@click.option(
    "--compute-only",
    is_flag=True,
    help="Show only compute resources and their directly related resources (VMs, disks, SSH keys, etc.)",
)
@click.option("--save-dot", is_flag=True, help="Save DOT source file alongside output")
@click.option(
    "--subscription",
    "-s",
    help="Azure subscription ID or name. If not specified, uses the global --subscription or first available subscription.",
)
@click.pass_context
def export(
    ctx: click.Context,
    resource_group: tuple,
    output: str,
    theme: str,
    output_format: str,
    verbosity: int,
    depth: int,
    direction: str,
    splines: str,
    exclude: tuple,
    legend: bool,
    no_power_state: bool,
    compute_only: bool,
    save_dot: bool,
    subscription: str | None,
) -> None:
    """Export Azure resource topology diagram.

    Generate a visual diagram showing Azure resources and their relationships
    within the specified resource group(s). If no resource groups are specified,
    visualizes all resource groups in the subscription.

    Examples:
      python-azviz export                                 # All resource groups in subscription
      python-azviz export -g my-resource-group            # Specific resource group
      python-azviz export -g rg1 -g rg2 --theme dark     # Multiple resource groups
      python-azviz export --exclude "*.subnets" --output all-topology.png
      python-azviz export -g my-rg --format html --output topology.html  # Interactive HTML output
      python-azviz export -g my-rg --no-power-state       # Disable VM power state display
      python-azviz export -g my-rg --compute-only         # Show only compute resources and dependencies
      python-azviz export -g my-rg --subscription "12345678-1234-1234-1234-123456789012"
      python-azviz export -g my-rg --subscription "My Production Subscription"
    """
    try:
        # Use command-level subscription, fallback to global, then None
        final_subscription = subscription or ctx.obj.get("subscription")
        verbose_mode = ctx.obj.get("verbose", False)

        # Initialize AzViz
        if verbose_mode:
            console.print("🔄 Initializing Azure connection...", style="blue")
        azviz = AzViz(subscription_identifier=final_subscription)

        # Validate prerequisites
        prereqs = azviz.validate_prerequisites()
        if not all(prereqs.values()):
            console.print("❌ Prerequisites check failed:", style="red")
            for name, status in prereqs.items():
                status_icon = "✅" if status else "❌"
                console.print(f"  {status_icon} {name}")
            if not prereqs["graphviz"]:
                console.print(
                    "\n💡 Install Graphviz: https://graphviz.org/download/",
                    style="yellow",
                )
            sys.exit(1)

        # Handle resource group selection
        if resource_group:
            # Use specified resource groups
            target_resource_groups = list(resource_group)
        else:
            # Use all resource groups in subscription
            if verbose_mode:
                console.print(
                    "🔍 No resource groups specified, using all in subscription...",
                    style="blue",
                )
            all_rgs = azviz.get_available_resource_groups()
            if not all_rgs:
                console.print(
                    "❌ No resource groups found in subscription.",
                    style="red",
                )
                sys.exit(1)
            target_resource_groups = [rg["name"] for rg in all_rgs]
            if verbose_mode:
                console.print(
                    f"📋 Found {len(target_resource_groups)} resource groups to visualize",
                    style="blue",
                )

        # Convert parameters to enum types
        theme_enum = Theme(theme)
        format_enum = OutputFormat(output_format)
        verbosity_enum = LabelVerbosity(verbosity)
        direction_enum = Direction(direction)
        splines_enum = Splines(splines)
        exclude_set: set[str] = set(exclude) if exclude else set()

        # Adjust output file extension based on format if default filename is used
        output_file = output
        if output == "azure-topology.png":
            if output_format == "svg":
                output_file = "azure-topology.svg"
            elif output_format == "html":
                output_file = "azure-topology.html"

        # Export diagram
        if verbose_mode:
            console.print(
                f"🎨 Generating diagram for {len(target_resource_groups)} resource group(s)...",
                style="green",
            )

        output_path = azviz.export_diagram(
            resource_group=target_resource_groups,
            output_file=output_file,
            theme=theme_enum,
            output_format=format_enum,
            label_verbosity=verbosity_enum,
            category_depth=depth,
            direction=direction_enum,
            splines=splines_enum,
            exclude_types=exclude_set,
            show_legends=legend,
            show_power_state=not no_power_state,
            compute_only=compute_only,
            save_dot=save_dot,
            verbose=verbose_mode,
        )

        console.print(f"{output_path}", style="green")

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        if logging.getLogger().level == logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@cli.command("list-rg")
@click.option(
    "--subscription",
    "-s",
    help="Azure subscription ID or name. If not specified, uses the global --subscription or first available subscription.",
)
@click.pass_context
def list_resource_groups(ctx: click.Context, subscription: str | None) -> None:
    """List available Azure resource groups in subscription.

    \b
    Examples:
      python-azviz list-rg
      python-azviz list-rg --subscription "12345678-1234-1234-1234-123456789012"
      python-azviz list-rg --subscription "My Production Subscription"
    """
    try:
        # Use command-level subscription, fallback to global, then None
        final_subscription = subscription or ctx.obj.get("subscription")
        verbose_mode = ctx.obj.get("verbose", False)

        if verbose_mode:
            console.print("🔄 Fetching resource groups...", style="blue")
        azviz = AzViz(subscription_identifier=final_subscription)

        resource_groups = azviz.get_available_resource_groups()

        if not resource_groups:
            console.print("No resource groups found in subscription.", style="yellow")
            return

        # Create table
        table = Table(title="Azure Resource Groups")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Location", style="magenta")
        table.add_column("Tags", style="green")

        for rg in resource_groups:
            tags_str = ", ".join(
                [f"{k}={v}" for k, v in (rg.get("tags") or {}).items()],
            )
            table.add_row(
                rg["name"],
                rg["location"],
                tags_str or "None",
            )

        console.print(table)
        if verbose_mode:
            console.print(
                f"\n📊 Total: {len(resource_groups)} resource groups",
                style="blue",
            )

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        if logging.getLogger().level == logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@cli.command("preview")
@click.argument("resource_group", required=False)
@click.option(
    "--subscription",
    "-s",
    help="Azure subscription ID or name. If not specified, uses the global --subscription or first available subscription.",
)
@click.pass_context
def preview_resources(
    ctx: click.Context,
    resource_group: str | None,
    subscription: str | None,
) -> None:
    """Preview resources in a resource group or all resource groups if none specified.

    \b
    Examples:
      python-azviz preview my-resource-group    # Preview specific RG
      python-azviz preview                      # Preview all RGs in subscription
    """
    try:
        # Use command-level subscription, fallback to global, then None
        final_subscription = subscription or ctx.obj.get("subscription")
        verbose_mode = ctx.obj.get("verbose", False)

        azviz = AzViz(subscription_identifier=final_subscription)

        if resource_group:
            # Preview specific resource group
            if verbose_mode:
                console.print(
                    f"🔄 Discovering resources in '{resource_group}'...",
                    style="blue",
                )

            resources = azviz.preview_resources(resource_group)

            if not resources:
                console.print(
                    f"No resources found in resource group '{resource_group}'.",
                    style="yellow",
                )
                return

            # Create table for specific RG
            table = Table(title=f"Resources in '{resource_group}'")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Type", style="magenta")
            table.add_column("Category", style="green")
            table.add_column("Location", style="blue")

            for resource in resources:
                table.add_row(
                    resource.name,
                    resource.resource_type,
                    resource.category,
                    resource.location,
                )

            console.print(table)
            if verbose_mode:
                console.print(f"\n📊 Total: {len(resources)} resources", style="blue")

        else:
            # Preview all resource groups in subscription
            if verbose_mode:
                console.print(
                    "🔄 Discovering all resources in subscription...",
                    style="blue",
                )

            # Get all resource groups
            resource_groups = azviz.get_available_resource_groups()

            if not resource_groups:
                console.print(
                    "No resource groups found in subscription.",
                    style="yellow",
                )
                return

            # Create table for all RGs
            table = Table(title="All Resources in Subscription")
            table.add_column("Resource Group", style="yellow", no_wrap=True)
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Type", style="magenta")
            table.add_column("Category", style="green")
            table.add_column("Location", style="blue")

            total_resources = 0
            for rg in resource_groups:
                rg_name = rg["name"]
                try:
                    resources = azviz.preview_resources(rg_name)
                    for resource in resources:
                        table.add_row(
                            rg_name,
                            resource.name,
                            resource.resource_type,
                            resource.category,
                            resource.location,
                        )
                        total_resources += 1
                except Exception as e:
                    if verbose_mode:
                        console.print(f"⚠️  Skipped RG '{rg_name}': {e}", style="yellow")
                    continue

            console.print(table)
            if verbose_mode:
                console.print(
                    f"\n📊 Total: {total_resources} resources across {len(resource_groups)} resource groups",
                    style="blue",
                )

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        if logging.getLogger().level == logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@cli.command("validate")
@click.option(
    "--subscription",
    "-s",
    help="Azure subscription ID or name. If not specified, uses the global --subscription or first available subscription.",
)
@click.pass_context
def validate_prerequisites(ctx: click.Context, subscription: str | None) -> None:
    """Validate prerequisites for diagram generation."""
    try:
        verbose_mode = ctx.obj.get("verbose", False)

        if verbose_mode:
            console.print("🔄 Validating prerequisites...", style="blue")

        # Test Azure connection
        try:
            # Use command-level subscription, fallback to global, then None
            final_subscription = subscription or ctx.obj.get("subscription")
            azviz = AzViz(subscription_identifier=final_subscription)
            prereqs = azviz.validate_prerequisites()
        except Exception as e:
            prereqs = {
                "azure_auth": False,
                "graphviz": False,
                "icons": False,
            }
            console.print(f"Failed to initialize: {e}", style="red")

        # Create table
        table = Table(title="Prerequisites Validation")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Description", style="green")

        descriptions = {
            "azure_auth": "Azure authentication and API access",
            "graphviz": "Graphviz installation for rendering",
            "icons": "Azure service icons directory",
        }

        for component, status in prereqs.items():
            status_str = "✅ OK" if status else "❌ FAILED"
            table.add_row(
                component.replace("_", " ").title(),
                status_str,
                descriptions.get(component, ""),
            )

        console.print(table)

        # Check critical vs optional prerequisites
        critical_failed = not prereqs.get("azure_auth") or not prereqs.get("graphviz")

        if all(prereqs.values()):
            console.print(
                "\n✅ All prerequisites validated successfully!",
                style="green bold",
            )
        elif critical_failed:
            console.print(
                "\n❌ Critical prerequisites failed. Please address the issues above.",
                style="red",
            )
            if not prereqs.get("azure_auth"):
                console.print(
                    "💡 Run 'az login' to authenticate with Azure",
                    style="yellow",
                )
            if not prereqs.get("graphviz"):
                console.print(
                    "💡 Install Graphviz: https://graphviz.org/download/",
                    style="yellow",
                )
            sys.exit(1)
        else:
            console.print(
                "\n⚠️  Core functionality ready, but some optional features missing.",
                style="yellow",
            )
            if not prereqs.get("icons"):
                console.print(
                    "💡 Icons enhance diagrams but are optional. See src/azviz/icons/azure_icons/README.md",
                    style="yellow",
                )

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        if logging.getLogger().level == logging.DEBUG:
            console.print_exception()
        sys.exit(1)


@cli.command("info")
def show_info() -> None:
    """Show information about supported themes, formats, and options."""
    # Themes
    themes_table = Table(title="Supported Themes")
    themes_table.add_column("Theme", style="cyan")
    themes_table.add_column("Description", style="green")

    theme_descriptions = {
        "light": "Light background with dark text (default)",
        "dark": "Dark background with light text",
        "neon": "High-contrast neon colors on black background",
    }

    for theme in Theme:
        themes_table.add_row(theme.value, theme_descriptions.get(theme.value, ""))

    console.print(themes_table)

    # Formats
    formats_table = Table(title="Supported Output Formats")
    formats_table.add_column("Format", style="cyan")
    formats_table.add_column("Description", style="green")

    format_descriptions = {
        "png": "Portable Network Graphics (raster)",
        "svg": "Scalable Vector Graphics (vector)",
        "html": "Interactive HTML page with embedded diagram",
    }

    for fmt in OutputFormat:
        formats_table.add_row(fmt.value, format_descriptions.get(fmt.value, ""))

    console.print(formats_table)

    # Layout options
    layout_table = Table(title="Layout Options")
    layout_table.add_column("Option", style="cyan")
    layout_table.add_column("Values", style="magenta")
    layout_table.add_column("Description", style="green")

    layout_table.add_row(
        "direction",
        "left-to-right, top-to-bottom",
        "Graph layout direction",
    )
    layout_table.add_row(
        "splines",
        "polyline, curved, ortho, line, spline",
        "Edge appearance style",
    )
    layout_table.add_row(
        "verbosity",
        "1, 2, 3",
        "Label detail level (1=minimal, 2=standard, 3=detailed)",
    )
    layout_table.add_row(
        "depth",
        "1, 2, 3",
        "Resource categorization depth",
    )
    layout_table.add_row(
        "--no-power-state",
        "flag",
        "Disable VM power state visualization (enabled by default)",
    )

    console.print(layout_table)


def main() -> None:
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
