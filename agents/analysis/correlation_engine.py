"""
DevOps Sentinel - Correlation Engine
Advanced correlation analysis for root cause identification
"""

import asyncio
import json
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter

from ..shared.utils import Logger, TimestampUtils

@dataclass
class IncidentPattern:
    """Represents a pattern found across multiple incidents"""
    pattern_id: str
    description: str
    frequency: int
    confidence: float
    contributing_factors: List[str]
    common_resolutions: List[str]
    time_patterns: Dict[str, Any]

class TemporalAnalyzer:
    """Analyze temporal patterns in incidents"""

    def __init__(self):
        self.logger = Logger.setup_logger("TemporalAnalyzer")

    def analyze_time_patterns(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze temporal patterns in incident data"""
        try:
            if not incidents:
                return {}

            patterns = {
                "hourly_distribution": self._analyze_hourly_distribution(incidents),
                "daily_distribution": self._analyze_daily_distribution(incidents),
                "weekly_patterns": self._analyze_weekly_patterns(incidents),
                "monthly_trends": self._analyze_monthly_trends(incidents),
                "seasonal_patterns": self._analyze_seasonal_patterns(incidents),
                "time_to_resolution_patterns": self._analyze_resolution_time_patterns(incidents)
            }

            return patterns

        except Exception as e:
            self.logger.error(f"Temporal analysis failed: {e}")
            return {"error": str(e)}

    def _analyze_hourly_distribution(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze incidents by hour of day"""
        hours = []
        for incident in incidents:
            timestamp = incident.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hours.append(dt.hour)
                except:
                    continue

        if not hours:
            return {"error": "No valid timestamps found"}

        hour_counts = Counter(hours)
        peak_hour = hour_counts.most_common(1)[0] if hour_counts else None

        return {
            "distribution": dict(hour_counts),
            "peak_hour": peak_hour[0] if peak_hour else None,
            "peak_hour_count": peak_hour[1] if peak_hour else 0,
            "average_incidents_per_hour": len(hours) / 24,
            "business_hours_incidents": len([h for h in hours if 9 <= h <= 17]),
            "after_hours_incidents": len([h for h in hours if h < 9 or h > 17])
        }

    def _analyze_daily_distribution(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze incidents by day of week"""
        weekdays = []
        for incident in incidents:
            timestamp = incident.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    weekdays.append(dt.weekday())  # 0 = Monday, 6 = Sunday
                except:
                    continue

        if not weekdays:
            return {"error": "No valid timestamps found"}

        weekday_counts = Counter(weekdays)
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        return {
            "distribution": {weekday_names[day]: count for day, count in weekday_counts.items()},
            "peak_day": weekday_names[weekday_counts.most_common(1)[0][0]] if weekday_counts else None,
            "weekend_incidents": len([d for d in weekdays if d >= 5]),
            "weekday_incidents": len([d for d in weekdays if d < 5])
        }

    def _analyze_weekly_patterns(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze week-over-week patterns"""
        weekly_counts = defaultdict(int)

        for incident in incidents:
            timestamp = incident.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    # Get ISO week number
                    iso_week = dt.isocalendar()[1]
                    year = dt.year
                    week_key = f"{year}-W{iso_week:02d}"
                    weekly_counts[week_key] += 1
                except:
                    continue

        if not weekly_counts:
            return {"error": "No valid timestamps found"}

        weeks = sorted(weekly_counts.keys())
        counts = [weekly_counts[week] for week in weeks]

        return {
            "weekly_counts": dict(weekly_counts),
            "trend": self._calculate_trend(counts),
            "average_per_week": statistics.mean(counts) if counts else 0,
            "max_week": max(weekly_counts.items(), key=lambda x: x[1]) if weekly_counts else None,
            "min_week": min(weekly_counts.items(), key=lambda x: x[1]) if weekly_counts else None
        }

    def _analyze_monthly_trends(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze month-over-month trends"""
        monthly_counts = defaultdict(int)

        for incident in incidents:
            timestamp = incident.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    month_key = f"{dt.year}-{dt.month:02d}"
                    monthly_counts[month_key] += 1
                except:
                    continue

        if not monthly_counts:
            return {"error": "No valid timestamps found"}

        months = sorted(monthly_counts.keys())
        counts = [monthly_counts[month] for month in months]

        return {
            "monthly_counts": dict(monthly_counts),
            "trend": self._calculate_trend(counts),
            "average_per_month": statistics.mean(counts) if counts else 0,
            "growth_rate": self._calculate_growth_rate(counts)
        }

    def _analyze_seasonal_patterns(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze seasonal patterns"""
        seasons = defaultdict(int)

        for incident in incidents:
            timestamp = incident.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    month = dt.month

                    # Determine season (Northern Hemisphere)
                    if month in [12, 1, 2]:
                        season = "Winter"
                    elif month in [3, 4, 5]:
                        season = "Spring"
                    elif month in [6, 7, 8]:
                        season = "Summer"
                    else:
                        season = "Fall"

                    seasons[season] += 1
                except:
                    continue

        return {
            "seasonal_distribution": dict(seasons),
            "peak_season": max(seasons.items(), key=lambda x: x[1])[0] if seasons else None
        }

    def _analyze_resolution_time_patterns(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze time to resolution patterns"""
        resolution_times = []

        for incident in incidents:
            res_time = incident.get('resolution_time_minutes')
            if res_time and isinstance(res_time, (int, float)):
                resolution_times.append(res_time)

        if not resolution_times:
            return {"error": "No resolution time data found"}

        return {
            "average_resolution_time": statistics.mean(resolution_times),
            "median_resolution_time": statistics.median(resolution_times),
            "min_resolution_time": min(resolution_times),
            "max_resolution_time": max(resolution_times),
            "std_deviation": statistics.stdev(resolution_times) if len(resolution_times) > 1 else 0,
            "fast_resolutions": len([t for t in resolution_times if t <= 30]),  # <= 30 minutes
            "slow_resolutions": len([t for t in resolution_times if t > 240])  # > 4 hours
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return "insufficient_data"

        # Simple linear regression to determine trend
        n = len(values)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    def _calculate_growth_rate(self, values: List[float]) -> float:
        """Calculate growth rate between consecutive periods"""
        if len(values) < 2:
            return 0.0

        growth_rates = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                growth_rate = ((values[i] - values[i-1]) / values[i-1]) * 100
                growth_rates.append(growth_rate)

        return statistics.mean(growth_rates) if growth_rates else 0.0

class CausalAnalyzer:
    """Analyze causal relationships between incidents"""

    def __init__(self):
        self.logger = Logger.setup_logger("CausalAnalyzer")

    def analyze_causal_relationships(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze causal relationships in incident data"""
        try:
            relationships = {
                "dependency_chains": self._find_dependency_chains(incidents),
                "common_root_causes": self._find_common_root_causes(incidents),
                "cascade_patterns": self._find_cascade_patterns(incidents),
                "recovery_patterns": self._analyze_recovery_patterns(incidents)
            }

            return relationships

        except Exception as e:
            self.logger.error(f"Causal analysis failed: {e}")
            return {"error": str(e)}

    def _find_dependency_chains(self, incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find dependency chains between services"""
        chains = []

        # Group incidents by time windows
        time_windows = self._group_incidents_by_time_window(incidents, window_minutes=30)

        for window, window_incidents in time_windows.items():
            if len(window_incidents) >= 2:
                # Look for service dependencies
                services = [inc.get('endpoint_name', '') for inc in window_incidents]
                services = [s for s in services if s]  # Remove empty strings

                if len(set(services)) >= 2:
                    # Potential dependency chain
                    chain = {
                        "time_window": window,
                        "services_involved": list(set(services)),
                        "incident_count": len(window_incidents),
                        "potential_chain": True
                    }
                    chains.append(chain)

        return chains

    def _find_common_root_causes(self, incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find common root causes across incidents"""
        root_causes = defaultdict(list)

        for incident in incidents:
            hypothesis = incident.get('primary_hypothesis', {})
            if hypothesis:
                cause = hypothesis.get('description', '')
                if cause:
                    root_causes[cause].append(incident)

        common_causes = []
        for cause, related_incidents in root_causes.items():
            if len(related_incidents) >= 2:
                common_causes.append({
                    "root_cause": cause,
                    "frequency": len(related_incidents),
                    "incidents": [inc.get('incident_id') for inc in related_incidents],
                    "confidence": self._calculate_cause_confidence(related_incidents)
                })

        # Sort by frequency
        common_causes.sort(key=lambda x: x['frequency'], reverse=True)
        return common_causes

    def _find_cascade_patterns(self, incidents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find cascade patterns where one incident triggers others"""
        cascades = []

        # Sort incidents by timestamp
        sorted_incidents = sorted(incidents, key=lambda x: x.get('timestamp', ''))

        for i, incident in enumerate(sorted_incidents):
            following_incidents = []
            current_time = self._parse_timestamp(incident.get('timestamp', ''))

            if current_time:
                # Look for incidents within 30 minutes after this one
                for j in range(i + 1, len(sorted_incidents)):
                    next_incident = sorted_incidents[j]
                    next_time = self._parse_timestamp(next_incident.get('timestamp', ''))

                    if next_time and (next_time - current_time).total_seconds() <= 1800:  # 30 minutes
                        following_incidents.append(next_incident)
                    else:
                        break

                if len(following_incidents) >= 2:
                    cascade = {
                        "trigger_incident": incident.get('incident_id'),
                        "trigger_service": incident.get('endpoint_name'),
                        "cascade_incidents": [inc.get('incident_id') for inc in following_incidents],
                        "cascade_services": list(set([inc.get('endpoint_name') for inc in following_incidents])),
                        "cascade_depth": len(following_incidents)
                    }
                    cascades.append(cascade)

        return cascades

    def _analyze_recovery_patterns(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze recovery patterns and effectiveness"""
        recovery_methods = defaultdict(list)
        recovery_times = []

        for incident in incidents:
            resolution = incident.get('resolution', '')
            res_time = incident.get('resolution_time_minutes')
            effectiveness = incident.get('resolution_effectiveness', 0.5)

            if resolution:
                recovery_methods[resolution].append({
                    "incident_id": incident.get('incident_id'),
                    "resolution_time": res_time,
                    "effectiveness": effectiveness
                })

            if res_time and isinstance(res_time, (int, float)):
                recovery_times.append(res_time)

        # Analyze each recovery method
        method_analysis = {}
        for method, data in recovery_methods.items():
            if len(data) >= 2:
                avg_time = statistics.mean([d['resolution_time'] for d in data if d['resolution_time']])
                avg_effectiveness = statistics.mean([d['effectiveness'] for d in data])
                success_rate = len([d for d in data if d['effectiveness'] > 0.7]) / len(data)

                method_analysis[method] = {
                    "usage_count": len(data),
                    "average_resolution_time": avg_time,
                    "average_effectiveness": avg_effectiveness,
                    "success_rate": success_rate
                }

        return {
            "recovery_methods": method_analysis,
            "overall_stats": {
                "average_resolution_time": statistics.mean(recovery_times) if recovery_times else 0,
                "median_resolution_time": statistics.median(recovery_times) if recovery_times else 0
            }
        }

    def _group_incidents_by_time_window(
        self, incidents: List[Dict[str, Any]], window_minutes: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group incidents into time windows"""
        windows = defaultdict(list)

        for incident in incidents:
            timestamp = self._parse_timestamp(incident.get('timestamp', ''))
            if timestamp:
                # Round down to nearest window boundary
                window_start = timestamp.replace(
                    minute=(timestamp.minute // window_minutes) * window_minutes,
                    second=0,
                    microsecond=0
                )
                window_key = window_start.isoformat()
                windows[window_key].append(incident)

        return dict(windows)

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime object"""
        try:
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except:
            return None

    def _calculate_cause_confidence(self, incidents: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for a root cause"""
        if not incidents:
            return 0.0

        # Base confidence on frequency and consistency
        frequency_factor = min(len(incidents) / 10.0, 1.0)  # Normalize to 0-1

        # Check consistency of confidence levels
        confidence_levels = []
        for incident in incidents:
            hypothesis = incident.get('primary_hypothesis', {})
            if hypothesis:
                conf = hypothesis.get('confidence', 0)
                confidence_levels.append(conf)

        if confidence_levels:
            consistency_factor = 1.0 - statistics.stdev(confidence_levels) if len(confidence_levels) > 1 else 1.0
            avg_confidence = statistics.mean(confidence_levels)
            return (frequency_factor + consistency_factor + avg_confidence) / 3.0

        return frequency_factor

class PredictiveAnalyzer:
    """Predict future incidents based on historical patterns"""

    def __init__(self):
        self.logger = Logger.setup_logger("PredictiveAnalyzer")

    def predict_incident_likelihood(
        self, historical_incidents: List[Dict[str, Any]],
        service_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict likelihood of future incidents"""
        try:
            predictions = {
                "overall_risk_score": self._calculate_overall_risk(historical_incidents, service_context),
                "service_specific_risks": self._calculate_service_risks(historical_incidents, service_context),
                "time_based_predictions": self._predict_time_based_incidents(historical_incidents),
                "preventive_recommendations": self._generate_preventive_recommendations(historical_incidents, service_context)
            }

            return predictions

        except Exception as e:
            self.logger.error(f"Predictive analysis failed: {e}")
            return {"error": str(e)}

    def _calculate_overall_risk(
        self, incidents: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall risk score"""
        if not incidents:
            return {"risk_score": 0.0, "risk_level": "low"}

        # Factor 1: Recent incident frequency
        recent_incidents = [
            inc for inc in incidents
            if self._is_recent_incident(inc.get('timestamp', ''), days=7)
        ]
        frequency_score = min(len(recent_incidents) / 10.0, 1.0)

        # Factor 2: System load (from context)
        load_score = 0.0
        sys_metrics = context.get('system_metrics', {})
        if sys_metrics:
            cpu_usage = sys_metrics.get('cpu_usage_percent', 0) / 100.0
            memory_usage = sys_metrics.get('memory_usage_percent', 0) / 100.0
            load_score = (cpu_usage + memory_usage) / 2.0

        # Factor 3: Historical patterns
        pattern_score = self._analyze_pattern_risk(incidents)

        # Calculate overall risk
        overall_score = (frequency_score * 0.4 + load_score * 0.3 + pattern_score * 0.3)

        risk_level = "low"
        if overall_score > 0.7:
            risk_level = "high"
        elif overall_score > 0.4:
            risk_level = "medium"

        return {
            "risk_score": round(overall_score, 3),
            "risk_level": risk_level,
            "contributing_factors": {
                "frequency": frequency_score,
                "system_load": load_score,
                "historical_patterns": pattern_score
            }
        }

    def _calculate_service_risks(
        self, incidents: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate risk scores for specific services"""
        service_risks = []

        # Group incidents by service
        service_incidents = defaultdict(list)
        for incident in incidents:
            service = incident.get('endpoint_name', '')
            if service:
                service_incidents[service].append(incident)

        for service, service_inc_list in service_incidents.items():
            # Calculate risk for this service
            recent_count = len([
                inc for inc in service_inc_list
                if self._is_recent_incident(inc.get('timestamp', ''), days=7)
            ])

            avg_confidence = 0.0
            confidences = []
            for inc in service_inc_list:
                hypothesis = inc.get('primary_hypothesis', {})
                if hypothesis:
                    confidences.append(hypothesis.get('confidence', 0))

            if confidences:
                avg_confidence = statistics.mean(confidences)

            risk_score = (recent_count / 5.0) * avg_confidence  # Normalize recent incidents

            service_risks.append({
                "service_name": service,
                "risk_score": round(min(risk_score, 1.0), 3),
                "recent_incidents": recent_count,
                "total_incidents": len(service_inc_list),
                "average_confidence": round(avg_confidence, 3)
            })

        # Sort by risk score
        service_risks.sort(key=lambda x: x['risk_score'], reverse=True)
        return service_risks

    def _predict_time_based_incidents(self, incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Predict incidents based on time patterns"""
        temporal_analyzer = TemporalAnalyzer()
        patterns = temporal_analyzer.analyze_time_patterns(incidents)

        predictions = {}

        # Hourly predictions
        hourly_dist = patterns.get('hourly_distribution', {})
        if hourly_dist.get('peak_hour') is not None:
            predictions["peak_risk_hour"] = hourly_dist['peak_hour']
            predictions["peak_risk_hour_count"] = hourly_dist.get('peak_hour_count', 0)

        # Daily predictions
        daily_dist = patterns.get('daily_distribution', {})
        if daily_dist.get('peak_day'):
            predictions["peak_risk_day"] = daily_dist['peak_day']

        # Trend predictions
        monthly_trends = patterns.get('monthly_trends', {})
        if monthly_trends.get('trend'):
            predictions["trend_direction"] = monthly_trends['trend']

        return predictions

    def _generate_preventive_recommendations(
        self, incidents: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[str]:
        """Generate preventive recommendations based on analysis"""
        recommendations = []

        # Analyze common root causes
        causal_analyzer = CausalAnalyzer()
        relationships = causal_analyzer.analyze_causal_relationships(incidents)

        common_causes = relationships.get('common_root_causes', [])
        if common_causes:
            top_cause = common_causes[0]
            recommendations.append(f"Address recurring issue: {top_cause['root_cause']} (occurred {top_cause['frequency']} times)")

        # Check for cascade patterns
        cascades = relationships.get('cascade_patterns', [])
        if cascades:
            recommendations.append("Implement circuit breakers to prevent cascade failures")

        # Analyze recovery patterns
        recovery_patterns = relationships.get('recovery_patterns', {})
        recovery_methods = recovery_patterns.get('recovery_methods', {})
        if recovery_methods:
            # Find most effective recovery method
            effective_methods = [
                (method, data) for method, data in recovery_methods.items()
                if data.get('success_rate', 0) > 0.8
            ]
            if effective_methods:
                best_method = max(effective_methods, key=lambda x: x[1]['success_rate'])
                recommendations.append(f"Consider automated {best_method[0]} for similar incidents")

        # System-specific recommendations
        sys_metrics = context.get('system_metrics', {})
        if sys_metrics:
            cpu_usage = sys_metrics.get('cpu_usage_percent', 0)
            memory_usage = sys_metrics.get('memory_usage_percent', 0)

            if cpu_usage > 80:
                recommendations.append("Monitor CPU usage closely - consider scaling up resources")
            if memory_usage > 80:
                recommendations.append("Monitor memory usage - investigate potential memory leaks")

        return recommendations

    def _is_recent_incident(self, timestamp_str: str, days: int = 7) -> bool:
        """Check if incident is recent"""
        try:
            timestamp = self._parse_timestamp(timestamp_str)
            if timestamp:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                return timestamp > cutoff
        except:
            pass
        return False

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime object"""
        try:
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str)
        except:
            return None

    def _analyze_pattern_risk(self, incidents: List[Dict[str, Any]]) -> float:
        """Analyze risk based on historical patterns"""
        if len(incidents) < 5:
            return 0.1  # Low risk for insufficient data

        # Check for increasing frequency
        temporal_analyzer = TemporalAnalyzer()
        patterns = temporal_analyzer.analyze_time_patterns(incidents)

        monthly_trends = patterns.get('monthly_trends', {})
        trend = monthly_trends.get('trend', 'stable')

        if trend == 'increasing':
            return 0.8
        elif trend == 'decreasing':
            return 0.2
        else:
            return 0.4