from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_customer_connections: Dict[str, WebSocket] = {}
        self.active_human_agents: Dict[str, WebSocket] = {}
        self.customer_conversations: Dict[str, list] = {}
        self.customer_to_agent: Dict[str, str] = {}
        self.pending_human_tasks: Dict[str, object] = {}
        
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