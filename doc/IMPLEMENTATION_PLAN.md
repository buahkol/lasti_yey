# SiMonPro — Implementation Plan (Deliverable 3)

Source: `PRD-SiMonPro.docx` v1.0 (23 Nov 2026). Deadline for code and tests: **27 Nov 2026, 23.59 WIB**. Demo: 2 and 4 Dec.

---

## 0. Where we are starting from

### 0.1 This repo is a different product
The code in `src/` is the older **IF2050 textile production monitor**: Owner/Admin roles, target produksi, pencapaian, kategori, defect types, and direct PostgreSQL access from PyQt6. The PRD describes a **new domain**: sardine-can packaging inspection with an ESP32-CAM, PatchCore, and a FastAPI server.

| Keep (reuse) | Replace / delete |
|---|---|
| PyQt6 MVC skeleton, `main.py`, login window, sidebar shell (`main_window.py`), styling, Inter fonts, logos | All domain tables (`kategori_produk`, `target_produksi`, `produksi_harian`, `tipe_defect`, `detail_defect`) |
| `docker-compose.yml` (Postgres 15 on :5433) | Target, Pencapaian, Kategori, Defect, Owner views, services, and controllers |
| `db_connection.py` (psycopg2 singleton), reused **server-side** | RBAC (owner/admin). The PRD has one role: Operasional |
| PDF export (fpdf2/reportlab + `templates/`), matplotlib charts | Direct DB access from the desktop app. The app goes through the REST API |
| uv, ruff, pytest, GitHub CI | Old tests (`tests/test_*` for removed services) |

**D2 and the PRD disagree on base features.** D2 §3.D 1.1 still lists the forked app's "fitur dasar": kategori, target produksi, and pencatatan produksi harian with defect types. The PRD (v1.0, written for D3) drops them, leaving product = SKU, nama, harga_satuan. **This plan follows the PRD**, since it's the newer document and it's what D3 is tested against. If the group wants to keep kategori, it costs one FK column. Target and produksi harian would need a redesign around batches, which isn't worth it before 27 Nov.

**Defect already present:** `AuthService._verify_password` compares plaintext (`input == stored`) and `users.password` stores plaintext, which violates **FR-02**. The fix goes into the new schema with bcrypt.

### 0.2 Hardware and machines (confirmed 23 Nov)

| Machine | Role | Facts |
|---|---|---|
| **ESP32-S3 camera board** on this laptop (`/dev/ttyACM0`, USB `303a:4001`, native USB CDC) | IoT device | It's an **S3, not the AI-Thinker ESP32-CAM** named in the PRD and D2. Update PRD Table 1 and D2 §1.3 wording to "ESP32-S3 N16R8 + kamera OV5640". Pins differ, see §5. The port needs `dialout`: `sudo usermod -aG dialout pn`, then log in again |
| **`pn@endeavour`** | Edge server: FastAPI, PatchCore, PostgreSQL | RTX 4060 Laptop **8 GB**, NVIDIA driver 615.78, Python 3.11, uv, Docker, 19 GB RAM. **PyTorch not installed yet** (installed into the project venv by `uv sync --group server`). `/mnt/storage` is **93% full (27 GB free)**, so **the home disk `/` is also 96% full (3.8 GB free)**, so the venv, dataset, models and inspection images live under `/mnt/storage/simonpro/` (see `.env.example`) |
| This laptop (MX150, no CUDA) | Development + desktop app | Runs the PyQt6 app against endeavour over the LAN (NF-09). Server tests use the stub model on CPU |

**Already on endeavour:** `~/lasti` holds the earlier **zero-shot VLM benchmark** (Qwen3-VL, LFM3-VL via llama.cpp), which D2 §3.D 1.2 cites as the reason for choosing PatchCore. It has **GoodsAD** (`~/lasti/data/goodsad`), including `drink_can` with 235 train/good images plus deformation and surface_damage test images. Use it to **build and debug the PatchCore pipeline today**, before our own photos exist (§3.0). GoodsAD numbers are **not** K2/K3 evidence, since those must come from our own photo box.

---

## 1. Target architecture

```
┌──────────────┐  multipart POST /api/v1/inspections   ┌──────────────────────────────────┐
│ ESP32-S3 cam │ ───────────────────────────────────▶  │ FastAPI edge server (uvicorn)    │
│ IR sensor    │  JSON POST /api/v1/production/outputs │  ├─ PatchCore (loaded once, GPU) │
│ reject LED   │ ◀─── {result, anomalyScore, reject}   │  ├─ psycopg2 → PostgreSQL 15     │
└──────────────┘     header: X-Device-Key              │  └─ /mnt/storage/simonpro/images │
                                                        └──────────────▲───────────────────┘
                                         Bearer token (POST /auth/login) │ JSON / JPEG
                                                        ┌────────────────┴─────────────────┐
                                                        │ PyQt6 desktop app (MVC)          │
                                                        │  ApiClient + 5 s QTimer polling  │
                                                        └──────────────────────────────────┘
```

