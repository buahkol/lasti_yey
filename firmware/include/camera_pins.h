#pragma once
// Camera pin map for generic "ESP32-S3-CAM" N16R8 boards with a 24-pin ribbon connector
// (same as Freenove ESP32-S3-WROOM CAM and Espressif ESP32-S3-EYE; OV2640/OV3660/OV5640).
// If the camera fails to start ("Camera init failed 0x105/0x20004"), compare this with the
// vendor's CameraWebServer example for your exact board.

#define PWDN_GPIO_NUM  -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  15
#define SIOD_GPIO_NUM  4
#define SIOC_GPIO_NUM  5

#define Y9_GPIO_NUM 16
#define Y8_GPIO_NUM 17
#define Y7_GPIO_NUM 18
#define Y6_GPIO_NUM 12
#define Y5_GPIO_NUM 10
#define Y4_GPIO_NUM 8
#define Y3_GPIO_NUM 9
#define Y2_GPIO_NUM 11

#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM  7
#define PCLK_GPIO_NUM  13

// Pins used above, plus the ones to avoid on an S3 N16R8:
//   strapping 0, 3, 45, 46 | USB 19, 20 | octal PSRAM/flash 26-32, 33-37
// Free for the photo box: 1, 2, 14, 21, 38, 39, 40, 41, 42, 47 (48 = onboard RGB LED on most boards).
