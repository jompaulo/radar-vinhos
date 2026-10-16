from typing import List, Dict, Any
from providers.vtex_provider import VTEXProvider, coletar_todas_camadas, passes_filters


async def scrape_all_stores() -> List[Dict[str, Any]]:
    """
    Delega a coleta para a nova arquitetura modular em `providers/vtex_provider.py`.
    """
    return await coletar_todas_camadas()


__all__ = ["VTEXProvider", "coletar_todas_camadas", "scrape_all_stores", "passes_filters"]
