"""Общий SQLite-бюджет. Инициализацию выполняет оператор явно."""
from contextlib import contextmanager
import math
from pathlib import Path
import sqlite3
import uuid

def amount(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Некорректная стоимость')
    return float(value)

class Budget:
    def __init__(self, path: str):
        target = Path(path)
        if not target.is_absolute() or not target.is_file(): raise ValueError('Нужен существующий абсолютный ledger path')
        self.path = target
        with self.connect() as db:
            if db.execute('SELECT total FROM config').fetchall() != [(1.0,)]: raise ValueError('Неизвестная конфигурация бюджета')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(f'file:{self.path}?mode=rw',uri=True,timeout=15)
        try:
            with db: yield db
        finally:
            db.close()
    @staticmethod
    def initialize(path: str):
        target = Path(path)
        if not target.is_absolute(): raise ValueError('Нужен абсолютный путь')
        # Создание без перезаписи не позволяет случайно сбросить потраченный бюджет.
        with target.open('x'): pass
        db = sqlite3.connect(target)
        try:
            with db:
                db.executescript('CREATE TABLE config(total REAL NOT NULL); INSERT INTO config VALUES(1.0); CREATE TABLE reservations(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, reserved REAL NOT NULL, actual REAL, settled INTEGER NOT NULL DEFAULT 0);')
        finally:
            db.close()
    def reserve(self, run_id: str, max_cost_usd: float) -> str:
        ceiling = amount(max_cost_usd)
        if not isinstance(run_id,str) or not run_id: raise ValueError('Нужен run_id')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            spent = db.execute('SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM reservations').fetchone()[0]
            if spent + ceiling > 1.0: raise RuntimeError('Общий бюджет $1 исчерпан')
            reservation = str(uuid.uuid4())
            db.execute('INSERT INTO reservations(id,run_id,reserved) VALUES(?,?,?)',(reservation,run_id,ceiling))
            return reservation
    def settle(self, reservation_id: str, actual_cost_usd: float | None) -> None:
        actual = None if actual_cost_usd is None else amount(actual_cost_usd)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT settled FROM reservations WHERE id=?',(reservation_id,)).fetchone()
            if row is None: raise ValueError('Неизвестный резерв')
            if not row[0]: db.execute('UPDATE reservations SET actual=?,settled=1 WHERE id=?',(actual,reservation_id))
