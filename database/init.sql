-- SiMonPro — Skema Basis Data (Deliverable 3)
-- Layanan pencatatan produksi dan inspeksi kemasan sarden kaleng (IoT + AI)
-- PostgreSQL 15. Mengikuti PRD §11.2.

SET TIME ZONE 'Asia/Jakarta';

CREATE TYPE status_batch    AS ENUM ('BERJALAN', 'DITUTUP');
CREATE TYPE status_inspeksi AS ENUM ('PASSED', 'HOLD');
CREATE TYPE hasil_inspeksi  AS ENUM ('OK', 'NG');
CREATE TYPE jenis_kejadian  AS ENUM ('REJECT', 'BAHAN_BAKU_HABIS', 'ALAT_BERHENTI', 'RATE_DROP');
CREATE TYPE sumber_kejadian AS ENUM ('AI', 'OPERATOR', 'SENSOR');

-- Pengguna aplikasi (satu peran: Operasional). Password disimpan sebagai hash bcrypt (FR-02).
CREATE TABLE pengguna (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT         NOT NULL,
    nama          VARCHAR(150),
    dibuat_pada   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Sesi login aplikasi desktop. Token disimpan sebagai SHA-256, bukan teks asli.
CREATE TABLE sesi (
    token_hash  CHAR(64)    PRIMARY KEY,
    id_pengguna INT         NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT now(),
    kedaluwarsa TIMESTAMPTZ NOT NULL,
    aktif       BOOLEAN     NOT NULL DEFAULT TRUE
);

-- Perangkat IoT (ESP32-S3). API key disimpan sebagai hash bcrypt.
CREATE TABLE perangkat (
    id           SERIAL PRIMARY KEY,
    nama         VARCHAR(100) NOT NULL,
    api_key_hash TEXT         NOT NULL,
    aktif        BOOLEAN      NOT NULL DEFAULT TRUE
);

-- Produk. versi_model dan ambang_batas diisi server saat memuat memory bank PatchCore.
CREATE TABLE produk (
    sku          VARCHAR(30)   PRIMARY KEY,
    nama         VARCHAR(150)  NOT NULL,
    harga_satuan NUMERIC(12,2) NOT NULL CHECK (harga_satuan >= 0),
    versi_model  VARCHAR(30),
    ambang_batas DOUBLE PRECISION
);

CREATE TABLE batch (
    kode_batch      VARCHAR(40)     PRIMARY KEY,
    sku             VARCHAR(30)     NOT NULL REFERENCES produk(sku),
    status_batch    status_batch    NOT NULL DEFAULT 'BERJALAN',
    status_inspeksi status_inspeksi NOT NULL DEFAULT 'HOLD',
    mulai           TIMESTAMPTZ     NOT NULL DEFAULT now(),
    selesai         TIMESTAMPTZ
);

CREATE TABLE output_produksi (
    id         SERIAL      PRIMARY KEY,
    kode_batch VARCHAR(40) NOT NULL REFERENCES batch(kode_batch),
    jumlah     INT         NOT NULL CHECK (jumlah > 0),
    waktu      TIMESTAMPTZ NOT NULL
);

CREATE TABLE inspeksi (
    id           BIGSERIAL        PRIMARY KEY,
    kode_batch   VARCHAR(40)      NOT NULL REFERENCES batch(kode_batch),
    hasil        hasil_inspeksi   NOT NULL,
    skor_anomali DOUBLE PRECISION NOT NULL,   -- skor ternormalisasi 0..1
    skor_mentah  DOUBLE PRECISION,            -- jarak kNN PatchCore sebelum normalisasi
    ambang_batas DOUBLE PRECISION NOT NULL,
    versi_model  VARCHAR(30)      NOT NULL,
    lokasi_citra TEXT             NOT NULL,
    waktu        TIMESTAMPTZ      NOT NULL,   -- waktu gambar diambil (dari perangkat)
    diterima     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    latensi_ms   INT                          -- waktu proses di server
);

CREATE TABLE kejadian_produksi (
    id          SERIAL          PRIMARY KEY,
    kode_batch  VARCHAR(40)     NOT NULL REFERENCES batch(kode_batch),
    jenis       jenis_kejadian  NOT NULL,
    sumber      sumber_kejadian NOT NULL,
    keterangan  TEXT,
    waktu       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    id_inspeksi BIGINT          REFERENCES inspeksi(id)
);

CREATE INDEX idx_inspeksi_batch_waktu ON inspeksi (kode_batch, waktu);
CREATE INDEX idx_inspeksi_hasil_waktu ON inspeksi (hasil, waktu);
CREATE INDEX idx_output_batch         ON output_produksi (kode_batch);
CREATE INDEX idx_kejadian_batch       ON kejadian_produksi (kode_batch, waktu);
CREATE INDEX idx_batch_sku            ON batch (sku);
