"""
Database connection module
"""
import sqlite3
from typing import Optional
from pathlib import Path
import sys

# backend/ 디렉토리를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH_NEWS, DB_PATH_SUPPLY_CHAIN, DB_PATH_ONTOLOGY


class DatabaseConnection:
    """SQLite 데이터베이스 연결 관리"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None

    def __enter__(self):
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row  # dict-like 접근 가능
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()


def get_news_db():
    """뉴스 DB 연결 반환"""
    return DatabaseConnection(DB_PATH_NEWS)


def get_supply_chain_db():
    """공급망 DB 연결 반환"""
    return DatabaseConnection(DB_PATH_SUPPLY_CHAIN)


def get_ontology_db():
    """온톨로지 DB 연결 반환"""
    return DatabaseConnection(DB_PATH_ONTOLOGY)
