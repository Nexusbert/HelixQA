"""
Base class for all QA agents. Enforces:
  - structured JSON I/O contract
  - confidence scoring on every output
  - grounding check (agent must cite which input fields it used) as a
    lightweight hallucination guard before a report is persisted
"""
from __future__ import annotations

import abc
import json
from typing import Any

from app.services.ai.provider import AIProvider, get_ai_provider


class AgentOutput:
    def __init__(self, summary: str, confidence: float, payload: dict[str, Any]):
        self.summary = summary
        self.confidence = confidence
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return {"summary": self.summary, "confidence": self.confidence, "payload": self.payload}


class BaseAgent(abc.ABC):
    agent_type: str
    system_prompt: str

    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_ai_provider()

    @abc.abstractmethod
    def build_user_prompt(self, context: dict[str, Any]) -> str:
        raise NotImplementedError

    def _validate_grounding(self, payload: dict[str, Any], context: dict[str, Any]) -> bool:
        """
        Minimal hallucination guard: every referenced id (commit sha, file path,
        test name) in the model output must be traceable to something present
        in the context we sent it. Reject ungrounded claims rather than
        silently accepting them.
        """
        referenced = payload.get("evidence_refs", [])
        if not referenced:
            return False
        context_blob = json.dumps(context)
        return all(str(ref) in context_blob for ref in referenced)

    async def run(self, context: dict[str, Any]) -> AgentOutput:
        user_prompt = self.build_user_prompt(context)
        response = await self.provider.complete(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
        )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            # Never fabricate a result on malformed output
            return AgentOutput(
                summary="Agent returned malformed output; discarded to avoid hallucination.",
                confidence=0.0,
                payload={"error": "malformed_json", "raw": response.text[:500]},
            )

        confidence = float(payload.get("confidence", 0.0))
        grounded = self._validate_grounding(payload, context)
        if not grounded:
            confidence = min(confidence, 0.4)  # downgrade ungrounded claims
            payload["grounding_warning"] = "Could not verify all evidence references against source data."

        return AgentOutput(
            summary=payload.get("summary", ""),
            confidence=confidence,
            payload=payload,
        )
