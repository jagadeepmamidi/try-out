"""
DevOps Sentinel - Delivery Service
Deliver alerts to various notification channels
"""

import asyncio
import aiohttp
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..shared.utils import (
    ConfigManager, Logger, TimestampUtils
)
from ..shared.messaging import create_agent_communication, Message, MessageType

@dataclass
class DeliveryResult:
    """Result of alert delivery attempt"""
    channel: str
    success: bool
    message: str
    timestamp: datetime
    response_data: Optional[Dict[str, Any]] = None

class SlackDelivery:
    """Handle Slack message delivery"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("SlackDelivery")
        self.webhook_url = config.get('slack_webhook_url')
        self.timeout = config.get('timeout', 30)

    async def send_alert(self, formatted_alert: Dict[str, Any]) -> DeliveryResult:
        """Send alert to Slack"""
        try:
            if not self.webhook_url:
                return DeliveryResult(
                    channel="slack",
                    success=False,
                    message="Slack webhook URL not configured",
                    timestamp=TimestampUtils.now_utc()
                )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=formatted_alert,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        self.logger.info("Slack alert sent successfully")
                        return DeliveryResult(
                            channel="slack",
                            success=True,
                            message="Alert sent to Slack successfully",
                            timestamp=TimestampUtils.now_utc(),
                            response_data={"status_code": response.status}
                        )
                    else:
                        error_msg = f"Slack API error: {response.status} - {response_text}"
                        self.logger.error(error_msg)
                        return DeliveryResult(
                            channel="slack",
                            success=False,
                            message=error_msg,
                            timestamp=TimestampUtils.now_utc(),
                            response_data={"status_code": response.status, "response": response_text}
                        )

        except asyncio.TimeoutError:
            error_msg = "Slack delivery timed out"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="slack",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )
        except Exception as e:
            error_msg = f"Slack delivery failed: {str(e)}"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="slack",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )

class EmailDelivery:
    """Handle email delivery"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("EmailDelivery")
        self.smtp_config = config.get('smtp_config', {})

    async def send_alert(self, formatted_alert: Dict[str, Any]) -> DeliveryResult:
        """Send alert via email"""
        try:
            if not self.smtp_config:
                return DeliveryResult(
                    channel="email",
                    success=False,
                    message="SMTP configuration not available",
                    timestamp=TimestampUtils.now_utc()
                )

            # Extract email details
            subject = formatted_alert.get('subject', 'DevOps Sentinel Alert')
            html_body = formatted_alert.get('html_body', '')
            text_body = formatted_alert.get('text_body', html_body)
            recipients = formatted_alert.get('recipients', [])

            if not recipients:
                return DeliveryResult(
                    channel="email",
                    success=False,
                    message="No email recipients specified",
                    timestamp=TimestampUtils.now_utc()
                )

            # Send email
            result = await self._send_email(
                recipients=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

            return result

        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="email",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )

    async def _send_email(
        self, recipients: List[str], subject: str,
        html_body: str, text_body: str
    ) -> DeliveryResult:
        """Send email using SMTP"""
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.smtp_config.get('from_address', 'devops-sentinel@company.com')
            message['To'] = ', '.join(recipients)

            # Attach plain text and HTML versions
            if text_body:
                text_part = MIMEText(text_body, 'plain')
                message.attach(text_part)

            if html_body:
                html_part = MIMEText(html_body, 'html')
                message.attach(html_part)

            # Send email
            with smtplib.SMTP(
                self.smtp_config.get('host', 'localhost'),
                self.smtp_config.get('port', 587)
            ) as server:
                if self.smtp_config.get('use_tls', True):
                    server.starttls()

                if self.smtp_config.get('username') and self.smtp_config.get('password'):
                    server.login(
                        self.smtp_config['username'],
                        self.smtp_config['password']
                    )

                server.send_message(message)

            self.logger.info(f"Email sent successfully to {len(recipients)} recipients")
            return DeliveryResult(
                channel="email",
                success=True,
                message=f"Email sent to {len(recipients)} recipients",
                timestamp=TimestampUtils.now_utc()
            )

        except Exception as e:
            error_msg = f"SMTP error: {str(e)}"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="email",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )

