# Air-Sentinel v2.6

**Author:** Andrew Armstrong
**Status:** v2.6 (Stable Build)

An engineering-grade environmental monitor and automation controller built for the **Raspberry Pi Pico W**. Air-Sentinel bridges the gap between raw particulate sensing and actionable hardware responses, featuring a robust calibration engine, real-time telemetry, and localized weather correlation.

## 🚀 Key Features

* **Precision AQI Sensing:** High-fidelity sampling of PM2.5 particulates using the PPD42NS sensor with adjustable voltage offsets.
* **Automated Mitigation (GPIO 2-7):** 6-stage hardware control logic that triggers external fans, scrubbers, or alarms based on EPA-standard AQI thresholds.
* **Environmental Correlation:** Synchronizes with the **Open-Meteo API** to overlay indoor air data with local temperature and sky conditions.
* **User Agency Calibration:** Dedicated 500-sample calibration routine with persistent flash storage and a `.txt` audit trail for sensor drift tracking.
* **Multi-View Interface:** 5-page OLED dashboard including live trend graphing and network diagnostics.
* **Telemetry Stream:** 1Hz JSON output via Serial for easy integration with Node-RED, InfluxDB, or Grafana.

---

## 🛠 Hardware Configuration

### Bill of Materials (BOM)

| Component | Specification | Quantity | Purpose |
| --- | --- | --- | --- |
| **Microcontroller** | Raspberry Pi Pico W | 1 | System logic and Wi-Fi stack |
| **Particulate Sensor** | PPD42NS Dust Sensor | 1 | PM2.5 detection (Analog/PWM) |
| **Display** | SSD1306 OLED (128x32) | 1 | Visual interface via I2C |
| **Resistor** | 10kΩ / 1kΩ | As needed | Voltage division for sensor signal |
| **Capacitor** | 10uF | 1 | Sensor power rail stabilization |
| **External Gear** | 5V/12V Fans or Relays | Opt. | Connected via GPIO 2-7 |

### Wiring Diagram

| Pico W Pin | Component | Pin Function |
| --- | --- | --- |
| **GP0** | SSD1306 OLED | I2C SDA |
| **GP1** | SSD1306 OLED | I2C SCL |
| **GP2 - GP7** | External Hardware | AQI Level 0-5 Outputs |
| **GP26** | PPD42NS | LED Trigger (Output) |
| **GP27** | PPD42NS | ADC Input (Analog Sampling) |
| **VBUS (5V)** | PPD42NS | Sensor Power |
| **3V3** | SSD1306 / Pico | Logic Power |

---

## 💻 Software Architecture

The OS is built on a non-blocking event loop in MicroPython, managing concurrent sensor sampling, UI refreshes, and API calls.

### AQI Logic & Automation

The system maps PM2.5 concentration () to specific GPIO outputs to drive mitigation hardware:

| Category | PM2.5 Range | GPIO Active | Status |
| --- | --- | --- | --- |
| **Good** | 0.0 – 12.0 | GP2 | Healthy |
| **Moderate** | 12.1 – 35.4 | GP3 | Caution |
| **Unhealthy-S** | 35.5 – 55.4 | GP4 | Sensitive Groups |
| **Unhealthy** | 55.5 – 150.4 | GP5 | Action Required |
| **Very Unhealthy** | 150.5 – 250.4 | GP6 | Critical |
| **Hazardous** | 250.5+ | GP7 | Emergency |

### Persistent Storage

* `config.json`: Stores Wi-Fi credentials, GPS coordinates, and the calibrated sensor offset.
* `cal_history.txt`: An append-only log recording every manual calibration event with a timestamp and voltage delta.

---

## 🕹 Operation Guide

### Input Controls (BOOTSEL Button)

* **Single Tap:** Cycle through UI views (Dashboard ➔ Weather ➔ Graph ➔ Diag ➔ Scan).
* **Double Tap:** Toggle **Auto-Cycle Mode** (Cycles views every 10s).
* **Hold (5s):** Initiates **Calibration Mode**. Ensure the device is in a "clean air" environment.
* **Hold (10s):** Launches **Setup AP Mode**.

### Setup Portal

When in AP Mode, connect to `AirSentinel_AP` and navigate to `192.168.4.1`. The web interface allows for:

1. Wi-Fi Credential Entry.
2. Lat/Lon configuration for Open-Meteo data.
3. Manual Sensor Offset adjustment.
4. Viewing the historical Calibration Audit Log.

### Serial Telemetry

The device outputs a standard JSON string every second:

```json
{
  "ts": "2026-01-10 20:05:12",
  "dust": 14.22,
  "cat": "MODERATE",
  "cal": 0.6145,
  "temp": "19C",
  "weather": "Clear",
  "rssi": -64,
  "auto": true
}

```
### Wiring Diagram

```text
            RPI PICO W                        SSD1306 OLED (I2C)
          _________________                   _________________
         |                 |                 |                 |
         |             VBUS|                 |                 |
         |              GND|---[ GND]--------|GND              |
         |          3V3_OUT|---[ 3V3]--------|VCC              |
         |                 |                 |                 |
         |        GP0 (SDA)|-----------------|SDA              |
         |        GP1 (SCL)|-----------------|SCL              |
         |_________________|                 |_________________|
                 |
                 |                             PPD42NS SENSOR
                 |                            _________________
                 |                           |                 |
                 |----[ 5V ]-----------------|Pin 1 (VCC)      |
                 |                           |                 |
                 |----[GP26]-----------------|Pin 2 (LED Trig) |
                 |                           |                 |
                 |----[GND ]-----------------|Pin 3 (GND)      |
                 |           ___             |                 |
                 |----[GP27]|_R*_|-----------|Pin 4 (Output)   |
                 |___________________________|_________________|
                               |
                        [ 10uF Capacitor* ]
                        (Between VCC & GND)

*May already be included in your module

```

### Connectivity Reference

Pico W Pin	Component	Function	Notes
VBUS	PPD42NS	5V Power	Essential for the sensor heater.
3V3_OUT	SSD1306	3.3V Power	Standard logic level for OLED.
GND	Both	Ground	Ensure a common ground for all.
GP0	SSD1306	I2C SDA	Data line for display.
GP1	SSD1306	I2C SCL	Clock line for display.
GP26	PPD42NS	LED Control	Triggers the internal IR LED.
GP27	PPD42NS	ADC Input	Measures the analog voltage drop

```

---

## 🛠 Installation

1. Flash your Raspberry Pi Pico W with the latest **MicroPython** firmware.
2. Upload `ssd1306.py` (driver) and `main.py` (the provided source code) to the root directory.
3. Create an empty `config.json` or let the OS generate one on first boot.
4. Reboot and hold **BOOTSEL** for 10s to configure your network.

---

**Project maintained by Andrew Armstrong.** *For hardware schematics or deployment logs, please refer to the `/docs` folder.*

## ⚠️ Disclaimer
This project is for educational and hobbyist purposes only. While Air-Sentinel OS is designed for precision, it is not a life-safety device. The author (Andrew Armstrong) is not responsible for any hardware damage, property loss, or health issues resulting from the use of this software or reliance on its readings. Always maintain manual oversight of high-voltage hardware.

## ⚖️ License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

**What this means:**
* ✅ **Personal/Hobbyist Use:** You are free to build, modify, and use this for your own home or research.
* ❌ **No Commercial Use:** You may not sell this software, or hardware pre-loaded with this software, without explicit permission.
* 🔄 **ShareAlike:** Any modifications you share must be released under the same license.

For commercial licensing inquiries, please contact Andrew Armstrong directly.
