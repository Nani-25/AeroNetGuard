"""
Unit tests for CRCProcessor in algorithms.crc module.

Validates:
- TEST 1: Deterministic CRC calculation
- TEST 2: Different payloads produce distinct CRC values
- TEST 3: Frame CRC attachment and calculation
- TEST 4: Verification of intact/valid frame
- TEST 5: Verification of corrupted frame fails
- TEST 6: Low-level string payload CRC verification
- TEST 7: Empty string payload raises ValueError
- TEST 8: Whitespace-only string payload raises ValueError
- TEST 9: Non-string payload raises TypeError
- TEST 10: Verification of frame without CRC raises ValueError
- TEST 11: Frame corruption modifies payload content
- TEST 12: Corrupted frame invalidates stored CRC
- TEST 13: CRC status transitions ('not_checked' -> 'valid'/'invalid')
- TEST 14: Known CRC-8 test vector validation ('123456789' -> 0xF4 / 244)
"""

import pytest
from simulation.frame import Frame
from algorithms.crc import CRCProcessor, CRC32, generate_crc, verify_crc, check_frame_crc


@pytest.fixture
def crc_processor():
    """Fixture providing a fresh CRCProcessor instance."""
    return CRCProcessor()


@pytest.fixture
def sample_frame():
    """Fixture providing a sample unverified Frame."""
    return Frame(
        packet_id="pkt-100",
        source="Security",
        destination="Baggage",
        payload="SECURITY",
        sequence_number=0,
    )


def test_1_deterministic_crc(crc_processor):
    """TEST 1: Calculate CRC twice for 'SECURITY'. Both values must be identical."""
    crc1 = crc_processor.calculate_crc("SECURITY")
    crc2 = crc_processor.calculate_crc("SECURITY")
    assert crc1 == crc2
    assert isinstance(crc1, int)
    assert 0 <= crc1 <= 255


def test_2_different_data(crc_processor):
    """TEST 2: Calculate CRC for 'SECURITY' and 'BAGGAGE'. Values must differ."""
    crc_sec = crc_processor.calculate_crc("SECURITY")
    crc_bag = crc_processor.calculate_crc("BAGGAGE")
    assert crc_sec != crc_bag


def test_3_frame_crc_calculation(crc_processor, sample_frame):
    """TEST 3: Calculate Frame CRC and verify attachment."""
    assert sample_frame.crc is None
    crc = crc_processor.calculate_frame_crc(sample_frame)
    assert sample_frame.crc is not None
    assert sample_frame.crc == crc
    assert sample_frame.crc_status == "not_checked"


def test_4_valid_frame(crc_processor, sample_frame):
    """TEST 4: Calculate Frame CRC, then verify intact frame."""
    crc_processor.calculate_frame_crc(sample_frame)
    is_valid = crc_processor.verify_frame(sample_frame)

    assert is_valid is True
    assert sample_frame.crc_status == "valid"


def test_5_corrupted_frame(crc_processor, sample_frame):
    """TEST 5: Calculate Frame CRC, corrupt payload, and verify failure."""
    crc_processor.calculate_frame_crc(sample_frame)
    crc_processor.corrupt_frame(sample_frame)
    is_valid = crc_processor.verify_frame(sample_frame)

    assert is_valid is False
    assert sample_frame.crc_status == "invalid"


def test_6_low_level_verification(crc_processor):
    """TEST 6: Low-level verification with expected CRC value."""
    crc = crc_processor.calculate_crc("SECURITY")
    assert crc_processor.verify_crc("SECURITY", crc) is True
    assert crc_processor.verify_crc("BAGGAGE", crc) is False


def test_7_empty_data(crc_processor):
    """TEST 7: Empty string payload raises ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        crc_processor.calculate_crc("")


def test_8_whitespace_data(crc_processor):
    """TEST 8: Whitespace-only string payload raises ValueError."""
    with pytest.raises(ValueError, match="cannot be empty or whitespace only"):
        crc_processor.calculate_crc("   ")


def test_9_invalid_data_type(crc_processor):
    """TEST 9: Non-string input raises TypeError."""
    with pytest.raises(TypeError, match="expects a string input"):
        crc_processor.calculate_crc(12345)


def test_10_frame_without_crc(crc_processor, sample_frame):
    """TEST 10: Verifying a frame without a calculated CRC raises ValueError."""
    with pytest.raises(ValueError, match="does not have a calculated CRC"):
        crc_processor.verify_frame(sample_frame)


def test_11_corruption_changes_payload(crc_processor, sample_frame):
    """TEST 11: corrupt_frame alters the frame payload string."""
    original_payload = sample_frame.payload
    crc_processor.corrupt_frame(sample_frame)
    assert sample_frame.payload != original_payload


def test_12_corruption_invalidates_crc(crc_processor, sample_frame):
    """TEST 12: Corrupting frame payload invalidates existing CRC."""
    crc_processor.calculate_frame_crc(sample_frame)
    crc_processor.corrupt_frame(sample_frame)
    assert crc_processor.verify_frame(sample_frame) is False


def test_13_crc_status_lifecycle(crc_processor, sample_frame):
    """TEST 13: Track status transitions ('not_checked' -> 'valid'/'invalid')."""
    assert sample_frame.crc_status == "not_checked"

    crc_processor.calculate_frame_crc(sample_frame)
    assert sample_frame.crc_status == "not_checked"

    crc_processor.verify_frame(sample_frame)
    assert sample_frame.crc_status == "valid"

    crc_processor.corrupt_frame(sample_frame)
    crc_processor.verify_frame(sample_frame)
    assert sample_frame.crc_status == "invalid"


def test_14_known_crc8_vector(crc_processor):
    """
    TEST 14: Known test vector validation for standard CRC-8.
    Polynomial: x^8 + x^2 + x + 1 (0x07), init 0x00, final XOR 0x00.
    Input '123456789' -> 0xF4 (244 decimal).
    """
    known_input = "123456789"
    expected_crc = 0xF4  # 244 decimal
    calculated_crc = crc_processor.calculate_crc(known_input)
    assert calculated_crc == expected_crc
    assert calculated_crc == 244
    assert crc_processor.verify_crc(known_input, expected_crc) is True


def test_legacy_crc32_compatibility():
    """Verify legacy CRC32 calculation."""
    data = "Control Tower Clearance Data"
    crc_int = CRC32.calculate(data)
    assert isinstance(crc_int, int)
    assert CRC32.calculate_hex(data).startswith("0x")
