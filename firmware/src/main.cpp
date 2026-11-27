// SiMonPro photo-box firmware (ESP32-S3 N16R8 + OV5640).
//
// IR sensor sees a can -> settle -> JPEG -> POST /inspections -> reject LED (FR-06..FR-15).
// Cans are also counted and flushed to /production/outputs every 10 cans or 30 s (FR-08).
// MODE capture posts to /dev/capture instead, for collecting the training dataset (§3.1).
//
// Settings live in NVS. Change them over serial ("help") or the web page http://<ip>/.
// With no Wi-Fi configured the board opens an access point "SiMonPro-Setup" (page at 192.168.4.1).

#include <esp_timer.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <StreamString.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <sys/time.h>
#include <time.h>

#include "camera_pins.h"
#if __has_include("device_config.h")
#include "device_config.h"
#else
#include "device_config.example.h"
#endif

// Default level of the sensor OUT pin while it sees a can. Our IR obstacle module (its LED lights on
// detect) pulls OUT LOW; HC-SR501 PIR modules drive HIGH. Changeable at runtime: `set irlevel low|high`.
#ifndef PIN_IR_ACTIVE_LEVEL
#define PIN_IR_ACTIVE_LEVEL LOW
#endif

// ---------------------------------------------------------------- constants
static const uint32_t CONFIRM_MS = 30;       // sensor must stay active this long (debounce)
static const uint32_t RELEASE_MS = 50;       // ... and inactive this long before the next can
#ifndef PIN_IR_WARMUP_MS
#define PIN_IR_WARMUP_MS 1000                // IR module: 1 s. The HC-SR501 PIR needed 60000
#endif
static const uint32_t LOCKOUT_MS = 500;      // min gap between two cans (FR-07)
static const uint32_t REJECT_LED_MS = 2000;  // FR-14
static const uint32_t ERROR_LED_MS = 2000;   // FR-15, 5 Hz blink
static const uint32_t OK_LED_MS = 300;       // short green flash on the RGB LED
static const uint32_t FLUSH_EVERY_MS = 30000;
static const uint32_t FLUSH_EVERY_N = 10;
static const uint32_t WIFI_RETRY_MS = 10000;  // DV-01
static const uint16_t HTTP_TIMEOUT_MS = 5000; // DV-07
static const char *BOUNDARY = "----SiMonProBoundary7d1f";
static const char *TZ_WIB = "WIB-7";

enum Mode : uint8_t { MODE_INSPECT = 0, MODE_CAPTURE = 1 };

struct Config {
  String ssid, pass, server, key, batch, sku, label, canId;
  uint8_t mode;
  int aec, agc, settleMs;
  int irLevel;  // 0 = sensor OUT is LOW while it sees a can, 1 = HIGH
  int rgbOn;    // onboard RGB status LED; off keeps its light out of the photo
  int autoBatch;  // inspect mode: follow the running batch from the app (GET /devices/current-batch)
} cfg;

Preferences prefs;
WebServer web(80);
bool cameraOk = false;
bool apMode = false;
uint32_t pending = 0;          // cans not yet sent to /production/outputs
uint32_t lastFlushMs = 0;
uint32_t lastWifiTry = 0;
uint32_t okCount = 0, ngCount = 0, errCount = 0;

// ---------------------------------------------------------------- config (DV-02)
void loadConfig() {
  prefs.begin("simonpro", true);
  cfg.ssid = prefs.getString("ssid", DEFAULT_WIFI_SSID);
  cfg.pass = prefs.getString("pass", DEFAULT_WIFI_PASS);
  cfg.server = prefs.getString("server", DEFAULT_SERVER_URL);
  cfg.key = prefs.getString("key", DEFAULT_DEVICE_KEY);
  cfg.batch = prefs.getString("batch", DEFAULT_BATCH_CODE);
  cfg.sku = prefs.getString("sku", DEFAULT_SKU);
  cfg.label = prefs.getString("label", "ok");
  cfg.canId = prefs.getString("can", "c001");
  cfg.mode = prefs.getUChar("mode", MODE_INSPECT);
  cfg.aec = prefs.getInt("aec", DEFAULT_AEC_VALUE);
  cfg.agc = prefs.getInt("agc", DEFAULT_AGC_GAIN);
  cfg.settleMs = prefs.getInt("settle", 200);
  cfg.irLevel = prefs.getInt("irlevel", PIN_IR_ACTIVE_LEVEL == HIGH ? 1 : 0);
  cfg.rgbOn = prefs.getInt("rgb", 1);
  cfg.autoBatch = prefs.getInt("autobatch", 1);
  pending = prefs.getUInt("pending", 0);
  prefs.end();
  while (cfg.server.endsWith("/")) cfg.server.remove(cfg.server.length() - 1);
}

