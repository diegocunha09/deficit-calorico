"""Fórmulas de TMB/TDEE e cálculos de déficit calórico."""

MULTIPLICADORES_ATIVIDADE = {
    "Sedentário (pouco ou nenhum exercício)": 1.2,
    "Leve (exercício leve 1-2x/semana)": 1.375,
    "Moderado (exercício moderado 3-5x/semana)": 1.55,
    "Intenso (exercício intenso 6-7x/semana)": 1.725,
    "Atleta (exercício muito intenso, 2x/dia)": 1.9,
}


def bmr_mifflin_st_jeor(sexo: str, peso_kg: float, altura_cm: float, idade: int) -> float:
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * idade
    return base + 5 if sexo == "Masculino" else base - 161


def bmr_harris_benedict(sexo: str, peso_kg: float, altura_cm: float, idade: int) -> float:
    if sexo == "Masculino":
        return 88.362 + 13.397 * peso_kg + 4.799 * altura_cm - 5.677 * idade
    return 447.593 + 9.247 * peso_kg + 3.098 * altura_cm - 4.330 * idade


def bmr_katch_mcardle(peso_kg: float, percentual_gordura: float) -> float:
    massa_magra = peso_kg * (1 - percentual_gordura / 100)
    return 370 + 21.6 * massa_magra


def calcular_tdees(bmr: float) -> dict:
    return {nivel: bmr * mult for nivel, mult in MULTIPLICADORES_ATIVIDADE.items()}


def calcular_dia(consumido: float, treino_bruto: float, minutos_treino: float, basal: float) -> dict:
    basal_por_minuto = basal / 1440
    kcal_se_repouso = minutos_treino * basal_por_minuto
    treino_liquido = treino_bruto - kcal_se_repouso
    resultado_liquido = consumido - treino_liquido
    deficit_do_dia = basal - resultado_liquido
    return {
        "kcal_repouso": kcal_se_repouso,
        "treino_liquido": treino_liquido,
        "resultado_liquido": resultado_liquido,
        "deficit_do_dia": deficit_do_dia,
    }
