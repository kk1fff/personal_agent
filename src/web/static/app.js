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
                    if (this.activeSection) {
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

// Global component for Conversation Debugger Subsection
function conversationDebugger() {
    return {
        selectedTraceId: null,
        selectedTrace: null,
        currentStep: 0,
        cleanupFuncs: [],

        init() {
            // Helper to bind and cleanup listeners
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
                    if (this.currentStep === this.totalSteps - 2) {
                        this.currentStep++;
                    }
                }
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

        async selectConversation(traceId) {
            this.selectedTraceId = traceId;
            this.currentStep = 0;
            const conv = this.data.conversations.find(c => c.trace_id === traceId);
            if (!conv) return;

            try {
                // Dispatch event to parent debugApp
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
            }
        },

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
