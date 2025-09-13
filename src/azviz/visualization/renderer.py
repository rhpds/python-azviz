"""Graph rendering using Graphviz."""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional
import base64

import graphviz

from ..core.models import OutputFormat

logger = logging.getLogger(__name__)


class GraphRenderer:
    """Renders DOT language to various output formats using Graphviz."""
    
    def __init__(self):
        """Initialize renderer and check Graphviz availability."""
        self._check_graphviz_installation()
    
    def _check_graphviz_installation(self) -> None:
        """Check if Graphviz is installed and accessible."""
        if not shutil.which('dot'):
            raise RuntimeError(
                "Graphviz 'dot' executable not found. Please install Graphviz:\n"
                "  Ubuntu/Debian: sudo apt-get install graphviz\n"
                "  macOS: brew install graphviz\n"
                "  Windows: Download from https://graphviz.org/download/"
            )
        
        logger.info("Graphviz installation verified")
    
    def render(
        self, 
        dot_content: str, 
        output_file: str, 
        output_format: OutputFormat,
        engine: str = 'dot'
    ) -> Path:
        """Render DOT content to specified format.
        
        Args:
            dot_content: DOT language content.
            output_file: Output file path.
            output_format: Output format (PNG, SVG, or HTML).
            engine: Graphviz engine to use (dot, neato, fdp, sfdp, circo, twopi).
            
        Returns:
            Path to the generated file.
        """
        logger.info(f"Rendering graph to {output_format.value} format")
        
        output_path = Path(output_file)
        
        try:
            # Use graphviz library for rendering
            graph = graphviz.Source(dot_content, engine=engine)
            
            # Render to specified format
            if output_format == OutputFormat.PNG:
                graph.render(
                    filename=output_path.stem,
                    directory=output_path.parent,
                    format='png',
                    cleanup=True
                )
                final_path = output_path.parent / f"{output_path.stem}.png"
            elif output_format == OutputFormat.SVG:
                # Generate SVG content and embed icons as data URLs
                svg_content = graph.pipe(format='svg', encoding='utf-8')
                svg_with_embedded_icons = self._embed_icons_in_svg(svg_content)
                
                # Write SVG file with embedded icons
                output_path.write_text(svg_with_embedded_icons, encoding='utf-8')
                final_path = output_path
            else:  # HTML
                # Generate SVG for embedding in HTML (first as SVG with file paths)
                svg_content = graph.pipe(format='svg', encoding='utf-8')
                
                # Post-process SVG to embed icons as data URLs
                svg_with_embedded_icons = self._embed_icons_in_svg(svg_content)
                
                html_content = self._generate_html_page(svg_with_embedded_icons, dot_content)
                
                # Write HTML file
                output_path.write_text(html_content, encoding='utf-8')
                final_path = output_path
            
            # Rename to desired output file if different
            if final_path != output_path:
                if output_path.exists():
                    output_path.unlink()
                final_path.rename(output_path)
                final_path = output_path
            
            logger.info(f"Graph rendered successfully to: {final_path}")
            return final_path
            
        except graphviz.ExecutableNotFound as e:
            raise RuntimeError(f"Graphviz executable not found: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to render graph: {e}") from e
    
    def render_to_string(
        self, 
        dot_content: str, 
        output_format: OutputFormat,
        engine: str = 'dot'
    ) -> bytes:
        """Render DOT content to bytes for in-memory usage.
        
        Args:
            dot_content: DOT language content.
            output_format: Output format (PNG, SVG, or HTML).
            engine: Graphviz engine to use.
            
        Returns:
            Rendered graph as bytes.
        """
        try:
            graph = graphviz.Source(dot_content, engine=engine)
            
            if output_format == OutputFormat.PNG:
                return graph.pipe(format='png')
            elif output_format == OutputFormat.SVG:
                return graph.pipe(format='svg')
            else:  # HTML
                svg_content = graph.pipe(format='svg', encoding='utf-8')
                svg_with_embedded_icons = self._embed_icons_in_svg(svg_content)
                html_content = self._generate_html_page(svg_with_embedded_icons, dot_content)
                return html_content.encode('utf-8')
                
        except Exception as e:
            raise RuntimeError(f"Failed to render graph to bytes: {e}") from e
    
    def validate_dot(self, dot_content: str) -> bool:
        """Validate DOT content syntax.
        
        Args:
            dot_content: DOT language content to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        try:
            # Try to parse the DOT content
            graph = graphviz.Source(dot_content)
            # Try to generate SVG to validate
            graph.pipe(format='svg')
            return True
        except Exception as e:
            logger.error(f"DOT validation failed: {e}")
            return False
    
    def get_available_engines(self) -> list[str]:
        """Get list of available Graphviz layout engines.
        
        Returns:
            List of available engine names.
        """
        common_engines = ['dot', 'neato', 'fdp', 'sfdp', 'circo', 'twopi']
        available = []
        
        for engine in common_engines:
            if shutil.which(engine):
                available.append(engine)
        
        return available
    
    def save_dot_file(self, dot_content: str, output_file: str) -> Path:
        """Save DOT content to a .dot file.
        
        Args:
            dot_content: DOT language content.
            output_file: Output file path.
            
        Returns:
            Path to the saved DOT file.
        """
        dot_path = Path(output_file)
        
        # Ensure .dot extension
        if dot_path.suffix.lower() != '.dot':
            dot_path = dot_path.with_suffix('.dot')
        
        dot_path.write_text(dot_content, encoding='utf-8')
        logger.info(f"DOT file saved to: {dot_path}")
        
        return dot_path
    
    def _generate_html_page(self, svg_content: str, dot_content: str) -> str:
        """Generate an interactive HTML page with the diagram.
        
        Args:
            svg_content: The SVG content of the diagram.
            dot_content: The original DOT source code.
            
        Returns:
            Complete HTML page content.
        """
        # Create interactive HTML with embedded SVG
        # Use triple braces for literal braces in JavaScript/CSS
        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Resource Topology</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 100%;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 20px;
        }}
        .diagram-container {{
            text-align: center;
            background: white;
            border-radius: 4px;
            padding: 10px;
            overflow: auto;
            max-height: 80vh;
        }}
        .diagram-container svg {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="diagram-container" id="diagramContainer">
            {svg_content}
        </div>
    </div>

</body>
</html>"""
        
        # Escape the DOT content for HTML
        escaped_dot = dot_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        return html_template.format(
            svg_content=svg_content,
            dot_content=escaped_dot
        )
    
    def _embed_icons_in_svg(self, svg_content: str) -> str:
        """Post-process SVG to embed icons as data URLs.
        
        Args:
            svg_content: Original SVG content with file paths.
            
        Returns:
            SVG content with embedded icons as data URLs.
        """
        import re
        from pathlib import Path
        
        # Import icon manager
        from ..icons.icon_manager import IconManager
        icon_manager = IconManager()
        
        # Find all img src references in the SVG
        img_pattern = r'<image[^>]*xlink:href="([^"]*)"[^>]*>'
        
        def replace_image(match):
            file_path = match.group(1)
            
            # Convert to Path object and check if it's an icon file
            path = Path(file_path)
            if path.exists() and path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.svg']:
                try:
                    # Read the icon file as binary
                    with open(path, 'rb') as icon_file:
                        icon_data = icon_file.read()
                    
                    # Get MIME type
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(str(path))
                    if not mime_type:
                        mime_type = 'image/png'
                    
                    # Encode as base64
                    base64_data = base64.b64encode(icon_data).decode('utf-8')
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    
                    # Replace the file path with data URL
                    return match.group(0).replace(file_path, data_url)
                    
                except Exception as e:
                    logger.warning(f"Failed to embed icon {file_path}: {e}")
                    return match.group(0)
            
            return match.group(0)
        
        # Process the SVG content
        processed_svg = re.sub(img_pattern, replace_image, svg_content)
        
        logger.debug("SVG post-processed to embed icons as data URLs")
        return processed_svg