"""
Thin LLM client interface, deliberately swappable so the orchestrator and
gate logic can be tested (see tests/test_isolation.py) without a real API
call, and so the underlying model/provider is a one-file change if that ever
needs to happen.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        messages: List[LLMMessage],
        json_schema: Optional[dict] = None,
    ) -> str:
        """Returns the model's raw text response. If json_schema is given,
        the implementation is responsible for forcing/validating structured
        output against it (e.g. via tool-use) and returning the resulting
        JSON as a string."""
        ...


class AnthropicClient:
    """Real implementation, backed by the Anthropic API. Requires
    ANTHROPIC_API_KEY in the environment. Not yet exercised against a live
    key in this codebase -- treat as unverified until it's actually been run
    for real, the same way everything else here gets a build/test pass
    before being trusted.
    """

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: Optional[str] = None):
        import anthropic  # local import: keeps this dependency optional for
        # callers that only use FakeLLMClient in tests

        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._model = model

    def complete(
        self,
        system: str,
        messages: List[LLMMessage],
        json_schema: Optional[dict] = None,
    ) -> str:
        kwargs = {}
        tool_name = "respond"
        if json_schema is not None:
            kwargs["tools"] = [
                {
                    "name": tool_name,
                    "description": "Respond with the required structured output.",
                    "input_schema": json_schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": tool_name}

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        )

        if json_schema is not None:
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return json.dumps(block.input)
            raise RuntimeError("Model did not return the expected tool call")

        return "".join(block.text for block in response.content if block.type == "text")
