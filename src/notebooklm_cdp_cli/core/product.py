from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ProductSpec:
    name: str
    hosts: tuple[str, ...]
    default_url: str

    def matches_url(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return any(host == candidate or host.endswith(f".{candidate}") for candidate in self.hosts)


NOTEBOOKLM_PRODUCT = ProductSpec(
    name="notebooklm",
    hosts=("notebooklm.google.com",),
    default_url="https://notebooklm.google.com/",
)


GEMINI_PRODUCT = ProductSpec(
    name="gemini",
    hosts=("gemini.google.com",),
    default_url="https://gemini.google.com/app",
)


FLOW_PRODUCT = ProductSpec(
    name="flow",
    hosts=("labs.google",),
    default_url="https://labs.google/fx/tools/flow?sia=true",
)


COLAB_PRODUCT = ProductSpec(
    name="colab",
    hosts=("colab.research.google.com",),
    default_url="https://colab.research.google.com/",
)


PRODUCT_SPECS = {
    NOTEBOOKLM_PRODUCT.name: NOTEBOOKLM_PRODUCT,
    GEMINI_PRODUCT.name: GEMINI_PRODUCT,
    FLOW_PRODUCT.name: FLOW_PRODUCT,
    COLAB_PRODUCT.name: COLAB_PRODUCT,
}


def get_product_spec(product: str) -> ProductSpec:
    try:
        return PRODUCT_SPECS[product]
    except KeyError as exc:
        raise ValueError(f"Unsupported product: {product}") from exc
