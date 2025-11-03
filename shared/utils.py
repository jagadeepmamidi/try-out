"""
DevOps Sentinel - Shared Utilities
Common utilities used across all agents
"""

import json
import time
import logging
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class IncidentStatus(Enum):
    """Incident status enumeration"""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    ANALYZED = "analyzed"
    RESOLVED = "resolved"

class AlertLevel(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class HealthCheckResult:
    """Health check result data structure"""
    endpoint_name: str
    url: str
    status_code: int
    response_time: float
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    ssl_expiry_days: Optional[int] = None

@dataclass
class Incident:
    """Incident data structure"""
    id: str
    endpoint_name: str
    status: IncidentStatus
    alert_level: AlertLevel
    timestamp: datetime
    last_updated: datetime
    health_check_result: HealthCheckResult
    triage_data: Optional[Dict[str, Any]] = None
    analysis_result: Optional[Dict[str, Any]] = None
    notifications_sent: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.notifications_sent is None:
            self.notifications_sent = []

class ConfigManager:
    """Configuration management for agents"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.endpoints = self._load_endpoints()
        self.agents_config = self._load_agents_config()

    def _load_endpoints(self) -> List[Dict[str, Any]]:
        """Load endpoint configurations"""
        try:
            with open(f"{self.config_dir}/endpoints.yaml", 'r') as f:
                return yaml.safe_load(f)['endpoints']
        except Exception as e:
            logging.error(f"Failed to load endpoints config: {e}")
            return []

    def _load_agents_config(self) -> Dict[str, Any]:
        """Load agent configurations"""
        try:
            with open(f"{self.config_dir}/agents.yaml", 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"Failed to load agents config: {e}")
            return {}

    def get_endpoints(self) -> List[Dict[str, Any]]:
        """Get configured endpoints"""
        return self.endpoints

    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get configuration for specific agent"""
        return self.agents_config.get('agents', {}).get(agent_name, {})

class Logger:
    """Standardized logging for all agents"""

    @staticmethod
    def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
        """Set up logger with consistent formatting"""
        logger = logging.getLogger(name)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(getattr(logging, level.upper()))
        return logger

class TimestampUtils:
    """Utilities for timestamp handling"""

    @staticmethod
    def now_utc() -> datetime:
        """Get current UTC time"""
        return datetime.now(timezone.utc)

    @staticmethod
    def format_timestamp(dt: datetime) -> str:
        """Format datetime for consistent display"""
        return dt.isoformat()

    @staticmethod
    def minutes_ago(minutes: int) -> datetime:
        """Get timestamp N minutes ago"""
        return TimestampUtils.now_utc() - timedelta(minutes=minutes)

class IncidentIDGenerator:
    """Generate unique incident IDs"""

    @staticmethod
    def generate() -> str:
        """Generate unique incident ID with timestamp"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"INC_{timestamp}"

class NetworkUtils:
    """Network-related utilities"""

    @staticmethod
    def is_ssl_error(error: Exception) -> bool:
        """Check if error is SSL-related"""
        ssl_error_keywords = ['ssl', 'certificate', 'tls', 'handshake']
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in ssl_error_keywords)

    @staticmethod
    def is_timeout_error(error: Exception) -> bool:
        """Check if error is timeout-related"""
        timeout_error_keywords = ['timeout', 'timed out', 'connection refused']
        error_str = str(error).lower()
        return any(keyword in error_str for keyword in timeout_error_keywords)

class MessageFormatter:
    """Format messages for inter-agent communication"""

    @staticmethod
    def format_health_check_alert(incident: Incident) -> Dict[str, Any]:
        """Format health check failure alert"""
        return {
            "type": "health_check_failure",
            "incident_id": incident.id,
            "endpoint_name": incident.endpoint_name,
            "alert_level": incident.alert_level.value,
            "timestamp": TimestampUtils.format_timestamp(incident.timestamp),
            "health_check": asdict(incident.health_check_result)
        }

    @staticmethod
    def format_triage_request(incident: Incident) -> Dict[str, Any]:
        """Format triage data collection request"""
        return {
            "type": "triage_request",
            "incident_id": incident.id,
            "endpoint_name": incident.endpoint_name,
            "url": incident.health_check_result.url,
            "timestamp": TimestampUtils.format_timestamp(incident.timestamp)
        }

    @staticmethod
    def format_analysis_request(incident: Incident) -> Dict[str, Any]:
        """Format analysis request"""
        return {
            "type": "analysis_request",
            "incident_id": incident.id,
            "health_check": asdict(incident.health_check_result),
            "triage_data": incident.triage_data,
            "timestamp": TimestampUtils.format_timestamp(incident.timestamp)
        }

    @staticmethod
    def format_notification_request(incident: Incident) -> Dict[str, Any]:
        """Format notification request"""
        return {
            "type": "notification_request",
            "incident": asdict(incident),
            "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc())
        }