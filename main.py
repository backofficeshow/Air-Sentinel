"""
AIR-SENTINEL OS v2.6
(c) 2026 Andrew Armstrong

DESCRIPTION:
Engineering-grade AQI (air quality Index) monitor. Includes persistent calibration logging,
manual auto-mode override (RAM-only), animated progress bars, and
expanded JSON telemetry including time, weather and network diagnostics.
"""

import network, urequests, utime, ntptime, rp2, json, socket, machine, math
from machine import Pin, I2C, ADC
import ssd1306

# --- 1. Hardware Setup ---
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 32, i2c)
dust_led, dust_adc = Pin(26, Pin.OUT), ADC(27)
CONFIG_FILE, LOG_FILE = 'config.json', 'cal_history.txt'

# Category Control Pins (GPIO 2-7)
control_pins = [Pin(i, Pin.OUT) for i in range(2, 8)]

# --- 2. State Management ---
state = {
    "mode": 0, "auto_cycle": False, "msg_timer": 0, "msg_text": "",
    "dust_val": 0.0, "dust_history": [0.0]*60, "dust_offset": 0.6,
    "weather_temp": "--C", "weather_desc": "Syncing...",
    "last_weather_update": -900000, "last_ntp_update": -86400000,
    "last_mode_change": utime.ticks_ms(), "last_scan_time": 0, "networks": [],
    "config": {"ssid": "", "pass": "", "lat": "51.7520", "lon": "-1.2577", "auto": False, "offset": 0.6}
}

# --- 3. Calibration & Logging ---
def log_calibration(offset):
    t = utime.localtime()
    ts = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4])
    try:
        with open(LOG_FILE, 'a') as f: f.write(f"{ts}, {offset:.4f}\n")
    except: pass

def calibrate_sensor():
    for pin in control_pins: pin.value(0)
    samples = []
    oled.fill(0)
    oled.text("CALIBRATING...", 10, 5)
    oled.rect(10, 20, 108, 10, 1)
    oled.show()
    for i in range(500):
        dust_led.value(0); utime.sleep_us(280)
        v = (dust_adc.read_u16()/65535)*3.3; utime.sleep_us(40); dust_led.value(1)
        samples.append(v)
        if i % 10 == 0:
            progress = int((i / 500) * 104)
            oled.fill_rect(12, 22, progress, 6, 1)
            oled.show()
        utime.sleep_ms(10)
    avg = sum(samples)/len(samples)
    state["dust_offset"] = avg
    save_config(offset=avg)
    state["msg_text"] = "CAL & LOGGED!"
    state["msg_timer"] = utime.ticks_ms() + 2000

# --- 4. Storage & Logic ---
def get_aqi_category(c):
    if c <= 12.0: return "GOOD", 0
    elif c <= 35.4: return "MODERATE", 1
    elif c <= 55.4: return "UNHEALTHY-S", 2
    elif c <= 150.4: return "UNHEALTHY", 3
    elif c <= 250.4: return "V. UNHEALTHY", 4
    else: return "HAZARDOUS", 5

def update_hardware(c):
    cat_str, level = get_aqi_category(c)
    for i, pin in enumerate(control_pins):
        pin.value(1 if i == level else 0)
    return cat_str

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            saved = json.load(f)
            state["config"].update(saved)
            state["auto_cycle"] = state["config"].get("auto", False)
            state["dust_offset"] = state["config"].get("offset", 0.6)
            print("Config loaded successfully.")
    except (OSError, ValueError):
        print("Config not found or corrupt. Creating default...")
        save_config() # This triggers the creation of a fresh config.json with state['config'] defaults

def save_config(ssid=None, password=None, lat=None, lon=None, auto=None, offset=None):
    if ssid is not None: state["config"]["ssid"] = ssid
    if password is not None: state["config"]["pass"] = password
    if lat is not None: state["config"]["lat"] = lat
    if lon is not None: state["config"]["lon"] = lon
    if auto is not None: state["config"]["auto"] = auto
    if offset is not None: 
        state["config"]["offset"] = float(offset); log_calibration(float(offset))
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(state["config"], f)
    except: pass

def url_decode(s):
    s = s.replace('+', ' ')
    res = ""; i = 0
    while i < len(s):
        if s[i] == '%' and i+2 < len(s):
            res += chr(int(s[i+1:i+3], 16)); i += 3
        else: res += s[i]; i += 1
    return res

