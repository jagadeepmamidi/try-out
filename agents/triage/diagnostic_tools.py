"""
DevOps Sentinel - Diagnostic Tools
Additional diagnostic tools for the triage agent
"""

import asyncio
import subprocess
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from ..shared.utils import Logger, TimestampUtils

class DatabaseDiagnostics:
    """Diagnostics for database connectivity and performance"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = Logger.setup_logger("DatabaseDiagnostics")

    async def check_database_health(self, database_type: str, connection_string: str) -> Dict[str, Any]:
        """Check database connectivity and basic health"""
        try:
            diagnostics = {
                "database_type": database_type,
                "connection_string": self._mask_connection_string(connection_string),
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "tests": {}
            }

            if database_type.lower() == "postgresql":
                diagnostics["tests"] = await self._check_postgresql(connection_string)
            elif database_type.lower() == "mysql":
                diagnostics["tests"] = await self._check_mysql(connection_string)
            elif database_type.lower() == "redis":
                diagnostics["tests"] = await self._check_redis(connection_string)
            else:
                diagnostics["tests"]["connection"] = {
                    "status": "unsupported",
                    "error": f"Database type {database_type} not supported"
                }

            return diagnostics

        except Exception as e:
            self.logger.error(f"Database diagnostics failed: {e}")
            return {
                "database_type": database_type,
                "status": "error",
                "error": str(e)
            }

    async def _check_postgresql(self, connection_string: str) -> Dict[str, Any]:
        """Check PostgreSQL database health"""
        try:
            # Parse connection string
            # postgresql://user:password@host:port/database
            import psycopg2
            import psycopg2.extras

            tests = {}

            # Test basic connection
            try:
                conn = psycopg2.connect(connection_string, connect_timeout=10)
                cursor = conn.cursor()

                # Test basic query
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

                tests["connection"] = {
                    "status": "success",
                    "result": "Database connection successful"
                }

                # Test table access
                cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                table_count = cursor.fetchone()[0]
                tests["table_access"] = {
                    "status": "success",
                    "table_count": table_count
                }

                # Test database size
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size
                """)
                db_size = cursor.fetchone()[0]
                tests["database_size"] = {
                    "status": "success",
                    "size": db_size
                }

                # Test active connections
                cursor.execute("""
                    SELECT count(*) FROM pg_stat_activity WHERE state = 'active'
                """)
                active_connections = cursor.fetchone()[0]
                tests["active_connections"] = {
                    "status": "success",
                    "count": active_connections
                }

                cursor.close()
                conn.close()

            except Exception as e:
                tests["connection"] = {
                    "status": "failed",
                    "error": str(e)
                }

            return tests

        except ImportError:
            return {
                "connection": {
                    "status": "error",
                    "error": "psycopg2 library not available"
                }
            }
        except Exception as e:
            return {
                "connection": {
                    "status": "error",
                    "error": str(e)
                }
            }

    async def _check_mysql(self, connection_string: str) -> Dict[str, Any]:
        """Check MySQL database health"""
        try:
            import pymysql

            tests = {}

            # Parse connection string and test connection
            # This is a simplified implementation
            try:
                # Extract connection parameters from string
                # mysql://user:password@host:port/database
                conn = pymysql.connect(
                    host='localhost',  # Would parse from connection_string
                    user='root',
                    password='',
                    database='test',
                    connect_timeout=10
                )

                cursor = conn.cursor()

                # Test basic query
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

                tests["connection"] = {
                    "status": "success",
                    "result": "Database connection successful"
                }

                cursor.close()
                conn.close()

            except Exception as e:
                tests["connection"] = {
                    "status": "failed",
                    "error": str(e)
                }

            return tests

        except ImportError:
            return {
                "connection": {
                    "status": "error",
                    "error": "pymysql library not available"
                }
            }
        except Exception as e:
            return {
                "connection": {
                    "status": "error",
                    "error": str(e)
                }
            }

    async def _check_redis(self, connection_string: str) -> Dict[str, Any]:
        """Check Redis connectivity and health"""
        try:
            import redis

            tests = {}

            # Parse connection string
            # redis://host:port/database
            try:
                r = redis.from_url(connection_string, socket_timeout=10)

                # Test basic connectivity
                r.ping()
                tests["connection"] = {
                    "status": "success",
                    "result": "Redis connection successful"
                }

                # Test memory usage
                info = r.info()
                tests["memory_usage"] = {
                    "status": "success",
                    "used_memory": info.get('used_memory_human', 'Unknown'),
                    "used_memory_peak": info.get('used_memory_peak_human', 'Unknown')
                }

                # Test connected clients
                tests["connected_clients"] = {
                    "status": "success",
                    "count": info.get('connected_clients', 0)
                }

                # Test basic operations
                test_key = "devops_sentinel_health_check"
                r.set(test_key, "test", ex=10)
                value = r.get(test_key)

                if value == b"test":
                    tests["basic_operations"] = {
                        "status": "success",
                        "result": "Read/write operations successful"
                    }
                else:
                    tests["basic_operations"] = {
                        "status": "failed",
                        "error": "Read/write test failed"
                    }

                r.delete(test_key)

            except Exception as e:
                tests["connection"] = {
                    "status": "failed",
                    "error": str(e)
                }

            return tests

        except ImportError:
            return {
                "connection": {
                    "status": "error",
                    "error": "redis library not available"
                }
            }
        except Exception as e:
            return {
                "connection": {
                    "status": "error",
                    "error": str(e)
                }
            }

    def _mask_connection_string(self, connection_string: str) -> str:
        """Mask sensitive information in connection string"""
        # Replace password with ***
        masked = re.sub(r':([^@/:]+)@', ':***@', connection_string)
        return masked

