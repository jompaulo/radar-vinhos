import os
from dotenv import load_dotenv

load_dotenv()

# Variáveis de ambiente
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_VIP = os.getenv("TELEGRAM_CHAT_ID_VIP", "") or TELEGRAM_CHAT_ID
TELEGRAM_CHAT_ID_FREE = os.getenv("TELEGRAM_CHAT_ID_FREE", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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
