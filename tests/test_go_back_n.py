"""
Test suite for Go-Back-N ARQ protocol (algorithms/go_back_n.py).
"""

import pytest
from algorithms.go_back_n import GBNSender, GBNReceiver, GoBackNProtocol
from algorithms.crc import CRC32
from simulation.frame import Frame


def test_gbn_in_order_delivery():
    sender = GBNSender(window_size=3)
    receiver = GBNReceiver()

    frames = [
        Frame(packet_id="p1", source="Control Tower", destination="Security", payload=f"Msg-{i}")
        for i in range(3)
    ]

    for f in frames:
        sender.transmit_frame(f)

    # Receive frame 0
    ack, valid, reason = receiver.receive_frame(frames[0])
    assert valid is True
    assert ack == 0
    assert reason == "accepted"
    sender.process_ack(ack)

    assert sender.window.send_base == 1
    assert len(receiver.received_frames) == 1


def test_gbn_corrupted_frame_discard():
    receiver = GBNReceiver()
    f0 = Frame(packet_id="p1", source="A", destination="B", payload="Clear Data", sequence_number=0)
    f0.set_crc(CRC32.calculate(f0.payload))

    # Accept f0
    ack, valid, _ = receiver.receive_frame(f0)
    assert valid is True

    # f1 with corrupted CRC
    f1 = Frame(packet_id="p1", source="A", destination="B", payload="Corrupted Data", sequence_number=1)
    f1.set_crc(999999999)  # Invalid CRC

    ack, valid, reason = receiver.receive_frame(f1)
    assert valid is False
    assert reason == "crc_error"
    assert ack == 0  # Highest in-order ACK remains 0


def test_gbn_out_of_order_discard():
    receiver = GBNReceiver()

    # Frame 1 arrives before Frame 0
    f1 = Frame(packet_id="p1", source="A", destination="B", payload="Msg1", sequence_number=1)
    f1.set_crc(CRC32.calculate(f1.payload))

    ack, valid, reason = receiver.receive_frame(f1)
    assert valid is False
    assert reason == "out_of_order"
    assert ack is None  # No valid frames received yet


def test_gbn_timeout_rollback():
    sender = GBNSender(window_size=4)
    f0 = Frame(packet_id="p1", source="A", destination="B", payload="D0")
    f1 = Frame(packet_id="p1", source="A", destination="B", payload="D1")

    sender.transmit_frame(f0)
    sender.transmit_frame(f1)

    # Timeout occurs before ACK
    unacked = sender.handle_timeout()
    assert len(unacked) == 2
    assert unacked[0].retransmission_count == 1
    assert unacked[1].retransmission_count == 1
    assert sender.window.next_seq_num == 0
    assert sender.total_retransmissions == 2


def test_gbn_telemetry():
    protocol = GoBackNProtocol(window_size=4)
    telemetry = protocol.get_telemetry()

    assert "window_state" in telemetry
    assert "total_retransmissions" in telemetry
    assert telemetry["delivered_count"] == 0
