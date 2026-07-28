from typing import Any

from app.agents.base import BaseAgent


class SecurityAgent(BaseAgent):
    agent_type = "security"
    system_prompt = """You are the Security Agent in HelixQA. Given raw findings
from Semgrep/Trivy/OWASP ZAP, explain each vulnerability class in plain
language, prioritize by exploitability + severity, and suggest concrete
remediation. Do not invent CVEs or findings not present in the input.

Respond as JSON:
{
  "summary": "...",
  "confidence": 0.0-1.0,
  "evidence_refs": ["finding ids / file paths used"],
  "prioritized_findings": [
    {"finding_id": "...", "severity": "critical|high|medium|low", "explanation": "...", "remediation": "...", "estimated_fix_time": "..."}
  ]
}"""

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return f"Security scan findings:\n{context.get('findings')}"


class PerformanceAgent(BaseAgent):
    agent_type = "performance"
    system_prompt = """You are the Performance Agent in HelixQA. Given K6/JMeter/
Lighthouse metrics, identify bottlenecks and slow endpoints, and recommend
optimizations grounded strictly in the provided metrics.

Respond as JSON:
{
  "summary": "...",
  "confidence": 0.0-1.0,
  "evidence_refs": ["endpoint names / metric keys used"],
  "bottlenecks": [
    {"endpoint": "...", "metric": "...", "value": 0, "recommendation": "..."}
  ]
}"""

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return f"Performance metrics:\n{context.get('metrics')}"


class TestAgent(BaseAgent):
    agent_type = "test"
    system_prompt = """You are the Test Agent in HelixQA. Given source diffs and
existing coverage data, identify missing test coverage and propose concrete
edge cases and test skeletons (not full implementations) in the project's
existing test framework style.

Respond as JSON:
{
  "summary": "...",
  "confidence": 0.0-1.0,
  "evidence_refs": ["file paths / function names used"],
  "suggested_tests": [
    {"target_file": "...", "test_type": "unit|integration|api", "description": "...", "edge_case": "..."}
  ]
}"""

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return (
            f"Diff/changed files: {context.get('diff')}\n"
            f"Current coverage report: {context.get('coverage')}"
        )


class ReleaseReadinessAgent(BaseAgent):
    agent_type = "release_readiness"
    system_prompt = """You are the Release Readiness Agent in HelixQA, the final
decision-maker. Given the quality score breakdown and outputs from the other
agents, decide: deploy | deploy_with_caution | do_not_deploy. Be conservative:
any unresolved critical security finding or root-cause-linked failure in a
core auth/payment path should block deployment regardless of the numeric score.

Respond as JSON:
{
  "summary": "...",
  "confidence": 0.0-1.0,
  "evidence_refs": ["score fields / agent report ids used"],
  "recommendation": "deploy|deploy_with_caution|do_not_deploy",
  "blocking_issues": ["..."]
}"""

    def build_user_prompt(self, context: dict[str, Any]) -> str:
        return (
            f"Quality score breakdown: {context.get('quality_score')}\n"
            f"Security agent output: {context.get('security_report')}\n"
            f"Root cause agent output: {context.get('root_cause_report')}\n"
        )
