import time
from typing import List, Dict, Optional, Set
from app.models.schemas import NetworkInterface
from app.networking.bandwidth_monitor import bandwidth_monitor
import logging

logger = logging.getLogger("multilink.scheduler")

class DynamicScheduler:
    def __init__(self, interfaces: List[NetworkInterface]):
        self.interfaces = {iface.id: iface for iface in interfaces if iface.usable}
        self.failure_counts: Dict[str, int] = {iface.id: 0 for iface in interfaces}
        self.last_failure_time: Dict[str, float] = {iface.id: 0.0 for iface in interfaces}
        # Track chunk-specific failed interfaces: chunk_id -> Set[interface_id]
        self.chunk_failed_interfaces: Dict[str, Set[str]] = {}

    def record_chunk_failure(self, chunk_id: str, interface_id: str):
        if chunk_id not in self.chunk_failed_interfaces:
            self.chunk_failed_interfaces[chunk_id] = set()
        self.chunk_failed_interfaces[chunk_id].add(interface_id)
        self.record_interface_failure(interface_id)

    def record_interface_failure(self, interface_id: str):
        self.failure_counts[interface_id] = self.failure_counts.get(interface_id, 0) + 1
        self.last_failure_time[interface_id] = time.time()
        logger.warning(f"Interface {interface_id} logged failure (count={self.failure_counts[interface_id]})")

    def record_interface_success(self, interface_id: str):
        if interface_id in self.failure_counts and self.failure_counts[interface_id] > 0:
            self.failure_counts[interface_id] = max(0, self.failure_counts[interface_id] - 1)

    def is_interface_healthy(self, interface_id: str) -> bool:
        fail_count = self.failure_counts.get(interface_id, 0)
        if fail_count == 0:
            return True
        # Exponential backoff delay: 2^(fail_count) seconds, capped at 60 seconds
        delay = min(2.0 ** fail_count, 60.0)
        return (time.time() - self.last_failure_time.get(interface_id, 0.0)) >= delay

    def has_healthy_interface(self) -> bool:
        return any(self.is_interface_healthy(if_id) for if_id in self.interfaces)

    def select_best_interface(
        self,
        active_assignments: Dict[str, str],
        candidate_interface_ids: Optional[List[str]] = None,
        chunk_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Dynamically selects the optimal interface for the next chunk:
        1. Filters candidate interfaces by health & enabled status.
        2. Avoids interfaces that already failed this specific chunk.
        3. Considers current throughput (higher throughput gets priority).
        4. Considers current load (interfaces with fewer active chunks get priority).
        """
        pool = [
            if_id for if_id in self.interfaces.keys()
            if (candidate_interface_ids is None or if_id in candidate_interface_ids) and self.is_interface_healthy(if_id)
        ]

        # Filter out interface that previously failed this chunk if alternative candidates exist
        if chunk_id and chunk_id in self.chunk_failed_interfaces:
            avoid_set = self.chunk_failed_interfaces[chunk_id]
            unfailed_pool = [if_id for if_id in pool if if_id not in avoid_set]
            if unfailed_pool:
                pool = unfailed_pool

        if not pool:
            # Fallback to any interface in candidate list
            if candidate_interface_ids:
                pool = [if_id for if_id in candidate_interface_ids if if_id in self.interfaces]
            else:
                pool = list(self.interfaces.keys())

        if not pool:
            return None

        # Count active chunks per interface
        load_map: Dict[str, int] = {if_id: 0 for if_id in pool}
        for c_id, if_id in active_assignments.items():
            if if_id in load_map:
                load_map[if_id] += 1

        # Retrieve measured throughputs
        speeds = bandwidth_monitor.get_all_interface_speeds()

        best_score = -1.0
        best_if = pool[0]

        for if_id in pool:
            speed_mbps = speeds.get(if_id, 0.0) / 1_000_000.0
            load = load_map[if_id]
            # Health penalty factor
            penalty = 1.0 + (0.5 * self.failure_counts.get(if_id, 0))
            score = (speed_mbps + 5.0) / ((load + 1) * penalty)
            if score > best_score:
                best_score = score
                best_if = if_id

        return best_if