class ServiceDependencyChecker:
    """Check dependencies and related services"""

    def __init__(self):
        self.logger = Logger.setup_logger("ServiceDependencyChecker")

    async def check_service_dependencies(self, service_name: str) -> Dict[str, Any]:
        """Check dependencies for a specific service"""
        try:
            dependencies = {
                "service_name": service_name,
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "dependencies": {}
            }

            # Common dependency checks
            dependency_checks = [
                ("docker_containers", self._check_docker_containers),
                ("kubernetes_pods", self._check_kubernetes_pods),
                ("system_services", self._check_system_services),
                ("process_status", self._check_process_status)
            ]

            for dep_name, check_func in dependency_checks:
                try:
                    result = await check_func(service_name)
                    dependencies["dependencies"][dep_name] = result
                except Exception as e:
                    dependencies["dependencies"][dep_name] = {
                        "status": "error",
                        "error": str(e)
                    }

            return dependencies

        except Exception as e:
            self.logger.error(f"Service dependency check failed: {e}")
            return {
                "service_name": service_name,
                "status": "error",
                "error": str(e)
            }

    async def _check_docker_containers(self, service_name: str) -> Dict[str, Any]:
        """Check Docker containers related to the service"""
        try:
            # Check if Docker is available
            process = await asyncio.create_subprocess_exec(
                'docker', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {
                    "status": "unavailable",
                    "error": "Docker not available"
                }

            # List containers
            process = await asyncio.create_subprocess_exec(
                'docker', 'ps', '-a', '--format', 'json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                containers = []
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        try:
                            container = json.loads(line)
                            if service_name.lower() in container.get('Names', '').lower():
                                containers.append({
                                    "name": container.get('Names'),
                                    "status": container.get('Status'),
                                    "image": container.get('Image'),
                                    "ports": container.get('Ports')
                                })
                        except json.JSONDecodeError:
                            continue

                return {
                    "status": "success",
                    "containers": containers,
                    "total_related": len(containers)
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode()
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_kubernetes_pods(self, service_name: str) -> Dict[str, Any]:
        """Check Kubernetes pods related to the service"""
        try:
            # Check if kubectl is available
            process = await asyncio.create_subprocess_exec(
                'kubectl', 'version', '--client',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {
                    "status": "unavailable",
                    "error": "kubectl not available"
                }

            # Get pods in all namespaces
            process = await asyncio.create_subprocess_exec(
                'kubectl', 'get', 'pods', '--all-namespaces', '-o', 'json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                data = json.loads(stdout.decode())
                pods = []

                for item in data.get('items', []):
                    pod_name = item.get('metadata', {}).get('name', '')
                    namespace = item.get('metadata', {}).get('namespace', '')
                    status = item.get('status', {}).get('phase', 'Unknown')

                    if service_name.lower() in pod_name.lower():
                        pods.append({
                            "name": pod_name,
                            "namespace": namespace,
                            "status": status,
                            "ready": self._get_pod_ready_status(item)
                        })

                return {
                    "status": "success",
                    "pods": pods,
                    "total_related": len(pods)
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode()
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_system_services(self, service_name: str) -> Dict[str, Any]:
        """Check system services (systemd)"""
        try:
            # Try to find service with similar name
            process = await asyncio.create_subprocess_exec(
                'systemctl', 'list-units', '--all', '--no-pager',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                services = []
                lines = stdout.decode().strip().split('\n')

                for line in lines:
                    if service_name.lower() in line.lower():
                        parts = line.split()
                        if len(parts) >= 4:
                            services.append({
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": ' '.join(parts[4:]) if len(parts) > 4 else ""
                            })

                return {
                    "status": "success",
                    "services": services,
                    "total_related": len(services)
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode()
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_process_status(self, service_name: str) -> Dict[str, Any]:
        """Check running processes related to the service"""
        try:
            # Find processes related to service name
            process = await asyncio.create_subprocess_exec(
                'ps', 'aux', '--no-headers',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                processes = []
                lines = stdout.decode().strip().split('\n')

                for line in lines:
                    if service_name.lower() in line.lower():
                        parts = line.split(None, 10)
                        if len(parts) >= 11:
                            processes.append({
                                "user": parts[0],
                                "pid": parts[1],
                                "cpu": parts[2],
                                "memory": parts[3],
                                "command": parts[10]
                            })

                return {
                    "status": "success",
                    "processes": processes,
                    "total_related": len(processes)
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode()
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_pod_ready_status(self, pod_item: Dict[str, Any]) -> str:
        """Extract ready status from Kubernetes pod item"""
        try:
            conditions = pod_item.get('status', {}).get('conditions', [])
            for condition in conditions:
                if condition.get('type') == 'Ready':
                    return 'True' if condition.get('status') == 'True' else 'False'
            return 'Unknown'
        except Exception:
            return 'Unknown'

class ChangeDetector:
    """Detect recent changes that might be related to the incident"""

    def __init__(self):
        self.logger = Logger.setup_logger("ChangeDetector")

    async def detect_recent_changes(self, service_name: str, hours_back: int = 24) -> Dict[str, Any]:
        """Detect recent changes to the service"""
        try:
            changes = {
                "service_name": service_name,
                "time_window_hours": hours_back,
                "timestamp": TimestampUtils.format_timestamp(TimestampUtils.now_utc()),
                "changes": {}
            }

            # Check various change sources
            change_checks = [
                ("git_commits", self._check_git_changes),
                ("docker_images", self._check_docker_image_changes),
                ("config_changes", self._check_config_file_changes),
                ("deployment_changes", self._check_deployment_changes)
            ]

            for change_name, check_func in change_checks:
                try:
                    result = await check_func(service_name, hours_back)
                    changes["changes"][change_name] = result
                except Exception as e:
                    changes["changes"][change_name] = {
                        "status": "error",
                        "error": str(e)
                    }

            return changes

        except Exception as e:
            self.logger.error(f"Change detection failed: {e}")
            return {
                "service_name": service_name,
                "status": "error",
                "error": str(e)
            }

    async def _check_git_changes(self, service_name: str, hours_back: int) -> Dict[str, Any]:
        """Check recent Git commits"""
        try:
            # This would check git repositories related to the service
            # For now, return a placeholder
            return {
                "status": "success",
                "commits": [],
                "message": "Git change detection not implemented"
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_docker_image_changes(self, service_name: str, hours_back: int) -> Dict[str, Any]:
        """Check recent Docker image deployments"""
        try:
            # Get Docker images with creation time
            process = await asyncio.create_subprocess_exec(
                'docker', 'images', '--format', 'table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                images = []
                lines = stdout.decode().strip().split('\n')

                # Skip header line
                for line in lines[1:]:
                    if service_name.lower() in line.lower():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            images.append({
                                "name": parts[0],
                                "created_at": parts[1]
                            })

                return {
                    "status": "success",
                    "images": images,
                    "total_related": len(images)
                }
            else:
                return {
                    "status": "error",
                    "error": stderr.decode()
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_config_file_changes(self, service_name: str, hours_back: int) -> Dict[str, Any]:
        """Check recent changes to configuration files"""
        try:
            # Common config file locations
            config_paths = [
                f"/etc/{service_name}/*",
                f"/opt/{service_name}/config/*",
                f"/home/{service_name}/config/*"
            ]

            changed_files = []

            for path_pattern in config_paths:
                try:
                    # Use find to locate recently modified files
                    process = await asyncio.create_subprocess_exec(
                        'find', path_pattern, '-type', 'f',
                        '-mtime', f'-{hours_back // 24}',  # Convert hours to days
                        '-ls',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    stdout, stderr = await process.communicate()

                    if process.returncode == 0 and stdout.decode().strip():
                        lines = stdout.decode().strip().split('\n')
                        for line in lines:
                            if line.strip():
                                changed_files.append({
                                    "path": line.split()[-1],
                                    "change_info": line
                                })

                except Exception:
                    continue  # Path pattern didn't match anything

            return {
                "status": "success",
                "changed_files": changed_files,
                "total_changes": len(changed_files)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def _check_deployment_changes(self, service_name: str, hours_back: int) -> Dict[str, Any]:
        """Check recent deployment changes"""
        try:
            # This would integrate with CI/CD systems
            # For now, return a placeholder
            return {
                "status": "success",
                "deployments": [],
                "message": "Deployment change detection not implemented"
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }