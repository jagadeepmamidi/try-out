"""
DevOps Sentinel - Monitoring Agent
Continuous health monitoring of API endpoints
"""

import time
import requests
import ssl
import socket
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..shared.utils import (
    ConfigManager, Logger, HealthCheckResult, Incident,
    IncidentStatus, AlertLevel, IncidentIDGenerator,
    NetworkUtils, TimestampUtils, MessageFormatter
)
from ..shared.messaging import create_agent_communication, get_message_queue

class HealthChecker:
    """Handles individual health checks for endpoints"""

    def __init__(self, endpoint_config: Dict[str, Any]):
        self.config = endpoint_config
        self.logger = Logger.setup_logger(f"HealthChecker_{endpoint_config['name']}")
        self.consecutive_failures = 0

    async def check_health(self) -> HealthCheckResult:
        """Perform health check on configured endpoint"""
        start_time = time.time()
        timestamp = TimestampUtils.now_utc()

        try:
            # Perform HTTP health check
            response_data = await self._make_http_request()
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Check SSL certificate expiry for HTTPS endpoints
            ssl_expiry_days = None
            if self.config['url'].startswith('https://'):
                ssl_expiry_days = self._check_ssl_expiry()

            # Determine success based on status code and response time
            success = (
                response_data['status_code'] in self.config['expected_status'] and
                response_time <= self.config['response_time_threshold']
            )

            result = HealthCheckResult(
                endpoint_name=self.config['name'],
                url=self.config['url'],
                status_code=response_data['status_code'],
                response_time=response_time,
                timestamp=timestamp,
                success=success,
                ssl_expiry_days=ssl_expiry_days
            )

            if success:
                self.consecutive_failures = 0
                self.logger.info(f"Health check passed: {self.config['name']} - {response_time:.0f}ms")
            else:
                self.consecutive_failures += 1
                error_msg = self._determine_error_message(response_data['status_code'], response_time)
                result.error_message = error_msg
                self.logger.warning(f"Health check failed: {self.config['name']} - {error_msg}")

            return result

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.consecutive_failures += 1

            error_message = str(e)
            if NetworkUtils.is_timeout_error(e):
                error_message = "Connection timeout"
            elif NetworkUtils.is_ssl_error(e):
                error_message = "SSL certificate error"

            result = HealthCheckResult(
                endpoint_name=self.config['name'],
                url=self.config['url'],
                status_code=0,
                response_time=response_time,
                timestamp=timestamp,
                success=False,
                error_message=error_message
            )

            self.logger.error(f"Health check exception: {self.config['name']} - {error_message}")
            return result

    async def _make_http_request(self) -> Dict[str, Any]:
        """Make HTTP request with timeout and error handling"""
        timeout = aiohttp.ClientTimeout(total=self.config['timeout'])

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method=self.config['method'],
                url=self.config['url'],
                headers={'User-Agent': 'DevOps-Sentinel/1.0'}
            ) as response:
                return {
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'content_length': response.headers.get('content-length', '0')
                }

    def _check_ssl_expiry(self) -> Optional[int]:
        """Check SSL certificate expiry for HTTPS endpoints"""
        try:
            parsed_url = urlparse(self.config['url'])
            hostname = parsed_url.hostname
            port = parsed_url.port or 443

            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as secure_sock:
                    cert = secure_sock.getpeercert()
                    expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    days_until_expiry = (expiry_date - TimestampUtils.now_utc()).days
                    return days_until_expiry

        except Exception as e:
            self.logger.warning(f"Failed to check SSL certificate for {self.config['url']}: {e}")
            return None

    def _determine_error_message(self, status_code: int, response_time: float) -> str:
        """Determine appropriate error message based on failure type"""
        if status_code not in self.config['expected_status']:
            return f"HTTP {status_code} error"
        elif response_time > self.config['response_time_threshold']:
            return f"Response time {response_time:.0f}ms exceeds threshold {self.config['response_time_threshold']}ms"
        else:
            return "Health check failed"

    def should_trigger_incident(self, failure_threshold: int) -> bool:
        """Check if incident should be triggered based on consecutive failures"""
        return self.consecutive_failures >= failure_threshold

