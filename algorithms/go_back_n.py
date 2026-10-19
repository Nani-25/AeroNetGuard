"""
Go-Back-N (GBN) ARQ Protocol module for AeroNetGuard.

This module implements the GoBackNProtocol class simulating sender sliding-window
transmission, receiver in-order sequence verification, cumulative acknowledgements,
and Go-Back-N window rollback retransmissions over simulated channels.
"""

from typing import List, Tuple, Optional, Dict, Any, Set
from simulation.frame import Frame
from algorithms.sliding_window import SlidingWindow
from algorithms.crc import CRC32


class GoBackNProtocol:
    """
    Go-Back-N Automatic Repeat reQuest (ARQ) Protocol Simulator.

    Maintains sender sliding-window state, in-order receiver verification,
    cumulative ACKs, and window-rollback retransmissions upon frame drop or error.
    """

    def __init__(self, frames: Optional[List[Frame]] = None, window_size: int = 4) -> None:
        """
        Initialize the GoBackNProtocol with a collection of frames and a window size.

        :param frames: List of ordered Frame instances to transmit.
        :param window_size: Maximum in-flight frames permitted (positive integer).
        :raises TypeError: If frames is not a list or window_size is not an int.
        :raises ValueError: If frames is empty, sequence numbers are invalid/unordered/duplicate,
                            or window_size is <= 0 or exceeds frame count.
        """
        if type(window_size) is not int:
            raise TypeError("window_size must be an integer.")

        if window_size <= 0:
            raise ValueError(f"window_size must be a positive integer (received {window_size}).")

        if frames is not None:
            if not isinstance(frames, list):
                raise TypeError("frames must be a list of Frame objects.")

            if len(frames) == 0:
                raise ValueError("frames list cannot be empty.")

            for idx, f in enumerate(frames):
                if not isinstance(f, Frame):
                    raise TypeError(f"Item at index {idx} is not an instance of Frame.")
                if type(f.sequence_number) is not int or f.sequence_number < 0:
                    raise ValueError(f"Frame at index {idx} has invalid sequence number {f.sequence_number}.")

            seqs = [f.sequence_number for f in frames]
            if len(set(seqs)) != len(seqs):
                raise ValueError("Frame sequence numbers must be unique.")
            if seqs != sorted(seqs):
                raise ValueError("Frame sequence numbers must be ordered.")

            if window_size > len(frames):
                raise ValueError(f"window_size ({window_size}) cannot exceed the number of frames ({len(frames)}).")

            self.frames: List[Frame] = list(frames)
        else:
            self.frames = []

        self.window_size: int = window_size

        # Protocol State
        self.base: int = 0
        self.next_sequence: int = 0
        self.expected_sequence: int = self.frames[0].sequence_number if self.frames else 0

        self.acknowledged_frames: Set[int] = set()
        self.transmitted_frames: List[int] = []

        self.retransmission_count: int = 0
        self.retransmission_history: List[Dict[str, Any]] = []
        self.last_acknowledged: Optional[int] = None
        self.completed: bool = False

    def get_current_window(self) -> List[Frame]:
        """
        Return the Frame objects currently inside the sender's Go-Back-N window.

        :return: List of Frame objects within [base, min(base + window_size, len(frames))].
        """
        if self.base >= len(self.frames):
            return []
        window_end = min(self.base + self.window_size, len(self.frames))
        return self.frames[self.base:window_end]

    def send_window(self) -> List[Frame]:
        """
        Transmit all currently eligible frames in the sender window without auto-ACK.

        :return: List of newly transmitted Frame objects.
        """
        newly_transmitted: List[Frame] = []
        window_end = min(self.base + self.window_size, len(self.frames))

        for idx in range(self.next_sequence, window_end):
            frame = self.frames[idx]
            frame.update_status("transmitted")
            if frame.sequence_number not in self.transmitted_frames:
                self.transmitted_frames.append(frame.sequence_number)
            newly_transmitted.append(frame)

        self.next_sequence = max(self.next_sequence, window_end)
        return newly_transmitted

    def process_frame_result(self, sequence_number: int, success: bool) -> bool:
        """
        Process transmission outcome of a frame on the receiver side.

        If success is False, records failure and triggers Go-Back-N state.
        If success is True, checks if sequence_number equals expected_sequence.
        If in order, advances expected_sequence and generates cumulative ACK.
        If out of order, discards the frame and keeps expected_sequence unchanged.

        :param sequence_number: Sequence number of the frame received.
        :param success: True if frame delivered intact, False if lost or corrupted.
        :return: True if frame accepted by receiver in-order, False otherwise.
        :raises ValueError: If sequence_number is not part of the frame set.
        """
        valid_seqs = {f.sequence_number for f in self.frames}
        if sequence_number not in valid_seqs:
            raise ValueError(f"Sequence number {sequence_number} does not exist.")

        if not success:
            self.handle_failure(sequence_number)
            return False

        if sequence_number == self.expected_sequence:
            self.expected_sequence += 1
            self.process_ack(sequence_number)
            return True
        else:
            # Out-of-order frame is discarded
            for f in self.frames:
                if f.sequence_number == sequence_number:
                    f.update_status("discarded_out_of_order")
                    break
            return False

    def process_ack(self, sequence_number: int) -> None:
        """
        Process a cumulative acknowledgement for all frames up to sequence_number.

        :param sequence_number: Cumulative ACK sequence number.
        :raises ValueError: If sequence_number does not exist or exceeds transmitted horizon.
        """
        valid_seqs = {f.sequence_number for f in self.frames}
        if sequence_number not in valid_seqs:
            raise ValueError(f"Sequence number {sequence_number} does not exist.")

        if sequence_number not in self.transmitted_frames:
            raise ValueError(f"Cannot acknowledge untransmitted frame {sequence_number}.")

        target_idx = -1
        for idx, f in enumerate(self.frames):
            if f.sequence_number == sequence_number:
                target_idx = idx
                break

        # If already acknowledged or prior to current base, safe duplicate ACK
        if target_idx < self.base:
            return

        # Cumulatively acknowledge frames from self.base up to target_idx
        for idx in range(self.base, target_idx + 1):
            frame = self.frames[idx]
            self.acknowledged_frames.add(frame.sequence_number)
            frame.update_status("acknowledged")

        self.base = target_idx + 1
        self.last_acknowledged = sequence_number
        if self.next_sequence < self.base:
            self.next_sequence = self.base

        if len(self.acknowledged_frames) == len(self.frames):
            self.completed = True

    def handle_failure(self, sequence_number: int) -> List[Frame]:
        """
        Handle a frame transmission failure (loss, bit corruption, or drop).

        Marks the failed frame and resets next_sequence back to base for Go-Back-N rollback.

        :param sequence_number: Failed frame sequence number.
        :return: List of frames eligible for retransmission.
        :raises ValueError: If sequence_number does not exist.
        """
        valid_seqs = {f.sequence_number for f in self.frames}
        if sequence_number not in valid_seqs:
            raise ValueError(f"Sequence number {sequence_number} does not exist.")

        for f in self.frames:
            if f.sequence_number == sequence_number:
                f.update_status("failed")
                break

        # In GBN, sender rolls back next_sequence to base
        self.next_sequence = self.base
        return self.get_retransmission_frames()

    def get_retransmission_frames(self) -> List[Frame]:
        """
        Return the list of outstanding frames eligible for Go-Back-N retransmission.
        Excludes already acknowledged frames.

        :return: List of unacknowledged Frame objects in current window.
        """
        if self.base >= len(self.frames):
            return []
        window_end = min(self.base + self.window_size, len(self.frames))
        return [f for f in self.frames[self.base:window_end] if f.sequence_number not in self.acknowledged_frames]

    def retransmit(self) -> List[Frame]:
        """
        Execute Go-Back-N window retransmission.
        Increments protocol and individual frame retransmission counters and records event history.

        :return: List of retransmitted Frame objects.
        """
        retrans_frames = self.get_retransmission_frames()
        if not retrans_frames:
            return []

        self.retransmission_count += 1
        for f in retrans_frames:
            f.increment_retransmission()
            f.update_status("retransmitted")
            if f.sequence_number not in self.transmitted_frames:
                self.transmitted_frames.append(f.sequence_number)

        event = {
            "start_sequence": retrans_frames[0].sequence_number,
            "frames": [f.sequence_number for f in retrans_frames],
            "count": self.retransmission_count,
        }
        self.retransmission_history.append(event)
        window_end = min(self.base + self.window_size, len(self.frames))
        self.next_sequence = max(self.next_sequence, window_end)
        return retrans_frames

    def get_telemetry(self) -> Dict[str, Any]:
        """
        Return telemetry dictionary for backward compatibility with simulator / tests.
        """
        return {
            "window_state": self.get_state(),
            "total_retransmissions": self.retransmission_count,
            "delivered_count": len(self.acknowledged_frames),
        }

    def is_complete(self) -> bool:
        """
        Check if all frames have been acknowledged.

        :return: True if all frames acknowledged, False otherwise.
        """
        if not self.frames:
            return True
        return self.completed or len(self.acknowledged_frames) == len(self.frames)

    def get_unacknowledged_frames(self) -> List[Frame]:
        """
        Return all frames in the stream that have not yet been cumulatively acknowledged.

        :return: List of unacknowledged Frame objects.
        """
        return [f for f in self.frames if f.sequence_number not in self.acknowledged_frames]

    def get_state(self) -> Dict[str, Any]:
        """
        Return a JSON-serializable dictionary representation of the Go-Back-N state.

        :return: State dictionary.
        """
        return {
            "base": self.base,
            "next_sequence": self.next_sequence,
            "expected_sequence": self.expected_sequence,
            "window_size": self.window_size,
            "current_window": [f.sequence_number for f in self.get_current_window()],
            "acknowledged_frames": sorted(list(self.acknowledged_frames)),
            "unacknowledged_frames": [f.sequence_number for f in self.get_unacknowledged_frames()],
            "retransmission_count": self.retransmission_count,
            "retransmission_history": list(self.retransmission_history),
            "completed": self.is_complete(),
        }

    def reset(self) -> None:
        """Reset the protocol and frame states back to their initial conditions."""
        self.base = 0
        self.next_sequence = 0
        self.expected_sequence = self.frames[0].sequence_number if self.frames else 0
        self.acknowledged_frames.clear()
        self.transmitted_frames.clear()
        self.retransmission_count = 0
        self.retransmission_history.clear()
        self.last_acknowledged = None
        self.completed = False

        for f in self.frames:
            f.status = "created"
            f.retransmission_count = 0


