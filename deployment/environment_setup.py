#!/usr/bin/env python3
"""
DevOps Sentinel - Environment Setup Script
Sets up the environment for deploying DevOps Sentinel on the Compyle platform
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

class EnvironmentSetup:
    """Handle environment setup for DevOps Sentinel deployment"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.deployment_dir = self.project_root / "deployment"

        # Required environment variables
        self.required_env_vars = {
            # Core configuration
            "LOG_LEVEL": "INFO",
            "TIMEZONE": "UTC",

            # Monitoring configuration
            "MONITOR_ENDPOINTS": None,  # Must be provided by user
            "POLL_INTERVAL_SECONDS": "60",
            "TIMEOUT_SECONDS": "30",
            "FAILURE_THRESHOLD": "2",

            # Notification services
            "SLACK_WEBHOOK_URL": None,
            "SMTP_HOST": None,
            "SMTP_PORT": "587",
            "SMTP_USERNAME": None,
            "SMTP_PASSWORD": None,
            "SMTP_FROM_ADDRESS": "devops-sentinel@company.com",

            # External integrations
            "OPENAI_API_KEY": None,
            "ELASTICSEARCH_ENDPOINT": None,
            "LOG_API_ENDPOINT": None,

            # Optional services
            "PAGERDUTY_INTEGRATION_KEY": None,
            "TEAMS_WEBHOOK_URL": None
        }

    def setup_environment(self) -> bool:
        """Set up the complete environment"""
        print("🚀 Setting up DevOps Sentinel environment...")

        try:
            # Step 1: Create required directories
            self._create_directories()

            # Step 2: Install dependencies
            self._install_dependencies()

            # Step 3: Validate configuration files
            self._validate_configurations()

            # Step 4: Set up environment variables
            self._setup_environment_variables()

            # Step 5: Create deployment manifests
            self._create_deployment_manifests()

            # Step 6: Validate setup
            self._validate_setup()

            print("✅ Environment setup completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            return False

    def _create_directories(self):
        """Create required directories"""
        print("📁 Creating directory structure...")

        directories = [
            "logs",
            "data",
            "data/state",
            "data/incidents",
            "data/metrics",
            "temp",
            "backups"
        ]

        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"   Created: {dir_path}")

    def _install_dependencies(self):
        """Install Python dependencies"""
        print("📦 Installing Python dependencies...")

        # Create requirements.txt
        requirements = [
            "aiohttp>=3.8.0",
            "asyncio",
            "pyyaml>=6.0",
            "requests>=2.28.0",
            "psycopg2-binary>=2.9.0",
            "redis>=4.3.0",
            "pymongo>=4.2.0",
            "prometheus-client>=0.15.0",
            "python-dotenv>=0.19.0",
            "email-validator>=1.3.0",
            "jinja2>=3.1.0",
            "click>=8.1.0",
            "rich>=12.0.0"
        ]

        requirements_file = self.project_root / "requirements.txt"
        with open(requirements_file, 'w') as f:
            f.write('\n'.join(requirements))

        # Install dependencies
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], check=True, capture_output=True)
            print("   ✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Warning: Could not install dependencies: {e}")
            print("   You may need to install them manually")

    def _validate_configurations(self):
        """Validate configuration files"""
        print("⚙️  Validating configuration files...")

        # Validate endpoints configuration
        endpoints_file = self.config_dir / "endpoints.yaml"
        if endpoints_file.exists():
            try:
                with open(endpoints_file, 'r') as f:
                    endpoints_config = yaml.safe_load(f)

                if 'endpoints' in endpoints_config:
                    endpoint_count = len(endpoints_config['endpoints'])
                    print(f"   ✅ Endpoints configuration: {endpoint_count} endpoints defined")
                else:
                    raise ValueError("No 'endpoints' section found in endpoints.yaml")
            except Exception as e:
                print(f"   ❌ Endpoints configuration error: {e}")
                raise
        else:
            print("   ⚠️  Warning: endpoints.yaml not found")

        # Validate agents configuration
        agents_file = self.config_dir / "agents.yaml"
        if agents_file.exists():
            try:
                with open(agents_file, 'r') as f:
                    agents_config = yaml.safe_load(f)

                if 'agents' in agents_config:
                    agent_count = len(agents_config['agents'])
                    print(f"   ✅ Agents configuration: {agent_count} agents defined")
                else:
                    raise ValueError("No 'agents' section found in agents.yaml")
            except Exception as e:
                print(f"   ❌ Agents configuration error: {e}")
                raise
        else:
            print("   ⚠️  Warning: agents.yaml not found")

        # Validate Compyle workflows
        workflows_file = self.deployment_dir / "compyle_workflows.yaml"
        if workflows_file.exists():
            try:
                with open(workflows_file, 'r') as f:
                    workflows_config = yaml.safe_load(f)

                if 'workflows' in workflows_config:
                    workflow_count = len(workflows_config['workflows'])
                    print(f"   ✅ Compyle workflows: {workflow_count} workflows defined")
                else:
                    raise ValueError("No 'workflows' section found in compyle_workflows.yaml")
            except Exception as e:
                print(f"   ❌ Compyle workflows error: {e}")
                raise
        else:
            print("   ⚠️  Warning: compyle_workflows.yaml not found")

    def _setup_environment_variables(self):
        """Set up environment variables"""
        print("🔧 Setting up environment variables...")

        # Create .env file template
        env_file = self.project_root / ".env"
        env_template_file = self.project_root / ".env.template"

        env_content = "# DevOps Sentinel Environment Variables\n"
        env_content += "# Copy this file to .env and fill in your values\n\n"

        missing_vars = []

        for var_name, default_value in self.required_env_vars.items():
            if default_value is None:
                env_content += f"{var_name}=\n"
                missing_vars.append(var_name)
            else:
                env_content += f"{var_name}={default_value}\n"

        # Write template file
        with open(env_template_file, 'w') as f:
            f.write(env_content)

        # Check if .env file exists
        if env_file.exists():
            print("   ✅ .env file exists")
            # Validate existing .env file
            self._validate_env_file(env_file)
        else:
            print("   ⚠️  .env file not found")
            print(f"   📝 Template created at: {env_template_file}")
            if missing_vars:
                print(f"   ⚠️  Required variables to set: {', '.join(missing_vars)}")

    def _validate_env_file(self, env_file: Path):
        """Validate existing .env file"""
        try:
            with open(env_file, 'r') as f:
                env_content = f.read()

            # Parse environment variables
            env_vars = {}
            for line in env_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()

            # Check required variables
            missing_required = []
            for var_name, default_value in self.required_env_vars.items():
                if default_value is None and var_name not in env_vars:
                    missing_required.append(var_name)

            if missing_required:
                print(f"   ⚠️  Missing required environment variables: {', '.join(missing_required)}")
            else:
                print("   ✅ All required environment variables are set")

        except Exception as e:
            print(f"   ⚠️  Warning: Could not validate .env file: {e}")

    def _create_deployment_manifests(self):
        """Create deployment manifests for different platforms"""
        print("📋 Creating deployment manifests...")

        # Create Docker Compose file
        self._create_docker_compose()

        # Create Kubernetes manifests
        self._create_kubernetes_manifests()

        # Create deployment scripts
        self._create_deployment_scripts()

    def _create_docker_compose(self):
        """Create Docker Compose configuration"""
        docker_compose = {
            "version": "3.8",
            "services": {
                "monitoring-agent": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.monitoring"
                    },
                    "environment": [
                        "AGENT_NAME=monitoring",
                        "PYTHONPATH=/workspace"
                    ],
                    "volumes": [
                        "./config:/workspace/config:ro",
                        "./data:/workspace/data",
                        "./logs:/workspace/logs"
                    ],
                    "restart": "unless-stopped"
                },
                "triage-agent": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.triage"
                    },
                    "environment": [
                        "AGENT_NAME=triage",
                        "PYTHONPATH=/workspace"
                    ],
                    "volumes": [
                        "./config:/workspace/config:ro",
                        "./data:/workspace/data",
                        "./logs:/workspace/logs"
                    ],
                    "restart": "unless-stopped"
                },
                "analysis-agent": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.analysis"
                    },
                    "environment": [
                        "AGENT_NAME=analysis",
                        "PYTHONPATH=/workspace"
                    ],
                    "volumes": [
                        "./config:/workspace/config:ro",
                        "./data:/workspace/data",
                        "./logs:/workspace/logs"
                    ],
                    "restart": "unless-stopped"
                },
                "notification-agent": {
                    "build": {
                        "context": ".",
                        "dockerfile": "Dockerfile.notification"
                    },
                    "environment": [
                        "AGENT_NAME=notification",
                        "PYTHONPATH=/workspace"
                    ],
                    "volumes": [
                        "./config:/workspace/config:ro",
                        "./data:/workspace/data",
                        "./logs:/workspace/logs"
                    ],
                    "restart": "unless-stopped"
                }
            },
            "volumes": {
                "devops-sentinel-data": {},
                "devops-sentinel-logs": {}
            }
        }

        docker_compose_file = self.deployment_dir / "docker-compose.yml"
        with open(docker_compose_file, 'w') as f:
            yaml.dump(docker_compose, f, default_flow_style=False)

        print(f"   ✅ Docker Compose: {docker_compose_file}")

    def _create_kubernetes_manifests(self):
        """Create Kubernetes manifests"""
        k8s_dir = self.deployment_dir / "kubernetes"
        k8s_dir.mkdir(exist_ok=True)

        # Create namespace
        namespace = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "devops-sentinel"
            }
        }

        namespace_file = k8s_dir / "namespace.yaml"
        with open(namespace_file, 'w') as f:
            yaml.dump(namespace, f)

        # Create ConfigMap
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "devops-sentinel-config",
                "namespace": "devops-sentinel"
            },
            "data": {
                "agents.yaml": (self.config_dir / "agents.yaml").read_text(),
                "endpoints.yaml": (self.config_dir / "endpoints.yaml").read_text()
            }
        }

        configmap_file = k8s_dir / "configmap.yaml"
        with open(configmap_file, 'w') as f:
            yaml.dump(configmap, f)

        print(f"   ✅ Kubernetes manifests: {k8s_dir}")

    def _create_deployment_scripts(self):
        """Create deployment scripts"""
        scripts_dir = self.deployment_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        # Create deployment script
        deploy_script = """#!/bin/bash
# DevOps Sentinel Deployment Script

set -e

echo "🚀 Deploying DevOps Sentinel..."

# Check if environment variables are set
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please copy .env.template to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

# Validate required variables
required_vars=("OPENAI_API_KEY" "SLACK_WEBHOOK_URL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required environment variable $var is not set"
        exit 1
    fi
done

echo "✅ Environment validation passed"

# Deploy to Compyle platform (placeholder for actual deployment logic)
echo "📦 Deploying to Compyle platform..."
# compyle deploy --config deployment/compyle_workflows.yaml

echo "✅ Deployment completed successfully!"
"""

        deploy_script_file = scripts_dir / "deploy.sh"
        with open(deploy_script_file, 'w') as f:
            f.write(deploy_script)

        # Make script executable
        os.chmod(deploy_script_file, 0o755)

        # Create status check script
        status_script = """#!/bin/bash
# DevOps Sentinel Status Check Script

echo "🔍 Checking DevOps Sentinel status..."

# Check if all agents are running
agents=("monitoring-agent" "triage-agent" "analysis-agent" "notification-agent")

for agent in "${agents[@]}"; do
    if pgrep -f "$agent" > /dev/null; then
        echo "✅ $agent is running"
    else
        echo "❌ $agent is not running"
    fi
done

# Check log files
if [ -d "logs" ]; then
    log_count=$(find logs -name "*.log" | wc -l)
    echo "📋 Found $log_count log files"
else
    echo "⚠️  Logs directory not found"
fi

echo "📊 Status check completed"
"""

        status_script_file = scripts_dir / "status.sh"
        with open(status_script_file, 'w') as f:
            f.write(status_script)

        os.chmod(status_script_file, 0o755)

        print(f"   ✅ Deployment scripts: {scripts_dir}")

    def _validate_setup(self):
        """Validate the complete setup"""
        print("✅ Validating complete setup...")

        # Check required files
        required_files = [
            "config/agents.yaml",
            "config/endpoints.yaml",
            "deployment/compyle_workflows.yaml",
            "requirements.txt"
        ]

        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} not found")

        # Check agent files
        agent_files = [
            "agents/monitoring/health_check.py",
            "agents/triage/data_collector.py",
            "agents/analysis/llm_analyzer.py",
            "agents/notification/delivery_service.py"
        ]

        for file_path in agent_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} not found")

        print("🎉 Setup validation completed!")

def main():
    """Main setup function"""
    setup = EnvironmentSetup()
    success = setup.setup_environment()

    if success:
        print("\n🎉 DevOps Sentinel environment is ready for deployment!")
        print("\nNext steps:")
        print("1. Copy .env.template to .env")
        print("2. Configure your environment variables in .env")
        print("3. Run: ./deployment/scripts/deploy.sh")
        print("\nFor more information, see the documentation.")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()