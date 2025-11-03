"""
DevOps Sentinel - Inter-Agent Messaging System
Manages communication between specialized monitoring agents
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timezone

from .utils import TimestampUtils, Logger

class MessageType(Enum):
    """Message types for inter-agent communication"""
    HEALTH_CHECK_FAILURE = "health_check_failure"
    TRIAGE_REQUEST = "triage_request"
    TRIAGE_RESPONSE = "triage_response"
    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_RESPONSE = "analysis_response"
    NOTIFICATION_REQUEST = "notification_request"
    NOTIFICATION_SENT = "notification_sent"
    INCIDENT_RESOLVED = "incident_resolved"

@dataclass
class Message:
    """Message structure for inter-agent communication"""
    id: str
    type: MessageType
    sender: str
    recipient: str
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    requires_response: bool = False
    response_timeout: int = 300  # 5 minutes default

class MessageQueue:
    """In-memory message queue for inter-agent communication"""

    def __init__(self):
        self.logger = Logger.setup_logger("MessageQueue")
        self.queues: Dict[str, list] = {}  # agent_name -> message queue
        self.message_handlers: Dict[str, Callable] = {}  # message_type -> handler
        self.delivered_messages: Dict[str, Message] = {}  # message_id -> message
        self.pending_responses: Dict[str, Message] = {}  # correlation_id -> original message

    def register_handler(self, agent_name: str, handler: Callable):
        """Register message handler for an agent"""
        self.message_handlers[agent_name] = handler
        if agent_name not in self.queues:
            self.queues[agent_name] = []
        self.logger.info(f"Registered handler for agent: {agent_name}")

    def send_message(self, message: Message) -> bool:
        """Send message to specified agent"""
        try:
            # Store message in delivery queue
            if message.recipient not in self.queues:
                self.queues[message.recipient] = []

            self.queues[message.recipient].append(message)
            self.delivered_messages[message.id] = message

            if message.requires_response:
                self.pending_responses[message.correlation_id] = message

            self.logger.info(f"Message sent: {message.type.value} from {message.sender} to {message.recipient}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False

    def receive_messages(self, agent_name: str) -> list:
        """Receive all messages for an agent"""
        if agent_name not in self.queues:
            return []

        messages = self.queues[agent_name].copy()
        self.queues[agent_name].clear()
        return messages

    def send_response(self, original_message: Message, response_data: Dict[str, Any]) -> bool:
        """Send response to a message that requires one"""
        if not original_message.correlation_id:
            return False

        response_message = Message(
            id=self._generate_message_id(),
            type=MessageType(f"{original_message.type.value}_response"),
            sender=original_message.recipient,
            recipient=original_message.sender,
            timestamp=TimestampUtils.now_utc(),
            data=response_data,
            correlation_id=original_message.correlation_id
        )

        return self.send_message(response_message)

    def wait_for_response(self, correlation_id: str, timeout: int = 300) -> Optional[Message]:
        """Wait for response to a message"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if response received (implementation would check queues)
            time.sleep(1)

        # Timeout occurred
        if correlation_id in self.pending_responses:
            del self.pending_responses[correlation_id]

        return None

    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        return f"MSG_{timestamp}"

class AgentCommunication:
    """High-level communication interface for agents"""

    def __init__(self, agent_name: str, message_queue: MessageQueue):
        self.agent_name = agent_name
        self.message_queue = message_queue
        self.logger = Logger.setup_logger(f"{agent_name}Communication")

    def send_triage_request(self, incident_id: str, endpoint_name: str, url: str) -> str:
        """Send triage request to Triage Agent"""
        message = Message(
            id=self.message_queue._generate_message_id(),
            type=MessageType.TRIAGE_REQUEST,
            sender=self.agent_name,
            recipient="triage",
            timestamp=TimestampUtils.now_utc(),
            data={
                "incident_id": incident_id,
                "endpoint_name": endpoint_name,
                "url": url
            },
            requires_response=True,
            correlation_id=f"triage_{incident_id}"
        )

        if self.message_queue.send_message(message):
            return message.correlation_id
        return None

    def send_analysis_request(self, incident_id: str, health_check: Dict[str, Any], triage_data: Dict[str, Any]) -> str:
        """Send analysis request to Analysis Agent"""
        message = Message(
            id=self.message_queue._generate_message_id(),
            type=MessageType.ANALYSIS_REQUEST,
            sender=self.agent_name,
            recipient="analysis",
            timestamp=TimestampUtils.now_utc(),
            data={
                "incident_id": incident_id,
                "health_check": health_check,
                "triage_data": triage_data
            },
            requires_response=True,
            correlation_id=f"analysis_{incident_id}"
        )

        if self.message_queue.send_message(message):
            return message.correlation_id
        return None

    def send_notification_request(self, incident: Dict[str, Any]) -> str:
        """Send notification request to Notification Agent"""
        message = Message(
            id=self.message_queue._generate_message_id(),
            type=MessageType.NOTIFICATION_REQUEST,
            sender=self.agent_name,
            recipient="notification",
            timestamp=TimestampUtils.now_utc(),
            data={"incident": incident},
            requires_response=True,
            correlation_id=f"notification_{incident['id']}"
        )

        if self.message_queue.send_message(message):
            return message.correlation_id
        return None

    def send_health_check_failure_alert(self, incident: Dict[str, Any]) -> None:
        """Send health check failure alert to monitoring system"""
        message = Message(
            id=self.message_queue._generate_message_id(),
            type=MessageType.HEALTH_CHECK_FAILURE,
            sender=self.agent_name,
            recipient="monitoring",
            timestamp=TimestampUtils.now_utc(),
            data=incident
        )

        self.message_queue.send_message(message)

    def process_messages(self) -> list:
        """Process all pending messages for this agent"""
        messages = self.message_queue.receive_messages(self.agent_name)
        processed = []

        for message in messages:
            try:
                if message.requires_response:
                    # This would trigger the agent's message handler
                    processed.append(message)
                else:
                    # Handle informational messages
                    self.logger.info(f"Received {message.type.value} message from {message.sender}")
                    processed.append(message)
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")

        return processed

# Global message queue instance
_message_queue = MessageQueue()

def get_message_queue() -> MessageQueue:
    """Get global message queue instance"""
    return _message_queue

def create_agent_communication(agent_name: str) -> AgentCommunication:
    """Create communication interface for an agent"""
    return AgentCommunication(agent_name, _message_queue)