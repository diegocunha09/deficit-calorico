import datetime
import json
import math

import altair as alt
import pandas as pd
import streamlit as st

import storage
from calculos import (
    MULTIPLICADORES_ATIVIDADE,
    bmr_harris_benedict,
    bmr_katch_mcardle,
    bmr_mifflin_st_jeor,
    calcular_dia,
    calcular_tdees,
)

st.set_page_config(page_title="Déficit Calórico", page_icon="🔥", layout="wide")

if not st.session_state.get("autenticado"):
    st.title("🔥 Déficit Calórico")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar", type="primary"):
        if senha == st.secrets.get("app_password"):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background-color: rgba(255, 107, 53, 0.08);
        border: 1px solid rgba(255, 107, 53, 0.25);
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stForm"] {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

config = storage.carregar_config()
registros = storage.carregar_registros()
composicao = storage.carregar_composicao()


DATA_FORMATO_STREAMLIT = "DD/MM/YYYY"


def data_para_chave(data: datetime.date) -> str:
    return data.isoformat()


def formatar_data_br(data_iso: str) -> str:
    return datetime.date.fromisoformat(data_iso).strftime("%d/%m/%Y")


def linhas_preenchidas(registros: dict) -> dict:
    return {
        k: v
        for k, v in registros.items()
        if v.get("consumido") is not None
        and v.get("treino_bruto") is not None
        and v.get("minutos_treino") is not None
    }


def calcular_resumo(preenchidos: dict, basal_atual: float) -> dict:
    """Cada dia usa o Basal salvo junto do registro (basal_usado); dias antigos sem esse
    campo (anteriores a essa versão) usam o Basal atual como fallback."""
    dias_calculados = {
        data_str: calcular_dia(
            v["consumido"], v["treino_bruto"], v["minutos_treino"], v.get("basal_usado", basal_atual)
        )
        for data_str, v in preenchidos.items()
    }
    deficit_total = sum(r["deficit_do_dia"] for r in dias_calculados.values())
    return {"dias_calculados": dias_calculados, "deficit_total": deficit_total}


def cor_deficit(valor: float) -> str:
    if valor > 0:
        return "color: #3DDC84; font-weight: 600;"
    if valor < 0:
        return "color: #FF5C5C; font-weight: 600;"
    return ""


def calcular_streak(preenchidos: dict) -> int:
    """Dias consecutivos registrados, terminando hoje ou ontem (senão a sequência está quebrada)."""
    if not preenchidos:
        return 0
    datas = sorted(datetime.date.fromisoformat(d) for d in preenchidos.keys())
    ultimo = datas[-1]
    if (datetime.date.today() - ultimo).days > 1:
        return 0
    streak = 1
    for i in range(len(datas) - 1, 0, -1):
        if (datas[i] - datas[i - 1]).days == 1:
            streak += 1
        else:
            break
    return streak


def media_diaria_deficit(deficit_total: float, dias_registrados: int) -> float:
    return deficit_total / dias_registrados if dias_registrados else 0.0


def prever_data_meta(deficit_total: float, kcal_necessario: float, media_diaria: float):
    """Retorna (data_prevista, dias_restantes) ou (None, None) se não houver previsão possível."""
    if deficit_total >= kcal_necessario:
        return None, 0
    if media_diaria <= 0:
        return None, None
    dias_restantes = math.ceil((kcal_necessario - deficit_total) / media_diaria)
    return datetime.date.today() + datetime.timedelta(days=dias_restantes), dias_restantes


def detectar_alertas(consumido: float, treino_bruto: float, minutos_treino: float, deficit_do_dia: float) -> list:
    alertas = []
    if consumido > 6000:
        alertas.append("Consumido muito alto (acima de 6000 kcal) — confira se não houve erro de digitação.")
    if 0 < consumido < 300:
        alertas.append("Consumido muito baixo (abaixo de 300 kcal) para um dia inteiro — confira o valor.")
    if treino_bruto > 2000:
        alertas.append("Treino Bruto muito alto (acima de 2000 kcal) — confira o valor.")
    if minutos_treino > 300:
        alertas.append("Minutos de Treino muito alto (acima de 5h) — confira o valor.")
    if treino_bruto > 0 and minutos_treino == 0:
        alertas.append("Treino Bruto informado sem Minutos de Treino.")
    if abs(deficit_do_dia) > 2000:
        alertas.append("Déficit do dia muito fora do padrão (acima de 2000 kcal) — confira os valores.")
    return alertas


preenchidos = linhas_preenchidas(registros)
basal_definido = bool(config.get("basal"))
resumo = calcular_resumo(preenchidos, config["basal"]) if basal_definido else None

