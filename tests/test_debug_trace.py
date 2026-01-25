"""Tests for debug trace module."""

import pytest
from datetime import datetime, timedelta

from src.debug.trace import TraceEventType, TraceEvent, RequestTrace


def test_trace_event_type_values():
    """Test trace event type enum values."""
    assert TraceEventType.REQUEST.value == "request"
    assert TraceEventType.RESPONSE.value == "response"
    assert TraceEventType.TOOL_CALL.value == "tool_call"
    assert TraceEventType.DELEGATION.value == "delegation"
    assert TraceEventType.ERROR.value == "error"


def test_trace_event_creation():
    """Test creating a trace event."""
    event = TraceEvent(
        timestamp=datetime.now(),
        event_type=TraceEventType.REQUEST,
        source="user",
        target="dispatcher",
        content_summary="Hello world",
    )

    assert event.event_type == TraceEventType.REQUEST
    assert event.source == "user"
    assert event.target == "dispatcher"
    assert event.content_summary == "Hello world"
    assert event.duration_ms is None


def test_trace_event_to_dict():
    """Test converting trace event to dictionary."""
    timestamp = datetime(2026, 1, 25, 10, 0, 0)
    event = TraceEvent(
        timestamp=timestamp,
        event_type=TraceEventType.DELEGATION,
        source="dispatcher",
        target="notion_specialist",
        content_summary="Search for documents",
        duration_ms=150.5,
        trace_id="abc123",
    )

    result = event.to_dict()

    assert result["timestamp"] == timestamp.isoformat()
    assert result["event_type"] == "delegation"
    assert result["source"] == "dispatcher"
    assert result["target"] == "notion_specialist"
    assert result["content_summary"] == "Search for documents"
    assert result["duration_ms"] == 150.5
    assert result["trace_id"] == "abc123"


def test_request_trace_creation():
    """Test creating a request trace."""
    trace = RequestTrace()

    assert trace.trace_id is not None
    assert trace.start_time is not None
    assert trace.end_time is None
    assert len(trace.events) == 0


def test_request_trace_add_event():
    """Test adding events to a trace."""
    trace = RequestTrace()

    event = trace.add_event(
        event_type=TraceEventType.REQUEST,
        source="telegram",
        target="dispatcher",
        content_summary="User message",
    )

    assert len(trace.events) == 1
    assert event.trace_id == trace.trace_id
    assert event.event_type == TraceEventType.REQUEST


def test_request_trace_complete():
    """Test completing a trace."""
    trace = RequestTrace()
    assert trace.end_time is None

    trace.complete()
    assert trace.end_time is not None


def test_request_trace_duration():
    """Test getting trace duration."""
    trace = RequestTrace()

    # Add some events
    trace.add_event(
        TraceEventType.REQUEST,
        "a", "b", "test"
    )

    # Duration should be > 0 even before completion
    duration = trace.get_duration_ms()
    assert duration >= 0


def test_request_trace_to_svg_data():
    """Test converting trace to SVG data."""
    trace = RequestTrace()

    trace.add_event(
        TraceEventType.REQUEST,
        source="telegram",
        target="dispatcher",
        content_summary="Hello",
    )
    trace.add_event(
        TraceEventType.DELEGATION,
        source="dispatcher",
        target="notion_specialist",
        content_summary="Search notes",
        duration_ms=100,
    )
    trace.complete()

    svg_data = trace.to_svg_data()

    assert svg_data["trace_id"] == trace.trace_id
    assert svg_data["start_time"] is not None
    assert svg_data["end_time"] is not None
    assert len(svg_data["events"]) == 2

    # Check first event
    first_event = svg_data["events"][0]
    assert first_event["type"] == "request"
    assert first_event["source"] == "telegram"
    assert first_event["target"] == "dispatcher"


def test_request_trace_to_dict():
    """Test converting trace to dictionary."""
    trace = RequestTrace()

    trace.add_event(
        TraceEventType.REQUEST,
        source="user",
        target="agent",
        content_summary="Test message",
    )
    trace.complete()

    result = trace.to_dict()

    assert result["trace_id"] == trace.trace_id
    assert result["event_count"] == 1
    assert len(result["events"]) == 1
    assert result["duration_ms"] >= 0


def test_request_trace_multiple_events():
    """Test trace with multiple events."""
    trace = RequestTrace()

    # Simulate a full request flow
    trace.add_event(
        TraceEventType.REQUEST,
        "telegram", "dispatcher", "User: Hello"
    )
    trace.add_event(
        TraceEventType.DELEGATION,
        "dispatcher", "chitchat_specialist", "Greeting detected"
    )
    trace.add_event(
        TraceEventType.RESPONSE,
        "chitchat_specialist", "dispatcher", "Hi there!",
        duration_ms=50,
    )
    trace.add_event(
        TraceEventType.RESPONSE,
        "dispatcher", "telegram", "Hi there!",
        duration_ms=5,
    )
    trace.complete()

    assert len(trace.events) == 4

    # Verify all events have trace_id
    for event in trace.events:
        assert event.trace_id == trace.trace_id
