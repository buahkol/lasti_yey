-- SiMonPro — Data awal (seed) untuk pengembangan dan pengujian
-- Akun : operasional / operasional123
-- Perangkat API key (X-Device-Key): simonpro-dev-key-01   (ganti untuk demo)

INSERT INTO pengguna (username, password_hash, nama) VALUES
    ('operasional', '$2b$12$GWG1qIdGzQC1kjCEPlzVgOuRkSX8q0aU42TH0x6Qbqe/M8xMMuiKG', 'Operasional Lini Pengemasan');

INSERT INTO perangkat (nama, api_key_hash) VALUES
    ('ESP32-S3 Kotak Foto 1', '$2b$12$rouj5VvPGixvxsINKfx9Buw4j0OfsJBRQOFUYz7Dp88orXpOCcMxa');

-- Produk sarden. Harga satuan dipakai untuk estimasi loss (NG x harga satuan).
-- DEMO-CAN hanya untuk uji coba pipeline dengan dataset GoodsAD drink_can.
INSERT INTO produk (sku, nama, harga_satuan) VALUES
    ('SRD-TOMAT-155G', 'Sarden Saus Tomat 155 g', 6000),
    ('SRD-CABAI-155G', 'Sarden Saus Cabai 155 g', 6500),
    ('SRD-TOMAT-425G', 'Sarden Saus Tomat 425 g', 15000),
    ('DEMO-CAN',       'Demo GoodsAD drink can',  5000);
