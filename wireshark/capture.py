"""
AeroNetGuard - Wireshark / PCAP Packet Capture & Traffic Analysis Module

Provides deterministic conversion of discrete simulation events into standard PCAP files
encapsulating Ethernet/IPv4/UDP packets for analysis in Wireshark or Scapy.

IMPORTANT:
This is a software simulation traffic generation layer for educational networking.
Packets are synthetic representations of simulation events and do NOT interface with
real airport hardware, raw sockets, or physical network interfaces.
"""

import os
import re
import struct
import time
import logging
from typing import List, Dict, Any, Optional

# Suppress Scapy runtime warnings on Windows (e.g. absence of libpcap/winpcap)
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

try:
    from scapy.all import Ether, IP, UDP, Raw, wrpcap, rdpcap
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


# Centralized deterministic IP address mapping for airport nodes.
# NOTE: These are synthetic simulation addresses, not real airport network IPs.
NODE_IP_MAP: Dict[str, str] = {
    "Control Tower": "10.0.0.1",
    "Check-in": "10.0.0.2",
    "Security": "10.0.0.3",
    "Baggage": "10.0.0.4",
    "Emergency Services": "10.0.0.5",
}

# Centralized deterministic MAC address mapping for airport nodes (locally administered range)
NODE_MAC_MAP: Dict[str, str] = {
    "Control Tower": "02:00:00:00:00:01",
    "Check-in": "02:00:00:00:00:02",
    "Security": "02:00:00:00:00:03",
    "Baggage": "02:00:00:00:00:04",
    "Emergency Services": "02:00:00:00:00:05",
}

