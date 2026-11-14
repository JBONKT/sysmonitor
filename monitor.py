#!/usr/bin/env python3
"""
System Monitor - Comprehensive System Monitoring Solution
Tracks CPU, Memory, Disk Usage, Server Status, and provides Real-time Alerting
"""

import time
import psutil
from datetime import datetime, timedelta
import logging
import threading
import json
import os
import signal
from config import *
from collections import deque

# Setup logging
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.metrics_history = deque(maxlen=100)  # Last 100 readings
        self.alerts = []
        self.running = True
        
    def get_cpu_percent(self):
        """Get current CPU usage percentage"""
        return psutil.cpu_percent(interval=0.1)
    
    def get_cpu_load(self):
        """Get CPU load in percent (0-100)"""
        cpu_count = psutil.cpu_count() or 1
        load_avg = psutil.getloadavg()[0]  # 1-minute load average
        return (load_avg / cpu_count) * 100
    
    def get_memory_info(self):
        """Get memory information"""
        mem = psutil.virtual_memory()
        return {
            'total': mem.total / (1024*1024),  # MB
            'used': mem.used / (1024*1024),  # MB
            'free': mem.free / (1024*1024),  # MB
            'percent': mem.percent,
            'available': mem.available / (1024*1024)  # MB
        }
    
    def get_disk_info(self):
        """Get disk information for all mounted filesystems"""
        disk_info = {}
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info[partition.device] = {
                    'mount': partition.mountpoint,
                    'total': usage.total / (1024*1024),  # MB
                    'used': usage.used / (1024*1024),  # MB
                    'free': usage.free / (1024*1024),  # MB
                    'percent': usage.percent,
                    'available': usage.free / (1024*1024)  # MB
                }
            except Exception:
                pass
        return disk_info
    
    def get_network_io(self):
        """Get network I/O statistics"""
        return psutil.net_io_counters()
    
    def get_system_info(self):
        """Get comprehensive system information"""
        import socket
        try:
            freq = psutil.cpu_freq()
            cpu_freq = freq._asdict() if freq else {}
        except Exception:
            cpu_freq = {}
        return {
            'hostname': socket.gethostname(),
            'uptime': psutil.boot_time(),
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': cpu_freq,
            'memory_total': psutil.virtual_memory().total / (1024*1024),
            'memory_available': psutil.virtual_memory().available / (1024*1024)
        }
    
    def check_alerts(self):
        """Check for threshold violations and generate alerts"""
        alerts = []
        
        # CPU Alert
        cpu_percent = self.get_cpu_percent()
        if cpu_percent >= CPU_THRESHOLD_CRITICAL:
            alerts.append({
                'type': 'CPU_CRITICAL',
                'message': f"CPU usage critical: {cpu_percent:.1f}%",
                'severity': 'critical',
                'timestamp': datetime.now().isoformat(),
                'value': cpu_percent,
                'threshold': CPU_THRESHOLD_CRITICAL
            })
        elif cpu_percent >= CPU_THRESHOLD_WARNING:
            alerts.append({
                'type': 'CPU_WARNING',
                'message': f"CPU usage warning: {cpu_percent:.1f}%",
                'severity': 'warning',
                'timestamp': datetime.now().isoformat(),
                'value': cpu_percent,
                'threshold': CPU_THRESHOLD_WARNING
            })
        
        # Memory Alert
        mem_info = self.get_memory_info()
        if mem_info['percent'] >= MEMORY_THRESHOLD_CRITICAL:
            alerts.append({
                'type': 'MEMORY_CRITICAL',
                'message': f"Memory usage critical: {mem_info['percent']:.1f}%",
                'severity': 'critical',
                'timestamp': datetime.now().isoformat(),
                'value': mem_info['percent'],
                'threshold': MEMORY_THRESHOLD_CRITICAL
            })
        elif mem_info['percent'] >= MEMORY_THRESHOLD_WARNING:
            alerts.append({
                'type': 'MEMORY_WARNING',
                'message': f"Memory usage warning: {mem_info['percent']:.1f}%",
                'severity': 'warning',
                'timestamp': datetime.now().isoformat(),
                'value': mem_info['percent'],
                'threshold': MEMORY_THRESHOLD_WARNING
            })
        
        # Disk Alert
        disk_info = self.get_disk_info()
        for device, usage in disk_info.items():
            if usage['percent'] >= DISK_THRESHOLD_CRITICAL:
                alerts.append({
                    'type': 'DISK_CRITICAL',
                    'message': f"Disk usage critical on {device}: {usage['percent']:.1f}%",
                    'severity': 'critical',
                    'timestamp': datetime.now().isoformat(),
                    'value': usage['percent'],
                    'threshold': DISK_THRESHOLD_CRITICAL,
                    'disk': device,
                    'mount': usage['mount']
                })
            elif usage['percent'] >= DISK_THRESHOLD_WARNING:
                alerts.append({
                    'type': 'DISK_WARNING',
                    'message': f"Disk usage warning on {device}: {usage['percent']:.1f}%",
                    'severity': 'warning',
                    'timestamp': datetime.now().isoformat(),
                    'value': usage['percent'],
                    'threshold': DISK_THRESHOLD_WARNING,
                    'disk': device,
                    'mount': usage['mount']
                })
        
        return alerts
    
    def record_metric(self, metric_name, value):
        """Record a metric for history tracking"""
        self.metrics_history.append({
            'timestamp': datetime.now().isoformat(),
            'metric': metric_name,
            'value': value
        })
    
    def save_metrics_to_file(self):
        """Save current metrics to file"""
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        
        with open(LOG_FILE, 'a') as f:
            for metric in self.metrics_history:
                f.write(json.dumps(metric) + '\n')
    
    def save_alert_to_file(self, alert):
        """Save alert to file"""
        with open(ALERT_LOG_FILE, 'a') as f:
            f.write(json.dumps(alert) + '\n')
    
    def start(self):
        """Start the monitoring loop"""
        logger.info("System Monitor started")
        
        while self.running:
            try:
                # Collect metrics
                cpu_percent = self.get_cpu_percent()
                cpu_load = self.get_cpu_load()
                mem_info = self.get_memory_info()
                disk_info = self.get_disk_info()
                net_io = self.get_network_io()
                system_info = self.get_system_info()
                
                # Record metrics
                self.record_metric('cpu_percent', cpu_percent)
                self.record_metric('cpu_load', cpu_load)
                self.record_metric('memory_percent', mem_info['percent'])
                self.record_metric('memory_total_mb', mem_info['total'])
                self.record_metric('disk_percent_0', disk_info.get('/dev/disk0s1', {}).get('percent', 0))
                self.record_metric('disk_percent_5', disk_info.get('/dev/disk5s1', {}).get('percent', 0))
                self.record_metric('network_rx_bytes', net_io.bytes_recv)
                self.record_metric('network_tx_bytes', net_io.bytes_sent)
                
                # Check for alerts
                alerts = self.check_alerts()
                if alerts:
                    for alert in alerts:
                        self.save_alert_to_file(alert)
                        logger.warning(f"ALERT: {alert['message']}")
                        print(f"\n⚠️  ALERT: {alert['message']}")
                
                # Save metrics periodically
                if self.running and len(self.metrics_history) >= 50:
                    self.save_metrics_to_file()
                
                # Log summary
                if len(self.metrics_history) % 10 == 0:
                    print(f"\n[Monitor] CPU: {cpu_percent:.1f}%, Memory: {mem_info['percent']:.1f}%")
                
                time.sleep(MONITORING_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(MONITORING_INTERVAL)
    
    def stop(self):
        """Stop the monitoring"""
        self.running = False


def main():
    monitor = SystemMonitor()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Received interrupt signal")
        monitor.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == '__main__':
    main()
