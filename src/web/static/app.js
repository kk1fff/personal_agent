function debugApp() {
    return {
        // State
        sections: [],
        activeSection: null,
        currentTemplate: '',
        data: {},
        wsStatus: 'connecting',
        ws: null,
        overflowOpen: false,
        visibleCount: 5,
        loading: true,
        reconnectAttempts: 0,
        maxReconnectAttempts: 10,
        reconnectDelay: 1000,

        // Computed
        get visibleSections() {
            return this.sections.slice(0, this.visibleCount);
        },

        get overflowSections() {
            return this.sections.slice(this.visibleCount);
        },

        get overflowHasActive() {
            return this.overflowSections.some(s => s.name === this.activeSection);
        },

        // Lifecycle
        async init() {
            await this.loadSections();
            this.connectWebSocket();
            this.handleResize();
            window.addEventListener('resize', () => this.handleResize());

            // Listen for actions from subsections
            window.addEventListener('send-action', (e) => {
                if (e.detail && e.detail.action) {
                    this.sendAction(e.detail.action, e.detail.data);
                }
            });
        },

        // Methods
        async loadSections() {
            this.loading = true;
            try {
                const response = await fetch('/api/subsections');
                if (!response.ok) throw new Error('Failed to load subsections');
                this.sections = await response.json();
                if (this.sections.length > 0) {
                    await this.selectSection(this.sections[0].name);
                }
            } catch (err) {
                console.error('Failed to load sections:', err);
            } finally {
                this.loading = false;
            }
        },

        async selectSection(name) {
            if (this.activeSection === name) return;

            this.activeSection = name;
            this.loading = true;

            try {
                const response = await fetch(`/api/subsection/${name}`);
                if (!response.ok) throw new Error('Failed to load subsection');
                const result = await response.json();
                this.data = result.data;
                this.currentTemplate = result.template;

                // Subscribe to updates via WebSocket
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'subscribe',
                        subsection: name
                    }));
                }
            } catch (err) {
                console.error('Failed to load subsection:', err);
                this.currentTemplate = '<div class="error">Failed to load subsection</div>';
            } finally {
                this.loading = false;
            }
        },

        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            try {
                this.ws = new WebSocket(wsUrl);
                this.wsStatus = 'connecting';

                this.ws.onopen = () => {
                    this.wsStatus = 'connected';
                    this.reconnectAttempts = 0;
                    this.reconnectDelay = 1000;

                    // Re-subscribe to current section
                    if (this.activeSection && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({
                            type: 'subscribe',
                            subsection: this.activeSection
                        }));
                    }
                };

                this.ws.onclose = (event) => {
                    this.wsStatus = 'disconnected';
                    this.scheduleReconnect();
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.wsStatus = 'disconnected';
                };

                this.ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        this.handleWSMessage(message);
                    } catch (e) {
                        console.error('Failed to parse WebSocket message:', e);
                    }
                };
            } catch (e) {
                console.error('Failed to create WebSocket:', e);
                this.wsStatus = 'disconnected';
                this.scheduleReconnect();
            }
        },

        scheduleReconnect() {
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.error('Max reconnection attempts reached');
                return;
            }

            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000);

            setTimeout(() => {
                if (this.wsStatus === 'disconnected') {
                    this.connectWebSocket();
                }
            }, delay);
        },

        handleWSMessage(message) {
            if (message.type === 'update' && message.subsection === this.activeSection) {
                // Merge update into current data
                if (message.data) {
                    // Special handling for new conversations
                    if (message.data.new_conversation && this.activeSection === 'conversations') {
                        const newConv = message.data.new_conversation;
                        // Prepend new conversation (newest first)
                        if (!this.data.conversations.find(c => c.trace_id === newConv.trace_id)) {
                            this.data.conversations = [newConv, ...this.data.conversations];
                        }
                    } else if (message.data.conversation_update && this.activeSection === 'conversations') {
                        const update = message.data.conversation_update;
                        // Update conversation list item logic
                        const conv = this.data.conversations.find(c => c.trace_id === update.trace_id);
                        if (conv) {
                            conv.event_count = (conv.event_count || 0) + 1;
                            // Update timestamp to now to show activity? 
                            // Maybe not, keep start time.
                        }
                        // Dispatch event for subsection component to handle details
                        window.dispatchEvent(new CustomEvent('conversation-update', { detail: update }));
                    } else {
                        // Deep merge for nested objects, replace for arrays
                        for (const [key, value] of Object.entries(message.data)) {
                            if (Array.isArray(value)) {
                                this.data[key] = value;
                            } else if (typeof value === 'object' && value !== null) {
                                this.data[key] = { ...this.data[key], ...value };
                            } else {
                                this.data[key] = value;
                            }
                        }
                    }
                }
            } else if (message.type === 'action_result') {
                // Handle action results - pass to subsection handler if available
                console.log('Action result:', message);
                // Trigger custom event for subsection to handle
                window.dispatchEvent(new CustomEvent('subsection-action-result', { detail: message }));
            }
        },

        handleResize() {
            // Adjust visible count based on window width
            const width = window.innerWidth;
            if (width < 500) {
                this.visibleCount = 2;
            } else if (width < 700) {
                this.visibleCount = 3;
            } else if (width < 900) {
                this.visibleCount = 4;
            } else if (width < 1100) {
                this.visibleCount = 5;
            } else {
                this.visibleCount = 7;
            }
        },

        // Action helper for subsections to use
        async sendAction(action, payload = {}) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'action',
                    subsection: this.activeSection,
                    action: action,
                    data: payload
                }));
            }
        }
    };
}

