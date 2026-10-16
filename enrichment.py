import logging
from typing import Dict, Any
from google import genai
import config
from analyzer import classificar_tier

logger = logging.getLogger(__name__)


def _fallback_card(item: Dict[str, Any]) -> str:
    """
    Gera um card técnico completo em Markdown caso a chave GEMINI_API_KEY
    não esteja configurada no ambiente de teste/dry-run ou ocorra erro na API.
    Inclui selo visual por Tier, comparativo com o Mercado Livre e assinatura oficial.
    """
    nome = item.get("nome", "Vinho Selecionado")
    marca = item.get("marca", "Produtor Selecionado")
    loja = item.get("loja", "E-commerce")
    preco_ref = float(item.get("preco_referencia", item.get("preco_tabela", 0.0)))
    preco_atual = float(item.get("preco_atual", 0.0))
    desconto_pct = float(item.get("desconto_real", 0.0)) * 100
    preco_ml = float(item.get("preco_mercado_ml", preco_ref))
    desconto_ml_pct = float(item.get("desconto_vs_ml", 0.0)) * 100
    estoque = int(item.get("estoque", 0))
    link = item.get("link", "#")

    _, selo_default = classificar_tier(preco_atual)
    selo_tier = item.get("selo_tier") or selo_default

    nome_l = nome.lower()
    if "malbec" in nome_l or "catena" in nome_l or "angelica zapata" in nome_l or "enemigo" in nome_l:
        regiao_estilo = "Mendoza, Argentina | Tinto Encorpado"
    elif "brunello" in nome_l or "tignanello" in nome_l:
        regiao_estilo = "Toscana, Itália | Sangiovese de Guarda"
    elif "barolo" in nome_l:
        regiao_estilo = "Piemonte, Itália | Nebbiolo Clássico"
    elif "bordeaux" in nome_l or "château" in nome_l or "chateau" in nome_l:
        regiao_estilo = "Bordeaux, França | Corte Bordalês"
    elif "almaviva" in nome_l or "cabernet" in nome_l or "gran reserva" in nome_l:
        regiao_estilo = "Vale do Maipo / Andes | Cabernet Estruturado"
    elif "chardonnay" in nome_l:
        regiao_estilo = "Branco de Alta Gama | Chardonnay Maturado"
    else:
        regiao_estilo = f"{marca} | Tinto Selecionado"

    return (
        f"{selo_tier}\n"
        f"🍷 *{nome}*\n"
        f"📍 *Região/Estilo estimado:* {regiao_estilo}\n"
        f"🏅 *Por que vale a pena:* Rótulo de destaque do produtor *{marca}* com estrutura gastronômica e excelente potencial em taça.\n"
        f"💰 *Preço Médio vs. Preço Agora:* De ~R$ {preco_ref:,.2f}~ por *R$ {preco_atual:,.2f}* (*-{desconto_pct:.1f}% OFF real*)\n"
        f"📊 *Comparador Mercado Livre (Top 3):* Média de *R$ {preco_ml:,.2f}* no ML (*-{desconto_ml_pct:.1f}% de assimetria real*)\n"
        f"⏳ *Alerta de Estoque:* Apenas *{estoque} garrafas* disponíveis na {loja}!\n"
        f"🔗 [Comprar agora na {loja}]({link})\n\n"
        f"{config.ASSINATURA_OFICIAL}"
    )


def gerar_card_telegram(item: Dict[str, Any]) -> str:
    """
    Utiliza a API do Gemini (`gemini-2.5-flash`) para gerar os cards em Markdown do Telegram,
    adicionando os selos visuais automáticos (🟢 [RADAR DIA A DIA], 🟡 [RADAR RESERVA] ou 🔴 [RADAR ALTA GAMA]),
    os dados do Comparador do Mercado Livre e a assinatura oficial no rodapé.
    """
    nome = item.get("nome", "")
    marca = item.get("marca", "")
    loja = item.get("loja", "")
    preco_ref = float(item.get("preco_referencia", item.get("preco_tabela", 0.0)))
    preco_atual = float(item.get("preco_atual", 0.0))
    desconto_pct = float(item.get("desconto_real", 0.0)) * 100
    preco_ml = float(item.get("preco_mercado_ml", preco_ref))
    desconto_ml_pct = float(item.get("desconto_vs_ml", 0.0)) * 100
    estoque = int(item.get("estoque", 0))
    link = item.get("link", "")

    _, selo_default = classificar_tier(preco_atual)
    selo_tier = item.get("selo_tier") or selo_default

    if not config.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY ausente; utilizando gerador de card técnico local (fallback).")
        return _fallback_card(item)

    prompt = f"""
Você é um sommelier especialista em mercado de vinhos no Brasil.
Gere um card conciso e elegante em formato Markdown para Telegram sobre a seguinte anomalia de preço:

- Selo Visual Obrigatório no Topo: {selo_tier}
- Nome do Vinho: {nome}
- Produtor/Marca: {marca}
- Loja: {loja}
- Preço Normal (Referência): R$ {preco_ref:.2f}
- Preço Agora: R$ {preco_atual:.2f} (-{desconto_pct:.1f}% de queda)
- Preço Médio no Mercado Livre (Top 3 ativos): R$ {preco_ml:.2f} (-{desconto_ml_pct:.1f}% abaixo do ML)
- Estoque disponível: {estoque} unidades
- Link: {link}
- Assinatura Obrigatória no Rodapé: {config.ASSINATURA_OFICIAL}

O card DEVE conter exatamente:
1. Selo Visual no topo: {selo_tier}
2. Nome do Vinho (em destaque)
3. Região/Estilo estimado
4. Por que vale a pena (exatamente 1 frase técnica direta sobre o produtor/corte)
5. Preço Médio vs. Preço Agora (mostrando o valor em R$ e a % de queda: -{desconto_pct:.1f}%)
6. Comparador Mercado Livre (mostrando a média no ML de R$ {preco_ml:.2f} e a assimetria de -{desconto_ml_pct:.1f}%)
7. Alerta de Estoque ({estoque} unidades) e Link clicável
8. No rodapé, exatamente a linha: {config.ASSINATURA_OFICIAL}
""".strip()

    try:
        import httpx
        from google.genai import types
        http_client = httpx.Client(verify=False, timeout=25.0)
        client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(httpx_client=http_client),
        )
        response = None
        for model_name in ("gemini-2.5-flash", "gemini-3.8-flash"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                if response and response.text:
                    break
            except Exception as model_exc:
                if model_name == "gemini-2.5-flash":
                    logger.info(
                        "Modelo 'gemini-2.5-flash' indisponível para esta chave; alternando automaticamente para 'gemini-3.8-flash'..."
                    )
                    continue
                raise model_exc

        if response and response.text:
            texto = response.text.strip()
            if selo_tier not in texto:
                texto = f"{selo_tier}\n{texto}"
            if config.ASSINATURA_OFICIAL not in texto:
                texto = f"{texto}\n\n{config.ASSINATURA_OFICIAL}"
            return texto
    except Exception as exc:
        logger.warning(f"Erro ao chamar Gemini (gemini-2.5-flash) para '{nome}': {exc}. Usando fallback.")

    return _fallback_card(item)
