"""
PyCatan Visualization Interfaces

This module contains different display and interaction interfaces:
- Visualization: Abstract base class for all visualizations
- ConsoleVisualization: Terminal/console based display
- WebVisualization: Browser-based interactive board
"""

from .visualization import Visualization
from .console_visualization import ConsoleVisualization
from .web_visualization import WebVisualization, create_web_visualization

__all__ = [
    'Visualization',
    'ConsoleVisualization',
    'WebVisualization',
    'create_web_visualization',
]
