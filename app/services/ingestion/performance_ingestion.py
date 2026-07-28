"""
Performance metrics ingestion service. Parses outputs from K6 (load testing)
and Lighthouse (web performance) into a normalized PerformanceReport model.
"""
from typing import Any


class PerformanceReportParser:
    """Base class for performance report parsers."""

    tool: str

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """Parse raw report into normalized structure."""
        raise NotImplementedError


class K6ReportParser(PerformanceReportParser):
    """Parse K6 load test report (JSON)."""

    tool = "k6"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        K6 JSON summary format (typically from k6 --summary-export or --out json):
        {
          "root_group": {
            "name": "",
            "groups": [...],
            "checks": [...],
            "max_duration": 60000,
            "path": ""
          },
          "options": {...},
          "metrics": {
            "http_req_duration": {
              "type": "Trend",
              "contains": "time",
              "values": {
                "avg": 250.5,
                "max": 1200,
                "med": 200,
                "min": 50,
                "p(90)": 500,
                "p(95)": 800,
                "p(99)": 1100
              }
            },
            "http_reqs": {
              "type": "Counter",
              "values": {"count": 10000}
            },
            "http_req_failed": {
              "type": "Rate",
              "values": {"rate": 0.01}
            }
          }
        }
        """
        metrics = raw_report.get("metrics", {})

        # Extract timing metrics
        http_duration = metrics.get("http_req_duration", {}).get("values", {})
        http_reqs = metrics.get("http_reqs", {}).get("values", {})
        http_failed = metrics.get("http_req_failed", {}).get("values", {})
        http_req_blocked = metrics.get("http_req_blocked", {}).get("values", {})
        http_req_connecting = metrics.get("http_req_connecting", {}).get("values", {})
        http_req_tls_handshaking = metrics.get("http_req_tls_handshaking", {}).get("values", {})
        http_req_sending = metrics.get("http_req_sending", {}).get("values", {})
        http_req_waiting = metrics.get("http_req_waiting", {}).get("values", {})
        http_req_receiving = metrics.get("http_req_receiving", {}).get("values", {})

        # Calculate derived metrics
        total_requests = http_reqs.get("count", 0)
        failed_requests = int(http_failed.get("rate", 0) * total_requests) if total_requests else 0
        error_rate_percent = (http_failed.get("rate", 0) * 100) if http_failed else 0

        # Calculate throughput (requests per second)
        # K6 test duration is in milliseconds, convert to seconds
        test_duration_ms = raw_report.get("root_group", {}).get("max_duration", 60000)
        test_duration_s = test_duration_ms / 1000 if test_duration_ms else 60
        throughput_rps = total_requests / test_duration_s if test_duration_s else 0

        return {
            "tool": self.tool,
            "avg_response_time_ms": http_duration.get("avg"),
            "p95_response_time_ms": http_duration.get("p(95)"),
            "p99_response_time_ms": http_duration.get("p(99)"),
            "max_response_time_ms": http_duration.get("max"),
            "min_response_time_ms": http_duration.get("min"),
            "throughput_rps": throughput_rps,
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "error_rate_percent": error_rate_percent,
            "raw_metrics": {
                "duration_metrics": {
                    "avg": http_duration.get("avg"),
                    "p90": http_duration.get("p(90)"),
                    "p95": http_duration.get("p(95)"),
                    "p99": http_duration.get("p(99)"),
                    "max": http_duration.get("max"),
                },
                "blocking": http_req_blocked.get("avg"),
                "connecting": http_req_connecting.get("avg"),
                "tls_handshaking": http_req_tls_handshaking.get("avg"),
                "sending": http_req_sending.get("avg"),
                "waiting": http_req_waiting.get("avg"),
                "receiving": http_req_receiving.get("avg"),
                "test_duration_seconds": test_duration_s,
            },
        }


class LighthouseReportParser(PerformanceReportParser):
    """Parse Lighthouse performance report (JSON)."""

    tool = "lighthouse"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Lighthouse JSON format:
        {
          "lighthouseVersion": "...",
          "finalUrl": "https://example.com",
          "requestedUrl": "https://example.com",
          "audits": {
            "first-contentful-paint": {
              "score": 0.90,
              "numericValue": 1200,  # milliseconds
              "displayValue": "1.2 s"
            },
            "speed-index": {
              "numericValue": 2000
            },
            "largest-contentful-paint": {
              "numericValue": 3000
            },
            "cumulative-layout-shift": {
              "numericValue": 0.1
            },
            "total-blocking-time": {
              "numericValue": 200
            }
          },
          "categories": {
            "performance": {"score": 0.90}
          }
        }
        """
        audits = raw_report.get("audits", {})
        categories = raw_report.get("categories", {})

        # Core Web Vitals
        fcp_ms = audits.get("first-contentful-paint", {}).get("numericValue")
        lcp_ms = audits.get("largest-contentful-paint", {}).get("numericValue")
        si_ms = audits.get("speed-index", {}).get("numericValue")
        cls = audits.get("cumulative-layout-shift", {}).get("numericValue")
        tbt_ms = audits.get("total-blocking-time", {}).get("numericValue")

        # Scores (0-1, convert to 0-100 for consistency)
        performance_score = categories.get("performance", {}).get("score", 0) * 100
        accessibility_score = categories.get("accessibility", {}).get("score", 0) * 100
        best_practices_score = categories.get("best-practices", {}).get("score", 0) * 100
        seo_score = categories.get("seo", {}).get("score", 0) * 100

        return {
            "tool": self.tool,
            "avg_response_time_ms": fcp_ms,  # Use FCP as proxy for response time
            "p95_response_time_ms": lcp_ms,  # Use LCP as p95 proxy
            "throughput_rps": None,  # Not applicable to Lighthouse
            "error_rate_percent": None,  # Not applicable
            "raw_metrics": {
                "core_web_vitals": {
                    "first_contentful_paint_ms": fcp_ms,
                    "largest_contentful_paint_ms": lcp_ms,
                    "cumulative_layout_shift": cls,
                    "total_blocking_time_ms": tbt_ms,
                },
                "speed_index_ms": si_ms,
                "scores": {
                    "performance": performance_score,
                    "accessibility": accessibility_score,
                    "best_practices": best_practices_score,
                    "seo": seo_score,
                },
                "url": raw_report.get("finalUrl"),
                "fetch_time": raw_report.get("fetchTime"),
            },
        }