# --- 5. Portal & Networking ---
def run_setup_ap():
    ap = network.WLAN(network.AP_IF); ap.active(True)
    ap.config(essid="AirSentinel_AP", password="password123")
    s = socket.socket(); s.bind(('192.168.4.1', 80)); s.listen(1); s.settimeout(0.5)
    while True:
        oled.fill(0)
        oled.text("AirSentinel_AP", 0, 0)
        oled.text("pass: password123", 0, 12)
        oled.text("IP: 192.168.4.1", 0, 24)
        oled.show()
        try:
            cl, addr = s.accept(); req = cl.recv(1024).decode('utf-8')
            if "GET /logs" in req:
                try: 
                    with open(LOG_FILE, 'r') as f: log_data = f.read()
                except: log_data = "No history found."
                cl.send('HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\n' + log_data); cl.close(); continue
            if "GET /?s=" in req:
                query = req.split('\n')[0].split(' ')[1].split('?')[1]
                p = {u.split('=')[0]: u.split('=')[1] for u in query.split('&')}
                save_config(url_decode(p['s']), url_decode(p['p']), url_decode(p['la']), url_decode(p['lo']), offset=p.get('os', 0.6))
                cl.send('HTTP/1.0 200 OK\r\n\r\nSaved! Rebooting...'); cl.close(); utime.sleep(1); machine.reset()
            
            html = f"""<html><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body{{font-family:sans-serif;padding:20px;background:#f4f4f9;}}input{{width:100%;padding:10px;margin:5px 0;}}.btn{{display:block;width:100%;padding:12px;text-align:center;background:#2ecc71;color:white;text-decoration:none;border-radius:5px;border:none;margin-top:10px;}}.log{{background:#3498db;}}</style></head>
            <body><h2>Air-Sentinel Settings</h2><p>(c) 2026 Andrew Armstrong</p><form>
            SSID:<input name='s' value='{state['config']['ssid']}'>
            Pass:<input name='p' type='password'>
            Lat:<input name='la' value='{state['config']['lat']}'>
            Lon:<input name='lo' value='{state['config']['lon']}'>
            Offset (V):<input name='os' value='{state['dust_offset']:.4f}'>
            <input type='submit' class='btn' value='Save & Reboot'></form>
            <a href='/logs' class='btn log'>View Calibration History</a></body></html>"""
            cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + html); cl.close()
        except: pass
        if rp2.bootsel_button(): break
    machine.reset()

def scan_wifi():
    wlan = network.WLAN(network.STA_IF)
    try: state["networks"] = sorted(wlan.scan(), key=lambda x: x[3], reverse=True)
    except: pass

def sync_data():
    now = utime.ticks_ms(); wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected(): return
    if utime.ticks_diff(now, state["last_ntp_update"]) > 86400000:
        try: ntptime.settime(); state["last_ntp_update"] = now
        except: pass
    if utime.ticks_diff(now, state["last_weather_update"]) > 900000:
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={state['config']['lat']}&longitude={state['config']['lon']}&current_weather=true"
            res = urequests.get(url).json(); curr = res['current_weather']
            state["weather_temp"] = f"{int(curr['temperature'])}C"
            state["weather_desc"] = {0:"Clear", 1:"Mainly Clear", 2:"Partly Cloud", 3:"Overcast", 61:"Rainy"}.get(curr['weathercode'], "Cloudy")
            state["last_weather_update"] = now
        except: pass

