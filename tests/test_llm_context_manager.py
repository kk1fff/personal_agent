
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from src.context.context_manager import ConversationContextManager
from src.context.models import Message
from src.llm.base import BaseLLM, LLMResponse

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_llm():
    llm = AsyncMock(spec=BaseLLM)
    llm.generate.return_value = LLMResponse(text="Summarized context")
    return llm

@pytest.mark.asyncio
async def test_get_llm_context(mock_db, mock_llm):
    # Setup
    chat_id = 123
    user_id = 456
    query = "What did we discuss?"
    
    # Mock messages
    messages = [
        Message(
            chat_id=chat_id, user_id=user_id, message_text="Hello",
            role="user", timestamp=datetime.now(timezone.utc), message_id=1
        ),
        Message(
            chat_id=chat_id, user_id=user_id, message_text="Hi there",
            role="assistant", timestamp=datetime.now(timezone.utc), message_id=2
        )
    ]
    mock_db.get_recent_messages.return_value = messages

    # Initialize manager
    manager = ConversationContextManager(
        db=mock_db,
        llm=mock_llm,
        message_limit=5
    )

    # Execute
    summary, count = await manager.get_llm_context(chat_id, user_id, query)

    # Verify
    assert summary == "Summarized context"
    assert count == 2
    mock_db.get_recent_messages.assert_called_once_with(chat_id, 5)
    mock_llm.generate.assert_called_once()
    
    # Check prompt content roughly
    call_args = mock_llm.generate.call_args[0][0]
    assert "User: Hello" in call_args
    assert "Assistant: Hi there" in call_args
    assert query in call_args

@pytest.mark.asyncio
async def test_get_llm_context_no_llm(mock_db):
    manager = ConversationContextManager(db=mock_db, llm=None)
    
    with pytest.raises(ValueError, match="LLM not initialized"):
        await manager.get_llm_context(1, 1, "query")

@pytest.mark.asyncio
async def test_get_llm_context_no_messages(mock_db, mock_llm):
    mock_db.get_recent_messages.return_value = []
    
    manager = ConversationContextManager(db=mock_db, llm=mock_llm)
    summary, count = await manager.get_llm_context(1, 1, "query")
    
    assert count == 0
    assert "No previous conversation context" in summary
    mock_llm.generate.assert_not_called()
