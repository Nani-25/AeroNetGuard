"""
Transmission error and packet degradation generator for AeroNetGuard.

Simulates physical layer channel flaws including random bit corruption,
frame loss, and delay simulation based on configurable probabilities.
"""

import random
from typing import Optional
from algorithms.crc import CRC32
from simulation.frame import Frame


class NetworkImpairmentGenerator:
    """
    Stochastic Network Degradation Generator.

    Injects packet drops, bit flips, and payload corruptions into transmitted frames
    to test the resilience of Go-Back-N ARQ and CRC error detection algorithms.
    """

    def __init__(
        self,
        loss_rate: float = 0.0,
        corruption_rate: float = 0.0,
        seed: Optional[int] = None,
    ) -> None:
        """
        Initialize network error generator.

        :param loss_rate: Probability of frame loss (0.0 to 1.0).
        :param corruption_rate: Probability of frame payload corruption (0.0 to 1.0).
        :param seed: Optional random seed for reproducible testing.
        :raises ValueError: If probabilities are outside [0.0, 1.0].
        """
        if not (0.0 <= loss_rate <= 1.0):
            raise ValueError("loss_rate must be between 0.0 and 1.0.")
        if not (0.0 <= corruption_rate <= 1.0):
            raise ValueError("corruption_rate must be between 0.0 and 1.0.")

        self.loss_rate: float = loss_rate
        self.corruption_rate: float = corruption_rate
        self.rng: random.Random = random.Random(seed)

    def set_rates(self, loss_rate: float, corruption_rate: float) -> None:
        """
        Update loss and corruption probability rates.

        :param loss_rate: New loss rate.
        :param corruption_rate: New corruption rate.
        """
        if not (0.0 <= loss_rate <= 1.0):
            raise ValueError("loss_rate must be between 0.0 and 1.0.")
        if not (0.0 <= corruption_rate <= 1.0):
            raise ValueError("corruption_rate must be between 0.0 and 1.0.")

        self.loss_rate = loss_rate
        self.corruption_rate = corruption_rate

    def should_drop(self) -> bool:
        """Determine whether current frame should be dropped in transit."""
        if self.loss_rate <= 0.0:
            return False
        return self.rng.random() < self.loss_rate

    def should_corrupt(self) -> bool:
        """Determine whether current frame should experience payload corruption."""
        if self.corruption_rate <= 0.0:
            return False
        return self.rng.random() < self.corruption_rate

    def corrupt_frame(self, frame: Frame) -> Frame:
        """
        Infect frame with bit corruption (flips a bit in payload without recomputing CRC).

        :param frame: Frame object to corrupt.
        :return: Corrupted Frame instance.
        """
        corrupted_payload = CRC32.corrupt_data(frame.payload, position=0)
        frame.payload = corrupted_payload
        frame.update_status("corrupted")
        return frame
