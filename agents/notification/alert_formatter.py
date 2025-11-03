"""
DevOps Sentinel - Alert Formatter
Format alerts for different delivery channels
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..shared.utils import (
    ConfigManager, Logger, TimestampUtils, AlertLevel
)

@dataclass
class AlertMessage:
    """Represents a formatted alert message"""
    title: str
    summary: str
    details: str
    severity: str
    timestamp: str
    service_name: str
    incident_id: str
    recommended_actions: List[str]
    supporting_evidence: List[str]

class AlertFormatter:
    """Format alerts for different delivery channels"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = Logger.setup_logger("AlertFormatter")

    def format_slack_alert(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for Slack delivery"""
        try:
            incident_id = incident_data.get('id', 'Unknown')
            service_name = incident_data.get('endpoint_name', 'Unknown Service')
            alert_level = incident_data.get('alert_level', 'medium')
            analysis_result = incident_data.get('analysis_result', {})
            health_check = incident_data.get('health_check_result', {})

            # Determine color based on alert level
            color = self._get_slack_color(alert_level)

            # Create Slack message
            slack_message = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 SERVICE ALERT: {service_name}",
                        "title_link": self._generate_incident_link(incident_id),
                        "text": self._generate_slack_summary(incident_data),
                        "fields": [
                            {
                                "title": "📍 Issue",
                                "value": self._extract_primary_hypothesis(analysis_result),
                                "short": False
                            },
                            {
                                "title": "⚡ Impact",
                                "value": self._assess_impact(incident_data),
                                "short": True
                            },
                            {
                                "title": "📊 Confidence",
                                "value": self._extract_confidence_level(analysis_result),
                                "short": True
                            },
                            {
                                "title": "🛠️ Recommended Actions",
                                "value": self._format_recommended_actions(analysis_result),
                                "short": False
                            }
                        ],
                        "footer": "DevOps Sentinel",
                        "ts": self._get_timestamp_seconds(incident_data.get('timestamp'))
                    }
                ]
            }

            # Add diagnostic details if available
            triage_data = incident_data.get('triage_data', {})
            if triage_data:
                diagnostic_fields = self._create_diagnostic_fields(triage_data)
                if diagnostic_fields:
                    slack_message["attachments"][0]["fields"].extend(diagnostic_fields)

            # Add quick actions
            quick_actions = self._create_quick_actions(incident_id, service_name)
            if quick_actions:
                slack_message["attachments"].append({
                    "color": color,
                    "title": "🔧 Quick Actions",
                    "actions": quick_actions
                })

            return slack_message

        except Exception as e:
            self.logger.error(f"Error formatting Slack alert: {e}")
            return self._create_fallback_slack_alert(incident_data, str(e))

    def format_email_alert(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for email delivery"""
        try:
            incident_id = incident_data.get('id', 'Unknown')
            service_name = incident_data.get('endpoint_name', 'Unknown Service')
            alert_level = incident_data.get('alert_level', 'medium')
            analysis_result = incident_data.get('analysis_result', {})
            health_check = incident_data.get('health_check_result', {})

            # Create email message
            email_message = {
                "subject": f"[{alert_level.upper()}] Service Alert: {service_name} (Incident {incident_id})",
                "html_body": self._generate_email_html(incident_data),
                "text_body": self._generate_email_text(incident_data),
                "recipients": self._get_email_recipients(alert_level),
                "priority": self._get_email_priority(alert_level)
            }

            return email_message

        except Exception as e:
            self.logger.error(f"Error formatting email alert: {e}")
            return self._create_fallback_email_alert(incident_data, str(e))

    def format_pagerduty_alert(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for PagerDuty delivery"""
        try:
            incident_id = incident_data.get('id', 'Unknown')
            service_name = incident_data.get('endpoint_name', 'Unknown Service')
            alert_level = incident_data.get('alert_level', 'medium')
            analysis_result = incident_data.get('analysis_result', {})

            # Determine severity for PagerDuty
            severity = self._get_pagerduty_severity(alert_level)

            pd_alert = {
                "routing_key": self._get_pagerduty_routing_key(),
                "event_action": "trigger",
                "dedup_key": f"devops-sentinel-{incident_id}",
                "payload": {
                    "summary": f"Service {service_name} is experiencing issues",
                    "source": "DevOps Sentinel",
                    "severity": severity,
                    "timestamp": incident_data.get('timestamp', TimestampUtils.format_timestamp(TimestampUtils.now_utc())),
                    "component": service_name,
                    "group": "Web Services",
                    "class": self._extract_primary_hypothesis(analysis_result),
                    "custom_details": {
                        "incident_id": incident_id,
                        "alert_level": alert_level,
                        "hypothesis": self._extract_primary_hypothesis(analysis_result),
                        "confidence": self._extract_confidence_level(analysis_result),
                        "recommended_actions": self._extract_recommended_actions(analysis_result),
                        "health_check": health_check
                    }
                }
            }

            return pd_alert

        except Exception as e:
            self.logger.error(f"Error formatting PagerDuty alert: {e}")
            return self._create_fallback_pagerduty_alert(incident_data, str(e))

    def format_teams_alert(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert for Microsoft Teams delivery"""
        try:
            incident_id = incident_data.get('id', 'Unknown')
            service_name = incident_data.get('endpoint_name', 'Unknown Service')
            alert_level = incident_data.get('alert_level', 'medium')
            analysis_result = incident_data.get('analysis_result', {})

            # Determine theme color
            theme_color = self._get_teams_theme_color(alert_level)

            teams_message = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": theme_color,
                "summary": f"Service Alert: {service_name}",
                "sections": [
                    {
                        "activityTitle": f"🚨 SERVICE ALERT: {service_name}",
                        "activitySubtitle": f"Incident ID: {incident_id}",
                        "facts": [
                            {
                                "name": "📍 Issue",
                                "value": self._extract_primary_hypothesis(analysis_result)
                            },
                            {
                                "name": "📊 Confidence",
                                "value": self._extract_confidence_level(analysis_result)
                            },
                            {
                                "name": "⚡ Impact",
                                "value": self._assess_impact(incident_data)
                            },
                            {
                                "name": "🛠️ Recommended Actions",
                                "value": self._format_recommended_actions(analysis_result)
                            }
                        ],
                        "markdown": True
                    }
                ],
                "potentialAction": [
                    {
                        "@type": "OpenUri",
                        "name": "View Incident Details",
                        "targets": [
                            {
                                "os": "default",
                                "uri": self._generate_incident_link(incident_id)
                            }
                        ]
                    }
                ]
            }

            return teams_message

        except Exception as e:
            self.logger.error(f"Error formatting Teams alert: {e}")
            return self._create_fallback_teams_alert(incident_data, str(e))

    def _get_slack_color(self, alert_level: str) -> str:
        """Get Slack color based on alert level"""
        colors = {
            "low": "#36a64f",      # Green
            "medium": "#ff9500",   # Orange
            "high": "#ff6b00",     # Dark orange
            "critical": "#ff0000"  # Red
        }
        return colors.get(alert_level, "#ff9500")

    def _generate_slack_summary(self, incident_data: Dict[str, Any]) -> str:
        """Generate Slack message summary"""
        service_name = incident_data.get('endpoint_name', 'Unknown Service')
        incident_id = incident_data.get('id', 'Unknown')
        health_check = incident_data.get('health_check_result', {})

        error_msg = health_check.get('error_message', 'Unknown error')
        response_time = health_check.get('response_time', 0)

        summary = f"Incident *{incident_id}* detected for *{service_name}*\n"
        summary += f"• Error: `{error_msg}`\n"
        if response_time > 0:
            summary += f"• Response time: {response_time:.0f}ms\n"

        return summary

    def _extract_primary_hypothesis(self, analysis_result: Dict[str, Any]) -> str:
        """Extract primary hypothesis from analysis result"""
        primary_hypothesis = analysis_result.get('primary_hypothesis', {})
        if primary_hypothesis:
            return primary_hypothesis.get('description', 'Root cause analysis in progress')
        return "Root cause analysis in progress"

    def _assess_impact(self, incident_data: Dict[str, Any]) -> str:
        """Assess impact of the incident"""
        service_name = incident_data.get('endpoint_name', 'Unknown Service')
        alert_level = incident_data.get('alert_level', 'medium')

        impact_descriptions = {
            "low": f"Minimal impact on {service_name}",
            "medium": f"Degraded performance for {service_name}",
            "high": f"Significant impact on {service_name}",
            "critical": f"Severe impact on {service_name} and dependent services"
        }

        return impact_descriptions.get(alert_level, impact_descriptions["medium"])

    def _extract_confidence_level(self, analysis_result: Dict[str, Any]) -> str:
        """Extract confidence level from analysis result"""
        confidence = analysis_result.get('confidence_level', 'low')
        return f"{confidence.upper()} confidence"

    def _format_recommended_actions(self, analysis_result: Dict[str, Any]) -> str:
        """Format recommended actions for display"""
        primary_hypothesis = analysis_result.get('primary_hypothesis', {})
        if primary_hypothesis:
            actions = primary_hypothesis.get('recommended_actions', [])
            if actions:
                return "\n".join([f"• {action}" for action in actions[:3]])

        return "• Investigate service logs\n• Check system resources\n• Verify recent deployments"

    def _create_diagnostic_fields(self, triage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create diagnostic fields for Slack message"""
        fields = []
        data_collection = triage_data.get('data_collection', {})

        # Log analysis
        logs = data_collection.get('logs', {})
        if logs:
            error_count = logs.get('error_count', 0)
            if error_count > 0:
                fields.append({
                    "title": "📋 Recent Errors",
                    "value": f"{error_count} errors found in recent logs",
                    "short": True
                })

        # Network diagnostics
        network = data_collection.get('network_diagnostics', {})
        if network:
            tests = network.get('tests', {})
            failed_tests = [name for name, result in tests.items()
                          if isinstance(result, dict) and result.get('status') in ['failed', 'timeout']]
            if failed_tests:
                fields.append({
                    "title": "🌐 Network Issues",
                    "value": f"Failed: {', '.join(failed_tests)}",
                    "short": True
                })

        # System metrics
        metrics = data_collection.get('system_metrics', {})
        if metrics:
            sys_metrics = metrics.get('system_metrics', {})
            cpu_usage = sys_metrics.get('cpu_usage_percent', 0)
            memory_usage = sys_metrics.get('memory_usage_percent', 0)

            if cpu_usage > 80 or memory_usage > 80:
                high_resources = []
                if cpu_usage > 80:
                    high_resources.append(f"CPU {cpu_usage}%")
                if memory_usage > 80:
                    high_resources.append(f"Memory {memory_usage}%")

                fields.append({
                    "title": "💻 High Resource Usage",
                    "value": ", ".join(high_resources),
                    "short": True
                })

        return fields

    def _create_quick_actions(self, incident_id: str, service_name: str) -> List[Dict[str, Any]]:
        """Create quick action buttons for Slack"""
        actions = [
            {
                "type": "button",
                "text": "View Logs",
                "url": f"https://logs.company.com/service/{service_name}"
            },
            {
                "type": "button",
                "text": "Check Metrics",
                "url": f"https://metrics.company.com/dashboard/{service_name}"
            },
            {
                "type": "button",
                "text": "Acknowledge",
                "url": f"https://devops-sentinel.company.com/incidents/{incident_id}/acknowledge"
            }
        ]

        return actions

    def _generate_incident_link(self, incident_id: str) -> str:
        """Generate link to incident details"""
        base_url = "https://devops-sentinel.company.com"
        return f"{base_url}/incidents/{incident_id}"

    def _get_timestamp_seconds(self, timestamp_str: Optional[str]) -> Optional[int]:
        """Convert timestamp to Unix timestamp seconds"""
        try:
            if timestamp_str:
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(timestamp_str)
                return int(dt.timestamp())
        except:
            pass
        return None

    def _generate_email_html(self, incident_data: Dict[str, Any]) -> str:
        """Generate HTML email body"""
        incident_id = incident_data.get('id', 'Unknown')
        service_name = incident_data.get('endpoint_name', 'Unknown Service')
        alert_level = incident_data.get('alert_level', 'medium')
        analysis_result = incident_data.get('analysis_result', {})
        health_check = incident_data.get('health_check_result', {})

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .header {{ background-color: {self._get_email_color(alert_level)}; color: white; padding: 20px; }}
                .content {{ padding: 20px; border: 1px solid #ddd; }}
                .section {{ margin-bottom: 20px; }}
                .label {{ font-weight: bold; }}
                .actions {{ background-color: #f5f5f5; padding: 15px; }}
                .footer {{ font-size: 12px; color: #666; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 SERVICE ALERT: {service_name}</h1>
                <p>Incident ID: {incident_id} | Severity: {alert_level.upper()}</p>
            </div>

            <div class="content">
                <div class="section">
                    <p class="label">Issue:</p>
                    <p>{self._extract_primary_hypothesis(analysis_result)}</p>
                </div>

                <div class="section">
                    <p class="label">Impact:</p>
                    <p>{self._assess_impact(incident_data)}</p>
                </div>

                <div class="section">
                    <p class="label">Confidence:</p>
                    <p>{self._extract_confidence_level(analysis_result)}</p>
                </div>

                <div class="section">
                    <p class="label">Health Check Details:</p>
                    <ul>
                        <li>URL: {health_check.get('url', 'N/A')}</li>
                        <li>Status Code: {health_check.get('status_code', 'N/A')}</li>
                        <li>Response Time: {health_check.get('response_time', 0):.0f}ms</li>
                        <li>Error: {health_check.get('error_message', 'N/A')}</li>
                    </ul>
                </div>

                <div class="actions">
                    <p class="label">Recommended Actions:</p>
                    <p>{self._format_recommended_actions(analysis_result).replace('•', '• ').replace('\n', '<br>')}</p>
                </div>

                <div class="section">
                    <p><a href="{self._generate_incident_link(incident_id)}">View Full Incident Details</a></p>
                </div>
            </div>

            <div class="footer">
                <p>This alert was generated by DevOps Sentinel at {incident_data.get('timestamp', 'Unknown time')}</p>
            </div>
        </body>
        </html>
        """

        return html

    def _generate_email_text(self, incident_data: Dict[str, Any]) -> str:
        """Generate plain text email body"""
        incident_id = incident_data.get('id', 'Unknown')
        service_name = incident_data.get('endpoint_name', 'Unknown Service')
        alert_level = incident_data.get('alert_level', 'medium')
        analysis_result = incident_data.get('analysis_result', {})
        health_check = incident_data.get('health_check_result', {})

        text = f"""
SERVICE ALERT: {service_name}
===============================

Incident ID: {incident_id}
Severity: {alert_level.upper()}
Timestamp: {incident_data.get('timestamp', 'Unknown time')}

ISSUE:
{self._extract_primary_hypothesis(analysis_result)}

IMPACT:
{self._assess_impact(incident_data)}

CONFIDENCE:
{self._extract_confidence_level(analysis_result)}

HEALTH CHECK DETAILS:
- URL: {health_check.get('url', 'N/A')}
- Status Code: {health_check.get('status_code', 'N/A')}
- Response Time: {health_check.get('response_time', 0):.0f}ms
- Error: {health_check.get('error_message', 'N/A')}

RECOMMENDED ACTIONS:
{self._format_recommended_actions(analysis_result).replace('•', '-').replace('\n', '\n')}

View Full Incident Details: {self._generate_incident_link(incident_id)}

---
This alert was generated by DevOps Sentinel
        """

        return text.strip()

    def _get_email_recipients(self, alert_level: str) -> List[str]:
        """Get email recipients based on alert level"""
        config = self.config_manager.get_agent_config("notification")

        # This would be configured in the actual system
        base_recipients = ["devops-alerts@company.com"]

        if alert_level in ["high", "critical"]:
            base_recipients.extend(["on-call@company.com", "engineering-leads@company.com"])

        return base_recipients

    def _get_email_priority(self, alert_level: str) -> str:
        """Get email priority based on alert level"""
        priorities = {
            "low": "5",
            "medium": "3",
            "high": "2",
            "critical": "1"
        }
        return priorities.get(alert_level, "3")

    def _get_email_color(self, alert_level: str) -> str:
        """Get email header color based on alert level"""
        colors = {
            "low": "#28a745",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545"
        }
        return colors.get(alert_level, "#ffc107")

    def _get_pagerduty_severity(self, alert_level: str) -> str:
        """Get PagerDuty severity based on alert level"""
        severities = {
            "low": "info",
            "medium": "warning",
            "high": "error",
            "critical": "critical"
        }
        return severities.get(alert_level, "warning")

    def _get_pagerduty_routing_key(self) -> str:
        """Get PagerDuty routing key (would be configured)"""
        return "configured-pagerduty-routing-key"

    def _get_teams_theme_color(self, alert_level: str) -> str:
        """Get Teams theme color based on alert level"""
        colors = {
            "low": "00FF00",
            "medium": "FFFF00",
            "high": "FF9900",
            "critical": "FF0000"
        }
        return colors.get(alert_level, "FFFF00")

    def _extract_recommended_actions(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Extract recommended actions from analysis result"""
        primary_hypothesis = analysis_result.get('primary_hypothesis', {})
        if primary_hypothesis:
            return primary_hypothesis.get('recommended_actions', [])
        return []

    # Fallback methods for error cases
    def _create_fallback_slack_alert(self, incident_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback Slack alert when formatting fails"""
        return {
            "text": f"🚨 SERVICE ALERT (Error in formatting)\n\nService: {incident_data.get('endpoint_name', 'Unknown')}\nIncident: {incident_data.get('id', 'Unknown')}\nError: {error}"
        }

    def _create_fallback_email_alert(self, incident_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback email alert when formatting fails"""
        return {
            "subject": f"[ERROR] Service Alert: {incident_data.get('endpoint_name', 'Unknown')}",
            "text_body": f"Service Alert (with formatting error):\n\nService: {incident_data.get('endpoint_name', 'Unknown')}\nIncident: {incident_data.get('id', 'Unknown')}\nError: {error}",
            "recipients": ["devops-alerts@company.com"]
        }

    def _create_fallback_pagerduty_alert(self, incident_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback PagerDuty alert when formatting fails"""
        return {
            "routing_key": self._get_pagerduty_routing_key(),
            "event_action": "trigger",
            "payload": {
                "summary": f"Service Alert (Error in formatting): {incident_data.get('endpoint_name', 'Unknown')}",
                "source": "DevOps Sentinel",
                "severity": "error",
                "custom_details": {
                    "error": error,
                    "incident_id": incident_data.get('id', 'Unknown')
                }
            }
        }

    def _create_fallback_teams_alert(self, incident_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback Teams alert when formatting fails"""
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF0000",
            "summary": "Service Alert (Error in formatting)",
            "sections": [
                {
                    "activityTitle": "🚨 SERVICE ALERT (Error)",
                    "activitySubtitle": f"Incident: {incident_data.get('id', 'Unknown')}",
                    "text": f"Service: {incident_data.get('endpoint_name', 'Unknown')}\nError: {error}"
                }
            ]
        }