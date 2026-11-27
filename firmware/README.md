# SiMonPro firmware (ESP32-S3 N16R8 + OV5640)

PlatformIO + Arduino-ESP32. No Arduino IDE needed.

```bash
cd firmware
cp include/device_config.example.h include/device_config.h   # optional: Wi-Fi, server IP, pins
uvx platformio run -t upload      # if upload fails: hold BOOT, tap RESET, release BOOT, retry
uvx --from pyserial pyserial-miniterm /dev/ttyACM0 115200     # serial console, type `help`; exit Ctrl+]
```

The serial port needs the `dialout` group on Linux (`sudo usermod -aG dialout $USER`, log in again).

## Current prototype (verified 2026-11-27)

| Part | Pin | Status |
|---|---|---|
| ESP32-S3 N16R8 | — | 16 MB flash, 8 MB PSRAM detected; powered over USB |
| Camera OV5640 | ribbon (pin map in `include/camera_pins.h`) | detected (`PID 0x5640`), 640×480 JPEG |
| IR obstacle sensor OUT (two-LED module, FC-51 style) | GPIO 14 | works: HIGH with nothing in front, **LOW while it sees a can** (its LED lights); `irlevel=low`, the firmware default |
| Red reject LED | GPIO 21 → 220 Ω → LED → GND | works (long leg towards the resistor) |
| Onboard RGB (WS2812) | GPIO 48 | status, mirrors the reject LED |

End-to-end test passed: sensor → photo → `POST /inspections` → PatchCore on endeavour's GPU (72 ms) →
NG → LED. Not done yet: exposure tuning (the first photo was overexposed at `aec=300`) and a model for
our own cans (DEMO-CAN is trained on GoodsAD drink cans, so its OK/NG on our photos means nothing).

### Wiring notes

- The sensor gets VCC/GND from the ESP32's 5V and GND pins (5V is only live when powered over USB).
  If the sensor runs on 5 V, its OUT must still be at most 3.3 V; check with a multimeter or power it from 3V3.
- **Sensor polarity:** `set irlevel low|high` = the OUT level while the sensor sees a can (saved, no reflash).
  Our two-LED obstacle module is `low`; the HC-SR501 PIR (dome) is `high`. Wrong polarity looks like this:
  nothing happens when the can is put down, and the photo (of an empty spot) is taken when it is lifted.
  `status` shows the live level, e.g. `sensor GPIO14=1 (clear) irlevel=low`. The firmware pulls GPIO 14
  towards "no can" (pull-up for `low`, pull-down for `high`).
- The screw (blue trimmer) on the sensor sets the **detection distance**. With nothing in front, turn it
  until the module's LED goes off, then a bit further. A can at its real position must light the LED steadily.
  Check with the darkest label, which reflects the least IR.
- The firmware ignores the sensor for `PIN_IR_WARMUP_MS` after boot (default 1 s). The old HC-SR501 PIR
  needed 60 s (`#define PIN_IR_WARMUP_MS 60000` in `device_config.h`).
- `settle` (ms, default 200) is the wait between the sensor seeing a can and the photo, so a can that is
  still moving is not blurred. Leave the can in place until the LED reacts.
- The HC-SR501 PIR is **not suitable**: in testing its output stayed HIGH ~95% of the time (even covered)
  and it reacts to body heat, not cans.

RGB status: blue blink = connecting to Wi-Fi, purple blink = setup access point, amber = dataset
capture mode, green flash = OK, red 2 s = reject (NG), red 5 Hz blink = error (FR-15).

## First setup

1. Flash. With no Wi-Fi set, the board opens the access point **SiMonPro-Setup**: join it and open
   `http://192.168.4.1/`. Or over serial: `set ssid ...`, `set pass ...`, `wifi`.
2. Point it at the server (see the network section below): `set server http://<server LAN IP>:8000/api/v1`.
3. `batch <code>` with a batch that exists in the app (e.g. `B-2311-01`, product DEMO-CAN).
4. Open `http://<esp-ip>/` (or `http://simonpro.local/`) from a device on the same Wi-Fi. The live photo
   at the bottom is for aligning the camera and lighting. Lower **Exposure** (`aec`, try 80 then 40) until
   the label is clearly visible, keep **Gain** (`agc`) at 0–2, then **keep both fixed** for capture and inspection.
5. The clock syncs over NTP, so the Wi-Fi needs internet; inspections are refused until `status` shows a time.

Settings are stored in NVS and survive reboots and reflashing. `status` shows them all.

## Network: where the server must be

The board talks plain HTTP to the server URL, so the server must be reachable **from the board's Wi-Fi**.
The board cannot join Tailscale, and Tailscale names don't resolve on it.

| Setup | Server URL on the board |
|---|---|
| **Recommended:** board on the same Wi-Fi as endeavour | `http://<endeavour LAN IP>:8000/api/v1` (`ip -4 -br addr` on endeavour) |
| Board elsewhere (e.g. phone hotspot), laptop on the same Wi-Fi with Tailscale | relay through the laptop, below |

Laptop relay (works only while the laptop is awake on that Wi-Fi and the command runs):

```bash
# on the laptop: forward its port 8000 to the server on endeavour over Tailscale
ssh -N -L 0.0.0.0:8000:localhost:8000 pn@<endeavour tailscale IP>
curl http://<laptop Wi-Fi IP>:8000/api/v1/health      # must answer from the laptop's Wi-Fi IP
# on the board
set server http://<laptop Wi-Fi IP>:8000/api/v1
```

If the laptop's IP changes (new hotspot session), update `server`. The relay adds about 2 s per can
(upload over the tunnel); same-Wi-Fi should be a few hundred ms. Campus/guest Wi-Fi often blocks
devices from reaching each other (client isolation); use a hotspot or your own router then.

Start the server on endeavour (see `server/README.md`) and check `GET /api/v1/health` lists the model.

## Inspection (MODE inspect)

Create and open the batch in the app, then `batch B-2311-01`. Each can: IR → settle (200 ms) → photo
→ `POST /inspections` → LED. Every 10 cans or 30 s the count goes to `/production/outputs`
(kept in NVS if the server is down). Before changing batch, pending outputs are flushed.
Serial log prints the K4 timings for each can (trigger → LED), e.g.

```
[insp] #21 NG score=1.000 thr=0.198 | jpg 6851B | K4 settle+cap 254ms, upload+infer 2530ms, trigger->LED 2784ms
```

Cans counted while offline are sent when Wi-Fi comes back (`[out] sent N`), into the **current** batch.
Trigger tests before setting the real batch therefore end up in it: `flush` or reboot-test with a test batch.

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
Tune exposure **before** capturing: the model must see the same lighting in training and inspection.

## Troubleshooting the hardware

- `pir` in the serial console toggles a raw log of the sensor pin: every change with a timestamp and how
  long the previous level lasted (also during warm-up). Use it to check the sensor without a server:
  ```
  [pir]    62.55s GPIO14=0 detect  (was 1 for 9.86s)
  [pir]    71.79s GPIO14=1 clear   (was 0 for 9.23s)
  ```
  Expected: `clear` with nothing in front, one `detect` per can, and the `[insp]` line right after `detect`.
- `snap` runs one inspection without the sensor (tests camera + network + server).
- LED does not light: check the LED direction (long leg to the resistor), that the LED and the GND wire
  sit on the same half of the breadboard rail (MB102 rails are split in the middle), and bypass GPIO 21 by
  touching the orange wire to 3V3. LED lights → the GPIO 21 joint/jumper is the problem.
- After opening the serial port the board may reboot; settings are kept, the warm-up restarts.
