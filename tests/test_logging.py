import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from src.debug import RequestTrace, TraceEventType, TelegramResponseLogger
from src.agent.agent_processor import PydanticAIModelAdapter
from src.llm.base import BaseLLM, LLMResponse

@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=BaseLLM)
    llm.generate = AsyncMock(return_value=LLMResponse(text="test response"))
    llm.get_model_name = MagicMock(return_value="test-model")
    return llm

@pytest.fixture
def trace():
    return RequestTrace()

@pytest.mark.asyncio
async def test_llm_request_logging(mock_llm, trace):
    adapter = PydanticAIModelAdapter(mock_llm)
    adapter.set_trace(trace)
    
    await adapter.request([])
    
    events = trace.events
    assert len(events) >= 2
    assert any(e.event_type == TraceEventType.LLM_REQUEST for e in events)
    assert any(e.event_type == TraceEventType.LLM_RESPONSE for e in events)

def test_trace_event_types():
    assert TraceEventType.LLM_REQUEST.value == "llm_request"
    assert TraceEventType.LLM_RESPONSE.value == "llm_response"

def test_trace_svg_data(trace):
    trace.add_event(
        TraceEventType.LLM_REQUEST,
        source="agent",
        target="model",
        content_summary="request"
    )
    
    data = trace.to_svg_data()
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "llm_request"

def test_response_logger_metadata_formatting(tmp_path):
    # Setup logger with temp dir
    log_dir = tmp_path / "logs"
    logger = TelegramResponseLogger(log_dir=str(log_dir), enable_svg=False)
    
    # Create trace with metadata
    trace = RequestTrace()
    trace.add_event(
        TraceEventType.LLM_REQUEST,
        source="agent", 
        target="llm",
        content_summary="request",
        metadata={"full_content": "Instruction\nMulti-line\nContent"}
    )
    
    # Log response
    chat_id = 123
    trace.complete()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    # Mocking datetime isn't strictly necessary if we rely on return value
    # But TelegramResponseLogger generates filename internally.
    
    log_path = logger.log_response(trace, chat_id, "user msg", "bot response")
    
    # Verify log content
    assert log_path is not None
    with open(log_path, "r") as f:
        content = f.read()
        
    assert "Metadata:" in content
    assert "full_content:" in content
    assert "Multi-line" in content
