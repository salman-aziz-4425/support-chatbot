import json
import logging
import os
from typing import Any, Awaitable, Callable, Optional, Dict, Sequence, List, Tuple
from datetime import datetime
import asyncio
import uuid

import aiofiles
import yaml
from autogen_core import (
    AgentId,
    FunctionCall,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
    message_handler,
    CancellationToken
)
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from autogen_core.tools import FunctionTool, Tool
from autogen_ext.models.ollama import OllamaChatCompletionClient
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger(__name__)

def safe_serialize_content(content):
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        serialized_items = []
        for item in content:
            try:
                if hasattr(item, 'name') and hasattr(item, 'arguments'):
                    serialized_items.append(f"Function call: {item.name}")
                else:
                    item_str = str(item)
                    import json
                    json.dumps(item_str)
                    serialized_items.append(item_str)
            except Exception:
                serialized_items.append(f"[Unserializable item: {type(item).__name__}]")
        
        return "; ".join(serialized_items) if serialized_items else "Processing request..."
    else:
        return str(content)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state_path = "team_state.json"
history_path = "team_history.json"

class UserLogin(BaseModel):
    customer_id: str

class UserTask(BaseModel):
    context: List[LLMMessage]

class AgentResponse(BaseModel):
    reply_to_topic_type: str
    context: List[LLMMessage]

triage_agent_topic_type = "TriageAgent"
technical_agent_topic_type = "TechnicalAgent"
billing_agent_topic_type = "BillingAgent"
sales_agent_topic_type = "SalesAgent"
human_agent_topic_type = "HumanAgent"
user_topic_type = "User"

def transfer_to_technical() -> str:
    return technical_agent_topic_type

def transfer_to_billing() -> str:
    return billing_agent_topic_type

def transfer_to_sales() -> str:
    return sales_agent_topic_type

def transfer_back_to_triage() -> str:
    return triage_agent_topic_type

def escalate_to_human() -> str:
    return human_agent_topic_type

def human_transfer_to_technical() -> str:
    return technical_agent_topic_type

def human_transfer_to_billing() -> str:
    return billing_agent_topic_type

def human_transfer_to_sales() -> str:
    return sales_agent_topic_type

def human_transfer_to_triage() -> str:
    return triage_agent_topic_type

transfer_to_technical_tool = FunctionTool(
    transfer_to_technical, 
    description="Transfer to technical support for hardware, software, network, installation, or troubleshooting issues."
)

transfer_to_billing_tool = FunctionTool(
    transfer_to_billing,
    description="Transfer to billing support for payment, subscription, refund, invoice, or account billing issues."
)

transfer_to_sales_tool = FunctionTool(
    transfer_to_sales,
    description="Transfer to sales for product information, purchasing, upgrades, or sales inquiries."
)

transfer_back_to_triage_tool = FunctionTool(
    transfer_back_to_triage,
    description="Transfer back to triage when the topic is outside your expertise or for general routing."
)

escalate_to_human_tool = FunctionTool(
    escalate_to_human, 
    description="Escalate to human agent for complex issues, complaints, or when customer explicitly requests human assistance."
)

human_to_technical_tool = FunctionTool(
    human_transfer_to_technical,
    description="Transfer customer from human agent to technical AI support for technical issues."
)

human_to_billing_tool = FunctionTool(
    human_transfer_to_billing,
    description="Transfer customer from human agent to billing AI support for billing issues."
)

human_to_sales_tool = FunctionTool(
    human_transfer_to_sales,
    description="Transfer customer from human agent to sales AI support for sales inquiries."
)

human_to_triage_tool = FunctionTool(
    human_transfer_to_triage,
    description="Transfer customer from human agent back to triage AI for general routing or new requests."
)

def lookup_account_info(customer_query: str) -> str:
    return f"Account info retrieved for query: {customer_query}"

def create_support_ticket(issue_description: str, priority: str = "medium") -> str:
    ticket_id = f"TICKET-{datetime.now().strftime('%Y%m%d')}-{hash(issue_description) % 10000:04d}"
    return f"Support ticket created: {ticket_id} (Priority: {priority})"

def check_system_status(service_name: str) -> str:
    return f"System status for {service_name}: All services operational"