void saveConfig() {
  prefs.begin("simonpro", false);
  prefs.putString("ssid", cfg.ssid);
  prefs.putString("pass", cfg.pass);
  prefs.putString("server", cfg.server);
  prefs.putString("key", cfg.key);
  prefs.putString("batch", cfg.batch);
  prefs.putString("sku", cfg.sku);
  prefs.putString("label", cfg.label);
  prefs.putString("can", cfg.canId);
  prefs.putUChar("mode", cfg.mode);
  prefs.putInt("aec", cfg.aec);
  prefs.putInt("agc", cfg.agc);
  prefs.putInt("settle", cfg.settleMs);
  prefs.putInt("irlevel", cfg.irLevel);
  prefs.putInt("rgb", cfg.rgbOn);
  prefs.putInt("autobatch", cfg.autoBatch);
  prefs.end();
}

void savePending() {
  prefs.begin("simonpro", false);
  prefs.putUInt("pending", pending);
  prefs.end();
}

// ---------------------------------------------------------------- LEDs (DV-05)
enum LedMode : uint8_t { LED_IDLE, LED_REJECT, LED_ERROR, LED_OK };
LedMode ledMode = LED_IDLE;
uint32_t ledUntil = 0;
int lastExt = -1;
uint32_t lastRgb = 0xFFFFFFFF;

void ledShow(LedMode m, uint32_t ms) {
  ledMode = m;
  ledUntil = millis() + ms;
}

void rgb(uint32_t c) {
  if (!cfg.rgbOn) c = 0;  // `set rgb off`: dark whatever the status
  if (PIN_RGB_LED < 0 || c == lastRgb) return;
  lastRgb = c;
  neopixelWrite(PIN_RGB_LED, (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF);
}

void ledTick() {
  uint32_t now = millis();
  if (ledMode != LED_IDLE && (int32_t)(now - ledUntil) >= 0) ledMode = LED_IDLE;
  bool ext = false;
  uint32_t c = 0;
  switch (ledMode) {
    case LED_REJECT: ext = true; c = 0x400000; break;
    case LED_ERROR: ext = (now / 100) % 2; c = ext ? 0x400000 : 0; break;
    case LED_OK: c = 0x003000; break;
    case LED_IDLE:
      if (apMode) c = (now / 500) % 2 ? 0x200020 : 0;                      // purple blink: setup AP
      else if (WiFi.status() != WL_CONNECTED) c = (now / 500) % 2 ? 0x000030 : 0;  // blue blink: connecting
      else if (cfg.mode == MODE_CAPTURE) c = 0x100800;                     // dim amber: capture mode
      break;
  }
  if ((int)ext != lastExt) {
    digitalWrite(PIN_REJECT_LED, ext ? HIGH : LOW);
    lastExt = ext;
  }
  rgb(c);
}

// ---------------------------------------------------------------- time
bool timeValid() { return time(nullptr) > 1700000000; }

String isoNow() {
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  struct tm t;
  localtime_r(&tv.tv_sec, &t);
  char buf[40];
  size_t n = strftime(buf, sizeof buf, "%Y-%m-%dT%H:%M:%S", &t);
  snprintf(buf + n, sizeof buf - n, ".%03ld+07:00", (long)(tv.tv_usec / 1000));
  return buf;
}

// ---------------------------------------------------------------- camera (DV-04)
void applySensorSettings() {
  sensor_t *s = esp_camera_sensor_get();
  if (!s) return;
  s->set_exposure_ctrl(s, 0);  // manual exposure
  s->set_aec_value(s, cfg.aec);
  s->set_gain_ctrl(s, 0);      // manual gain
  s->set_agc_gain(s, cfg.agc);
  s->set_whitebal(s, 0);       // freeze white balance at the value auto-WB settled on
  s->set_awb_gain(s, 0);
}

bool initCamera() {
  camera_config_t c = {};
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d0 = Y2_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[cam] init failed 0x%x (check camera_pins.h and the ribbon cable)\n", err);
    return false;
  }
  sensor_t *s = esp_camera_sensor_get();
  Serial.printf("[cam] sensor PID 0x%04x %s\n", s->id.PID, s->id.PID == OV5640_PID ? "(OV5640)" : "");
  // Let auto white balance settle for ~2 s under the box lighting, then lock everything.
  for (int i = 0; i < 20; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    delay(100);
  }
  applySensorSettings();
  for (int i = 0; i < 3; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
  }
  return true;
}

