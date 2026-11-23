# SiMonPro firmware (ESP32-S3 N16R8 + OV5640)

PlatformIO + Arduino-ESP32. No Arduino IDE needed.

```bash
cd firmware
cp include/device_config.example.h include/device_config.h   # optional: Wi-Fi, server IP, pins
uvx platformio run -t upload      # if upload fails: hold BOOT, tap RESET, release BOOT, retry
uvx platformio device monitor     # type `help`
```

The serial port needs the `dialout` group on Linux (`sudo usermod -aG dialout $USER`, log in again).

## Wiring

| Part | Pin | Notes |
|---|---|---|
| Camera OV5640 | ribbon | pin map in `include/camera_pins.h` (ESP32-S3-EYE / Freenove layout) |
| IR obstacle sensor OUT | GPIO 14 | active LOW, VCC 3.3 V, GND |
| Red reject LED | GPIO 21 | + 220 Ω to GND |
| Onboard RGB (WS2812) | GPIO 48 | status, mirrors the reject LED |

RGB status: blue blink = connecting to Wi-Fi, purple blink = setup access point, amber = dataset
capture mode, green flash = OK, red 2 s = reject (NG), red 5 Hz blink = error (FR-15).

## First setup

1. Flash. With no Wi-Fi set, the board opens the access point **SiMonPro-Setup**: join it and open
   `http://192.168.4.1/`. Or over serial: `set ssid ...`, `set pass ...`, `wifi`.
2. `set server http://<endeavour LAN IP>:8000/api/v1` (Tailscale names don't resolve on the ESP).
3. The page `http://<esp-ip>/` (or `http://simonpro.local/`) shows a live photo for aligning the
   camera and lighting. Tune `aec`/`agc` there, then **keep them fixed** for capture and inspection.
4. The clock syncs over NTP (needs internet); inspections are refused until it has synced.

## Inspection (MODE inspect)

Create and open the batch in the app, then `batch B-2311-01`. Each can: IR → settle (200 ms) → photo
→ `POST /inspections` → LED. Every 10 cans or 30 s the count goes to `/production/outputs`
(kept in NVS if the server is down). Before changing batch, pending outputs are flushed.
Serial log prints the K4 timings for each can (trigger → LED).

## Dataset capture (MODE capture)

Server needs `ENABLE_DEV_CAPTURE=1`. Then:

```
mode capture
set sku SRD-TOMAT-155G
label ok
can c001        # physical can id; each photo of this can keeps the same id (AI-07)
snap            # or put the can in front of the sensor; rotate it and repeat
next            # next physical can -> c002
label ng
```

Photos land in `$DATASET_DIR/raw/<sku>/<label>/<canId>_<time>.jpg`. Switch back with `mode inspect`.