class PagerDutyDelivery:
    """Handle PagerDuty alert delivery"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("PagerDutyDelivery")
        self.integration_key = config.get('pagerduty_integration_key')
        self.timeout = config.get('timeout', 30)

    async def send_alert(self, formatted_alert: Dict[str, Any]) -> DeliveryResult:
        """Send alert to PagerDuty"""
        try:
            if not self.integration_key:
                return DeliveryResult(
                    channel="pagerduty",
                    success=False,
                    message="PagerDuty integration key not configured",
                    timestamp=TimestampUtils.now_utc()
                )

            url = "https://events.pagerduty.com/v2/enqueue"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=formatted_alert,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response_data = await response.json()

                    if response.status == 202:  # Accepted
                        dedup_key = response_data.get('dedup_key')
                        self.logger.info(f"PagerDuty alert sent successfully (dedup_key: {dedup_key})")
                        return DeliveryResult(
                            channel="pagerduty",
                            success=True,
                            message=f"Alert sent to PagerDuty (dedup_key: {dedup_key})",
                            timestamp=TimestampUtils.now_utc(),
                            response_data=response_data
                        )
                    else:
                        error_msg = f"PagerDuty API error: {response.status} - {response_data}"
                        self.logger.error(error_msg)
                        return DeliveryResult(
                            channel="pagerduty",
                            success=False,
                            message=error_msg,
                            timestamp=TimestampUtils.now_utc(),
                            response_data={"status_code": response.status, "response": response_data}
                        )

        except asyncio.TimeoutError:
            error_msg = "PagerDuty delivery timed out"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="pagerduty",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )
        except Exception as e:
            error_msg = f"PagerDuty delivery failed: {str(e)}"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="pagerduty",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )

class TeamsDelivery:
    """Handle Microsoft Teams message delivery"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("TeamsDelivery")
        self.webhook_url = config.get('teams_webhook_url')
        self.timeout = config.get('timeout', 30)

    async def send_alert(self, formatted_alert: Dict[str, Any]) -> DeliveryResult:
        """Send alert to Microsoft Teams"""
        try:
            if not self.webhook_url:
                return DeliveryResult(
                    channel="teams",
                    success=False,
                    message="Teams webhook URL not configured",
                    timestamp=TimestampUtils.now_utc()
                )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=formatted_alert,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        self.logger.info("Teams alert sent successfully")
                        return DeliveryResult(
                            channel="teams",
                            success=True,
                            message="Alert sent to Teams successfully",
                            timestamp=TimestampUtils.now_utc(),
                            response_data={"status_code": response.status}
                        )
                    else:
                        error_msg = f"Teams API error: {response.status} - {response_text}"
                        self.logger.error(error_msg)
                        return DeliveryResult(
                            channel="teams",
                            success=False,
                            message=error_msg,
                            timestamp=TimestampUtils.now_utc(),
                            response_data={"status_code": response.status, "response": response_text}
                        )

        except asyncio.TimeoutError:
            error_msg = "Teams delivery timed out"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="teams",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )
        except Exception as e:
            error_msg = f"Teams delivery failed: {str(e)}"
            self.logger.error(error_msg)
            return DeliveryResult(
                channel="teams",
                success=False,
                message=error_msg,
                timestamp=TimestampUtils.now_utc()
            )

