"""
DevOps Sentinel - Analysis Agent
Perform LLM-powered root cause analysis
"""

import asyncio
import json
import re
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from ..shared.utils import (
    ConfigManager, Logger, TimestampUtils, MessageFormatter
)
from ..shared.messaging import create_agent_communication, Message, MessageType

@dataclass
class AnalysisHypothesis:
    """Represents a root cause hypothesis"""
    id: str
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: List[str]
    recommended_actions: List[str]
    supporting_data: Dict[str, Any]

class LLMPatternMatcher:
    """Pattern matching for common DevOps issues"""

    def __init__(self):
        self.logger = Logger.setup_logger("LLMPatternMatcher")
        self.patterns = self._initialize_patterns()

    def _initialize_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize known failure patterns"""
        return {
            "database_connection_error": {
                "keywords": ["connection refused", "timeout", "connection pool", "database", "sql"],
                "evidence_patterns": [
                    r"connection.*refused",
                    r"database.*timeout",
                    r"connection.*pool.*exhausted",
                    r"sql.*error"
                ],
                "confidence_boost": 0.3,
                "actions": [
                    "Check database server availability",
                    "Verify connection string and credentials",
                    "Check connection pool settings",
                    "Monitor database server resources"
                ]
            },
            "memory_leak": {
                "keywords": ["out of memory", "memory", "heap", "oom", "allocation"],
                "evidence_patterns": [
                    r"out of memory",
                    r"memory.*usage.*high",
                    r"heap.*space",
                    r"allocation.*failed"
                ],
                "confidence_boost": 0.25,
                "actions": [
                    "Analyze memory usage patterns",
                    "Check for memory leaks in application code",
                    "Increase heap size if appropriate",
                    "Monitor garbage collection metrics"
                ]
            },
            "network_connectivity": {
                "keywords": ["network", "connection", "timeout", "unreachable", "dns"],
                "evidence_patterns": [
                    r"network.*unreachable",
                    r"connection.*timeout",
                    r"dns.*resolution.*failed",
                    r"host.*unreachable"
                ],
                "confidence_boost": 0.2,
                "actions": [
                    "Verify network connectivity between services",
                    "Check DNS resolution",
                    "Verify firewall rules",
                    "Test network latency and packet loss"
                ]
            },
            "ssl_certificate": {
                "keywords": ["ssl", "certificate", "tls", "handshake", "expired"],
                "evidence_patterns": [
                    r"ssl.*certificate.*expired",
                    r"certificate.*error",
                    r"tls.*handshake.*failed",
                    r"certificate.*invalid"
                ],
                "confidence_boost": 0.4,
                "actions": [
                    "Renew SSL certificate",
                    "Verify certificate chain",
                    "Check certificate installation",
                    "Update certificate trust store"
                ]
            },
            "service_overload": {
                "keywords": ["overload", "too many requests", "rate limit", "high cpu", "high memory"],
                "evidence_patterns": [
                    r"too many requests",
                    r"rate limit.*exceeded",
                    r"cpu.*usage.*high",
                    r"memory.*usage.*high"
                ],
                "confidence_boost": 0.2,
                "actions": [
                    "Scale up service resources",
                    "Implement rate limiting",
                    "Optimize application performance",
                    "Add load balancing"
                ]
            },
            "deployment_issue": {
                "keywords": ["deployment", "release", "version", "rollback", "config"],
                "evidence_patterns": [
                    r"deployment.*failed",
                    r"version.*mismatch",
                    r"configuration.*error",
                    r"rollback.*required"
                ],
                "confidence_boost": 0.35,
                "actions": [
                    "Review recent deployment changes",
                    "Consider rolling back to previous version",
                    "Verify configuration files",
                    "Check deployment logs"
                ]
            }
        }

    def match_patterns(self, health_check: Dict[str, Any], triage_data: Dict[str, Any]) -> List[AnalysisHypothesis]:
        """Match known patterns against the incident data"""
        hypotheses = []

        # Combine all text data for analysis
        combined_text = self._extract_text_data(health_check, triage_data)

        for pattern_name, pattern_config in self.patterns.items():
            confidence = self._calculate_pattern_confidence(
                pattern_config, combined_text, health_check, triage_data
            )

            if confidence > 0.1:  # Minimum confidence threshold
                evidence = self._extract_pattern_evidence(
                    pattern_config, combined_text, health_check, triage_data
                )

                hypothesis = AnalysisHypothesis(
                    id=f"pattern_{pattern_name}",
                    description=self._generate_pattern_description(pattern_name, evidence),
                    confidence=confidence,
                    evidence=evidence,
                    recommended_actions=pattern_config["actions"],
                    supporting_data={
                        "pattern_type": pattern_name,
                        "matched_keywords": self._find_matched_keywords(
                            pattern_config["keywords"], combined_text
                        )
                    }
                )
                hypotheses.append(hypothesis)

        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    def _extract_text_data(self, health_check: Dict[str, Any], triage_data: Dict[str, Any]) -> str:
        """Extract all text data for pattern matching"""
        text_parts = []

        # Health check data
        if health_check.get('error_message'):
            text_parts.append(health_check['error_message'])

        # Triage data
        data_collection = triage_data.get('data_collection', {})

        # Logs
        logs = data_collection.get('logs', {}).get('logs', [])
        for log in logs[:20]:  # Limit to recent logs
            text_parts.append(log.get('message', ''))

        # Network diagnostics
        net_tests = data_collection.get('network_diagnostics', {}).get('tests', {})
        for test_name, test_result in net_tests.items():
            if isinstance(test_result, dict):
                text_parts.append(f"{test_name}: {test_result.get('error', '')}")

        # System metrics
        sys_metrics = data_collection.get('system_metrics', {}).get('system_metrics', {})
        for metric_name, value in sys_metrics.items():
            if isinstance(value, (int, float)) and value > 80:  # High values might indicate issues
                text_parts.append(f"High {metric_name}: {value}")

        return ' '.join(text_parts).lower()

    def _calculate_pattern_confidence(
        self, pattern_config: Dict[str, Any], text: str,
        health_check: Dict[str, Any], triage_data: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a pattern"""
        confidence = 0.0

        # Keyword matching
        keyword_matches = 0
        for keyword in pattern_config["keywords"]:
            if keyword in text:
                keyword_matches += 1

        keyword_confidence = keyword_matches / len(pattern_config["keywords"])
        confidence += keyword_confidence * 0.4

        # Pattern matching
        pattern_matches = 0
        for pattern in pattern_config["evidence_patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                pattern_matches += 1

        pattern_confidence = pattern_matches / len(pattern_config["evidence_patterns"])
        confidence += pattern_confidence * 0.4

        # Context-specific boosts
        context_boost = self._calculate_context_boost(
            pattern_config, health_check, triage_data
        )
        confidence += context_boost

        # Apply pattern-specific confidence boost
        confidence += pattern_config["confidence_boost"]

        return min(confidence, 1.0)  # Cap at 1.0

    def _calculate_context_boost(
        self, pattern_config: Dict[str, Any],
        health_check: Dict[str, Any], triage_data: Dict[str, Any]
    ) -> float:
        """Calculate context-specific confidence boost"""
        boost = 0.0

        pattern_name = None
        for name, config in self.patterns.items():
            if config == pattern_config:
                pattern_name = name
                break

        if not pattern_name:
            return boost

        # Pattern-specific context analysis
        if pattern_name == "database_connection_error":
            # Check if database metrics are available
            db_metrics = triage_data.get('data_collection', {}).get('database_diagnostics', {})
            if db_metrics:
                boost += 0.2

        elif pattern_name == "memory_leak":
            # Check memory usage
            sys_metrics = triage_data.get('data_collection', {}).get('system_metrics', {}).get('system_metrics', {})
            memory_usage = sys_metrics.get('memory_usage_percent', 0)
            if memory_usage > 80:
                boost += 0.3

        elif pattern_name == "network_connectivity":
            # Check network diagnostics
            net_tests = triage_data.get('data_collection', {}).get('network_diagnostics', {}).get('tests', {})
            failed_tests = [name for name, result in net_tests.items()
                          if isinstance(result, dict) and result.get('status') in ['failed', 'timeout']]
            if failed_tests:
                boost += 0.3

        elif pattern_name == "ssl_certificate":
            # Check SSL certificate expiry
            if health_check.get('ssl_expiry_days') and health_check['ssl_expiry_days'] < 30:
                boost += 0.4

        elif pattern_name == "service_overload":
            # Check system metrics for high usage
            sys_metrics = triage_data.get('data_collection', {}).get('system_metrics', {}).get('system_metrics', {})
            cpu_usage = sys_metrics.get('cpu_usage_percent', 0)
            memory_usage = sys_metrics.get('memory_usage_percent', 0)
            if cpu_usage > 80 or memory_usage > 80:
                boost += 0.3

        return boost

    def _extract_pattern_evidence(
        self, pattern_config: Dict[str, Any], text: str,
        health_check: Dict[str, Any], triage_data: Dict[str, Any]
    ) -> List[str]:
        """Extract evidence supporting the pattern"""
        evidence = []

        # Find matching evidence patterns
        for pattern in pattern_config["evidence_patterns"]:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:3]:  # Limit to top 3 matches
                evidence.append(f"Pattern match: {match}")

        # Add context-specific evidence
        if "database" in str(pattern_config).lower():
            db_data = triage_data.get('data_collection', {}).get('database_diagnostics', {})
            if db_data:
                evidence.append("Database diagnostics available")

        if "ssl" in str(pattern_config).lower():
            if health_check.get('ssl_expiry_days'):
                evidence.append(f"SSL certificate expires in {health_check['ssl_expiry_days']} days")

        return evidence[:5]  # Limit to top 5 pieces of evidence

    def _generate_pattern_description(self, pattern_name: str, evidence: List[str]) -> str:
        """Generate human-readable description for the pattern"""
        descriptions = {
            "database_connection_error": "Database connectivity issue detected",
            "memory_leak": "Memory leak or excessive memory usage detected",
            "network_connectivity": "Network connectivity problem identified",
            "ssl_certificate": "SSL/TLS certificate issue detected",
            "service_overload": "Service overload or resource exhaustion detected",
            "deployment_issue": "Recent deployment-related issue detected"
        }

        base_desc = descriptions.get(pattern_name, f"Pattern {pattern_name} detected")
        if evidence:
            base_desc += f" (based on {len(evidence)} evidence points)"

        return base_desc

    def _find_matched_keywords(self, keywords: List[str], text: str) -> List[str]:
        """Find keywords that matched in the text"""
        matched = []
        for keyword in keywords:
            if keyword in text:
                matched.append(keyword)
        return matched

