from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

import httpx
from openai import AzureOpenAI, OpenAI

from app.config import Settings
# from app.models import AgentStep
from app.llm.prompts import RESPONSE_FORMAT

ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]

class AzureOpenAIChatClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        verify: bool | str = settings.openai_ca_bundle or settings.openai_verify_ssl
        http_client = httpx.Client(verify=verify)
        if settings.use_azure_openai:
            self.client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                http_client=http_client,
            )
        else:
            self.client = OpenAI(
                api_key=settings.azure_openai_api_key,
                http_client=http_client,
            )

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
    ) -> list[dict[str, Any]] | str | None:
        working_messages = list(messages)
        # agent_steps: list[AgentStep] = []

        for _ in range(self.settings.agent_max_tool_rounds):
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.settings.azure_openai_deployment,
                temperature=self.settings.llm_temperature,
                messages=working_messages,
                tools=tools,
                tool_choice="auto",
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "arcgis_query_response",
                        "strict": False,
                        "schema": RESPONSE_FORMAT
                        }
                    }
            )
            message = response.choices[0].message

            assistant_message: dict[str, Any] = {"role": "assistant"}
            if message.content:
                assistant_message["content"] = message.content
            if message.tool_calls:
                assistant_message["tool_calls"] = [
                    tool_call.model_dump()
                    for tool_call in message.tool_calls
                ]
            working_messages.append(assistant_message)

            if not message.tool_calls:
                return message.content

            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = await tool_executor(tool_call.function.name, arguments)
                # agent_steps.append(
                #     AgentStep(
                #         tool_name=tool_call.function.name,
                #         arguments=arguments,
                #         result=result,
                #     )
                # )
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result if isinstance(result, str) else json.dumps(result),
                    }
                )

        raise RuntimeError("The agent exceeded the maximum number of tool rounds")

    def complete(self, messages: list[dict[str, Any]]) -> str:
        response = self.client.chat.completions.create(
            model=self.settings.azure_openai_deployment,
            temperature=self.settings.llm_temperature,
            messages=messages,
        )
        return response.choices[0].message.content or ""
