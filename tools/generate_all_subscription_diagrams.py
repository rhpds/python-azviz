#!/usr/bin/env python3
"""
Script to generate Azure topology diagrams for all subscriptions with resource groups.
Creates HTML output for each subscription in the specified output directory.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Sanitize subscription name for use as filename."""
    # Replace spaces and special characters with underscores
    sanitized = re.sub(r"[^\w\-_]", "_", name)
    # Remove multiple consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized


def get_all_subscriptions() -> list[dict[str, str]]:
    """Get list of all Azure subscriptions."""
    try:
        result = subprocess.run(
            ["az", "account", "list", "--query", "[].{name:name, id:id}", "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )

        subscriptions = json.loads(result.stdout)
        print(f"Found {len(subscriptions)} total subscriptions")
        return subscriptions
    except subprocess.CalledProcessError as e:
        print(f"Error getting subscriptions: {e}")
        return []


def check_resource_groups(
    subscription_name: str,
    azviz_command: str,
) -> tuple[bool, int, str]:
    """Check if subscription has any resource groups."""
    try:
        # Use our tool to check for resource groups in this subscription
        result = subprocess.run(
            [azviz_command, "list-rg", "--subscription", subscription_name],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Count lines in output (subtract header lines)
            lines = result.stdout.strip().split("\n")
            # Look for table content (lines with │)
            data_lines = [
                line
                for line in lines
                if "│" in line
                and not (
                    "┏" in line
                    or "┃" in line
                    or "┗" in line
                    or "┯" in line
                    or "┷" in line
                )
            ]
            rg_count = len(data_lines)
            return rg_count > 0, rg_count, ""
        error_msg = result.stderr.strip()
        return False, 0, error_msg

    except Exception as e:
        return False, 0, str(e)


def generate_diagram(
    subscription_name: str,
    output_dir: Path,
    azviz_command: str,
    output_format: str = "html",
    theme: str = "light",
    include_legend: bool = False,
) -> tuple[bool, str]:
    """Generate diagram for a subscription."""
    try:
        # Sanitize subscription name for filename
        safe_name = sanitize_filename(subscription_name)
        file_extension = output_format
        output_file = output_dir / f"{safe_name}.{file_extension}"

        print(f"  Generating diagram: {output_file}")

        # Generate diagram for all resource groups in the subscription
        cmd_args = [
            azviz_command,
            "export",
            "--subscription",
            subscription_name,
            "--format",
            output_format,
            "--output",
            str(output_file),
            "--theme",
            theme,
            "--verbosity",
            "2",
        ]

        # Add legend flag only if requested
        if include_legend:
            cmd_args.append("--legend")

        result = subprocess.run(cmd_args, check=False, capture_output=True, text=True)

        if result.returncode == 0:
            return True, str(output_file)
        error_msg = result.stderr.strip()
        return False, f"Export failed: {error_msg}"

    except Exception as e:
        return False, f"Exception: {e!s}"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Azure topology diagrams for all subscriptions with resource groups",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path.cwd() / "azure-diagrams",
        help="Output directory for diagrams (default: ./azure-diagrams)",
    )
    parser.add_argument(
        "--azviz-command",
        "-c",
        default="python-azviz",
        help="Command to run azviz (default: python-azviz)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["png", "svg", "html"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument(
        "--theme",
        "-t",
        choices=["light", "dark", "neon"],
        default="light",
        help="Visual theme (default: light)",
    )
    parser.add_argument(
        "--max-subscriptions",
        "-m",
        type=int,
        help="Maximum number of subscriptions to process (for testing)",
    )
    parser.add_argument(
        "--legend",
        action="store_true",
        help="Include legend in diagrams (disabled by default)",
    )
    return parser.parse_args()


def main():
    """Main function to generate diagrams for all subscriptions."""
    args = parse_args()

    print("🚀 Starting Azure subscription diagram generation...")
    print(f"📁 Output directory: {args.output_dir}")
    print(f"🎨 Format: {args.format}, Theme: {args.theme}")
    print(f"🔧 AzViz command: {args.azviz_command}")

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Get all subscriptions
    subscriptions = get_all_subscriptions()
    if not subscriptions:
        print("❌ No subscriptions found or error accessing Azure")
        return 1

    # Limit subscriptions if specified
    if args.max_subscriptions:
        subscriptions = subscriptions[: args.max_subscriptions]
        print(f"🔢 Limited to first {len(subscriptions)} subscriptions for testing")

    # Track results
    successful_diagrams = []
    failed_diagrams = []
    empty_subscriptions = []

    print(f"\n🔍 Checking {len(subscriptions)} subscriptions for resource groups...")

    for i, subscription in enumerate(subscriptions, 1):
        sub_name = subscription["name"]
        sub_id = subscription["id"]

        print(f"\n[{i}/{len(subscriptions)}] Processing: {sub_name}")
        print(f"    ID: {sub_id}")

        # Check if subscription has resource groups
        has_resources, rg_count, error = check_resource_groups(
            sub_name,
            args.azviz_command,
        )

        if error:
            print(f"    ⚠️  Error checking subscription: {error}")
            failed_diagrams.append((sub_name, f"Access error: {error}"))
            continue

        if not has_resources:
            print("    📭 No resource groups found - skipping")
            empty_subscriptions.append(sub_name)
            continue

        print(f"    ✅ Found {rg_count} resource group(s) - generating diagram...")

        # Generate diagram
        success, result = generate_diagram(
            sub_name,
            args.output_dir,
            args.azviz_command,
            args.format,
            args.theme,
            args.legend,
        )

        if success:
            print(f"    🎨 Diagram created: {result}")
            successful_diagrams.append((sub_name, result))
        else:
            print(f"    ❌ Failed to generate diagram: {result}")
            failed_diagrams.append((sub_name, result))

    # Print summary
    print("\n📊 Summary:")
    print(f"  Total subscriptions checked: {len(subscriptions)}")
    print(f"  Successful diagrams: {len(successful_diagrams)}")
    print(f"  Failed diagrams: {len(failed_diagrams)}")
    print(f"  Empty subscriptions: {len(empty_subscriptions)}")

    if successful_diagrams:
        print("\n✅ Successfully generated diagrams:")
        for sub_name, file_path in successful_diagrams:
            print(f"  • {sub_name} → {file_path}")

    if failed_diagrams:
        print("\n❌ Failed diagrams:")
        for sub_name, error in failed_diagrams:
            print(f"  • {sub_name}: {error}")

    if empty_subscriptions:
        print("\n📭 Empty subscriptions (no resource groups):")
        for sub_name in empty_subscriptions:
            print(f"  • {sub_name}")

    print("\n🏁 Diagram generation complete!")
    print(f"📁 All diagrams saved to: {args.output_dir}")

    return 0 if successful_diagrams else 1


if __name__ == "__main__":
    sys.exit(main())