class CorrelationEngine:
    """Correlate current incident with historical data"""

    def __init__(self):
        self.logger = Logger.setup_logger("CorrelationEngine")

    def analyze_correlations(
        self, incident_data: Dict[str, Any],
        historical_incidents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze correlations with historical incidents"""
        try:
            correlations = {
                "similar_incidents": [],
                "patterns_found": [],
                "recommendations": []
            }

            if not historical_incidents:
                return correlations

            # Find similar incidents
            similar_incidents = self._find_similar_incidents(incident_data, historical_incidents)
            correlations["similar_incidents"] = similar_incidents

            # Analyze patterns
            patterns = self._analyze_historical_patterns(similar_incidents)
            correlations["patterns_found"] = patterns

            # Generate recommendations based on history
            recommendations = self._generate_historical_recommendations(similar_incidents)
            correlations["recommendations"] = recommendations

            return correlations

        except Exception as e:
            self.logger.error(f"Correlation analysis failed: {e}")
            return {"error": str(e)}

    def _find_similar_incidents(
        self, incident_data: Dict[str, Any],
        historical_incidents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find incidents similar to current one"""
        similar_incidents = []

        current_endpoint = incident_data.get('endpoint_name', '')
        current_error = incident_data.get('health_check', {}).get('error_message', '').lower()

        for incident in historical_incidents:
            similarity_score = 0.0

            # Check endpoint similarity
            hist_endpoint = incident.get('endpoint_name', '')
            if hist_endpoint == current_endpoint:
                similarity_score += 0.5

            # Check error message similarity
            hist_error = incident.get('health_check', {}).get('error_message', '').lower()
            if hist_error and current_error:
                # Simple text similarity
                common_words = set(current_error.split()) & set(hist_error.split())
                if common_words:
                    similarity_score += len(common_words) * 0.1

            # Check time proximity (recent incidents more relevant)
            hist_time = incident.get('timestamp', '')
            if hist_time:
                try:
                    hist_dt = datetime.fromisoformat(hist_time.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    days_diff = (now - hist_dt).days
                    if days_diff < 7:
                        similarity_score += 0.2
                    elif days_diff < 30:
                        similarity_score += 0.1
                except:
                    pass

            if similarity_score > 0.3:  # Similarity threshold
                similar_incidents.append({
                    "incident": incident,
                    "similarity_score": similarity_score
                })

        # Sort by similarity score
        similar_incidents.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similar_incidents[:5]  # Return top 5 similar incidents

    def _analyze_historical_patterns(self, similar_incidents: List[Dict[str, Any]]) -> List[str]:
        """Analyze patterns from similar incidents"""
        patterns = []

        if not similar_incidents:
            return patterns

        # Common resolutions
        resolutions = []
        for sim_incident in similar_incidents:
            resolution = sim_incident["incident"].get("resolution", "")
            if resolution:
                resolutions.append(resolution)

        # Most common resolutions
        if resolutions:
            from collections import Counter
            common_resolutions = Counter(resolutions).most_common(3)
            for resolution, count in common_resolutions:
                patterns.append(f"Common resolution: {resolution} (used {count} times)")

        # Time patterns
        timestamps = []
        for sim_incident in similar_incidents:
            timestamp = sim_incident["incident"].get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamps.append(dt.hour)  # Hour of day
                except:
                    continue

        if len(timestamps) >= 2:
            avg_hour = statistics.mean(timestamps)
            if 9 <= avg_hour <= 17:  # Business hours
                patterns.append("Incidents tend to occur during business hours")
            else:
                patterns.append("Incidents tend to occur outside business hours")

        return patterns

    def _generate_historical_recommendations(
        self, similar_incidents: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on historical incidents"""
        recommendations = []

        if not similar_incidents:
            return recommendations

        # Most effective resolutions
        resolutions = []
        for sim_incident in similar_incidents:
            resolution = sim_incident["incident"].get("resolution", "")
            effectiveness = sim_incident["incident"].get("resolution_effectiveness", 0.5)
            if resolution and effectiveness > 0.7:
                resolutions.append((resolution, effectiveness))

        if resolutions:
            # Sort by effectiveness
            resolutions.sort(key=lambda x: x[1], reverse=True)
            best_resolution = resolutions[0][0]
            recommendations.append(f"Consider resolution: {best_resolution}")

        # Frequency-based recommendations
        if len(similar_incidents) >= 3:
            recommendations.append("This type of incident occurs frequently - consider permanent fix")

        # Time-to-resolution patterns
        resolution_times = []
        for sim_incident in similar_incidents:
            res_time = sim_incident["incident"].get("resolution_time_minutes")
            if res_time:
                resolution_times.append(res_time)

        if resolution_times:
            avg_resolution_time = statistics.mean(resolution_times)
            if avg_resolution_time > 60:
                recommendations.append("Historical resolution time is high - consider preventive measures")

        return recommendations

class AnalysisAgent:
    """Main analysis agent that performs root cause analysis"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = Logger.setup_logger("AnalysisAgent")
        self.communication = create_agent_communication("analysis")

        # Initialize analysis components
        self.analysis_config = self.config_manager.get_agent_config("analysis")
        self.pattern_matcher = LLMPatternMatcher()
        self.correlation_engine = CorrelationEngine()

        # Historical incidents storage (would be persistent in real implementation)
        self.historical_incidents = []

        # Register message handler
        get_message_queue().register_handler("analysis", self._handle_message)

        self.logger.info("Analysis agent initialized")

    async def _handle_message(self, message: Message):
        """Handle incoming messages"""
        try:
            if message.type == MessageType.ANALYSIS_REQUEST:
                await self._process_analysis_request(message)
            else:
                self.logger.warning(f"Unexpected message type: {message.type}")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def _process_analysis_request(self, message: Message):
        """Process analysis request"""
        try:
            data = message.data
            incident_id = data['incident_id']
            health_check = data['health_check']
            triage_data = data['triage_data']

            self.logger.info(f"Processing analysis request for incident {incident_id}")

            # Perform comprehensive analysis
            analysis_result = await self._perform_root_cause_analysis(
                incident_id, health_check, triage_data
            )

            # Send response
            self.communication.send_response(message, {
                "status": "completed",
                "analysis_result": analysis_result
            })

            # Store incident for historical analysis
            self._store_incident_for_history(incident_id, health_check, triage_data, analysis_result)

            # Trigger notification agent
            await self._trigger_notification_workflow(incident_id, health_check, triage_data, analysis_result)

        except Exception as e:
            self.logger.error(f"Error processing analysis request: {e}")
            # Send error response
            self.communication.send_response(message, {
                "status": "error",
                "error": str(e)
            })

    async def _perform_root_cause_analysis(
        self, incident_id: str, health_check: Dict[str, Any],
        triage_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive root cause analysis"""
        try:
            analysis_start = TimestampUtils.now_utc()

            analysis_result = {
                "incident_id": incident_id,
                "analysis_start_time": TimestampUtils.format_timestamp(analysis_start),
                "hypotheses": [],
                "primary_hypothesis": None,
                "confidence_level": "low",
                "correlations": {},
                "recommendations": [],
                "analysis_summary": ""
            }

            # Step 1: Pattern matching
            pattern_hypotheses = self.pattern_matcher.match_patterns(health_check, triage_data)
            analysis_result["hypotheses"].extend(pattern_hypotheses)

            # Step 2: Correlation analysis
            if self.historical_incidents:
                correlations = self.correlation_engine.analyze_correlations(
                    {"endpoint_name": health_check.get("endpoint_name"), "health_check": health_check},
                    self.historical_incidents
                )
                analysis_result["correlations"] = correlations

                # Generate hypotheses based on correlations
                correlation_hypotheses = self._generate_correlation_hypotheses(correlations)
                analysis_result["hypotheses"].extend(correlation_hypotheses)

            # Step 3: Rank and select primary hypothesis
            if analysis_result["hypotheses"]:
                # Sort by confidence
                analysis_result["hypotheses"].sort(key=lambda h: h.confidence, reverse=True)

                # Select primary hypothesis
                primary = analysis_result["hypotheses"][0]
                analysis_result["primary_hypothesis"] = {
                    "id": primary.id,
                    "description": primary.description,
                    "confidence": primary.confidence,
                    "evidence": primary.evidence,
                    "recommended_actions": primary.recommended_actions
                }

                # Determine confidence level
                confidence = primary.confidence
                if confidence >= 0.8:
                    analysis_result["confidence_level"] = "high"
                elif confidence >= 0.5:
                    analysis_result["confidence_level"] = "medium"
                else:
                    analysis_result["confidence_level"] = "low"

                # Compile recommendations
                analysis_result["recommendations"] = primary.recommended_actions
                if correlations.get("recommendations"):
                    analysis_result["recommendations"].extend(correlations["recommendations"])

            # Step 4: Generate analysis summary
            analysis_result["analysis_summary"] = self._generate_analysis_summary(analysis_result)
            analysis_result["analysis_end_time"] = TimestampUtils.format_timestamp(TimestampUtils.now_utc())

            self.logger.info(f"Root cause analysis completed for incident {incident_id}")
            return analysis_result

        except Exception as e:
            self.logger.error(f"Root cause analysis failed: {e}")
            return {
                "incident_id": incident_id,
                "status": "error",
                "error": str(e)
            }

    def _generate_correlation_hypotheses(self, correlations: Dict[str, Any]) -> List[AnalysisHypothesis]:
        """Generate hypotheses based on correlation analysis"""
        hypotheses = []

        similar_incidents = correlations.get("similar_incidents", [])
        if similar_incidents and len(similar_incidents) >= 2:
            # Frequent incident pattern
            confidence = min(len(similar_incidents) * 0.1, 0.7)
            hypothesis = AnalysisHypothesis(
                id="correlation_frequent_incident",
                description=f"Similar incident pattern detected (occurred {len(similar_incidents)} times historically)",
                confidence=confidence,
                evidence=[f"Found {len(similar_incidents)} similar historical incidents"],
                recommended_actions=[
                    "Investigate root cause of recurring incidents",
                    "Implement preventive measures",
                    "Consider system architecture review"
                ],
                supporting_data={"similar_incidents_count": len(similar_incidents)}
            )
            hypotheses.append(hypothesis)

        return hypotheses

    def _generate_analysis_summary(self, analysis_result: Dict[str, Any]) -> str:
        """Generate human-readable analysis summary"""
        try:
            if analysis_result.get("primary_hypothesis"):
                primary = analysis_result["primary_hypothesis"]
                confidence = analysis_result["confidence_level"]

                summary = f"Primary hypothesis: {primary['description']} (confidence: {confidence})\n"
                summary += f"Supporting evidence: {'; '.join(primary['evidence'][:3])}\n"
                summary += f"Recommended actions: {'; '.join(primary['recommended_actions'][:2])}"

                if analysis_result.get("correlations", {}).get("similar_incidents"):
                    summary += f"\nNote: Similar incidents have occurred in the past"

                return summary
            else:
                return "Insufficient data to determine root cause. Manual investigation required."

        except Exception as e:
            self.logger.error(f"Error generating analysis summary: {e}")
            return "Analysis summary generation failed"

    def _store_incident_for_history(
        self, incident_id: str, health_check: Dict[str, Any],
        triage_data: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Store incident for future correlation analysis"""
        try:
            incident = {
                "incident_id": incident_id,
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "endpoint_name": health_check.get("endpoint_name"),
                "health_check": health_check,
                "triage_summary": triage_data.get("summary", {}),
                "primary_hypothesis": analysis_result.get("primary_hypothesis"),
                "confidence_level": analysis_result.get("confidence_level"),
                "recommendations": analysis_result.get("recommendations", [])
            }

            self.historical_incidents.append(incident)

            # Keep only recent incidents (last 100)
            if len(self.historical_incidents) > 100:
                self.historical_incidents = self.historical_incidents[-100:]

        except Exception as e:
            self.logger.error(f"Error storing incident for history: {e}")

    async def _trigger_notification_workflow(
        self, incident_id: str, health_check: Dict[str, Any],
        triage_data: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Trigger notification agent with analysis results"""
        try:
            # Prepare incident data for notification
            incident_data = {
                "id": incident_id,
                "endpoint_name": health_check.get("endpoint_name"),
                "status": "analyzed",
                "alert_level": self._determine_alert_level(health_check, analysis_result),
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "last_updated": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "health_check_result": health_check,
                "triage_data": triage_data,
                "analysis_result": analysis_result
            }

            correlation_id = self.communication.send_notification_request(incident_data)

            if correlation_id:
                self.logger.info(f"Notification request sent for incident {incident_id}")
            else:
                self.logger.error(f"Failed to send notification request for incident {incident_id}")

        except Exception as e:
            self.logger.error(f"Error triggering notification workflow: {e}")

    def _determine_alert_level(
        self, health_check: Dict[str, Any], analysis_result: Dict[str, Any]
    ) -> str:
        """Determine alert level based on analysis"""
        confidence = analysis_result.get("confidence_level", "low")

        # Upgrade alert level based on confidence and incident type
        if confidence == "high":
            return "critical"
        elif confidence == "medium":
            return "high"
        else:
            return "medium"

    async def start(self):
        """Start the analysis agent"""
        self.logger.info("Analysis agent started - waiting for analysis requests")

        # Keep the agent running and processing messages
        while True:
            try:
                # Process any pending messages
                self.communication.process_messages()
                await asyncio.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("Analysis agent stopped")
                break
            except Exception as e:
                self.logger.error(f"Error in analysis agent main loop: {e}")
                await asyncio.sleep(5)

# Main execution function for Compyle platform
async def main():
    """Main entry point for analysis agent"""
    agent = AnalysisAgent()
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())