// The board has no camera RESET/PWDN line, so after a software reboot the OV5640 is still running and
// the first init can fail. Retry a few times; the driver resets the sensor over SCCB on each init.
bool startCamera() {
  for (int attempt = 1; attempt <= 3; attempt++) {
    if (initCamera()) return true;
    esp_camera_deinit();
    Serial.printf("[cam] retry %d/3\n", attempt);
    delay(500);
  }
  Serial.println("[cam] giving up: unplug and replug USB to power-cycle the camera, then check the ribbon");
  return false;
}

// A frame whose readout started after this call. The driver keeps finished frames in its buffer, so
// the first one or two can be from before the can arrived (or from after the previous can left).
// fb->timestamp is the time since boot at the frame's first DMA buffer.
extern bool pirDebug;
camera_fb_t *grabFresh() {
  const int64_t t0 = esp_timer_get_time();
  camera_fb_t *fb = nullptr;
  int stale = 0;
  for (int i = 0; i < 5; i++) {
    fb = esp_camera_fb_get();
    if (!fb) return nullptr;
    int64_t ts = (int64_t)fb->timestamp.tv_sec * 1000000LL + fb->timestamp.tv_usec;
    if (ts >= t0) break;
    if (i == 4) break;  // give up waiting; use the newest we have
    esp_camera_fb_return(fb);
    stale++;
  }
  if (pirDebug || stale > 1) Serial.printf("[cam] skipped %d stale frame(s), frame %lld ms after request\n", stale,
                                           ((int64_t)fb->timestamp.tv_sec * 1000000LL + fb->timestamp.tv_usec - t0) / 1000);
  return fb;
}

// ---------------------------------------------------------------- HTTP (DV-06, DV-07)
struct Field {
  const char *name;
  String value;
};

int postMultipart(const String &path, const Field *fields, size_t nFields, camera_fb_t *fb, String &body) {
  String head;
  for (size_t i = 0; i < nFields; i++) {
    head += "--"; head += BOUNDARY;
    head += "\r\nContent-Disposition: form-data; name=\""; head += fields[i].name;
    head += "\"\r\n\r\n"; head += fields[i].value; head += "\r\n";
  }
  head += "--"; head += BOUNDARY;
  head += "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"can.jpg\"\r\n"
          "Content-Type: image/jpeg\r\n\r\n";
  String tail = String("\r\n--") + BOUNDARY + "--\r\n";

  size_t total = head.length() + fb->len + tail.length();
  uint8_t *buf = (uint8_t *)ps_malloc(total);
  if (!buf) return -100;
  memcpy(buf, head.c_str(), head.length());
  memcpy(buf + head.length(), fb->buf, fb->len);
  memcpy(buf + head.length() + fb->len, tail.c_str(), tail.length());

  int code = -1;
  for (int attempt = 0; attempt < 2; attempt++) {  // retry once (DV-07)
    HTTPClient http;
    http.setConnectTimeout(3000);
    http.setTimeout(HTTP_TIMEOUT_MS);
    if (!http.begin(cfg.server + path)) break;
    http.addHeader("X-Device-Key", cfg.key);
    http.addHeader("Content-Type", String("multipart/form-data; boundary=") + BOUNDARY);
    code = http.POST(buf, total);
    body = code > 0 ? http.getString() : http.errorToString(code);
    http.end();
    if (code > 0 && code < 500) break;
  }
  free(buf);
  return code;
}

int postJson(const String &path, const String &json, String &body) {
  HTTPClient http;
  http.setConnectTimeout(3000);
  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(cfg.server + path)) return -1;
  http.addHeader("X-Device-Key", cfg.key);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(json);
  body = code > 0 ? http.getString() : http.errorToString(code);
  http.end();
  return code;
}

int getJson(const String &path, String &body, uint32_t timeoutMs = HTTP_TIMEOUT_MS) {
  HTTPClient http;
  http.setConnectTimeout(min(timeoutMs, (uint32_t)3000));
  http.setTimeout(timeoutMs);
  if (!http.begin(cfg.server + path)) return -1;
  http.addHeader("X-Device-Key", cfg.key);
  int code = http.GET();
  body = code > 0 ? http.getString() : http.errorToString(code);
  http.end();
  return code;
}

String shortBody(const String &b) { return b.length() > 200 ? b.substring(0, 200) + "..." : b; }

// ---------------------------------------------------------------- output counting (FR-08)
bool flushOutputs(bool force) {
  if (pending == 0 || cfg.batch.isEmpty() || WiFi.status() != WL_CONNECTED || !timeValid()) return pending == 0;
  if (!force && pending < FLUSH_EVERY_N && millis() - lastFlushMs < FLUSH_EVERY_MS) return false;
  lastFlushMs = millis();
  JsonDocument doc;
  doc["batchCode"] = cfg.batch;
  doc["quantity"] = pending;
  doc["timestamp"] = isoNow();
  String json, body;
  serializeJson(doc, json);
  int code = postJson("/production/outputs", json, body);
  if (code == 201) {
    JsonDocument r;
    deserializeJson(r, body);
    Serial.printf("[out] sent %u, batch total %d\n", pending, (int)(r["totalOutput"] | -1));
    pending = 0;
    savePending();
    return true;
  }
  Serial.printf("[out] failed (%d) %s, keeping %u pending\n", code, shortBody(body).c_str(), pending);
  return false;
}

