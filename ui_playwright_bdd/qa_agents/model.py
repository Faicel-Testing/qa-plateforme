"""LangChain chat model: every request still crosses the security gateway."""
import json
from typing import Any, Callable
from pydantic import Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, convert_to_openai_messages
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from .bridge import Bridge, BridgeError


class GatewayChatModel(BaseChatModel):
    agent: str = "quality"
    transport: Callable[..., Any] | None = Field(default=None, exclude=True)
    model_config = {"arbitrary_types_allowed": True}

    @property
    def _llm_type(self):
        return "qa-guarded-gateway"

    def bind_tools(self, tools, **kwargs):
        converted = [convert_to_openai_tool(tool)["function"] for tool in tools]
        return self.bind(tools=[{"name": tool["name"], "description": tool.get("description", ""),
                                 "input_schema": tool["parameters"]} for tool in converted], **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if stop:
            raise ValueError("Stop sequences are not supported by the guarded transport")
        options = {key: value for key, value in kwargs.items()
                   if key in {"tools", "temperature", "rag", "_fnName"}}
        call = self.transport or Bridge(self.agent).call
        result = call("chat", messages=convert_to_openai_messages(messages), options=options)
        message = result.get("message", {})
        calls = []
        for tool in message.get("tool_calls") or []:
            args = tool["function"]["arguments"]
            args = json.loads(args) if isinstance(args, str) else args
            if not isinstance(args, dict) or not tool.get("id"):
                raise BridgeError("Malformed provider tool call")
            calls.append({"name": tool["function"]["name"], "args": args, "id": tool["id"]})
        content = message.get("content") or ""
        if not content.strip() and not calls:
            raise BridgeError("Empty provider response")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content, tool_calls=calls))])
