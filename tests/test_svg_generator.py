"""Tests for SVG data flow generator."""

import pytest

from src.debug.svg_generator import SVGDataFlowGenerator


@pytest.fixture
def generator():
    """Create SVG generator instance."""
    return SVGDataFlowGenerator()


def test_generate_empty_trace(generator):
    """Test generating SVG with no events."""
    trace_data = {"trace_id": "test123", "events": []}

    svg = generator.generate(trace_data)

    assert "svg" in svg
    assert "No trace events to display" in svg


def test_generate_single_event(generator):
    """Test generating SVG with a single event."""
    trace_data = {
        "trace_id": "test123",
        "duration_ms": 100,
        "events": [
            {
                "type": "request",
                "source": "telegram",
                "target": "dispatcher",
                "summary": "Hello world",
                "time_offset_ms": 0,
            }
        ]
    }

    svg = generator.generate(trace_data)

    assert "<svg" in svg
    assert "</svg>" in svg
    assert "telegram" in svg.lower() or "Telegram" in svg
    assert "dispatcher" in svg.lower() or "Dispatcher" in svg


def test_generate_multiple_events(generator):
    """Test generating SVG with multiple events."""
    trace_data = {
        "trace_id": "test123",
        "duration_ms": 250,
        "events": [
            {
                "type": "request",
                "source": "telegram",
                "target": "dispatcher",
                "summary": "User message",
                "time_offset_ms": 0,
            },
            {
                "type": "delegation",
                "source": "dispatcher",
                "target": "notion_specialist",
                "summary": "Search notes",
                "time_offset_ms": 50,
            },
            {
                "type": "response",
                "source": "notion_specialist",
                "target": "dispatcher",
                "summary": "Found 3 results",
                "time_offset_ms": 200,
                "duration_ms": 150,
            },
        ]
    }

    svg = generator.generate(trace_data)

    assert "<svg" in svg
    # Should have actor lanes
    assert "actor-lanes" in svg or "actor" in svg.lower()
    # Should have arrows for events
    assert "arrow" in svg.lower() or "line" in svg


def test_generate_with_duration(generator):
    """Test that duration is included in SVG."""
    trace_data = {
        "trace_id": "test123",
        "duration_ms": 150.5,
        "events": [
            {
                "type": "request",
                "source": "a",
                "target": "b",
                "summary": "Test",
                "time_offset_ms": 0,
                "duration_ms": 100.5,
            }
        ]
    }

    svg = generator.generate(trace_data)

    # Duration should be displayed
    assert "100.5" in svg or "ms" in svg


def test_extract_actors(generator):
    """Test extracting unique actors from events."""
    events = [
        {"source": "telegram", "target": "dispatcher"},
        {"source": "dispatcher", "target": "notion_specialist"},
        {"source": "notion_specialist", "target": "dispatcher"},
        {"source": "dispatcher", "target": "telegram"},
    ]

    actors = generator._extract_actors(events)

    # Should have unique actors
    assert len(actors) == 3
    # telegram and dispatcher should be first (default ordering)
    assert "telegram" in actors
    assert "dispatcher" in actors
    assert "notion_specialist" in actors


def test_colors_defined(generator):
    """Test that colors are defined for known actors."""
    assert "dispatcher" in generator.COLORS
    assert "notion_specialist" in generator.COLORS
    assert "calendar_specialist" in generator.COLORS
    assert "memory_specialist" in generator.COLORS
    assert "telegram" in generator.COLORS


def test_event_colors_defined(generator):
    """Test that colors are defined for event types."""
    assert "request" in generator.EVENT_COLORS
    assert "response" in generator.EVENT_COLORS
    assert "tool_call" in generator.EVENT_COLORS
    assert "delegation" in generator.EVENT_COLORS
    assert "error" in generator.EVENT_COLORS


def test_svg_includes_styles(generator):
    """Test that SVG includes CSS styles."""
    trace_data = {
        "trace_id": "test",
        "events": [
            {"type": "request", "source": "a", "target": "b", "summary": "test", "time_offset_ms": 0}
        ]
    }

    svg = generator.generate(trace_data)

    assert "<style>" in svg
    assert "</style>" in svg


def test_svg_includes_defs(generator):
    """Test that SVG includes marker definitions."""
    trace_data = {
        "trace_id": "test",
        "events": [
            {"type": "request", "source": "a", "target": "b", "summary": "test", "time_offset_ms": 0}
        ]
    }

    svg = generator.generate(trace_data)

    assert "<defs>" in svg
    assert "</defs>" in svg
    assert "arrowhead" in svg


def test_long_summary_truncated(generator):
    """Test that long summaries are truncated."""
    long_summary = "x" * 100

    trace_data = {
        "trace_id": "test",
        "events": [
            {"type": "request", "source": "a", "target": "b", "summary": long_summary, "time_offset_ms": 0}
        ]
    }

    svg = generator.generate(trace_data)

    # Full summary should not appear, truncated with ... should
    assert long_summary not in svg
    assert "..." in svg


def test_custom_dimensions(generator):
    """Test custom width and row height."""
    custom_gen = SVGDataFlowGenerator(width=1200, row_height=80)

    assert custom_gen.width == 1200
    assert custom_gen.row_height == 80
