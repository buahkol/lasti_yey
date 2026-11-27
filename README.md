# SiMonPro - Sistem Monitoring Produksi

Pencatatan produksi dan inspeksi kemasan sarden kaleng berbasis IoT dan AI. Perangkat ESP32-S3 dengan
kamera OV5640 memotret setiap kaleng yang lewat sensor IR, server memeriksanya dengan model PatchCore
(deteksi anomali), LED merah menyala bila kaleng NG, dan operator memantau semuanya di aplikasi desktop.

---

## Arsitektur

| Bagian | Berjalan di | Panduan |
|---|---|---|
| PostgreSQL 15 | Docker/Podman, port 5433 | bagian *Menjalankan* di bawah |
| Server REST API + PatchCore (FastAPI) | edge server (GPU) atau laptop (CPU), port 8000 | [`server/README.md`](server/README.md) |
| Perangkat ESP32-S3 + OV5640 + sensor IR | kotak foto di lini | [`firmware/README.md`](firmware/README.md) |
| Aplikasi desktop (PyQt6) | komputer operator | bagian *Menjalankan* di bawah |

```
ESP32 --(Wi-Fi, HTTP)--> server :8000 --> PostgreSQL :5433
                            ^
aplikasi desktop --(REST /api/v1)--+
```

**Aplikasi desktop tidak membaca database langsung.** Semua data (produk, batch, inspeksi, foto, kejadian,
laporan) diambil dari server lewat REST API `/api/v1`. Tanpa server yang berjalan, aplikasi hanya bisa
dibuka dalam mode data contoh (lihat di bawah).

---

## Prasyarat