// ---------------------------------------------------------------- batch follower
// The operator opens and closes batches in the desktop app; in inspect mode the device asks the server
// which batch is running and switches to it (`set autobatch off` to set the batch by hand instead).
static const uint32_t AUTO_BATCH_MS = 5000;

void switchBatch(const String &code) {
  if (pending) {
    flushOutputs(true);  // counted cans belong to the old batch
    if (pending) {       // server answered but refused: the old batch is closed, its cans cannot be added
      Serial.printf("[batch] old batch %s refused %u counted can(s); dropped\n", cfg.batch.c_str(), pending);
      pending = 0;
      savePending();
    }
  }
  Serial.printf("[batch] following the app: %s -> %s\n", cfg.batch.isEmpty() ? "(none)" : cfg.batch.c_str(),
                code.isEmpty() ? "(none running)" : code.c_str());
  cfg.batch = code;
  saveConfig();
}

void batchTick() {
  static uint32_t last = 0;
  if (!cfg.autoBatch || cfg.mode != MODE_INSPECT || apMode || WiFi.status() != WL_CONNECTED) return;
  if (millis() - last < AUTO_BATCH_MS) return;
  last = millis();
  String body;
  int code = getJson("/devices/current-batch", body, 2000);  // short: the sensor loop waits meanwhile
  if (code != 200) return;  // server down or old server: keep the current batch
  JsonDocument r;
  if (deserializeJson(r, body)) return;
  String running = r["batchCode"].isNull() ? String("") : String((const char *)r["batchCode"]);
  if (running != cfg.batch) switchBatch(running);
}

// ---------------------------------------------------------------- one can
void inspectCan() {
  if (cfg.batch.isEmpty()) {
    Serial.println("[insp] no batch set: `set batch <code>`");
    ledShow(LED_ERROR, ERROR_LED_MS);
    return;
  }
  uint32_t tTrig = millis();
  pending++;  // the can was produced whatever happens next
  savePending();

  if (cfg.settleMs > 0) delay(cfg.settleMs);
  camera_fb_t *fb = cameraOk ? grabFresh() : nullptr;
  uint32_t tCap = millis();
  if (!fb || WiFi.status() != WL_CONNECTED || !timeValid()) {
    Serial.printf("[insp] cannot inspect: camera=%d wifi=%d time=%d\n", fb != nullptr,
                  WiFi.status() == WL_CONNECTED, timeValid());
    if (fb) esp_camera_fb_return(fb);
    errCount++;
    ledShow(LED_ERROR, ERROR_LED_MS);
    return;
  }

  Field fields[] = {{"batchCode", cfg.batch}, {"timestamp", isoNow()}};
  String body;
  size_t jpgLen = fb->len;
  int code = postMultipart("/inspections", fields, 2, fb, body);
  esp_camera_fb_return(fb);
  uint32_t tResp = millis();

  if (code == 201) {
    JsonDocument r;
    deserializeJson(r, body);
    bool reject = r["reject"] | false;
    ledShow(reject ? LED_REJECT : LED_OK, reject ? REJECT_LED_MS : OK_LED_MS);
    ledTick();
    uint32_t tLed = millis();
    reject ? ngCount++ : okCount++;
    Serial.printf("[insp] #%d %s score=%.3f thr=%.3f | jpg %uB | K4 settle+cap %ums, upload+infer %ums, "
                  "trigger->LED %ums\n",
                  (int)(r["inspectionId"] | 0), (const char *)(r["result"] | "?"), (float)(r["anomalyScore"] | 0.0),
                  (float)(r["threshold"] | 0.0), (unsigned)jpgLen, tCap - tTrig, tResp - tCap, tLed - tTrig);
  } else {
    errCount++;
    ledShow(LED_ERROR, ERROR_LED_MS);
    Serial.printf("[insp] failed (%d) %s\n", code, shortBody(body).c_str());
  }
  flushOutputs(false);
}

