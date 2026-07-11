"""Persistência em Postgres (Supabase). Credenciais vêm de st.secrets["postgres"],
configurado em .streamlit/secrets.toml (local) ou nos secrets do Streamlit Community Cloud."""
import json

import psycopg2
import streamlit as st

CONFIG_PADRAO = {
    "perfil": None,
    "basal": None,
    "kcal_por_kg_gordura": 7700,
    "metas_kg": [1, 2, 3, 4, 5, 6],
}


def _conectar():
    cfg = st.secrets["postgres"]
    return psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        sslmode="require",
    )


def carregar_config() -> dict:
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute("select data from config where id = 'singleton'")
        row = cur.fetchone()
    if row is None:
        return dict(CONFIG_PADRAO)
    config = row[0]
    for chave, valor in CONFIG_PADRAO.items():
        config.setdefault(chave, valor)
    return config


def salvar_config(config: dict):
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into config (id, data) values ('singleton', %s) "
            "on conflict (id) do update set data = excluded.data",
            (json.dumps(config),),
        )
        conn.commit()


def carregar_registros() -> dict:
    """Retorna dict {data_iso: {consumido, treino_bruto, minutos_treino, ...}}"""
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute("select data_iso, data from registros")
        rows = cur.fetchall()
    return {data_iso: data for data_iso, data in rows}


def salvar_registros(registros: dict):
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute("select data_iso from registros")
        existentes = {row[0] for row in cur.fetchall()}
        for chave in existentes - set(registros.keys()):
            cur.execute("delete from registros where data_iso = %s", (chave,))
        for chave, valor in registros.items():
            cur.execute(
                "insert into registros (data_iso, data) values (%s, %s) "
                "on conflict (data_iso) do update set data = excluded.data",
                (chave, json.dumps(valor)),
            )
        conn.commit()


def carregar_composicao() -> dict:
    """Retorna dict {data_iso: {peso, percentual_gordura, percentual_massa_magra}}"""
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute("select data_iso, data from composicao")
        rows = cur.fetchall()
    return {data_iso: data for data_iso, data in rows}


def salvar_composicao(composicao: dict):
    with _conectar() as conn, conn.cursor() as cur:
        cur.execute("select data_iso from composicao")
        existentes = {row[0] for row in cur.fetchall()}
        for chave in existentes - set(composicao.keys()):
            cur.execute("delete from composicao where data_iso = %s", (chave,))
        for chave, valor in composicao.items():
            cur.execute(
                "insert into composicao (data_iso, data) values (%s, %s) "
                "on conflict (data_iso) do update set data = excluded.data",
                (chave, json.dumps(valor)),
            )
        conn.commit()
