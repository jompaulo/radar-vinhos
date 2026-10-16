import asyncio
from typing import List, Dict, Any, Tuple
import httpx
import pandas as pd
import config
import database
from providers.marketplace_comparator import obter_preco_mercado_ml


def classificar_tier(preco_atual: float) -> Tuple[str, str]:
    """
    Retorna `(tier_codigo, selo_visual)` de acordo com a faixa de preço atual:
    - Tier 1 (Dia a Dia): R$ 50,00 a R$ 119,99 -> 🟢 [RADAR DIA A DIA]
    - Tier 2 (Reserva): R$ 120,00 a R$ 349,99 -> 🟡 [RADAR RESERVA]
    - Tier 3 (Alta Gama): R$ 350,00 a R$ 3.500,00 -> 🔴 [RADAR ALTA GAMA]
    """
    if preco_atual < 120.00:
        return "TIER_1", "🟢 [RADAR DIA A DIA]"
    if preco_atual < 350.00:
        return "TIER_2", "🟡 [RADAR RESERVA]"
    return "TIER_3", "🔴 [RADAR ALTA GAMA]"


async def analisar_produtos_async(
    produtos: List[Dict[str, Any]],
    db_path: str = config.DB_PATH,
    ignorar_alertas_hoje: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Implementa a Regra de Tiers e Anti-Falso-Desconto comparando com o histórico SQLite
    e com o comparador do Mercado Livre:

    - Tier 1 (Dia a Dia - R$ 50 a R$ 119,99):
      Desconto real >= 35% vs histórico (ou >= 45% sobre tabela se sem histórico)
      E pelo menos 25% abaixo do preço do Mercado Livre (`desconto_vs_ml >= 0.25`) e `estoque > 0`.
    - Tier 2 (Reserva - R$ 120 a R$ 349,99):
      Desconto real >= 28% e `0 < estoque <= 36`.
    - Tier 3 (Alta Gama - R$ 350 a R$ 3.500,00):
      Desconto real >= 22% e estoque escasso (`0 < estoque <= 24`).
    """
    if not produtos:
        vazio = pd.DataFrame()
        return vazio, vazio

    skus = [p["sku"] for p in produtos]
    df_hist = database.obter_historico_60_dias(skus, db_path=db_path)

    # Grava a coleta atual na tabela historico_precos
    df_atual = database.salvar_coleta(produtos, db_path=db_path)

    if not df_hist.empty:
        medias_60d = df_hist.groupby("sku")["preco_atual"].mean().to_dict()
    else:
        medias_60d = {}

    def tem_historico_real(row: pd.Series) -> bool:
        sku = row["sku"]
        if sku not in medias_60d or medias_60d[sku] <= 0:
            return False
        media = float(medias_60d[sku])
        # Se a média histórica for superior ao preço atual, há histórico real de preço maior
        return media > float(row["preco_atual"]) + 0.01

    def calcular_referencia(row: pd.Series) -> float:
        sku = row["sku"]
        if sku in medias_60d and medias_60d[sku] > 0:
            media = float(medias_60d[sku])
            if abs(media - float(row["preco_atual"])) < 0.01 and float(row["preco_tabela"]) > media:
                return round(float(row["preco_tabela"]), 2)
            return round(media, 2)
        return round(float(row["preco_tabela"]), 2)

    df_atual["tem_historico"] = df_atual.apply(tem_historico_real, axis=1)
    df_atual["origem_referencia"] = df_atual["tem_historico"].apply(
        lambda h: "Histórico 60d" if h else "Preço Tabela (1ª coleta)"
    )
    df_atual["preco_referencia"] = df_atual.apply(calcular_referencia, axis=1)

    df_atual["desconto_real"] = df_atual.apply(
        lambda r: (
            (r["preco_referencia"] - r["preco_atual"]) / r["preco_referencia"]
            if r["preco_referencia"] > 0
            else 0.0
        ),
        axis=1,
    )

    df_atual["desconto_tabela"] = df_atual.apply(
        lambda r: (
            (r["preco_tabela"] - r["preco_atual"]) / r["preco_tabela"]
            if r["preco_tabela"] > 0
            else 0.0
        ),
        axis=1,
    )

    # Classificação de Tiers e Selos Visuais
    tiers_info = df_atual["preco_atual"].apply(classificar_tier)
    df_atual["tier"] = [t[0] for t in tiers_info]
    df_atual["selo_tier"] = [t[1] for t in tiers_info]

    # Pré-seleciona candidatos a anomalia por Tier (antes do check do Mercado Livre)
    def pre_candidato_anomalia(row: pd.Series) -> bool:
        est = int(row["estoque"])
        if est <= 0:
            return False
        tier = row["tier"]
        desc_real = float(row["desconto_real"])
        desc_tab = float(row["desconto_tabela"])

        if tier == "TIER_1":
            if bool(row["tem_historico"]):
                return desc_real >= 0.35
            return desc_tab >= 0.45
        if tier == "TIER_2":
            return desc_real >= 0.28 and est <= 36
        if tier == "TIER_3":
            return desc_real >= 0.22 and est <= 24
        return False

    df_atual["pre_candidato"] = df_atual.apply(pre_candidato_anomalia, axis=1)
    df_atual = df_atual.sort_values(by="desconto_real", ascending=False).reset_index(drop=True)

    # Consulta a API do Mercado Livre para todos os pré-candidatos e para o Top 10 geral
    indices_para_ml = set(df_atual[df_atual["pre_candidato"]].index.tolist())
    indices_para_ml.update(df_atual.head(10).index.tolist())

    resultados_ml: Dict[int, Dict[str, Any]] = {}
    async with httpx.AsyncClient(verify=False) as client:
        tasks = {
            idx: obter_preco_mercado_ml(
                nome_vinho=str(df_atual.loc[idx, "nome"]),
                preco_referencia_fallback=float(df_atual.loc[idx, "preco_referencia"]),
                client=client,
            )
            for idx in indices_para_ml
        }
        if tasks:
            res_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for idx, res in zip(tasks.keys(), res_list):
                if isinstance(res, dict):
                    resultados_ml[idx] = res

    df_atual["preco_mercado_ml"] = [
        resultados_ml.get(i, {}).get("preco_mercado_ml", float(df_atual.loc[i, "preco_referencia"]))
        for i in df_atual.index
    ]
    df_atual["fonte_ml"] = [
        resultados_ml.get(i, {}).get("fonte_ml", "Benchmark Mercado")
        for i in df_atual.index
    ]
    df_atual["desconto_vs_ml"] = df_atual.apply(
        lambda r: (
            (r["preco_mercado_ml"] - r["preco_atual"]) / r["preco_mercado_ml"]
            if r["preco_mercado_ml"] > 0
            else 0.0
        ),
        axis=1,
    )

    # Validação final da Regra de Tiers + Anti-Falso-Desconto (Mercado Livre)
    def validar_anomalia_final(row: pd.Series) -> bool:
        if not bool(row["pre_candidato"]):
            return False
        if row["tier"] == "TIER_1":
            # Tier 1 exige ser pelo menos 25% abaixo do preço do Mercado Livre
            return float(row["desconto_vs_ml"]) >= 0.25
        return True

    df_atual["anomalia_confirmada"] = df_atual.apply(validar_anomalia_final, axis=1)
    df_anomalias = df_atual[df_atual["anomalia_confirmada"]].copy()

    if not ignorar_alertas_hoje and not df_anomalias.empty:
        mask_nao_enviado = ~df_anomalias["sku"].apply(
            lambda sku: database.ja_alertado_hoje(sku, db_path=db_path)
        )
        df_anomalias = df_anomalias[mask_nao_enviado].copy()

    df_anomalias = df_anomalias.sort_values(by="desconto_real", ascending=False).reset_index(drop=True)
    return df_anomalias, df_atual


def analisar_produtos(
    produtos: List[Dict[str, Any]],
    db_path: str = config.DB_PATH,
    ignorar_alertas_hoje: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Wrapper síncrono caso chamado fora de uma corrotina.
    """
    return asyncio.run(
        analisar_produtos_async(
            produtos=produtos,
            db_path=db_path,
            ignorar_alertas_hoje=ignorar_alertas_hoje,
        )
    )