void captureCan() {
  if (cfg.settleMs > 0) delay(cfg.settleMs);
  camera_fb_t *fb = cameraOk ? grabFresh() : nullptr;
  if (!fb || WiFi.status() != WL_CONNECTED) {
    Serial.println("[cap] camera or Wi-Fi not ready");
    if (fb) esp_camera_fb_return(fb);
    ledShow(LED_ERROR, ERROR_LED_MS);
    return;
  }
  Field fields[] = {{"sku", cfg.sku}, {"label", cfg.label}, {"canId", cfg.canId}};
  String body;
  int code = postMultipart("/dev/capture", fields, 3, fb, body);
  esp_camera_fb_return(fb);
  if (code == 201) {
    JsonDocument r;
    deserializeJson(r, body);
    ledShow(LED_OK, OK_LED_MS);
    Serial.printf("[cap] %s/%s can %s saved (%d in folder)\n", cfg.sku.c_str(), cfg.label.c_str(),
                  cfg.canId.c_str(), (int)(r["count"] | 0));
  } else {
    ledShow(LED_ERROR, ERROR_LED_MS);
    Serial.printf("[cap] failed (%d) %s\n", code, shortBody(body).c_str());
  }
}

void onCan() { cfg.mode == MODE_CAPTURE ? captureCan() : inspectCan(); }

// ---------------------------------------------------------------- IR sensor (DV-03, FR-07)
// Polled state machine: active for CONFIRM_MS -> one can; then wait for inactive for RELEASE_MS.
enum IrState : uint8_t { IR_IDLE, IR_CONFIRM, IR_WAIT_RELEASE, IR_RELEASING };
IrState irState = IR_WAIT_RELEASE;  // require an inactive baseline after PIR warm-up
uint32_t irSince = 0, lastCanMs = 0;
uint32_t irReadyMs = 0;

// Pull the pin towards "no can": some modules only drive the detect level and float otherwise.
void applyIrPin() {
  pinMode(PIN_IR_SENSOR, cfg.irLevel ? INPUT_PULLDOWN : INPUT_PULLUP);
}

bool pirDebug = false;  // `pir` console command: log raw GPIO level changes

void pirDebugTick(uint32_t now) {
  static int last = -1;
  static uint32_t since = 0;
  int v = digitalRead(PIN_IR_SENSOR);
  if (v == last) return;
  if (pirDebug) {
    Serial.printf("[pir] %8.2fs GPIO%d=%d %-6s", now / 1000.0, PIN_IR_SENSOR, v,
                  v == (cfg.irLevel ? HIGH : LOW) ? "detect" : "clear");
    if (last >= 0) Serial.printf("  (was %d for %.2fs)", last, (now - since) / 1000.0);
    if ((int32_t)(now - irReadyMs) < 0) Serial.print("  [warm-up]");
    Serial.println();
  }
  last = v;
  since = now;
}

void irTick() {
  uint32_t now = millis();
  pirDebugTick(now);
  if ((int32_t)(now - irReadyMs) < 0) return;  // ignore PIR output during power-on calibration
  bool active = digitalRead(PIN_IR_SENSOR) == (cfg.irLevel ? HIGH : LOW);
  switch (irState) {
    case IR_IDLE:
      if (active) { irState = IR_CONFIRM; irSince = now; }
      break;
    case IR_CONFIRM:
      if (!active) irState = IR_IDLE;
      else if (now - irSince >= CONFIRM_MS && now - lastCanMs >= LOCKOUT_MS) {
        lastCanMs = now;
        irState = IR_WAIT_RELEASE;
        onCan();
      }
      break;
    case IR_WAIT_RELEASE:
      if (!active) { irState = IR_RELEASING; irSince = now; }
      break;
    case IR_RELEASING:
      if (active) irState = IR_WAIT_RELEASE;
      else if (now - irSince >= RELEASE_MS) irState = IR_IDLE;
      break;
  }
}

// ---------------------------------------------------------------- Wi-Fi (DV-01)
void startWifi() {
  if (cfg.ssid.isEmpty()) {
    apMode = true;
    WiFi.mode(WIFI_AP);
    WiFi.softAP("SiMonPro-Setup");
    Serial.printf("[wifi] no SSID set: AP \"SiMonPro-Setup\", open http://%s/\n", WiFi.softAPIP().toString().c_str());
    return;
  }
  apMode = false;
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // lower, steadier latency
  WiFi.setAutoReconnect(true);
  WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
  lastWifiTry = millis();
  Serial.printf("[wifi] connecting to %s\n", cfg.ssid.c_str());
}

void wifiTick() {
  static bool wasUp = false;
  if (apMode) return;
  bool up = WiFi.status() == WL_CONNECTED;
  if (up && !wasUp) {
    Serial.printf("[wifi] connected, IP %s (http://%s/ or http://simonpro.local/)\n",
                  WiFi.localIP().toString().c_str(), WiFi.localIP().toString().c_str());
    MDNS.begin("simonpro");
    configTzTime(TZ_WIB, "pool.ntp.org", "time.google.com", "id.pool.ntp.org");
  }
  if (!up && wasUp) Serial.println("[wifi] lost connection");
  if (!up && millis() - lastWifiTry > WIFI_RETRY_MS) {
    Serial.println("[wifi] reconnecting");
    WiFi.disconnect();
    WiFi.begin(cfg.ssid.c_str(), cfg.pass.c_str());
    lastWifiTry = millis();
  }
  wasUp = up;
}

