"""Migração única: lê os JSONs locais antigos (data/) e grava no Supabase via storage.py.
Rode manualmente uma vez, depois que as tabelas do Supabase existirem e
.streamlit/secrets.toml estiver preenchido. Não faz parte do app em execução."""
import json
import os

import storage

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _ler_json_local(nome_arquivo, padrao):
    caminho = os.path.join(DATA_DIR, nome_arquivo)
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config_local = _ler_json_local("config.json", dict(storage.CONFIG_PADRAO))
    registros_local = _ler_json_local("registros.json", {})
    composicao_local = _ler_json_local("composicao_corporal.json", {})

    storage.salvar_config(config_local)
    storage.salvar_registros(registros_local)
    storage.salvar_composicao(composicao_local)

    print(f"Config migrado: basal={config_local.get('basal')}")
    print(f"{len(registros_local)} registro(s) diário(s) migrado(s): {sorted(registros_local.keys())}")
    print(f"{len(composicao_local)} medição(ões) de composição migrada(s): {sorted(composicao_local.keys())}")


if __name__ == "__main__":
    main()
