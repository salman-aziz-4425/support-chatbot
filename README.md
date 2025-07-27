# 🤖 Multi-Agent Customer Support System

A sophisticated customer support system with AI agents, human agents, and seamless handoffs between them.

## 📁 Project Structure

```
autogen-project/
├── main.py                          # Main application entry point
├── requirements.txt                  # Python dependencies
├── README.md                        # This file
├── src/                             # Source code
│   ├── agents/                      # Agent implementations
│   │   ├── __init__.py
│   │   ├── ai_agent.py             # AI agent base class
│   │   ├── tools.py                # Function tools and delegate tools
│   │   └── websocket_agents.py     # WebSocket agents for human/user
│   ├── api/                         # API endpoints
│   │   ├── __init__.py
│   │   ├── routes.py               # REST API routes
│   │   └── websockets.py           # WebSocket endpoints
│   ├── models/                      # Data models
│   │   ├── __init__.py
│   │   └── message_models.py       # Pydantic models for messages
│   ├── services/                    # Business logic services
│   │   ├── __init__.py
│   │   ├── agent_runtime.py        # Agent runtime initialization
│   │   ├── connection_manager.py   # WebSocket connection management
│   │   └── transfer_service.py     # Human-to-AI transfer logic
│   └── utils/                       # Utility functions
│       ├── __init__.py
│       └── serialization.py        # Message serialization utilities
├── static/                          # Static files
│   ├── index.html                   # Customer chat interface
│   ├── agent_dashboard.html         # Human agent dashboard
│   ├── style.css                    # Stylesheets
│   └── script.js                    # Frontend JavaScript
└── autogen_env/                     # Virtual environment
```

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   python main.py
   ```

3. **Access the interfaces:**
   - Customer Chat: http://localhost:8000
   - Agent Dashboard: http://localhost:8000/agent-dashboard

## 🏗️ Architecture Overview

### **Core Components**

#### **🤖 AI Agents**
- **CustomerServiceTriageAgent**: Routes customer requests to appropriate specialists
- **TechnicalSupportAgent**: Handles hardware/software issues
- **BillingSupportAgent**: Manages payment and subscription issues
- **SalesSupportAgent**: Provides product information and sales assistance

#### **👨‍💼 Human Agents**
- **HumanSupportAgent**: Manages human agent interactions
- **ConnectionManager**: Tracks active connections and assignments

#### **🔄 Transfer System**
- **AI → AI**: Seamless handoffs between specialized agents
- **AI → Human**: Escalation for complex issues
- **Human → AI**: Transfer back to AI for routine tasks

### **Message Flow**

```
Customer → WebSocket → Agent Runtime → AI Agent → Response → Customer
Human Agent → WebSocket → Agent Runtime → Customer
```

## 📋 Key Features

### ✅ **Fixed Issues**
- **No duplicate messages** - Human agent messages sent once
- **No multiple connections** - Clean connection handling
- **Proper transfers** - AI ↔ Human ↔ AI all work
- **Clean code** - Organized into logical modules
- **Professional agent names** - Clear, descriptive agent identities

### 🔧 **System Capabilities**
- **Real-time communication** via WebSockets
- **Multi-agent routing** with intelligent handoffs
- **Human agent dashboard** with transfer controls
- **Conversation history** preservation
- **Error handling** and graceful fallbacks

## 🎯 Usage Examples

### **Customer Journey**
1. Customer opens chat → CustomerServiceTriageAgent greets
2. Customer asks technical question → Routes to TechnicalSupportAgent
3. Customer needs billing help → Transfers to BillingSupportAgent
4. Customer requests human → Escalates to HumanSupportAgent
5. Human agent transfers back → Routes to appropriate AI agent

### **Agent Responsibilities**

#### **CustomerServiceTriageAgent** 🎯
- Initial customer greeting and assessment
- Intelligent routing to specialized agents
- Handling transfers from human agents
- General customer service inquiries

#### **TechnicalSupportAgent** 🔧
- Hardware and software troubleshooting
- System configuration assistance
- Network and connectivity issues
- Technical documentation and guides

#### **BillingSupportAgent** 💳
- Payment processing and verification
- Subscription management
- Refund and billing inquiries
- Account billing questions

#### **SalesSupportAgent** 🛒
- Product information and features
- Pricing and package details
- Purchase assistance
- Sales inquiries and quotes

#### **HumanSupportAgent** 👤
- Complex issue resolution
- Customer complaints and escalations
- Account-specific assistance
- Personalized customer service

## 🔧 Technical Details

### **Agent Communication**
- **WebSocket-based** real-time messaging
- **Topic-based routing** for agent handoffs
- **Message persistence** for conversation history
- **Error recovery** and connection management

### **Security & Performance**
- **Connection validation** prevents duplicates
- **Message sanitization** for safe content
- **Graceful degradation** when agents unavailable
- **Scalable architecture** for multiple concurrent users

## 📊 System Status

Access system status at `/api/system/status` to monitor:
- Active agent connections
- Customer session status
- Human agent availability
- System performance metrics 