**Decision (resolves PRD §18 Q3):** the desktop app talks **only** to the REST API. Add these endpoints and record them as "penyesuaian rancangan" in the D3 report:
`POST /auth/login`, `POST /auth/logout`, `GET/POST/PUT /products`, `GET/POST /batches`, `POST /batches/{code}/close`, `GET /production/events`, `GET /shipments`, and the dev-only `POST /dev/capture` (dataset collection, §3.1).
**Deployment:** `docker compose up -d` (Postgres) and `uv run uvicorn server.app.main:app --host 0.0.0.0 --port 8000` both run on **endeavour**. The desktop app (`API_BASE_URL=http://endeavour:8000/api/v1`) and the ESP (`server_url` = endeavour's LAN IP, since the ESP can't resolve hostnames without mDNS) both point there. For the demo, put all three devices on one dedicated hotspot (PRD risk table), and fix endeavour's IP with a DHCP reservation or static IP.

This satisfies NF-04 (session token) and NF-05 (one database), and keeps the app runnable from another PC on the LAN (NF-09).

### 1.1 Repository layout

```
server/                     # NEW — FastAPI service
  app/main.py               # app factory, lifespan loads PatchCore once (AI-03)
  app/config.py             # env: DB_*, DEVICE_KEYS, MODEL_DIR, IMAGE_DIR, NG_TOLERANCE=0.05
  app/deps.py               # get_db, require_device_key, require_user_token
  app/routers/              # auth, products, batches, production, inspections, shipments, dev
  app/services/             # business rules (batch status, loss, availability)
  app/ml/patchcore.py       # inference-side PatchCore (feature extractor + kNN)
  app/schemas.py            # pydantic models matching the D2 examples
  tests/                    # pytest + TestClient against a test DB
ml/                         # NEW — offline tooling (AI-06), not imported by the server
  build_memory_bank.py      # train/<sku>/*.jpg → models/<sku>/v<N>.pt
  calibrate_threshold.py    # val/<sku>/{ok,ng} → threshold to models/<sku>/v<N>.json
  evaluate.py               # test set → recall, specificity, latency, confusion matrix (K2, K3, AI-04)
  split_dataset.py          # deterministic train/val/test split (AI-07)
firmware/                   # NEW — PlatformIO (Arduino-ESP32)
  platformio.ini, src/main.cpp, src/config.h, src/camera_pins.h
tools/fake_device.py        # NEW — simulates the ESP from a folder of JPEGs (tests, K6, demo backup)
src/                        # desktop app (refactored)
database/init.sql           # REPLACED with the PRD §11.2 schema
database/seed.sql           # 1 user, 1 device, 2–3 products
models/  storage/  dataset/ # gitignored
```

---

## 2. Database (`database/init.sql`, replaces the old schema)