- [uv](https://docs.astral.sh/uv/) (mengatur Python dan semua dependensi; Python 3.10 atau lebih baru)
- Docker Desktop (Windows) atau Docker/Podman (Linux) untuk PostgreSQL
- Git
- Opsional: GPU NVIDIA untuk server (CPU juga bisa, lihat [CPU atau GPU](server/README.md#cpu-or-gpu))

Instalasi otomatis (Python, uv, Docker, shortcut desktop, `uv sync`, `docker compose up -d`):

- **Windows** (PowerShell sebagai Administrator): `.\install.ps1`
- **Linux**: `chmod +x install.sh && ./install.sh`

Skrip ini hanya menyiapkan **aplikasi desktop dan database**. Dependensi server dipasang terpisah
(langkah 2 di bawah).

---

## Menjalankan

Semua perintah dijalankan dari folder repositori.

```bash
git clone https://github.com/buahkol/lasti_yey.git
cd lasti_yey
```

### 1. Database

```bash
docker compose up -d          # PostgreSQL 15 di port 5433; init.sql + dummy.sql dimuat saat pertama dibuat
docker compose ps             # status harus "running"
```

Database yang dibuat **sebelum 27 Nov 2026** perlu migrasi satu kali (jenis kejadian bebas):

```bash
docker compose exec -T postgres psql -U postgres -d simonpro < database/migrations/2026-11-27-event-kinds.sql
```

PowerShell tidak mendukung `<`; gunakan:

```powershell
Get-Content database\migrations\2026-11-27-event-kinds.sql | docker compose exec -T postgres psql -U postgres -d simonpro
```

### 2. Server

```bash
uv sync --group server --group ml-cpu      # tanpa GPU NVIDIA (unduhan ~250 MB)
uv sync --group server --group ml          # dengan GPU NVIDIA (CUDA, ~3 GB)
uv run uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

Biarkan terminal ini tetap terbuka. Di terminal lain, periksa:

```bash
curl http://localhost:8000/api/v1/health       # PowerShell: curl.exe http://localhost:8000/api/v1/health
```

Jawaban yang benar memuat `"status":"ok"` dan model `PLS-Sarden` (model showcase ada di `models/`).
Dokumentasi API interaktif: `http://localhost:8000/docs`.

> **Penting:** `uv sync` tanpa `--group` **menghapus** paket server (torch, fastapi). Selalu sertakan grup
> yang dipakai saat menjalankan `uv sync` lagi.

### 3. Aplikasi desktop

```bash
uv run python main.py
```

- **Windows/PowerShell:** ketik `uv run python main.py` (atau `.\run-simonpro.ps1`), **bukan** `main.py` saja.
- Server di komputer lain: atur alamatnya dulu.
  - PowerShell: `$env:SIMONPRO_API_URL = "http://192.168.1.15:8000/api/v1"; uv run python main.py`
  - Linux: `SIMONPRO_API_URL=http://192.168.1.15:8000/api/v1 uv run python main.py`
- Tanpa server (hanya melihat tampilan dengan data contoh yang tetap): `SIMONPRO_SAMPLE=1`
  (PowerShell: `$env:SIMONPRO_SAMPLE = "1"`), login `operasional` / `simonpro`.

**Login** (akun dari `database/dummy.sql`): username `operasional`, password `operasional123`.
Ganti sebelum dipakai di lini.

### 4. Perangkat ESP32

Lihat [`firmware/README.md`](firmware/README.md): flash, Wi-Fi, alamat server
(`set server http://<IP komputer server>:8000/api/v1`), arah sensor (`irlevel`), pencahayaan dan kamera.
Perangkat dan komputer server harus berada di jaringan Wi-Fi yang sama.

---

## Alur pemakaian

1. **Produk**: daftarkan SKU dan harga satuan (dipakai untuk estimasi kerugian). Ambang batas dan versi
   model terisi otomatis setelah server memuat model PatchCore untuk SKU itu.
2. **Batch**: buat batch (format `B-YYMM-NN`, contoh `B-2611-01`). Perangkat otomatis mengikuti batch yang
   sedang berjalan (paling baru) dalam 5 detik; kode batch tidak perlu diketik di perangkat.
3. Letakkan kaleng di depan sensor dan **biarkan sampai LED bereaksi** (sekitar 2 detik).
4. **Dashboard** diperbarui setiap 5 detik. Halaman lain punya tombol ⟳ (Muat ulang data) di kanan atas.
5. **Alert** menampilkan kaleng NG; **Riwayat** menampilkan foto setiap kaleng (OK dan NG) per batch.
6. **Kejadian**: catat kejadian manual (bahan baku habis, alat berhenti, atau jenis yang diketik sendiri).
   REJECT dicatat otomatis oleh AI.
7. **Laporan**: laporan per batch dan rekap per tanggal, bisa diekspor ke PDF.
8. **Tutup batch** menghitung status akhir: PASSED bila NG paling banyak 5%, selain itu HOLD.

Setiap inspeksi menyimpan ambang dan versi model yang dipakai saat itu, jadi mengubah ambang tidak
mengubah putusan kaleng yang sudah diperiksa.

---

## Masalah umum

| Gejala | Penyebab dan solusi |
|---|---|
| Login: "Server SiMonPro tidak dapat dihubungi" | Server belum berjalan atau alamat salah. Jalankan langkah 2 dan cek `/api/v1/health`; atur `SIMONPRO_API_URL` bila server di komputer lain. |
| Login berhasil tetapi muncul "Gagal membuka aplikasi" | Pesan menyebutkan penyebabnya. Pastikan kode terbaru (`git pull`), server terbaru (restart setelah pull), dan migrasi database sudah dijalankan. |
| `IndexError` di `kejadian.py` setelah login | Versi lama tidak bisa dibuka pada database tanpa batch. Sudah diperbaiki; `git pull`. |
| `qt.qpa.windowclass: Failed to register window class ... Class already exists` | Peringatan Qt di Windows, tidak berbahaya. |
| PowerShell: "The command main.py was not found" | Jalankan `uv run python main.py`. |
| Server: `ModuleNotFoundError: torch` / `fastapi` | Dependensi server terhapus oleh `uv sync` tanpa grup. Ulangi `uv sync --group server --group ml-cpu`. |
| Linux (Nix): `libstdc++.so.6: cannot open shared object file` saat impor numpy | `.venv` dibuat dari Python Nix. Buat ulang: `rm -rf .venv && uv sync --python-preference only-managed ...`. |
| Semua kaleng NG dengan skor 1,00 | Foto tidak mirip data latih: cahaya, white balance, posisi kamera atau kaleng berubah. Lihat `firmware/README.md` (bagian kamera) dan [`server/README.md`](server/README.md). |

---

## Halaman aplikasi

| Halaman | Isi |
|---|---|
| Login | Autentikasi ke server (token sesi, berlaku 12 jam). |
| Dashboard | Batch aktif, output hari ini, OK/NG, grafik output per jam, alert terbaru; diperbarui setiap 5 detik. |
| Produk | Daftar SKU, harga, ambang batas dan versi model; ketersediaan kaleng OK hari ini. |
| Batch | Daftar batch dengan filter, buat batch, tutup batch, ekspor PDF. |
| Alert | Kaleng NG terbaru dengan foto dan skor anomali, per rentang waktu. |
| Laporan | Laporan inspeksi per batch dan rekap produksi per tanggal (PDF). |
| Kejadian | Kejadian produksi per batch; catat kejadian manual. |
| Riwayat | Folder foto per batch berisi setiap kaleng yang diperiksa (OK dan NG). |

---

## Tabel basis data

Skema lengkap: [`database/init.sql`](database/init.sql). Data awal: [`database/dummy.sql`](database/dummy.sql).

| Tabel | Isi |
|---|---|
| `pengguna` | Akun aplikasi (password disimpan sebagai hash bcrypt). |
| `sesi` | Token login (hash), waktu kedaluwarsa, status aktif. |
| `perangkat` | Perangkat ESP32 dan hash API key-nya (header `X-Device-Key`). |
| `produk` | SKU, nama, harga satuan, versi model dan ambang batas PatchCore. |
| `batch` | Kode batch, SKU, status batch (BERJALAN/DITUTUP), status inspeksi (PASSED/HOLD), waktu mulai/selesai. |
| `output_produksi` | Jumlah kaleng yang terhitung sensor per kiriman perangkat. |
| `inspeksi` | Hasil tiap kaleng: OK/NG, skor anomali, skor mentah, ambang dan versi model yang dipakai, lokasi foto, latensi. |
| `kejadian_produksi` | REJECT (AI), RATE_DROP (sensor), kejadian manual operator (jenis bebas, huruf besar). |

---

## Pengujian

Tes server menghapus dan membuat ulang schema `public`, jadi selalu memakai database terpisah
`simonpro_test` (dibuat otomatis oleh `docker compose` pada volume baru; tes menolak nama database
yang tidak berakhiran `_test`).

```bash
uv sync --group server --group ml-cpu --group dev
uv run pytest                                   # server/tests + tests (aplikasi desktop)
uv run ruff check src server ml tools
```

Volume database lama: buat sekali `docker compose exec postgres psql -U postgres -c "CREATE DATABASE simonpro_test;"`.

CI (GitHub Actions, `.github/workflows/ci.yml`) menjalankan lint dan tes pada setiap push dan pull request.

---

## Dokumen lain

- [`server/README.md`](server/README.md): server, model PatchCore, CPU/GPU, alur dataset dan pelatihan.
- [`firmware/README.md`](firmware/README.md): perakitan, pengaturan perangkat, kamera, sensor, pemecahan masalah.
- [`doc/IMPLEMENTATION_PLAN.md`](doc/IMPLEMENTATION_PLAN.md): rencana implementasi dan keputusan desain.
- [`doc/model_eval/`](doc/model_eval/): laporan evaluasi tiap versi model.
