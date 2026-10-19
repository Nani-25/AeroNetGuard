"""
Sliding Window Flow Control module for AeroNetGuard.

This module provides the SlidingWindow class to manage sender-side windowing,
frame transmission eligibility, cumulative/selective acknowledgement processing,
and window advancement across the data link layer.
"""

from typing import List, Set, Dict, Any, Optional
from simulation.frame import Frame


class SlidingWindow:
    """
    Sender-Side Sliding Window Flow Control Manager.

    Maintains the sender window state, tracks transmitted vs. acknowledged frames,
    advances the window base upon sequential ACKs, and isolates unacknowledged frames.
    """

    def __init__(self, frames: Optional[List[Frame]] = None, window_size: int = 4) -> None:
        """
        Initialize the SlidingWindow with a list of Frames and a window size.

        :param frames: Ordered list of Frame objects to transmit (defaults to empty list).
        :param window_size: Maximum number of unacknowledged frames permitted in flight (positive int).
        :raises TypeError: If frames is not a list or window_size is not an integer.
        :raises ValueError: If window_size <= 0 or frames contains invalid/unordered sequence numbers.
        """
        if frames is None:
            frames = []

        if not isinstance(frames, list):
            raise TypeError("frames must be a list of Frame objects.")

        if type(window_size) is not int:
            raise TypeError("window_size must be an integer.")

        if window_size <= 0:
            raise ValueError(f"window_size must be greater than zero (received {window_size}).")

        for idx, f in enumerate(frames):
            if not isinstance(f, Frame):
                raise TypeError(f"Item at index {idx} is not an instance of Frame.")
            if type(f.sequence_number) is not int or f.sequence_number < 0:
                raise ValueError(f"Frame at index {idx} has invalid sequence number {f.sequence_number}.")

        # Core Sliding Window state
        self.frames: List[Frame] = list(frames)
        self.window_size: int = window_size
        self.base: int = 0
        self.next_sequence: int = 0
        self.acknowledged_frames: Set[int] = set()
        self.transmitted_frames: Set[int] = set()

    @property
    def send_base(self) -> int:
        return self.base

    @send_base.setter
    def send_base(self, value: int) -> None:
        self.base = value

    @property
    def next_seq_num(self) -> int:
        return self.next_sequence

    @next_seq_num.setter
    def next_seq_num(self, value: int) -> None:
        self.next_sequence = value

    def get_current_window(self) -> List[Frame]:
        """
        Return the list of Frame objects currently positioned inside the sender window.

        :return: List of Frame objects within [base, min(base + window_size, len(frames))].
        """
        if self.base >= len(self.frames):
            return []
        window_end = min(self.base + self.window_size, len(self.frames))
        return self.frames[self.base:window_end]

    def send_window(self) -> List[Frame]:
        """
        Transmit all frames currently eligible within the sliding window.

        Marks newly transmitted frames with status 'transmitted' and records them
        in transmitted_frames. Advances next_sequence accordingly. Does not automatically ACK.

        :return: List of Frame objects that were transmitted in this operation.
        """
        eligible_frames: List[Frame] = []
        window_end = min(self.base + self.window_size, len(self.frames))

        for idx in range(self.next_sequence, window_end):
            frame = self.frames[idx]
            frame.update_status("transmitted")
            self.transmitted_frames.add(frame.sequence_number)
            eligible_frames.append(frame)

        self.next_sequence = max(self.next_sequence, window_end)
        return eligible_frames

    def acknowledge(self, sequence_number: int) -> None:
        """
        Process an acknowledgement (ACK) for a specific frame sequence number.

        Advances the window base only when all prior frames have been acknowledged.
        Duplicate ACKs are safely ignored without corrupting state.

        :param sequence_number: Sequence number of the acknowledged frame.
        :raises ValueError: If the sequence number does not correspond to any known frame.
        """
        valid_seqs = {f.sequence_number for f in self.frames}
        if sequence_number not in valid_seqs:
            raise ValueError(f"Cannot acknowledge non-existent sequence number {sequence_number}.")

        # If already acknowledged, ignore duplicate ACK safely
        if sequence_number in self.acknowledged_frames:
            return

        # Mark as acknowledged
        self.acknowledged_frames.add(sequence_number)

        # Locate frame and update its status
        for f in self.frames:
            if f.sequence_number == sequence_number:
                f.update_status("acknowledged")
                break

        # Advance window base while the frame at the current base is acknowledged
        while self.base < len(self.frames) and self.frames[self.base].sequence_number in self.acknowledged_frames:
            self.base += 1

    def get_base(self) -> int:
        """
        Return the current base sequence index.

        :return: Integer base index.
        """
        return self.base

    def get_next_sequence(self) -> int:
        """
        Return the next frame sequence index eligible for transmission.

        :return: Integer next_sequence index.
        """
        return self.next_sequence

    def is_complete(self) -> bool:
        """
        Check if all frames in the stream have been successfully acknowledged.

        :return: True if all frames are acknowledged, False otherwise.
        """
        if not self.frames:
            return True
        return len(self.acknowledged_frames) == len(self.frames)

    def get_unacknowledged_frames(self) -> List[Frame]:
        """
        Return frames that have been transmitted but have not yet been acknowledged.

        :return: List of transmitted, unacknowledged Frame objects.
        """
        return [
            f for f in self.frames
            if f.sequence_number in self.transmitted_frames
            and f.sequence_number not in self.acknowledged_frames
        ]

    def get_window_state(self) -> Dict[str, Any]:
        """
        Return a structured dictionary detailing the current sliding window state.

        :return: Dictionary with base, next_sequence, window_size, current_window,
                 acknowledged_frames, and unacknowledged_frames.
        """
        current_win = self.get_current_window()
        unacked = self.get_unacknowledged_frames()

        return {
            "base": self.base,
            "next_sequence": self.next_sequence,
            "window_size": self.window_size,
            "current_window": [f.sequence_number for f in current_win],
            "acknowledged_frames": sorted(list(self.acknowledged_frames)),
            "unacknowledged_frames": [f.sequence_number for f in unacked],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Return dictionary representation of sliding window state."""
        return self.get_window_state()

    # Compatibility Helpers for Go-Back-N Protocol Integration
    def can_send(self) -> bool:
        """Check if sliding window allows transmission of more frames."""
        unacked = [f for f in self.frames if f.sequence_number not in self.acknowledged_frames and f.sequence_number in self.transmitted_frames]
        return len(unacked) < self.window_size

    def add_frame(self, frame: Frame) -> bool:
        """Add a frame to the transmission buffer and transmit if window permits."""
        if not isinstance(frame, Frame):
            raise TypeError("Expected Frame object.")
        if frame not in self.frames:
            if frame.sequence_number == 0 and len(self.frames) > 0:
                frame.sequence_number = len(self.frames)
            self.frames.append(frame)
        if self.can_send():
            frame.update_status("transmitted")
            self.transmitted_frames.add(frame.sequence_number)
            self.next_sequence = max(self.next_sequence, frame.sequence_number + 1)
            return True
        return False

    def process_ack(self, ack_num: int) -> int:
        """Cumulative ACK helper for GBN."""
        initial_acked = len(self.acknowledged_frames)
        for seq in range(self.base, ack_num + 1):
            if seq in {f.sequence_number for f in self.frames}:
                self.acknowledge(seq)
        return len(self.acknowledged_frames) - initial_acked

    def get_unacked_frames(self) -> List[Frame]:
        """Alias for get_unacknowledged_frames."""
        return self.get_unacknowledged_frames()

    def reset_next_seq_to_base(self) -> None:
        """Reset next_sequence back to base for GBN timeout rollback."""
        self.next_sequence = self.base

    def __repr__(self) -> str:
        return (
            f"<SlidingWindow base={self.base} next_seq={self.next_sequence} "
            f"size={self.window_size} acked={len(self.acknowledged_frames)}/{len(self.frames)}>"
        )
