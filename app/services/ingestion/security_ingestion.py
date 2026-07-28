"""
Security scan ingestion service. Parses outputs from Semgrep and Trivy
into a normalized SecurityScan model. Deduplicates findings via fingerprinting.
"""
from typing import Any

from app.models.analysis import Severity

class SecurityScanParser:
    """Base class for security scan parsers."""

    tool: str

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """Parse raw report into normalized structure."""
        raise NotImplementedError

    def _severity_to_enum(self, severity: str) -> Severity:
        sev_lower = severity.lower()
        if sev_lower in ("critical", "crit"):
            return Severity.CRITICAL
        if sev_lower in ("high", "major", "error"):
            return Severity.HIGH
        if sev_lower in ("medium", "moderate", "warning"):
            return Severity.MEDIUM
        return Severity.LOW

    def _fingerprint_finding(self, rule_id: str, file_path: str, line: int) -> str:
        """Generate deterministic fingerprint for deduplication."""
        import hashlib
        key = f"{rule_id}:{file_path}:{line}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

class SemgrepReportParser(SecurityScanParser):
    """Parse Semgrep security report (JSON)."""

    tool = "semgrep"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Semgrep JSON format:
        {
          "results": [
            {
              "check_id": "python.lang.best-practice.use-fstring",
              "path": "src/app.py",
              "start": {"line": 42},
              "end": {"line": 42},
              "message": "...",
              "severity": "INFO|WARNING|ERROR"
            }
          ]
        }
        """
        findings_by_severity = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
        }

        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        for result in raw_report.get("results", []):
            check_id = result.get("check_id", "unknown")
            severity_str = result.get("severity", "INFO")
            file_path = result.get("path", "unknown")
            line = result.get("start", {}).get("line", 0)
            message = result.get("message", "")

            severity_enum = self._severity_to_enum(severity_str)
            fp = self._fingerprint_finding(check_id, file_path, line)

            finding = {
                "id": fp,
                "rule_id": check_id,
                "severity": severity_enum.value,
                "file": file_path,
                "line": line,
                "message": message,
                "cwe": None,              }

            if severity_enum == Severity.CRITICAL:
                critical_count += 1
                findings_by_severity["CRITICAL"].append(finding)
            elif severity_enum == Severity.HIGH:
                high_count += 1
                findings_by_severity["HIGH"].append(finding)
            elif severity_enum == Severity.MEDIUM:
                medium_count += 1
                findings_by_severity["MEDIUM"].append(finding)
            else:
                low_count += 1
                findings_by_severity["LOW"].append(finding)

        total_severity = critical_count * 5 + high_count * 3 + medium_count * 1
        risk_score = min(100, (total_severity / 50) * 100) if total_severity else 0

        return {
            "tool": self.tool,
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "risk_score": risk_score,
            "findings": findings_by_severity,
            "raw_report": raw_report,
        }

class TrivyReportParser(SecurityScanParser):
    """Parse Trivy vulnerability report (JSON)."""

    tool = "trivy"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        Trivy JSON format:
        {
          "Results": [
            {
              "Target": "package.json",
              "Type": "npm",
              "Vulnerabilities": [
                {
                  "VulnerabilityID": "CVE-2023-1234",
                  "Severity": "CRITICAL|HIGH|MEDIUM|LOW",
                  "Title": "...",
                  "Description": "...",
                  "PkgName": "lodash",
                  "InstalledVersion": "1.0.0",
                  "FixedVersion": "1.0.1"
                }
              ],
              "Misconfigurations": [...]
            }
          ]
        }
        """
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        findings_by_severity = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
        }

        for result in raw_report.get("Results", []):
            target = result.get("Target", "unknown")

            for vuln in result.get("Vulnerabilities", []):
                vuln_id = vuln.get("VulnerabilityID", "unknown")
                severity_str = vuln.get("Severity", "LOW")
                severity_enum = self._severity_to_enum(severity_str)
                pkg_name = vuln.get("PkgName", "unknown")
                fp = self._fingerprint_finding(vuln_id, target, 0)

                finding = {
                    "id": fp,
                    "vulnerability_id": vuln_id,
                    "severity": severity_enum.value,
                    "package": pkg_name,
                    "installed_version": vuln.get("InstalledVersion"),
                    "fixed_version": vuln.get("FixedVersion"),
                    "title": vuln.get("Title", ""),
                    "description": vuln.get("Description", ""),
                    "cwe": None,
                }

                if severity_enum == Severity.CRITICAL:
                    critical_count += 1
                    findings_by_severity["CRITICAL"].append(finding)
                elif severity_enum == Severity.HIGH:
                    high_count += 1
                    findings_by_severity["HIGH"].append(finding)
                elif severity_enum == Severity.MEDIUM:
                    medium_count += 1
                    findings_by_severity["MEDIUM"].append(finding)
                else:
                    low_count += 1
                    findings_by_severity["LOW"].append(finding)

            for misconfig in result.get("Misconfigurations", []):
                misconfig_id = misconfig.get("ID", "unknown")
                severity_str = misconfig.get("Severity", "MEDIUM")
                severity_enum = self._severity_to_enum(severity_str)
                fp = self._fingerprint_finding(misconfig_id, target, 0)

                finding = {
                    "id": fp,
                    "misconfiguration_id": misconfig_id,
                    "severity": severity_enum.value,
                    "title": misconfig.get("Title", ""),
                    "description": misconfig.get("Description", ""),
                    "cwe": misconfig.get("CweID"),
                }

                if severity_enum == Severity.CRITICAL:
                    critical_count += 1
                    findings_by_severity["CRITICAL"].append(finding)
                elif severity_enum == Severity.HIGH:
                    high_count += 1
                    findings_by_severity["HIGH"].append(finding)
                elif severity_enum == Severity.MEDIUM:
                    medium_count += 1
                    findings_by_severity["MEDIUM"].append(finding)
                else:
                    low_count += 1
                    findings_by_severity["LOW"].append(finding)

        total_severity = critical_count * 5 + high_count * 3 + medium_count * 1
        risk_score = min(100, (total_severity / 50) * 100) if total_severity else 0

        return {
            "tool": self.tool,
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "risk_score": risk_score,
            "findings": findings_by_severity,
            "raw_report": raw_report,
        }