# ---------------------------------------------------------------------------
# CABEÇALHO
# ---------------------------------------------------------------------------
col_titulo, col_status = st.columns([3, 1])
with col_titulo:
    st.title("🔥 Déficit Calórico")
    st.caption(
        f"Acompanhamento pessoal de déficit calórico e perda de gordura · "
        f"Hoje: {formatar_data_br(data_para_chave(datetime.date.today()))}"
    )
with col_status:
    if basal_definido:
        st.metric("Basal em uso", f"{round(config['basal'])} kcal/dia")
    else:
        st.warning("Basal não definido")

# ---------------------------------------------------------------------------
# BARRA LATERAL: resumo sempre visível
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📌 Resumo rápido")

    if not basal_definido:
        st.info("Configure seu perfil na aba **Perfil (TMB/TDEE)** para começar.")
    else:
        hoje_chave = data_para_chave(datetime.date.today())
        if hoje_chave in preenchidos:
            st.success("✅ Hoje já foi registrado")
        else:
            st.warning("📝 Hoje ainda não foi registrado")

        streak = calcular_streak(preenchidos)
        if streak > 0:
            st.caption(f"🔥 Sequência atual: {streak} dia(s) seguidos")

        st.divider()

        if not preenchidos:
            st.caption("Nenhum dia registrado ainda.")
        else:
            deficit_total = resumo["deficit_total"]
            kg_perdidos = deficit_total / config["kcal_por_kg_gordura"]
            media_diaria = media_diaria_deficit(deficit_total, len(preenchidos))

            st.metric("Déficit acumulado", f"{round(deficit_total)} kcal")
            st.metric("Perda estimada", f"{kg_perdidos:.2f} kg")
            st.caption(f"{len(preenchidos)} dia(s) registrado(s)")

            metas_futuras = [m for m in sorted(config["metas_kg"]) if m > kg_perdidos]
            proxima_meta = metas_futuras[0] if metas_futuras else (max(config["metas_kg"]) if config["metas_kg"] else None)
            if proxima_meta:
                kcal_necessario = config["kcal_por_kg_gordura"] * proxima_meta
                progresso = min(max(deficit_total / kcal_necessario, 0), 1) if kcal_necessario else 0
                st.divider()
                st.caption(f"Próxima meta: {proxima_meta} kg")
                st.progress(progresso, text=f"{progresso * 100:.0f}%")
                data_prevista, dias_restantes = prever_data_meta(deficit_total, kcal_necessario, media_diaria)
                if data_prevista:
                    st.caption(f"📅 Previsão: {formatar_data_br(data_para_chave(data_prevista))} (~{dias_restantes} dias)")
                elif dias_restantes is None:
                    st.caption("📅 Sem previsão (déficit médio diário não é positivo)")

st.divider()

abas = st.tabs(
    [
        "👤 Perfil (TMB/TDEE)",
        "📝 Registro Diário",
        "🧬 Composição Corporal",
        "📊 Histórico",
        "🎯 Resumo e Metas",
        "📈 Gráfico",
        "⚙️ Configurações",
    ]
)

