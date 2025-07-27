import logging
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from autogen_core import TopicId
from src.models.message_models import UserLogin, UserTask, AgentResponse
from src.services.connection_manager import manager
from src.services.agent_runtime import initialize_agent_runtime
from src.services.transfer_service import handle_human_to_ai_transfer
from src.agents.tools import triage_agent_topic_type, user_topic_type
from autogen_core.models import UserMessage, AssistantMessage

logger = logging.getLogger(__name__)

def setup_websockets(app):
    """Setup all WebSocket endpoints"""
    
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
        from src.services.agent_runtime import agent_runtime as runtime
        if runtime is None:
            await initialize_agent_runtime()
            from src.services.agent_runtime import agent_runtime as runtime
        
        # Send initial login message only once
        try:
            await runtime.publish_message(
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
                    from src.services.agent_runtime import agent_runtime as runtime
                    await runtime.publish_message(
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
                        from src.services.agent_runtime import agent_runtime as runtime
                        await runtime.publish_message(
                            AgentResponse(context=context, reply_to_topic_type="HumanAgent"),
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
                        from src.services.agent_runtime import agent_runtime as runtime
                        success = await handle_human_to_ai_transfer(
                            runtime, customer_id, transfer_command, transfer_message
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