import logging
from typing import Dict, Any
import httpx
import config
import database

logger = logging.getLogger(__name__)


async def enviar_telegram(mensagem: str, chat_id: str) -> bool:
    """
    Envia um card formatado em Markdown para o chat/canal especificado no Telegram.
    """
    if not config.TELEGRAM_BOT_TOKEN or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.post(url, json=payload, timeout=15.0)
            if resp.status_code == 200:
                return True
            payload.pop("parse_mode", None)
            resp_retry = await client.post(url, json=payload, timeout=15.0)
            return resp_retry.status_code == 200
    except Exception as exc:
        logger.error(f"Erro ao enviar mensagem para o Telegram ({chat_id}): {exc}")
        return False


async def disparar_alerta(item: Dict[str, Any], card_markdown: str) -> bool:
    """
    Dispara o alerta enriquecido para os canais configurados do Telegram (`TELEGRAM_CHAT_ID`,
    `TELEGRAM_CHAT_ID_VIP`, `TELEGRAM_CHAT_ID_FREE`) sem duplicar envios para o mesmo canal,
    e registra o envio na tabela `alertas_enviados` do SQLite.
    """
    enviado = False
    canais = []
    for cid in (config.TELEGRAM_CHAT_ID, config.TELEGRAM_CHAT_ID_VIP, config.TELEGRAM_CHAT_ID_FREE):
        if cid and cid not in canais:
            canais.append(cid)

    for chat_id in canais:
        ok = await enviar_telegram(card_markdown, chat_id)
        enviado = enviado or ok

    if enviado:
        database.registrar_alerta(
            sku=str(item["sku"]),
            preco_alerta=float(item["preco_atual"]),
            desconto_real=float(item["desconto_real"]),
        )
        logger.info(f"Alerta enviado ao Telegram ({', '.join(canais)}) e registrado: {item['sku']} ({item['nome']}).")
    else:
        logger.warning(
            f"Card gerado para {item['sku']}, mas envio ao Telegram falhou ou não está configurado."
        )

    return enviado