# --- 6. UI Views ---
def view_dashboard(t):
    oled.text("{:02d}:{:02d}:{:02d}  {}".format(t[3],t[4],t[5],state["weather_temp"]), 0, 0)
    oled.text("{:02d}/{:02d}/{:04d}".format(t[2], t[1], t[0]), 0, 8)
    cat = update_hardware(state["dust_val"])
    label = f"STATUS: {cat}"
    if state["dust_val"] > 35 and (utime.ticks_ms()//500)%2 == 0: label = "!!! WARNING !!!"
    oled.text(label, 0, 16); oled.text("PM2.5: {:.2f} ug/m3".format(state["dust_val"]), 0, 24)

def view_weather(t):
    oled.text("WEATHER REPORT", 0, 0); oled.text("-" * 16, 0, 8)
    oled.text("TEMP: " + state["weather_temp"], 0, 16); oled.text(state["weather_desc"].upper(), 0, 24)

def view_graph(t):
    cat, _ = get_aqi_category(state["dust_val"])
    oled.text(f"TREND: {cat}", 0, 0)
    bar = min(120, int(state['dust_val'] * 2))
    oled.rect(0, 18, 122, 12, 1); oled.fill_rect(2, 20, bar, 8, 1)

def view_wifi_diag(t):
    wlan = network.WLAN(network.STA_IF); oled.text("WIFI DIAGNOSTIC", 0, 0)
    if wlan.isconnected():
        oled.text("RSSI: {} dBm".format(wlan.status('rssi')), 0, 10); oled.text("IP: " + wlan.ifconfig()[0], 0, 18)
    else: oled.text("DISCONNECTED", 0, 12)

def view_wifi_scan(t):
    oled.text("NEARBY NETWORKS", 0, 0)
    for i, net in enumerate(state["networks"][:3]):
        try: ssid = net[0].decode('utf-8')[:10]
        except: ssid = "???"
        oled.text(f"{i+1}.{ssid:<10} {net[3]}", 0, 8+(i*8))

# --- 7. Main Loop ---
VIEWS = [view_dashboard, view_weather, view_graph, view_wifi_diag, view_wifi_scan]
AUTO_VIEWS = [view_dashboard, view_weather, view_graph]

load_config()
wlan = network.WLAN(network.STA_IF); wlan.active(True); scan_wifi()
if state["config"]["ssid"]: wlan.connect(state["config"]["ssid"], state["config"]["pass"])

last_btn_state, btn_start, click_count, last_click = 0, 0, 0, 0
while True:
    now = utime.ticks_ms(); curr_btn = rp2.bootsel_button()
    
    if curr_btn != last_btn_state:
        if curr_btn == 1: btn_start = now
        else:
            dur = utime.ticks_diff(now, btn_start)
            if dur > 10000: run_setup_ap()
            elif dur > 5000: calibrate_sensor()
            elif dur > 20: click_count += 1; last_click = now
        last_btn_state = curr_btn

    if click_count > 0 and utime.ticks_diff(now, last_click) > 250:
        if click_count >= 2:
            state["auto_cycle"] = not state["auto_cycle"]; save_config(auto=state["auto_cycle"])
            state["msg_text"] = "AUTO ON" if state["auto_cycle"] else "AUTO OFF"; state["msg_timer"] = now + 1000
        else:
            state["auto_cycle"] = False # RAM-only override
            state["mode"] = (state["mode"] + 1) % len(VIEWS); state["last_mode_change"] = now
        click_count = 0

    # Read sensor
    dust_led.value(0); utime.sleep_us(280)
    v = (dust_adc.read_u16()/65535)*3.3; utime.sleep_us(40); dust_led.value(1)
    cur = max(0, (v - state["dust_offset"]) * 170)
    state["dust_history"].pop(0); state["dust_history"].append(cur)
    state["dust_val"] = sum(state["dust_history"][-15:])/15
    sync_data(); t = utime.localtime(); update_hardware(state["dust_val"])
    
    # Telemetry with Weather & Network Info
    if utime.ticks_diff(now, state.get("last_serial", 0)) >= 1000:
        cat_str = get_aqi_category(state["dust_val"])[0]
        ts = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5])
        rssi = wlan.status('rssi') if wlan.isconnected() else "DISC"
        telemetry = {
            "ts": ts, "dust": round(state["dust_val"], 2), "cat": cat_str, 
            "cal": round(state["dust_offset"], 4), "temp": state["weather_temp"], 
            "weather": state["weather_desc"], "rssi": rssi, "auto": state["auto_cycle"]
        }
        print(json.dumps(telemetry)); state["last_serial"] = now

    if state["auto_cycle"] and utime.ticks_diff(now, state["last_mode_change"]) > 10000:
        cur_v = VIEWS[state["mode"]]
        idx = (AUTO_VIEWS.index(cur_v) + 1) % len(AUTO_VIEWS) if cur_v in AUTO_VIEWS else 0
        state["mode"] = VIEWS.index(AUTO_VIEWS[idx])
        state["last_mode_change"] = now

    oled.fill(0)
    if now < state["msg_timer"]:
        oled.text(state["msg_text"].center(16), 0, 12)
    elif curr_btn and utime.ticks_diff(now, btn_start) > 10000:
        oled.text("RELEASE FOR", 0, 8); oled.text("SETUP PORTAL", 0, 18)
    elif curr_btn and utime.ticks_diff(now, btn_start) > 5000:
        oled.text("RELEASE TO", 0, 8); oled.text("CALIBRATE", 0, 18)
    else:
        VIEWS[state["mode"]](t)
    oled.show(); utime.sleep(0.05)
