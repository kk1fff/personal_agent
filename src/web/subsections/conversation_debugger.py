"""Conversation debugger subsection for web UI."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..base import BaseSubsection
from ..registry import subsection

logger = logging.getLogger(__name__)


@subsection
class ConversationDebuggerSubsection(BaseSubsection):
    """Displays conversation traces for debugging."""

    def __init__(self, log_dir: str = "logs/responses"):
        """Initialize conversation debugger.

        Args:
            log_dir: Directory containing JSON trace files
        """
        super().__init__(
            name="conversations",
            display_name="Conversation Debugger",
            priority=30,
            icon="💬",
        )
        self.log_dir = Path(log_dir)

    async def get_initial_data(self) -> Dict[str, Any]:
        """Load all conversation traces from disk.

        Returns:
            Dictionary with list of conversations
        """
        conversations = self._load_conversations()
        return {"conversations": conversations}

    def _load_conversations(self) -> List[Dict[str, Any]]:
        """Scan log directory for JSON trace files.

        Returns:
            List of conversation summaries sorted by timestamp (newest first)
        """
        if not self.log_dir.exists():
            return []

        conversations = []
        for json_file in self.log_dir.glob("response_*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract summary info
                conversations.append({
                    "trace_id": data.get("trace_id", ""),
                    "chat_id": data.get("chat_id", 0),
                    "user_id": data.get("user_id"),
                    "timestamp": data.get("timestamp", ""),
                    "duration_ms": data.get("duration_ms", 0),
                    "user_message": data.get("user_message", "")[:100],  # Truncate
                    "event_count": len(data.get("events", [])),
                    "file_path": str(json_file),
                })
            except Exception as e:
                logger.warning(f"Failed to load {json_file}: {e}")
                continue

        # Sort by timestamp descending (newest first)
        conversations.sort(key=lambda x: x["timestamp"], reverse=True)
        return conversations

    async def get_html_template(self) -> str:
        """Return HTML template for conversation debugger.

        Returns:
            HTML string with Alpine.js directives
        """
        return """
