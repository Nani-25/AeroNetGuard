"""
Discrete-event network simulation engine for AeroNetGuard.

Orchestrates end-to-end airport communications:
    AirportNetwork
          ↓
    DijkstraRouter
          ↓
       Packet
          ↓
       Framing
          ↓
        CRC
          ↓
    Sliding Window
          ↓
      Go-Back-N
          ↓
    Delivery Result
          ↓
   Simulation Metrics
"""

from typing import List, Dict, Any, Optional
from simulation.network import (
    AirportNetwork,
    NODE_CONTROL_TOWER,
    NODE_SECURITY,
    NODE_BAGGAGE,
    NODE_CHECK_IN,
    NODE_EMERGENCY_SERVICES,
)
from simulation.dijkstra import DijkstraRouter
from simulation.packet import Packet
from simulation.frame import Frame
from simulation.error_generator import NetworkImpairmentGenerator
from algorithms.framing import FramingEngine, ByteStuffing
from algorithms.crc import CRCProcessor, CRC32
from algorithms.go_back_n import GoBackNProtocol, GBNSender, GBNReceiver


class NetworkSimulator:
    """
    Central Discrete Event Network Simulator for AeroNetGuard.

    Integrates topology routing, packet generation, word-based framing,
    CRC-8 error detection, and Go-Back-N flow control into a single unified pipeline.
    """

    def __init__(self, network: Optional[AirportNetwork] = None) -> None:
        """
        Initialize the simulator with its core component engines.

        :param network: Optional custom AirportNetwork instance. Defaults to AirportNetwork().
        """
        self.network: AirportNetwork = network if network is not None else AirportNetwork()
        self.router: DijkstraRouter = DijkstraRouter(self.network)
        self.crc_processor: CRCProcessor = CRCProcessor()
        self.framing_engine: FramingEngine = FramingEngine()

        # Simulation state
        self.state: str = "initialized"
        self.events: List[Dict[str, Any]] = []
        self.event_logs: List[Dict[str, Any]] = self.events  # Backward compatibility alias
        self.packet: Optional[Packet] = None
        self.frames: List[Frame] = []
        self.result: Optional[Dict[str, Any]] = None

    def simulate(
        self,
        source: str,
        destination: str,
        message: str,
        window_size: int = 3,
        failure_sequence: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end discrete event simulation for a message between airport nodes.

        Pipeline Stages:
            1. Validate source, destination, message, and parameters
            2. Compute shortest route via Dijkstra
            3. Create and route Packet
            4. Frame packet payload into discrete Frame objects
            5. Calculate CRC-8 for every frame
            6. Initialize Go-Back-N protocol manager
            7. Transmit frames through window
            8. Verify CRC, process acknowledgements, and simulate failures
            9. Execute Go-Back-N retransmission recovery on failures
            10. Mark delivery completion and compile structured metrics

        :param source: Name of source airport node.
        :param destination: Name of destination airport node.
        :param message: String payload to transmit.
        :param window_size: Positive integer sliding window size (default 3).
        :param failure_sequence: Optional list of sequence numbers that fail on first transmission.
        :return: JSON-serializable simulation result dictionary.
        :raises TypeError: If inputs have invalid types.
        :raises ValueError: If nodes or parameters are invalid or out of range.
        """
        # --- Stage 1: Validation ---
        if not isinstance(message, str):
            raise TypeError("Message must be a string.")
        if not message.strip():
            raise ValueError("Message cannot be empty or whitespace only.")

        if not isinstance(source, str) or not source.strip():
            raise ValueError("Source node must be a non-empty string.")
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("Destination node must be a non-empty string.")

        # Fixed source node restriction: Control Tower is the ONLY allowed source
        if source != NODE_CONTROL_TOWER:
            raise ValueError("Invalid source node. Source must be Control Tower.")

        # Destination node restrictions: Control Tower cannot be destination
        if destination == NODE_CONTROL_TOWER:
            raise ValueError("Invalid destination node. Destination cannot be Control Tower.")

        if not self.network.has_node(destination):
            raise ValueError(f"Destination node '{destination}' does not exist in the airport network.")

        if type(window_size) is not int:
            raise TypeError("window_size must be an integer.")
        if window_size <= 0:
            raise ValueError("window_size must be a positive integer.")

        if failure_sequence is not None:
            if not isinstance(failure_sequence, (list, tuple)):
                raise TypeError("failure_sequence must be a list of integers.")
            for seq in failure_sequence:
                if type(seq) is not int:
                    raise TypeError("Items in failure_sequence must be integers.")
                if seq < 0:
                    raise ValueError("Sequence numbers in failure_sequence cannot be negative.")

        self.reset()

        # --- Stage 2: Routing ---
        self.state = "routing"
        route_info = self.router.find_route(source, destination)
        route: List[str] = route_info["path"]
        route_cost: int = route_info["total_cost"]
        hop_count: int = route_info["hop_count"]

        self.events.append({
            "event": "routing",
            "source": source,
            "destination": destination,
            "route": route,
            "route_cost": route_cost,
            "hop_count": hop_count,
        })

        # --- Stage 3: Packet Creation ---
        packet = Packet(
            source=source,
            destination=destination,
            payload=message,
        )
        packet.set_route(route)
        packet.update_status("routed")
        self.packet = packet

        self.events.append({
            "event": "packet_created",
            "packet_id": packet.packet_id,
            "source": source,
            "destination": destination,
            "payload": message,
        })

        # --- Stage 4: Framing ---
        self.state = "framing"
        frames = self.framing_engine.create_frames(packet)
        self.frames = frames
        total_frames = len(frames)

        if window_size > total_frames:
            if window_size > 4:
                raise ValueError(
                    f"window_size ({window_size}) cannot exceed total frames ({total_frames})."
                )
            window_size = total_frames

        if failure_sequence is not None:
            for seq in failure_sequence:
                if seq >= total_frames:
                    raise ValueError(
                        f"Failure sequence number {seq} is outside frame range [0, {total_frames - 1}]."
                    )

        for f in frames:
            self.events.append({
                "event": "frame_created",
                "frame_id": f.frame_id,
                "sequence_number": f.sequence_number,
                "payload": f.payload,
            })

        # --- Stage 5: CRC Calculation ---
        self.state = "crc"
        for f in frames:
            crc_val = self.crc_processor.calculate_frame_crc(f)
            self.events.append({
                "event": "crc_calculated",
                "sequence_number": f.sequence_number,
                "crc": crc_val,
            })

        # --- Stage 6: Go-Back-N Setup ---
        protocol = GoBackNProtocol(frames=frames, window_size=window_size)

        # Track failure budget per sequence number
        remaining_failures: Dict[int, int] = {}
        if failure_sequence:
            for s in failure_sequence:
                remaining_failures[s] = remaining_failures.get(s, 0) + 1

        # --- Stage 7: Transmission & Recovery Loop ---
        self.state = "transmitting"
        packet.update_status("transmitting")

        in_flight: List[Frame] = []
        max_simulation_steps = 1000
        step = 0

        # Prime initial window transmission
        in_flight.extend(protocol.send_window())

        while not protocol.is_complete() and step < max_simulation_steps:
            step += 1

            if in_flight:
                frame = in_flight.pop(0)
                seq = frame.sequence_number

                if remaining_failures.get(seq, 0) > 0:
                    remaining_failures[seq] -= 1
                    self.events.append({
                        "event": "transmission",
                        "sequence_number": seq,
                        "status": "failed",
                    })
                    self.events.append({
                        "event": "failure",
                        "sequence_number": seq,
                        "reason": "simulated_transmission_failure",
                    })
                    protocol.process_frame_result(seq, success=False)
                else:
                    self.events.append({
                        "event": "transmission",
                        "sequence_number": seq,
                        "status": "success",
                    })
                    is_valid = self.crc_processor.verify_frame(frame)
                    self.events.append({
                        "event": "crc_verification",
                        "sequence_number": seq,
                        "is_valid": is_valid,
                    })

                    if is_valid:
                        accepted = protocol.process_frame_result(seq, success=True)
                        if accepted:
                            self.events.append({
                                "event": "acknowledgement",
                                "sequence_number": seq,
                            })
                            # Window slid forward; transmit newly eligible frames
                            newly_sent = protocol.send_window()
                            in_flight.extend(newly_sent)
                        else:
                            self.events.append({
                                "event": "discarded_out_of_order",
                                "sequence_number": seq,
                            })
                    else:
                        self.events.append({
                            "event": "failure",
                            "sequence_number": seq,
                            "reason": "crc_verification_failed",
                        })
                        protocol.process_frame_result(seq, success=False)

            else:
                # in_flight is empty but transmission incomplete -> Go-Back-N recovery
                self.state = "retransmitting"
                retrans_frames = protocol.retransmit()
                if not retrans_frames:
                    break
                for rf in retrans_frames:
                    self.events.append({
                        "event": "retransmission",
                        "sequence_number": rf.sequence_number,
                        "attempt": rf.retransmission_count,
                    })
                in_flight.extend(retrans_frames)

        # --- Stage 8: Delivery & Result Construction ---
        delivery_successful = protocol.is_complete()
        if delivery_successful:
            self.state = "delivered"
            packet.update_status("delivered")
            self.events.append({
                "event": "delivery",
                "packet_id": packet.packet_id,
                "status": "delivered",
            })
        else:
            self.state = "failed"
            packet.update_status("failed")

        failed_frames_count = len(failure_sequence) if failure_sequence else 0
        retransmitted_frames_count = sum(1 for f in frames if f.retransmission_count > 0)
        successful_frames_count = len(protocol.acknowledged_frames)

        result: Dict[str, Any] = {
            "status": self.state,
            "source": source,
            "destination": destination,
            "message": message,
            "route": route,
            "route_cost": route_cost,
            "hop_count": hop_count,
            "packet_id": packet.packet_id,
            "total_frames": total_frames,
            "window_size": window_size,
            "frames": [f.to_dict() for f in frames],
            "events": list(self.events),
            "retransmission_count": protocol.retransmission_count,
            "delivery_successful": delivery_successful,
            "successful_frames": successful_frames_count,
            "failed_frames": failed_frames_count,
            "retransmitted_frames": retransmitted_frames_count,
            "metrics": {
                "total_frames": total_frames,
                "successful_frames": successful_frames_count,
                "failed_frames": failed_frames_count,
                "retransmitted_frames": retransmitted_frames_count,
                "retransmission_count": protocol.retransmission_count,
                "route_cost": route_cost,
                "hop_count": hop_count,
                "delivery_successful": delivery_successful,
            },
        }

        self.result = result
        return result

    def get_state(self) -> Dict[str, Any]:
        """
        Return a JSON-friendly snapshot of current simulator state.

        :return: State dictionary.
        """
        return {
            "state": self.state,
            "source": self.packet.source if self.packet else None,
            "destination": self.packet.destination if self.packet else None,
            "packet_id": self.packet.packet_id if self.packet else None,
            "total_frames": len(self.frames),
            "events": list(self.events),
        }

    def reset(self) -> None:
        """
        Reset simulator state to initialized conditions without rebuilding topology.
        """
        self.state = "initialized"
        self.events.clear()
        self.event_logs = self.events
        self.packet = None
        self.frames.clear()
        self.result = None

    # Legacy Backward-Compatibility Support
    def run_simulation(
        self,
        source: str,
        destination: str,
        payloads: List[str],
        window_size: int = 4,
        loss_rate: float = 0.0,
        corruption_rate: float = 0.0,
        allow_emergency_transit: bool = False,
        seed: Optional[int] = 42,
    ) -> Dict[str, Any]:
        if source != NODE_CONTROL_TOWER:
            raise ValueError("Invalid source node. Source must be Control Tower.")
        if destination == NODE_CONTROL_TOWER:
            raise ValueError("Invalid destination node. Destination cannot be Control Tower.")

        self.event_logs.clear()
        step = 0

        route_info = self.router.find_route(
            source, destination, allow_emergency_transit=allow_emergency_transit
        )
        route = route_info["path"]
        path_cost = route_info["total_cost"]

        step += 1
        self._log_event(
            step=step,
            event="ROUTE_CALCULATED",
            node=source,
            next_node=route[1] if len(route) > 1 else source,
            description=f"Calculated optimal path via Dijkstra: {' -> '.join(route)} (Cost: {path_cost})",
            details={"route": route, "path_cost": path_cost, "hop_count": route_info["hop_count"]},
        )

        impairment_gen = NetworkImpairmentGenerator(
            loss_rate=loss_rate, corruption_rate=corruption_rate, seed=seed
        )

        gbn_sender = GBNSender(window_size=window_size)
        gbn_receiver = GBNReceiver()

        total_frames_sent = 0
        total_frames_delivered = 0
        total_frames_dropped = 0
        total_frames_corrupted = 0
        total_retransmissions = 0
        crc_checks_passed = 0
        crc_checks_failed = 0

        packets: List[Packet] = []
        frames: List[Frame] = []

        for seq_idx, payload in enumerate(payloads):
            pkt = Packet(
                source=source,
                destination=destination,
                payload=payload,
                sequence_number=seq_idx,
                route=route,
            )
            pkt.update_status("framed")
            packets.append(pkt)

            stuffed_payload = ByteStuffing.stuff_bytes(payload)
            frm = Frame(
                packet_id=pkt.packet_id,
                source=source,
                destination=destination,
                payload=payload,
                sequence_number=seq_idx,
            )
            crc_val = CRC32.calculate(payload)
            frm.set_crc(crc_val)
            frames.append(frm)

            step += 1
            self._log_event(
                step=step,
                event="FRAME_CREATED",
                node=source,
                next_node=route[1] if len(route) > 1 else source,
                description=f"Created Frame seq={seq_idx} (Stuffed Payload: '{stuffed_payload}', CRC: {f'0x{crc_val:08x}'})",
                details=frm.to_dict(),
            )

        pending_frames = list(frames)
        frame_index = 0
        max_simulation_steps = 1000

        while (len(gbn_receiver.received_frames) < len(frames)) and step < max_simulation_steps:
            while gbn_sender.can_send() and frame_index < len(pending_frames):
                frm = pending_frames[frame_index]
                gbn_sender.transmit_frame(frm)
                total_frames_sent += 1

                current_hop = route[0]
                next_hop = route[1] if len(route) > 1 else route[0]

                step += 1
                self._log_event(
                    step=step,
                    event="FRAME_TRANSMITTING",
                    node=current_hop,
                    next_node=next_hop,
                    description=f"Transmitting Frame seq={frm.sequence_number} from {current_hop} towards {next_hop}",
                    details=frm.to_dict(),
                    window_state=gbn_sender.window.to_dict(),
                )

                dropped = impairment_gen.should_drop()
                corrupted = impairment_gen.should_corrupt() if not dropped else False

                if dropped:
                    total_frames_dropped += 1
                    frm.update_status("dropped")
                    step += 1
                    self._log_event(
                        step=step,
                        event="FRAME_DROPPED",
                        node=next_hop,
                        next_node=next_hop,
                        description=f"[LOSS] Frame seq={frm.sequence_number} dropped on link {current_hop} -> {next_hop}",
                        details=frm.to_dict(),
                        window_state=gbn_sender.window.to_dict(),
                    )
                elif corrupted:
                    total_frames_corrupted += 1
                    corrupted_frame = Frame(
                        packet_id=frm.packet_id,
                        source=frm.source,
                        destination=frm.destination,
                        payload=CRC32.corrupt_data(frm.payload, 0),
                        sequence_number=frm.sequence_number,
                        crc=frm.crc,
                    )
                    step += 1
                    self._log_event(
                        step=step,
                        event="FRAME_CORRUPTED",
                        node=next_hop,
                        next_node=next_hop,
                        description=f"[CORRUPTION] Bit error injected into Frame seq={frm.sequence_number}",
                        details=corrupted_frame.to_dict(),
                        window_state=gbn_sender.window.to_dict(),
                    )

                    ack_seq, valid, reason = gbn_receiver.receive_frame(corrupted_frame)
                    crc_checks_failed += 1
                    step += 1
                    self._log_event(
                        step=step,
                        event="CRC_CHECK_FAILED",
                        node=destination,
                        next_node=source,
                        description=f"CRC check FAILED for Frame seq={frm.sequence_number}. Reason: {reason}",
                        details={"ack_seq": ack_seq, "valid": valid, "reason": reason},
                        window_state=gbn_sender.window.to_dict(),
                    )

                else:
                    ack_seq, valid, reason = gbn_receiver.receive_frame(frm)
                    if valid:
                        total_frames_delivered += 1
                        crc_checks_passed += 1
                        step += 1
                        self._log_event(
                            step=step,
                            event="FRAME_DELIVERED",
                            node=destination,
                            next_node=source,
                            description=f"Frame seq={frm.sequence_number} successfully delivered to {destination}. Sending ACK={ack_seq}",
                            details=frm.to_dict(),
                            window_state=gbn_sender.window.to_dict(),
                        )

                        newly_acked = gbn_sender.process_ack(ack_seq)
                        step += 1
                        self._log_event(
                            step=step,
                            event="ACK_RECEIVED",
                            node=source,
                            next_node=source,
                            description=f"Sender received ACK={ack_seq}. Window advanced by {newly_acked}.",
                            details={"ack_seq": ack_seq, "newly_acked": newly_acked},
                            window_state=gbn_sender.window.to_dict(),
                        )
                    else:
                        step += 1
                        self._log_event(
                            step=step,
                            event="FRAME_DISCARDED",
                            node=destination,
                            next_node=source,
                            description=f"Frame seq={frm.sequence_number} discarded by receiver ({reason}).",
                            details={"ack_seq": ack_seq, "reason": reason},
                            window_state=gbn_sender.window.to_dict(),
                        )

                frame_index += 1

            if len(gbn_receiver.received_frames) < len(frames):
                unacked_frames = gbn_sender.handle_timeout()
                if unacked_frames:
                    total_retransmissions += len(unacked_frames)
                    retransmit_seqs = [f.sequence_number for f in unacked_frames]
                    step += 1
                    self._log_event(
                        step=step,
                        event="GBN_TIMEOUT_ROLLBACK",
                        node=source,
                        next_node=route[1] if len(route) > 1 else source,
                        description=f"[TIMEOUT] GBN timer expired. Rolling back window and retransmitting seqs: {retransmit_seqs}",
                        details={"retransmitting_seqs": retransmit_seqs},
                        window_state=gbn_sender.window.to_dict(),
                    )
                    frame_index = gbn_sender.window.send_base

        pdr = (total_frames_delivered / len(frames) * 100.0) if frames else 100.0
        total_crc_checks = crc_checks_passed + crc_checks_failed
        crc_pass_rate = (crc_checks_passed / total_crc_checks * 100.0) if total_crc_checks else 100.0

        return {
            "source": source,
            "destination": destination,
            "route": route,
            "path_cost": path_cost,
            "hop_count": route_info["hop_count"],
            "window_size": window_size,
            "loss_rate": loss_rate,
            "corruption_rate": corruption_rate,
            "total_packets": len(payloads),
            "total_frames_sent": total_frames_sent,
            "total_frames_delivered": total_frames_delivered,
            "total_frames_dropped": total_frames_dropped,
            "total_frames_corrupted": total_frames_corrupted,
            "total_retransmissions": total_retransmissions,
            "packet_delivery_ratio": round(pdr, 2),
            "crc_pass_rate": round(crc_pass_rate, 2),
            "total_steps": step,
            "event_logs": self.event_logs,
        }

    def _log_event(
        self,
        step: int,
        event: str,
        node: str,
        next_node: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
        window_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Helper to append structured event log entry."""
        log_entry = {
            "step": step,
            "event": event,
            "node": node,
            "next_node": next_node,
            "description": description,
            "details": details or {},
            "window_state": window_state or {},
        }
        self.event_logs.append(log_entry)