lookup_account_tool = FunctionTool(lookup_account_info, description="Look up customer account information")
create_ticket_tool = FunctionTool(create_support_ticket, description="Create a support ticket for complex issues")
check_status_tool = FunctionTool(check_system_status, description="Check system or service status")

class AIAgent(RoutedAgent):
    def __init__(
        self,
        description: str,
        system_message: SystemMessage,
        model_client: ChatCompletionClient,
        tools: List[Tool],
        delegate_tools: List[Tool],
        agent_topic_type: str,
        user_topic_type: str,
    ) -> None:
        super().__init__(description)
        self._system_message = system_message
        self._model_client = model_client
        self._tools = dict([(tool.name, tool) for tool in tools])
        self._tool_schema = [tool.schema for tool in tools]
        self._delegate_tools = dict([(tool.name, tool) for tool in delegate_tools])
        self._delegate_tool_schema = [tool.schema for tool in delegate_tools]
        self._agent_topic_type = agent_topic_type
        self._user_topic_type = user_topic_type

    @message_handler
    async def handle_task(self, message: UserTask, ctx: MessageContext) -> None:
        try:
            llm_result = await self._model_client.create(
                messages=[self._system_message] + message.context,
                tools=self._tool_schema + self._delegate_tool_schema,
                cancellation_token=ctx.cancellation_token,
            )
            
            while isinstance(llm_result.content, list) and all(isinstance(m, FunctionCall) for m in llm_result.content):
                tool_call_results: List[FunctionExecutionResult] = []
                delegate_targets: List[Tuple[str, UserTask]] = []
                
                for call in llm_result.content:
                    arguments = json.loads(call.arguments)
                    
                    if call.name in self._tools:
                        result = await self._tools[call.name].run_json(arguments, ctx.cancellation_token)
                        result_as_str = self._tools[call.name].return_value_as_string(result)
                        tool_call_results.append(
                            FunctionExecutionResult(
                                call_id=call.id, 
                                content=result_as_str, 
                                is_error=False, 
                                name=call.name
                            )
                        )
                    elif call.name in self._delegate_tools:
                        result = await self._delegate_tools[call.name].run_json(arguments, ctx.cancellation_token)
                        topic_type = self._delegate_tools[call.name].return_value_as_string(result)
                        
                        delegate_messages = list(message.context) + [
                            AssistantMessage(content=[call], source=self.id.type),
                            FunctionExecutionResultMessage(
                                content=[
                                    FunctionExecutionResult(
                                        call_id=call.id,
                                        content=f"Transferred to {topic_type}. Adopt persona immediately.",
                                        is_error=False,
                                        name=call.name,
                                    )
                                ]
                            ),
                        ]
                        delegate_targets.append((topic_type, UserTask(context=delegate_messages)))
                    else:
                        raise ValueError(f"Unknown tool: {call.name}")
                
                if len(delegate_targets) > 0:
                    for topic_type, task in delegate_targets:
                        await self.publish_message(task, topic_id=TopicId(topic_type, source=ctx.topic_id.source))
                    return
                
                if len(tool_call_results) > 0:
                    message.context.extend([
                        AssistantMessage(content=llm_result.content, source=self.id.type),
                        FunctionExecutionResultMessage(content=tool_call_results),
                    ])
                    
                    llm_result = await self._model_client.create(
                        messages=[self._system_message] + message.context,
                        tools=self._tool_schema + self._delegate_tool_schema,
                        cancellation_token=ctx.cancellation_token,
                    )
            
            assert isinstance(llm_result.content, str)
            message.context.append(AssistantMessage(content=llm_result.content, source=self.id.type))
            await self.publish_message(
                AgentResponse(context=message.context, reply_to_topic_type=self._agent_topic_type),
                topic_id=TopicId(self._user_topic_type, source=ctx.topic_id.source),
            )
            
        except Exception as e:
            logger.error(f"Error in {self.id.type}.handle_task: {str(e)}")
            error_message = AssistantMessage(
                content="I apologize, but I encountered an error processing your request. Please try again.", 
                source=self.id.type
            )
            message.context.append(error_message)
            await self.publish_message(
                AgentResponse(context=message.context, reply_to_topic_type=self._agent_topic_type),
                topic_id=TopicId(self._user_topic_type, source=ctx.topic_id.source),
            )

