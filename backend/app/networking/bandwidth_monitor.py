import time
from collections import deque
from typing import Dict, List, Tuple
from app.models.schemas import SpeedHistoryPoint
import threading

class InterfaceSpeedTracker:
    def __init__(self, window_seconds: float = 3.0):
        self.window_seconds = window_seconds
        self.samples: deque[Tuple[float, int]] = deque()
        self.total_bytes: int = 0
        self.ema_speed_bps: float = 0.0
        self.alpha: float = 0.3  # Smoothing factor

    def record(self, count: int, now: float):
        self.samples.append((now, count))
        self.total_bytes += count
        self._prune(now)

    def _prune(self, now: float):
        cutoff = now - self.window_seconds
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()

    def get_current_speed_bps(self, now: float) -> float:
        self._prune(now)
        if not self.samples or len(self.samples) < 2:
            # Decay if no recent samples
            if self.samples:
                elapsed = now - self.samples[-1][0]
                if elapsed > 1.5:
                    self.ema_speed_bps *= 0.5
            else:
                self.ema_speed_bps = 0.0
            return self.ema_speed_bps

        time_span = self.samples[-1][0] - self.samples[0][0]
        if time_span <= 0:
            return self.ema_speed_bps

        window_bytes = sum(b for _, b in self.samples)
        instant_speed = (window_bytes / time_span) * 8.0  # bits per second
        
        # Apply Exponential Moving Average
        if self.ema_speed_bps == 0.0:
            self.ema_speed_bps = instant_speed
        else:
            self.ema_speed_bps = self.alpha * instant_speed + (1 - self.alpha) * self.ema_speed_bps
            
        return self.ema_speed_bps

class BandwidthMonitor:
    def __init__(self, history_max_points: int = 60):
        self.trackers: Dict[str, InterfaceSpeedTracker] = {}
        self.history: deque[SpeedHistoryPoint] = deque(maxlen=history_max_points)
        self.lock = threading.Lock()
        self.last_history_tick = 0.0

    def record_bytes(self, interface_id: str, count: int):
        now = time.time()
        with self.lock:
            if interface_id not in self.trackers:
                self.trackers[interface_id] = InterfaceSpeedTracker()
            self.trackers[interface_id].record(count, now)

    def get_interface_speed(self, interface_id: str) -> float:
        now = time.time()
        with self.lock:
            if interface_id in self.trackers:
                return self.trackers[interface_id].get_current_speed_bps(now)
            return 0.0

    def get_all_interface_speeds(self) -> Dict[str, float]:
        now = time.time()
        with self.lock:
            return {
                if_id: tracker.get_current_speed_bps(now)
                for if_id, tracker in self.trackers.items()
            }

    def get_combined_speed(self) -> float:
        speeds = self.get_all_interface_speeds()
        return sum(speeds.values())

    def tick_history(self) -> SpeedHistoryPoint:
        """Called every second to record a point for the live speed graph."""
        now = time.time()
        speeds = self.get_all_interface_speeds()
        combined = sum(speeds.values())
        point = SpeedHistoryPoint(
            timestamp=now,
            combined_bps=combined,
            interfaces=speeds
        )
        with self.lock:
            self.history.append(point)
            self.last_history_tick = now
        return point

    def get_history(self) -> List[SpeedHistoryPoint]:
        with self.lock:
            return list(self.history)

bandwidth_monitor = BandwidthMonitor()
