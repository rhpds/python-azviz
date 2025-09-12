"""Data models and enums for AzViz."""

from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
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
    dependencies: List[str] = field(default_factory=list)
    
    
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
        "microsoft.network/publicipaddresses": 1,
        "microsoft.network/loadbalancers": 2,
        "microsoft.network/virtualnetworks": 3,
        "microsoft.network/networksecuritygroups": 4,
        "microsoft.network/networkinterfaces": 5,
        "microsoft.compute/virtualmachines": 6,
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
    output_file: Optional[str] = None