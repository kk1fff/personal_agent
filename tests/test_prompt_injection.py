"""Tests for prompt injection system."""

import json
import tempfile
from pathlib import Path

import pytest

from src.agent.prompt_injection import BasePromptInjector, PromptInjectionRegistry
from src.notion.prompt_injector import NotionPromptInjector


class MockInjector(BasePromptInjector):
    """Mock injector for testing."""

    def __init__(self, name: str, context: str, priority: int = 100):
        super().__init__(name, priority)
        self._context = context

    def get_context(self):
        return self._context


class FailingInjector(BasePromptInjector):
    """Injector that raises an exception."""

    def __init__(self):
        super().__init__("failing", priority=100)

    def get_context(self):
        raise RuntimeError("Intentional failure")


class TestBasePromptInjector:
    """Tests for BasePromptInjector."""

    def test_get_name(self):
        injector = MockInjector("test", "context")
        assert injector.get_name() == "test"

    def test_get_priority(self):
        injector = MockInjector("test", "context", priority=50)
        assert injector.get_priority() == 50

    def test_default_priority(self):
        injector = MockInjector("test", "context")
        assert injector.get_priority() == 100


class TestPromptInjectionRegistry:
    """Tests for PromptInjectionRegistry."""

    def test_register_injector(self):
        registry = PromptInjectionRegistry()
        injector = MockInjector("test", "Test context")
        registry.register(injector)
        assert len(registry.get_injectors()) == 1

    def test_register_multiple_injectors(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("a", "Context A"))
        registry.register(MockInjector("b", "Context B"))
        assert len(registry.get_injectors()) == 2

    def test_collect_all_context(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("a", "Context A"))
        registry.register(MockInjector("b", "Context B"))

        context = registry.collect_all_context()
        assert "Context A" in context
        assert "Context B" in context

    def test_collect_context_respects_priority(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("low", "Low priority", priority=100))
        registry.register(MockInjector("high", "High priority", priority=50))

        context = registry.collect_all_context()
        # High priority (lower number) should come first
        assert context.index("High priority") < context.index("Low priority")

    def test_empty_registry(self):
        registry = PromptInjectionRegistry()
        assert registry.collect_all_context() == ""

    def test_none_context_skipped(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("a", None))
        registry.register(MockInjector("b", "Context B"))

        context = registry.collect_all_context()
        assert context == "Context B"

    def test_empty_string_context_skipped(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("a", ""))
        registry.register(MockInjector("b", "Context B"))

        context = registry.collect_all_context()
        assert context == "Context B"

    def test_failing_injector_skipped(self):
        registry = PromptInjectionRegistry()
        registry.register(FailingInjector())
        registry.register(MockInjector("b", "Context B"))

        # Should not raise, should skip failing injector
        context = registry.collect_all_context()
        assert context == "Context B"

    def test_clear(self):
        registry = PromptInjectionRegistry()
        registry.register(MockInjector("a", "Context A"))
        registry.clear()
        assert len(registry.get_injectors()) == 0


class TestNotionPromptInjector:
    """Tests for NotionPromptInjector."""

    def test_file_not_found(self):
        injector = NotionPromptInjector("/nonexistent/path.json")
        assert injector.get_context() is None

    def test_valid_info_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "generated_at": "2026-01-24T12:00:00Z",
                    "summary": "Test summary of workspace.",
                    "workspaces": [
                        {
                            "name": "Main",
                            "page_count": 10,
                            "topics": ["Projects", "Notes"],
                        }
                    ],
                },
                f,
            )
            f.flush()

            injector = NotionPromptInjector(f.name)
            context = injector.get_context()

            assert context is not None
            assert "Test summary of workspace" in context
            assert "Main: 10 pages" in context
            assert "Projects" in context

            Path(f.name).unlink()

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json")
            f.flush()

            injector = NotionPromptInjector(f.name)
            assert injector.get_context() is None

            Path(f.name).unlink()

    def test_empty_info_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"summary": "", "workspaces": []}, f)
            f.flush()

            injector = NotionPromptInjector(f.name)
            assert injector.get_context() is None

            Path(f.name).unlink()

    def test_summary_only(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "summary": "Just a summary without workspaces.",
                    "workspaces": [],
                },
                f,
            )
            f.flush()

            injector = NotionPromptInjector(f.name)
            context = injector.get_context()

            assert context is not None
            assert "Just a summary without workspaces" in context

            Path(f.name).unlink()

    def test_workspaces_only(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "summary": "",
                    "workspaces": [
                        {"name": "Work", "page_count": 5, "topics": ["Meetings"]}
                    ],
                },
                f,
            )
            f.flush()

            injector = NotionPromptInjector(f.name)
            context = injector.get_context()

            assert context is not None
            assert "Work: 5 pages" in context

            Path(f.name).unlink()

    def test_default_path(self):
        injector = NotionPromptInjector()
        assert injector.info_path == Path("data/notion/info.json")

    def test_injector_name_and_priority(self):
        injector = NotionPromptInjector()
        assert injector.get_name() == "notion"
        assert injector.get_priority() == 50

    def test_multiple_workspaces(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "summary": "Multi-workspace summary.",
                    "workspaces": [
                        {"name": "Personal", "page_count": 20, "topics": ["Notes"]},
                        {"name": "Work", "page_count": 30, "topics": ["Projects"]},
                    ],
                },
                f,
            )
            f.flush()

            injector = NotionPromptInjector(f.name)
            context = injector.get_context()

            assert "Personal: 20 pages" in context
            assert "Work: 30 pages" in context

            Path(f.name).unlink()

    def test_topics_truncated(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "summary": "",
                    "workspaces": [
                        {
                            "name": "Many Topics",
                            "page_count": 100,
                            "topics": ["A", "B", "C", "D", "E", "F", "G", "H"],
                        }
                    ],
                },
                f,
            )
            f.flush()

            injector = NotionPromptInjector(f.name)
            context = injector.get_context()

            # Only first 5 topics should be shown
            assert "A, B, C, D, E" in context
            assert "F" not in context

            Path(f.name).unlink()
