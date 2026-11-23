#pragma once
// Default settings, used on first boot (later changes live in NVS, set over serial or
// http://<esp-ip>/). Copy to device_config.h (gitignored) to put real Wi-Fi details in.

#define DEFAULT_WIFI_SSID   ""
#define DEFAULT_WIFI_PASS   ""
// The ESP cannot resolve Tailscale names: use the edge server's LAN IP.
#define DEFAULT_SERVER_URL  "http://192.168.1.10:8000/api/v1"
#define DEFAULT_DEVICE_KEY  "simonpro-dev-key-01"
#define DEFAULT_BATCH_CODE  ""

// Dataset capture mode (POST /dev/capture)
#define DEFAULT_SKU         "SRD-TOMAT-155G"

// Hardware
#define PIN_IR_SENSOR       14   // IR obstacle sensor OUT, active LOW (FC-51 style)
#define PIN_REJECT_LED      21   // external red LED + 220 ohm to GND, active HIGH
#define PIN_RGB_LED         48   // onboard WS2812, mirrors the reject LED; -1 to disable

// Locked exposure (DV-04). Same values for dataset capture and inspection.
#define DEFAULT_AEC_VALUE   300  // 0..1200
#define DEFAULT_AGC_GAIN    2    // 0..30