// Color maps for diagram components and event types
const COMPONENT_COLORS = {
    telegram: '#229ED9',
    dispatcher: '#4A90D9',
    notion_specialist: '#7B68EE',
    calendar_specialist: '#20B2AA',
    memory_specialist: '#FF8C00',
    chitchat_specialist: '#9370DB',
    tool: '#808080',
    default: '#6B7280',
};

const EVENT_TYPE_COLORS = {
    request: '#4CAF50',
    response: '#2196F3',
    tool_call: '#FF9800',
    delegation: '#9C27B0',
    llm_request: '#607D8B',
    llm_response: '#00BCD4',
    vector_search: '#FF5722',
    error: '#F44336',
};

function _getComponentColor(name) {
    const key = name.toLowerCase().replace(/\s+/g, '_');
    return COMPONENT_COLORS[key] || COMPONENT_COLORS.default;
}

function _getEventColor(eventType) {
    const key = eventType.toLowerCase().replace(/\s+/g, '_');
    return EVENT_TYPE_COLORS[key] || EVENT_TYPE_COLORS.request;
}

// SVG namespace
const SVG_NS = 'http://www.w3.org/2000/svg';

// Global component for Conversation Debugger Subsection
function conversationDebugger() {
    return {
        selectedTraceId: null,
        selectedTrace: null,
        currentStep: 0,
        cleanupFuncs: [],

        // Diagram state
        viewAll: true,
        allComponents: [],       // [{name, x, y, color}]
        componentPositions: {},  // name -> {x, y}
        diagramRendered: false,

        // Pan/zoom state (manual, no library)
        zoomLevel: 1,
        panX: 0,
        panY: 0,
        isPanning: false,
        panStartX: 0,
        panStartY: 0,
        panStartPanX: 0,
        panStartPanY: 0,

        // Layout constants
        BOX_W: 130,
        BOX_H: 46,
        BOX_PAD: 30,
        SVG_PAD: 30,
        BOX_RX: 8,

        init() {
            const bindListener = (event, handler) => {
                const boundHandler = handler.bind(this);
                window.addEventListener(event, boundHandler);
                this.cleanupFuncs.push(() => window.removeEventListener(event, boundHandler));
            };

            bindListener('subsection-action-result', (e) => {
                const result = e.detail?.result;
                if (result && result.trace_id) {
                    this.handleTraceLoaded(result);
                }
            });

            bindListener('conversation-update', (e) => {
                const update = e.detail;
                if (this.selectedTrace && update.trace_id === this.selectedTrace.trace_id) {
                    this.selectedTrace.events.push(update.event);
                    // Recompute layout if new components appear
                    this.computeLayout(this.selectedTrace);
                    if (this.currentStep === this.totalSteps - 2) {
                        this.currentStep++;
                    }
                }
            });

            // Watch for step changes and viewAll toggle to update highlighting
            this.$watch('currentStep', () => {
                this.updateHighlighting();
            });
            this.$watch('viewAll', () => {
                this.renderDiagram();
            });
        },

        destroy() {
            this.cleanupFuncs.forEach(fn => fn());
            this.cleanupFuncs = [];
        },

        get totalSteps() {
            return this.selectedTrace?.events?.length || 0;
        },

        get currentEvent() {
            if (!this.selectedTrace || this.currentStep >= this.totalSteps) {
                return null;
            }
            return this.selectedTrace.events[this.currentStep];
        },

        get currentMetadataEntries() {
            const meta = this.currentEvent?.metadata;
            if (!meta || typeof meta !== 'object') return [];
            return Object.entries(meta);
        },

        async selectConversation(traceId) {
            this.selectedTraceId = traceId;
            this.currentStep = 0;
            this.resetView();
            this.diagramRendered = false;
            const conv = this.data.conversations.find(c => c.trace_id === traceId);
            if (!conv) return;

            try {
                window.dispatchEvent(new CustomEvent('send-action', {
                    detail: {
                        action: 'load_trace',
                        data: { trace_id: traceId }
                    }
                }));
            } catch (e) {
                console.error('Failed to load trace:', e);
            }
        },

        handleTraceLoaded(traceData) {
            if (traceData && traceData.trace_id === this.selectedTraceId) {
                this.selectedTrace = traceData;
                this.computeLayout(traceData);
                this.$nextTick(() => {
                    this.renderDiagram();
                });
            }
        },

        // ---- Layout computation (stable positions) ----

        computeLayout(trace) {
            if (!trace || !trace.events || trace.events.length === 0) {
                this.allComponents = [];
                this.componentPositions = {};
                return;
            }

            // Extract unique components in order of first appearance
            const seen = new Set();
            const names = [];
            for (const ev of trace.events) {
                for (const actor of [ev.source, ev.target]) {
                    if (actor && !seen.has(actor)) {
                        seen.add(actor);
                        names.push(actor);
                    }
                }
            }

            // Compute positions - horizontal row
            const components = [];
            const positions = {};

            for (let i = 0; i < names.length; i++) {
                const name = names[i];
                const x = this.SVG_PAD + i * (this.BOX_W + this.BOX_PAD);
                const y = this.SVG_PAD;
                const color = _getComponentColor(name);
                components.push({ name, x, y, color });
                positions[name] = { x, y };
            }

            this.allComponents = components;
            this.componentPositions = positions;
        },

        // ---- SVG rendering ----

        _getSvgDimensions() {
            const totalW = this.allComponents.length * (this.BOX_W + this.BOX_PAD) - this.BOX_PAD + this.SVG_PAD * 2;
            const totalH = this.BOX_H + this.SVG_PAD * 2 + 40;
            return { w: Math.max(totalW, 200), h: Math.max(totalH, 100) };
        },

        renderDiagram() {
            const group = this.$refs.diagramGroup;
            const svg = this.$refs.diagramSvg;
            if (!group || !svg) return;

            // Clear existing content
            while (group.firstChild) {
                group.removeChild(group.firstChild);
            }

            if (this.allComponents.length === 0) return;

            const event = this.currentEvent;
            const source = event?.source;
            const target = event?.target;
            const eventType = event?.event_type || 'request';

            // Determine which components to render
            let componentsToRender;
            if (this.viewAll) {
                componentsToRender = this.allComponents;
            } else {
                componentsToRender = this.allComponents.filter(
                    c => c.name === source || c.name === target
                );
            }

            // Set SVG viewBox (always based on ALL components for stable sizing)
            const dim = this._getSvgDimensions();
            svg.setAttribute('viewBox', `0 0 ${dim.w} ${dim.h}`);
            svg.setAttribute('width', dim.w);
            svg.setAttribute('height', dim.h);

            // Apply pan/zoom transform to the group
            group.setAttribute('transform',
                `translate(${this.panX}, ${this.panY}) scale(${this.zoomLevel})`);

            // Update arrow marker color
            const marker = svg.querySelector('#arrow-active');
            if (marker) {
                const markerPath = marker.querySelector('path');
                if (markerPath) {
                    markerPath.setAttribute('fill', _getEventColor(eventType));
                }
            }

            // Draw arrow first (behind boxes)
            if (source && target && source !== target) {
                const srcPos = this.componentPositions[source];
                const tgtPos = this.componentPositions[target];
                if (srcPos && tgtPos) {
                    this._drawArrow(group, srcPos, tgtPos, eventType);
                }
            }

            // Draw component boxes
            for (const comp of componentsToRender) {
                const isActive = comp.name === source || comp.name === target;
                this._drawComponent(group, comp, isActive);
            }

            this.diagramRendered = true;
        },

        _drawComponent(parent, comp, isActive) {
            const g = document.createElementNS(SVG_NS, 'g');
            g.setAttribute('data-comp', comp.name);

            const rect = document.createElementNS(SVG_NS, 'rect');
            rect.setAttribute('x', comp.x);
            rect.setAttribute('y', comp.y);
            rect.setAttribute('width', this.BOX_W);
            rect.setAttribute('height', this.BOX_H);
            rect.setAttribute('rx', this.BOX_RX);

            if (isActive) {
                rect.setAttribute('fill', comp.color);
                rect.setAttribute('fill-opacity', '0.15');
                rect.setAttribute('stroke', comp.color);
                rect.setAttribute('stroke-width', '2.5');
                rect.setAttribute('class', 'comp-box-active');
            } else {
                rect.setAttribute('fill', '#f3f4f6');
                rect.setAttribute('fill-opacity', '0.6');
                rect.setAttribute('stroke', '#d1d5db');
                rect.setAttribute('stroke-width', '1');
                rect.setAttribute('class', 'comp-box-inactive');
            }

            g.appendChild(rect);

            const text = document.createElementNS(SVG_NS, 'text');
            text.setAttribute('x', comp.x + this.BOX_W / 2);
            text.setAttribute('y', comp.y + this.BOX_H / 2 + 4);
            text.setAttribute('class', isActive ? 'comp-label comp-label-active' : 'comp-label comp-label-inactive');

            // Truncate long names
            const displayName = comp.name.replace(/_/g, ' ');
            const truncated = displayName.length > 16 ? displayName.slice(0, 14) + '..' : displayName;
            text.textContent = truncated;

            g.appendChild(text);
            parent.appendChild(g);
        },

        _drawArrow(parent, srcPos, tgtPos, eventType) {
            const color = _getEventColor(eventType);

            // Source and target x centers
            const srcCx = srcPos.x + this.BOX_W / 2;
            const tgtCx = tgtPos.x + this.BOX_W / 2;

            // Start/end at box edges (midpoint of side)
            let x1, x2;
            if (srcCx < tgtCx) {
                x1 = srcPos.x + this.BOX_W;
                x2 = tgtPos.x;
            } else {
                x1 = srcPos.x;
                x2 = tgtPos.x + this.BOX_W;
            }

            const y1 = srcPos.y + this.BOX_H / 2;
            const y2 = tgtPos.y + this.BOX_H / 2;

            // Curved path below the boxes
            const midY = Math.max(y1, y2) + this.BOX_H / 2 + 14;
            const controlOffset = Math.abs(x2 - x1) * 0.15;

            const path = document.createElementNS(SVG_NS, 'path');
            const d = `M ${x1} ${y1} `
                    + `C ${x1 + (x2 > x1 ? controlOffset : -controlOffset)} ${midY}, `
                    + `${x2 + (x2 > x1 ? -controlOffset : controlOffset)} ${midY}, `
                    + `${x2} ${y2}`;

            path.setAttribute('d', d);
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', color);
            path.setAttribute('stroke-width', '3');
            path.setAttribute('marker-end', 'url(#arrow-active)');
            path.setAttribute('class', 'event-arrow-active');

            parent.appendChild(path);
        },

        // ---- Highlighting update ----

        updateHighlighting() {
            if (!this.diagramRendered) return;
            // Re-render content; pan/zoom state is preserved via zoomLevel/panX/panY
            this.renderDiagram();
        },

        // ---- Manual Pan/Zoom ----

        handleWheel(e) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            this.zoomLevel = Math.max(0.3, Math.min(5, this.zoomLevel + delta));
            this._applyTransform();
        },

        handleMouseDown(e) {
            if (e.button !== 0) return; // left button only
            this.isPanning = true;
            this.panStartX = e.clientX;
            this.panStartY = e.clientY;
            this.panStartPanX = this.panX;
            this.panStartPanY = this.panY;
            e.preventDefault();
        },

        handleMouseMove(e) {
            if (!this.isPanning) return;
            const dx = e.clientX - this.panStartX;
            const dy = e.clientY - this.panStartY;
            this.panX = this.panStartPanX + dx / this.zoomLevel;
            this.panY = this.panStartPanY + dy / this.zoomLevel;
            this._applyTransform();
        },

        handleMouseUp() {
            this.isPanning = false;
        },

        _applyTransform() {
            const group = this.$refs.diagramGroup;
            if (!group) return;
            group.setAttribute('transform',
                `translate(${this.panX}, ${this.panY}) scale(${this.zoomLevel})`);
        },

        resetView() {
            this.zoomLevel = 1;
            this.panX = 0;
            this.panY = 0;
        },

        // ---- Navigation ----

        nextStep() {
            if (this.currentStep < this.totalSteps - 1) {
                this.currentStep++;
            }
        },

        prevStep() {
            if (this.currentStep > 0) {
                this.currentStep--;
            }
        },

        formatTimestamp(ts) {
            if (!ts) return '';
            const date = new Date(ts);
            return date.toLocaleString();
        }
    };
}
