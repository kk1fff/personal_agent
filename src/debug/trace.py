"""Request tracing for multi-agent orchestrator pattern."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class TraceEventType(Enum):
    """Types of events that can be traced."""
    REQUEST = "request"
    RESPONSE = "response"
    TOOL_CALL = "tool_call"
    DELEGATION = "delegation"
    ERROR = "error"


@dataclass
class TraceEvent:
    """Single event in the trace."""

    timestamp: datetime
    event_type: TraceEventType
    source: str  # Agent or tool name
    target: str  # Destination agent or tool
    content_summary: str
    duration_ms: Optional[float] = None
    trace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "source": self.source,
            "target": self.target,
            "content_summary": self.content_summary,
            "duration_ms": self.duration_ms,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


@dataclass
class RequestTrace:
    """Complete trace of a request through the multi-agent system."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    events: List[TraceEvent] = field(default_factory=list)

    def add_event(
        self,
        event_type: TraceEventType,
        source: str,
        target: str,
        content_summary: str,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        """Add an event to the trace.

        Args:
            event_type: Type of event
            source: Source agent/component
            target: Target agent/component
            content_summary: Brief description of the event
            duration_ms: Optional duration in milliseconds
            metadata: Optional additional metadata

        Returns:
            The created TraceEvent
        """
        event = TraceEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source=source,
            target=target,
            content_summary=content_summary,
            duration_ms=duration_ms,
            trace_id=self.trace_id,
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def complete(self) -> None:
        """Mark the trace as complete."""
        self.end_time = datetime.now()

    def get_duration_ms(self) -> float:
        """Get total trace duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now() - self.start_time).total_seconds() * 1000

    def to_svg_data(self) -> Dict[str, Any]:
        """Convert trace to data structure for SVG generation.

        Returns:
            Dictionary with trace data for SVG rendering
        """
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.get_duration_ms(),
            "events": [
                {
                    "type": e.event_type.value,
                    "source": e.source,
                    "target": e.target,
                    "summary": e.content_summary,
                    "time_offset_ms": (e.timestamp - self.start_time).total_seconds() * 1000,
                    "duration_ms": e.duration_ms,
                }
                for e in self.events
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.get_duration_ms(),
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
        }
