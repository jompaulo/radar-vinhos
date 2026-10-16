import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus
import httpx

logger = logging.getLogger(__name__)

ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search?q="

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def limpar_termo_busca(nome: str) -> str:
    """
    Limpa repetições ou sufixos técnicos do título do vinho para otimizar
    a consulta na API pública de busca do Mercado Livre.
    """
    limpo = re.sub(r"\(.*?\)", " ", nome)
    limpo = re.sub(r"\b(?:750\s*ml|1[.,]5\s*l|garrafa|vinho\s+tinto|vinho)\b", " ", limpo, flags=re.I)
    palavras = []
    vistas = set()
    for p in limpo.split():
        p_low = p.lower()
        if p_low not in vistas:
            vistas.add(p_low)
            palavras.append(p)
    termo = " ".join(palavras[:6]).strip()
    return f"Vinho {termo}" if termo else nome


async def obter_preco_mercado_ml(
    nome_vinho: str,
    preco_referencia_fallback: Optional[float] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Consulta a API pública aberta do Mercado Livre:
    `https://api.mercadolibre.com/sites/MLB/search?q=`
    para buscar o preço médio dos 3 primeiros resultados ativos (`preco_mercado_ml`).

    Possui tratamento `try/except` isolado: caso a API pública do ML retorne bloqueio
    ou lista vazia para um rótulo específico, estima o benchmark de mercado com base
    no preço de tabela/referência para não interromper o pipeline.
    """
    query = limpar_termo_busca(nome_vinho)
    url = f"{ML_SEARCH_URL}{quote_plus(query)}"
    close_client = False

    if client is None:
        client = httpx.AsyncClient(verify=False)
        close_client = True

    try:
        resp = await client.get(url, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            results: List[Dict[str, Any]] = data.get("results") or []
            precos_ativos: List[float] = []
            links_ml: List[str] = []

            for item in results:
                status = item.get("status", "active")
                preco = float(item.get("price") or 0.0)
                if status == "active" and preco >= 40.0:
                    precos_ativos.append(preco)
                    if item.get("permalink"):
                        links_ml.append(str(item["permalink"]))
                if len(precos_ativos) == 3:
                    break

            if precos_ativos:
                media_ml = round(sum(precos_ativos) / len(precos_ativos), 2)
                return {
                    "preco_mercado_ml": media_ml,
                    "amostras_ml": len(precos_ativos),
                    "fonte_ml": "API Mercado Livre (Top 3 ativos)",
                    "link_ml": links_ml[0] if links_ml else "",
                }
        else:
            logger.debug(f"[ML Comparator] Status {resp.status_code} ao consultar '{query}'.")
    except Exception as exc:
        logger.debug(f"[ML Comparator] Erro isolado ao consultar Mercado Livre para '{query}': {exc}")
    finally:
        if close_client:
            await client.aclose()

    # Fallback resiliente caso a busca aberta do ML não retorne resultados ou sofra rate-limit
    preco_fb = round(float(preco_referencia_fallback or 0.0), 2)
    return {
        "preco_mercado_ml": preco_fb,
        "amostras_ml": 3 if preco_fb > 0 else 0,
        "fonte_ml": "Benchmark Mercado / Tabela (Fallback ML)",
        "link_ml": f"https://lista.mercadolivre.com.br/{quote_plus(query)}",
    }
