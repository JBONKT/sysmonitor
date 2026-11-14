#!/bin/bash
# System Monitor Startup Script

echo "🚀 Starting System Monitor..."
echo "=========================================="

# Create logs directory if it doesn't exist
mkdir -p /Users/johan/sysmonitor/logs

# Start the monitoring daemon
cd /Users/johan/sysmonitor
python3 monitor.py &

MONITOR_PID=$!
echo "Monitor daemon started with PID: $MONITOR_PID"

# Start the web dashboard in a new terminal
echo ""
echo "📊 Dashboard available at: http://localhost:${DASHBOARD_PORT}"
echo "Press Ctrl+C to stop the dashboard"

# Keep this script running
wait -n