# ---------------------------------------------------------------------------
# ABA: Perfil / entrevista inicial
# ---------------------------------------------------------------------------
with abas[0]:
    st.subheader("Dados pessoais e cálculo de TMB/TDEE")
    st.caption(
        "Preencha seus dados para calcular sua Taxa Metabólica Basal (TMB) e seu Gasto "
        "Calórico Total (TDEE), no estilo do tdeecalculator.net."
    )

    perfil_atual = config.get("perfil") or {}

    with st.form("form_perfil"):
        col1, col2 = st.columns(2)
        with col1:
            sexo = st.selectbox(
                "Sexo", ["Masculino", "Feminino"],
                index=["Masculino", "Feminino"].index(perfil_atual.get("sexo", "Masculino")),
            )
            idade = st.number_input(
                "Idade (anos)", min_value=10, max_value=100,
                value=int(perfil_atual.get("idade", 30)),
            )
            peso = st.number_input(
                "Peso atual (kg)", min_value=30.0, max_value=300.0,
                value=float(perfil_atual.get("peso", 70.0)), step=0.1,
            )
        with col2:
            altura = st.number_input(
                "Altura (cm)", min_value=100.0, max_value=250.0,
                value=float(perfil_atual.get("altura", 170.0)), step=0.5,
            )
            nivel_atividade = st.selectbox(
                "Nível de atividade física",
                list(MULTIPLICADORES_ATIVIDADE.keys()),
                index=list(MULTIPLICADORES_ATIVIDADE.keys()).index(
                    perfil_atual.get("nivel_atividade", list(MULTIPLICADORES_ATIVIDADE.keys())[0])
                ),
            )
            tem_bf = st.checkbox(
                "Tenho o % de gordura corporal", value=perfil_atual.get("percentual_gordura") is not None
            )
            percentual_gordura = None
            if tem_bf:
                percentual_gordura = st.number_input(
                    "% de gordura corporal", min_value=3.0, max_value=60.0,
                    value=float(perfil_atual.get("percentual_gordura") or 20.0), step=0.5,
                )

        calcular = st.form_submit_button("Calcular TMB e TDEE", type="primary")

    if calcular:
        bmr_mifflin = bmr_mifflin_st_jeor(sexo, peso, altura, idade)
        bmr_harris = bmr_harris_benedict(sexo, peso, altura, idade)
        bmr_katch = bmr_katch_mcardle(peso, percentual_gordura) if percentual_gordura else None

        st.session_state["perfil_calculado"] = {
            "sexo": sexo,
            "idade": idade,
            "peso": peso,
            "altura": altura,
            "nivel_atividade": nivel_atividade,
            "percentual_gordura": percentual_gordura,
            "bmr_mifflin": bmr_mifflin,
            "bmr_harris": bmr_harris,
            "bmr_katch": bmr_katch,
        }

    if "perfil_calculado" in st.session_state:
        pc = st.session_state["perfil_calculado"]

        with st.container(border=True):
            st.markdown("#### TMB (Taxa Metabólica Basal) por fórmula")
            cols_bmr = st.columns(3 if pc["bmr_katch"] else 2)
            cols_bmr[0].metric("Mifflin-St Jeor", f"{round(pc['bmr_mifflin'])} kcal")
            cols_bmr[1].metric("Harris-Benedict", f"{round(pc['bmr_harris'])} kcal")
            if pc["bmr_katch"]:
                cols_bmr[2].metric("Katch-McArdle", f"{round(pc['bmr_katch'])} kcal")

        with st.container(border=True):
            st.markdown("#### TDEE (Gasto Calórico Total) por nível de atividade")
            formula_base = st.radio(
                "Qual TMB usar como base para o TDEE?",
                ["Mifflin-St Jeor", "Harris-Benedict (revisada)"]
                + (["Katch-McArdle"] if pc["bmr_katch"] else []),
                horizontal=True,
            )
            bmr_escolhido = {
                "Mifflin-St Jeor": pc["bmr_mifflin"],
                "Harris-Benedict (revisada)": pc["bmr_harris"],
                "Katch-McArdle": pc["bmr_katch"],
            }[formula_base]

            tdees = calcular_tdees(bmr_escolhido)
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Nível de atividade": nivel, "TDEE (kcal/dia)": round(valor)}
                        for nivel, valor in tdees.items()
                    ]
                ),
                width='stretch',
                hide_index=True,
            )

        with st.container(border=True):
            st.markdown("#### Escolha o valor Basal a ser usado no sistema")
            opcoes_basal = {f"TMB - {formula_base}": bmr_escolhido}
            for nivel, valor in tdees.items():
                opcoes_basal[f"TDEE - {nivel}"] = valor

            escolha = st.selectbox("Selecione o valor que será usado como Basal", list(opcoes_basal.keys()))
            basal_escolhido = opcoes_basal[escolha]
            st.info(f"Valor selecionado: **{round(basal_escolhido)} kcal/dia**")

            valor_manual = st.number_input(
                "Ou sobrescreva manualmente o Basal (kcal/dia)",
                min_value=0.0, value=float(round(basal_escolhido)), step=10.0,
            )

            if st.button("💾 Salvar como Basal do sistema", type="primary"):
                config["perfil"] = {
                    "sexo": pc["sexo"],
                    "idade": pc["idade"],
                    "peso": pc["peso"],
                    "altura": pc["altura"],
                    "nivel_atividade": pc["nivel_atividade"],
                    "percentual_gordura": pc["percentual_gordura"],
                }
                config["basal"] = valor_manual
                storage.salvar_config(config)
                st.success(f"Basal salvo: {round(valor_manual)} kcal/dia")
                st.rerun()

    st.divider()
    with st.expander("🔧 Sobrescrever o Basal manualmente"):
        st.markdown(f"**Basal atual em uso no sistema:** {config.get('basal') or 'ainda não definido'}")
        novo_basal_direto = st.number_input(
            "Novo valor de Basal (kcal/dia)",
            min_value=0.0, value=float(config.get("basal") or 0.0), step=10.0,
            key="override_basal",
        )
        if st.button("Atualizar Basal manualmente"):
            config["basal"] = novo_basal_direto
            storage.salvar_config(config)
            st.success("Basal atualizado.")
            st.rerun()