<div class="conversation-debugger" x-data="conversationDebugger()">
    <div class="debugger-layout">
        <!-- Left Panel: Conversation Selector -->
        <div class="conversation-selector">
            <div class="selector-header">
                <h3>Conversations</h3>
                <span class="count" x-text="data.conversations.length"></span>
            </div>
            <div class="conversation-list">
                <template x-for="conv in data.conversations" :key="conv.trace_id">
                    <div 
                        class="conversation-item"
                        :class="{ 'active': selectedTraceId === conv.trace_id }"
                        @click="selectConversation(conv.trace_id)">
                        <div class="conv-time" x-text="formatTimestamp(conv.timestamp)"></div>
                        <div class="conv-chat">Chat: <span x-text="conv.chat_id"></span></div>
                        <div class="conv-message" x-text="conv.user_message"></div>
                        <div class="conv-meta">
                            <span x-text="conv.event_count + ' steps'"></span>
                            <span x-text="(conv.duration_ms / 1000).toFixed(2) + 's'"></span>
                        </div>
                    </div>
                </template>
                <div x-show="data.conversations.length === 0" class="empty-state">
                    No conversations yet
                </div>
            </div>
        </div>

        <!-- Right Panel: Conversation Analyzer -->
        <div class="conversation-analyzer">
            <div x-show="!selectedTrace" class="empty-state">
                Select a conversation to analyze
            </div>

            <div x-show="selectedTrace" class="analyzer-content">
                <!-- Header -->
                <div class="analyzer-header">
                    <h3>Conversation Analysis</h3>
                    <div class="header-info">
                        <span>Trace ID: <code x-text="selectedTrace?.trace_id"></code></span>
                        <span>Duration: <span x-text="(selectedTrace?.duration_ms / 1000).toFixed(2) + 's'"></span></span>
                    </div>
                </div>

                <!-- Canvas: Data Flow Visualization -->
                <div class="flow-canvas">
                    <div class="flow-step" x-show="currentEvent">
                        <div class="step-header">
                            <span class="step-number" x-text="'Step ' + (currentStep + 1) + ' / ' + totalSteps"></span>
                            <span class="step-type" x-text="currentEvent?.event_type"></span>
                        </div>

                        <!-- Diagram controls -->
                        <div class="diagram-controls">
                            <label class="view-all-toggle">
                                <input type="checkbox" x-model="viewAll"> View All
                            </label>
                        </div>

                        <!-- Interactive SVG diagram -->
                        <div class="diagram-container" x-ref="diagramContainer"
                             @wheel.prevent="handleWheel($event)"
                             @mousedown="handleMouseDown($event)"
                             @mousemove="handleMouseMove($event)"
                             @mouseup="handleMouseUp()"
                             @mouseleave="handleMouseUp()">
                            <svg x-ref="diagramSvg" class="flow-diagram"
                                 xmlns="http://www.w3.org/2000/svg"
                                 width="200" height="146">
                                <defs>
                                    <marker id="arrow-active" markerWidth="12" markerHeight="8" refX="11" refY="4" orient="auto" markerUnits="strokeWidth">
                                        <path d="M0,0 L12,4 L0,8 L3,4 Z" class="arrow-marker-active"/>
                                    </marker>
                                </defs>
                                <g x-ref="diagramGroup"></g>
                            </svg>
                        </div>

                        <div class="flow-content" x-text="currentEvent?.content_summary"></div>
                        <div x-show="currentMetadataEntries.length > 0" class="flow-metadata">
                            <details open>
                                <summary>Details</summary>
                                <div class="metadata-table-wrapper">
                                    <table class="metadata-table">
                                        <thead>
                                            <tr>
                                                <th>Key</th>
                                                <th>Value</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <template x-for="[key, value] in currentMetadataEntries" :key="key">
                                                <tr>
                                                    <td class="meta-key" x-text="key"></td>
                                                    <td class="meta-value">
                                                        <template x-if="typeof value === 'object' && value !== null">
                                                            <pre x-text="JSON.stringify(value, null, 2)"></pre>
                                                        </template>
                                                        <template x-if="typeof value !== 'object' || value === null">
                                                            <div x-text="value" class="text-value"></div>
                                                        </template>
                                                    </td>
                                                </tr>
                                            </template>
                                        </tbody>
                                    </table>
                                </div>
                            </details>
                        </div>
                    </div>
                </div>

                <!-- Controls -->
                <div class="analyzer-controls">
                    <button @click="prevStep" :disabled="currentStep === 0">← Prev</button>
                    <input 
                        type="range" 
                        :min="0" 
                        :max="totalSteps - 1" 
                        x-model.number="currentStep"
                        class="step-slider">
                    <button @click="nextStep" :disabled="currentStep >= totalSteps - 1">Next →</button>
                </div>
            </div>
        </div>
    </div>
</div>



