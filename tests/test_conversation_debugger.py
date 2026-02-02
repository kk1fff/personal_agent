"""Test conversation debugger subsection."""

import json
import pytest
from pathlib import Path
from src.web.subsections.conversation_debugger import ConversationDebuggerSubsection


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create temporary log directory."""
    log_dir = tmp_path / "logs" / "responses"
    log_dir.mkdir(parents=True)
    return log_dir


@pytest.fixture
def sample_trace(temp_log_dir):
    """Create sample trace JSON file."""
    trace_data = {
        "trace_id": "test-trace-123",
        "chat_id": 12345,
        "user_id": 98765,
        "timestamp": "2026-02-01T16:00:00",
        "end_time": "2026-02-01T16:00:05",
        "duration_ms": 5000,
        "user_message": "Hello bot",
        "bot_response": "Hi there!",
        "file_path": str(temp_log_dir / "response_12345_20260201_160000.json"),
        "events": [
            {
                "event_type": "request",
                "source": "telegram",
                "target": "dispatcher",
                "content_summary": "Hello bot",
                "timestamp": "2026-02-01T16:00:00",
                "metadata": {}
            },
            {
                "event_type": "llm_call",
                "source": "dispatcher",
                "target": "llm",
                "content_summary": "Processing request",
                "timestamp": "2026-02-01T16:00:01",
                "metadata": {"model": "gpt-4"}
            },
            {
                "event_type": "response",
                "source": "dispatcher",
                "target": "telegram",
                "content_summary": "Hi there!",
                "timestamp": "2026-02-01T16:00:05",
                "metadata": {}
            }
        ]
    }
    
    file_path = temp_log_dir / "response_12345_20260201_160000.json"
    with open(file_path, "w") as f:
        json.dump(trace_data, f)
    
    return trace_data


@pytest.mark.asyncio
async def test_conversation_debugger_initialization(temp_log_dir):
    """Test subsection initialization."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    
    assert debugger.name == "conversations"
    assert debugger.display_name == "Conversation Debugger"
    assert debugger.priority == 30


@pytest.mark.asyncio
async def test_get_initial_data_empty(temp_log_dir):
    """Test get_initial_data with no conversations."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    data = await debugger.get_initial_data()
    
    assert "conversations" in data
    assert data["conversations"] == []


@pytest.mark.asyncio
async def test_get_initial_data_with_conversations(temp_log_dir, sample_trace):
    """Test get_initial_data with sample conversation."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    data = await debugger.get_initial_data()
    
    assert "conversations" in data
    assert len(data["conversations"]) == 1
    
    conv = data["conversations"][0]
    assert conv["trace_id"] == "test-trace-123"
    assert conv["chat_id"] == 12345
    assert conv["user_id"] == 98765
    assert conv["user_message"] == "Hello bot"
    assert conv["event_count"] == 3
    assert conv["duration_ms"] == 5000


@pytest.mark.asyncio
async def test_load_trace_action(temp_log_dir, sample_trace):
    """Test load_trace action."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    
    result = await debugger.handle_action("load_trace", {"trace_id": "test-trace-123"})
    
    assert result["trace_id"] == "test-trace-123"
    assert result["chat_id"] == 12345
    assert len(result["events"]) == 3
    assert result["events"][0]["event_type"] == "request"


@pytest.mark.asyncio
async def test_load_trace_not_found(temp_log_dir):
    """Test load_trace with non-existent trace."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    
    result = await debugger.handle_action("load_trace", {"trace_id": "nonexistent"})
    
    assert "error" in result
    assert result["error"] == "Trace not found"


@pytest.mark.asyncio
async def test_html_template(temp_log_dir):
    """Test HTML template is returned."""
    debugger = ConversationDebuggerSubsection(log_dir=str(temp_log_dir))
    template = await debugger.get_html_template()
    
    assert "conversation-debugger" in template
    assert "conversation-selector" in template
    assert "conversation-analyzer" in template
    assert "x-data" in template  # Alpine.js
