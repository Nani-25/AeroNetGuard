"""
CRC error detection module for AeroNetGuard.

This module provides the CRCProcessor class implementing standard CRC-8 error detection
for data-link-layer frames, as well as legacy CRC32 utilities.

Algorithm Specification:
- Standard: CRC-8
- Polynomial: x^8 + x^2 + x + 1 (0x07)
- Initial Value: 0x00
- Final XOR: 0x00
- Representation: Integer (0 to 255)
"""

import binascii
from typing import Union, Optional
from simulation.frame import Frame


class CRCProcessor:
    """
    Cyclic Redundancy Check (CRC-8) Processor.

    Calculates deterministic 8-bit checksums using polynomial division (0x07),
    attaches checksums to data frames, verifies transmission integrity,
    and provides deterministic corruption simulation for testing.
    """

    POLYNOMIAL: int = 0x07
    INITIAL_VALUE: int = 0x00
    FINAL_XOR: int = 0x00

    def calculate_crc(self, data: str) -> int:
        """
        Calculate deterministic CRC-8 checksum for a string payload.

        Performs bitwise division using generator polynomial x^8 + x^2 + x + 1 (0x07).

        :param data: String payload to encode.
        :return: Integer CRC checksum in the range [0, 255].
        :raises TypeError: If data is not a string.
        :raises ValueError: If data is empty or contains only whitespace.
        """
        if not isinstance(data, str):
            raise TypeError("calculate_crc() expects a string input.")

        if not data or not data.strip():
            raise ValueError("Data cannot be empty or whitespace only for CRC calculation.")

        crc = self.INITIAL_VALUE
        byte_data = data.encode("utf-8")

        for byte in byte_data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ self.POLYNOMIAL) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF

        return crc ^ self.FINAL_XOR

    def calculate_frame_crc(self, frame: Frame) -> int:
        """
        Calculate CRC from the frame payload and attach it to the Frame object.
        Leaves frame.crc_status as 'not_checked'.

        :param frame: Frame object to process.
        :return: Integer CRC checksum attached to the frame.
        :raises TypeError: If frame is not a Frame object.
        """
        if not isinstance(frame, Frame):
            raise TypeError("calculate_frame_crc() expects a Frame object.")

        crc = self.calculate_crc(frame.payload)
        frame.set_crc(crc)
        frame.crc_status = "not_checked"
        return crc

    def verify_frame(self, frame: Frame) -> bool:
        """
        Verify the integrity of a Frame by recalculating the payload CRC
        and comparing it against frame.crc. Updates frame.crc_status.

        :param frame: Frame object to verify.
        :return: True if checksums match, False otherwise.
        :raises TypeError: If frame is not a Frame object.
        :raises ValueError: If frame.crc has not been calculated.
        """
        if not isinstance(frame, Frame):
            raise TypeError("verify_frame() expects a Frame object.")

        if frame.crc is None:
            raise ValueError("Frame does not have a calculated CRC to verify.")

        recalculated_crc = self.calculate_crc(frame.payload)
        is_valid = recalculated_crc == frame.crc

        frame.set_crc_status("valid" if is_valid else "invalid")
        return is_valid

    def verify_crc(self, data: str, expected_crc: int) -> bool:
        """
        Low-level utility to verify string data against an expected CRC-8 integer.

        :param data: String payload.
        :param expected_crc: Expected CRC integer (0 to 255).
        :return: True if calculated CRC equals expected_crc, False otherwise.
        :raises ValueError: If expected_crc is not in [0, 255].
        """
        if not isinstance(expected_crc, int) or expected_crc < 0 or expected_crc > 255:
            raise ValueError("expected_crc must be an integer between 0 and 255.")

        calculated = self.calculate_crc(data)
        return calculated == expected_crc

    def corrupt_frame(self, frame: Frame) -> None:
        """
        Deliberately modify a frame's payload to simulate bit-level or character corruption
        without recalculating its CRC.

        :param frame: Frame object to corrupt.
        :raises TypeError: If frame is not a Frame object.
        :raises ValueError: If frame payload is empty.
        """
        if not isinstance(frame, Frame):
            raise TypeError("corrupt_frame() expects a Frame object.")

        if not frame.payload:
            raise ValueError("Cannot corrupt a frame with an empty payload.")

        original = frame.payload
        last_char = original[-1]
        corrupted_char = "X" if last_char != "X" else "Y"
        frame.payload = original[:-1] + corrupted_char


class CRC32:
    """Legacy 32-bit CRC helper for backwards compatibility."""

    @classmethod
    def calculate(cls, data: Union[str, bytes]) -> int:
        if isinstance(data, str):
            raw_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            raw_bytes = data
        else:
            raise TypeError("Data for CRC calculation must be str or bytes.")
        return binascii.crc32(raw_bytes) & 0xFFFFFFFF

    @classmethod
    def calculate_hex(cls, data: Union[str, bytes]) -> str:
        return f"0x{cls.calculate(data):08x}"

    @classmethod
    def verify(cls, data: Union[str, bytes], expected_crc: Union[int, str]) -> bool:
        computed = cls.calculate(data)
        if isinstance(expected_crc, str):
            try:
                expected_int = int(expected_crc, 16) if expected_crc.lower().startswith("0x") else int(expected_crc)
            except ValueError:
                return False
        elif isinstance(expected_crc, int):
            expected_int = expected_crc
        else:
            return False
        return (computed & 0xFFFFFFFF) == (expected_int & 0xFFFFFFFF)

    @classmethod
    def corrupt_data(cls, data: str, position: int = 0) -> str:
        if not data:
            return "X"
        pos = position % len(data)
        return data[:pos] + chr(ord(data[pos]) ^ 0x01) + data[pos + 1:]


def generate_crc(data: Union[str, bytes]) -> int:
    return CRC32.calculate(data)


def verify_crc(data: Union[str, bytes], expected_crc: Union[int, str]) -> bool:
    return CRC32.verify(data, expected_crc)


def check_frame_crc(frame: Frame) -> bool:
    if frame.crc is None:
        frame.set_crc_status("invalid")
        return False
    is_valid = CRC32.verify(frame.payload, frame.crc)
    frame.set_crc_status("valid" if is_valid else "invalid")
    return is_valid
