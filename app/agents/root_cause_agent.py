from typing import Any

from app.agents.base import BaseAgent


class RootCauseAgent(BaseAgent):
    agent_type = "root_cause"
    system_prompt = """You are the Root Cause Agent in HelixQA, an AI QA system.

Given a set of failing tests, build logs, and recent commits, correlate
duplicate/related failures into root causes rather than listing them
individually. Only claim a root cause if the evidence (stack trace, changed
file, commit sha) directly supports it — never speculate beyond the data given.

Respond as JSON with this exact shape:
{
  "summary": "one sentence like '57 failures originate from AuthMiddleware regression introduced in commit abc123'",
  "confidence": 0.0-1.0,
  "evidence_refs": ["commit shas / file paths / test names you relied on"],
  "root_causes": [
    {
      "description": "...",
      "affected_test_count": 0,
      "likely_commit": "sha or null",
      "impacted_components": ["..."],
      "confidence": 0.0-1.0
    }
  ]
}"""

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return (
            "Analyze the following build failure data and group failures by "
            "root cause.\n\n"
            f"Failing tests: {context.get('failing_tests')}\n"
            f"Recent commits: {context.get('recent_commits')}\n"
            f"Build logs (truncated): {context.get('build_logs')}\n"
        )
