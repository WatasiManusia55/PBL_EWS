# system_monitor.py
import psutil

def get_system_metrics():
    """Mendapatkan metrik sistem: CPU, Memory, Disk, Load Avg, Pi Temperature"""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)

        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)

        load_avg = psutil.getloadavg()

        temp_celsius = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_celsius = float(f.read().strip()) / 1000.0
        except:
            pass

        return {
            "cpu_percent":          round(cpu_percent, 1),
            "memory_percent":       round(memory_percent, 1),
            "memory_used_mb":       round(memory_used_mb, 1),
            "memory_total_mb":      round(memory_total_mb, 1),
            "disk_percent":         round(disk_percent, 1),
            "disk_used_gb":         round(disk_used_gb, 1),
            "disk_total_gb":        round(disk_total_gb, 1),
            "load_avg_1min":        round(load_avg[0], 2),
            "load_avg_5min":        round(load_avg[1], 2),
            "load_avg_15min":       round(load_avg[2], 2),
            "temperature_celsius":  temp_celsius
        }
    except Exception as e:
        print(f"⚠️ Error getting system metrics: {e}")
        return {
            "cpu_percent": 0, "memory_percent": 0,
            "memory_used_mb": 0, "memory_total_mb": 0,
            "disk_percent": 0, "disk_used_gb": 0, "disk_total_gb": 0,
            "load_avg_1min": 0, "load_avg_5min": 0, "load_avg_15min": 0,
            "temperature_celsius": None
        }