# ---------------------------------------------------------------------------
# ABA: Registro diário
# ---------------------------------------------------------------------------
with abas[1]:
    st.subheader("Registro diário")

    if not basal_definido:
        st.warning("Defina o Basal na aba 'Perfil (TMB/TDEE)' antes de registrar dias.")
    else:
        data_selecionada = st.date_input(
            "Data", value=datetime.date.today(), format=DATA_FORMATO_STREAMLIT, key="data_registro"
        )
        chave = data_para_chave(data_selecionada)
        registro_existente = registros.get(chave, {})

        if chave in preenchidos:
            st.caption(f"✏️ Já existe um registro para {formatar_data_br(chave)} — salvar irá sobrescrevê-lo.")

        with st.form("form_registro_diario"):
            col1, col2, col3 = st.columns(3)
            with col1:
                consumido = st.number_input(
                    "Consumido (Kcal)", min_value=0.0,
                    value=float(registro_existente.get("consumido") or 0.0), step=10.0,
                )
            with col2:
                treino_bruto = st.number_input(
                    "Treino Bruto (Kcal)", min_value=0.0,
                    value=float(registro_existente.get("treino_bruto") or 0.0), step=10.0,
                )
            with col3:
                minutos_treino = st.number_input(
                    "Minutos de Treino", min_value=0.0,
                    value=float(registro_existente.get("minutos_treino") or 0.0), step=1.0,
                )
            salvar = st.form_submit_button("💾 Salvar dia", type="primary")

        if salvar:
            registros[chave] = {
                "consumido": consumido,
                "treino_bruto": treino_bruto,
                "minutos_treino": minutos_treino,
                "basal_usado": config["basal"],
            }
            storage.salvar_registros(registros)
            resultado = calcular_dia(consumido, treino_bruto, minutos_treino, config["basal"])
            deficit_dia = resultado["deficit_do_dia"]
            data_fmt = formatar_data_br(chave)
            if deficit_dia >= 0:
                st.success(f"Dia {data_fmt} salvo. Déficit do dia: {round(deficit_dia)} kcal 🔥")
            else:
                st.error(f"Dia {data_fmt} salvo. Superávit do dia: {round(-deficit_dia)} kcal")
            for alerta in detectar_alertas(consumido, treino_bruto, minutos_treino, deficit_dia):
                st.toast(alerta, icon="⚠️")
            st.rerun()

