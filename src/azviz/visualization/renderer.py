"""Graph rendering using Graphviz."""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional

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
            output_format: Output format (PNG or SVG).
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
            else:  # SVG
                graph.render(
                    filename=output_path.stem,
                    directory=output_path.parent,
                    format='svg',
                    cleanup=True
                )
                final_path = output_path.parent / f"{output_path.stem}.svg"
            
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
            output_format: Output format (PNG or SVG).
            engine: Graphviz engine to use.
            
        Returns:
            Rendered graph as bytes.
        """
        try:
            graph = graphviz.Source(dot_content, engine=engine)
            
            if output_format == OutputFormat.PNG:
                return graph.pipe(format='png')
            else:  # SVG
                return graph.pipe(format='svg')
                
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