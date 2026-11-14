#!/usr/bin/env python3
"""
System Monitor Dashboard - Web Interface for Real-time System Monitoring
"""

import json
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import psutil
import time

app = Flask(__name__)

# Dashboard HTML template
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Monitor Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .header h1 { font-size: 2rem; margin-bottom: 5px; }
        .header p { opacity: 0.8; font-size: 0.9rem; }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.2rem;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding-bottom: 10px;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            color: #fff;
        }
        .metric-unit { font-size: 1rem; opacity: 0.7; }
        .progress-bar {
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            height: 24px;
            margin-top: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 8px;
            transition: width 0.3s ease;
        }
        .fill-green { background: linear-gradient(90deg, #4caf50, #8bc34a); }
        .fill-yellow { background: linear-gradient(90deg, #ffeb3b, #ffc107); }
        .fill-red { background: linear-gradient(90deg, #f44336, #e53935); }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background: #4caf50; box-shadow: 0 0 8px #4caf50; }
        .status-warning { background: #ff9800; box-shadow: 0 0 8px #ff9800; }
        .status-critical { background: #f44336; box-shadow: 0 0 8px #f44336; }
        .refresh-btn {
            background: linear-gradient(90deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 20px;
        }
        .refresh-btn:hover { opacity: 0.9; }
        .alerts { margin-top: 20px; }
        .alert-item {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 5px;
            font-size: 0.9rem;
        }
        .alert-critical { border-left: 3px solid #f44336; }
        .alert-warning { border-left: 3px solid #ff9800; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 System Monitor Dashboard</h1>
        <p>Last updated: {{ last_update|default("Just now") }}</p>
    </div>
    
    <div class="container">
        <div class="metrics-grid">
            <div class="card">
                <h3>CPU Usage</h3>
                <div style="display: flex; align-items: baseline;">
                    <span class="status-indicator" style="background-color: {{ cpu_status_color }};"></span>
                    <span>{{ cpu_percent|default(0) }}</span>
                </div>
                <div class="metric-unit">%</div>
                <div class="progress-bar">
                    <div class="progress-fill {{ cpu_bar_class }}" style="width: {{ cpu_percent|default(0) }}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Memory Usage</h3>
                <div style="display: flex; align-items: baseline;">
                    <span class="status-indicator" style="background-color: {{ mem_status_color }};"></span>
                    <span>{{ memory_percent|default(0) }}</span>
                </div>
                <div class="metric-unit">%</div>
                <div class="progress-bar">
                    <div class="progress-fill {{ mem_bar_class }}" style="width: {{ memory_percent|default(0) }}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Disk Usage</h3>
                <div style="display: flex; align-items: baseline;">
                    <span class="status-indicator" style="background-color: {{ disk_status_color }};"></span>
                    <span>{{ disk_percent|default(0) }}</span>
                </div>
                <div class="metric-unit">%</div>
                <div class="progress-bar">
                    <div class="progress-fill {{ disk_bar_class }}" style="width: {{ disk_percent|default(0) }}%"></div>
                </div>
            </div>
            
            <div class="card">
                <h3>Network I/O</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div>
                        <small style="opacity: 0.7;">Received</small>
                        <div>{{ network_rx|default(0) }}</div>
                    </div>
                    <div>
                        <small style="opacity: 0.7;">Sent</small>
                        <div>{{ network_tx|default(0) }}</div>
                    </div>
                </div>
                <div class="metric-unit">bytes</div>
            </div>
            
            <div class="card">
                <h3>System Info</h3>
                <div style="font-size: 0.9rem; line-height: 1.6;">
                    <p><strong>Hostname:</strong> {{ hostname|default("Unknown") }}</p>
                    <p><strong>Uptime:</strong> {{ uptime|default("Unknown") }}</p>
                    <p><strong>CPU Count:</strong> {{ cpu_count|default(0) }}</p>
                    <p><strong>Boot Time:</strong> {{ boot_time|default("Unknown") }}</p>
                </div>
            </div>
        </div>
        
        <div class="alerts" id="alerts-container">
            <h3 style="color: #667eea; margin-bottom: 10px;">🚨 Recent Alerts</h3>
            {% if alerts %}
                {% for alert in alerts %}
                <div class="alert-item alert-{{ alert.severity }}">
                    <strong>{{ alert.type }}</strong>: {{ alert.message }}
                </div>
                {% endfor %}
            {% else %}
                <p style="opacity: 0.6; font-style: italic;">No recent alerts</p>
            {% endif %}
        </div>
        
        <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Data</button>
    </div>
    
    <script>
        function refreshData() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('cpu_percent').textContent = data.cpu_percent.toFixed(1);
                    document.getElementById('memory_percent').textContent = data.memory_percent.toFixed(1);
                    document.getElementById('disk_percent').textContent = data.disk_percent.toFixed(1);
                    document.getElementById('network_rx').textContent = formatBytes(data.network_rx_bytes);
                    document.getElementById('network_tx').textContent = formatBytes(data.network_tx_bytes);
                    document.getElementById('last_update').textContent = 'Just now';
                    
                    // Update status indicators
                    const cpuColor = data.cpu_percent > 90 ? 'status-critical' : (data.cpu_percent > 70 ? 'status-warning' : 'status-online');
                    const memColor = data.memory_percent > 90 ? 'status-critical' : (data.memory_percent > 70 ? 'status-warning' : 'status-online');
                    const diskColor = data.disk_percent > 90 ? 'status-critical' : (data.disk_percent > 70 ? 'status-warning' : 'status-online');
                    
                    document.querySelector('[style*="cpu_percent"] span').style.backgroundColor = cpuColor;
                    document.querySelector('[style*="memory_percent"] span').style.backgroundColor = memColor;
                    document.querySelector('[style*="disk_percent"] span').style.backgroundColor = diskColor;
                });
        }
        
        function formatBytes(bytes) {
            if (bytes === undefined || bytes === null) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
        }
        
        // Auto-refresh every 5 seconds
        setInterval(refreshData, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML, 
        last_update=datetime.now().strftime('%H:%M:%S'),
        cpu_percent=cpu_percent,
        cpu_status_color=cpu_status,
        cpu_bar_class=cpu_bar_class,
        memory_percent=memory_percent,
        mem_status_color=mem_status,
        mem_bar_class=mem_bar_class,
        disk_percent=disk_percent,
        disk_status_color=disk_status,
        disk_bar_class=disk_bar_class,
        network_rx_bytes=network_rx_bytes,
        network_tx_bytes=network_tx_bytes,
        hostname=hostname,
        uptime=uptime_seconds,
        cpu_count=cpu_count,
        boot_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        alerts=alerts
    )

@app.route('/api/metrics')
def get_metrics():
    global cpu_percent, memory_percent, disk_percent, network_rx_bytes, network_tx_bytes, hostname, uptime_seconds, cpu_count
    # Update values if not already set (on first request)
    if cpu_percent == 0:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
    
    if memory_percent == 0:
        mem_info = psutil.virtual_memory()
        memory_percent = mem_info.percent
    
    if disk_percent == 0:
        try:
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
        except:
            disk_percent = 0
    
    try:
        net_io = psutil.net_io_counters()
        network_rx_bytes = net_io.bytes_recv
        network_tx_bytes = net_io.bytes_sent
    except:
        network_rx_bytes = 0
        network_tx_bytes = 0
    
    try:
        uptime_seconds = datetime.now().timestamp() - psutil.boot_time()
    except:
        uptime_seconds = 0
    
    # Get recent alerts from log file
    alerts = []
    try:
        with open('/Users/johan/sysmonitor/logs/alerts.log', 'r') as f:
            for line in f:
                try:
                    alert = json.loads(line.strip())
                    alerts.append(alert)
                except:
                    pass
    except:
        pass
    
    return jsonify({
        'cpu_percent': cpu_percent,
        'memory_percent': memory_percent,
        'disk_percent': disk_percent,
        'network_rx_bytes': network_rx_bytes,
        'network_tx_bytes': network_tx_bytes,
        'hostname': hostname,
        'uptime_seconds': uptime_seconds,
        'cpu_count': cpu_count,
        'alerts': alerts[-10:]  # Last 10 alerts
    })

if __name__ == '__main__':
    print(f"Starting dashboard on port {DASHBOARD_PORT}...")
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, debug=False)
