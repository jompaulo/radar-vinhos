import argparse
import asyncio
import logging
import sys
import pandas as pd

import database
import analyzer
import enrichment
import notifier
from providers.vtex_provider import coletar_todas_camadas

# Garante saída UTF-8 no terminal do Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("radar_vinhos")


async def executar_radar(dry_run: bool = False, max_envios: int = 5) -> None:
    logger.info("Iniciando Radar Vinhos em Modo de Produção (Multi-Provider + Comparador Mercado Livre)...")
    database.init_db()

    # 1. Coleta isolada por loja em todas as camadas (VTEX, Shopify/Boutiques, Marketplaces/E-commerces)
    produtos = await coletar_todas_camadas()
    logger.info(f"Total de vinhos aprovados nos filtros: {len(produtos)}")

    if not produtos:
        logger.warning("Nenhum produto retornou das lojas consultadas.")
        return

    # 2. Análise escalonada por Tiers (Tier 1, Tier 2, Tier 3) + Anti-Falso-Desconto (Mercado Livre)
    df_anomalias, df_todos = await analyzer.analisar_produtos_async(
        produtos,
        ignorar_alertas_hoje=dry_run,
    )

    logger.info(
        f"Análise concluída: {len(df_todos)} vinhos processados | "
        f"{len(df_anomalias)} anomalias inéditas hoje confirmadas pelas regras de Tiers & Mercado Livre."
    )

    # Seleciona as melhores oportunidades priorizando diversidade de Tiers (Tier 3, Tier 2, Tier 1)
    partes_tier = []
    for t_code in ("TIER_3", "TIER_2", "TIER_1"):
        sub_t = df_anomalias[df_anomalias["tier"] == t_code]
        if not sub_t.empty:
            partes_tier.append(sub_t.head(2 if t_code != "TIER_3" else 1))
    if partes_tier:
        df_lote = pd.concat(partes_tier, ignore_index=True).drop_duplicates(subset=["sku"]).head(max_envios)
    else:
        df_lote = df_anomalias.head(max_envios).copy()

    if len(df_lote) < max_envios and not df_anomalias.empty:
        faltam = max_envios - len(df_lote)
        skus_ja_incluidos = set(df_lote["sku"].tolist())
        restantes_anom = df_anomalias[~df_anomalias["sku"].isin(skus_ja_incluidos)].head(faltam)
        if not restantes_anom.empty:
            df_lote = pd.concat([df_lote, restantes_anom], ignore_index=True)

    if dry_run:
        print("\n" + "=" * 84)
        print("🍷 RADAR VINHOS — MODO DRY-RUN (TOP 5 OPORTUNIDADES COM COMPARADOR MERCADO LIVRE)")
        print("=" * 84)

        for idx, row in df_lote.iterrows():
            item = row.to_dict()
            card = enrichment.gerar_card_telegram(item)
            print(f"\n[{idx + 1}/{len(df_lote)}] 🚨 ANOMALIA CONFIRMADA ({item['tier']}) | Origem Ref.: {item['origem_referencia']}")
            print("-" * 84)
            print(card)
            print("-" * 84)

        print("\n✅ Dry-run finalizado com sucesso! Histórico gravado em 'radar_vinhos.db'.\n")
        return

    # 3. Fluxo de Produção Padrão: envia alertas reais ao Telegram (@radarvinhos) e registra no SQLite
    if df_lote.empty:
        logger.info("Nenhuma anomalia nova para alertar no Telegram neste ciclo.")
        return

    print("\n" + "=" * 84)
    print(f"🚀 RADAR VINHOS — MODO PRODUÇÃO: DISPARANDO {len(df_lote)} ALERTAS PARA O TELEGRAM")
    print("=" * 84)

    enviados_sucesso = 0
    for idx, row in df_lote.iterrows():
        item = row.to_dict()
        card = enrichment.gerar_card_telegram(item)
        ok = await notifier.disparar_alerta(item, card)
        status_envio = "✅ ENVIADO E REGISTRADO NO SQLITE" if ok else "❌ FALHA NO ENVIO"
        if ok:
            enviados_sucesso += 1

        print(f"\n[{idx + 1}/{len(df_lote)}] {status_envio} | SKU: {item['sku']} ({item['tier']})")
        print("-" * 84)
        print(card)
        print("-" * 84)
        await asyncio.sleep(1.0)  # Evita rate-limit da API do Telegram

    print(
        f"\n🎯 Ciclo de produção concluído: {enviados_sucesso}/{len(df_lote)} alertas enviados ao canal "
        f"e gravados na tabela 'alertas_enviados' de 'radar_vinhos.db'!\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Radar Vinhos - Monitor multi-provider de anomalias reais de preços com envio para o Telegram."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Apenas imprime no terminal sem enviar ao Telegram.",
    )
    parser.add_argument(
        "--max-envios",
        type=int,
        default=5,
        help="Número máximo de alertas disparados por ciclo de execução (padrão: 5).",
    )
    args = parser.parse_args()
    asyncio.run(executar_radar(dry_run=args.dry_run, max_envios=args.max_envios))


if __name__ == "__main__":
    main()