// ---------------------------------------------------------------- settings changes
// Returns "" on success, else an error message.
String setKey(String k, const String &v) {
  k.toLowerCase();
  if (k == "batch" && v != cfg.batch) {
    flushOutputs(true);  // pending cans belong to the old batch
    if (pending) return "could not send pending outputs for the old batch; try `flush` first";
    cfg.batch = v;
  } else if (k == "batch") {
  } else if (k == "ssid") cfg.ssid = v;
  else if (k == "pass") cfg.pass = v;
  else if (k == "server") { cfg.server = v; while (cfg.server.endsWith("/")) cfg.server.remove(cfg.server.length() - 1); }
  else if (k == "key") cfg.key = v;
  else if (k == "sku") cfg.sku = v;
  else if (k == "label") { if (v != "ok" && v != "ng") return "label must be ok or ng"; cfg.label = v; }
  else if (k == "can") { if (v.indexOf('_') >= 0 || v.isEmpty()) return "can id: no '_'"; cfg.canId = v; }
  else if (k == "mode") {
    if (v == "inspect") cfg.mode = MODE_INSPECT;
    else if (v == "capture") cfg.mode = MODE_CAPTURE;
    else return "mode must be inspect or capture";
  }
  else if (k == "aec") { cfg.aec = constrain(v.toInt(), 0, 1200); applySensorSettings(); }
  else if (k == "agc") { cfg.agc = constrain(v.toInt(), 0, 30); applySensorSettings(); }
  else if (k == "settle") cfg.settleMs = constrain(v.toInt(), 0, 3000);
  else if (k == "irlevel") {
    String lv = v;
    lv.toLowerCase();
    if (lv == "low" || lv == "0") cfg.irLevel = 0;
    else if (lv == "high" || lv == "1") cfg.irLevel = 1;
    else return "irlevel must be low or high";
    applyIrPin();
    irState = IR_WAIT_RELEASE;  // wait for "no can" under the new meaning before counting
  }
  else if (k == "autobatch") {
    String lv = v;
    lv.toLowerCase();
    if (lv == "on" || lv == "1") cfg.autoBatch = 1;
    else if (lv == "off" || lv == "0") cfg.autoBatch = 0;
    else return "autobatch must be on or off";
  }
  else if (k == "rgb") {
    String lv = v;
    lv.toLowerCase();
    if (lv == "on" || lv == "1") cfg.rgbOn = 1;
    else if (lv == "off" || lv == "0") cfg.rgbOn = 0;
    else return "rgb must be on or off";
  }
  else return "unknown key " + k;
  saveConfig();
  return "";
}

// "c001" -> "c002" (keeps the prefix and zero padding)
void nextCan() {
  int i = cfg.canId.length();
  while (i > 0 && isDigit(cfg.canId[i - 1])) i--;
  String prefix = cfg.canId.substring(0, i), digits = cfg.canId.substring(i);
  String n = String(digits.toInt() + 1);
  while (n.length() < max((unsigned)digits.length(), 3u)) n = "0" + n;
  cfg.canId = prefix + n;
  saveConfig();
}

void printStatus(Print &out) {
  out.printf("mode=%s batch=%s pending=%u ok=%u ng=%u err=%u\n", cfg.mode == MODE_CAPTURE ? "capture" : "inspect",
             cfg.batch.c_str(), pending, okCount, ngCount, errCount);
  out.printf("wifi=%s ip=%s server=%s time=%s\n", cfg.ssid.c_str(),
             apMode ? WiFi.softAPIP().toString().c_str() : WiFi.localIP().toString().c_str(), cfg.server.c_str(),
             timeValid() ? isoNow().c_str() : "not synced");
  out.printf("sensor GPIO%d=%d (%s) irlevel=%s rgb=%s autobatch=%s\n", PIN_IR_SENSOR, digitalRead(PIN_IR_SENSOR),
             digitalRead(PIN_IR_SENSOR) == (cfg.irLevel ? HIGH : LOW) ? "detect" : "clear", cfg.irLevel ? "high" : "low",
             cfg.rgbOn ? "on" : "off", cfg.autoBatch ? "on" : "off");
  out.printf("camera=%s aec=%d agc=%d settle=%dms | capture: sku=%s label=%s can=%s | psram free %u\n",
             cameraOk ? "ok" : "FAIL", cfg.aec, cfg.agc, cfg.settleMs, cfg.sku.c_str(), cfg.label.c_str(),
             cfg.canId.c_str(), ESP.getFreePsram());
}

