from dataclasses import dataclass


@dataclass
class Product:
    """Sardine can SKU (FR-04) with today's availability of OK cans (FR-18)."""

    sku: str
    name: str
    price: int  # harga satuan in rupiah
    threshold: float = 0.60  # anomaly threshold, set by the AI team
    model_version: str = "belum ada"
    status: str = "DITUTUP"  # status of its latest batch
    ok_today: int = 0
    ok_ratio: float = 0.0  # percent
    updated: str = "baru saja"
    batch_count: int = 0

    @property
    def label(self) -> str:
        return f"{self.name} ({self.sku})"
