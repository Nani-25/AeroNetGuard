"""
Frame data model for AeroNetGuard.

This module defines the Frame data structure representing an individual unit
of data link transmission generated from a Packet.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import uuid


@dataclass
class Frame:
    """
    Data Link Layer Frame model.

    Represents a discrete transmission frame encapsulating a segment of packet payload,
    sequence numbers, CRC checksum, and retransmission telemetry.
    """

    packet_id: str
    source: str
    destination: str
    payload: str
    frame_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sequence_number: int = 0
    crc: Optional[Any] = None
    crc_status: str = "not_checked"
    status: str = "created"
    retransmission_count: int = 0

    VALID_CRC_STATUSES = {"not_checked", "valid", "invalid"}

    def __post_init__(self) -> None:
        """Validate frame fields upon instantiation."""
        self.validate()

    def validate(self) -> None:
        """
        Validate frame attributes.

        :raises ValueError: If IDs, source, or destination are empty, or counts are negative.
        :raises TypeError: If payload is not a string, or numbers are not integers.
        """
        if not isinstance(self.packet_id, str) or not self.packet_id.strip():
            raise ValueError("Frame packet_id cannot be empty.")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Frame source cannot be empty.")
        if not isinstance(self.destination, str) or not self.destination.strip():
            raise ValueError("Frame destination cannot be empty.")
        if not isinstance(self.payload, str):
            raise TypeError("Frame payload must be a string.")
        if type(self.sequence_number) is not int:
            raise TypeError("Frame sequence_number must be an integer.")
        if self.sequence_number < 0:
            raise ValueError("Frame sequence_number cannot be negative.")
        if type(self.retransmission_count) is not int:
            raise TypeError("Frame retransmission_count must be an integer.")
        if self.retransmission_count < 0:
            raise ValueError("Frame retransmission_count cannot be negative.")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Frame status cannot be empty.")

    def set_crc(self, crc: Any) -> None:
        """
        Store the calculated CRC value for this frame.

        :param crc: CRC integer, hex string, or bitstring representation.
        """
        self.crc = crc

    def set_crc_status(self, status: str) -> None:
        """
        Update the CRC verification status.

        :param status: 'not_checked', 'valid', or 'invalid'.
        :raises ValueError: If status is not a recognized CRC status.
        """
        if status not in self.VALID_CRC_STATUSES:
            raise ValueError(
                f"Invalid CRC status '{status}'. Must be one of {self.VALID_CRC_STATUSES}."
            )
        self.crc_status = status

    def update_status(self, status: str) -> None:
        """
        Update current transmission status of the frame.

        :param status: New status (e.g. 'created', 'transmitted', 'acked', 'corrupted', 'lost').
        :raises ValueError: If status is empty.
        """
        if not isinstance(status, str) or not status.strip():
            raise ValueError("Frame status cannot be empty.")
        self.status = status

    def increment_retransmission(self) -> int:
        """
        Increment the retransmission counter by 1.

        :return: Updated retransmission count.
        """
        self.retransmission_count += 1
        return self.retransmission_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize frame attributes to a JSON-compatible dictionary.

        :return: Dict representation of the frame.
        """
        return {
            "frame_id": self.frame_id,
            "packet_id": self.packet_id,
            "sequence_number": self.sequence_number,
            "payload": self.payload,
            "source": self.source,
            "destination": self.destination,
            "crc": self.crc,
            "crc_status": self.crc_status,
            "status": self.status,
            "retransmission_count": self.retransmission_count,
        }

    def __repr__(self) -> str:
        return (
            f"<Frame id={self.frame_id[:8]} pkt={self.packet_id[:8]} "
            f"seq={self.sequence_number} status={self.status} crc_status={self.crc_status}>"
        )