// ---------------------------------------------------------------- serial console
void handleCommand(String line) {
  line.trim();
  if (line.isEmpty()) return;
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String rest = sp < 0 ? "" : line.substring(sp + 1);
  rest.trim();
  cmd.toLowerCase();

  if (cmd == "help") {
    Serial.println(
        "status | snap (= one can, without the sensor) | flush | next (can id +1) | wifi | reboot\n"
        "pir (toggle raw sensor GPIO log) | camera (restart camera, re-lock white balance on the current scene)\n"
        "set <key> <value>  keys: ssid pass server key batch mode(inspect|capture) sku label(ok|ng) can aec agc settle\n"
        "                   irlevel(low|high: sensor OUT level while it sees a can) rgb(on|off: onboard LED)\n"
        "                   autobatch(on|off: follow the batch running in the app)\n"
        "mode inspect|capture | batch <code> | label ok|ng | can <id>");
  } else if (cmd == "status") printStatus(Serial);
  else if (cmd == "snap") onCan();
  else if (cmd == "flush") Serial.println(flushOutputs(true) ? "[out] nothing pending" : "[out] still pending");
  else if (cmd == "next") { nextCan(); Serial.printf("can=%s\n", cfg.canId.c_str()); }
  else if (cmd == "wifi") startWifi();
  else if (cmd == "reboot") ESP.restart();
  else if (cmd == "camera") {  // restart only the camera: white balance re-locks on what it sees now
    Serial.println("[cam] restarting; keep the scene still for ~2 s (white balance locks on it)");
    esp_camera_deinit();
    cameraOk = startCamera();
    Serial.printf("[cam] %s\n", cameraOk ? "ready" : "FAIL");
  }
  else if (cmd == "pir") { pirDebug = !pirDebug; Serial.printf("pir log %s\n", pirDebug ? "on" : "off"); }
  else if (cmd == "set" || cmd == "mode" || cmd == "batch" || cmd == "label" || cmd == "can") {
    String k = cmd, v = rest;
    if (cmd == "set") {
      int s2 = rest.indexOf(' ');
      k = s2 < 0 ? rest : rest.substring(0, s2);
      v = s2 < 0 ? "" : rest.substring(s2 + 1);
      v.trim();
    }
    String err = setKey(k, v);
    Serial.println(err.isEmpty() ? "ok" : "error: " + err);
    if (err.isEmpty() && (k == "ssid" || k == "pass")) Serial.println("type `wifi` to reconnect");
  } else Serial.println("unknown command, type `help`");
}

void serialTick() {
  static String line;
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (line.length()) handleCommand(line);
      line = "";
    } else if (line.length() < 200) line += ch;
  }
}

// ---------------------------------------------------------------- web page
String htmlEscape(const String &s) {
  String o;
  for (char c : s) {
    if (c == '<') o += "&lt;";
    else if (c == '>') o += "&gt;";
    else if (c == '"') o += "&quot;";
    else if (c == '&') o += "&amp;";
    else o += c;
  }
  return o;
}

String inputRow(const char *label, const char *name, const String &value, const char *type = "text") {
  return String("<label>") + label + "<input type=" + type + " name=" + name + " value=\"" + htmlEscape(value) +
         "\"></label>";
}

