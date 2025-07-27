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
└── templates/                       # Template files (if needed)
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
- **TriageAgent**: Routes customer requests to appropriate specialists
- **TechnicalAgent**: Handles hardware/software issues
- **BillingAgent**: Manages payment and subscription issues
- **SalesAgent**: Provides product information and sales assistance

#### **👨‍💼 Human Agents**
- **WebSocketHumanAgent**: Manages human agent interactions
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

### 🔧 **System Capabilities**
- **Real-time communication** via WebSockets
- **Multi-agent routing** with intelligent handoffs
- **Human agent dashboard** with transfer controls
- **Conversation history** preservation
- **Error handling** and graceful fallbacks

## 🎯 Usage Examples

### **Customer Journey**
1. Customer opens chat → TriageAgent greets
2. Customer describes issue → AI routes to appropriate specialist
3. If complex → Escalates to human agent
4. Human can transfer back to AI if needed

### **Human Agent Workflow**
1. Login to agent dashboard
2. Receive customer assignments
3. View conversation history
4. Respond to customers
5. Transfer to AI agents when appropriate

## 🔧 API Endpoints

### **REST APIs**
- `GET /` - Customer chat interface
- `GET /agent-dashboard` - Human agent dashboard
- `POST /api/agent/login` - Agent authentication
- `GET /api/system/status` - System status
- `GET /api/agents/types` - Agent information
- `GET /api/human/transfer-options` - Transfer options

### **WebSocket Endpoints**
- `ws://localhost:8000/ws/chat` - Customer chat
- `ws://localhost:8000/ws/agent/{agent_id}` - Human agent

## 🛠️ Development

### **Adding New Agents**
1. Add agent type to `src/agents/tools.py`
2. Create agent class in `src/agents/ai_agent.py`
3. Register in `src/services/agent_runtime.py`

### **Adding New Tools**
1. Define function in `src/agents/tools.py`
2. Create FunctionTool instance
3. Add to agent's tools list

### **Modifying Transfers**
1. Update delegate tools in `src/agents/tools.py`
2. Modify transfer logic in `src/services/transfer_service.py`

## 📊 System Status

Monitor system health via:
```bash
curl http://localhost:8000/api/system/status
```

Returns:
```json
{
  "ai_agents": { "triage_agent": "active", ... },
  "human_agents": { "total_connected": 2, "available": 1 },
  "customers": { "total_connected": 5, "assigned_to_humans": 2 }
}
```

## 🎉 Benefits of New Structure

### **✅ Organization**
- **Logical separation** of concerns
- **Easy to find** specific functionality
- **Modular design** for easy maintenance

### **✅ Maintainability**
- **Clear imports** and dependencies
- **Isolated components** for testing
- **Scalable architecture** for new features

### **✅ Understanding**
- **Self-documenting** folder structure
- **Related code** grouped together
- **Clear responsibilities** for each module

---

**The system is now organized, maintainable, and easy to understand!** 🚀 