# Running Python AzViz Examples

## Quick Start Commands

Once you've cloned the repository and are in the `python-azviz` directory:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Verify Installation
```bash
python azviz.py validate
```
This checks that all prerequisites are working (Azure auth, Graphviz, icons).

### 3. Basic Commands

**Get help:**
```bash
python azviz.py --help
```

**List all available resource groups:**
```bash
python azviz.py list-rg
```

**Preview resources in a specific group:**
```bash
python azviz.py preview my-resource-group
```

**Preview all resources in subscription:**
```bash
python azviz.py preview
```

**Validate prerequisites:**
```bash
python azviz.py validate
```

**Show supported options:**
```bash
python azviz.py info
```

### 4. Generate Diagrams

**Diagram all resource groups in subscription:**
```bash
python azviz.py export                           # Output: azure-topology.png
python azviz.py export --output all-resources.png  # Custom output filename
```

**Basic diagram for specific resource group:**
```bash
python azviz.py export --resource-group my-rg
```

**Multiple resource groups with dark theme:**
```bash
python azviz.py export -g rg1 -g rg2 --theme dark --format svg --output multi-rg.svg
```

**Filtered diagram (exclude subnets):**
```bash
python azviz.py export -g production-rg --exclude "*subnet*" --save-dot
```

**High-detail neon theme:**
```bash
python azviz.py export -g my-rg --theme neon --verbosity 3 --direction top-to-bottom
```

## Authentication

Make sure you're authenticated with Azure:
```bash
az login
```

Or set environment variables:
```bash
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

## Troubleshooting

**Python import errors:**
```bash
# Make sure you're in the python-azviz directory
pwd  # Should show .../AzViz/python-azviz

# Install dependencies
pip install -r requirements.txt
```

**Graphviz not found:**
```bash
# Ubuntu/Debian
sudo apt-get install graphviz

# macOS
brew install graphviz

# Verify installation
dot -V
```

**Azure authentication:**
```bash
# Validate your setup
python azviz.py validate

# Login if needed
az login
```

## Example Workflow

Complete workflow to generate your first diagram:

```bash
# 1. Clone and navigate to directory
git clone https://github.com/your-username/python-azviz.git
cd python-azviz

# 2. Install dependencies
pip install -r requirements.txt

# 3. Validate setup
python azviz.py validate

# 4. See what resource groups are available
python azviz.py list-rg

# 5. Preview resources (all or specific group)
python azviz.py preview                    # All resources in subscription
python azviz.py preview <resource-group-name>  # Specific resource group

# 6. Generate diagram (all or specific resource groups)
python azviz.py export                          # All resource groups in subscription
python azviz.py export --resource-group <name>  # Specific resource group

# 7. View your diagram!
# Output file will be saved as azure-topology.png
```

The wrapper script (`azviz.py`) handles all the Python path setup automatically, so you can run it directly without installing the package!

## Icons Included

This repository includes 65+ Azure service icons from Microsoft's official Azure Architecture Icons, so no additional setup is required for full visual diagrams.
