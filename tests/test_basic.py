"""Basic smoke tests for python-azviz package."""

from unittest.mock import Mock, patch

from azviz.core.models import (
    AzureResource,
    DependencyType,
    Direction,
    LabelVerbosity,
    OutputFormat,
    Splines,
    Theme,
    VisualizationConfig,
)
from azviz.icons.icon_manager import IconManager


def test_azure_resource_creation():
    """Test AzureResource model creation."""
    resource = AzureResource(
        name="test-vm",
        resource_type="Microsoft.Compute/virtualMachines",
        category="Compute",
        location="eastus",
        resource_group="test-rg",
        subscription_id="test-sub",
        properties={"test": "value"},
        tags={"env": "test"},
        dependencies=[],
    )

    assert resource.name == "test-vm"
    assert resource.resource_type == "Microsoft.Compute/virtualMachines"
    assert resource.category == "Compute"
    assert resource.location == "eastus"
    assert resource.resource_group == "test-rg"
    assert resource.subscription_id == "test-sub"
    assert resource.properties == {"test": "value"}
    assert resource.tags == {"env": "test"}
    assert resource.dependencies == []


def test_azure_resource_add_dependency():
    """Test adding dependencies to AzureResource."""
    resource = AzureResource(
        name="test-vm",
        resource_type="Microsoft.Compute/virtualMachines",
        category="Compute",
        location="eastus",
        resource_group="test-rg",
        subscription_id="test-sub",
        properties={},
        tags={},
        dependencies=[],
    )

    resource.add_dependency("test-disk", DependencyType.EXPLICIT, "test source")

    assert len(resource.dependencies) == 1
    # Dependencies are ResourceDependency objects, not strings
    assert resource.dependencies[0].target_name == "test-disk"
    assert resource.dependencies[0].dependency_type == DependencyType.EXPLICIT
    assert resource.dependencies[0].description == "test source"

    # Test getting dependency names
    dep_names = resource.get_dependency_names()
    assert "test-disk" in dep_names


def test_visualization_config_creation():
    """Test VisualizationConfig model creation."""
    config = VisualizationConfig(
        resource_groups=["test-rg"],
        theme=Theme.LIGHT,
        output_format=OutputFormat.PNG,
        direction=Direction.LEFT_TO_RIGHT,
        splines=Splines.SPLINE,
        label_verbosity=LabelVerbosity.DETAILED,
        show_legends=True,
        show_power_state=True,
    )

    assert config.theme == Theme.LIGHT
    assert config.output_format == OutputFormat.PNG
    assert config.direction == Direction.LEFT_TO_RIGHT
    assert config.splines == Splines.SPLINE
    assert config.label_verbosity == LabelVerbosity.DETAILED
    assert config.show_legends is True
    assert config.show_power_state is True


def test_icon_manager_creation():
    """Test IconManager creation and basic functionality."""
    icon_manager = IconManager()

    # Test getting available icons
    mappings = icon_manager.get_available_icons()
    assert isinstance(mappings, dict)
    assert len(mappings) > 0

    # Test getting icon path for known resource type
    icon_path = icon_manager.get_icon_path("Microsoft.Compute/virtualMachines")
    # Should return a path or None if icon doesn't exist on disk
    assert icon_path is None or str(icon_path).endswith(".png")


def test_icon_manager_custom_mapping():
    """Test adding custom icon mapping."""
    icon_manager = IconManager()

    # Add custom mapping
    icon_manager.add_custom_mapping("custom.resource/type", "custom-icon.png")

    mappings = icon_manager.get_available_icons()
    assert "custom.resource/type" in mappings
    assert mappings["custom.resource/type"] == "custom-icon.png"


@patch("azviz.azure.client.DefaultAzureCredential")
@patch("azviz.azure.client.SubscriptionClient")
def test_azure_client_import(mock_subscription_client, mock_credential):
    """Test that AzureClient can be imported and basic functionality works."""
    from azviz.azure.client import AzureClient

    # Mock the credential and subscription client
    mock_credential.return_value = Mock()
    mock_subscription_client.return_value = Mock()

    # This should not raise an import error
    assert AzureClient is not None


def test_cli_import():
    """Test that CLI module can be imported."""
    from azviz import cli

    # This should not raise an import error
    assert cli is not None


def test_graph_builder_import():
    """Test that GraphBuilder can be imported."""
    from azviz.visualization.graph_builder import GraphBuilder

    # This should not raise an import error
    assert GraphBuilder is not None


def test_dot_generator_import():
    """Test that DOTGenerator can be imported."""
    from azviz.visualization.dot_generator import DOTGenerator

    # Create with minimal config
    config = VisualizationConfig(resource_groups=["test-rg"])
    generator = DOTGenerator(config)

    assert generator is not None
    assert generator.config == config


def test_package_version():
    """Test that package version can be imported."""
    from azviz import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_enums_values():
    """Test that enums have expected values."""
    # Test Theme enum
    assert Theme.LIGHT.value == "light"
    assert Theme.DARK.value == "dark"
    assert Theme.NEON.value == "neon"

    # Test OutputFormat enum
    assert OutputFormat.PNG.value == "png"
    assert OutputFormat.SVG.value == "svg"
    assert OutputFormat.HTML.value == "html"

    # Test Direction enum
    assert Direction.LEFT_TO_RIGHT.value == "left-to-right"
    assert Direction.TOP_TO_BOTTOM.value == "top-to-bottom"

    # Test DependencyType enum
    assert DependencyType.EXPLICIT.value == "explicit"
    assert DependencyType.DERIVED.value == "derived"