DEFAULT_SIM_IP = "10.0.0.254"
DEFAULT_SIM_MAC = "02:00:00:00:00:fe"
DEFAULT_UDP_PORT = 5001
BASE_SIM_TIMESTAMP = 1700000000.0  # Epoch base for deterministic simulation ordering


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize and validate user-supplied PCAP filename to prevent path traversal.

    :param filename: Filename provided by user or API caller.
    :return: Sanitized safe filename ending with .pcap.
    """
    if not filename or not isinstance(filename, str):
        return "aeronetguard_capture.pcap"

    # Remove any directory path separators
    clean_name = os.path.basename(filename.strip())

    # Keep only safe alphanumeric characters, dashes, underscores, and dots
    clean_name = re.sub(r"[^a-zA-Z0-9_\.-]", "", clean_name)

    # Prevent hidden files or leading periods
    clean_name = clean_name.lstrip(".")

    if not clean_name:
        clean_name = "aeronetguard_capture"

    if not clean_name.lower().endswith(".pcap"):
        clean_name += ".pcap"

    return clean_name


class SimulationCapture:
    """
    Captures discrete simulation events from NetworkSimulator and translates them
    into structured capture records and Wireshark-compatible PCAP network packets.
    """

    def __init__(self) -> None:
        """Initialize empty simulation capture buffer."""
        self.simulation_result: Optional[Dict[str, Any]] = None
        self.packets: List[Dict[str, Any]] = []
        self._scapy_packets: List[Any] = []
        self.pcap_path: Optional[str] = None

    def create_capture(self, simulation_result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert actual NetworkSimulator output and events into synthetic network capture records.

        :param simulation_result: Output dictionary from NetworkSimulator.simulate().
        :return: List of structured capture records.
        """
        self.reset()

        if not simulation_result or not isinstance(simulation_result, dict):
            return []

        self.simulation_result = simulation_result
        events: List[Dict[str, Any]] = simulation_result.get("events", [])
        frames: List[Dict[str, Any]] = simulation_result.get("frames", [])
        src_node = simulation_result.get("source", "Control Tower")
        dst_node = simulation_result.get("destination", "Check-in")
        packet_id = simulation_result.get("packet_id", "")
        route = simulation_result.get("route", [])

        # Create quick frame index for metadata lookups
        frames_by_seq: Dict[int, Dict[str, Any]] = {}
        for f in frames:
            seq = f.get("sequence_number")
            if seq is not None:
                frames_by_seq[seq] = f

        records: List[Dict[str, Any]] = []
        scapy_pkts: List[Any] = []
        capture_id = 1

        for idx, evt in enumerate(events):
            event_name = evt.get("event")
            seq = evt.get("sequence_number")
            frame_data = frames_by_seq.get(seq, {}) if seq is not None else {}
            frame_id = frame_data.get("frame_id", f"F{seq}" if seq is not None else "N/A")
            frame_payload = frame_data.get("payload", "")
            frame_crc = frame_data.get("crc")
            retrans_count = frame_data.get("retransmission_count", 0)

            record: Optional[Dict[str, Any]] = None
            pkt_src = src_node
            pkt_dst = dst_node
            pkt_type = ""
            status = "success"
            crc_status = "valid"
            raw_payload = ""

            if event_name == "routing":
                pkt_type = "ROUTE"
                status = "success"
                crc_status = "N/A"
                path_str = "->".join(route)
                raw_payload = f"AERONETGUARD|ROUTE|SRC={src_node}|DST={dst_node}|PATH={path_str}"
                record = {
                    "capture_id": capture_id,
                    "event_index": idx,
                    "frame_id": "N/A",
                    "packet_id": packet_id,
                    "source": src_node,
                    "destination": dst_node,
                    "sequence_number": None,
                    "payload": path_str,
                    "event_type": pkt_type,
                    "status": status,
                    "crc": None,
                    "crc_status": crc_status,
                    "retransmission_count": 0,
                    "raw_payload": raw_payload,
                }

            elif event_name == "transmission":
                pkt_type = "FRAME"
                status = evt.get("status", "success")
                crc_status = "valid" if status == "success" else "unknown"
                raw_payload = (
                    f"AERONETGUARD|FRAME|SEQ={seq}|SRC={src_node}|DST={dst_node}"
                    f"|STATUS={status.upper()}|PAYLOAD={frame_payload}"
                )
                record = {
                    "capture_id": capture_id,
                    "event_index": idx,
                    "frame_id": frame_id,
                    "packet_id": packet_id,
                    "source": src_node,
                    "destination": dst_node,
                    "sequence_number": seq,
                    "payload": frame_payload,
                    "event_type": pkt_type,
                    "status": status,
                    "crc": frame_crc,
                    "crc_status": crc_status,
                    "retransmission_count": retrans_count,
                    "raw_payload": raw_payload,
                }

            elif event_name == "retransmission":
                pkt_type = "RETRANSMISSION"
                status = "retransmitted"
                crc_status = "valid"
                attempt = evt.get("attempt", retrans_count if retrans_count > 0 else 1)
                raw_payload = (
                    f"AERONETGUARD|FRAME|SEQ={seq}|SRC={src_node}|DST={dst_node}"
                    f"|RETRANSMISSION={attempt}|PAYLOAD={frame_payload}"
                )
                record = {
                    "capture_id": capture_id,
                    "event_index": idx,
                    "frame_id": frame_id,
                    "packet_id": packet_id,
                    "source": src_node,
                    "destination": dst_node,
                    "sequence_number": seq,
                    "payload": frame_payload,
                    "event_type": pkt_type,
                    "status": status,
                    "crc": frame_crc,
                    "crc_status": crc_status,
                    "retransmission_count": attempt,
                    "raw_payload": raw_payload,
                }

            elif event_name == "acknowledgement":
                pkt_type = "ACK"
                status = "acknowledged"
                crc_status = "valid"
                # ACKs travel backwards from destination to source
                pkt_src = dst_node
                pkt_dst = src_node
                raw_payload = (
                    f"AERONETGUARD|ACK|SEQ={seq}|SRC={dst_node}|DST={src_node}|STATUS=SUCCESS"
                )
                record = {
                    "capture_id": capture_id,
                    "event_index": idx,
                    "frame_id": frame_id,
                    "packet_id": packet_id,
                    "source": dst_node,
                    "destination": src_node,
                    "sequence_number": seq,
                    "payload": f"ACK_{seq}",
                    "event_type": pkt_type,
                    "status": status,
                    "crc": frame_crc,
                    "crc_status": crc_status,
                    "retransmission_count": retrans_count,
                    "raw_payload": raw_payload,
                }

            elif (
                event_name == "crc_verification" and evt.get("is_valid") is False
            ) or (
                event_name == "failure" and evt.get("reason") == "crc_verification_failed"
            ):
                pkt_type = "CRC_FAILURE"
                status = "crc_invalid"
                crc_status = "invalid"
                raw_payload = (
                    f"AERONETGUARD|FRAME|SEQ={seq}|CRC=INVALID|PAYLOAD={frame_payload}"
                )
                record = {
                    "capture_id": capture_id,
                    "event_index": idx,
                    "frame_id": frame_id,
                    "packet_id": packet_id,
                    "source": src_node,
                    "destination": dst_node,
                    "sequence_number": seq,
                    "payload": frame_payload,
                    "event_type": pkt_type,
                    "status": status,
                    "crc": frame_crc,
                    "crc_status": crc_status,
                    "retransmission_count": retrans_count,
                    "raw_payload": raw_payload,
                }

            if record is not None:
                src_ip = NODE_IP_MAP.get(pkt_src, DEFAULT_SIM_IP)
                dst_ip = NODE_IP_MAP.get(pkt_dst, DEFAULT_SIM_IP)
                src_mac = NODE_MAC_MAP.get(pkt_src, DEFAULT_SIM_MAC)
                dst_mac = NODE_MAC_MAP.get(pkt_dst, DEFAULT_SIM_MAC)

                record["source_ip"] = src_ip
                record["destination_ip"] = dst_ip
                record["source_mac"] = src_mac
                record["destination_mac"] = dst_mac
                record["udp_port"] = DEFAULT_UDP_PORT
                record["timestamp_offset_ms"] = idx

                records.append(record)

                # Construct Scapy packet representation if available
                if SCAPY_AVAILABLE:
                    sim_ts = BASE_SIM_TIMESTAMP + (idx * 0.001)
                    pkt = (
                        Ether(src=src_mac, dst=dst_mac)
                        / IP(src=src_ip, dst=dst_ip)
                        / UDP(sport=DEFAULT_UDP_PORT, dport=DEFAULT_UDP_PORT)
                        / Raw(load=raw_payload.encode("utf-8"))
                    )
                    pkt.time = sim_ts
                    scapy_pkts.append(pkt)

                capture_id += 1

        self.packets = records
        self._scapy_packets = scapy_pkts
        return list(self.packets)

    def get_packets(self) -> List[Dict[str, Any]]:
        """Return the structured capture records list."""
        return list(self.packets)

    def get_capture_summary(self) -> Dict[str, Any]:
        """
        Return high-level breakdown statistics of captured packets.

        :return: Summary dictionary matching specification.
        """
        packet_count = len(self.packets)
        frame_packets = sum(1 for p in self.packets if p.get("event_type") == "FRAME")
        ack_packets = sum(1 for p in self.packets if p.get("event_type") == "ACK")
        retransmission_packets = sum(1 for p in self.packets if p.get("event_type") == "RETRANSMISSION")
        crc_failure_packets = sum(1 for p in self.packets if p.get("event_type") == "CRC_FAILURE")
        route_packets = sum(1 for p in self.packets if p.get("event_type") == "ROUTE")

        return {
            "packet_count": packet_count,
            "frame_packets": frame_packets,
            "ack_packets": ack_packets,
            "retransmission_packets": retransmission_packets,
            "crc_failure_packets": crc_failure_packets,
            "route_packets": route_packets,
            "pcap_file": os.path.basename(self.pcap_path) if self.pcap_path else None,
            "is_ready": packet_count > 0,
        }

    def export_pcap(self, output_path: str) -> Dict[str, Any]:
        """
        Write captured simulation packets into a standard binary PCAP file.

        :param output_path: Absolute or relative destination filesystem path.
        :return: Metadata dictionary indicating success and packet count.
        :raises RuntimeError: If no capture records exist or PCAP export fails.
        """
        if not self.packets:
            raise RuntimeError("No simulation capture records available to export.")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if SCAPY_AVAILABLE and self._scapy_packets:
            wrpcap(output_path, self._scapy_packets)
        else:
            # Fallback manual PCAP writer if Scapy is absent
            self._write_fallback_pcap(output_path)

        self.pcap_path = output_path
        filename = os.path.basename(output_path)

        return {
            "success": True,
            "file": filename,
            "filename": filename,
            "packet_count": len(self.packets),
            "file_path": output_path,
        }

    def _write_fallback_pcap(self, output_path: str) -> None:
        """Write raw standard PCAP binary stream when Scapy is not available."""
        pcap_buffer = bytearray()
        # Global PCAP Header (24 bytes)
        global_hdr = struct.pack(
            "<IHHiIII",
            0xA1B2C3D4,  # Magic number
            2,           # Major version
            4,           # Minor version
            0,           # Thiszone
            0,           # Sigfigs
            65535,       # Snaplen
            1,           # Link-type: Ethernet
        )
        pcap_buffer.extend(global_hdr)

        for p in self.packets:
            raw_bytes = p.get("raw_payload", "").encode("utf-8")
            # Minimal Ethernet (14) + IP (20) + UDP (8) dummy header = 42 bytes
            pkt_data = (b"\x00" * 42) + raw_bytes
            pkt_len = len(pkt_data)
            ts_sec = int(BASE_SIM_TIMESTAMP) + (p.get("event_index", 0) // 1000)
            ts_usec = (p.get("event_index", 0) * 1000) % 1000000
            pkt_hdr = struct.pack("<IIII", ts_sec, ts_usec, pkt_len, pkt_len)
            pcap_buffer.extend(pkt_hdr)
            pcap_buffer.extend(pkt_data)

        with open(output_path, "wb") as f:
            f.write(pcap_buffer)

    def reset(self) -> None:
        """Restore clean initialized capture state."""
        self.simulation_result = None
        self.packets = []
        self._scapy_packets = []
        self.pcap_path = None


# --- Backward Compatibility Alias ---
class PCAPExporter:
    """Legacy backward-compatibility facade for earlier test references."""

    @classmethod
    def generate_pcap_bytes(cls, event_logs: List[Dict[str, Any]]) -> bytes:
        """Generate PCAP bytes from legacy event logs."""
        capture = SimulationCapture()
        sim_result = {
            "source": "Security",
            "destination": "Baggage",
            "events": event_logs,
            "frames": [],
        }
        capture.create_capture(sim_result)
        temp_file = "temp_capture.pcap"
        try:
            capture.export_pcap(temp_file)
            with open(temp_file, "rb") as f:
                data = f.read()
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return data
        except Exception:
            return b""
