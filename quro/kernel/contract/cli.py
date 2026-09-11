"""CLI entry point: print the closed Kernel contract laws.

Run with ``make laws`` or::

    PYTHONPATH=src python3 -m quro.kernel.contract.cli
"""

from __future__ import annotations

from .laws import ALL_LAWS


def main() -> None:  # pragma: no cover - CLI helper
    for item in ALL_LAWS:
        print(f"{item.id:<4} {item.name}\n     {item.statement}")


if __name__ == "__main__":  # pragma: no cover
    main()
