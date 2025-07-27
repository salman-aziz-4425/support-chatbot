import logging
from datetime import datetime
from autogen_core import (
    RoutedAgent,
    MessageContext,
    message_handler,
    TopicId,
)
from autogen_core.models import (
    AssistantMessage,
    UserMessage,
)
from src.models.message_models import UserTask, AgentResponse, UserLogin
from src.utils.serialization import safe_serialize_content
from src.agents.tools import (
    triage_agent_topic_type,
)

logger = logging.getLogger(__name__)

class WebSocketHumanAgent(RoutedAgent):
    def __init__(self, description: str, agent_topic_type: str, user_topic_type: str) -> None:
        super().__init__(description)
        self._agent_topic_type = agent_topic_type
        self._user_topic_type = user_topic_type

    @message_handler
    async def handle_user_task(self, message: UserTask, ctx: MessageContext) -> None:
        """Handle human agent assignment when triage agent escalates to human"""
        from src.services.connection_manager import manager
        
        customer_id = ctx.topic_id.source
        
        if customer_id in manager.customer_to_agent:
            logger.info(f"Customer {customer_id} already assigned to human agent {manager.customer_to_agent[customer_id]}")
            return
        
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
        from src.services.connection_manager import manager
        
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
        from src.services.connection_manager import manager
        
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