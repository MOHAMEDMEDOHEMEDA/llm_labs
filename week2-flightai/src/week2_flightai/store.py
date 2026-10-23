"""Fares and bookings in SQLite. All SQL is parameterised; nothing the model says is
interpolated into a query."""

from __future__ import annotations

import secrets
import sqlite3
import string
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

# Return fares in USD, from the course's examples.
SEED_FARES = {"london": 799, "paris": 899, "tokyo": 1420, "berlin": 499, "sydney": 2999}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fares (
    city TEXT PRIMARY KEY,
    price_usd INTEGER NOT NULL CHECK (price_usd > 0)
);
CREATE TABLE IF NOT EXISTS bookings (
    ref TEXT PRIMARY KEY,
    city TEXT NOT NULL REFERENCES fares(city),
    passenger TEXT NOT NULL,
    price_usd INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class BookingError(Exception):
    """A booking action that cannot be done; the message is safe to show customers."""


@dataclass(frozen=True)
class Booking:
    ref: str
    city: str
    passenger: str
    price_usd: int
    status: str


def normalise_city(city: str) -> str:
    return " ".join(city.strip().lower().split())


class FareStore:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> closing[sqlite3.Connection]:
        # One short-lived connection per call: Gradio runs handlers on worker threads,
        # and sqlite3 connections must not be shared across threads.
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA foreign_keys = ON")
        return closing(conn)

    def seed(self, fares: dict[str, int] = SEED_FARES) -> None:
        with self._connect() as conn, conn:
            conn.executemany(
                "INSERT INTO fares (city, price_usd) VALUES (?, ?) "
                "ON CONFLICT(city) DO UPDATE SET price_usd = excluded.price_usd",
                [(normalise_city(c), p) for c, p in fares.items()],
            )

    def fare(self, city: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT price_usd FROM fares WHERE city = ?", (normalise_city(city),)
            ).fetchone()
        return row[0] if row else None

    def destinations(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT city FROM fares ORDER BY city").fetchall()
        return [r[0].title() for r in rows]

    def request_booking(self, city: str, passenger: str) -> Booking:
        """Create a pending booking. Only confirm() turns it into a real one."""
        price = self.fare(city)
        if price is None:
            raise BookingError(f"We don't fly to {city.strip()}.")
        passenger = " ".join(passenger.split())
        if not passenger:
            raise BookingError("A passenger name is needed to book.")
        booking = Booking(_new_ref(), normalise_city(city), passenger, price, "pending")
        with self._connect() as conn, conn:
            conn.execute(
                "INSERT INTO bookings (ref, city, passenger, price_usd, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (booking.ref, booking.city, booking.passenger, booking.price_usd, booking.status),
            )
        return booking

    def booking(self, ref: str) -> Booking | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ref, city, passenger, price_usd, status FROM bookings WHERE ref = ?",
                (ref,),
            ).fetchone()
        return Booking(*row) if row else None

    def pending(self) -> list[Booking]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ref, city, passenger, price_usd, status FROM bookings "
                "WHERE status = 'pending' ORDER BY created_at, ref"
            ).fetchall()
        return [Booking(*r) for r in rows]

    def confirm(self, ref: str) -> Booking:
        return self._transition(ref, "confirmed")

    def cancel(self, ref: str) -> Booking:
        return self._transition(ref, "cancelled")

    def _transition(self, ref: str, status: str) -> Booking:
        with self._connect() as conn, conn:
            changed = conn.execute(
                "UPDATE bookings SET status = ? WHERE ref = ? AND status = 'pending'",
                (status, ref),
            ).rowcount
        booking = self.booking(ref)
        if booking is None:
            raise BookingError(f"No booking with reference {ref}.")
        if not changed:
            raise BookingError(f"Booking {ref} is already {booking.status}.")
        return booking


def _new_ref() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "FA-" + "".join(secrets.choice(alphabet) for _ in range(6))
