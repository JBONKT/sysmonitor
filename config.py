# System Monitor Configuration

# Monitoring interval (seconds)
MONITORING_INTERVAL = 5

# Alert thresholds
CPU_THRESHOLD_CRITICAL = 90
CPU_THRESHOLD_WARNING = 70
MEMORY_THRESHOLD_CRITICAL = 85
MEMORY_THRESHOLD_WARNING = 70
DISK_THRESHOLD_CRITICAL = 90
DISK_THRESHOLD_WARNING = 75

# Log file path
LOG_FILE = "/Users/johan/sysmonitor/logs/monitor.log"

# Alert log file path
ALERT_LOG_FILE = "/Users/johan/sysmonitor/logs/alerts.log"

# Dashboard port
DASHBOARD_PORT = 5001

# Metrics export port (for Prometheus)
METRICS_EXPORT_PORT = 9090

# Enable/disable features
ENABLE_DASHBOARD = True
ENABLE_PROMETHEUS = False
ENABLE_EMAIL_ALERTS = False

# Email configuration (if enabled)
EMAIL_RECIPIENT = None