class AlertDeliveryService:
    """Main service for delivering alerts to multiple channels"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = Logger.setup_logger("AlertDeliveryService")
        self.communication = create_agent_communication("notification")

        # Initialize delivery services
        self.notification_config = self.config_manager.get_agent_config("notification")
        self.delivery_services = self._initialize_delivery_services()

        # Alert deduplication and cooldown
        self.recent_alerts: Dict[str, datetime] = {}
        self.cooldown_period = self.notification_config.get('cooldown_period', 15)  # minutes

        # Register message handler
        get_message_queue().register_handler("notification", self._handle_message)

        self.logger.info("Alert delivery service initialized")

    def _initialize_delivery_services(self) -> Dict[str, Any]:
        """Initialize delivery services for different channels"""
        services = {}

        # Slack delivery
        if self.notification_config.get('delivery_channels', {}).get('slack', {}).get('enabled', False):
            services['slack'] = SlackDelivery(
                self.notification_config.get('delivery_channels', {}).get('slack', {})
            )

        # Email delivery
        if self.notification_config.get('delivery_channels', {}).get('email', {}).get('enabled', False):
            services['email'] = EmailDelivery(
                self.notification_config.get('delivery_channels', {}).get('email', {})
            )

        # PagerDuty delivery
        if self.notification_config.get('delivery_channels', {}).get('pagerduty', {}).get('enabled', False):
            services['pagerduty'] = PagerDutyDelivery(
                self.notification_config.get('delivery_channels', {}).get('pagerduty', {})
            )

        # Teams delivery
        if self.notification_config.get('delivery_channels', {}).get('teams', {}).get('enabled', False):
            services['teams'] = TeamsDelivery(
                self.notification_config.get('delivery_channels', {}).get('teams', {})
            )

        self.logger.info(f"Initialized delivery services: {list(services.keys())}")
        return services

    async def _handle_message(self, message: Message):
        """Handle incoming notification requests"""
        try:
            if message.type == MessageType.NOTIFICATION_REQUEST:
                await self._process_notification_request(message)
            else:
                self.logger.warning(f"Unexpected message type: {message.type}")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def _process_notification_request(self, message: Message):
        """Process notification request and deliver alerts"""
        try:
            data = message.data
            incident = data.get('incident')
            incident_id = incident.get('id', 'unknown')

            self.logger.info(f"Processing notification request for incident {incident_id}")

            # Check cooldown period
            if self._is_in_cooldown(incident):
                self.logger.info(f"Incident {incident_id} is in cooldown period, skipping notification")
                self.communication.send_response(message, {
                    "status": "skipped",
                    "reason": "cooldown_period",
                    "incident_id": incident_id
                })
                return

            # Format alerts for different channels
            from .alert_formatter import AlertFormatter
            formatter = AlertFormatter()

            # Determine which channels to use based on alert level and configuration
            channels = self._determine_delivery_channels(incident)

            if not channels:
                self.logger.warning("No delivery channels configured")
                self.communication.send_response(message, {
                    "status": "failed",
                    "reason": "no_delivery_channels",
                    "incident_id": incident_id
                })
                return

            # Deliver alerts
            delivery_results = await self._deliver_alerts(incident, channels, formatter)

            # Update cooldown tracking
            self._update_cooldown_tracking(incident)

            # Send response
            successful_deliveries = [r for r in delivery_results if r.success]
            failed_deliveries = [r for r in delivery_results if not r.success]

            self.communication.send_response(message, {
                "status": "completed",
                "incident_id": incident_id,
                "successful_deliveries": len(successful_deliveries),
                "failed_deliveries": len(failed_deliveries),
                "delivery_results": [
                    {
                        "channel": r.channel,
                        "success": r.success,
                        "message": r.message,
                        "timestamp": TimestampUtils.format_timestamp(r.timestamp)
                    }
                    for r in delivery_results
                ]
            })

            self.logger.info(
                f"Notification completed for incident {incident_id}: "
                f"{len(successful_deliveries)} successful, {len(failed_deliveries)} failed"
            )

        except Exception as e:
            self.logger.error(f"Error processing notification request: {e}")
            self.communication.send_response(message, {
                "status": "error",
                "error": str(e),
                "incident_id": incident.get('id', 'unknown')
            })

    def _is_in_cooldown(self, incident: Dict[str, Any]) -> bool:
        """Check if incident is in cooldown period"""
        incident_id = incident.get('id', '')
        service_name = incident.get('endpoint_name', '')
        alert_level = incident.get('alert_level', 'medium')

        # Create cooldown key
        cooldown_key = f"{service_name}:{alert_level}"

        # Check if recent alert exists
        if cooldown_key in self.recent_alerts:
            last_alert_time = self.recent_alerts[cooldown_key]
            time_since_last = TimestampUtils.now_utc() - last_alert_time
            cooldown_threshold = timedelta(minutes=self.cooldown_period)

            if time_since_last < cooldown_threshold:
                return True

        return False

    def _determine_delivery_channels(self, incident: Dict[str, Any]) -> List[str]:
        """Determine which channels to use for delivery"""
        alert_level = incident.get('alert_level', 'medium')
        configured_channels = self.notification_config.get('delivery_channels', {})

        channels = []

        # Always use primary channels
        for channel_name, channel_config in configured_channels.items():
            if channel_config.get('enabled', False):
                # Check if channel should be used for this alert level
                min_level = channel_config.get('min_alert_level', 'low')
                if self._should_use_channel(alert_level, min_level):
                    channels.append(channel_name)

        # Ensure at least one channel is used
        if not channels and self.delivery_services:
            channels = list(self.delivery_services.keys())[:1]  # Use first available

        return channels

    def _should_use_channel(self, current_level: str, min_level: str) -> bool:
        """Check if channel should be used based on alert level"""
        level_hierarchy = {
            'low': 1,
            'medium': 2,
            'high': 3,
            'critical': 4
        }

        current_value = level_hierarchy.get(current_level, 2)
        min_value = level_hierarchy.get(min_level, 1)

        return current_value >= min_value

    async def _deliver_alerts(
        self, incident: Dict[str, Any], channels: List[str], formatter
    ) -> List[DeliveryResult]:
        """Deliver alerts to specified channels"""
        delivery_tasks = []

        for channel in channels:
            if channel in self.delivery_services:
                task = self._deliver_to_channel(incident, channel, formatter)
                delivery_tasks.append(task)

        # Execute deliveries concurrently
        results = await asyncio.gather(*delivery_tasks, return_exceptions=True)

        # Convert exceptions to failed results
        delivery_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                delivery_results.append(DeliveryResult(
                    channel=channels[i],
                    success=False,
                    message=f"Delivery exception: {str(result)}",
                    timestamp=TimestampUtils.now_utc()
                ))
            else:
                delivery_results.append(result)

        return delivery_results

    async def _deliver_to_channel(
        self, incident: Dict[str, Any], channel: str, formatter
    ) -> DeliveryResult:
        """Deliver alert to specific channel"""
        try:
            # Format alert for the channel
            if channel == 'slack':
                formatted_alert = formatter.format_slack_alert(incident)
                delivery_service = self.delivery_services['slack']
            elif channel == 'email':
                formatted_alert = formatter.format_email_alert(incident)
                delivery_service = self.delivery_services['email']
            elif channel == 'pagerduty':
                formatted_alert = formatter.format_pagerduty_alert(incident)
                delivery_service = self.delivery_services['pagerduty']
            elif channel == 'teams':
                formatted_alert = formatter.format_teams_alert(incident)
                delivery_service = self.delivery_services['teams']
            else:
                return DeliveryResult(
                    channel=channel,
                    success=False,
                    message=f"Unsupported channel: {channel}",
                    timestamp=TimestampUtils.now_utc()
                )

            # Deliver the alert
            result = await delivery_service.send_alert(formatted_alert)
            return result

        except Exception as e:
            self.logger.error(f"Error delivering to {channel}: {e}")
            return DeliveryResult(
                channel=channel,
                success=False,
                message=f"Channel delivery error: {str(e)}",
                timestamp=TimestampUtils.now_utc()
            )

    def _update_cooldown_tracking(self, incident: Dict[str, Any]):
        """Update cooldown tracking for the incident"""
        service_name = incident.get('endpoint_name', '')
        alert_level = incident.get('alert_level', 'medium')
        cooldown_key = f"{service_name}:{alert_level}"

        self.recent_alerts[cooldown_key] = TimestampUtils.now_utc()

        # Clean up old entries (older than 1 hour)
        cutoff_time = TimestampUtils.now_utc() - timedelta(hours=1)
        old_keys = [
            key for key, timestamp in self.recent_alerts.items()
            if timestamp < cutoff_time
        ]

        for key in old_keys:
            del self.recent_alerts[key]

    async def start(self):
        """Start the notification agent"""
        self.logger.info("Notification agent started - waiting for notification requests")

        # Keep the agent running and processing messages
        while True:
            try:
                # Process any pending messages
                self.communication.process_messages()
                await asyncio.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("Notification agent stopped")
                break
            except Exception as e:
                self.logger.error(f"Error in notification agent main loop: {e}")
                await asyncio.sleep(5)

    def get_delivery_status(self) -> Dict[str, Any]:
        """Get current delivery service status"""
        return {
            "available_channels": list(self.delivery_services.keys()),
            "recent_alerts_count": len(self.recent_alerts),
            "cooldown_period_minutes": self.cooldown_period,
            "services_status": {
                name: "available" for name in self.delivery_services.keys()
            }
        }

# Main execution function for Compyle platform
async def main():
    """Main entry point for notification agent"""
    service = AlertDeliveryService()
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())