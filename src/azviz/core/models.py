"""Data models and enums for AzViz."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel


class Theme(str, Enum):
    """Visual themes for diagram generation."""
    LIGHT = "light"
    DARK = "dark"
    NEON = "neon"


class OutputFormat(str, Enum):
    """Supported output formats."""
    PNG = "png"
    SVG = "svg"
    HTML = "html"


class LabelVerbosity(int, Enum):
    """Label verbosity levels."""
    MINIMAL = 1
    STANDARD = 2
    DETAILED = 3


class Direction(str, Enum):
    """Graph layout direction."""
    LEFT_TO_RIGHT = "left-to-right"
    TOP_TO_BOTTOM = "top-to-bottom"


class Splines(str, Enum):
    """Edge appearance options."""
    POLYLINE = "polyline"
    CURVED = "curved"
    ORTHO = "ortho"
    LINE = "line"
    SPLINE = "spline"


class DependencyType(str, Enum):
    """Types of dependencies between resources."""
    EXPLICIT = "explicit"  # Direct Azure API relationship
    DERIVED = "derived"   # Inferred from patterns/heuristics


@dataclass
class ResourceDependency:
    """Represents a dependency between Azure resources."""
    target_name: str
    dependency_type: DependencyType = DependencyType.EXPLICIT
    description: Optional[str] = None


@dataclass
class AzureResource:
    """Represents an Azure resource."""
    name: str
    resource_type: str
    category: str
    location: str
    resource_group: str
    subscription_id: str
    properties: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    dependencies: List[Union[str, ResourceDependency]] = field(default_factory=list)

    def add_dependency(self, target_name: str, dependency_type: DependencyType = DependencyType.EXPLICIT, description: Optional[str] = None):
        """Add a dependency with type information."""
        dependency = ResourceDependency(target_name, dependency_type, description)
        self.dependencies.append(dependency)

    def get_dependency_names(self) -> List[str]:
        """Get all dependency target names (for backward compatibility)."""
        names = []
        for dep in self.dependencies:
            if isinstance(dep, str):
                names.append(dep)
            else:
                names.append(dep.target_name)
        return names


@dataclass
class NetworkTopology:
    """Network topology information."""
    virtual_networks: List[Dict[str, Any]] = field(default_factory=list)
    subnets: List[Dict[str, Any]] = field(default_factory=list)
    network_interfaces: List[Dict[str, Any]] = field(default_factory=list)
    public_ips: List[Dict[str, Any]] = field(default_factory=list)
    load_balancers: List[Dict[str, Any]] = field(default_factory=list)
    network_security_groups: List[Dict[str, Any]] = field(default_factory=list)
    associations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphNode:
    """Graph node representation."""
    id: str
    name: str
    label: str
    category: str
    resource_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Graph edge representation."""
    source: str
    target: str
    label: str = ""
    edge_type: str = "association"  # association or dependency
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThemeConfig:
    """Theme configuration settings."""
    background_color: str
    node_color: str
    edge_color: str
    font_color: str
    font_name: str = "Arial"
    font_size: str = "10"


class ResourceRanking:
    """Resource ranking for layout priority."""
    RANKINGS = {
        "microsoft.network/dnszones": 1,  # DNS zones at top - provide naming for entire infrastructure
        "microsoft.network/privatednszones": 1,  # Private DNS zones at same level as public DNS
        "microsoft.network/publicipaddresses": 2,
        "microsoft.network/loadbalancers": 3,
        "microsoft.redhatopenshift/openshiftclusters": 4,  # OpenShift clusters at high priority
        "microsoft.containerservice/managedclusters": 4,  # AKS clusters at same level
        "microsoft.network/virtualnetworks": 5,
        "microsoft.network/privatednszones/virtualnetworklinks": 5,  # VNet links should be near VNets
        "microsoft.network/routetables": 6,  # Route tables should be near networking components
        "microsoft.network/networksecuritygroups": 6,
        "microsoft.network/networkinterfaces": 7,
        "microsoft.compute/sshpublickeys": 7,  # SSH keys should be close to compute resources
        "microsoft.managedidentity/userassignedidentities": 7,  # Managed identities should be close to resources using them
        "microsoft.compute/virtualmachines": 8,
        "microsoft.compute/disks": 9,  # Disks should appear below VMs
        "microsoft.compute/snapshots": 10,
        "microsoft.compute/galleries": 11,  # Galleries for image management
        "microsoft.compute/galleries/images": 12,  # Gallery images within galleries
        "microsoft.compute/galleries/images/versions": 13,  # Image versions within images
        "microsoft.storage/storageaccounts": 14,  # Storage accounts for data storage
    }

    @classmethod
    def get_rank(cls, resource_type: str) -> int:
        """Get ranking for resource type."""
        return cls.RANKINGS.get(resource_type.lower(), 99)


class VisualizationConfig(BaseModel):
    """Configuration for visualization generation."""
    resource_groups: List[str]
    label_verbosity: LabelVerbosity = LabelVerbosity.STANDARD
    category_depth: int = 2
    theme: Theme = Theme.LIGHT
    output_format: OutputFormat = OutputFormat.PNG
    direction: Direction = Direction.LEFT_TO_RIGHT
    splines: Splines = Splines.POLYLINE
    exclude_types: Set[str] = field(default_factory=set)
    show_legends: bool = True
    show_power_state: bool = True
    compute_only: bool = False
    output_file: Optional[str] = None