class ConnectionManager:
    def __init__(self):
        self.active_customer_connections: Dict[str, WebSocket] = {}
        self.active_human_agents: Dict[str, WebSocket] = {}
        self.customer_conversations: Dict[str, list] = {}
        self.customer_to_agent: Dict[str, str] = {}
        self.pending_human_tasks: Dict[str, UserTask] = {}
        
    async def connect_customer(self, customer_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_customer_connections[customer_id] = websocket
        if customer_id not in self.customer_conversations:
            self.customer_conversations[customer_id] = []
        
    async def connect_human_agent(self, agent_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_human_agents[agent_id] = websocket
        
    def disconnect_customer(self, customer_id: str):
        if customer_id in self.active_customer_connections:
            del self.active_customer_connections[customer_id]
        if customer_id in self.customer_to_agent:
            del self.customer_to_agent[customer_id]
        if customer_id in self.pending_human_tasks:
            del self.pending_human_tasks[customer_id]
            
    def disconnect_human_agent(self, agent_id: str):
        if agent_id in self.active_human_agents:
            del self.active_human_agents[agent_id]
        customers_to_remove = [cid for cid, aid in self.customer_to_agent.items() if aid == agent_id]
        for cid in customers_to_remove:
            del self.customer_to_agent[cid]
            
    def get_available_human_agents(self) -> list:
        all_agents = set(self.active_human_agents.keys())
        busy_agents = set(self.customer_to_agent.values())
        available = list(all_agents - busy_agents)
        return available
    
    def assign_human_agent(self, customer_id: str, agent_id: str):
        self.customer_to_agent[customer_id] = agent_id

manager = ConnectionManager()

class WebSocketHumanAgent(RoutedAgent):
    def __init__(self, description: str, agent_topic_type: str, user_topic_type: str) -> None:
        super().__init__(description)
        self._agent_topic_type = agent_topic_type
        self._user_topic_type = user_topic_type
        self._delegate_tools = dict([
            (human_to_technical_tool.name, human_to_technical_tool),
            (human_to_billing_tool.name, human_to_billing_tool),
            (human_to_sales_tool.name, human_to_sales_tool),
            (human_to_triage_tool.name, human_to_triage_tool),
        ])

    @message_handler
    async def handle_user_task(self, message: UserTask, ctx: MessageContext) -> None:
        customer_id = ctx.topic_id.source
        available_agents = manager.get_available_human_agents()
        
        if not available_agents:
            message.context.append(AssistantMessage(
                content="I understand you'd like to speak with a human representative. Unfortunately, no human agents are currently available. I'm here to help you with your request - please let me know what you need assistance with and I'll do my best to resolve it.",
                source=self.id.type
            ))
            await self.publish_message(
                AgentResponse(context=message.context, reply_to_topic_type=self._agent_topic_type),
                topic_id=TopicId(self._user_topic_type, source=customer_id),
            )
            return
        
        manager.pending_human_tasks[customer_id] = message
        agent_id = available_agents[0]
        
        if agent_id not in manager.active_human_agents:
            available_agents = [aid for aid in available_agents if aid in manager.active_human_agents]
            if not available_agents:
                message.context.append(AssistantMessage(
                    content="I understand you'd like to speak with a human representative. Unfortunately, no human agents are currently available. I'm here to help you with your request - please let me know what you need assistance with and I'll do my best to resolve it.",
                    source=self.id.type
                ))
                await self.publish_message(
                    AgentResponse(context=message.context, reply_to_topic_type=self._agent_topic_type),
                    topic_id=TopicId(self._user_topic_type, source=customer_id),
                )
                return
            agent_id = available_agents[0]
        
        manager.assign_human_agent(customer_id, agent_id)
        agent_ws = manager.active_human_agents[agent_id]
        
        conversation_history = []
        for msg in message.context[-10:]:
            try:
                if isinstance(msg, UserMessage):
                    conversation_history.append({
                        'content': str(msg.content) if msg.content else "User message",
                        'source': 'user',
                        'timestamp': datetime.now().isoformat()
                    })
                elif isinstance(msg, AssistantMessage):
                    content = safe_serialize_content(msg.content)
                    try:
                        import json
                        json.dumps(content)
                    except (TypeError, ValueError):
                        content = f"Agent response (content type: {type(msg.content).__name__})"
                        
                    conversation_history.append({
                        'content': content,
                        'source': str(msg.source) if msg.source else 'assistant',
                        'timestamp': datetime.now().isoformat()
                    })
                elif hasattr(msg, '__class__') and 'FunctionExecutionResultMessage' in str(type(msg)):
                    if hasattr(msg, 'content') and msg.content:
                        results = []
                        for result in msg.content:
                            if hasattr(result, 'content'):
                                results.append(f"Function result: {result.content}")
                        content = "; ".join(results) if results else "Function execution completed"
                    else:
                        content = "Function execution completed"
                    
                    conversation_history.append({
                        'content': content,
                        'source': 'system',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    continue
            except Exception:
                conversation_history.append({
                    'content': "Message processing error",
                    'source': 'system',
                    'timestamp': datetime.now().isoformat()
                })
        
        latest_message = "Customer needs assistance"
        if message.context:
            for msg in reversed(message.context):
                if isinstance(msg, UserMessage):
                    latest_message = str(msg.content) if msg.content else "Customer needs assistance"
                    break
        
        try:
            assignment_data = {
                "type": "new_assignment",
                "customer_id": customer_id,
                "initial_message": latest_message,
                "conversation_history": conversation_history,
                "timestamp": datetime.now().isoformat(),
                "task_type": "human_escalation"
            }
            
            try:
                import json
                json.dumps(assignment_data)
            except (TypeError, ValueError):
                assignment_data = {
                    "type": "new_assignment",
                    "customer_id": customer_id,
                    "initial_message": "Customer needs assistance (conversation history unavailable)",
                    "conversation_history": [],
                    "timestamp": datetime.now().isoformat(),
                    "task_type": "human_escalation"
                }
            
            await agent_ws.send_json(assignment_data)
            
            if customer_id in manager.active_customer_connections:
                customer_ws = manager.active_customer_connections[customer_id]
                await customer_ws.send_json({
                    "type": "TextMessage",
                    "content": "I'm connecting you to a human support representative. They will assist you shortly...",
                    "source": "Human_Support",
                    "agent_type": "Human_Support", 
                    "timestamp": datetime.now().isoformat(),
                    "transfer_status": "connecting"
                })
            
        except Exception as e:
            logger.error(f"Failed to notify human agent {agent_id}: {str(e)}")
            manager.disconnect_human_agent(agent_id)
            if customer_id in manager.pending_human_tasks:
                del manager.pending_human_tasks[customer_id]
            
            message.context.append(AssistantMessage(
                content="I apologize, but I'm having trouble connecting you to a human agent right now. I'm here to help you with your request - please let me know what you need assistance with.",
                source=self.id.type
            ))
            await self.publish_message(
                AgentResponse(context=message.context, reply_to_topic_type=self._agent_topic_type),
                topic_id=TopicId(self._user_topic_type, source=customer_id),
            )

class WebSocketUserAgent(RoutedAgent):
    def __init__(self, description: str, user_topic_type: str, agent_topic_type: str) -> None:
        super().__init__(description)
        self._user_topic_type = user_topic_type
        self._agent_topic_type = agent_topic_type

    @message_handler
    async def handle_user_login(self, message: UserLogin, ctx: MessageContext) -> None:
        customer_id = message.customer_id
        
        if customer_id in manager.active_customer_connections:
            customer_ws = manager.active_customer_connections[customer_id]
            await customer_ws.send_json({
                "type": "TextMessage",
                "content": "Hello! I'm your AI support assistant. How can I help you today?",
                "source": "TriageAgent_AI",
                "agent_type": "TriageAgent", 
                "timestamp": datetime.now().isoformat()
            })

    @message_handler
    async def handle_task_result(self, message: AgentResponse, ctx: MessageContext) -> None:
        customer_id = ctx.topic_id.source
        
        if customer_id in manager.active_customer_connections:
            customer_ws = manager.active_customer_connections[customer_id]
            
            latest_response = None
            for msg in reversed(message.context):
                if isinstance(msg, AssistantMessage):
                    latest_response = msg
                    break
            
            if latest_response:
                agent_type = latest_response.source.replace("Agent", "")
                if agent_type == "HumanAgent":
                    agent_type = "Human_Support"
                else:
                    agent_type = f"{agent_type}_AI"
                
                content = safe_serialize_content(latest_response.content)
                
                if isinstance(content, list):
                    function_names = []
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'function_call':
                            function_names.append(f"Processing: {item['name']}")
                        else:
                            function_names.append(str(item))
                    content = "; ".join(function_names) if function_names else "Processing your request..."
                
                await customer_ws.send_json({
                    "type": "TextMessage",
                    "content": content,
                    "source": agent_type,
                    "agent_type": latest_response.source,
                    "timestamp": datetime.now().isoformat()
                })
                
                manager.customer_conversations[customer_id].append({
                    "content": content,
                    "source": agent_type,
                    "agent_type": latest_response.source,
                    "timestamp": datetime.now().isoformat()
                })

async def handle_human_to_ai_transfer(runtime, customer_id: str, transfer_command: str, transfer_message: str = ""):
    transfer_mapping = {
        "transfer_to_technical": technical_agent_topic_type,
        "transfer_to_billing": billing_agent_topic_type, 
        "transfer_to_sales": sales_agent_topic_type,
        "transfer_to_triage": triage_agent_topic_type,
    }
    
    target_agent = transfer_mapping.get(transfer_command)
    if not target_agent:
        return False
        
    try:
        conversation_history = manager.customer_conversations.get(customer_id, [])
        context = []
        
        for msg in conversation_history[-10:]:
            if msg.get('source') == 'user':
                context.append(UserMessage(content=msg['content'], source="User"))
            elif msg.get('source') in ['Human_Support', 'human']:
                context.append(AssistantMessage(content=msg['content'], source="HumanAgent"))
            elif msg.get('source', '').endswith('_AI'):
                context.append(AssistantMessage(content=msg['content'], source=msg.get('agent_type', 'Assistant')))
        
        if transfer_message:
            context.append(AssistantMessage(
                content=f"Human agent note: {transfer_message}", 
                source="HumanAgent"
            ))
            
        context.append(AssistantMessage(
            content=f"This conversation has been transferred from a human agent. Please continue assisting the customer.",
            source="HumanAgent"
        ))
        
        await runtime.publish_message(
            UserTask(context=context),
            topic_id=TopicId(target_agent, source=customer_id)
        )
        
        if customer_id in manager.customer_to_agent:
            del manager.customer_to_agent[customer_id]
        if customer_id in manager.pending_human_tasks:
            del manager.pending_human_tasks[customer_id]
            
        if customer_id in manager.active_customer_connections:
            customer_ws = manager.active_customer_connections[customer_id]
            await customer_ws.send_json({
                "type": "TextMessage",
                "content": f"I'm transferring you to our {target_agent.replace('Agent', '')} team. They will continue assisting you.",
                "source": "Human_Support",
                "agent_type": "HumanAgent",
                "timestamp": datetime.now().isoformat(),
                "transfer_status": "transferred_to_ai"
            })
            
        return True
        
    except Exception as e:
        logger.error(f"Error in human transfer for customer {customer_id}: {str(e)}")
        return False

agent_runtime = None

async def initialize_agent_runtime():
    global agent_runtime
    
    if agent_runtime is None:
        agent_runtime = SingleThreadedAgentRuntime()
        model_client = OllamaChatCompletionClient(model="llama3.1:latest")
        
        triage_agent_type = await AIAgent.register(
            agent_runtime,
            type=triage_agent_topic_type,
            factory=lambda: AIAgent(
                description="A triage agent that routes customer requests to appropriate specialists.",
                system_message=SystemMessage(
                    content="You are a customer service triage agent. "
                    "You handle initial customer requests and conversations transferred back from human agents. "
                    "For new customers: Greet them briefly and professionally. "
                    "For all requests: Listen carefully and route to the appropriate department: "
                    "- Technical issues → technical support "
                    "- Billing/payment issues → billing support "
                    "- Sales inquiries → sales team "
                    "- Complex issues → human agent "
                    "When receiving transfers from human agents, acknowledge the handoff and continue assisting. "
                    "Ask clarifying questions only if needed to properly route the request."
                ),
                model_client=model_client,
                tools=[lookup_account_tool],
                delegate_tools=[
                    transfer_to_technical_tool,
                    transfer_to_billing_tool, 
                    transfer_to_sales_tool,
                    escalate_to_human_tool,
                ],
                agent_topic_type=triage_agent_topic_type,
                user_topic_type=user_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=triage_agent_topic_type, agent_type=triage_agent_type.type)
        )
        
        technical_agent_type = await AIAgent.register(
            agent_runtime,
            type=technical_agent_topic_type,
            factory=lambda: AIAgent(
                description="A technical support agent for hardware and software issues.",
                system_message=SystemMessage(
                    content="You are a technical support specialist. "
                    "Help customers with hardware, software, network, and system issues. "
                    "Provide clear step-by-step solutions. "
                    "Create support tickets for complex issues. "
                    "If the issue is outside technical scope or customer requests human help, transfer appropriately."
                ),
                model_client=model_client,
                tools=[create_ticket_tool, check_status_tool],
                delegate_tools=[transfer_back_to_triage_tool, escalate_to_human_tool],
                agent_topic_type=technical_agent_topic_type,
                user_topic_type=user_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=technical_agent_topic_type, agent_type=technical_agent_type.type)
        )
        
        billing_agent_type = await AIAgent.register(
            agent_runtime,
            type=billing_agent_topic_type,
            factory=lambda: AIAgent(
                description="A billing support agent for payment and subscription issues.",
                system_message=SystemMessage(
                    content="You are a billing support specialist. "
                    "Help customers with payments, subscriptions, refunds, and billing questions. "
                    "For account-specific information, recommend human verification for security. "
                    "Provide general billing guidance and policies. "
                    "Create tickets for complex billing issues."
                ),
                model_client=model_client,
                tools=[lookup_account_tool, create_ticket_tool],
                delegate_tools=[transfer_back_to_triage_tool, escalate_to_human_tool],
                agent_topic_type=billing_agent_topic_type,
                user_topic_type=user_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=billing_agent_topic_type, agent_type=billing_agent_type.type)
        )
        
        sales_agent_type = await AIAgent.register(
            agent_runtime,
            type=sales_agent_topic_type,
            factory=lambda: AIAgent(
                description="A sales agent for product information and purchasing.",
                system_message=SystemMessage(
                    content="You are a sales specialist. "
                    "Help customers with product information, features, pricing, and purchasing decisions. "
                    "Be helpful and informative without being pushy. "
                    "For complex sales inquiries, you can escalate to human sales representatives."
                ),
                model_client=model_client,
                tools=[lookup_account_tool],
                delegate_tools=[transfer_back_to_triage_tool, escalate_to_human_tool],
                agent_topic_type=sales_agent_topic_type,
                user_topic_type=user_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=sales_agent_topic_type, agent_type=sales_agent_type.type)  
        )
        
        human_agent_type = await WebSocketHumanAgent.register(
            agent_runtime,
            type=human_agent_topic_type,
            factory=lambda: WebSocketHumanAgent(
                description="A human agent proxy for WebSocket communication.",
                agent_topic_type=human_agent_topic_type,
                user_topic_type=user_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=human_agent_topic_type, agent_type=human_agent_type.type)
        )
        
        user_agent_type = await WebSocketUserAgent.register(
            agent_runtime,
            type=user_topic_type,
            factory=lambda: WebSocketUserAgent(
                description="A user agent proxy for WebSocket communication.",
                user_topic_type=user_topic_type,
                agent_topic_type=triage_agent_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=user_topic_type, agent_type=user_agent_type.type)
        )
        
        agent_runtime.start()

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/agent-dashboard")
async def agent_dashboard():
    return FileResponse("agent_dashboard.html")

@app.post("/api/agent/login")
async def agent_login(request: dict):
    username = request.get("username")
    agent_type = request.get("agent_type", "support")
    
    if username:
        clean_username = "".join(c for c in username if c.isalnum() or c in "_-")
        timestamp = str(int(datetime.now().timestamp()))
        agent_id = f"agent_{clean_username}_{timestamp}"
        return {"success": True, "agent_id": agent_id, "username": username}
    else:
        return {"success": False, "message": "Username required"}

@app.get("/api/system/status") 
async def system_status():
    try:
        if agent_runtime is None:
            await initialize_agent_runtime()
        
        available_human_agents = manager.get_available_human_agents()
        active_assignments = manager.customer_to_agent
        
        return {
            "ai_agents": {
                "triage_agent": {
                    "name": "Triage Agent",
                    "status": "active",
                    "expertise": ["Request routing", "Initial assessment", "Customer triage"]
                },
                "technical_agent": {
                    "name": "Technical Support",
                    "status": "active", 
                    "expertise": ["Hardware troubleshooting", "Software issues", "System configuration"]
                },
                "billing_agent": {
                    "name": "Billing Support",
                    "status": "active",
                    "expertise": ["Payment processing", "Subscription management", "Billing inquiries"]
                },
                "sales_agent": {
                    "name": "Sales Support",
                    "status": "active",
                    "expertise": ["Product information", "Sales inquiries", "Purchase assistance"]
                }
            },
            "human_agents": {
                "total_connected": len(manager.active_human_agents),
                "available": len(available_human_agents),
                "busy": len(manager.active_human_agents) - len(available_human_agents),
                "active_sessions": len(active_assignments),
                "available_agent_ids": available_human_agents,
                "active_assignments": active_assignments,
                "all_connected_agents": list(manager.active_human_agents.keys())
            },
            "customers": {
                "total_connected": len(manager.active_customer_connections),
                "active_conversations": len(manager.customer_conversations),
                "assigned_to_humans": len(active_assignments),
                "pending_human_tasks": len(manager.pending_human_tasks)
            },
            "system_initialized": agent_runtime is not None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        return {"error": "Unable to retrieve system status"}

@app.get("/api/agents/types")
async def get_agent_types():
    return {
        "TriageAgent": {
            "display_name": "Triage Agent",
            "icon": "🎯",
            "color": "#6366F1",
            "description": "Routes customer requests to appropriate specialists"
        },
        "TechnicalAgent": {
            "display_name": "Technical Support",
            "icon": "🔧", 
            "color": "#3B82F6",
            "description": "Handles technical issues and troubleshooting"
        },
        "BillingAgent": {
            "display_name": "Billing Support",
            "icon": "💳",
            "color": "#10B981", 
            "description": "Manages billing and payment inquiries"
        },
        "SalesAgent": {
            "display_name": "Sales Support",
            "icon": "🛒",
            "color": "#8B5CF6",
            "description": "Provides product information and sales assistance"
        },
        "HumanAgent": {
            "display_name": "Human Support",
            "icon": "👤",
            "color": "#F59E0B",
            "description": "Live human agent assistance"
        }
    }

@app.get("/history")
async def history():
    try:
        if not os.path.exists(history_path):
            return []
        async with aiofiles.open(history_path, "r") as file:
            return json.loads(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/api/debug/agents")
async def debug_agents():
    return {
        "active_human_agents": list(manager.active_human_agents.keys()),
        "customer_to_agent_assignments": manager.customer_to_agent,
        "available_agents": manager.get_available_human_agents(),
        "pending_human_tasks": list(manager.pending_human_tasks.keys()),
        "active_customer_connections": list(manager.active_customer_connections.keys()),
        "runtime_initialized": agent_runtime is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/human/transfer-options")
async def get_transfer_options():
    return {
        "transfer_to_triage": {
            "display_name": "Triage Agent",
            "description": "General routing and new request handling",
            "icon": "🎯",
            "color": "#6366F1"
        },
        "transfer_to_technical": {
            "display_name": "Technical Support",
            "description": "Hardware, software, and technical troubleshooting",
            "icon": "🔧",
            "color": "#3B82F6"
        },
        "transfer_to_billing": {
            "display_name": "Billing Support", 
            "description": "Payment, subscription, and billing inquiries",
            "icon": "💳",
            "color": "#10B981"
        },
        "transfer_to_sales": {
            "display_name": "Sales Support",
            "description": "Product information and sales assistance",
            "icon": "🛒",
            "color": "#8B5CF6"
        }
    }

@app.websocket("/ws/chat")
async def chat(websocket: WebSocket):
    customer_id = f"customer_{datetime.now().timestamp()}"
    
    # Check if customer already exists to prevent duplicate connections
    if customer_id in manager.active_customer_connections:
        logger.warning(f"Customer {customer_id} already connected, closing duplicate")
        await websocket.close()
        return
        
    await manager.connect_customer(customer_id, websocket)
    
    # Initialize runtime only once
    if agent_runtime is None:
        await initialize_agent_runtime()
    
    # Send initial login message only once
    try:
        await agent_runtime.publish_message(
            UserLogin(customer_id=customer_id),
            topic_id=TopicId(user_topic_type, source=customer_id)
        )
    except Exception as e:
        logger.error(f"Error sending initial login: {str(e)}")
    
    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("content", "")
            
            if not user_message.strip():
                continue  # Skip empty messages
            
            try:
                conversation_history = manager.customer_conversations.get(customer_id, [])
                conversation_history.append({
                    "content": user_message,
                    "source": "user", 
                    "timestamp": datetime.now().isoformat()
                })
                manager.customer_conversations[customer_id] = conversation_history
                
                # Check if already assigned to human agent
                if customer_id in manager.customer_to_agent:
                    agent_id = manager.customer_to_agent[customer_id]
                    if agent_id in manager.active_human_agents:
                        agent_ws = manager.active_human_agents[agent_id] 
                        await agent_ws.send_json({
                            "type": "customer_message",
                            "customer_id": customer_id,
                            "message": user_message,
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                
                # Create context for AI processing
                context = []
                for msg in conversation_history[-10:]:
                    if msg.get('source') == 'user':
                        context.append(UserMessage(content=msg['content'], source="User"))
                    elif msg.get('source', '').endswith('_AI'):
                        context.append(AssistantMessage(content=msg['content'], source=msg.get('agent_type', 'Assistant')))
                
                context.append(UserMessage(content=user_message, source="User"))
                
                # Send to AI agent system
                await agent_runtime.publish_message(
                    UserTask(context=context),
                    topic_id=TopicId(triage_agent_topic_type, source=customer_id)
                )
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    "type": "TextMessage",
                    "content": "Sorry, I encountered an error. Please try again.",
                    "source": "System",
                    "timestamp": datetime.now().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"Customer {customer_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for customer {customer_id}: {str(e)}")
    finally:
        manager.disconnect_customer(customer_id)

@app.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    # Check if agent already connected to prevent duplicates
    if agent_id in manager.active_human_agents:
        logger.warning(f"Agent {agent_id} already connected, closing duplicate")
        await websocket.close()
        return
        
    try:
        await manager.connect_human_agent(agent_id, websocket)
        
        # Send connection confirmation only once
        await websocket.send_json({
            "type": "connection_confirmed",
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
            "message": "Connected successfully to agent dashboard"
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "agent_message":
                customer_id = data.get("customer_id")
                message = data.get("message", "")
                
                if not message.strip():
                    continue  # Skip empty messages
                
                try:
                    context = []
                    conversation_history = manager.customer_conversations.get(customer_id, [])
                    for msg in conversation_history[-5:]:
                        if msg.get('source') == 'user':
                            context.append(UserMessage(content=msg['content'], source="User"))
                        elif msg.get('source') != 'Human_Support':
                            context.append(AssistantMessage(content=msg['content'], source=msg.get('agent_type', 'Assistant')))
                    
                    context.append(AssistantMessage(content=message, source="HumanAgent"))
                    
                    # Send via agent runtime
                    await agent_runtime.publish_message(
                        AgentResponse(context=context, reply_to_topic_type=human_agent_topic_type),
                        topic_id=TopicId(user_topic_type, source=customer_id)
                    )
                    
                    # Update conversation history
                    conversation_history = manager.customer_conversations.get(customer_id, [])
                    conversation_history.append({
                        "content": message,
                        "source": "Human_Support",
                        "agent_type": "HumanAgent", 
                        "timestamp": datetime.now().isoformat()
                    })
                    manager.customer_conversations[customer_id] = conversation_history
                    
                except Exception as agent_error:
                    logger.error(f"Error sending human response via agent system: {str(agent_error)}")
                    
            elif data.get("type") == "transfer_to_ai":
                customer_id = data.get("customer_id")
                transfer_command = data.get("transfer_command")
                transfer_message = data.get("transfer_message", "")
                
                try:
                    success = await handle_human_to_ai_transfer(
                        agent_runtime, customer_id, transfer_command, transfer_message
                    )
                except Exception as transfer_error:
                    logger.error(f"Error in human transfer: {str(transfer_error)}")
                    success = False
                    
                await websocket.send_json({
                    "type": "transfer_confirmation",
                    "customer_id": customer_id,
                    "success": success,
                    "target_agent": transfer_command,
                    "timestamp": datetime.now().isoformat()
                })
                    
    except WebSocketDisconnect:
        logger.info(f"Human agent {agent_id} disconnected")
    except Exception as e:
        logger.error(f"Error in agent WebSocket for {agent_id}: {str(e)}")
        try:
            await websocket.close()
        except:
            pass
    finally:
        manager.disconnect_human_agent(agent_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 