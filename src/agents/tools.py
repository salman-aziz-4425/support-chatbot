from datetime import datetime
from autogen_core.tools import FunctionTool


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

# Human-to-AI transfer functions
def human_transfer_to_technical() -> str:
    return technical_agent_topic_type

def human_transfer_to_billing() -> str:
    return billing_agent_topic_type

def human_transfer_to_sales() -> str:
    return sales_agent_topic_type

def human_transfer_to_triage() -> str:
    return triage_agent_topic_type

# Delegate tools
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

# Human-to-AI delegate tools
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

# Regular tools for AI agents
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