# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-12

### Added
- **Initial Python implementation** inspired by the PowerShell AzViz module
- **Azure Resource Discovery** using Azure Management APIs
- **Network Topology Mapping** with Virtual Networks, Subnets, and relationships
- **VM Power State Visualization** - Shows running/stopped status with color coding
- **40+ Azure Service Icons** with automatic mapping based on resource types
- **Multiple Visual Themes** - Light, Dark, and Neon color schemes
- **Hybrid Layout System** - Horizontal resource groups with vertical resource stacking
- **Private Link Support** - Visualizes Private Endpoints and Private Link Services
- **Multiple Output Formats** - PNG and SVG support
- **Flexible CLI Interface** with comprehensive options
- **Resource Filtering** - Include/exclude specific resource types
- **Subscription Support** - Global and per-command subscription specification
- **Icon Mappings** for common Azure services:
  - Compute: Virtual Machines, VM Scale Sets, Disks
  - Network: Virtual Networks, Load Balancers, Public IPs, Network Security Groups, Network Interfaces
  - Storage: Storage Accounts, Blobs, Files, Queues, Tables
  - Database: SQL Servers, Cosmos DB, Redis Cache
  - Container: Azure Container Registry, Container Instances, AKS
  - Analytics: Data Factory, Databricks, Event Hubs, Log Analytics
  - Security: Key Vault
  - Management: Automation Accounts, Resource Groups, Subscriptions
  - Web: App Services, CDN Profiles
  - Azure Red Hat OpenShift clusters
  - Network Watcher, DNS Zones, Private Endpoints/Link Services

### Features
- **CLI Commands**:
  - `export` - Generate topology diagrams
  - `list-rg` - List available resource groups
  - `preview` - Preview resources without generating diagrams
  - `validate` - Validate prerequisites
  - `info` - Show supported themes and formats

- **Authentication Support**:
  - Azure CLI (`az login`)
  - Environment variables
  - Managed Identity
  - Service Principal

- **Advanced Visualization**:
  - HTML table labels with embedded icons
  - Color-coded VM power states (Green=Running, Red=Stopped, Orange=Transitional)
  - Resource type information in labels
  - Configurable label verbosity (1-3 levels)
  - Legend support (can be disabled)

### Technical
- Modern Python packaging with `pyproject.toml`
- NetworkX for graph data structures
- Graphviz for diagram rendering
- Click framework for CLI
- Rich console for formatted output
- Pydantic for data models
- Azure SDK for Python integration

### Credits
- Inspired by the original PowerShell AzViz module by [Prateek Kumar Singh](https://github.com/PrateekKumarSingh/AzViz)
- Azure service icons from Microsoft's official Azure Architecture Icons