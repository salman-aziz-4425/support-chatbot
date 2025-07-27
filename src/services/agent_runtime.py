import logging
from autogen_core import (
    SingleThreadedAgentRuntime,
    TypeSubscription,
)
from autogen_core.models import SystemMessage
from autogen_ext.models.ollama import OllamaChatCompletionClient
from src.agents.ai_agent import AIAgent
from src.agents.websocket_agents import WebSocketHumanAgent, WebSocketUserAgent
from src.agents.tools import (
    triage_agent_topic_type,
    technical_agent_topic_type,
    billing_agent_topic_type,
    sales_agent_topic_type,
    human_agent_topic_type,
    user_topic_type,
    transfer_to_technical_tool,
    transfer_to_billing_tool,
    transfer_to_sales_tool,
    escalate_to_human_tool,
    transfer_back_to_triage_tool,
    lookup_account_tool,
    create_ticket_tool,
    check_status_tool,
)

logger = logging.getLogger(__name__)

agent_runtime = None



async def initialize_agent_runtime():
    """Initialize the handoff pattern agent runtime"""
    global agent_runtime
    
    if agent_runtime is None:
        agent_runtime = SingleThreadedAgentRuntime()
        model_client = OllamaChatCompletionClient(model="llama3.1:latest")
        
        triage_agent_type = await AIAgent.register(
            agent_runtime,
            type=triage_agent_topic_type,
            factory=lambda: AIAgent(
                description="A customer service triage agent that routes customer requests to appropriate specialists.",
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
                description="A technical support specialist for hardware and software issues.",
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
                description="A billing support specialist for payment and subscription issues.",
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
                description="A sales support specialist for product information and purchasing.",
                system_message=SystemMessage(
                    content="You are a sales support specialist. "
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
                description="A human support agent proxy for WebSocket communication.",
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
                description="A customer user agent proxy for WebSocket communication.",
                user_topic_type=user_topic_type,
                agent_topic_type=triage_agent_topic_type,
            ),
        )
        await agent_runtime.add_subscription(
            TypeSubscription(topic_type=user_topic_type, agent_type=user_agent_type.type)
        )
        
        agent_runtime.start() 