<style>
.conversation-debugger {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.debugger-layout {
    display: grid;
    grid-template-columns: 350px 1fr;
    gap: 1rem;
    height: 100%;
    overflow: hidden;
}

.conversation-selector {
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border-color, #e0e0e0);
    overflow: hidden;
}

.selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.selector-header h3 {
    margin: 0;
    font-size: 1.1rem;
}

.selector-header .count {
    background: var(--accent-color, #007bff);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-size: 0.85rem;
}

.conversation-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
}

.conversation-item {
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.conversation-item:hover {
    background: var(--hover-bg, #f5f5f5);
    border-color: var(--accent-color, #007bff);
}

.conversation-item.active {
    background: var(--accent-light, #e3f2fd);
    border-color: var(--accent-color, #007bff);
}

.conv-time {
    font-size: 0.85rem;
    color: var(--text-secondary, #666);
    margin-bottom: 0.25rem;
}

.conv-chat {
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 0.25rem;
}

.conv-message {
    font-size: 0.9rem;
    color: var(--text-primary, #333);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 0.25rem;
}

.conv-meta {
    display: flex;
    gap: 0.75rem;
    font-size: 0.8rem;
    color: var(--text-secondary, #666);
}

.conversation-analyzer {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.analyzer-content {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.analyzer-header {
    padding: 1rem;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.analyzer-header h3 {
    margin: 0 0 0.5rem 0;
}

.header-info {
    display: flex;
    gap: 1rem;
    font-size: 0.9rem;
    color: var(--text-secondary, #666);
}

.flow-canvas {
    flex: 1;
    padding: 2rem;
    padding-bottom: 5rem; /* Extra space for fixed controls */
    overflow-y: auto;
}

.flow-step {
    max-width: 800px;
    margin: 0 auto;
}

.step-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 1rem;
}

.step-number {
    font-weight: 600;
    color: var(--accent-color, #007bff);
}

.step-type {
    background: var(--tag-bg, #e0e0e0);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
    text-transform: uppercase;
}

.diagram-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.5rem;
}

.view-all-toggle {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.9rem;
    cursor: pointer;
    user-select: none;
}

.view-all-toggle input[type="checkbox"] {
    cursor: pointer;
}

.diagram-container {
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 8px;
    overflow: hidden;
    background: var(--card-bg, #f9f9f9);
    min-height: 120px;
    margin-bottom: 1rem;
    position: relative;
    cursor: grab;
    user-select: none;
}

.diagram-container:active {
    cursor: grabbing;
}

.flow-diagram {
    display: block;
    width: 100%;
}

.flow-diagram rect,
.flow-diagram text,
.flow-diagram line,
.flow-diagram path {
    transition: all 0.3s ease;
}

.flow-diagram .comp-box-active {
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.15));
}

.flow-diagram .comp-box-inactive {
    opacity: 0.3;
}

.flow-diagram .comp-label {
    font: 600 12px sans-serif;
    text-anchor: middle;
    pointer-events: none;
}

.flow-diagram .comp-label-active {
    fill: #1f2937;
}

.flow-diagram .comp-label-inactive {
    fill: #9ca3af;
}

.flow-diagram .event-arrow-active {
    stroke-width: 3;
}

.flow-diagram .event-arrow-inactive {
    stroke-width: 1;
    opacity: 0.2;
}

.arrow-marker-active {
    fill: #6B7280;
}

.flow-content {
    padding: 1rem;
    background: var(--card-bg, #f9f9f9);
    border-left: 4px solid var(--accent-color, #007bff);
    border-radius: 4px;
    font-family: monospace;
    white-space: pre-wrap;
    word-break: break-word;
}

.flow-metadata {
    margin-top: 1rem;
}

.flow-metadata details {
    background: var(--card-bg, #f9f9f9);
    padding: 0.5rem;
    border-radius: 4px;
}

.flow-metadata summary {
    cursor: pointer;
    font-weight: 600;
    padding: 0.5rem;
}

.flow-metadata pre {
    margin: 0;
    padding: 0.25rem;
    background: transparent;
    border: none;
    overflow-x: auto;
    font-size: 0.85rem;
}

.metadata-table-wrapper {
    margin-top: 0.5rem;
    background: white;
    border: 1px solid var(--border-color, #e0e0e0);
    border-radius: 4px;
    overflow: hidden;
}

.metadata-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.metadata-table th,
.metadata-table td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--border-color, #eee);
    text-align: left;
    vertical-align: top;
}

.metadata-table th {
    background: var(--bg-secondary, #f5f5f5);
    font-weight: 600;
    color: var(--text-secondary, #666);
    width: 30%;
}

.meta-key {
    font-family: monospace;
    font-weight: 600;
    color: var(--accent-dark, #0056b3);
}

.meta-value {
    font-family: monospace;
    white-space: pre-wrap;
    word-break: break-word;
}

.text-value {
    white-space: pre-wrap;
}

.analyzer-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    border-top: 1px solid var(--border-color, #e0e0e0);
    position: fixed;
    bottom: 0;
    left: 350px; /* Width of conversation-selector + gap */
    right: 0;
    background: white;
    z-index: 100;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

.step-slider {
    flex: 1;
}

.analyzer-controls button {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color, #e0e0e0);
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.analyzer-controls button:hover:not(:disabled) {
    background: var(--accent-color, #007bff);
    color: white;
    border-color: var(--accent-color, #007bff);
}

.analyzer-controls button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-secondary, #666);
    font-style: italic;
}
</style>
"""

    async def handle_action(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle actions from the frontend.

        Args:
            action: Action name
            data: Action payload

        Returns:
            Response data
        """
        if action == "load_trace":
            trace_id = data.get("trace_id")
            if not trace_id:
                return {"error": "trace_id required"}

            # Find the JSON file
            for json_file in self.log_dir.glob("response_*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        trace_data = json.load(f)
                    if trace_data.get("trace_id") == trace_id:
                        return trace_data
                except Exception as e:
                    logger.warning(f"Failed to load {json_file}: {e}")
                    continue

            return {"error": "Trace not found"}

        return await super().handle_action(action, data)
