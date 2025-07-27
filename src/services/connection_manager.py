from typing import Dict
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_customer_connections: Dict[str, WebSocket] = {}
        self.active_human_agents: Dict[str, WebSocket] = {}
        self.customer_conversations: Dict[str, list] = {}
        self.customer_to_agent: Dict[str, str] = {}
        self.pending_human_tasks: Dict[str, object] = {}
        
    async def connect_customer(self, customer_id: str, websocket: WebSocket):
        if customer_id in self.active_customer_connections:
            logger.warning(f"Customer {customer_id} already connected, closing duplicate")
            await websocket.close()
            return False
            
        await websocket.accept()
        self.active_customer_connections[customer_id] = websocket
        if customer_id not in self.customer_conversations:
            self.customer_conversations[customer_id] = []
        logger.info(f"Customer {customer_id} connected successfully")
        return True
        
    async def connect_human_agent(self, agent_id: str, websocket: WebSocket):
        if agent_id in self.active_human_agents:
            logger.warning(f"Human agent {agent_id} already connected, closing duplicate")
            await websocket.close()
            return False
            
        await websocket.accept()
        self.active_human_agents[agent_id] = websocket
        logger.info(f"Human agent {agent_id} connected successfully")
        return True
        
    def disconnect_customer(self, customer_id: str):
        if customer_id in self.active_customer_connections:
            del self.active_customer_connections[customer_id]
            logger.info(f"Customer {customer_id} disconnected")
        if customer_id in self.customer_to_agent:
            del self.customer_to_agent[customer_id]
        if customer_id in self.pending_human_tasks:
            del self.pending_human_tasks[customer_id]
            
    def disconnect_human_agent(self, agent_id: str):
        if agent_id in self.active_human_agents:
            del self.active_human_agents[agent_id]
            logger.info(f"Human agent {agent_id} disconnected")
        customers_to_remove = [cid for cid, aid in self.customer_to_agent.items() if aid == agent_id]
        for cid in customers_to_remove:
            del self.customer_to_agent[cid]
            
    def get_available_human_agents(self) -> list:
        all_agents = set(self.active_human_agents.keys())
        busy_agents = set(self.customer_to_agent.values())
        available = list(all_agents - busy_agents)
        logger.debug(f"Available human agents: {available}")
        return available
    
    def assign_human_agent(self, customer_id: str, agent_id: str):
        self.customer_to_agent[customer_id] = agent_id
        logger.info(f"Assigned customer {customer_id} to human agent {agent_id}")

manager = ConnectionManager() 