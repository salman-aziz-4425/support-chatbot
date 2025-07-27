
class ChatApp {
    constructor() {
        this.currentAgent = 'ai'; // 'ai' or 'human'
        this.isTransferring = false;
        this.messageHistory = [];
        this.isTyping = false;
        this.connectionStatus = 'connected';
        this.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.websocket = null;
        this.agentTypes = {}; // Store agent type information
        
        this.initializeElements();
        this.bindEvents();
        this.loadAgentTypes();
        this.initializeWebSocket();
        this.initializeChat();
    }

    initializeElements() {
        // Chat elements
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.transferNotice = document.getElementById('transferNotice');
        this.queuePosition = document.getElementById('queuePosition');
        this.charCount = document.getElementById('charCount');
        
        // Header elements
        this.agentName = document.getElementById('agent-name');
        this.agentStatus = document.getElementById('agent-status');
        this.agentIcon = document.getElementById('agent-icon');
        
        // Connection status
        this.connectionStatus = document.getElementById('connectionStatus');
        
        // Quick action buttons
        this.quickButtons = document.querySelectorAll('.quick-btn');
        
        // Control buttons
        this.btnMinimize = document.querySelector('.btn-minimize');
        this.btnClose = document.querySelector('.btn-close');
    }

    bindEvents() {
        // Message input events
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.messageInput.addEventListener('input', (e) => {
            this.updateCharCount();
            this.toggleSendButton();
        });

        // Send button
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Quick action buttons
        this.quickButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const message = e.currentTarget.dataset.message;
                console.log('Quick action clicked:', message);
                this.messageInput.value = message;
                this.sendMessage();
            });
        });

        // Control buttons
        this.btnMinimize.addEventListener('click', () => this.minimizeChat());
        this.btnClose.addEventListener('click', () => this.closeChat());

        // Focus input when clicking on chat
        this.chatMessages.addEventListener('click', () => {
            this.messageInput.focus();
        });
    }

    initializeWebSocket() {
        const wsUrl = `ws://localhost:8000/ws/chat`;
        
        // Close existing connection if any
        if (this.websocket && this.websocket.readyState !== WebSocket.CLOSED) {
            this.websocket.close();
        }
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus('connected');
        };
        
        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus('disconnected');
            setTimeout(() => {
                if (this.websocket.readyState === WebSocket.CLOSED) {
                    this.initializeWebSocket();
                }
            }, 3000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus('error');
        };
    }

    handleWebSocketMessage(data) {
        console.log('Received WebSocket message:', data);
        
        if (data.type === 'TextMessage') {
            this.hideTyping();
            
            const agentType = data.agent_type || 'GeneralSupport';
            const isHuman = data.source === 'Human_Support' || (data.source && data.source.startsWith('Human_Agent_'));
            
            if (data.source === 'AI_Support' || data.source?.includes('_AI')) {
                this.addBotMessage(data.content, false, agentType);
                this.updateAgentDisplay(agentType, false);
                
                // Check for transfer status instead of message content
                if (data.transfer_status === 'connecting') {
                    this.showTransferNotice();
                } else if (data.content.includes('no human agents are currently available') || 
                          data.content.includes('none are currently available')) {
                    // Explicitly hide transfer notice for no-agents-available messages
                    this.hideTransferNotice();
                }
            } else if (isHuman) {
                this.hideTransferNotice();
                this.addBotMessage(data.content, true, 'Human_Support');
                this.updateAgentDisplay('Human_Support', true);
            } else if (data.source === 'system') {
                this.addBotMessage(data.content, false, 'GeneralSupport');
            }
        } else if (data.type === 'error') {
            this.hideTyping();
            this.addBotMessage(`Error: ${data.content}`, false, 'GeneralSupport');
        } else if (data.type === 'UserInputRequestedEvent') {
            // Handle user input requests if needed
            console.log('User input requested:', data);
        }
    }

    updateAgentDisplay(agentType, isHuman) {
        const agentInfo = this.agentTypes[agentType];
        if (agentInfo && this.agentName) {
            this.agentName.textContent = agentInfo.display_name;
            this.agentName.style.color = agentInfo.color;
            
            if (this.agentIcon) {
                this.agentIcon.textContent = agentInfo.icon;
                this.agentIcon.className = ''; // Clear font-awesome classes
                this.agentIcon.style.fontSize = '1.2em';
            }
            
            this.agentStatus.textContent = 'Online';
            this.agentStatus.style.color = '#22c55e';
            
            this.currentAgent = isHuman ? 'human' : 'ai';
        }
    }

    async loadAgentTypes() {
        try {
            const response = await fetch('/api/agents/types');
            if (response.ok) {
                this.agentTypes = await response.json();
                console.log('Agent types loaded:', this.agentTypes);
            }
        } catch (error) {
            console.error('Failed to load agent types:', error);
        }
    }

    initializeChat() {
        this.messageInput.focus();
        this.updateConnectionStatus('connected');
    }

    showTransferNotice() {
        this.isTransferring = true;
        this.transferNotice.style.display = 'block';
        this.scrollToBottom();
    }

    hideTransferNotice() {
        this.isTransferring = false;
        this.transferNotice.style.display = 'none';
    }

    updateCharCount() {
        const count = this.messageInput.value.length;
        this.charCount.textContent = count;
        
        if (count > 450) {
            this.charCount.style.color = '#ef4444';
        } else if (count > 400) {
            this.charCount.style.color = '#f59e0b';
        } else {
            this.charCount.style.color = '#94a3b8';
        }
    }

    toggleSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;
        this.sendButton.disabled = !hasText || this.isTyping;
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isTyping) return;

        // Add user message to chat
        this.addUserMessage(message);
        this.messageInput.value = '';
        this.updateCharCount();
        this.toggleSendButton();

        // Store message in history
        this.messageHistory.push({
            role: 'user',
            content: message,
            timestamp: new Date()
        });

        // Show typing indicator
        this.simulateTyping();

        // Send message via WebSocket
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            try {
                const messageData = {
                    type: 'TextMessage',
                    content: message,
                    source: 'user'
                };
                this.websocket.send(JSON.stringify(messageData));
                console.log('Message sent via WebSocket:', messageData);
            } catch (error) {
                console.error('Error sending message via WebSocket:', error);
                this.hideTyping();
                this.addBotMessage("Sorry, there was an error sending your message. Please try again.", false, 'GeneralSupport');
            }
        } else {
            console.error('WebSocket not connected, readyState:', this.websocket ? this.websocket.readyState : 'null');
            this.hideTyping();
            this.addBotMessage("Connection lost. Please refresh the page to reconnect.", false, 'GeneralSupport');
        }
    }

    addUserMessage(message) {
        const messageElement = this.createMessageElement(message, 'user');
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addBotMessage(message, isHuman = false, agentType = 'GeneralSupport') {
        const messageElement = this.createMessageElement(message, 'bot', isHuman, agentType);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
        
        // Store in history
        this.messageHistory.push({
            role: isHuman ? 'human' : 'assistant',
            content: message,
            agentType: agentType,
            timestamp: new Date()
        });
    }

    createMessageElement(message, type, isHuman = false, agentType = 'GeneralSupport') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        
        if (type === 'user') {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        } else {
            const agentInfo = this.agentTypes[agentType];
            if (agentInfo) {
                avatar.innerHTML = `<span style="font-size: 1.2em;">${agentInfo.icon}</span>`;
                avatar.style.backgroundColor = agentInfo.color + '20'; // Add transparency
                avatar.style.borderColor = agentInfo.color;
            } else {
                avatar.innerHTML = isHuman ? '<i class="fas fa-user-tie"></i>' : '<i class="fas fa-robot"></i>';
            }
        }
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        // Add agent type label for bot messages
        if (type === 'bot' && !isHuman && this.agentTypes[agentType]) {
            const agentLabel = document.createElement('div');
            agentLabel.className = 'agent-label';
            agentLabel.style.cssText = `
                font-size: 0.75em;
                color: ${this.agentTypes[agentType].color};
                font-weight: 600;
                margin-bottom: 4px;
                opacity: 0.8;
            `;
            agentLabel.textContent = this.agentTypes[agentType].display_name;
            content.appendChild(agentLabel);
        }
        
        const messageText = document.createElement('p');
        messageText.textContent = message;
        
        const timestamp = document.createElement('span');
        timestamp.className = 'message-time';
        timestamp.textContent = this.formatTime(new Date());
        
        content.appendChild(messageText);
        content.appendChild(timestamp);
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        
        return messageDiv;
    }

    simulateTyping() {
        this.isTyping = true;
        this.typingIndicator.style.display = 'flex';
        this.toggleSendButton();
        this.scrollToBottom();
    }

    hideTyping() {
        this.isTyping = false;
        this.typingIndicator.style.display = 'none';
        this.toggleSendButton();
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }

    updateConnectionStatus(status) {
        const statusElement = this.connectionStatus;
        const statusText = statusElement.querySelector('span');
        const statusIcon = statusElement.querySelector('i');
        
        if (status === 'connected') {
            statusElement.className = 'connection-status';
            statusText.textContent = 'Connected';
            statusIcon.className = 'fas fa-wifi';
        } else {
            statusElement.className = 'connection-status disconnected';
            statusText.textContent = 'Disconnected';
            statusIcon.className = 'fas fa-wifi-slash';
        }
    }

    minimizeChat() {
        // In a real application, this would minimize the chat widget
        console.log('Chat minimized');
        document.querySelector('.chat-container').style.transform = 'scale(0.8)';
        setTimeout(() => {
            document.querySelector('.chat-container').style.transform = 'scale(1)';
        }, 200);
    }

    closeChat() {
        // In a real application, this would close the chat widget
        console.log('Chat closed');
        if (confirm('Are you sure you want to close the chat? Your conversation will be saved.')) {
            document.querySelector('.chat-container').style.opacity = '0';
            setTimeout(() => {
                document.querySelector('.chat-container').style.display = 'none';
            }, 300);
        }
    }

    // Public methods for external integration
    addMessage(message, type = 'bot') {
        if (type === 'bot') {
            this.addBotMessage(message);
        } else {
            this.addUserMessage(message);
        }
    }

    getCurrentAgent() {
        return this.currentAgent;
    }

    getMessageHistory() {
        return this.messageHistory;
    }
}

// Initialize the chat application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
    
    // Add some demo functionality
    console.log('AI Support Chatbot initialized');
    console.log('Try typing messages like:');
    console.log('- "I need help with billing"');
    console.log('- "I want to speak to a human"');
    console.log('- "I have a technical issue"');
});

// Service Worker registration for offline support (optional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('SW registered: ', registration);
            })
            .catch((registrationError) => {
                console.log('SW registration failed: ', registrationError);
            });
    });
} 