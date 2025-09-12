# CLI Usage Examples

## Basic Usage

Generate a basic diagram for a single resource group:
```bash
python-azviz export --resource-group my-rg
```

## Multiple Resource Groups

Visualize multiple resource groups in a single diagram:
```bash
python-azviz export -g production-rg -g staging-rg -g development-rg
```

## Custom Output and Theme

Generate a dark-themed SVG diagram:
```bash
python-azviz export -g my-rg --output my-topology.svg --theme dark --format svg
```

## Advanced Filtering

Exclude specific resource types using wildcards:
```bash
python-azviz export -g my-rg --exclude "*.subnets" --exclude "Microsoft.Network/routeTables"
```

## Layout Customization

Customize the diagram layout and appearance:
```bash
python-azviz export -g my-rg \
  --direction top-to-bottom \
  --splines curved \
  --verbosity 3 \
  --depth 1
```

## Resource Group Management

List all available resource groups:
```bash
python-azviz list-rg
```

Preview resources in a specific group:
```bash
python-azviz preview my-resource-group
```

## Validation and Troubleshooting

Validate prerequisites:
```bash
python-azviz validate
```

Show supported options:
```bash
python-azviz info
```

Enable verbose logging for debugging:
```bash
python-azviz --verbose export -g my-rg
```

## Complete Example

Generate a comprehensive diagram with all options:
```bash
python-azviz export \
  --resource-group production-network \
  --resource-group production-compute \
  --output production-topology.svg \
  --theme neon \
  --format svg \
  --verbosity 2 \
  --depth 2 \
  --direction left-to-right \
  --splines polyline \
  --exclude "*.test*" \
  --save-dot \
  --subscription-id "12345678-1234-1234-1234-123456789012"
```

## Automation and Scripting

Use in shell scripts:
```bash
#!/bin/bash
RG_NAME="my-production-rg"
OUTPUT_DIR="./diagrams"
DATE=$(date +%Y%m%d)

mkdir -p "$OUTPUT_DIR"

# Generate diagram
python-azviz export \
  --resource-group "$RG_NAME" \
  --output "$OUTPUT_DIR/topology-$DATE.png" \
  --theme light

echo "Diagram generated: $OUTPUT_DIR/topology-$DATE.png"
```

## CI/CD Integration

Example GitHub Actions workflow:
```yaml
- name: Generate Azure Topology Diagram
  run: |
    pip install python-azviz
    az login --service-principal -u ${{ secrets.AZURE_CLIENT_ID }} -p ${{ secrets.AZURE_CLIENT_SECRET }} --tenant ${{ secrets.AZURE_TENANT_ID }}
    python-azviz export --resource-group production-rg --output topology.png
    
- name: Upload diagram artifact
  uses: actions/upload-artifact@v3
  with:
    name: azure-topology
    path: topology.png
```