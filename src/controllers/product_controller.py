import re

from ..models import Product
from ..services import ProductService

_SKU = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)+$")


class ProductController:
    """Product list and the add or edit form (FR-04, FR-18)."""

    def __init__(self, service: ProductService):
        self._service = service

    def products(self) -> list[Product]:
        return self._service.list_products()

    def save(self, sku: str, name: str, price_text: str, is_new: bool) -> tuple[Product | None, dict]:
        """Validate the form. Returns the saved product, or field errors keyed by sku, name, price."""
        sku = sku.strip().upper() if is_new else sku.strip()  # an existing SKU is kept exactly as stored
        name = name.strip()
        price_text = price_text.replace(".", "").replace("Rp", "").strip()
        errors = {}
        if not name:
            errors["name"] = "Nama produk wajib diisi."
        if not price_text.isdigit() or int(price_text) <= 0:
            errors["price"] = "Harga satuan harus berupa angka lebih dari 0."
        if is_new:
            if not _SKU.match(sku):
                errors["sku"] = "Format SKU belum sesuai, contoh SDN-TMT-155."
            elif self._service.find(sku):
                errors["sku"] = "SKU sudah terdaftar."
        if errors:
            return None, errors
        if is_new:
            return self._service.add(Product(sku, name, int(price_text))), {}
        return self._service.update(sku, name, int(price_text)), {}