class JmeterReportParser(PerformanceReportParser):
    """Parse Apache JMeter performance report (JSON)."""

    tool = "jmeter"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        JMeter JSON format (aggregated summary):
        {
          "Total": {
            "totalCount": 10000,
            "failCount": 100,
            "successCount": 9900,
            "average": 250,
            "max": 1200,
            "min": 50,
            "percentiles": {
              "90.0": 500,
              "95.0": 800,
              "99.0": 1100
            }
          },
          "duration": 300000  # milliseconds
        }
        """
        total = raw_report.get("Total", {})
        duration_ms = raw_report.get("duration", 60000)
        duration_s = duration_ms / 1000 if duration_ms else 60

        total_count = total.get("totalCount", 0)
        fail_count = total.get("failCount", 0)
        error_rate_percent = (fail_count / total_count * 100) if total_count else 0
        throughput_rps = total_count / duration_s if duration_s else 0

        return {
            "tool": self.tool,
            "avg_response_time_ms": total.get("average"),
            "p95_response_time_ms": total.get("percentiles", {}).get("95.0"),
            "p99_response_time_ms": total.get("percentiles", {}).get("99.0"),
            "throughput_rps": throughput_rps,
            "total_requests": total_count,
            "failed_requests": fail_count,
            "error_rate_percent": error_rate_percent,
            "raw_metrics": {
                "max_response_time_ms": total.get("max"),
                "min_response_time_ms": total.get("min"),
                "percentiles": total.get("percentiles", {}),
                "test_duration_seconds": duration_s,
            },
        }


def get_performance_parser(tool: str) -> PerformanceReportParser:
    """Factory to get parser for performance tool."""
    parsers = {
        "k6": K6ReportParser(),
        "lighthouse": LighthouseReportParser(),
        "jmeter": JmeterReportParser(),
    }
    if tool not in parsers:
        raise ValueError(f"Unknown performance tool: {tool}")
    return parsers[tool]