class MonitoringAgent:
    """Main monitoring agent that orchestrates health checks"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = Logger.setup_logger("MonitoringAgent")
        self.communication = create_agent_communication("monitoring")
        self.health_checkers: Dict[str, HealthChecker] = {}
        self.active_incidents: Dict[str, Incident] = {}
        self.ssl_warnings: Dict[str, datetime] = {}
        self.running = False

        # Load configuration
        self.monitoring_config = self.config_manager.get_agent_config("monitoring")
        self.endpoints = self.config_manager.get_endpoints()

        # Initialize health checkers for each endpoint
        for endpoint in self.endpoints:
            checker = HealthChecker(endpoint)
            self.health_checkers[endpoint['name']] = checker

        self.logger.info(f"Monitoring agent initialized with {len(self.endpoints)} endpoints")

    async def start_monitoring(self):
        """Start continuous monitoring loop"""
        self.running = True
        self.logger.info("Starting continuous monitoring")

        while self.running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(self.monitoring_config.get('poll_interval', 60))

            except Exception as e:
                self.logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(10)  # Brief pause before retry

    async def stop_monitoring(self):
        """Stop monitoring loop"""
        self.running = False
        self.logger.info("Monitoring stopped")

    async def _monitoring_cycle(self):
        """Execute one complete monitoring cycle"""
        # Process any pending messages
        self.communication.process_messages()

        # Run health checks for all endpoints concurrently
        tasks = [
            self._check_endpoint(checker)
            for checker in self.health_checkers.values()
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Check for SSL certificate warnings
        await self._check_ssl_warnings()

        # Clean up resolved incidents
        self._cleanup_resolved_incidents()

    async def _check_endpoint(self, checker: HealthChecker):
        """Check a single endpoint and handle results"""
        try:
            result = await checker.check_health()

            if not result.success and checker.should_trigger_incident(
                self.monitoring_config.get('failure_threshold', 2)
            ):
                await self._handle_endpoint_failure(result, checker)

            elif result.success:
                # Check if there's an active incident to resolve
                await self._check_incident_resolution(result)

        except Exception as e:
            self.logger.error(f"Error checking endpoint {checker.config['name']}: {e}")

    async def _handle_endpoint_failure(self, result: HealthCheckResult, checker: HealthChecker):
        """Handle endpoint failure by creating incident and triggering workflow"""
        endpoint_name = result.endpoint_name

        # Check if incident already exists
        if endpoint_name in self.active_incidents:
            incident = self.active_incidents[endpoint_name]
            incident.last_updated = TimestampUtils.now_utc()
            return

        # Create new incident
        incident = Incident(
            id=IncidentIDGenerator.generate(),
            endpoint_name=endpoint_name,
            status=IncidentStatus.DETECTED,
            alert_level=self._determine_alert_level(result),
            timestamp=result.timestamp,
            last_updated=result.timestamp,
            health_check_result=result
        )

        self.active_incidents[endpoint_name] = incident
        self.logger.warning(f"Incident created: {incident.id} for endpoint {endpoint_name}")

        # Send health check failure alert
        self.communication.send_health_check_failure_alert(
            MessageFormatter.format_health_check_alert(incident)
        )

        # Trigger triage agent
        await self._trigger_triage_workflow(incident)

    async def _check_incident_resolution(self, result: HealthCheckResult):
        """Check if endpoint recovery should resolve active incidents"""
        endpoint_name = result.endpoint_name

        if endpoint_name in self.active_incidents:
            incident = self.active_incidents[endpoint_name]
            incident.status = IncidentStatus.RESOLVED
            incident.last_updated = result.timestamp

            self.logger.info(f"Incident resolved: {incident.id} for endpoint {endpoint_name}")

    async def _trigger_triage_workflow(self, incident: Incident):
        """Trigger triage agent to collect diagnostic data"""
        try:
            correlation_id = self.communication.send_triage_request(
                incident.id,
                incident.endpoint_name,
                incident.health_check_result.url
            )

            if correlation_id:
                self.logger.info(f"Triage request sent for incident {incident.id}")
            else:
                self.logger.error(f"Failed to send triage request for incident {incident.id}")

        except Exception as e:
            self.logger.error(f"Error triggering triage workflow: {e}")

    async def _check_ssl_warnings(self):
        """Check for SSL certificate expiry warnings"""
        ssl_warning_days = self.monitoring_config.get('ssl_warning_days', 30)
        now = TimestampUtils.now_utc()

        for checker in self.health_checkers.values():
            try:
                if not checker.config['url'].startswith('https://'):
                    continue

                # Perform SSL check (this could be optimized to check less frequently)
                ssl_expiry_days = checker._check_ssl_expiry()

                if ssl_expiry_days and ssl_expiry_days <= ssl_warning_days:
                    endpoint_name = checker.config['name']

                    # Check if we've already sent a warning recently
                    if (endpoint_name not in self.ssl_warnings or
                        (now - self.ssl_warnings[endpoint_name]) > timedelta(days=1)):

                        self.ssl_warnings[endpoint_name] = now
                        self.logger.warning(
                            f"SSL certificate for {endpoint_name} expires in {ssl_expiry_days} days"
                        )
                        # Could trigger separate SSL warning workflow here

            except Exception as e:
                self.logger.error(f"Error checking SSL for {checker.config['name']}: {e}")

    def _determine_alert_level(self, result: HealthCheckResult) -> AlertLevel:
        """Determine alert level based on failure type"""
        if result.error_message and "timeout" in result.error_message.lower():
            return AlertLevel.HIGH
        elif result.status_code >= 500:
            return AlertLevel.CRITICAL
        elif result.status_code >= 400:
            return AlertLevel.MEDIUM
        else:
            return AlertLevel.LOW

    def _cleanup_resolved_incidents(self):
        """Clean up old resolved incidents"""
        cutoff_time = TimestampUtils.now_utc() - timedelta(hours=24)

        resolved_incidents = [
            name for name, incident in self.active_incidents.items()
            if incident.status == IncidentStatus.RESOLVED and
            incident.last_updated < cutoff_time
        ]

        for name in resolved_incidents:
            del self.active_incidents[name]
            self.logger.info(f"Cleaned up resolved incident for endpoint: {name}")

    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "running": self.running,
            "endpoints_monitored": len(self.health_checkers),
            "active_incidents": len(self.active_incidents),
            "endpoint_status": {
                name: checker.consecutive_failures
                for name, checker in self.health_checkers.items()
            }
        }

# Main execution function for Compyle platform
async def main():
    """Main entry point for monitoring agent"""
    agent = MonitoringAgent()

    try:
        await agent.start_monitoring()
    except KeyboardInterrupt:
        await agent.stop_monitoring()
        print("Monitoring agent stopped")
    except Exception as e:
        Logger.setup_logger("MonitoringAgent").error(f"Fatal error: {e}")
        await agent.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())