class OWASPZapReportParser(SecurityScanParser):
    """Parse OWASP ZAP security report (JSON)."""

    tool = "owasp_zap"

    def parse(self, raw_report: dict[str, Any]) -> dict[str, Any]:
        """
        OWASP ZAP JSON format:
        {
          "site": [
            {
              "name": "http://target.com",
              "alerts": [
                {
                  "pluginid": "10038",
                  "alert": "X-Frame-Options Header Missing",
                  "riskcode": "2",                    "confidence": "2",
                  "instances": [{"url": "...", "method": "GET"}],
                  "desc": "..."
                }
              ]
            }
          ]
        }
        """
        risk_code_map = {"0": "LOW", "1": "LOW", "2": "MEDIUM", "3": "HIGH"}

        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        findings_by_severity = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
        }

        for site in raw_report.get("site", []):
            target = site.get("name", "unknown")

            for alert in site.get("alerts", []):
                alert_id = alert.get("pluginid", "unknown")
                severity_str = risk_code_map.get(str(alert.get("riskcode", "1")), "LOW")
                severity_enum = self._severity_to_enum(severity_str)
                fp = self._fingerprint_finding(alert_id, target, 0)

                finding = {
                    "id": fp,
                    "alert_id": alert_id,
                    "alert": alert.get("alert", ""),
                    "severity": severity_enum.value,
                    "confidence": alert.get("confidence", ""),
                    "description": alert.get("desc", ""),
                    "instances_count": len(alert.get("instances", [])),
                }

                if severity_enum == Severity.CRITICAL:
                    critical_count += 1
                    findings_by_severity["CRITICAL"].append(finding)
                elif severity_enum == Severity.HIGH:
                    high_count += 1
                    findings_by_severity["HIGH"].append(finding)
                elif severity_enum == Severity.MEDIUM:
                    medium_count += 1
                    findings_by_severity["MEDIUM"].append(finding)
                else:
                    low_count += 1
                    findings_by_severity["LOW"].append(finding)

        total_severity = critical_count * 5 + high_count * 3 + medium_count * 1
        risk_score = min(100, (total_severity / 50) * 100) if total_severity else 0

        return {
            "tool": self.tool,
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "risk_score": risk_score,
            "findings": findings_by_severity,
            "raw_report": raw_report,
        }

def get_security_parser(tool: str) -> SecurityScanParser:
    """Factory to get parser for security tool."""
    parsers = {
        "semgrep": SemgrepReportParser(),
        "trivy": TrivyReportParser(),
        "owasp_zap": OWASPZapReportParser(),
    }
    if tool not in parsers:
        raise ValueError(f"Unknown security tool: {tool}")
    return parsers[tool]
