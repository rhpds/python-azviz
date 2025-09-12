# Python AzViz

A modern Python implementation for automatically generating Azure resource topology diagrams, inspired by the PowerShell [AzViz](https://github.com/PrateekKumarSingh/AzViz) module.

## Overview

Python AzViz generates visual diagrams of Azure Resource Groups and their dependencies by:
- Discovering Azure resources using Azure Management APIs
- Mapping resource relationships and dependencies  
- Creating graph visualizations using NetworkX and Graphviz
- Supporting multiple themes and output formats

## Features

- **Azure Resource Discovery**: Automatically finds resources and dependencies
- **Network Topology Mapping**: Maps VNets, subnets, and network relationships
- **VM Power State Visualization**: Shows running/stopped status with color coding
- **Visual Themes**: Light, dark, and neon color schemes
- **Multiple Formats**: PNG and SVG output support
- **Flexible Filtering**: Include/exclude specific resource types
- **Icon Integration**: 40+ Azure service icons for visual clarity
- **Hybrid Layout**: Horizontal resource groups with vertical resource stacking
- **Private Link Support**: Visualizes Private Endpoints and Private Link Services

## Installation

### Prerequisites
- Python 3.8+
- [Graphviz](https://graphviz.org/download/) installed on your system
- Azure CLI or Azure credentials configured

### Install Graphviz
**Ubuntu/Debian:**
```bash
sudo apt-get install graphviz
```

**macOS:**
```bash
brew install graphviz
```

**Windows:**
Download from https://graphviz.org/download/

### Option 1: Install Python AzViz (Future)
```bash
pip install python-azviz
```

### Option 2: Run Directly from Source
```bash
# Clone the repository
git clone https://github.com/rut31337/python-azviz.git
cd python-azviz

# Install dependencies
pip install -r requirements.txt

# Run directly using wrapper script
python azviz.py --help
python azviz.py export --resource-group my-rg
python azviz.py list-rg
```

### Option 3: Development Installation
```bash
# Install in editable mode for development
pip install -e .
python-azviz --help
```

## Quick Start

```python
from azviz import AzViz

# Initialize with Azure credentials
viz = AzViz()

# Generate diagram for all resource groups
viz.export_diagram(
    resource_group=[],  # Empty list = all RGs
    output_file="all-resources.png",
    theme="light"
)

# Generate diagram for specific resource group
viz.export_diagram(
    resource_group="my-resource-group",
    output_file="my-diagram.png",
    theme="light"
)
```

### CLI Usage
```bash
# Diagram all resource groups in subscription
python-azviz export --output all-resources.png

# Basic usage for specific resource group
python-azviz export --resource-group my-rg --output diagram.png

# With custom theme and format
python-azviz export --resource-group my-rg --theme dark --format svg --output diagram.svg

# Multiple resource groups
python-azviz export -g rg1 -g rg2 -g rg3 --output multi-rg.png
```

## Configuration

### Authentication
Python AzViz supports multiple authentication methods:
- Azure CLI (`az login`)
- Environment variables
- Managed Identity
- Service Principal

### Themes
- `light`: Light background with dark text
- `dark`: Dark background with light text  
- `neon`: High-contrast neon colors

### Output Formats
- `png`: Portable Network Graphics
- `svg`: Scalable Vector Graphics

## Examples

See the `examples/` directory for more usage examples.

## Migration from PowerShell AzViz

Python AzViz maintains compatibility with the original PowerShell version:
- Same parameter names and behavior
- Identical output formats and themes
- Compatible icon system

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

- Original PowerShell AzViz by [Prateek Kumar Singh](https://github.com/PrateekKumarSingh/AzViz)
- Python implementation by [Patrick Rutledge](https://github.com/rut31337) with assistance from Claude AI
- Azure service icons from Microsoft's official Azure Architecture Icons