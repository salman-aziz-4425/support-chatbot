import logging
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import FileResponse
from src.services.connection_manager import manager
from src.services.agent_runtime import agent_runtime, initialize_agent_runtime

logger = logging.getLogger(__name__)

def setup_routes(app):
    """Setup all API routes"""
    
    @app.get("/")
    async def root():
        return FileResponse("static/index.html")

    @app.get("/agent-dashboard")
    async def agent_dashboard():
        return FileResponse("static/agent_dashboard.html")

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
                    "customer_service_triage": {
                        "name": "Customer Service Triage",
                        "status": "active",
                        "expertise": ["Request routing", "Initial assessment", "Customer triage"]
                    },
                    "technical_support": {
                        "name": "Technical Support",
                        "status": "active", 
                        "expertise": ["Hardware troubleshooting", "Software issues", "System configuration"]
                    },
                    "billing_support": {
                        "name": "Billing Support",
                        "status": "active",
                        "expertise": ["Payment processing", "Subscription management", "Billing inquiries"]
                    },
                    "sales_support": {
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
            "CustomerServiceTriageAgent": {
                "display_name": "Customer Service Triage",
                "icon": "🎯",
                "color": "#6366F1",
                "description": "Routes customer requests to appropriate specialists"
            },
            "TechnicalSupportAgent": {
                "display_name": "Technical Support",
                "icon": "🔧", 
                "color": "#3B82F6",
                "description": "Handles technical issues and troubleshooting"
            },
            "BillingSupportAgent": {
                "display_name": "Billing Support",
                "icon": "💳",
                "color": "#10B981", 
                "description": "Manages billing and payment inquiries"
            },
            "SalesSupportAgent": {
                "display_name": "Sales Support",
                "icon": "🛒",
                "color": "#8B5CF6",
                "description": "Provides product information and sales assistance"
            },
            "HumanSupportAgent": {
                "display_name": "Human Support",
                "icon": "👤",
                "color": "#F59E0B",
                "description": "Live human agent assistance"
            }
        }

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
                "display_name": "Customer Service Triage",
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