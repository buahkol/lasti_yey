# SiMonPro REST API server

FastAPI service that receives data from the ESP32-S3, runs PatchCore, and serves the desktop app.
The contract follows D2 §3.C (base URL `/api/v1`). Interactive docs: `http://<server>:8000/docs`.

## Run (edge server, `pn@endeavour`)

```bash
docker compose up -d                       # PostgreSQL 15 on :5433 (init.sql + dummy.sql on first start)
uv sync --group server --group ml          # see "Offline install" if downloads fail
cp .env.example .env                       # adjust paths if needed
uv run uvicorn server.app.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/api/v1/health   # lists loaded models and the device (cuda/cpu)
```

Without a model yet, run with `MODEL_BACKEND=stub` (score = image brightness; a bright image is NG).
Use this to try the firmware and the desktop app before PatchCore is trained.

Seed credentials (`database/dummy.sql`): user `operasional` / `operasional123`,
device key `simonpro-dev-key-01` (header `X-Device-Key`). Change both before the demo.

## Model workflow (offline scripts in `ml/`, AI-06)

```bash
# 1. Collect photos through the device (server with ENABLE_DEV_CAPTURE=1, firmware in capture mode)
#    -> $DATASET_DIR/raw/<sku>/{ok,ng}/<canId>_<time>.jpg
# 2. Split by physical can (AI-07)
uv run python -m ml.split_dataset raw --raw $DATASET_DIR/raw/SRD-TOMAT-155G --out $DATASET_DIR/manifests/SRD-TOMAT-155G.csv
# 3. Memory bank -> models/<sku>/vN.pt
uv run python -m ml.build_memory_bank --manifest $DATASET_DIR/manifests/SRD-TOMAT-155G.csv --sku SRD-TOMAT-155G
# 4. Normalisation + threshold on the val split (recall >= 90%)
uv run python -m ml.calibrate_threshold --manifest $DATASET_DIR/manifests/SRD-TOMAT-155G.csv --sku SRD-TOMAT-155G
# 5. K2/K3/AI-04 report on the held-out test split -> doc/model_eval/<sku>_vN/
uv run python -m ml.evaluate --manifest $DATASET_DIR/manifests/SRD-TOMAT-155G.csv --sku SRD-TOMAT-155G
# 6. Restart the server; it loads the newest calibrated version per SKU.
```

Pipeline dry run on GoodsAD `drink_can` (product `DEMO-CAN` in the seed):
`python -m ml.split_dataset goodsad --root ~/lasti/data/goodsad --category drink_can --out .../DEMO-CAN.csv`, then steps 3–5.

## Simulated device

```bash
uv run python tools/fake_device.py --server http://endeavour:8000 --batch B-2311-01 \
    --manifest $DATASET_DIR/manifests/DEMO-CAN.csv --split test --limit 40 --shuffle
```

## Tests

The API tests use the stub model and a real Postgres. **They drop and recreate the `public`
schema of `DB_NAME`**, so point them at a test database:

```bash
DB_HOST=localhost DB_PORT=5433 DB_NAME=simonpro_test uv run pytest server/tests
```

## Offline install (flaky network / DNS)

On endeavour, Nix-built `uv` resolves DNS directly against Tailscale MagicDNS (100.100.100.100),
which keeps timing out, while system tools (curl, via systemd-resolved) work. Workaround:

```bash
export VENV=/mnt/storage/simonpro/venv WHEELS=/mnt/storage/simonpro/wheels
uv export --frozen --no-hashes --no-emit-project --group server --group ml --group dev > /tmp/req.txt
/usr/bin/python3 tools/fetch_wheels.py --req /tmp/req.txt --out $WHEELS --python-tag cp311
uv venv --python 3.11 $VENV
uv pip install --python $VENV/bin/python --no-index --find-links $WHEELS -r /tmp/req.txt
$VENV/bin/python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

Permanent fix (needs sudo): point `/etc/resolv.conf` at the systemd-resolved stub
(`127.0.0.53`) or run `tailscale set --accept-dns=false`.
