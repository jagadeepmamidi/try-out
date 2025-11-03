# DevOps Sentinel

An autonomous monitoring and diagnostics system built on the Compyle platform that drastically reduces Mean Time to Detection (MTTD) for web service outages through intelligent agent collaboration.

## 🎯 Overview

DevOps Sentinel transforms the manual, time-consuming process of identifying and analyzing service failures into a proactive, intelligent workflow. The system uses a team of specialized AI agents to continuously monitor services, automatically diagnose issues, and provide actionable insights to DevOps teams.

## 🤖 Agent Architecture

### System Flow
1. **Monitoring Agent** detects endpoint failure
2. **Triage Agent** collects diagnostic data
3. **Analysis Agent** performs root cause analysis
4. **Notification Agent** delivers actionable insights

### Health Check Configuration
- **Frequency**: Every 1 minute for balanced monitoring
- **Timeout**: 30 seconds per check
- **Failure Threshold**: 2 consecutive failures trigger workflow

## 📁 Project Structure

```
try-out/
├── agents/                          # Specialized monitoring agents
│   ├── monitoring/                  # Continuous health monitoring
│   │   ├── health_check.py         # Main monitoring agent
│   │   └── endpoint_config.json    # Monitoring configuration
│   ├── triage/                     # Diagnostic data collection
│   │   ├── data_collector.py       # Main triage agent
│   │   └── diagnostic_tools.py     # Additional diagnostics
│   ├── analysis/                   # Root cause analysis
│   │   ├── llm_analyzer.py         # Main analysis agent
│   │   └── correlation_engine.py   # Pattern correlation
│   └── notification/               # Alert delivery
│       ├── alert_formatter.py      # Message formatting
│       └── delivery_service.py     # Multi-channel delivery
├── config/                         # System configuration
│   ├── agents.yaml                # Agent settings
│   └── endpoints.yaml             # Monitoring targets
├── deployment/                     # Deployment configuration
│   ├── compyle_workflows.yaml     # Compyle platform config
│   ├── environment_setup.py       # Environment setup
│   ├── docker-compose.yml         # Docker deployment
│   ├── kubernetes/                # K8s manifests
│   └── scripts/                   # Deployment scripts
└── shared/                        # Shared utilities
    ├── messaging.py               # Inter-agent communication
    └── utils.py                   # Common utilities
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Compyle platform access
- Required API keys and configurations

### Installation

1. **Clone and set up the environment**:
   ```bash
   cd deployment
   python environment_setup.py
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.template .env
   # Edit .env with your configurations
   ```

3. **Deploy to Compyle platform**:
   ```bash
   ./deployment/scripts/deploy.sh
   ```

### Required Environment Variables

```bash
# Core Configuration
LOG_LEVEL=INFO
TIMEZONE=UTC

# Monitoring
MONITOR_ENDPOINTS='[{"name": "Example API", "url": "https://api.example.com/health", "method": "GET"}]'

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# AI/Analysis
OPENAI_API_KEY=sk-...

# Optional Integrations
ELASTICSEARCH_ENDPOINT=https://elasticsearch.example.com
PAGERDUTY_INTEGRATION_KEY=...
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

## 📊 Monitoring Configuration

### Adding Endpoints

Edit `config/endpoints.yaml` to add services to monitor:

```yaml
endpoints:
  - name: "User Service"
    url: "http://user-service:8080/health"
    method: "GET"
    timeout: 30
    expected_status: [200]
    response_time_threshold: 2000

  - name: "Payment Gateway"
    url: "https://api.stripe.com/v1/health"
    method: "GET"
    timeout: 30
    expected_status: [200]
    response_time_threshold: 3000
```

### Agent Configuration

Customize agent behavior in `config/agents.yaml`:

```yaml
agents:
  monitoring:
    poll_interval: 60
    failure_threshold: 2
    ssl_warning_days: 30

  triage:
    log_window_minutes: 15
    diagnostic_timeout: 120

  analysis:
    llm_model: "gpt-4"
    confidence_threshold: 0.7

  notification:
    cooldown_period: 15
    delivery_channels: ["slack", "email"]
```

## 🔔 Notification Channels

### Slack Integration

Configure Slack webhook to receive alerts:

1. Create a Slack app and enable incoming webhooks
2. Add webhook URL to environment variables
3. Alerts include interactive buttons and detailed diagnostics

### Email Notifications

SMTP configuration for email alerts:

```yaml
delivery_channels:
  email:
    enabled: true
    smtp_config:
      host: "smtp.gmail.com"
      port: 587
      use_tls: true
      username: "alerts@company.com"
      from_address: "DevOps Sentinel <alerts@company.com>"
```

### PagerDuty Integration

Optional PagerDuty integration for critical alerts:

```yaml
delivery_channels:
  pagerduty:
    enabled: true
    min_alert_level: "high"
    integration_key: "your-integration-key"
```

## 📈 Alert Format

### Slack Message Example

```
🚨 SERVICE ALERT: User Service

📍 Issue: Database connection error detected in logs
🔍 Evidence: Found 15 errors in recent logs; Failed: ping, traceroute
⚡ Impact: Degraded performance for User Service
🛠️ Recommended Actions: Check database server availability; Verify connection string
📊 Confidence: HIGH confidence
⏰ Detected: 2024-01-15T14:30:00Z

🔧 Quick Actions: [View Logs] [Check Metrics] [Acknowledge]
```

### Email Alert Example

Subject: `[HIGH] Service Alert: User Service (Incident INC_20240115_143000)`

The email includes:
- Detailed issue description
- Complete diagnostic data
- Recommended actions
- Links to incident details and monitoring dashboards

## 🔍 Advanced Features

### Root Cause Analysis

The Analysis Agent uses multiple techniques:

- **Pattern Matching**: Matches known failure patterns
- **Historical Correlation**: Compares with past incidents
- **LLM Analysis**: Uses AI to analyze diagnostic data
- **Confidence Scoring**: Provides confidence levels for hypotheses

### Diagnostic Data Collection

The Triage Agent automatically collects:

- **Recent Logs**: 15 minutes of application logs
- **Network Diagnostics**: Ping, traceroute, DNS resolution
- **System Metrics**: CPU, memory, disk usage
- **Service Dependencies**: Docker containers, Kubernetes pods
- **Recent Changes**: Git commits, deployments, config changes

### Intelligent Alerting

- **Cooldown Periods**: Prevents alert fatigue
- **Escalation Rules**: Automatic escalation for unresolved issues
- **Multi-channel Delivery**: Simultaneous Slack and email notifications
- **Context-aware Alerts**: Different formats based on incident severity

## 🛠️ Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AGENT_NAME=monitoring
export OPENAI_API_KEY=your-key

# Run individual agents
python agents/monitoring/health_check.py
python agents/triage/data_collector.py
python agents/analysis/llm_analyzer.py
python agents/notification/delivery_service.py
```

### Testing

```bash
# Run tests (when implemented)
python -m pytest tests/

# Test end-to-end workflow
python deployment/scripts/test_workflow.py
```

### Adding New Agents

1. Create agent directory under `agents/`
2. Implement agent class with async main function
3. Add message handling for inter-agent communication
4. Update deployment configuration
5. Add to workflow configuration

## 📊 Monitoring and Observability

### Agent Health Monitoring

- Agent status and performance metrics
- Message queue monitoring
- Error tracking and alerting
- Resource usage monitoring

### System Metrics

- Incident detection rates
- Mean Time to Detection (MTTD)
- Analysis accuracy
- Alert delivery success rates
- False positive rates

### Logging

Structured JSON logging with:
- Agent-specific log streams
- Correlation IDs for request tracing
- Configurable log levels
- Log retention policies

## 🔧 Configuration Management

### Environment-based Configuration

- Separate configs for development, staging, production
- Environment variable override support
- Configuration validation
- Hot reloading support

### Secret Management

- Encrypted environment variables
- Integration with secret management systems
- Secure credential storage
- Access control and auditing

## 🚨 Troubleshooting

### Common Issues

**Agent not starting**:
- Check environment variables
- Verify configuration files
- Check logs for startup errors

**No alerts being sent**:
- Verify notification channel configurations
- Check network connectivity
- Validate API keys and webhooks

**High false positive rate**:
- Adjust failure thresholds
- Fine-tune confidence levels
- Review endpoint configurations

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python agents/monitoring/health_check.py
```

### Health Checks

Check system status:

```bash
./deployment/scripts/status.sh
```

## 📚 API Reference

### Agent Communication

Messages follow this structure:

```python
{
    "type": "triage_request",
    "incident_id": "INC_20240115_143000",
    "endpoint_name": "User Service",
    "url": "http://user-service:8080/health",
    "timestamp": "2024-01-15T14:30:00Z"
}
```

### Configuration Schema

See individual configuration files for detailed schema documentation.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests and documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: See `/docs` directory
- **Issues**: Create an issue on GitHub
- **Community**: Join our Slack channel
- **Enterprise**: Contact enterprise-support@devops-sentinel.com

---

## 🎉 Success Metrics

DevOps Sentinel is designed to achieve:

- **75% reduction** in Mean Time to Detection (MTTD)
- **<5% false positive rate** for alerts
- **80%+ accuracy** in root cause identification
- **99%+ notification delivery** success rate
- **99.9%+ monitoring system** availability

Built with ❤️ by the DevOps Sentinel team.