void handleRoot() {
  String msg = web.hasArg("msg") ? htmlEscape(web.arg("msg")) : "";
  String s =
      "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
      "<title>SiMonPro device</title><style>body{font:15px sans-serif;max-width:560px;margin:16px auto;padding:0 12px}"
      "label{display:block;margin:6px 0}input,select{width:100%;padding:6px;box-sizing:border-box}"
      "button{padding:8px 14px;margin:4px 4px 0 0}pre{background:#eee;padding:8px;white-space:pre-wrap}"
      "img{width:100%;margin-top:8px}</style><h2>SiMonPro kotak foto</h2>";
  if (msg.length()) s += "<p><b>" + msg + "</b></p>";
  StreamString st;
  printStatus(st);
  s += "<pre>" + htmlEscape(st) + "</pre>";
  s += "<form method=post action=/save>";
  s += inputRow("Kode batch", "batch", cfg.batch);
  s += "<label>Mode<select name=mode><option value=inspect" + String(cfg.mode == MODE_INSPECT ? " selected" : "") +
       ">Inspeksi</option><option value=capture" + String(cfg.mode == MODE_CAPTURE ? " selected" : "") +
       ">Ambil dataset</option></select></label>";
  s += inputRow("SKU (dataset)", "sku", cfg.sku);
  s += "<label>Label (dataset)<select name=label><option" + String(cfg.label == "ok" ? " selected" : "") +
       ">ok</option><option" + String(cfg.label == "ng" ? " selected" : "") + ">ng</option></select></label>";
  s += inputRow("ID kaleng (dataset)", "can", cfg.canId);
  s += inputRow("Exposure (aec 0..1200)", "aec", String(cfg.aec), "number");
  s += inputRow("Gain (agc 0..30)", "agc", String(cfg.agc), "number");
  s += inputRow("Jeda sebelum foto (ms)", "settle", String(cfg.settleMs), "number");
  s += inputRow("Level sensor saat ada kaleng (low/high)", "irlevel", cfg.irLevel ? "high" : "low", "text");
  s += inputRow("LED RGB di board (on/off)", "rgb", cfg.rgbOn ? "on" : "off", "text");
  s += inputRow("Ikuti batch dari aplikasi (on/off)", "autobatch", cfg.autoBatch ? "on" : "off", "text");
  s += inputRow("Server URL", "server", cfg.server);
  s += inputRow("Device key", "key", cfg.key, "password");
  s += inputRow("Wi-Fi SSID", "ssid", cfg.ssid);
  s += inputRow("Wi-Fi password (kosongkan = tetap)", "pass", "", "password");
  s += "<button>Simpan</button></form>";
  s += "<form method=post action=/snap style=display:inline><button>Foto + kirim (1 kaleng)</button></form>"
       "<form method=post action=/next style=display:inline><button>ID kaleng +1</button></form>"
       "<form method=post action=/flush style=display:inline><button>Kirim jumlah output</button></form>"
       "<p><a href=/>refresh</a> &middot; <a href=/jpg target=_blank>foto langsung</a></p>"
       "<img src=/jpg alt='preview kamera'>";
  web.send(200, "text/html", s);
}

void redirect(const String &msg) {
  web.sendHeader("Location", "/?msg=" + msg);
  web.send(303);
}

void handleSave() {
  const char *keys[] = {"batch", "mode", "sku", "label", "can", "aec", "agc", "settle", "irlevel", "rgb", "autobatch", "server", "key", "ssid", "pass"};
  String errs;
  String oldSsid = cfg.ssid, oldPass = cfg.pass;
  for (const char *k : keys) {
    if (!web.hasArg(k)) continue;
    String v = web.arg(k);
    v.trim();
    if (String(k) == "pass" && v.isEmpty()) continue;
    String e = setKey(k, v);
    if (e.length()) errs += e + "; ";
  }
  redirect(errs.isEmpty() ? "Tersimpan" : errs);
  if (cfg.ssid != oldSsid || cfg.pass != oldPass) {
    delay(200);
    startWifi();
  }
}

void handleJpg() {
  camera_fb_t *fb = cameraOk ? grabFresh() : nullptr;
  if (!fb) { web.send(503, "text/plain", "camera not ready"); return; }
  web.sendHeader("Cache-Control", "no-store");
  web.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void setupWeb() {
  web.on("/", HTTP_GET, handleRoot);
  web.on("/save", HTTP_POST, handleSave);
  web.on("/jpg", HTTP_GET, handleJpg);
  web.on("/snap", HTTP_POST, [] { onCan(); redirect("Terkirim, lihat status"); });
  web.on("/next", HTTP_POST, [] { nextCan(); redirect("ID kaleng " + cfg.canId); });
  web.on("/flush", HTTP_POST, [] { redirect(flushOutputs(true) ? "Output terkirim" : "Gagal kirim output"); });
  web.begin();
}

// ---------------------------------------------------------------- main
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 1500) delay(10);
  Serial.println("\n[boot] SiMonPro firmware");

  pinMode(PIN_REJECT_LED, OUTPUT);
  digitalWrite(PIN_REJECT_LED, LOW);
  rgb(0);

  loadConfig();
  applyIrPin();  // after loadConfig: the pull direction follows the saved irlevel
  irReadyMs = millis() + PIN_IR_WARMUP_MS;
  Serial.printf("[sensor] warming up for %u s; waiting for \"no can\" first\n", PIN_IR_WARMUP_MS / 1000);
  Serial.printf("[boot] PSRAM %u KB, flash %u MB\n", ESP.getPsramSize() / 1024, ESP.getFlashChipSize() >> 20);
  cameraOk = startCamera();
  startWifi();
  setupWeb();
  printStatus(Serial);
  Serial.println("type `help` for commands");
}

void loop() {
  serialTick();
  wifiTick();
  web.handleClient();
  irTick();
  ledTick();
  flushOutputs(false);
  batchTick();
  delay(2);
}
