import asyncio
import html
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx
import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def passes_filters(nome: str, preco_atual: float) -> bool:
    """
    Aplica os filtros estritos de termos positivos, negativos e faixa global (R$ 50 a R$ 3.500)
    definidos em config.py.
    """
    if not (config.PRECO_MIN <= preco_atual <= config.PRECO_MAX):
        return False

    nome_lower = nome.lower()

    for termo_neg in config.TERMOS_NEGATIVOS:
        if termo_neg.lower() in nome_lower:
            return False

    if not any(termo_pos.lower() in nome_lower for termo_pos in config.TERMOS_POSITIVOS):
        return False

    return True


class BaseWineProvider(ABC):
    """
    Classe base para todos os providers de coleta com isolamento de falhas (try/except por loja).
    """

    @abstractmethod
    async def fetch_store(self, client: httpx.AsyncClient, store: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass


class VTEXProvider(BaseWineProvider):
    """
    Varre as lojas configuradas na camada VTEX (incluindo fallback adaptativo para
    Grand Cru e Zahil) coletando sku, nome, marca, preco_tabela, preco_atual, estoque e link.
    """

    @staticmethod
    def parse_vtex_products(data: List[Dict[str, Any]], store_name: str, base_url: str) -> List[Dict[str, Any]]:
        produtos_filtrados = []
        if not isinstance(data, list):
            return produtos_filtrados

        for product in data:
            try:
                nome = (product.get("productName") or "").strip()
                marca = (product.get("brand") or "Desconhecida").strip()
                link = product.get("link") or ""
                if link and link.startswith("/"):
                    link = f"{base_url.rstrip('/')}{link}"
                elif not link and product.get("linkText"):
                    link = f"{base_url.rstrip('/')}/{product['linkText']}/p"

                items = product.get("items") or []
                for item in items:
                    raw_sku = str(item.get("itemId") or product.get("productId") or "")
                    if not raw_sku:
                        continue
                    sku = f"{store_name.upper().replace(' ', '_')}_{raw_sku}"
                    item_name = (item.get("nameComplete") or item.get("name") or nome).strip()

                    sellers = item.get("sellers") or []
                    for seller in sellers:
                        offer = seller.get("commertialOffer") or {}
                        preco_tabela = float(offer.get("ListPrice") or 0.0)
                        preco_atual = float(offer.get("Price") or 0.0)
                        estoque = int(offer.get("AvailableQuantity") or 0)

                        if preco_atual <= 0:
                            continue
                        if preco_tabela < preco_atual:
                            preco_tabela = preco_atual

                        link_final = config.converter_link_afiliado(link, store_name)
                        if passes_filters(item_name, preco_atual):
                            produtos_filtrados.append({
                                "sku": sku,
                                "loja": store_name,
                                "nome": item_name,
                                "marca": marca,
                                "preco_tabela": round(preco_tabela, 2),
                                "preco_atual": round(preco_atual, 2),
                                "estoque": estoque,
                                "link": link_final,
                            })
                            break
            except Exception as exc:
                logger.debug(f"Erro ao processar item VTEX em {store_name}: {exc}")

        return produtos_filtrados

    @staticmethod
    def parse_grandcru_products(data: Any, store_name: str, base_url: str) -> List[Dict[str, Any]]:
        produtos_filtrados = []
        items = data if isinstance(data, list) else (data.get("items") or [])
        if not isinstance(items, list):
            return produtos_filtrados

        for product in items:
            try:
                if not isinstance(product, dict):
                    continue
                raw_sku = str(product.get("sku") or product.get("id") or "").strip()
                nome = (product.get("name") or "").strip()
                if not raw_sku or not nome:
                    continue

                custom_attrs = {
                    a.get("attribute_code"): a.get("value")
                    for a in (product.get("custom_attributes") or [])
                    if isinstance(a, dict) and a.get("attribute_code")
                }
                ext_attrs = product.get("extension_attributes") or {}

                preco_tabela = float(product.get("price") or 0.0)
                preco_atual = float(
                    ext_attrs.get("product_final_price")
                    or custom_attrs.get("special_price")
                    or preco_tabela
                )
                if preco_atual <= 0:
                    continue
                if preco_tabela < preco_atual:
                    preco_tabela = preco_atual

                status_ativo = int(product.get("status") or 0) == 1
                estoque = int(ext_attrs.get("stock_qty") or (12 if status_ativo else 0))

                url_key = custom_attrs.get("url_key") or ""
                link = f"{base_url.rstrip('/')}/{url_key}" if url_key else base_url

                categorias_nomes = " ".join(
                    c.get("name", "") for c in (ext_attrs.get("categories") or []) if isinstance(c, dict)
                )
                nome_avaliacao = f"{nome} {categorias_nomes}".strip()
                raw_winery = str(custom_attrs.get("winery") or "").strip()
                if raw_winery and not raw_winery.isdigit():
                    marca = raw_winery
                else:
                    marca = " ".join(nome.split()[:2]) if nome else "Grand Cru Selection"

                if passes_filters(nome_avaliacao, preco_atual):
                    produtos_filtrados.append({
                        "sku": f"GRAND_CRU_{raw_sku}",
                        "loja": store_name,
                        "nome": nome,
                        "marca": marca,
                        "preco_tabela": round(preco_tabela, 2),
                        "preco_atual": round(preco_atual, 2),
                        "estoque": estoque,
                        "link": link,
                    })
            except Exception as exc:
                logger.debug(f"Erro ao processar item Grand Cru: {exc}")

        return produtos_filtrados

    @staticmethod
    def parse_zahil_products(data: Any, store_name: str, base_url: str) -> List[Dict[str, Any]]:
        produtos_filtrados = []
        if not isinstance(data, list):
            return produtos_filtrados

        mapa_precos = {
            "range-de-preco-ate-r-150": 135.00,
            "range-de-preco-de-r-151-a-r-350": 245.00,
            "range-de-preco-acima-de-r-501": 445.00,
            "range-de-preco-acima-de-r-551": 650.00,
        }

        for post in data:
            try:
                if not isinstance(post, dict):
                    continue
                raw_id = str(post.get("id") or "")
                raw_title = (post.get("title") or {}).get("rendered") or ""
                nome = html.unescape(raw_title).strip()
                link = post.get("link") or base_url
                class_list = post.get("class_list") or []

                if not raw_id or not nome:
                    continue

                marca = "Zahil Importadora"
                tags_extras = []
                preco_estimado = 245.00

                for cls in class_list:
                    if cls.startswith("produtores-"):
                        marca = cls.replace("produtores-", "").replace("-", " ").title()
                    elif cls.startswith("tipo-") or cls.startswith("uva-") or cls.startswith("regiao-"):
                        tags_extras.append(cls.split("-", 1)[1].replace("-", " "))
                    elif cls in mapa_precos:
                        preco_estimado = mapa_precos[cls]

                texto_avaliacao = f"{nome} {' '.join(tags_extras)}"
                if "tintos" in texto_avaliacao.lower():
                    texto_avaliacao += " Tinto"

                if passes_filters(texto_avaliacao, preco_estimado):
                    produtos_filtrados.append({
                        "sku": f"ZAHIL_{raw_id}",
                        "loja": store_name,
                        "nome": nome,
                        "marca": marca,
                        "preco_tabela": round(preco_estimado, 2),
                        "preco_atual": round(preco_estimado, 2),
                        "estoque": 15,
                        "link": link,
                    })
            except Exception as exc:
                logger.debug(f"Erro ao processar item Zahil: {exc}")

        return produtos_filtrados

    @staticmethod
    def parse_shopify_products(data: Any, store_name: str, base_url: str) -> List[Dict[str, Any]]:
        produtos_filtrados = []
        products = data.get("products") if isinstance(data, dict) else []
        if not isinstance(products, list):
            return produtos_filtrados

        for prod in products:
            try:
                nome = (prod.get("title") or "").strip()
                marca = (prod.get("vendor") or store_name).strip()
                handle = prod.get("handle") or ""
                link = f"{base_url.rstrip('/')}/products/{handle}" if handle else base_url
                tags = prod.get("tags") or []
                tags_str = " ".join(tags) if isinstance(tags, list) else str(tags)

                for variant in (prod.get("variants") or []):
                    raw_sku = str(variant.get("id") or variant.get("sku") or "")
                    preco_atual = float(variant.get("price") or 0.0)
                    preco_tabela = float(variant.get("compare_at_price") or preco_atual)
                    if preco_tabela < preco_atual:
                        preco_tabela = preco_atual
                    disponivel = bool(variant.get("available", True))
                    estoque = 12 if disponivel else 0

                    if preco_atual > 0 and passes_filters(f"{nome} {tags_str}", preco_atual):
                        produtos_filtrados.append({
                            "sku": f"{store_name.upper().replace(' ', '_')}_{raw_sku}",
                            "loja": store_name,
                            "nome": nome,
                            "marca": marca,
                            "preco_tabela": round(preco_tabela, 2),
                            "preco_atual": round(preco_atual, 2),
                            "estoque": estoque,
                            "link": link,
                        })
                        break
            except Exception as exc:
                logger.debug(f"Erro ao processar item Shopify em {store_name}: {exc}")

        return produtos_filtrados

    async def fetch_store(self, client: httpx.AsyncClient, store: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Coleta isolada de uma loja com try/except individual para que falhas nunca interrompam as demais.
        """
        store_name = store.get("nome", "Loja")
        base_url = store.get("base_url", "")
        endpoints = store.get("endpoints", [])
        acumulados: List[Dict[str, Any]] = []

        try:
            for endpoint in endpoints:
                url = f"{base_url.rstrip('/')}{endpoint}"
                try:
                    resp = await client.get(url, headers=HEADERS, timeout=18.0, follow_redirects=True)
                    content_type = resp.headers.get("content-type", "")

                    if resp.status_code not in (200, 206) or "json" not in content_type.lower():
                        logger.debug(
                            f"[{store_name}] Endpoint {endpoint} retornou {resp.status_code}; tentando alternativa..."
                        )
                        continue

                    data = resp.json()
                    if not data:
                        continue

                    if "/api/products" in endpoint:
                        filtrados = self.parse_grandcru_products(data, store_name, base_url)
                        brutos_len = len(data) if isinstance(data, list) else len(data.get("items") or [])
                    elif "/wp-json/wp/v2/vinhos" in endpoint:
                        filtrados = self.parse_zahil_products(data, store_name, base_url)
                        brutos_len = len(data) if isinstance(data, list) else 0
                    elif "/products.json" in endpoint:
                        filtrados = self.parse_shopify_products(data, store_name, base_url)
                        brutos_len = len(data.get("products") or []) if isinstance(data, dict) else 0
                    else:
                        filtrados = self.parse_vtex_products(data, store_name, base_url)
                        brutos_len = len(data) if isinstance(data, list) else 0

                    acumulados.extend(filtrados)
                    logger.info(
                        f"[{store_name}] OK ({resp.status_code}) em {endpoint} -> "
                        f"{brutos_len} brutos | {len(filtrados)} aprovados."
                    )
                except Exception as inner_exc:
                    logger.warning(f"[{store_name}] Falha isolada em {url}: {inner_exc}")
        except Exception as store_exc:
            logger.error(f"[{store_name}] Erro geral isolado no provider: {store_exc}")

        return acumulados


async def coletar_todas_camadas() -> List[Dict[str, Any]]:
    """
    Executa a varredura assíncrona em todas as lojas das camadas configuradas em `config.FONTES_TECNOLOGIA`,
    com isolamento total de falhas por loja e deduplicação por SKU.
    """
    provider = VTEXProvider()
    todas_lojas: List[Dict[str, Any]] = []
    for camada, lojas in config.FONTES_TECNOLOGIA.items():
        todas_lojas.extend(lojas)

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [provider.fetch_store(client, loja) for loja in todas_lojas]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    produtos_unicos: Dict[str, Dict[str, Any]] = {}
    for res in results:
        if isinstance(res, list):
            for prod in res:
                produtos_unicos[prod["sku"]] = prod

    return list(produtos_unicos.values())
