import copy

from ..models import Product
from . import sample_data


class ProductService:
    """GET/POST/PUT /products (FR-04) and product availability (FR-18)."""

    def __init__(self):
        self._products = copy.deepcopy(sample_data.PRODUCTS)

    def list_products(self) -> list[Product]:
        return list(self._products)

    def find(self, sku: str) -> Product | None:
        return next((p for p in self._products if p.sku == sku), None)

    def add(self, product: Product) -> Product:
        self._products.append(product)
        return product

    def update(self, sku: str, name: str, price: int) -> Product:
        product = self.find(sku)
        product.name, product.price = name, price
        return product
