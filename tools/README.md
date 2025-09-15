# Python AzViz Tools

This directory contains utility scripts and tools for Python AzViz.

## Scripts

### generate_all_subscription_diagrams.py

A utility script to automatically generate Azure topology diagrams for all subscriptions in your Azure tenant that contain resource groups.

#### Features
- Scans all Azure subscriptions accessible to your credentials
- Skips empty subscriptions (no resource groups)
- Generates diagrams only for subscriptions with resources
- Configurable output format, theme, and directory
- Progress tracking with detailed logging
- Error handling with helpful feedback

#### Usage

```bash
# Basic usage - generates HTML diagrams in ./azure-diagrams/
python tools/generate_all_subscription_diagrams.py

# Custom output directory and format
python tools/generate_all_subscription_diagrams.py --output-dir /path/to/output --format png

# Using development version of azviz
python tools/generate_all_subscription_diagrams.py --azviz-command "python azviz.py"

# Limit processing for testing
python tools/generate_all_subscription_diagrams.py --max-subscriptions 5

# Custom theme
python tools/generate_all_subscription_diagrams.py --theme dark --format svg

# Include legends in diagrams
python tools/generate_all_subscription_diagrams.py --legend
```

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `./azure-diagrams` | Output directory for diagrams |
| `--azviz-command` | `-c` | `python-azviz` | Command to run azviz |
| `--format` | `-f` | `html` | Output format (png, svg, html) |
| `--theme` | `-t` | `light` | Visual theme (light, dark, neon) |
| `--max-subscriptions` | `-m` | None | Maximum subscriptions to process |
| `--legend` | | False | Include legend in diagrams (disabled by default) |

#### Output

The script creates one diagram file per subscription with resources, using the sanitized subscription name as the filename:

- `My Production Subscription` → `My_Production_Subscription.html`
- `dev-environment-01` → `dev-environment-01.html`
- `Test Subscription (East US)` → `Test_Subscription__East_US_.html`

#### Example Output

```
🚀 Starting Azure subscription diagram generation...
📁 Output directory: ./azure-diagrams
🎨 Format: html, Theme: light
🔧 AzViz command: python-azviz

🔍 Checking 15 subscriptions for resource groups...

[1/15] Processing: Production Subscription
    ID: 12345678-1234-1234-1234-123456789012
    ✅ Found 8 resource group(s) - generating diagram...
  Generating diagram: ./azure-diagrams/Production_Subscription.html
    🎨 Diagram created: ./azure-diagrams/Production_Subscription.html

[2/15] Processing: Empty Test Sub
    ID: 87654321-4321-4321-4321-210987654321
    📭 No resource groups found - skipping

📊 Summary:
  Total subscriptions checked: 15
  Successful diagrams: 8
  Failed diagrams: 0
  Empty subscriptions: 7

🏁 Diagram generation complete!
📁 All diagrams saved to: ./azure-diagrams
```

#### Prerequisites

- Python AzViz installed and accessible via the specified command
- Azure CLI authentication (`az login`) or other credential provider
- Read access to all subscriptions you want to visualize
- Sufficient disk space for generated diagrams

#### Error Handling

The script handles various error conditions gracefully:
- **Access denied**: Subscriptions you can't access are skipped with a warning
- **Empty subscriptions**: Subscriptions with no resource groups are skipped
- **Generation failures**: Individual diagram failures are logged but don't stop processing
- **Invalid credentials**: Clear error message with authentication guidance

#### Performance

Processing time depends on:
- Number of subscriptions with resources
- Size and complexity of each subscription
- Output format (HTML is fastest, PNG/SVG require rendering)
- Network latency to Azure APIs

Typical performance:
- ~10-30 seconds per subscription with moderate resources
- ~2-5 minutes for large, complex subscriptions
- HTML format: ~5-15 seconds per subscription
- PNG/SVG format: ~15-45 seconds per subscription
