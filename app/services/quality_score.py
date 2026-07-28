"""
Deterministic weighted scoring engine. Deliberately NOT an LLM call — the
final production-readiness number must be reproducible and auditable.
AI agents explain and contextualize; this function decides the score.
"""
from dataclasses import dataclass

WEIGHTS = {
    "testing": 0.30,
    "security": 0.30,
    "performance": 0.15,
    "code_quality": 0.15,
    "build_stability": 0.10,
}


@dataclass
class ScoreBreakdown:
    testing_score: float
    security_score: float
    performance_score: float
    code_quality_score: float
    build_stability_score: float

    @property
    def final_score(self) -> float:
        return round(
            self.testing_score * WEIGHTS["testing"]
            + self.security_score * WEIGHTS["security"]
            + self.performance_score * WEIGHTS["performance"]
            + self.code_quality_score * WEIGHTS["code_quality"]
            + self.build_stability_score * WEIGHTS["build_stability"],
            2,
        )

    @property
    def category(self) -> str:
        s = self.final_score
        if s >= 90:
            return "production_ready"
        if s >= 75:
            return "minor_risks"
        if s >= 50:
            return "needs_attention"
        return "block_release"


def score_testing(coverage_percent: float, pass_rate: float) -> float:
    """50/50 blend of coverage and pass rate, both 0-100."""
    return round(0.5 * coverage_percent + 0.5 * pass_rate, 2)


def score_security(critical: int, high: int, medium: int, low: int) -> float:
    """Start at 100, subtract weighted penalties per finding, floor at 0."""
    penalty = critical * 25 + high * 10 + medium * 3 + low * 1
    return max(0.0, round(100 - penalty, 2))


def score_performance(p95_ms: float, error_rate_percent: float, target_p95_ms: float = 500.0) -> float:
    latency_score = max(0.0, 100 - max(0, (p95_ms - target_p95_ms) / target_p95_ms * 100))
    error_score = max(0.0, 100 - error_rate_percent * 10)
    return round(0.6 * latency_score + 0.4 * error_score, 2)


def score_code_quality(maintainability_index: float, code_smells: int, complexity_penalty_cap: float = 30.0) -> float:
    penalty = min(complexity_penalty_cap, code_smells * 0.5)
    return max(0.0, round(maintainability_index - penalty, 2))


def score_build_stability(recent_builds_success_rate: float) -> float:
    """recent_builds_success_rate: 0-100, e.g. successes/total over last N builds."""
    return round(recent_builds_success_rate, 2)


def compute_score_breakdown(
    *,
    coverage_percent: float,
    test_pass_rate: float,
    critical_findings: int,
    high_findings: int,
    medium_findings: int,
    low_findings: int,
    p95_response_ms: float,
    error_rate_percent: float,
    maintainability_index: float,
    code_smells: int,
    recent_build_success_rate: float,
) -> ScoreBreakdown:
    return ScoreBreakdown(
        testing_score=score_testing(coverage_percent, test_pass_rate),
        security_score=score_security(critical_findings, high_findings, medium_findings, low_findings),
        performance_score=score_performance(p95_response_ms, error_rate_percent),
        code_quality_score=score_code_quality(maintainability_index, code_smells),
        build_stability_score=score_build_stability(recent_build_success_rate),
    )
