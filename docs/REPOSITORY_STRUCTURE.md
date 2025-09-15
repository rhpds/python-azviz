# Repository Structure

This document describes the structure and organization of the Python AzViz repository.

## Project Layout

```
python-azviz/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI/CD pipeline
├── examples/
│   ├── basic_usage.py            # Python API usage examples
│   └── cli_examples.md           # Command-line usage examples
├── src/
│   └── azviz/
│       ├── __init__.py           # Package initialization and exports
│       ├── cli.py                # Command-line interface (Click-based)
│       ├── azure/
│       │   ├── __init__.py
│       │   └── client.py         # Azure API client (Resource, Network, Compute)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── azviz.py          # Main AzViz class
│       │   └── models.py         # Data models and enums
│       ├── icons/
│       │   ├── __init__.py
│       │   ├── icon_manager.py   # Icon mapping and management
│       │   └── azure_icons/      # Microsoft Azure service icons
│       │       └── General Service Icons/
│       │           ├── virtualmachines.png
│       │           ├── storageaccounts.png
│       │           ├── virtualnetworks.png
│       │           └── ... (40+ service icons)
│       └── visualization/
│           ├── __init__.py
│           ├── dot_generator.py  # DOT language generation for Graphviz
│           ├── graph_builder.py  # NetworkX graph construction
│           └── renderer.py       # Graphviz rendering engine
├── azviz.py                      # Direct execution wrapper script
├── pyproject.toml               # Modern Python packaging configuration
├── requirements.txt             # Pip requirements (generated from pyproject.toml)
├── .gitignore                   # Git ignore patterns
├── LICENSE                      # MIT License
├── README.md                    # Main project documentation
├── CHANGELOG.md                 # Version history and changes
└── REPOSITORY_STRUCTURE.md     # This file
```

## Key Components

### Core Library (`src/azviz/`)

- **`__init__.py`**: Package exports and version information
- **`cli.py`**: Full-featured command-line interface built with Click
- **`core/azviz.py`**: Main AzViz class with public API
- **`core/models.py`**: Pydantic data models and enums for type safety

### Azure Integration (`src/azviz/azure/`)

- **`client.py`**: Azure SDK integration for resource discovery
  - Resource Management API
  - Network Management API
  - Compute Management API (for VM power states)
  - Subscription Management API

### Visualization Engine (`src/azviz/visualization/`)

- **`graph_builder.py`**: Converts Azure resources to NetworkX graphs
- **`dot_generator.py`**: Generates DOT language for Graphviz rendering
- **`renderer.py`**: Handles Graphviz execution and output generation

### Icon System (`src/azviz/icons/`)

- **`icon_manager.py`**: Maps Azure resource types to appropriate icons
- **`azure_icons/`**: Microsoft's official Azure service icons (40+ icons)

## Features by Module

### CLI Features (`cli.py`)
- `export` - Generate topology diagrams
- `list-rg` - List available resource groups
- `preview` - Preview resources without generating diagrams
- `validate` - Check prerequisites (Azure auth, Graphviz)
- `info` - Show supported themes and formats

### Core Features (`core/azviz.py`)
- Azure resource discovery across subscriptions
- Network topology mapping with Virtual Networks
- VM power state visualization with color coding
- Multiple output formats (PNG, SVG)
- Visual themes (Light, Dark, Neon)
- Resource filtering and exclusion patterns

### Visualization Features
- HTML table labels with embedded Azure service icons
- Hybrid layout: horizontal resource groups, vertical resources
- Color-coded VM power states (Green/Red/Orange)
- Support for Private Link components
- Configurable label verbosity (1-3 levels)
- DOT source file generation for debugging

## Dependencies

### Core Dependencies
- **azure-identity**: Azure authentication
- **azure-mgmt-***: Azure Management SDK packages
- **networkx**: Graph data structures and algorithms
- **graphviz**: DOT language rendering
- **click**: Command-line interface framework
- **rich**: Formatted console output
- **pydantic**: Data validation and modeling

### Development Dependencies
- **pytest**: Testing framework
- **black**: Code formatting
- **ruff**: Fast Python linter
- **mypy**: Static type checking

## Configuration

### Authentication
Supports multiple Azure authentication methods:
- Azure CLI (`az login`)
- Environment variables
- Managed Identity
- Service Principal

### Themes
- **Light**: Light background, dark text (default)
- **Dark**: Dark background, light text
- **Neon**: High-contrast neon colors on black

### Layout Options
- **Direction**: Left-to-right (default) or top-to-bottom
- **Splines**: Edge styles (polyline, curved, ortho, line, spline)
- **Verbosity**: Label detail levels (1=minimal, 2=standard, 3=detailed)

## Development Workflow

1. **Local Development**: Use `pip install -e .` for editable installation
2. **Testing**: Run `pytest` for unit tests
3. **Linting**: Use `ruff check` and `ruff format`
4. **Type Checking**: Run `mypy src/azviz`
5. **CI/CD**: GitHub Actions automatically test on Python 3.8-3.12

## Distribution

### PyPI Package
- Package name: `python-azviz`
- Entry point: `python-azviz` command
- Installable via: `pip install python-azviz`

### Direct Usage
- Clone repository and run `./azviz.py` directly
- Install dependencies with `pip install -r requirements.txt`

## Credits and Licensing

- **MIT License** - See LICENSE file
- **Inspired by**: PowerShell AzViz by Prateek Kumar Singh
- **Author**: Patrick Rutledge (rut31337)
- **Icons**: Microsoft Azure Architecture Icons