# ---------------------------------------------------------------------------
# ABA: Composição corporal
# ---------------------------------------------------------------------------
with abas[2]:
    st.subheader("Composição corporal")
    st.caption(
        "Registro esporádico de peso, % de gordura corporal e % de massa magra "
        "(ex.: sempre que fizer uma bioimpedância ou medição)."
    )

    data_composicao = st.date_input(
        "Data da coleta", value=datetime.date.today(), format=DATA_FORMATO_STREAMLIT, key="data_composicao"
    )
    chave_composicao = data_para_chave(data_composicao)
    composicao_existente = composicao.get(chave_composicao, {})

    if chave_composicao in composicao:
        st.caption(f"✏️ Já existe uma medição para {formatar_data_br(chave_composicao)} — salvar irá sobrescrevê-la.")

    with st.form("form_composicao"):
        col1, col2, col3 = st.columns(3)
        with col1:
            c_peso = st.number_input(
                "Peso (kg)", min_value=0.0,
                value=float(composicao_existente.get("peso") or 0.0), step=0.1,
            )
        with col2:
            c_gordura = st.number_input(
                "% de Gordura Corporal", min_value=0.0, max_value=100.0,
                value=float(composicao_existente.get("percentual_gordura") or 0.0), step=0.1,
            )
        with col3:
            c_massa_magra = st.number_input(
                "% de Massa Magra", min_value=0.0, max_value=100.0,
                value=float(composicao_existente.get("percentual_massa_magra") or 0.0), step=0.1,
            )
        salvar_composicao_btn = st.form_submit_button("💾 Salvar medição", type="primary")

    if salvar_composicao_btn:
        if c_peso == 0 and c_gordura == 0 and c_massa_magra == 0:
            st.error("Informe ao menos um valor (Peso, % Gordura ou % Massa Magra).")
        else:
            composicao[chave_composicao] = {
                "peso": c_peso if c_peso > 0 else None,
                "percentual_gordura": c_gordura if c_gordura > 0 else None,
                "percentual_massa_magra": c_massa_magra if c_massa_magra > 0 else None,
            }
            storage.salvar_composicao(composicao)
            st.success(f"Medição de {formatar_data_br(chave_composicao)} salva.")
            st.rerun()

    if composicao:
        st.markdown("#### Histórico de medições")
        linhas_composicao = []
        for data_str in sorted(composicao.keys()):
            c = composicao[data_str]
            linhas_composicao.append(
                {
                    "Data": formatar_data_br(data_str),
                    "Peso (kg)": c.get("peso"),
                    "% Gordura": c.get("percentual_gordura"),
                    "% Massa Magra": c.get("percentual_massa_magra"),
                }
            )
        df_composicao = pd.DataFrame(linhas_composicao)
        st.dataframe(
            df_composicao.style.format(
                {"Peso (kg)": "{:.1f}", "% Gordura": "{:.1f}", "% Massa Magra": "{:.1f}"}, na_rep="-"
            ),
            width="stretch",
            hide_index=True,
        )

        st.markdown("#### ✏️ Editar / corrigir uma medição")
        with st.container(border=True):
            data_editar_comp = st.selectbox(
                "Selecione a data para editar",
                sorted(composicao.keys(), reverse=True),
                format_func=formatar_data_br,
                key="select_editar_composicao",
            )
            c = composicao[data_editar_comp]
            with st.form("form_editar_composicao"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    e_c_peso = st.number_input("Peso (kg)", min_value=0.0, value=float(c.get("peso") or 0.0), step=0.1)
                with col2:
                    e_c_gordura = st.number_input(
                        "% de Gordura Corporal", min_value=0.0, max_value=100.0,
                        value=float(c.get("percentual_gordura") or 0.0), step=0.1,
                    )
                with col3:
                    e_c_massa_magra = st.number_input(
                        "% de Massa Magra", min_value=0.0, max_value=100.0,
                        value=float(c.get("percentual_massa_magra") or 0.0), step=0.1,
                    )
                col_a, col_b = st.columns(2)
                with col_a:
                    atualizar_comp = st.form_submit_button("💾 Atualizar medição", type="primary")
                with col_b:
                    excluir_comp = st.form_submit_button("🗑️ Excluir medição")

            if atualizar_comp:
                if e_c_peso == 0 and e_c_gordura == 0 and e_c_massa_magra == 0:
                    st.error("Informe ao menos um valor (Peso, % Gordura ou % Massa Magra).")
                else:
                    composicao[data_editar_comp] = {
                        "peso": e_c_peso if e_c_peso > 0 else None,
                        "percentual_gordura": e_c_gordura if e_c_gordura > 0 else None,
                        "percentual_massa_magra": e_c_massa_magra if e_c_massa_magra > 0 else None,
                    }
                    storage.salvar_composicao(composicao)
                    st.success(f"Medição de {formatar_data_br(data_editar_comp)} atualizada.")
                    st.rerun()

            if excluir_comp:
                st.session_state["confirmar_exclusao_composicao"] = data_editar_comp
                st.rerun()

            if st.session_state.get("confirmar_exclusao_composicao") == data_editar_comp:
                st.warning(
                    f"⚠️ Tem certeza que deseja excluir a medição de **{formatar_data_br(data_editar_comp)}**? "
                    "Essa ação não pode ser desfeita."
                )
                col_confirma, col_cancela = st.columns(2)
                with col_confirma:
                    if st.button("✅ Sim, excluir definitivamente", key="confirmar_exclusao_composicao_botao"):
                        del composicao[data_editar_comp]
                        storage.salvar_composicao(composicao)
                        st.session_state["confirmar_exclusao_composicao"] = None
                        st.success(f"Medição de {formatar_data_br(data_editar_comp)} excluída.")
                        st.rerun()
                with col_cancela:
                    if st.button("Cancelar", key="cancelar_exclusao_composicao_botao"):
                        st.session_state["confirmar_exclusao_composicao"] = None
                        st.rerun()

# ---------------------------------------------------------------------------
# ABA: Histórico
# ---------------------------------------------------------------------------
with abas[3]:
    st.subheader("Histórico de registros")

    if not preenchidos or not basal_definido:
        st.info("Nenhum dia registrado ainda (ou Basal não definido).")
    else:
        colunas_decimais = [
            "Consumido",
            "Treino Bruto",
            "Minutos",
            "Kcal Repouso",
            "Treino Líquido",
            "Resultado Líquido",
            "Déficit do Dia",
        ]
        linhas = []
        for data_str in sorted(preenchidos.keys()):
            v = preenchidos[data_str]
            r = resumo["dias_calculados"][data_str]
            linhas.append(
                {
                    "Data": formatar_data_br(data_str),
                    "Consumido": v["consumido"],
                    "Treino Bruto": v["treino_bruto"],
                    "Minutos": v["minutos_treino"],
                    "Kcal Repouso": r["kcal_repouso"],
                    "Treino Líquido": r["treino_liquido"],
                    "Resultado Líquido": r["resultado_liquido"],
                    "Déficit do Dia": r["deficit_do_dia"],
                }
            )
        df_historico = pd.DataFrame(linhas)
        st.dataframe(
            df_historico.style.format({c: "{:.1f}" for c in colunas_decimais}, na_rep="-").map(
                cor_deficit, subset=["Déficit do Dia"]
            ),
            width='stretch',
            hide_index=True,
        )

        st.markdown("#### ✏️ Editar / corrigir um dia")
        with st.container(border=True):
            data_editar = st.selectbox(
                "Selecione a data para editar",
                sorted(preenchidos.keys(), reverse=True),
                format_func=formatar_data_br,
            )
            v = preenchidos[data_editar]
            basal_do_dia = v.get("basal_usado", config["basal"])
            st.caption(f"Basal usado neste dia: {round(basal_do_dia)} kcal/dia (não muda mesmo se o Basal atual do sistema for alterado depois)")
            with st.form("form_editar_dia"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    e_consumido = st.number_input("Consumido (Kcal)", min_value=0.0, value=float(v["consumido"]), step=10.0)
                with col2:
                    e_treino_bruto = st.number_input("Treino Bruto (Kcal)", min_value=0.0, value=float(v["treino_bruto"]), step=10.0)
                with col3:
                    e_minutos = st.number_input("Minutos de Treino", min_value=0.0, value=float(v["minutos_treino"]), step=1.0)
                col_a, col_b = st.columns(2)
                with col_a:
                    atualizar = st.form_submit_button("💾 Atualizar dia", type="primary")
                with col_b:
                    excluir = st.form_submit_button("🗑️ Excluir dia")

            if atualizar:
                registros[data_editar] = {
                    "consumido": e_consumido,
                    "treino_bruto": e_treino_bruto,
                    "minutos_treino": e_minutos,
                    "basal_usado": basal_do_dia,
                }
                storage.salvar_registros(registros)
                e_resultado = calcular_dia(e_consumido, e_treino_bruto, e_minutos, basal_do_dia)
                for alerta in detectar_alertas(e_consumido, e_treino_bruto, e_minutos, e_resultado["deficit_do_dia"]):
                    st.toast(alerta, icon="⚠️")
                st.success(f"Dia {formatar_data_br(data_editar)} atualizado.")
                st.rerun()

            if excluir:
                st.session_state["confirmar_exclusao_data"] = data_editar
                st.rerun()

            if st.session_state.get("confirmar_exclusao_data") == data_editar:
                st.warning(
                    f"⚠️ Tem certeza que deseja excluir o dia **{formatar_data_br(data_editar)}**? "
                    "Essa ação não pode ser desfeita."
                )
                col_confirma, col_cancela = st.columns(2)
                with col_confirma:
                    if st.button("✅ Sim, excluir definitivamente", key="confirmar_exclusao_botao"):
                        del registros[data_editar]
                        storage.salvar_registros(registros)
                        st.session_state["confirmar_exclusao_data"] = None
                        st.success(f"Dia {formatar_data_br(data_editar)} excluído.")
                        st.rerun()
                with col_cancela:
                    if st.button("Cancelar", key="cancelar_exclusao_botao"):
                        st.session_state["confirmar_exclusao_data"] = None
                        st.rerun()

# ---------------------------------------------------------------------------
# ABA: Resumo e metas
# ---------------------------------------------------------------------------
with abas[4]:
    st.subheader("Resumo e progresso das metas")

    if not preenchidos or not basal_definido:
        st.info("Nenhum dia registrado ainda (ou Basal não definido).")
    else:
        deficit_total = resumo["deficit_total"]
        kg_perdidos_estimados = deficit_total / config["kcal_por_kg_gordura"]
        media_diaria = media_diaria_deficit(deficit_total, len(preenchidos))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Déficit total acumulado", f"{round(deficit_total)} kcal")
        col2.metric("Perda de gordura estimada", f"{kg_perdidos_estimados:.2f} kg")
        col3.metric("Dias registrados", len(preenchidos))
        col4.metric("Sequência atual", f"{calcular_streak(preenchidos)} dia(s)")

        st.caption(f"Déficit médio diário (histórico completo): {media_diaria:.1f} kcal/dia")

        st.markdown("#### 🎯 Metas de perda de gordura")
        for meta_kg in sorted(config["metas_kg"]):
            kcal_necessario = config["kcal_por_kg_gordura"] * meta_kg
            percentual = (deficit_total / kcal_necessario) if kcal_necessario else 0
            atingida = percentual >= 1
            with st.container(border=True):
                col_label, col_bar = st.columns([1, 3])
                with col_label:
                    st.markdown(f"**{'✅' if atingida else '🎯'} {meta_kg} kg**")
                    st.caption(f"{round(kcal_necessario)} kcal necessários")
                with col_bar:
                    st.progress(min(max(percentual, 0), 1), text=f"{percentual * 100:.1f}%")
                    if not atingida:
                        data_prevista, dias_restantes = prever_data_meta(deficit_total, kcal_necessario, media_diaria)
                        if data_prevista:
                            st.caption(
                                f"📅 Previsão no ritmo atual: {formatar_data_br(data_para_chave(data_prevista))} "
                                f"(~{dias_restantes} dias)"
                            )
                        else:
                            st.caption("📅 Sem previsão (déficit médio diário não é positivo)")

# ---------------------------------------------------------------------------
# ABA: Gráfico
# ---------------------------------------------------------------------------
with abas[5]:
    st.subheader("Evolução do déficit")

    if not preenchidos or not basal_definido:
        st.info("Nenhum dia registrado ainda (ou Basal não definido).")
    else:
        datas_ordenadas = sorted(preenchidos.keys())
        deficit_diario = []
        acumulado = 0.0
        acumulados = []
        for d in datas_ordenadas:
            r = resumo["dias_calculados"][d]
            deficit_diario.append(r["deficit_do_dia"])
            acumulado += r["deficit_do_dia"]
            acumulados.append(acumulado)

        df_evolucao = pd.DataFrame(
            {
                "Data": pd.to_datetime(datas_ordenadas),
                "Déficit do Dia": deficit_diario,
                "Déficit Acumulado": acumulados,
            }
        )
        df_evolucao["Média Móvel (7 dias)"] = df_evolucao["Déficit do Dia"].rolling(7, min_periods=1).mean()

        eixo_data = alt.X("Data:T", axis=alt.Axis(format="%d/%m/%Y", title=None))

        st.markdown("##### Déficit acumulado")
        area = (
            alt.Chart(df_evolucao)
            .mark_area(line={"color": "#FF6B35"}, color="#FF6B35", opacity=0.25)
            .encode(
                x=eixo_data,
                y=alt.Y("Déficit Acumulado:Q", title="kcal acumulado"),
                tooltip=[
                    alt.Tooltip("Data:T", format="%d/%m/%Y", title="Data"),
                    alt.Tooltip("Déficit Acumulado:Q", format=".1f", title="Déficit Acumulado"),
                ],
            )
            .properties(height=260)
        )
        st.altair_chart(area, width="stretch")

        st.markdown("##### Déficit diário (com média móvel de 7 dias)")
        barras = (
            alt.Chart(df_evolucao)
            .mark_bar()
            .encode(
                x=eixo_data,
                y=alt.Y("Déficit do Dia:Q", title="kcal"),
                color=alt.condition(
                    "datum['Déficit do Dia'] >= 0", alt.value("#3DDC84"), alt.value("#FF5C5C")
                ),
                tooltip=[
                    alt.Tooltip("Data:T", format="%d/%m/%Y", title="Data"),
                    alt.Tooltip("Déficit do Dia:Q", format=".1f", title="Déficit do Dia"),
                ],
            )
        )
        linha_media = (
            alt.Chart(df_evolucao)
            .mark_line(color="#F2F2F2", strokeDash=[4, 3], strokeWidth=2)
            .encode(
                x=eixo_data,
                y=alt.Y("Média Móvel (7 dias):Q"),
                tooltip=[alt.Tooltip("Média Móvel (7 dias):Q", format=".1f", title="Média (7 dias)")],
            )
        )
        st.altair_chart((barras + linha_media).properties(height=260), width="stretch")

    if composicao:
        st.divider()
        st.markdown("##### 🧬 Evolução da composição corporal")
        st.caption("Baseado nas medições registradas na aba Composição Corporal.")

        datas_comp = sorted(composicao.keys())
        df_comp = pd.DataFrame(
            {
                "Data": pd.to_datetime(datas_comp),
                "Peso (kg)": [composicao[d].get("peso") for d in datas_comp],
                "% Gordura": [composicao[d].get("percentual_gordura") for d in datas_comp],
                "% Massa Magra": [composicao[d].get("percentual_massa_magra") for d in datas_comp],
            }
        )

        df_peso_comp = df_comp.dropna(subset=["Peso (kg)"])
        if not df_peso_comp.empty:
            st.markdown("###### Peso")
            linha_peso_comp = (
                alt.Chart(df_peso_comp)
                .mark_line(color="#4EA8FF", point=True)
                .encode(
                    x=alt.X("Data:T", axis=alt.Axis(format="%d/%m/%Y", title=None)),
                    y=alt.Y("Peso (kg):Q", scale=alt.Scale(zero=False)),
                    tooltip=[
                        alt.Tooltip("Data:T", format="%d/%m/%Y", title="Data"),
                        alt.Tooltip("Peso (kg):Q", format=".1f", title="Peso"),
                    ],
                )
                .properties(height=220)
            )
            st.altair_chart(linha_peso_comp, width="stretch")

        df_percentuais = df_comp.melt(
            id_vars=["Data"],
            value_vars=["% Gordura", "% Massa Magra"],
            var_name="Métrica",
            value_name="Percentual",
        ).dropna(subset=["Percentual"])
        if not df_percentuais.empty:
            st.markdown("###### % Gordura e % Massa Magra")
            linha_percentuais = (
                alt.Chart(df_percentuais)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Data:T", axis=alt.Axis(format="%d/%m/%Y", title=None)),
                    y=alt.Y("Percentual:Q", scale=alt.Scale(zero=False), title="%"),
                    color=alt.Color(
                        "Métrica:N",
                        scale=alt.Scale(
                            domain=["% Gordura", "% Massa Magra"], range=["#FF5C5C", "#3DDC84"]
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("Data:T", format="%d/%m/%Y", title="Data"),
                        alt.Tooltip("Métrica:N", title="Métrica"),
                        alt.Tooltip("Percentual:Q", format=".1f", title="Percentual"),
                    ],
                )
                .properties(height=220)
            )
            st.altair_chart(linha_percentuais, width="stretch")

# ---------------------------------------------------------------------------
# ABA: Configurações
# ---------------------------------------------------------------------------
with abas[6]:
    st.subheader("Parâmetros de configuração")

    with st.container(border=True):
        kcal_por_kg = st.number_input(
            "Kcal por kg de gordura", min_value=1000.0, max_value=15000.0,
            value=float(config.get("kcal_por_kg_gordura", 7700)), step=50.0,
        )

        metas_texto = st.text_input(
            "Metas de perda de gordura (kg), separadas por vírgula",
            value=", ".join(str(m) for m in config.get("metas_kg", [])),
        )

        if st.button("💾 Salvar configurações", type="primary"):
            try:
                novas_metas = [float(x.strip()) for x in metas_texto.split(",") if x.strip()]
            except ValueError:
                st.error("Formato inválido nas metas. Use números separados por vírgula, ex: 1, 2, 3")
            else:
                config["kcal_por_kg_gordura"] = kcal_por_kg
                config["metas_kg"] = novas_metas
                storage.salvar_config(config)
                st.success("Configurações salvas.")
                st.rerun()

    st.markdown("#### 💾 Exportar / backup dos dados")
    with st.container(border=True):
        st.caption("Baixe seus dados a qualquer momento — útil como backup ou para abrir no Excel.")
        col_csv, col_json = st.columns(2)

        with col_csv:
            if preenchidos and basal_definido:
                linhas_export = []
                for data_str in sorted(preenchidos.keys()):
                    v = preenchidos[data_str]
                    r = resumo["dias_calculados"][data_str]
                    linhas_export.append(
                        {
                            "Data": formatar_data_br(data_str),
                            "Consumido": v["consumido"],
                            "Treino Bruto": v["treino_bruto"],
                            "Minutos": v["minutos_treino"],
                            "Kcal Repouso": round(r["kcal_repouso"], 1),
                            "Treino Líquido": round(r["treino_liquido"], 1),
                            "Resultado Líquido": round(r["resultado_liquido"], 1),
                            "Déficit do Dia": round(r["deficit_do_dia"], 1),
                        }
                    )
                csv_bytes = pd.DataFrame(linhas_export).to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇️ Baixar Histórico (CSV)",
                    data=csv_bytes,
                    file_name=f"deficit_calorico_historico_{datetime.date.today().isoformat()}.csv",
                    mime="text/csv",
                    width="stretch",
                )
            else:
                st.caption("Nenhum dado para exportar ainda.")

        with col_json:
            backup = {"config": config, "registros": registros}
            backup_bytes = json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button(
                "⬇️ Baixar Backup Completo (JSON)",
                data=backup_bytes,
                file_name=f"deficit_calorico_backup_{datetime.date.today().isoformat()}.json",
                mime="application/json",
                width="stretch",
            )

    st.markdown("#### ⚠️ Zona de risco")
    with st.container(border=True):
        st.caption(
            "Reseta o histórico diário — Consumido, Treino Bruto, Minutos, déficit acumulado e "
            "sequência de dias — pra começar uma fase nova do zero. Perfil, Basal, Metas e Composição "
            "Corporal não são afetados."
        )
        if st.button("🔄 Resetar registros diários"):
            st.session_state["confirmar_reset"] = True
            st.rerun()

        if st.session_state.get("confirmar_reset"):
            st.warning(
                "⚠️ Isso vai apagar **todos os dias registrados** — o déficit acumulado e a sequência de "
                "dias voltam a zero. Perfil, Basal, Metas e Composição Corporal continuam intactos. "
                "Essa ação não pode ser desfeita."
            )
            st.download_button(
                "⬇️ Baixar backup antes de continuar (recomendado)",
                data=backup_bytes,
                file_name=f"deficit_calorico_backup_{datetime.date.today().isoformat()}.json",
                mime="application/json",
                key="backup_antes_reset",
            )
            col_confirma, col_cancela = st.columns(2)
            with col_confirma:
                if st.button("✅ Sim, apagar todo o histórico diário", key="confirmar_reset_botao"):
                    storage.salvar_registros({})
                    st.session_state["confirmar_reset"] = None
                    st.success("Histórico diário resetado.")
                    st.rerun()
            with col_cancela:
                if st.button("Cancelar", key="cancelar_reset_botao"):
                    st.session_state["confirmar_reset"] = None
                    st.rerun()
