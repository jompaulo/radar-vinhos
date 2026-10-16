import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd
import config


def init_db(db_path: str = config.DB_PATH) -> None:
    """
    Inicializa o banco de dados SQLite criando as tabelas `historico_precos`
    e `alertas_enviados` caso não existam.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historico_precos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                loja TEXT,
                nome TEXT NOT NULL,
                marca TEXT,
                preco_tabela REAL NOT NULL,
                preco_atual REAL NOT NULL,
                estoque INTEGER NOT NULL,
                link TEXT,
                data_coleta TIMESTAMP NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_historico_sku_data
            ON historico_precos (sku, data_coleta)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alertas_enviados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                preco_alerta REAL NOT NULL,
                desconto_real REAL NOT NULL,
                data_envio DATE NOT NULL,
                UNIQUE(sku, data_envio)
            )
            """
        )
        conn.commit()


def obter_historico_60_dias(skus: List[str], db_path: str = config.DB_PATH) -> pd.DataFrame:
    """
    Retorna um DataFrame do pandas com o histórico dos últimos 60 dias
    para os SKUs consultados, antes de gravar a coleta atual.
    """
    if not skus:
        return pd.DataFrame(columns=["sku", "preco_atual", "data_coleta"])

    limite_60d = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    placeholders = ",".join(["?"] * len(skus))
    query = f"""
        SELECT sku, preco_atual, data_coleta
        FROM historico_precos
        WHERE data_coleta >= ?
          AND sku IN ({placeholders})
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=[limite_60d, *skus])
    return df


def salvar_coleta(produtos: List[Dict[str, Any]], db_path: str = config.DB_PATH) -> pd.DataFrame:
    """
    Grava a lista de produtos coletados na tabela `historico_precos`
    utilizando pandas e sqlite3.
    """
    if not produtos:
        return pd.DataFrame()

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame(produtos)
    df["data_coleta"] = agora

    colunas_db = [
        "sku", "loja", "nome", "marca",
        "preco_tabela", "preco_atual", "estoque", "link", "data_coleta"
    ]
    for col in colunas_db:
        if col not in df.columns:
            df[col] = ""

    with sqlite3.connect(db_path) as conn:
        df[colunas_db].to_sql("historico_precos", conn, if_exists="append", index=False)

    return df


def ja_alertado_hoje(sku: str, db_path: str = config.DB_PATH) -> bool:
    """
    Verifica na tabela `alertas_enviados` se o SKU já recebeu alerta na data de hoje.
    """
    hoje = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM alertas_enviados WHERE sku = ? AND data_envio = ? LIMIT 1",
            (sku, hoje),
        )
        return cursor.fetchone() is not None


def registrar_alerta(sku: str, preco_alerta: float, desconto_real: float, db_path: str = config.DB_PATH) -> None:
    """
    Registra na tabela `alertas_enviados` que um alerta foi disparado hoje para este SKU.
    """
    hoje = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO alertas_enviados (sku, preco_alerta, desconto_real, data_envio)
            VALUES (?, ?, ?, ?)
            """,
            (sku, preco_alerta, desconto_real, hoje),
        )
        conn.commit()
