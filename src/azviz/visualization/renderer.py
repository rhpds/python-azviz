"""Graph rendering using Graphviz."""

import logging
import shutil
import os
import sys
from pathlib import Path
from typing import Optional
import base64
from contextlib import contextmanager, nullcontext

import graphviz

from ..core.models import OutputFormat

logger = logging.getLogger(__name__)


@contextmanager
def suppress_stderr():
    """Context manager to temporarily suppress stderr output."""
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


class GraphRenderer:
    """Renders DOT language to various output formats using Graphviz."""
    
    def __init__(self, verbose: bool = False):
        """Initialize renderer and check Graphviz availability.

        Args:
            verbose: Whether to show verbose output including Graphviz warnings.
        """
        self.verbose = verbose
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

            # Use context manager to suppress stderr if not in verbose mode
            context_manager = suppress_stderr() if not self.verbose else nullcontext()

            with context_manager:
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

            # Use context manager to suppress stderr if not in verbose mode
            context_manager = suppress_stderr() if not self.verbose else nullcontext()

            with context_manager:
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
            position: relative;
        }}
        .zoom-controls {{
            position: absolute;
            top: 30px;
            right: 30px;
            display: flex;
            gap: 8px;
            z-index: 1000;
        }}
        .zoom-btn {{
            background: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            width: 40px;
            height: 40px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            transition: all 0.2s ease;
        }}
        .zoom-btn:hover {{
            background: #106ebe;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .zoom-btn:active {{
            transform: translateY(0);
            box-shadow: 0 1px 4px rgba(0,0,0,0.15);
        }}
        .zoom-level {{
            background: #f8f9fa;
            color: #333;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            min-width: 60px;
            justify-content: center;
        }}
        .diagram-container {{
            text-align: center;
            background: white;
            border-radius: 4px;
            padding: 10px;
            overflow: hidden;
            max-height: 80vh;
            position: relative;
            cursor: grab;
        }}
        .diagram-container.dragging {{
            cursor: grabbing;
        }}
        .diagram-container svg {{
            max-width: none;
            height: auto;
            transition: transform 0.1s ease;
            transform-origin: center center;
            user-select: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="zoom-controls">
            <button class="zoom-btn" id="zoomOut" title="Zoom Out">−</button>
            <div class="zoom-level" id="zoomLevel">100%</div>
            <button class="zoom-btn" id="zoomIn" title="Zoom In">+</button>
            <button class="zoom-btn" id="resetZoom" title="Reset Zoom" style="width: auto; padding: 0 12px; font-size: 12px;">Reset</button>
        </div>
        <div class="diagram-container" id="diagramContainer">
            {svg_content}
        </div>
    </div>

    <script>
        // Pan and zoom functionality
        let currentZoom = 1.0;
        let panX = 0;
        let panY = 0;
        const zoomStep = 0.05;  // Much smaller increment (5% instead of 10%)
        const minZoom = 0.1;
        const maxZoom = 5.0;

        // Drag state
        let isDragging = false;
        let dragStartX = 0;
        let dragStartY = 0;
        let dragStartPanX = 0;
        let dragStartPanY = 0;

        const svg = document.querySelector('#diagramContainer svg');
        const diagramContainer = document.getElementById('diagramContainer');
        const zoomLevelDisplay = document.getElementById('zoomLevel');
        const zoomInBtn = document.getElementById('zoomIn');
        const zoomOutBtn = document.getElementById('zoomOut');
        const resetZoomBtn = document.getElementById('resetZoom');

        function updateTransform() {{
            if (svg) {{
                svg.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{currentZoom}})`;
                svg.style.transformOrigin = 'center center';
                zoomLevelDisplay.textContent = Math.round(currentZoom * 100) + '%';

                // Update button states
                zoomInBtn.disabled = currentZoom >= maxZoom;
                zoomOutBtn.disabled = currentZoom <= minZoom;

                // Update button styling for disabled state
                if (zoomInBtn.disabled) {{
                    zoomInBtn.style.opacity = '0.5';
                    zoomInBtn.style.cursor = 'not-allowed';
                }} else {{
                    zoomInBtn.style.opacity = '1';
                    zoomInBtn.style.cursor = 'pointer';
                }}

                if (zoomOutBtn.disabled) {{
                    zoomOutBtn.style.opacity = '0.5';
                    zoomOutBtn.style.cursor = 'not-allowed';
                }} else {{
                    zoomOutBtn.style.opacity = '1';
                    zoomOutBtn.style.cursor = 'pointer';
                }}
            }}
        }}

        function zoomIn() {{
            if (currentZoom < maxZoom) {{
                currentZoom = Math.min(currentZoom + zoomStep, maxZoom);
                updateTransform();
            }}
        }}

        function zoomOut() {{
            if (currentZoom > minZoom) {{
                currentZoom = Math.max(currentZoom - zoomStep, minZoom);
                updateTransform();
            }}
        }}

        function resetZoom() {{
            initializeFitToScreen();
        }}

        // Zoom at specific point (for mouse wheel)
        function zoomAtPoint(x, y, zoomIn) {{
            const containerRect = diagramContainer.getBoundingClientRect();

            // Calculate mouse position relative to container
            const mouseX = x - containerRect.left;
            const mouseY = y - containerRect.top;

            const oldZoom = currentZoom;
            const newZoom = zoomIn ?
                Math.min(currentZoom + zoomStep, maxZoom) :
                Math.max(currentZoom - zoomStep, minZoom);

            if (newZoom !== oldZoom) {{
                // Calculate the point we want to keep stationary
                const containerCenterX = containerRect.width / 2;
                const containerCenterY = containerRect.height / 2;

                // Current point under mouse in the scaled coordinate system
                const pointX = (mouseX - containerCenterX - panX) / oldZoom;
                const pointY = (mouseY - containerCenterY - panY) / oldZoom;

                // Update zoom
                currentZoom = newZoom;

                // Calculate new pan to keep the same point under the mouse
                panX = mouseX - containerCenterX - (pointX * newZoom);
                panY = mouseY - containerCenterY - (pointY * newZoom);

                updateTransform();
            }}
        }}

        // Event listeners for zoom buttons
        zoomInBtn.addEventListener('click', zoomIn);
        zoomOutBtn.addEventListener('click', zoomOut);
        resetZoomBtn.addEventListener('click', resetZoom);

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (e.ctrlKey || e.metaKey) {{
                if (e.key === '=' || e.key === '+') {{
                    e.preventDefault();
                    zoomIn();
                }} else if (e.key === '-') {{
                    e.preventDefault();
                    zoomOut();
                }} else if (e.key === '0') {{
                    e.preventDefault();
                    resetZoom();
                }}
            }}
        }});

        // Mouse wheel zoom (without requiring Ctrl) - center zoom
        diagramContainer.addEventListener('wheel', function(e) {{
            e.preventDefault();
            if (e.deltaY < 0) {{
                zoomIn();
            }} else {{
                zoomOut();
            }}
        }});

        // Drag functionality
        diagramContainer.addEventListener('mousedown', function(e) {{
            // Only start drag with left mouse button and not on zoom controls
            if (e.button === 0 && !e.target.closest('.zoom-controls')) {{
                isDragging = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                dragStartPanX = panX;
                dragStartPanY = panY;
                diagramContainer.classList.add('dragging');
                e.preventDefault();
            }}
        }});

        document.addEventListener('mousemove', function(e) {{
            if (isDragging) {{
                const deltaX = e.clientX - dragStartX;
                const deltaY = e.clientY - dragStartY;
                panX = dragStartPanX + deltaX;
                panY = dragStartPanY + deltaY;
                updateTransform();
            }}
        }});

        document.addEventListener('mouseup', function(e) {{
            if (isDragging) {{
                isDragging = false;
                diagramContainer.classList.remove('dragging');
            }}
        }});

        // Prevent context menu on right click
        diagramContainer.addEventListener('contextmenu', function(e) {{
            e.preventDefault();
        }});

        // Touch support for mobile devices
        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartPanX = 0;
        let touchStartPanY = 0;
        let touchStartDistance = 0;
        let touchStartZoom = 1;

        diagramContainer.addEventListener('touchstart', function(e) {{
            if (e.touches.length === 1) {{
                // Single touch - start pan
                const touch = e.touches[0];
                touchStartX = touch.clientX;
                touchStartY = touch.clientY;
                touchStartPanX = panX;
                touchStartPanY = panY;
            }} else if (e.touches.length === 2) {{
                // Two finger touch - start pinch zoom
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                touchStartDistance = Math.sqrt(
                    Math.pow(touch2.clientX - touch1.clientX, 2) +
                    Math.pow(touch2.clientY - touch1.clientY, 2)
                );
                touchStartZoom = currentZoom;
            }}
            e.preventDefault();
        }});

        diagramContainer.addEventListener('touchmove', function(e) {{
            if (e.touches.length === 1) {{
                // Single touch - pan
                const touch = e.touches[0];
                const deltaX = touch.clientX - touchStartX;
                const deltaY = touch.clientY - touchStartY;
                panX = touchStartPanX + deltaX;
                panY = touchStartPanY + deltaY;
                updateTransform();
            }} else if (e.touches.length === 2) {{
                // Two finger touch - pinch zoom
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                const currentDistance = Math.sqrt(
                    Math.pow(touch2.clientX - touch1.clientX, 2) +
                    Math.pow(touch2.clientY - touch1.clientY, 2)
                );
                const scale = currentDistance / touchStartDistance;
                currentZoom = Math.max(minZoom, Math.min(maxZoom, touchStartZoom * scale));
                updateTransform();
            }}
            e.preventDefault();
        }});

        // Initialize with fit-to-screen zoom
        function initializeFitToScreen() {{
            if (svg) {{
                // Get SVG dimensions
                const svgRect = svg.getBoundingClientRect();
                const svgWidth = svg.viewBox.baseVal.width || svgRect.width;
                const svgHeight = svg.viewBox.baseVal.height || svgRect.height;

                // Get container dimensions (minus padding)
                const containerRect = diagramContainer.getBoundingClientRect();
                const containerWidth = containerRect.width - 40; // Account for padding
                const containerHeight = containerRect.height - 40; // Account for padding

                // Calculate scale to fit both width and height with some margin
                const scaleX = containerWidth / svgWidth;
                const scaleY = containerHeight / svgHeight;
                const fitScale = Math.min(scaleX, scaleY) * 0.9; // 90% for some margin

                // Set initial zoom to fit the screen, but don't go below minZoom or above 1.0
                currentZoom = Math.max(minZoom, Math.min(fitScale, 1.0));

                // Reset pan to center
                panX = 0;
                panY = 0;

                updateTransform();
            }}
        }}

        // Wait for SVG to be fully loaded, then initialize
        if (svg && svg.complete !== false) {{
            // SVG is ready
            setTimeout(initializeFitToScreen, 100);
        }} else {{
            // Wait for SVG to load
            svg.addEventListener('load', initializeFitToScreen);
            setTimeout(initializeFitToScreen, 500); // Fallback
        }}
    </script>

</body>
</html>"""
        
        # Escape the DOT content for HTML
        escaped_dot = dot_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        return html_template.format(
            svg_content=svg_content,
            dot_content=escaped_dot
        )

    def _optimize_svg_viewbox(self, svg_content: str) -> str:
        """Optimize SVG viewBox to fit content snugly by analyzing element positions.

        Args:
            svg_content: SVG content with embedded icons.

        Returns:
            SVG content with optimized viewBox.
        """
        import re
        import xml.etree.ElementTree as ET

        try:
            # Parse the SVG content
            # Remove the XML declaration if present to avoid parsing issues
            svg_clean = re.sub(r'<\?xml[^>]*\?>', '', svg_content)

            # Parse with ElementTree
            root = ET.fromstring(svg_clean)

            # Find all elements with coordinates to determine actual content bounds
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')

            # Check all elements for position attributes
            for elem in root.iter():
                # Check for x, y attributes
                if 'x' in elem.attrib:
                    try:
                        x = float(elem.attrib['x'])
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                    except ValueError:
                        pass

                if 'y' in elem.attrib:
                    try:
                        y = float(elem.attrib['y'])
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)
                    except ValueError:
                        pass

                # Check for width and height to extend bounds
                if 'width' in elem.attrib and 'x' in elem.attrib:
                    try:
                        x = float(elem.attrib['x'])
                        width = float(elem.attrib['width'])
                        max_x = max(max_x, x + width)
                    except ValueError:
                        pass

                if 'height' in elem.attrib and 'y' in elem.attrib:
                    try:
                        y = float(elem.attrib['y'])
                        height = float(elem.attrib['height'])
                        max_y = max(max_y, y + height)
                    except ValueError:
                        pass

                # Check transform attributes for additional positioning
                if 'transform' in elem.attrib:
                    transform = elem.attrib['transform']
                    # Look for translate values
                    translate_match = re.search(r'translate\(([^,]+)[,\s]+([^)]+)\)', transform)
                    if translate_match:
                        try:
                            tx = float(translate_match.group(1))
                            ty = float(translate_match.group(2))
                            min_x = min(min_x, tx)
                            min_y = min(min_y, ty)
                            max_x = max(max_x, tx)
                            max_y = max(max_y, ty)
                        except ValueError:
                            pass

            # If we found valid bounds, update the viewBox
            if min_x != float('inf') and min_y != float('inf'):
                # Add small padding around content
                padding = 20
                content_min_x = max(0, min_x - padding)
                content_min_y = max(0, min_y - padding)
                content_width = (max_x - min_x) + (2 * padding)
                content_height = (max_y - min_y) + (2 * padding)

                # Update the viewBox attribute
                new_viewbox = f"{content_min_x} {content_min_y} {content_width} {content_height}"

                # Use regex to replace the existing viewBox
                viewbox_pattern = r'viewBox="[^"]*"'
                if re.search(viewbox_pattern, svg_content):
                    optimized_svg = re.sub(viewbox_pattern, f'viewBox="{new_viewbox}"', svg_content)
                    logger.debug(f"Optimized SVG viewBox to: {new_viewbox}")
                    return optimized_svg
                else:
                    # Add viewBox if it doesn't exist
                    svg_tag_pattern = r'<svg([^>]*?)>'
                    def add_viewbox(match):
                        attrs = match.group(1)
                        return f'<svg{attrs} viewBox="{new_viewbox}">'

                    optimized_svg = re.sub(svg_tag_pattern, add_viewbox, svg_content)
                    logger.debug(f"Added SVG viewBox: {new_viewbox}")
                    return optimized_svg

            logger.debug("No valid content bounds found, keeping original SVG")
            return svg_content

        except Exception as e:
            logger.warning(f"Failed to optimize SVG viewBox: {e}")
            return svg_content

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