# Legacy Support for Network Simulator
class GBNReceiver:
    def __init__(self) -> None:
        self.expected_seq_num: int = 0
        self.received_frames: List[Frame] = []

    def receive_frame(self, frame: Frame) -> Tuple[Optional[int], bool, str]:
        if frame.crc is not None:
            if not CRC32.verify(frame.payload, frame.crc):
                frame.set_crc_status("invalid")
                frame.update_status("corrupted")
                last_valid_ack = self.expected_seq_num - 1 if self.expected_seq_num > 0 else None
                return (last_valid_ack, False, "crc_error")
            frame.set_crc_status("valid")

        if frame.sequence_number == self.expected_seq_num:
            frame.update_status("delivered")
            self.received_frames.append(frame)
            ack_num = self.expected_seq_num
            self.expected_seq_num += 1
            return (ack_num, True, "accepted")
        else:
            frame.update_status("discarded_out_of_order")
            last_valid_ack = self.expected_seq_num - 1 if self.expected_seq_num > 0 else None
            return (last_valid_ack, False, "out_of_order")

    def reset(self) -> None:
        self.expected_seq_num = 0
        self.received_frames.clear()


class GBNSender:
    def __init__(self, window_size: int = 4) -> None:
        self.window: SlidingWindow = SlidingWindow(window_size=window_size)
        self.total_retransmissions: int = 0

    def can_send(self) -> bool:
        return self.window.can_send()

    def transmit_frame(self, frame: Frame) -> bool:
        if frame.crc is None:
            crc_val = CRC32.calculate(frame.payload)
            frame.set_crc(crc_val)
        success = self.window.add_frame(frame)
        if success:
            frame.update_status("transmitting")
        return success

    def process_ack(self, ack_num: Optional[int]) -> int:
        if ack_num is None:
            return 0
        return self.window.process_ack(ack_num)

    def handle_timeout(self) -> List[Frame]:
        unacked = self.window.get_unacked_frames()
        if not unacked:
            return []
        for frame in unacked:
            frame.increment_retransmission()
            frame.update_status("retransmitting")
            self.total_retransmissions += 1
        self.window.reset_next_seq_to_base()
        return unacked
