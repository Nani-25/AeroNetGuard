"""
Framing algorithm module for AeroNetGuard.

This module provides the FramingEngine responsible for converting logical Packet
payloads into discrete Frame objects for reliable transmission across the data link layer,
as well as ByteStuffing for physical character-oriented frame delimitation.
"""

from typing import List, Union
from simulation.packet import Packet
from simulation.frame import Frame

FLAG: str = "~"  # Frame boundary marker (0x7E ascii equivalence '~')
ESC: str = "}"   # Escape byte marker (0x7D ascii equivalence '}')


class FramingEngine:
    """
    Data Link Layer Framing Engine.

    Converts a network-layer Packet into a sequence of data-link-layer Frame objects
    using word-based token framing.
    """

    def create_frames(self, packet: Packet) -> List[Frame]:
        """
        Convert a Packet's payload into a list of Frame objects.

        Splits the payload on whitespace to create individual frames with sequential
        zero-indexed sequence numbers. Updates the packet's status to 'framed' upon success.

        :param packet: Packet object to frame.
        :return: List of Frame objects preserving original word sequence.
        :raises TypeError: If the input is not a Packet instance.
        :raises ValueError: If the packet payload is empty or contains only whitespace.
        """
        if not isinstance(packet, Packet):
            raise TypeError("create_frames() expects a Packet object.")

        if not packet.payload or not packet.payload.strip():
            raise ValueError("Packet payload cannot be empty or whitespace only.")

        words = packet.payload.split()
        if not words:
            raise ValueError("Packet payload yielded zero frames after tokenization.")

        frames: List[Frame] = []
        for seq_num, word in enumerate(words):
            frame = Frame(
                packet_id=packet.packet_id,
                source=packet.source,
                destination=packet.destination,
                payload=word,
                sequence_number=seq_num,
            )
            frames.append(frame)

        # Update packet status after successful frame generation
        packet.update_status("framed")

        return frames

    def get_frame_count(self, frames: List[Frame]) -> int:
        """
        Return the total number of frames in a frame collection.

        :param frames: List of Frame objects.
        :return: Integer count of frames.
        """
        return len(frames)


class ByteStuffing:
    """
    Byte Stuffing framing algorithm implementation.

    Encapsulates payload data with start and end FLAG markers.
    Escapes occurrence of FLAG or ESC characters within payload using ESC byte.
    """

    FLAG_CHAR: str = FLAG
    ESC_CHAR: str = ESC

    @classmethod
    def stuff_bytes(cls, payload: Union[str, bytes]) -> Union[str, bytes]:
        if isinstance(payload, bytes):
            flag_b = cls.FLAG_CHAR.encode('utf-8')
            esc_b = cls.ESC_CHAR.encode('utf-8')
            stuffed = payload.replace(esc_b, esc_b + esc_b)
            stuffed = stuffed.replace(flag_b, esc_b + flag_b)
            return flag_b + stuffed + flag_b
        elif isinstance(payload, str):
            stuffed = payload.replace(cls.ESC_CHAR, cls.ESC_CHAR + cls.ESC_CHAR)
            stuffed = stuffed.replace(cls.FLAG_CHAR, cls.ESC_CHAR + cls.FLAG_CHAR)
            return f"{cls.FLAG_CHAR}{stuffed}{cls.FLAG_CHAR}"
        else:
            raise TypeError("Payload must be either str or bytes.")

    @classmethod
    def destuff_bytes(cls, framed_data: Union[str, bytes]) -> Union[str, bytes]:
        if isinstance(framed_data, bytes):
            flag_b = cls.FLAG_CHAR.encode('utf-8')
            esc_b = cls.ESC_CHAR.encode('utf-8')
            if len(framed_data) < 2 or not (framed_data.startswith(flag_b) and framed_data.endswith(flag_b)):
                raise ValueError("Invalid frame: missing start or end FLAG delimiter.")
            inner = framed_data[len(flag_b):-len(flag_b)]
            res = bytearray()
            i = 0
            n = len(inner)
            while i < n:
                if inner[i:i+len(esc_b)] == esc_b:
                    if i + len(esc_b) < n:
                        next_char = inner[i+len(esc_b):i+2*len(esc_b)]
                        if next_char == flag_b:
                            res.extend(flag_b)
                            i += 2 * len(esc_b)
                            continue
                        elif next_char == esc_b:
                            res.extend(esc_b)
                            i += 2 * len(esc_b)
                            continue
                res.append(inner[i])
                i += 1
            return bytes(res)
        elif isinstance(framed_data, str):
            if len(framed_data) < 2 or not (framed_data.startswith(cls.FLAG_CHAR) and framed_data.endswith(cls.FLAG_CHAR)):
                raise ValueError("Invalid frame: missing start or end FLAG delimiter.")
            inner = framed_data[1:-1]
            res = []
            i = 0
            n = len(inner)
            while i < n:
                if inner[i] == cls.ESC_CHAR and i + 1 < n:
                    next_char = inner[i + 1]
                    if next_char in (cls.FLAG_CHAR, cls.ESC_CHAR):
                        res.append(next_char)
                        i += 2
                        continue
                res.append(inner[i])
                i += 1
            return "".join(res)
        else:
            raise TypeError("Framed data must be either str or bytes.")


def create_frame_data(payload: str) -> str:
    return ByteStuffing.stuff_bytes(payload)


def extract_frame_data(framed_payload: str) -> str:
    return ByteStuffing.destuff_bytes(framed_payload)
