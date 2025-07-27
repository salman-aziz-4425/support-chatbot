import logging
from datetime import datetime
from autogen_core import TopicId
from autogen_core.models import AssistantMessage, UserMessage
from src.models.message_models import UserTask
from src.agents.tools import (
    technical_agent_topic_type,
    billing_agent_topic_type,
    sales_agent_topic_type,
    triage_agent_topic_type,
)

logger = logging.getLogger(__name__)

async def handle_human_to_ai_transfer(runtime, customer_id: str, transfer_command: str, transfer_message: str = ""):
    """Handle transfer from human agent back to AI agents"""
    from src.services.connection_manager import manager
    
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