```sql
CREATE TYPE status_batch    AS ENUM ('BERJALAN','DITUTUP');
CREATE TYPE status_inspeksi AS ENUM ('PASSED','HOLD');
CREATE TYPE hasil_inspeksi  AS ENUM ('OK','NG');
CREATE TYPE jenis_kejadian  AS ENUM ('REJECT','BAHAN_BAKU_HABIS','ALAT_BERHENTI','RATE_DROP');
CREATE TYPE sumber_kejadian AS ENUM ('AI','OPERATOR','SENSOR');

CREATE TABLE pengguna (id SERIAL PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, nama VARCHAR(150), dibuat_pada TIMESTAMPTZ DEFAULT now());
CREATE TABLE sesi (token CHAR(64) PRIMARY KEY, id_pengguna INT REFERENCES pengguna, dibuat_pada TIMESTAMPTZ DEFAULT now(),
  kedaluwarsa TIMESTAMPTZ NOT NULL, aktif BOOLEAN DEFAULT true);
CREATE TABLE perangkat (id SERIAL PRIMARY KEY, nama VARCHAR(100), api_key_hash TEXT NOT NULL, aktif BOOLEAN DEFAULT true);
CREATE TABLE produk (sku VARCHAR(30) PRIMARY KEY, nama VARCHAR(150) NOT NULL, harga_satuan NUMERIC(12,2) NOT NULL,
  versi_model VARCHAR(30), ambang_batas DOUBLE PRECISION);
CREATE TABLE batch (kode_batch VARCHAR(40) PRIMARY KEY, sku VARCHAR(30) REFERENCES produk NOT NULL,
  status_batch status_batch DEFAULT 'BERJALAN', status_inspeksi status_inspeksi DEFAULT 'HOLD',
  mulai TIMESTAMPTZ DEFAULT now(), selesai TIMESTAMPTZ);
CREATE TABLE output_produksi (id SERIAL PRIMARY KEY, kode_batch VARCHAR(40) REFERENCES batch, jumlah INT CHECK (jumlah>0),
  waktu TIMESTAMPTZ NOT NULL);
CREATE TABLE inspeksi (id BIGSERIAL PRIMARY KEY, kode_batch VARCHAR(40) REFERENCES batch, hasil hasil_inspeksi NOT NULL,
  skor_anomali DOUBLE PRECISION NOT NULL, ambang_batas DOUBLE PRECISION NOT NULL, versi_model VARCHAR(30) NOT NULL,
  lokasi_citra TEXT NOT NULL, waktu TIMESTAMPTZ NOT NULL, latensi_ms INT);   -- latensi_ms supports K4/AI-04 evidence
CREATE TABLE kejadian_produksi (id SERIAL PRIMARY KEY, kode_batch VARCHAR(40) REFERENCES batch, jenis jenis_kejadian,
  sumber sumber_kejadian, keterangan TEXT, waktu TIMESTAMPTZ DEFAULT now(), id_inspeksi BIGINT REFERENCES inspeksi);
CREATE TABLE pengiriman (id SERIAL PRIMARY KEY, nomor_pesanan VARCHAR(50) NOT NULL, jumlah INT NOT NULL, dibuat_pada TIMESTAMPTZ DEFAULT now());
CREATE TABLE pengiriman_batch (id_pengiriman INT REFERENCES pengiriman, kode_batch VARCHAR(40) REFERENCES batch,
  PRIMARY KEY (id_pengiriman, kode_batch));
CREATE INDEX ON inspeksi (kode_batch, waktu);  CREATE INDEX ON inspeksi (hasil, waktu);
```
Passwords and device keys are hashed with **bcrypt** (`passlib[bcrypt]`) for FR-02 and NF-04.

---

## 3. AI model: PatchCore (critical path, starts first)

### 3.0 Dry run on GoodsAD `drink_can` (today, on endeavour)
Build the whole `ml/` pipeline against GoodsAD first: train on `train/good`, then split `test/` into val and test. That shakes out bugs in feature extraction, coreset, normalisation, thresholding and latency while the photo box is still being built. Exit criteria: AUROC is reasonable, inference is ≤ 500 ms on the 4060, and the `.pt`/`.json` artifacts load in the server. Then rerun the identical scripts on our own photos.

### 3.1 Data collection: use the device camera itself
Training photos **must** come from the same camera, box, lighting, and locked exposure used at inspection (AI-01, DV-04, risk table). Build this pipeline first:

1. Firmware "capture mode": the IR trigger → JPEG → `POST /api/v1/dev/capture?sku=...&label=ok|ng`.
2. The server saves the file to `dataset/raw/<sku>/<label>/<timestamp>.jpg` without running inference.
3. Target per product (2–3 SKUs):

| Split | Normal (OK) | Defect (NG) | Used for |
|---|---|---|---|
| train | 60–100 | 0 | memory bank only |
| val | 20 | 15–25 | threshold (AI-02) |
| test | 25–50 | 25–50 | **K2, K3 only**, never seen before (AI-07) |

Make defects by hand (dents, scratches, rust spots with paint, torn labels), and photograph each defect at several rotations. `split_dataset.py` uses a fixed seed and **splits by physical can**, so the same can never appears in two splits. Encode the can ID in the filename.

### 3.2 Model (own minimal implementation, no anomalib)
A small PatchCore keeps dependencies light and gives full control over the file format (AI-05, AI-06).
- Backbone: `torchvision wide_resnet50_2` (ImageNet), eval mode, features from `layer2` + `layer3`. Upsample layer3 to layer2 resolution, apply 3×3 average-pool for local neighbourhood aggregation, and concatenate (≈1536-d). Optionally project down with a random projection.
- Preprocessing: center-crop the region of interest of the can (fixed box coordinates from the photo box), resize to **224×224**, ImageNet normalisation. The crop has to be identical in training and serving, so it lives in one shared function in `app/ml/patchcore.py`. `ml/` imports it.
- Memory bank: patch features from all train images → **greedy coreset subsampling to 1–10%** → stored as a `float16` tensor.
- Score: for each test patch, find the nearest-neighbour distance to the bank (`torch.cdist`, chunked). Image score = max patch score. Optionally keep the patch-score map for a heatmap thumbnail (nice to have).
- CPU inference is officially supported (D2 §3.D 1.2: at least 8 GB RAM, 2 cores / 4 threads, for example an i3-6100), so the server must run without CUDA. Use a `resnet18` backbone if wide_resnet50 on CPU breaks the 3 s end-to-end budget (K4). AI-04 (≤ 500 ms) is measured on the GPU box.

