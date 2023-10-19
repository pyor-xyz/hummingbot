from decimal import Decimal
from math import exp, log
from typing import List


class Distributions:

    @classmethod
    def linear(cls, n_levels: int, start: float = 0.0, end: float = 1.0) -> List[Decimal]:
        return [Decimal(start) + (Decimal(end) - Decimal(start)) * Decimal(i) / (Decimal(n_levels) - 1) for i in range(n_levels)]

    @classmethod
    def exponential(cls, n_levels: int, initial_value: float = 1.0, base: float = 2.0) -> List[Decimal]:
        return [Decimal(initial_value) * Decimal(base) ** Decimal(i) for i in range(n_levels)]

    @classmethod
    def fibonacci(cls, n_levels: int) -> List[Decimal]:
        fib_sequence = [Decimal("1"), Decimal("1")]
        for i in range(2, n_levels):
            fib_sequence.append(fib_sequence[-1] + fib_sequence[-2])
        return fib_sequence[:n_levels]

    @classmethod
    def logarithmic(cls, n_levels: int, base: float = exp(1), scaling_factor: float = 1.0,
                    initial_value: float = 0.4) -> List[Decimal]:
        translation = Decimal(initial_value) - Decimal(scaling_factor) * Decimal(log(2, base))
        return [Decimal(scaling_factor) * Decimal(log(i + 2, base)) + translation for i in range(n_levels)]

    @classmethod
    def arithmetic(cls, n_levels: int, start: float, increment: float) -> List[Decimal]:
        """
        Generate an arithmetic sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - start: The starting value of the sequence.
        - increment: The constant value to be added in each iteration.

        Returns:
        List[Decimal]: A list containing the generated arithmetic sequence.
        """
        return [Decimal(start) + i * Decimal(increment) for i in range(n_levels)]

    @classmethod
    def geometric(cls, n_levels: int, start: float, ratio: float) -> List[Decimal]:
        """
        Generate a geometric sequence of spreads.

        Parameters:
        - n_levels: The number of spread levels to be generated.
        - start: The starting value of the sequence.
        - ratio: The ratio to multiply the current value in each iteration. Should be greater than 1 for increasing sequence.

        Returns:
        List[Decimal]: A list containing the generated geometric sequence.
        """
        if ratio <= 1:
            raise ValueError(
                "Ratio for modified geometric distribution should be greater than 1 for increasing spreads.")

        return [Decimal(start) * Decimal(ratio) ** Decimal(i) for i in range(n_levels)]
