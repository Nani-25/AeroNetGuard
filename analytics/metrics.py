"""
AeroNetGuard - Simulation Performance & Protocol Analytics Engine

Computes deterministic analytics from actual NetworkSimulator results,
including framing statistics, CRC integrity metrics, transmission attempts,
Go-Back-N window recovery metrics, routing efficiency, and timeline telemetry.

NOTE: This is a software simulation metrics engine for educational computer networks.
Metrics represent discrete simulation counts and event ratios, not physical hardware throughput.
"""

from typing import Dict, Any, List, Optional


class SimulationMetrics:
    """
    Analyzes simulation outputs produced by NetworkSimulator and derives
    actionable networking telemetry, protocol performance indicators, and event timelines.
    """

    def __init__(self, result: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the analytics engine with an optional simulation result.

        :param result: Dictionary returned by NetworkSimulator.simulate().
        """
        self._raw_result: Optional[Dict[str, Any]] = None
        self._summary: Dict[str, Any] = {}
        self._frame_metrics: List[Dict[str, Any]] = []
        self._protocol_metrics: Dict[str, Any] = {}
        self._crc_metrics: Dict[str, Any] = {}
        self._route_metrics: Dict[str, Any] = {}
        self._timeline: List[Dict[str, Any]] = []

        if result is not None:
            self.analyze(result)
        else:
            self._set_empty_defaults()

    def analyze(self, result: Optional[Dict[str, Any]]) -> "SimulationMetrics":
        """
        Analyze a simulation result dictionary and compute all metric models.

        :param result: Output dictionary from NetworkSimulator.
        :return: self for method chaining.
        """
        if not result or not isinstance(result, dict):
            self._set_empty_defaults()
            return self

        self._raw_result = result
        events = result.get("events", [])
        frames = result.get("frames", [])
        route = result.get("route", [])
        total_frames = result.get("total_frames", len(frames))

        # 1. Route Analysis
        self._route_metrics = {
            "source": result.get("source", ""),
            "destination": result.get("destination", ""),
            "path": list(route),
            "route_cost": result.get("route_cost", 0),
            "hop_count": result.get("hop_count", 0),
        }

        # 2. Transmission & Event Calculations
        tx_events = [e for e in events if e.get("event") == "transmission"]
        tx_attempts = len(tx_events)
        tx_success = sum(1 for e in tx_events if e.get("status") == "success")
        tx_failed = sum(1 for e in tx_events if e.get("status") == "failed")
        tx_success_rate = round(tx_success / tx_attempts, 4) if tx_attempts > 0 else 0.0

        # 3. CRC Verification Calculations
        crc_events = [e for e in events if e.get("event") == "crc_verification"]
        crc_checked = len(crc_events)
        crc_valid = sum(1 for e in crc_events if e.get("is_valid") is True)
        crc_invalid = sum(1 for e in crc_events if e.get("is_valid") is False)
        crc_error_rate = round(crc_invalid / crc_checked, 4) if crc_checked > 0 else 0.0

        self._crc_metrics = {
            "checked": crc_checked,
            "valid": crc_valid,
            "invalid": crc_invalid,
            "error_rate": crc_error_rate,
        }

        # 4. ACK Analytics
        ack_events = [e for e in events if e.get("event") == "acknowledgement"]
        ack_count = len(ack_events)
        ack_seqs = sorted(list({e.get("sequence_number") for e in ack_events if e.get("sequence_number") is not None}))

        # 5. Retransmission Calculations
        retrans_events = [e for e in events if e.get("event") == "retransmission"]
        retrans_count = result.get("retransmission_count", len(retrans_events))

        affected_seqs = {
            e.get("sequence_number")
            for e in retrans_events
            if e.get("sequence_number") is not None
        }
        # Also include frames whose retransmission_count > 0
        for f in frames:
            if f.get("retransmission_count", 0) > 0:
                affected_seqs.add(f.get("sequence_number"))

        affected_frames_count = len(affected_seqs)
        retrans_rate = round(affected_frames_count / total_frames, 4) if total_frames > 0 else 0.0
        avg_per_affected = (
            round(retrans_count / affected_frames_count, 2)
            if affected_frames_count > 0
            else 0.0
        )
        retrans_history = [
            {
                "sequence_number": e.get("sequence_number"),
                "attempt": e.get("attempt", 1),
            }
            for e in retrans_events
        ]

        # 6. Frame Delivery & Efficiency
        delivery_successful = bool(result.get("delivery_successful", False))
        successful_unique_frames = len(ack_seqs) if not delivery_successful else total_frames
        failed_unique_frames = max(0, total_frames - successful_unique_frames)

        # Efficiency: Useful frames delivered / total transmission attempts
        delivery_efficiency = (
            round(successful_unique_frames / tx_attempts, 4)
            if tx_attempts > 0
            else 0.0
        )

        # 7. Simulated Failures
        failure_events = [e for e in events if e.get("event") == "failure"]
        simulated_failures_count = len(failure_events)
        simulated_failure_rate = (
            round(simulated_failures_count / tx_attempts, 4)
            if tx_attempts > 0
            else 0.0
        )

        # 8. Frame Metrics Table Construction
        # Count attempts per sequence number
        attempts_per_seq: Dict[int, int] = {}
        failed_seqs: set = set()
        for e in tx_events:
            s = e.get("sequence_number")
            if s is not None:
                attempts_per_seq[s] = attempts_per_seq.get(s, 0) + 1
                if e.get("status") == "failed":
                    failed_seqs.add(s)

        for e in failure_events:
            s = e.get("sequence_number")
            if s is not None:
                failed_seqs.add(s)

        self._frame_metrics = []
        for f in frames:
            s = f.get("sequence_number", 0)
            is_acked = s in ack_seqs or delivery_successful
            retrans_c = f.get("retransmission_count", 0)
            attempts = attempts_per_seq.get(s, 1 + retrans_c)

            self._frame_metrics.append({
                "sequence_number": s,
                "frame_id": f.get("frame_id", f"F{s}"),
                "packet_id": f.get("packet_id", result.get("packet_id", "")),
                "payload": f.get("payload", ""),
                "status": "acknowledged" if is_acked else f.get("status", "pending"),
                "crc": f.get("crc"),
                "crc_status": f.get("crc_status", "valid" if crc_invalid == 0 else "unknown"),
                "retransmission_count": retrans_c,
                "transmission_attempts": attempts,
                "successful": is_acked,
                "failed": s in failed_seqs,
            })

        # 9. Protocol Performance Metrics
        self._protocol_metrics = {
            "framing": {
                "total_frames": total_frames,
                "strategy": "word_based",
            },
            "crc": {
                "checked": crc_checked,
                "valid": crc_valid,
                "invalid": crc_invalid,
                "error_rate": crc_error_rate,
            },
            "sliding_window": {
                "window_size": result.get("window_size", 3),
            },
            "go_back_n": {
                "retransmissions": retrans_count,
                "affected_frames": affected_frames_count,
                "retransmission_rate": retrans_rate,
                "average_per_affected_frame": avg_per_affected,
            },
        }

        # 10. Event Timeline
        self._timeline = []
        for idx, evt in enumerate(events):
            event_type = evt.get("event", "unknown")
            self._timeline.append({
                "event_index": idx,
                "event_type": event_type,
                "sequence_number": evt.get("sequence_number"),
                "frame_id": evt.get("frame_id"),
                "status": evt.get("status", "success" if event_type != "failure" else "failed"),
                "description": self._format_timeline_description(evt),
                "details": dict(evt),
            })

        # 11. Comprehensive Overall Summary
        self._summary = {
            "simulation": {
                "status": result.get("status", "delivered" if delivery_successful else "failed"),
                "delivery_successful": delivery_successful,
                "total_events": len(events),
            },
            "route": dict(self._route_metrics),
            "frames": {
                "total": total_frames,
                "successful": successful_unique_frames,
                "failed": failed_unique_frames,
            },
            "transmission": {
                "attempts": tx_attempts,
                "successful": tx_success,
                "failed": tx_failed,
                "success_rate": tx_success_rate,
            },
            "crc": dict(self._crc_metrics),
            "acknowledgements": {
                "count": ack_count,
                "acknowledged_sequences": ack_seqs,
            },
            "retransmission": {
                "count": retrans_count,
                "affected_frames": affected_frames_count,
                "rate": retrans_rate,
                "average_per_affected_frame": avg_per_affected,
                "history": retrans_history,
            },
            "simulated_failures": {
                "count": simulated_failures_count,
                "rate": simulated_failure_rate,
                "description": "Simulated fault injection counts, not physical hardware loss",
            },
            "efficiency": {
                "frame_delivery_efficiency": delivery_efficiency,
                "efficiency_definition": "successful_unique_frames / total_transmission_attempts",
            },
            "protocol": dict(self._protocol_metrics),
            # Backward-compatible flat keys for legacy tests & existing UI consumers
            "total_frames": total_frames,
            "successful_frames": successful_unique_frames,
            "failed_frames": failed_unique_frames,
            "total_transmission_attempts": tx_attempts,
            "retransmission_count": retrans_count,
            "retransmissions": retrans_count,
            "affected_frames": affected_frames_count,
            "delivery_successful": delivery_successful,
            "delivery_status": "delivered" if delivery_successful else "failed",
            "route_cost": self._route_metrics["route_cost"],
            "hop_count": self._route_metrics["hop_count"],
            "total_events": len(events),
            "successful_transmissions": tx_success,
            "failed_transmissions": tx_failed,
            "ack_count": ack_count,
            "crc_valid_count": crc_valid,
            "crc_invalid_count": crc_invalid,
        }

        return self

    def get_summary(self) -> Dict[str, Any]:
        """Return the complete structured summary dictionary."""
        return dict(self._summary)

    def get_frame_metrics(self) -> List[Dict[str, Any]]:
        """Return per-frame performance metrics list."""
        return list(self._frame_metrics)

    def get_protocol_metrics(self) -> Dict[str, Any]:
        """Return breakdown of protocol metrics (Framing, CRC, Window, GBN)."""
        return dict(self._protocol_metrics)

    def get_crc_metrics(self) -> Dict[str, Any]:
        """Return CRC calculation and verification statistics."""
        return dict(self._crc_metrics)

    def get_route_metrics(self) -> Dict[str, Any]:
        """Return routing metrics from Dijkstra path calculation."""
        return dict(self._route_metrics)

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Return sequential simulation timeline records."""
        return list(self._timeline)

    def _set_empty_defaults(self) -> None:
        """Initialize empty, safe default values when no simulation result exists."""
        self._raw_result = None
        self._route_metrics = {
            "source": None,
            "destination": None,
            "path": [],
            "route_cost": 0,
            "hop_count": 0,
        }
        self._crc_metrics = {
            "checked": 0,
            "valid": 0,
            "invalid": 0,
            "error_rate": 0.0,
        }
        self._protocol_metrics = {
            "framing": {"total_frames": 0, "strategy": "word_based"},
            "crc": {"checked": 0, "valid": 0, "invalid": 0, "error_rate": 0.0},
            "sliding_window": {"window_size": 0},
            "go_back_n": {
                "retransmissions": 0,
                "affected_frames": 0,
                "retransmission_rate": 0.0,
                "average_per_affected_frame": 0.0,
            },
        }
        self._frame_metrics = []
        self._timeline = []
        self._summary = {
            "simulation": {"status": "idle", "delivery_successful": False, "total_events": 0},
            "route": dict(self._route_metrics),
            "frames": {"total": 0, "successful": 0, "failed": 0},
            "transmission": {"attempts": 0, "successful": 0, "failed": 0, "success_rate": 0.0},
            "crc": dict(self._crc_metrics),
            "acknowledgements": {"count": 0, "acknowledged_sequences": []},
            "retransmission": {
                "count": 0,
                "affected_frames": 0,
                "rate": 0.0,
                "average_per_affected_frame": 0.0,
                "history": [],
            },
            "simulated_failures": {"count": 0, "rate": 0.0, "description": ""},
            "efficiency": {"frame_delivery_efficiency": 0.0, "efficiency_definition": ""},
            "protocol": dict(self._protocol_metrics),
            "total_frames": 0,
            "successful_frames": 0,
            "failed_frames": 0,
            "total_transmission_attempts": 0,
            "retransmission_count": 0,
            "retransmissions": 0,
            "affected_frames": 0,
            "delivery_successful": False,
            "delivery_status": "idle",
            "route_cost": 0,
            "hop_count": 0,
            "total_events": 0,
            "successful_transmissions": 0,
            "failed_transmissions": 0,
            "ack_count": 0,
            "crc_valid_count": 0,
            "crc_invalid_count": 0,
        }

    @staticmethod
    def _format_timeline_description(evt: Dict[str, Any]) -> str:
        """Create a human-readable description for an event log entry."""
        ev_type = evt.get("event", "")
        seq = evt.get("sequence_number")
        if ev_type == "routing":
            route = evt.get("route", [])
            return f"Route calculated: {' ➔ '.join(route)} (Cost: {evt.get('route_cost', 0)})"
        elif ev_type == "packet_created":
            return f"Packet created: '{evt.get('payload', '')}'"
        elif ev_type == "frame_created":
            return f"Frame F{seq} tokenized: '{evt.get('payload', '')}'"
        elif ev_type == "crc_calculated":
            crc_hex = hex(evt.get("crc", 0)).upper() if isinstance(evt.get("crc"), int) else str(evt.get("crc"))
            return f"Frame F{seq} CRC computed: {crc_hex}"
        elif ev_type == "transmission":
            st = evt.get("status", "unknown").upper()
            return f"Frame F{seq} transmission: {st}"
        elif ev_type == "crc_verification":
            v = "VALID" if evt.get("is_valid") else "INVALID"
            return f"Frame F{seq} CRC check: {v}"
        elif ev_type == "failure":
            return f"Frame F{seq} failed ({evt.get('reason', 'dropped')})"
        elif ev_type == "retransmission":
            return f"Frame F{seq} retransmitted (Attempt #{evt.get('attempt', 1)})"
        elif ev_type == "acknowledgement":
            return f"ACK received for Frame F{seq}"
        elif ev_type == "discarded_out_of_order":
            return f"Frame F{seq} discarded (Out of order)"
        elif ev_type == "delivery":
            return "Message delivery complete"
        return f"Event {ev_type}"


# Backward compatibility alias
class NetworkAnalytics:
    """Legacy backward-compatibility facade mapping to SimulationMetrics."""

    @classmethod
    def analyze_simulation(cls, sim_result: Dict[str, Any]) -> Dict[str, Any]:
        """Map legacy analyze_simulation call to SimulationMetrics."""
        metrics = SimulationMetrics(sim_result)
        summary = metrics.get_summary()
        summary["quality_rating"] = "EXCELLENT" if summary.get("delivery_successful") else "DEGRADED"
        return summary