**Artifact per product:** `models/<sku>/v<N>.pt` (bank + backbone name + crop box + image size) plus `models/<sku>/v<N>.json`:
```json
{"sku":"SRD-TOMAT-155G","version":"v1","threshold":0.62,"raw_min":1.91,"raw_max":5.37,"backbone":"wide_resnet50_2","coreset_ratio":0.05,
 "val_recall":0.95,"val_specificity":0.90,"created_at":"2026-11-24T10:00:00+07:00"}
```
On startup the server reads the latest version per SKU and writes `versi_model` and `ambang_batas` into `produk`. Each inspection row stores the version and threshold it used (AI-05, NF-06).

### 3.3 Score normalisation and threshold (AI-02)
D2 shows scores in the 0–1 range (`anomalyScore 0.87`, `threshold 0.62`), but raw PatchCore scores are unbounded nearest-neighbour distances. Normalise per product with **min-max over the val split's raw scores**: `score = clip((raw − raw_min) / (raw_max − raw_min), 0, 1)`. Store `raw_min` and `raw_max` in the model JSON. Thresholds and API responses use the normalised value; the raw score can go in an extra DB column for debugging.

On the val split, sweep thresholds over the sorted scores and pick the **highest threshold with recall ≥ 0.90**, which maximises specificity. Report the ROC/AUROC as well. Write the result into the JSON file.

### 3.4 Evaluation (K2, K3, AI-04)
`ml/evaluate.py` runs on the held-out test split and outputs a confusion matrix, recall, specificity, AUROC, and per-image latency (p50/p95, warm, on the GPU server). Save the CSV, PNG, and markdown summary in `doc/` as D3 evidence.

### 3.5 Serving
- FastAPI `lifespan`: load the backbone once onto `cuda` if available, otherwise `cpu`. Load every SKU's bank and run one warm-up inference (AI-03).
- Inference runs in a threadpool (`run_in_threadpool`) behind an `asyncio.Lock` (one GPU, sequential requests), so the event loop never blocks.
- Install on endeavour with `uv sync --group server`, using the CUDA 12.x PyTorch wheel index via `[tool.uv.sources]` (driver 615 supports it). Dependencies to add (server group): `fastapi`, `uvicorn[standard]`, `python-multipart`, `torch`, `torchvision`, `pillow`, `numpy`, `passlib[bcrypt]`, `pydantic-settings`. Desktop group: `httpx`.

---

## 4. REST API (`/api/v1`), from D2 §3.C (Tabel 3.2–3.12)

Field names, response shapes and status codes below are **copied from D2**, because K5 is scored against them. Put them into `server/app/schemas.py` as pydantic models, using camelCase aliases for JSON and snake_case in Python. Every row adds **401** for a missing or invalid credential, which FR-09 and NF-04 require even though D2 doesn't list it. Desktop requests send `Authorization: Bearer <token>`; device requests send `X-Device-Key`.

