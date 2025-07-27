import json
import logging
from typing import List, Tuple
from autogen_core import (
    RoutedAgent,
    MessageContext,
    message_handler,
    TopicId,
    FunctionCall
)
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    SystemMessage,
)
from autogen_core.tools import Tool
from src.models.message_models import UserTask, AgentResponse

logger = logging.getLogger(__name__)

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