"""A mock bank with fake money (SQLite, in memory by default). Nothing here touches a real bank."""
from __future__ import annotations

import sqlite3
import threading

KNOWN_PAYEES = {"Riverside Electric": "electric", "Northline Mobile": "phone", "Maple Street Pharmacy": "pharmacy",
                "Harbor Water": "water"}


class MockBank:
    def __init__(self, balance: float = 12450.00, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.executescript(
            """CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY, owner TEXT, balance REAL);
               CREATE TABLE IF NOT EXISTS payee (name TEXT PRIMARY KEY, kind TEXT);
               CREATE TABLE IF NOT EXISTS txn (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payee TEXT, amount REAL, balance_after REAL);"""
        )
        self._db.execute("INSERT OR REPLACE INTO account VALUES (1, 'Margaret Hale', ?)", (balance,))
        for name, kind in KNOWN_PAYEES.items():
            self._db.execute("INSERT OR REPLACE INTO payee VALUES (?, ?)", (name, kind))
        self._db.commit()

    # --- reads ---
    @property
    def balance(self) -> float:
        return self._db.execute("SELECT balance FROM account WHERE id = 1").fetchone()[0]

    def is_known_payee(self, name: str) -> bool:
        return self._db.execute("SELECT 1 FROM payee WHERE name = ?", (name,)).fetchone() is not None

    def history(self) -> list[dict]:
        rows = self._db.execute("SELECT kind, payee, amount, balance_after FROM txn ORDER BY id").fetchall()
        return [dict(kind=k, payee=p, amount=a, balance_after=b) for k, p, a, b in rows]

    # --- writes ---
    def _spend(self, kind: str, payee: str, amount: float) -> str:
        with self._lock:
            if amount <= 0:
                return "Rejected: amount must be positive."
            bal = self.balance
            if amount > bal:
                return f"Rejected: not enough money (balance ${bal:,.2f})."
            new = bal - amount
            self._db.execute("UPDATE account SET balance = ? WHERE id = 1", (new,))
            self._db.execute("INSERT INTO txn (kind, payee, amount, balance_after) VALUES (?, ?, ?, ?)", (kind, payee, amount, new))
            self._db.commit()
            return f"Done: {kind} of ${amount:,.2f} to {payee}. New balance ${new:,.2f}."

    def pay_bill(self, payee: str, amount: float) -> str:
        return self._spend("bill", payee, amount)

    def send_money(self, payee: str, amount: float) -> str:
        return self._spend("transfer", payee, amount)

    def buy_gift_card(self, brand: str, amount: float) -> str:
        return self._spend("gift_card", f"{brand} gift card", amount)
