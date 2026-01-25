"""SVG diagram generator for multi-agent data flow visualization."""

import html
from typing import Any, Dict, List, Set


class SVGDataFlowGenerator:
    """Generates SVG sequence diagrams showing request/response flow.

    Creates visual representations of how requests flow through the
    multi-agent system, including delegations and tool calls.
    """

    # Colors for different components
    COLORS = {
        "telegram": "#229ED9",  # Telegram blue
        "dispatcher": "#4A90D9",  # Blue
        "notion_specialist": "#7B68EE",  # Medium slate blue
        "calendar_specialist": "#20B2AA",  # Light sea green
        "memory_specialist": "#FF8C00",  # Dark orange
        "chitchat_specialist": "#9370DB",  # Medium purple
        "tool": "#808080",  # Gray
        "default": "#6B7280",  # Gray
    }

    # Event type colors
    EVENT_COLORS = {
        "request": "#4CAF50",  # Green
        "response": "#2196F3",  # Blue
        "tool_call": "#FF9800",  # Orange
        "delegation": "#9C27B0",  # Purple
        "error": "#F44336",  # Red
    }

    def __init__(self, width: int = 900, row_height: int = 60, margin: int = 40):
        """Initialize SVG generator.

        Args:
            width: SVG width in pixels
            row_height: Height per event row
            margin: Margin around the diagram
        """
        self.width = width
        self.row_height = row_height
        self.margin = margin

    def generate(self, trace_data: Dict[str, Any]) -> str:
        """Generate SVG from trace data.

        Args:
            trace_data: Dictionary with trace information from RequestTrace.to_svg_data()

        Returns:
            SVG content as string
        """
        events = trace_data.get("events", [])
        if not events:
            return self._generate_empty_svg()

        # Extract unique actors
        actors = self._extract_actors(events)

        # Calculate dimensions
        height = (len(events) + 3) * self.row_height + self.margin * 2
        lane_width = (self.width - self.margin * 2) // max(len(actors), 1)

        # Build SVG
        svg_parts = [self._get_header(height)]
        svg_parts.append(self._get_styles())
        svg_parts.append(self._get_defs())

        # Draw actor lanes
        svg_parts.append(self._draw_actor_lanes(actors, lane_width, height))

        # Draw events
        for i, event in enumerate(events):
            svg_parts.append(self._draw_event(event, i, actors, lane_width))

        # Add trace info
        svg_parts.append(self._draw_trace_info(trace_data))

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def _get_header(self, height: int) -> str:
        """Get SVG header."""
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}" viewBox="0 0 {self.width} {height}">'''

    def _get_styles(self) -> str:
        """Get CSS styles."""
        return '''<style>
            .actor-label { font: bold 12px sans-serif; fill: #374151; }
            .actor-line { stroke: #D1D5DB; stroke-width: 2; stroke-dasharray: 5,5; }
            .event-label { font: 11px sans-serif; fill: #4B5563; }
            .arrow { stroke-width: 2; fill: none; }
            .arrow-request { stroke: #4CAF50; }
            .arrow-response { stroke: #2196F3; }
            .arrow-tool_call { stroke: #FF9800; }
            .arrow-delegation { stroke: #9C27B0; }
            .arrow-error { stroke: #F44336; }
            .trace-info { font: 10px monospace; fill: #6B7280; }
            .title { font: bold 14px sans-serif; fill: #1F2937; }
        </style>'''

    def _get_defs(self) -> str:
        """Get SVG definitions (markers, etc.)."""
        return '''<defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#6B7280"/>
            </marker>
            <marker id="arrowhead-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#4CAF50"/>
            </marker>
            <marker id="arrowhead-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#2196F3"/>
            </marker>
            <marker id="arrowhead-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#FF9800"/>
            </marker>
            <marker id="arrowhead-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#9C27B0"/>
            </marker>
        </defs>'''

    def _extract_actors(self, events: List[Dict[str, Any]]) -> List[str]:
        """Extract unique actors from events in order of first appearance."""
        seen: Set[str] = set()
        actors: List[str] = []

        # Always start with telegram and dispatcher
        for default in ["telegram", "dispatcher"]:
            if default not in seen:
                seen.add(default)
                actors.append(default)

        for event in events:
            for actor in [event.get("source", ""), event.get("target", "")]:
                if actor and actor not in seen:
                    seen.add(actor)
                    actors.append(actor)

        return actors

    def _draw_actor_lanes(self, actors: List[str], lane_width: int, height: int) -> str:
        """Draw vertical lanes for each actor."""
        parts = ['<g class="actor-lanes">']

        for i, actor in enumerate(actors):
            x = self.margin + (i + 0.5) * lane_width

            # Actor box
            color = self.COLORS.get(actor, self.COLORS["default"])
            parts.append(
                f'<rect x="{x - 50}" y="{self.margin}" width="100" height="30" '
                f'rx="5" fill="{color}" opacity="0.2"/>'
            )

            # Actor label
            display_name = actor.replace("_", " ").title()
            parts.append(
                f'<text x="{x}" y="{self.margin + 20}" text-anchor="middle" '
                f'class="actor-label">{html.escape(display_name)}</text>'
            )

            # Vertical line
            parts.append(
                f'<line x1="{x}" y1="{self.margin + 35}" x2="{x}" y2="{height - self.margin}" '
                f'class="actor-line"/>'
            )

        parts.append("</g>")
        return "\n".join(parts)

    def _draw_event(
        self,
        event: Dict[str, Any],
        index: int,
        actors: List[str],
        lane_width: int
    ) -> str:
        """Draw an event as an arrow between actors."""
        parts = ['<g class="event">']

        source = event.get("source", "")
        target = event.get("target", "")
        event_type = event.get("type", "request")
        summary = event.get("summary", "")

        # Get positions
        try:
            source_idx = actors.index(source)
        except ValueError:
            source_idx = 0

        try:
            target_idx = actors.index(target)
        except ValueError:
            target_idx = min(source_idx + 1, len(actors) - 1)

        source_x = self.margin + (source_idx + 0.5) * lane_width
        target_x = self.margin + (target_idx + 0.5) * lane_width
        y = self.margin + 50 + (index + 1) * self.row_height

        # Determine arrow direction and marker
        if source_x < target_x:
            x1, x2 = source_x + 5, target_x - 5
        elif source_x > target_x:
            x1, x2 = source_x - 5, target_x + 5
        else:
            # Self-reference
            x1, x2 = source_x, source_x + 30

        marker_map = {
            "request": "arrowhead-green",
            "response": "arrowhead-blue",
            "tool_call": "arrowhead-orange",
            "delegation": "arrowhead-purple",
        }
        marker = marker_map.get(event_type, "arrowhead")

        # Draw arrow
        parts.append(
            f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
            f'class="arrow arrow-{event_type}" marker-end="url(#{marker})"/>'
        )

        # Draw label
        mid_x = (x1 + x2) / 2
        truncated = summary[:40] + "..." if len(summary) > 40 else summary
        parts.append(
            f'<text x="{mid_x}" y="{y - 8}" text-anchor="middle" '
            f'class="event-label">{html.escape(truncated)}</text>'
        )

        # Add timing if available
        duration = event.get("duration_ms")
        if duration:
            parts.append(
                f'<text x="{mid_x}" y="{y + 15}" text-anchor="middle" '
                f'class="trace-info">{duration:.1f}ms</text>'
            )

        parts.append("</g>")
        return "\n".join(parts)

    def _draw_trace_info(self, trace_data: Dict[str, Any]) -> str:
        """Draw trace information box."""
        trace_id = trace_data.get("trace_id", "")[:8]
        duration = trace_data.get("duration_ms", 0)
        event_count = len(trace_data.get("events", []))

        y = self.margin + 10

        return f'''<g class="trace-info-box">
            <text x="{self.width - self.margin}" y="{y}" text-anchor="end" class="trace-info">
                Trace: {trace_id} | Events: {event_count} | Duration: {duration:.1f}ms
            </text>
        </g>'''

    def _generate_empty_svg(self) -> str:
        """Generate an empty SVG with a message."""
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="100">
            <text x="{self.width // 2}" y="50" text-anchor="middle"
                  style="font: 14px sans-serif; fill: #6B7280;">
                No trace events to display
            </text>
        </svg>'''
