import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from dotenv import load_dotenv

load_dotenv()

# Variáveis de ambiente
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_VIP = os.getenv("TELEGRAM_CHAT_ID_VIP", "") or TELEGRAM_CHAT_ID
TELEGRAM_CHAT_ID_FREE = os.getenv("TELEGRAM_CHAT_ID_FREE", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configuração de Afiliado Lomadee para a Vivavinho
LOMADEE_VIVAVINHO_BASE = os.getenv("LOMADEE_VIVAVINHO_BASE", "https://compre.vc/iqaRQK3sSodH")
LOMADEE_VIVAVINHO_PARAMS = {
    "utm_source": "lomadee",
    "utm_medium": "link_generator",
    "utm_campaign": "25cd48f8-b229-4bd8-9476-b08b4eab68c2_1b8e4084-b123-404e-9565-b546424cf839_iqaRQK3sSodH_6PVnBRjghQvxNdG9NbrsUR",
    "lmdeeTracking": "9836071",
    "lomadee_ref": LOMADEE_VIVAVINHO_BASE,
}


def converter_link_afiliado(url: str, loja: str = "") -> str:
    """
    Transforma o link original de uma garrafa da Vivavinho em um Deep Link
    rastreado da Lomadee (preservando o caminho exato da página do produto
    e injetando a assinatura de campanha do link https://compre.vc/iqaRQK3sSodH).
    """
    if not url:
        return url

    url_lower = url.lower()
    loja_lower = (loja or "").lower()
    if "vivavinho.com.br" not in url_lower and "vivavinho" not in loja_lower:
        return url

    try:
        parsed = urlparse(url)
        query_dict = dict(parse_qsl(parsed.query, keep_blank_values=True))
        for k, v in LOMADEE_VIVAVINHO_PARAMS.items():
            query_dict[k] = v
        nova_query = urlencode(query_dict)
        return urlunparse((
            parsed.scheme or "https",
            parsed.netloc or "www.vivavinho.com.br",
            parsed.path,
            parsed.params,
            nova_query,
            parsed.fragment,
        ))
    except Exception:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urlencode(LOMADEE_VIVAVINHO_PARAMS)}"


# Filtros estritos de termos positivos e negativos
TERMOS_POSITIVOS = [
    "Malbec", "Cabernet", "Bordeaux", "Brunello", "Barolo",
    "Pinotage", "Syrah", "Chardonnay", "Blend", "Tinto",
    "Gran Reserva", "Catena", "Angelica Zapata", "Enemigo",
    "Almaviva", "Tignanello", "Château"
]

TERMOS_NEGATIVOS = [
    "Suave", "Demi-Sec", "Sem Álcool", "Cooler", "Lata",
    "Bag in Box", "Taça", "Saca-rolhas"
]

# Faixa global de preços (R$)
PRECO_MIN = 50.00
PRECO_MAX = 3500.00

# Dicionários de fontes por categorias de tecnologia
FONTES_TECNOLOGIA = {
    "vtex": [
        {
            "nome": "Vivavinho",
            "base_url": "https://www.vivavinho.com.br",
            "afiliado_lomadee": LOMADEE_VIVAVINHO_BASE,
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=50&_to=99&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search?_from=0&_to=49&O=OrderByBestDiscountDESC",
            ],
        },
        {
            "nome": "Grand Cru",
            "base_url": "https://www.grandcru.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/products?page=0&pageSize=50&category=102&sort=position&sortDirection=ASC",
                "/api/products?page=1&pageSize=50&category=102&sort=position&sortDirection=ASC",
                "/api/products?page=0&pageSize=50&sort=position&sortDirection=ASC",
            ],
        },
        {
            "nome": "World Wine",
            "base_url": "https://www.worldwine.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=50&_to=99&O=OrderByBestDiscountDESC",
            ],
        },
        {
            "nome": "Zahil",
            "base_url": "https://www.zahil.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/wp-json/wp/v2/vinhos?per_page=50&_embed=1",
            ],
        },
        {
            "nome": "Decanter",
            "base_url": "https://www.decanter.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=50&_to=99&O=OrderByBestDiscountDESC",
            ],
        },
        {
            "nome": "TodoVino",
            "base_url": "https://www.todovino.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search/vinhos?_from=0&_to=49&O=OrderByBestDiscountDESC",
            ],
        },
        {
            "nome": "Divvino",
            "base_url": "https://www.divvino.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=50&_to=99&O=OrderByBestDiscountDESC",
            ],
        },
    ],
    "shopify_boutiques": [
        {
            "nome": "Cellar Vinhos",
            "base_url": "https://www.cellarvinhos.com",
            "endpoints": [
                "/products.json?limit=50",
            ],
        },
        {
            "nome": "Cave Léman",
            "base_url": "https://www.caveleman.com.br",
            "endpoints": [
                "/products.json?limit=50",
            ],
        },
    ],
    "marketplaces_ecommerces": [
        {
            "nome": "Mistral",
            "base_url": "https://www.mistral.com.br",
            "endpoints": [
                "/api/catalog_system/pub/products/search/vinhos/tinto?_from=0&_to=49&O=OrderByBestDiscountDESC",
            ],
        },
        {
            "nome": "Evino Fine Wines",
            "base_url": "https://www.evino.com.br",
            "endpoints": [
                "/api/products?page=0&pageSize=50",
            ],
        },
    ],
}

# Alias de compatibilidade para a camada VTEX
VTEX_STORES = FONTES_TECNOLOGIA["vtex"]

# Assinatura oficial do rodapé
ASSINATURA_OFICIAL = "⚡ *Radar Vinhos — Fase Beta Aberta (Tempo Real)*"

DB_PATH = os.path.join(os.path.dirname(__file__), "radar_vinhos.db")
