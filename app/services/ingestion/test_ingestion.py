"""
Test report ingestion service. Parses outputs from Jest, Pytest, JUnit, Playwright
into a normalized TestRun model. Deduplicates failures via fingerprinting.
"""
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.models.analysis import TestFramework


@dataclass
class TestFailure:
    """Normalized test failure for deduplication."""
    test_name: str
    error_message: str
    stack_trace: str
    file_path: str | None
    fingerprint: str  # sha256 of (test_name + error_message) for grouping


class TestReportParser:
    """Base class for test report parsers."""

    framework: TestFramework

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """Parse raw report into normalized structure."""
        raise NotImplementedError

    def _fingerprint_failure(self, test_name: str, error_msg: str) -> str:
        """Generate deterministic fingerprint for deduplication."""
        import hashlib
        key = f"{test_name}:{error_msg}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


class JestReportParser(TestReportParser):
    """Parse Jest test report (JSON)."""

    framework = TestFramework.JEST

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Jest JSON format:
        {
          "numFailedTests": 5,
          "numPassedTests": 85,
          "numPendingTests": 10,
          "testResults": [
            {
              "name": "path/to/test.js",
              "assertionResults": [
                {
                  "title": "should do X",
                  "status": "passed|failed",
                  "failureMessages": ["..."]
                }
              ]
            }
          ]
        }
        """
        total_tests = (
            raw_report.get("numPassedTests", 0)
            + raw_report.get("numFailedTests", 0)
            + raw_report.get("numPendingTests", 0)
        )

        failures = {}
        for test_file in raw_report.get("testResults", []):
            for result in test_file.get("assertionResults", []):
                if result.get("status") == "failed":
                    test_name = result.get("title", "unknown")
                    error_msg = "\n".join(result.get("failureMessages", []))
                    fp = self._fingerprint_failure(test_name, error_msg)
                    failures[fp] = {
                        "test_name": test_name,
                        "error_message": error_msg,
                        "file_path": test_file.get("name"),
                    }

        return {
            "framework": self.framework.value,
            "total_tests": total_tests,
            "passed": raw_report.get("numPassedTests", 0),
            "failed": raw_report.get("numFailedTests", 0),
            "skipped": raw_report.get("numPendingTests", 0),
            "coverage_percent": raw_report.get("coverage", {}).get("lines", {}).get("percentage"),
            "raw_report": raw_report,
            "failure_fingerprints": failures,
        }


class PytestReportParser(TestReportParser):
    """Parse Pytest test report (JSON)."""

    framework = TestFramework.PYTEST

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Pytest JSON format:
        {
          "summary": {"total": 100, "passed": 85, "failed": 5, "skipped": 10},
          "tests": [
            {
              "nodeid": "tests/test_auth.py::test_login",
              "outcome": "passed|failed|skipped",
              "call": {"longrepr": "..."},
              "location": [...path, line]
            }
          ]
        }
        """
        summary = raw_report.get("summary", {})

        failures = {}
        for test in raw_report.get("tests", []):
            if test.get("outcome") == "failed":
                test_name = test.get("nodeid", "unknown")
                error_msg = test.get("call", {}).get("longrepr", "")
                fp = self._fingerprint_failure(test_name, error_msg)
                failures[fp] = {
                    "test_name": test_name,
                    "error_message": error_msg,
                    "file_path": test.get("location", [None])[0],
                }

        return {
            "framework": self.framework.value,
            "total_tests": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "skipped": summary.get("skipped", 0),
            "coverage_percent": None,  # Parse from coverage report separately
            "raw_report": raw_report,
            "failure_fingerprints": failures,
        }


class JunitReportParser(TestReportParser):
    """Parse JUnit XML test report."""

    framework = TestFramework.JUNIT

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Expects pre-converted JUnit XML to dict via xmltodict:
        {
          "testsuites": {
            "testsuite": [
              {
                "name": "...",
                "tests": "100",
                "failures": "5",
                "skipped": "10",
                "testcase": [
                  {
                    "name": "test_foo",
                    "classname": "TestClass",
                    "failure": {"message": "...", ...}
                  }
                ]
              }
            ]
          }
        }
        """
        testsuites = raw_report.get("testsuites", {})
        suite_list = testsuites.get("testsuite", [])
        if not isinstance(suite_list, list):
            suite_list = [suite_list]

        total_tests = 0
        passed = 0
        failed = 0
        skipped = 0
        failures = {}

        for suite in suite_list:
            total_tests += int(suite.get("tests", 0))
            failed += int(suite.get("failures", 0))
            skipped += int(suite.get("skipped", 0))

            test_cases = suite.get("testcase", [])
            if not isinstance(test_cases, list):
                test_cases = [test_cases]

            for test_case in test_cases:
                if "failure" in test_case:
                    test_name = f"{test_case.get('classname')}.{test_case.get('name')}"
                    error_msg = test_case.get("failure", {}).get("message", "")
                    fp = self._fingerprint_failure(test_name, error_msg)
                    failures[fp] = {
                        "test_name": test_name,
                        "error_message": error_msg,
                        "file_path": None,
                    }
                elif "skipped" not in test_case:
                    passed += 1

        return {
            "framework": self.framework.value,
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "coverage_percent": None,
            "raw_report": raw_report,
            "failure_fingerprints": failures,
        }


class PlaywrightReportParser(TestReportParser):
    """Parse Playwright test report (JSON)."""

    framework = TestFramework.PLAYWRIGHT

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Playwright JSON format:
        {
          "config": {...},
          "stats": {
            "expected": 100,
            "unexpected": 5,
            "skipped": 10,
            "flaky": 0
          },
          "tests": [
            {
              "testId": "...",
              "title": "should do X",
              "file": "tests/e2e.spec.ts",
              "results": [
                {
                  "status": "passed|failed|skipped",
                  "error": {...}
                }
              ]
            }
          ]
        }
        """
        stats = raw_report.get("stats", {})
        total = stats.get("expected", 0) + stats.get("unexpected", 0) + stats.get("skipped", 0)

        failures = {}
        for test in raw_report.get("tests", []):
            for result in test.get("results", []):
                if result.get("status") == "failed":
                    test_name = test.get("title", "unknown")
                    error_msg = str(result.get("error", {}).get("message", ""))
                    fp = self._fingerprint_failure(test_name, error_msg)
                    failures[fp] = {
                        "test_name": test_name,
                        "error_message": error_msg,
                        "file_path": test.get("file"),
                    }

        return {
            "framework": self.framework.value,
            "total_tests": total,
            "passed": stats.get("expected", 0),
            "failed": stats.get("unexpected", 0),
            "skipped": stats.get("skipped", 0),
            "coverage_percent": None,
            "raw_report": raw_report,
            "failure_fingerprints": failures,
        }


def get_test_parser(framework: str) -> TestReportParser:
    """Factory to get parser for framework."""
    parsers = {
        "jest": JestReportParser(),
        "pytest": PytestReportParser(),
        "junit": JunitReportParser(),
        "playwright": PlaywrightReportParser(),
        "vitest": JestReportParser(),  # Vitest is Jest-compatible
        "mocha": JunitReportParser(),  # Mocha can output JUnit
    }
    if framework not in parsers:
        raise ValueError(f"Unknown test framework: {framework}")
    return parsers[framework]
