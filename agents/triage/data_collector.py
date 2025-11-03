"""
DevOps Sentinel - Triage Agent
Gather comprehensive diagnostic data upon failure detection
"""

import asyncio
import aiohttp
import subprocess
import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import socket

from ..shared.utils import (
    ConfigManager, Logger, TimestampUtils, MessageFormatter
)
from ..shared.messaging import create_agent_communication, Message, MessageType

class LogCollector:
    """Collects and analyzes application logs"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("LogCollector")

    async def collect_logs(self, service_name: str, endpoint_url: str, minutes_back: int = 15) -> Dict[str, Any]:
        """Collect recent logs for the failing service"""
        try:
            log_data = {
                "service_name": service_name,
                "collection_time": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "time_window_minutes": minutes_back,
                "logs": [],
                "error_patterns": [],
                "warning_count": 0,
                "error_count": 0
            }

            # Try multiple log sources
            log_sources = [
                self._collect_from_elasticsearch,
                self._collect_from_splunk,
                self._collect_from_application_api,
                self._collect_from_file_system
            ]

            for source_func in log_sources:
                try:
                    logs = await source_func(service_name, minutes_back)
                    if logs:
                        log_data["logs"].extend(logs)
                        break  # Use first successful source
                except Exception as e:
                    self.logger.debug(f"Log source {source_func.__name__} failed: {e}")
                    continue

            # Analyze collected logs
            if log_data["logs"]:
                log_data.update(self._analyze_logs(log_data["logs"]))

            return log_data

        except Exception as e:
            self.logger.error(f"Failed to collect logs for {service_name}: {e}")
            return {"error": str(e), "service_name": service_name}

    async def _collect_from_elasticsearch(self, service_name: str, minutes_back: int) -> List[Dict[str, Any]]:
        """Collect logs from Elasticsearch/ELK stack"""
        # This would integrate with actual Elasticsearch endpoint
        es_endpoint = self.config.get('elasticsearch_endpoint')
        if not es_endpoint:
            raise Exception("Elasticsearch endpoint not configured")

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"service": service_name}},
                        {"range": {"@timestamp": {"gte": f"now-{minutes_back}m"}}}
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": 1000
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{es_endpoint}/_search", json=query) as response:
                if response.status == 200:
                    data = await response.json()
                    return [hit["_source"] for hit in data["hits"]["hits"]]
                else:
                    raise Exception(f"Elasticsearch query failed: {response.status}")

    async def _collect_from_splunk(self, service_name: str, minutes_back: int) -> List[Dict[str, Any]]:
        """Collect logs from Splunk"""
        # This would integrate with actual Splunk endpoint
        splunk_endpoint = self.config.get('splunk_endpoint')
        if not splunk_endpoint:
            raise Exception("Splunk endpoint not configured")

        query = f"search service={service_name} earliest=-{minutes_back}m | head 1000"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{splunk_endpoint}/services/search/jobs",
                data={"search": query}
            ) as response:
                # Implement actual Splunk API integration
                raise Exception("Splunk integration not implemented")

    async def _collect_from_application_api(self, service_name: str, minutes_back: int) -> List[Dict[str, Any]]:
        """Collect logs from application's log API"""
        # Try to construct log API URL from service endpoint
        log_api_url = self.config.get('log_api_endpoint')
        if not log_api_url:
            raise Exception("Log API endpoint not configured")

        params = {
            "service": service_name,
            "minutes": minutes_back,
            "limit": 1000
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(log_api_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('logs', [])
                else:
                    raise Exception(f"Log API request failed: {response.status}")

    async def _collect_from_file_system(self, service_name: str, minutes_back: int) -> List[Dict[str, Any]]:
        """Collect logs from local file system (fallback)"""
        log_paths = self.config.get('log_paths', [])
        logs = []

        cutoff_time = TimestampUtils.now_utc() - timedelta(minutes=minutes_back)

        for log_path in log_paths:
            try:
                # This is a simplified implementation
                result = subprocess.run(
                    ["tail", "-n", "1000", log_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        try:
                            # Parse log line (simplified)
                            log_entry = {
                                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                                "message": line,
                                "source": log_path,
                                "level": "INFO"
                            }

                            # Try to extract log level
                            if "ERROR" in line.upper():
                                log_entry["level"] = "ERROR"
                            elif "WARN" in line.upper():
                                log_entry["level"] = "WARN"

                            logs.append(log_entry)
                        except Exception:
                            continue

            except Exception as e:
                self.logger.debug(f"Failed to read log file {log_path}: {e}")
                continue

        return logs

    def _analyze_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze collected logs for patterns"""
        error_count = sum(1 for log in logs if log.get('level') == 'ERROR')
        warning_count = sum(1 for log in logs if log.get('level') == 'WARN')

        # Common error patterns
        error_patterns = []
        error_keywords = [
            'connection refused', 'timeout', 'out of memory',
            'database error', 'null pointer', 'stack overflow',
            'authentication failed', 'authorization failed'
        ]

        for log in logs:
            message = log.get('message', '').lower()
            for keyword in error_keywords:
                if keyword in message:
                    error_patterns.append({
                        "pattern": keyword,
                        "timestamp": log.get('timestamp'),
                        "message": log.get('message')[:200]  # Truncate for readability
                    })

        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "error_patterns": error_patterns[:10]  # Limit to top 10 patterns
        }

class NetworkDiagnostics:
    """Perform network diagnostics on failing endpoints"""

    def __init__(self):
        self.logger = Logger.setup_logger("NetworkDiagnostics")

    async def run_diagnostics(self, endpoint_url: str) -> Dict[str, Any]:
        """Run comprehensive network diagnostics"""
        try:
            parsed_url = urlparse(endpoint_url)
            hostname = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)

            diagnostics = {
                "endpoint_url": endpoint_url,
                "hostname": hostname,
                "port": port,
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "tests": {}
            }

            # Run diagnostic tests concurrently
            test_tasks = [
                ("ping", self._test_ping(hostname)),
                ("traceroute", self._test_traceroute(hostname)),
                ("port_connectivity", self._test_port_connectivity(hostname, port)),
                ("dns_resolution", self._test_dns_resolution(hostname)),
                ("ssl_certificate", self._test_ssl_certificate(hostname, port) if port == 443 else None)
            ]

            for test_name, task in test_tasks:
                if task:
                    try:
                        result = await asyncio.wait_for(task, timeout=30)
                        diagnostics["tests"][test_name] = result
                    except asyncio.TimeoutError:
                        diagnostics["tests"][test_name] = {"status": "timeout", "error": "Test timed out"}
                    except Exception as e:
                        diagnostics["tests"][test_name] = {"status": "error", "error": str(e)}

            return diagnostics

        except Exception as e:
            self.logger.error(f"Network diagnostics failed for {endpoint_url}: {e}")
            return {"error": str(e), "endpoint_url": endpoint_url}

    async def _test_ping(self, hostname: str) -> Dict[str, Any]:
        """Test ping connectivity"""
        try:
            # Use system ping command
            process = await asyncio.create_subprocess_exec(
                'ping', '-c', '4', '-W', '10', hostname,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Parse ping output
                output = stdout.decode()
                packet_loss_match = re.search(r'(\d+)% packet loss', output)
                avg_time_match = re.search(r'avg = ([\d.]+)', output)

                return {
                    "status": "success",
                    "packet_loss": int(packet_loss_match.group(1)) if packet_loss_match else None,
                    "average_time_ms": float(avg_time_match.group(1)) if avg_time_match else None,
                    "raw_output": output
                }
            else:
                return {
                    "status": "failed",
                    "error": stderr.decode(),
                    "return_code": process.returncode
                }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _test_traceroute(self, hostname: str) -> Dict[str, Any]:
        """Test traceroute to hostname"""
        try:
            process = await asyncio.create_subprocess_exec(
                'traceroute', '-m', '15', '-w', '5', hostname,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                output = stdout.decode()
                hops = self._parse_traceroute_output(output)

                return {
                    "status": "success",
                    "hops": hops,
                    "total_hops": len(hops),
                    "raw_output": output
                }
            else:
                return {
                    "status": "failed",
                    "error": stderr.decode(),
                    "return_code": process.returncode
                }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _test_port_connectivity(self, hostname: str, port: int) -> Dict[str, Any]:
        """Test TCP port connectivity"""
        try:
            start_time = time.time()

            # Try to connect to the port
            future = asyncio.open_connection(hostname, port)
            reader, writer = await asyncio.wait_for(future, timeout=10)

            connection_time = (time.time() - start_time) * 1000

            writer.close()
            await writer.wait_closed()

            return {
                "status": "success",
                "connection_time_ms": round(connection_time, 2),
                "port_open": True
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "connection_time_ms": 10000,
                "port_open": False
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "port_open": False
            }

    async def _test_dns_resolution(self, hostname: str) -> Dict[str, Any]:
        """Test DNS resolution"""
        try:
            start_time = time.time()

            # Resolve hostname
            loop = asyncio.get_event_loop()
            addresses = await loop.getaddrinfo(hostname, None)
            resolution_time = (time.time() - start_time) * 1000

            ip_addresses = list(set([addr[4][0] for addr in addresses]))

            return {
                "status": "success",
                "ip_addresses": ip_addresses,
                "resolution_time_ms": round(resolution_time, 2)
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    async def _test_ssl_certificate(self, hostname: str, port: int) -> Dict[str, Any]:
        """Test SSL certificate"""
        try:
            import ssl
            import socket

            context = ssl.create_default_context()

            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as secure_sock:
                    cert = secure_sock.getpeercert()

                    # Parse certificate
                    expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                    days_until_expiry = (expiry_date - TimestampUtils.now_utc()).days

                    return {
                        "status": "success",
                        "subject": dict(x[0] for x in cert['subject']),
                        "issuer": dict(x[0] for x in cert['issuer']),
                        "not_after": cert['notAfter'],
                        "days_until_expiry": days_until_expiry,
                        "version": cert['version']
                    }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def _parse_traceroute_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse traceroute output into structured data"""
        hops = []
        lines = output.strip().split('\n')

        for line in lines[1:]:  # Skip first line (traceroute header)
            # Parse each hop line
            hop_match = re.match(r'^\s*(\d+)\s+(.+)', line)
            if hop_match:
                hop_number = int(hop_match.group(1))
                rest = hop_match.group(2)

                # Extract IP addresses and times
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', rest)
                time_matches = re.findall(r'(\d+\.\d+)\s*ms', rest)

                hops.append({
                    "hop": hop_number,
                    "ip_address": ip_match.group(1) if ip_match else None,
                    "times_ms": [float(t) for t in time_matches],
                    "status": "success" if time_matches else "timeout"
                })

        return hops

class SystemMetricsCollector:
    """Collect system metrics for troubleshooting"""

    def __init__(self):
        self.logger = Logger.setup_logger("SystemMetricsCollector")

    async def collect_metrics(self, service_name: str) -> Dict[str, Any]:
        """Collect system metrics for the failing service"""
        try:
            metrics = {
                "service_name": service_name,
                "collection_time": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "system_metrics": {},
                "service_metrics": {}
            }

            # Collect system metrics
            metrics["system_metrics"] = await self._collect_system_metrics()

            # Collect service-specific metrics
            metrics["service_metrics"] = await self._collect_service_metrics(service_name)

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to collect metrics for {service_name}: {e}")
            return {"error": str(e), "service_name": service_name}

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect general system metrics"""
        try:
            # Use system commands to collect metrics
            cpu_usage = await self._get_cpu_usage()
            memory_usage = await self._get_memory_usage()
            disk_usage = await self._get_disk_usage()
            load_average = await self._get_load_average()

            return {
                "cpu_usage_percent": cpu_usage,
                "memory_usage_percent": memory_usage,
                "disk_usage_percent": disk_usage,
                "load_average": load_average
            }

        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {"error": str(e)}

    async def _collect_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Collect metrics specific to the service"""
        try:
            # This would integrate with monitoring systems like Prometheus
            service_metrics = {}

            # Try to get metrics from service's metrics endpoint
            metrics_endpoint = f"http://{service_name}:8080/metrics"

            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(metrics_endpoint, timeout=10) as response:
                        if response.status == 200:
                            metrics_text = await response.text()
                            service_metrics = self._parse_prometheus_metrics(metrics_text)
                except:
                    pass  # Metrics endpoint not available

            return service_metrics

        except Exception as e:
            self.logger.error(f"Failed to collect service metrics: {e}")
            return {"error": str(e)}

    async def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage"""
        try:
            process = await asyncio.create_subprocess_exec(
                'top', '-bn1', '-p', '1',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()
            output = stdout.decode()

            # Parse CPU usage from top output
            cpu_match = re.search(r'%Cpu\(s\):\s+([\d.]+)\s+us', output)
            if cpu_match:
                return float(cpu_match.group(1))

            return 0.0

        except Exception:
            return 0.0

    async def _get_memory_usage(self) -> float:
        """Get memory usage percentage"""
        try:
            process = await asyncio.create_subprocess_exec(
                'free', '-m',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()
            output = stdout.decode()

            # Parse memory usage
            lines = output.strip().split('\n')
            if len(lines) >= 2:
                memory_line = lines[1].split()
                if len(memory_line) >= 3:
                    total = int(memory_line[1])
                    used = int(memory_line[2])
                    return (used / total) * 100

            return 0.0

        except Exception:
            return 0.0

    async def _get_disk_usage(self) -> float:
        """Get disk usage percentage"""
        try:
            process = await asyncio.create_subprocess_exec(
                'df', '-h', '/',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()
            output = stdout.decode()

            # Parse disk usage
            lines = output.strip().split('\n')
            if len(lines) >= 2:
                disk_line = lines[1].split()
                if len(disk_line) >= 5:
                    usage_str = disk_line[4].replace('%', '')
                    return float(usage_str)

            return 0.0

        except Exception:
            return 0.0

    async def _get_load_average(self) -> Dict[str, float]:
        """Get system load average"""
        try:
            process = await asyncio.create_subprocess_exec(
                'uptime',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()
            output = stdout.decode()

            # Parse load average
            load_match = re.search(r'load average: ([\d.]+), ([\d.]+), ([\d.]+)', output)
            if load_match:
                return {
                    "1min": float(load_match.group(1)),
                    "5min": float(load_match.group(2)),
                    "15min": float(load_match.group(3))
                }

            return {"1min": 0.0, "5min": 0.0, "15min": 0.0}

        except Exception:
            return {"1min": 0.0, "5min": 0.0, "15min": 0.0}

    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """Parse Prometheus metrics format"""
        metrics = {}

        for line in metrics_text.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if ' ' in line:
                    metric_name, value = line.split(' ', 1)
                    try:
                        metrics[metric_name] = float(value)
                    except ValueError:
                        continue

        return metrics

class TriageAgent:
    """Main triage agent that orchestrates diagnostic data collection"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.logger = Logger.setup_logger("TriageAgent")
        self.communication = create_agent_communication("triage")

        # Initialize data collectors
        self.triage_config = self.config_manager.get_agent_config("triage")
        self.log_collector = LogCollector(self.triage_config)
        self.network_diagnostics = NetworkDiagnostics()
        self.metrics_collector = SystemMetricsCollector()

        # Register message handler
        get_message_queue().register_handler("triage", self._handle_message)

        self.logger.info("Triage agent initialized")

    async def _handle_message(self, message: Message):
        """Handle incoming messages"""
        try:
            if message.type == MessageType.TRIAGE_REQUEST:
                await self._process_triage_request(message)
            else:
                self.logger.warning(f"Unexpected message type: {message.type}")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def _process_triage_request(self, message: Message):
        """Process triage request and collect diagnostic data"""
        try:
            data = message.data
            incident_id = data['incident_id']
            endpoint_name = data['endpoint_name']
            endpoint_url = data['url']

            self.logger.info(f"Processing triage request for incident {incident_id}")

            # Collect diagnostic data
            triage_data = await self._collect_diagnostic_data(
                incident_id, endpoint_name, endpoint_url
            )

            # Send response
            self.communication.send_response(message, {
                "status": "completed",
                "triage_data": triage_data
            })

            # Trigger analysis agent
            await self._trigger_analysis_workflow(incident_id, triage_data)

        except Exception as e:
            self.logger.error(f"Error processing triage request: {e}")
            # Send error response
            self.communication.send_response(message, {
                "status": "error",
                "error": str(e)
            })

    async def _collect_diagnostic_data(self, incident_id: str, endpoint_name: str, endpoint_url: str) -> Dict[str, Any]:
        """Collect all diagnostic data for the incident"""
        try:
            triage_data = {
                "incident_id": incident_id,
                "endpoint_name": endpoint_name,
                "endpoint_url": endpoint_url,
                "collection_start_time": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "data_collection": {}
            }

            # Run data collection concurrently
            collection_tasks = [
                ("logs", self.log_collector.collect_logs(
                    endpoint_name, endpoint_url,
                    self.triage_config.get('log_window_minutes', 15)
                )),
                ("network_diagnostics", self.network_diagnostics.run_diagnostics(endpoint_url)),
                ("system_metrics", self.metrics_collector.collect_metrics(endpoint_name))
            ]

            # Execute all collection tasks with timeout
            timeout = self.triage_config.get('diagnostic_timeout', 120)
            results = await asyncio.wait_for(
                asyncio.gather(*collection_tasks, return_exceptions=True),
                timeout=timeout
            )

            for i, (data_type, _) in enumerate(collection_tasks):
                result = results[i]
                if isinstance(result, Exception):
                    triage_data["data_collection"][data_type] = {
                        "status": "error",
                        "error": str(result)
                    }
                else:
                    triage_data["data_collection"][data_type] = result

            triage_data["collection_end_time"] = TimestampUtils.format_timestamp(TimestampUtils.now_utc())

            # Generate summary
            triage_data["summary"] = self._generate_triage_summary(triage_data)

            self.logger.info(f"Diagnostic data collection completed for incident {incident_id}")
            return triage_data

        except asyncio.TimeoutError:
            self.logger.error(f"Diagnostic data collection timed out for incident {incident_id}")
            return {
                "incident_id": incident_id,
                "status": "timeout",
                "error": "Data collection timed out"
            }
        except Exception as e:
            self.logger.error(f"Error collecting diagnostic data: {e}")
            return {
                "incident_id": incident_id,
                "status": "error",
                "error": str(e)
            }

    def _generate_triage_summary(self, triage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of collected diagnostic data"""
        try:
            summary = {
                "data_sources_successful": [],
                "data_sources_failed": [],
                "key_findings": [],
                "recommendations": []
            }

            data_collection = triage_data.get("data_collection", {})

            # Analyze each data source
            for data_type, data in data_collection.items():
                if data.get("status") == "error":
                    summary["data_sources_failed"].append(data_type)
                else:
                    summary["data_sources_successful"].append(data_type)

                    # Extract key findings based on data type
                    if data_type == "logs":
                        error_count = data.get("error_count", 0)
                        if error_count > 0:
                            summary["key_findings"].append(f"Found {error_count} errors in recent logs")

                    elif data_type == "network_diagnostics":
                        tests = data.get("tests", {})
                        failed_tests = [name for name, result in tests.items()
                                      if result.get("status") in ["failed", "timeout"]]
                        if failed_tests:
                            summary["key_findings"].append(f"Network tests failed: {', '.join(failed_tests)}")

                    elif data_type == "system_metrics":
                        system_metrics = data.get("system_metrics", {})
                        cpu_usage = system_metrics.get("cpu_usage_percent", 0)
                        memory_usage = system_metrics.get("memory_usage_percent", 0)

                        if cpu_usage > 80:
                            summary["key_findings"].append(f"High CPU usage: {cpu_usage}%")
                        if memory_usage > 80:
                            summary["key_findings"].append(f"High memory usage: {memory_usage}%")

            # Generate recommendations
            if len(summary["data_sources_failed"]) > 0:
                summary["recommendations"].append("Investigate failed data sources for access issues")

            if len(summary["key_findings"]) == 0:
                summary["recommendations"].append("No obvious issues detected in collected data")

            return summary

        except Exception as e:
            self.logger.error(f"Error generating triage summary: {e}")
            return {"error": str(e)}

    async def _trigger_analysis_workflow(self, incident_id: str, triage_data: Dict[str, Any]):
        """Trigger analysis agent to process the collected data"""
        try:
            # This would send message to analysis agent
            correlation_id = self.communication.send_analysis_request(
                incident_id,
                {},  # health check data would be included
                triage_data
            )

            if correlation_id:
                self.logger.info(f"Analysis request sent for incident {incident_id}")
            else:
                self.logger.error(f"Failed to send analysis request for incident {incident_id}")

        except Exception as e:
            self.logger.error(f"Error triggering analysis workflow: {e}")

    async def start(self):
        """Start the triage agent"""
        self.logger.info("Triage agent started - waiting for triage requests")

        # Keep the agent running and processing messages
        while True:
            try:
                # Process any pending messages
                self.communication.process_messages()
                await asyncio.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("Triage agent stopped")
                break
            except Exception as e:
                self.logger.error(f"Error in triage agent main loop: {e}")
                await asyncio.sleep(5)

# Main execution function for Compyle platform
async def main():
    """Main entry point for triage agent"""
    agent = TriageAgent()
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())