| # | Endpoint | Auth | Request | Response (D2 example) | Codes | Server logic |
|---|---|---|---|---|---|---|
| 1 | `POST /production/outputs` | device | `{"batchCode","quantity","timestamp"}` | `201 {"status":"recorded","batchCode":"B-1113-01","totalOutput":1250}` | 201, 400 | insert into `output_produksi`; `totalOutput` = running sum for the batch. 400 for an unknown or closed batch, or quantity ≤ 0 |
| 2 | `POST /production/events` | user (the server also writes REJECT internally) | `{"batchCode","eventType","source","timestamp","note"?}`; eventType ∈ RATE_DROP/REJECT/BAHAN_BAKU_HABIS/ALAT_BERHENTI, source ∈ SENSOR/AI/OPERATOR | `201 {"status":"recorded","eventId":42}` | 201, 400 | insert into `kejadian_produksi` |
| 3 | `GET /products/{sku}/availability?date=` | user | date defaults to today | `{"sku","date","availableQty":1228,"updatedAt"}` | 200, 404 | `availableQty` = count of OK inspections for that SKU's batches on that date; `updatedAt` = latest inspection time. Shipped cans **not** subtracted (PRD §18 Q2) |
| 4 | `GET /production/reports?batchCode=&date=` | user | both optional; date defaults to today | `{"date","batches":[{"batchCode","totalOutput","ok","ng","events"}]}` | 200 | `totalOutput` = sum of outputs; ok/ng from `inspeksi`; events = count of `kejadian_produksi` |
| 5 | `POST /inspections` | device | multipart: `image` (JPEG), `batchCode`, `timestamp` | `201 {"inspectionId":1250,"result":"NG","anomalyScore":0.87,"threshold":0.62,"reject":true}` | 201, 400 | check the JPEG with PIL (FR-13) → PatchCore for the batch's SKU → save the image → insert into `inspeksi` → if NG, insert a REJECT/AI event **in the same transaction** (FR-16) |
| 6 | `GET /inspections/alerts?since=` | user | since is optional | **bare array** `[{"inspectionId","batchCode","anomalyScore","imageUrl","timestamp"}]` | 200 | NG rows after `since`, newest first, limit 50 |
| 7 | `GET /inspections/reports/{batchCode}` | user | — | `{"batchCode","total","ok","ng","ngPerHour":{"08":3,"09":11},"estimatedLoss":132000}` | 200, 404 | `ngPerHour` keys are zero-padded hours in local WIB time (`to_char(waktu AT TIME ZONE 'Asia/Jakarta','HH24')`); `estimatedLoss = ng × harga_satuan` (FR-24). The app computes %NG as ng/total, or the server adds an `ngPercent` field (additive, doesn't break D2) |
| 8 | `GET /batches/inspection-status?sku=&status=` | user | **status defaults to `PASSED`** | `{"batches":[{"batchCode","sku","status","okQty"}]}` | 200 | the Batch page must pass `status=HOLD`, or call twice, to show everything |
| 9 | `POST /shipments` | user | `{"orderId","batchCodes":[...],"quantity"}` | `201 {"shipmentId":31,"orderId","batchCodes","status":"recorded"}` | 201, 400, 409 | any batch HOLD → **409** `{"detail":"...","holdBatches":[...]}` (FR-29); unknown batch → 400. `orderId` is stored in `pengiriman.nomor_pesanan` |
| 10 | `GET /batches/{batchCode}/inspections?result=` | user | result OK/NG, optional | `{"batchCode","total","ng","inspections":[{"inspectionId","result","anomalyScore","timestamp"}]}` | 200, 404 | 404 if the batch has no inspection data (FR-30) |
| 11 | `GET /inspections/{inspectionId}/photo` | user | (extra, optional: `?size=thumb`) | JPEG, `Content-Type: image/jpeg` | 200, 404 | `FileResponse`; the thumbnail is made on first request and cached |

**Mismatch in D2:** the alert example uses `imageUrl: "/api/v1/inspections/1250/image"`, but endpoint 11 is `/photo`. Resolution: return `imageUrl` pointing at **`/photo`**, register `/image` as an alias of the same handler, and note it as a correction in the D3 report.

**Endpoints added beyond D2** (record them as "penyesuaian rancangan" in the D3 report, per PRD §11.3): `POST /auth/login` → `{"token","expiresAt","user"}`, `POST /auth/logout`, `GET/POST/PUT /products`, `GET/POST /batches`, `POST /batches/{batchCode}/close`, `GET /production/events?batchCode=`, `GET /shipments`, and the dev-only `POST /dev/capture` (enabled only when `ENABLE_DEV_CAPTURE=1`).

**Batch status rule (FR-26, §18 Q1 → tolerance 5%, configurable via `NG_TOLERANCE`):**
`HOLD` while `BERJALAN`. On close: `PASSED` if `NG/total_inspected ≤ 0.05`, otherwise `HOLD`. A closed batch rejects outputs and inspections with 400 (FR-06).

**Cross-cutting:** a global exception handler logs the error and returns JSON, and never crashes the worker (NF-03). Structured logging with request timing. GET endpoints should take under 1 s (NF-02), which the indexes above cover. Device key check: compare the bcrypt hash against the `X-Device-Key` header, with keys cached in memory at startup.

---

## 5. Firmware (`firmware/`, PlatformIO + Arduino-ESP32)

**Board: ESP32-S3 N16R8 (16 MB flash, 8 MB octal PSRAM) with an OV5640 on the ribbon connector**, confirmed 23 Nov; camera pins use the ESP32-S3-EYE/Freenove layout. **Implemented** in `firmware/` (builds; see `firmware/README.md`). Deviations from the table below: the IR sensor is a polled state machine (no ISR), there is a settle delay (default 200 ms) before the photo, and the board opens a setup access point when no Wi-Fi is configured. Original notes: (native USB). PlatformIO env: `board = esp32-s3-devkitc-1`, `build_flags = -DARDUINO_USB_CDC_ON_BOOT=1 -DBOARD_HAS_PSRAM`, and `board_build.arduino.memory_type = qio_opi` for N8R8/N16R8 modules (check the module marking). Flashing works over the same USB port. If upload fails, hold **BOOT** and tap **RESET**. `camera_pins.h` must match the **exact S3 board model** (Freenove ESP32-S3-WROOM CAM, ESP32-S3-EYE, XIAO S3 Sense and generic "ESP32-S3-CAM" boards all differ). Copy it from the vendor's `CameraWebServer` example. **Action:** read the board's silkscreen or model name, run `uvx esptool --port /dev/ttyACM0 flash_id` (flash/PSRAM size), and add the model to this section.

| Concern | Implementation |
|---|---|
| Wi-Fi (DV-01) | `WiFi.setAutoReconnect(true)` plus a watchdog loop that reconnects after more than 10 s offline; slow LED blink while connecting |
| Config (DV-02) | `Preferences` (NVS) holds `ssid, pass, server_url, device_key, batch_code`. Change it through a tiny on-device web page `http://<esp-ip>/config` **and** serial commands (`set batch B-2411-01`). Defaults come from `config.h`, which is gitignored and has a `config.example.h` |
| IR sensor (DV-03) | ESP32-S3: use a GPIO that the camera, PSRAM and USB **don't** use. Avoid strapping pins **0, 3, 45, 46**, USB **19/20**, and octal-PSRAM **35–37**. Typical free choices are **GPIO 14, 21, 47** or **1/2**; check them against the board's camera pin map. Interrupt on falling edge sets a flag; the main loop confirms the level is still low after 30 ms and applies a **≥ 500 ms lockout** plus "wait for release" → exactly one count per can (FR-07) |
| Camera (DV-04) | `FRAMESIZE_VGA`, `jpeg_quality 12`, `fb_count 1`, `CAMERA_GRAB_LATEST`. **Lock exposure and white balance** (`set_exposure_ctrl(0)`, `set_aec_value(...)`, `set_gain_ctrl(0)`, `set_agc_gain(...)`, `set_whitebal(0)`), with the same values for capture mode and inspection. Discard one stale frame before each capture |
| Reject LED (DV-05) | External red LED (+ 220 Ω) on another free GPIO (for example **GPIO 21 or 47**), or the board's onboard LED (often GPIO 2, or a WS2812 on GPIO 48: drive it with `neopixelWrite`). **Never the camera flash/illumination LED**, because it disturbs the photo lighting. `reject=true` → LED on for 2 s (FR-14). Error → fast blink 5 Hz for 2 s (FR-15) |
| HTTP (DV-06, DV-07) | `HTTPClient`, `X-Device-Key` header, `setTimeout(5000)`. Multipart POST to `/inspections`. On failure, retry once, then show the error blink. Parse the response with ArduinoJson |
| Output counting (FR-08) | `pending += 1` per can. Flush `{"batchCode","quantity","timestamp"}` to `/production/outputs` when `pending ≥ 10` or 30 s have passed. On failure, keep `pending` (also mirrored to NVS) and resend on the next attempt. Serial command `flush` / web button "Tutup batch" sends the remainder before closing |
| Timing (K4) | Log `t_trigger`, `t_captured`, `t_response`, `t_led` over serial; the server logs inference ms. Expected budget: about 150 ms capture + 300–800 ms upload + ≤ 500 ms inference, well under 3 s |
| Modes | `MODE_INSPECT` (default) and `MODE_CAPTURE` (posts to `/dev/capture` for dataset collection), switched through config |

Libraries: `esp32-camera` (bundled), `ArduinoJson@7`. Build and flash: `pio run -t upload && pio device monitor`.

---

## 6. Desktop app refactor (`src/`)

- **`src/api/client.py`**: an `ApiClient` (httpx) with base URL from env `API_BASE_URL`, bearer token, and Indonesian error mapping (401 → "Sesi berakhir, silakan login ulang", 409 → list of HOLD batches, network error → "Server tidak dapat dihubungi").
- **Polling**: one `QTimer(5000)` on the Dashboard and Alert pages runs requests in a `QThreadPool` worker, so the UI never freezes. Alerts use `since=<last seen timestamp>` (FR-20, FR-22).
- **Services** become thin wrappers over `ApiClient`. Controllers and views keep the existing MVC pattern.
- **Pages (PRD §12)**: replace the sidebar items with:

| Page | Built from | FR |
|---|---|---|
| Login | existing `loginpage.py`, now calls `/auth/login` | FR-01–03 |
| Dashboard | rewrite `dashboardview.py`: active batch cards (output, OK, NG, %NG) plus the latest alerts on the same screen (NF-07) | FR-19, 20, 22 |
| Produk | adapt `produklistview.py` / `TambahProduk` / `EditProduk` → SKU, nama, harga_satuan, plus availability column | FR-04, 18 |
| Batch | new: table with filters (status, SKU), "Buat batch" dialog, "Tutup batch" button | FR-05, 06, 26, 27 |
| Alert | adapt `defectviewer.py`: thumbnail grid, click → full image dialog | FR-22, 23 |
| Laporan | adapt `laporanviewer.py` + `LaporanService` PDF: production recap by date or batch, inspection report with matplotlib NG-per-hour bar chart and loss, export PDF | FR-21, 24, 25 |
| Kejadian | adapt `produksiviewer.py`: form (batch, type, keterangan) plus event list | FR-17 |
| Pengiriman | new: form with multi-select of PASSED batches, list of shipments, shows the 409 response | FR-28, 29 |
| Riwayat & Klaim | new: batch code search, OK/NG filter, table, photo viewer | FR-30, 31 |

- Delete: `targetviewer`, `pencapaianviewer`, `KategoriView`, `OverwriteTarget`, `ownerview`, and their services and controllers. Remove role checks.
- All labels in Bahasa Indonesia (NF-08).

---

## 7. Testing (PRD §14), producing the evidence

| Type | How | Output for the D3 report |
|---|---|---|
| API (K5) | `server/tests/`: pytest + `TestClient`, test DB, a **stub model** (fixed score via dependency override) so tests don't need a GPU. For each of the 11 endpoints: valid case, plus 401/400/404/409 cases | `pytest --cov` report, plus a Postman/Bruno collection for manual screenshots |
| Model (K2, K3, AI-04) | `ml/evaluate.py` on the test split, on the GPU server | confusion matrix PNG, metrics table |
| Device (DV-01–07, FR-14/15) | Manual checklist: 20 cans → count 20; unplug the server → fast blink; Wi-Fi drop → reconnect; serial timing logs | checklist with photos and video |
| End-to-end (K1, K4, K6) | A batch of N normal and M defect cans: create batch → run cans → close batch → shipment → history search. Compare the dashboard counts with the handwritten tally | screen recording, timing table |
| Backup | `tools/fake_device.py --batch B1 --dir dataset/test/SRD-001` replays the real HTTP flow if the device or Wi-Fi fails during the demo | — |
| Functional (FR-01–31) | Scenario table: scenario, steps, expected, actual, status, evidence | spreadsheet / report table |

Update CI: ruff on `server/` and `ml/`, pytest for `server/tests` with a Postgres service container and the stub model.

---

## 8. Schedule (23–27 Nov), with four parallel workstreams

People: **A** = model/data, **B** = server/DB, **C** = firmware, **D** = desktop app.

| Day | A: Model | B: Server | C: Firmware | D: Desktop |
|---|---|---|---|---|
| **Sun 23 (today)** | `ml/` pipeline dry run on GoodsAD `drink_can` on endeavour (§3.0). Build the photo box (fixed can holder, even light). Pick 2–3 SKUs. Make defect cans | New `init.sql` + seed; FastAPI skeleton; `/dev/capture`; device-key auth | Find the exact S3 board model and pin map (§5); camera + locked exposure; IR + debounce; capture mode → `/dev/capture` | Strip old modules; `ApiClient`; login against `/auth/login`; new sidebar |
| **Mon 24** | Collect photos through the device; `split_dataset`; `build_memory_bank`; `calibrate_threshold` (**milestone: v1 models**) | `POST /inspections` with real PatchCore; `POST /production/outputs`; batch CRUD and close logic | Inspect mode: multipart upload, JSON parse, reject LED, error blink, retry | Produk and Batch pages |
| **Tue 25** | `evaluate.py` on the GPU server; retune crop or threshold if K2/K3 miss | GET endpoints 3, 4, 6, 7; auth/login; pytest for P1 | Output batching (10 cans / 30 s, NVS persistence); config web page; timing logs | Dashboard (5 s poll), Alert page, Laporan + PDF (**milestone: P1 end-to-end, K1**) |
| **Wed 26** | Heatmap thumbnail (optional); write the model section of the report | Endpoints 2, 8, 9, 10, 11; 409 rule; all API tests (K5) | Stability run (100+ cans), fix edge cases | Kejadian, Pengiriman, Riwayat & Klaim pages (**milestone: P2 done**) |
| **Thu 27** | — everyone — full test scenarios, K1–K6 measurements, screenshots, video, README (NF-10), report. **Submit before 23.59 WIB** | | | |
| 28 Nov – 1 Dec | Demo rehearsal, record backup video, fix demo-blocking bugs only | | | |

**Critical path:** board ID → camera with locked exposure → dataset capture → memory bank → `POST /inspections` → firmware inspect mode → E2E. Any slip in the photo box or dataset delays everything, so A and C start the capture pipeline today.

If time runs out, cut in this order (PRD risk table): P2 pages, then PDF for the inspection report, then the config web page (fall back to serial config only).

---

## 9. Decisions (resolved 23 Nov)

| # | Question | Decision |
|---|---|---|
| 1 | Board | **ESP32-S3** (exact model still needed for `camera_pins.h`, §5) |
| 2 | D2 `/image` vs `/photo` | `/photo`, with `/image` as an alias; noted in the report |
| 2b | Keep D2's base features (kategori, target, produksi harian)? | **No**, follow the PRD scope |
| 3 | NG tolerance for HOLD | **5%** (`NG_TOLERANCE=0.05`) |
| 4 | Availability minus shipped | **No**, not subtracted |
| 5 | App auth | **`POST /auth/login` → bearer token**, recorded as a design adjustment |
| 6 | GPU server | **`pn@endeavour`** (RTX 4060 8 GB) |
| 7 | Repo strategy | **Adapt this repo's components** to the PRD (§0.1) |

---

## 10. Progress log

### 23 Nov: server, schema and ML pipeline (committed to `main`)
- `database/init.sql` and `dummy.sql` replaced with the PRD §11.2 schema. Passwords and device keys are bcrypt hashes; session tokens are stored as SHA-256.
- `server/`: FastAPI app with **all 11 D2 endpoints** plus auth, products, batches/close, event list, shipment list and `/dev/capture`. Validation errors return 400 as D2 specifies, not FastAPI's default 422.
- `server/tests/`: **27 tests pass**, covering every D2 endpoint's success and error codes, with a stub model.
- `ml/`: PatchCore (`server/app/ml/patchcore.py`) plus scripts for splitting, building the memory bank, calibrating and evaluating. **Trial on GoodsAD drink_can** (`doc/model_eval/DEMO-CAN_v1/`): AUROC 0.92, recall 91.5%, specificity 65.5%, p95 216 ms **on CPU**. GoodsAD photos are uncontrolled, so this validates the pipeline only and is not K2/K3 evidence.
- End-to-end run on endeavour (real model, `tools/fake_device.py`, 30 cans): dashboard counts equal the device tally (K6), one REJECT event per NG (FR-16), HOLD → shipment 409 (FR-29), server round trip about 250 ms per can on CPU.
- `tools/fetch_wheels.py`: offline install. Nix-built uv on endeavour can't resolve DNS through Tailscale MagicDNS (see `server/README.md`).

**GPU rerun (23 Nov, after the GPU was freed)** (`doc/model_eval/DEMO-CAN_v2/`): RTX 4060, memory bank in 23 s (CPU: 371 s), **inference p95 43 ms** (AI-04 met). Recall 90.2%, specificity 75.0%, AUROC 0.93 on GoodsAD. API on CUDA: about 75 ms server-side and about 86 ms round trip per can; the model uses about 750 MB of VRAM. Start and stop the server with `tools/server.sh start|stop|restart|status|log`.

**Endeavour setup done (23 Nov):** DNS fixed (`/etc/resolv.conf` → systemd-resolved stub), so `uv sync` works normally again (the venv is at `/mnt/storage/simonpro/venv` via `.envrc.endeavour`). `pn` is in the `docker` group, and Postgres now runs from `docker compose` on :5433; the temporary user-space instance is stopped. Full suite on endeavour: **29 passed** (`QT_QPA_PLATFORM=offscreen` is needed for the Qt smoke test over SSH). API on CUDA with the simulated device: counts match (K6), about 87 ms round trip per can.
- Keep `llama-server` stopped while the API runs: the model uses about 0.75 GB of the 8 GB.
- `/` has about 4.5 GB free, and the Docker volume `pgdata` lives there. That's fine for the prototype, but watch it if inspection photos grow (they go to `/mnt/storage`).
- CI now runs `server/tests` and lints `server ml tools`. The legacy desktop tests in `tests/` target the old textile schema and are excluded until §6. Ruff on `src/` already reported 71 errors before this change.

**Next:** firmware (§5, needs the exact S3 board model), desktop app migration to the API (§6), and photo-box dataset capture (§3.1).
