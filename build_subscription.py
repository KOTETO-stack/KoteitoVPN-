#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import json
import subprocess
import concurrent.futures
import time
import os
import pycountry
import emoji

# ========== КОНФИГ ==========
MAX_PING = 500
MAX_SERVERS = 150
ALLOWED_PROTOCOLS = ["hy2", "trojan", "vless"]   # VLESS добавил для большего выбора
EXCLUDED_COUNTRIES = ["Ukraine", "Russia"]
TOR_BRIDGES_ENABLED = True
STATE_FILE = "source_state.json"
FAIL_THRESHOLD = 3

# ========== РАСШИРЕННЫЙ СПИСОК ИСТОЧНИКОВ (с прямыми ссылками на конфиги) ==========
SOURCES = [
    # Основные агрегаторы (где есть строки с протоколами)
    "https://raw.githubusercontent.com/iwantonline/FreeV2Ray/main/README.md",
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/README.md",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/README.md",
    "https://raw.githubusercontent.com/niizam/OX-Ray/main/README.md",
    "https://raw.githubusercontent.com/PojavLauncherTeam/vpn/refs/heads/main/vless.txt",
    "https://raw.githubusercontent.com/MAXIMUM-KA/VPN-Configs/main/vless.txt",
    "https://raw.githubusercontent.com/Epodon/FreeV2Ray/main/README.md",
    "https://raw.githubusercontent.com/alanbobs999/TopFreeProxies/master/README.md",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/README.md",
    "https://raw.githubusercontent.com/xiyaowong/freeV2ray/main/README.md",
    "https://raw.githubusercontent.com/AlexNet123/v2ray/main/README.md",
    "https://raw.githubusercontent.com/v2ray-links/v2ray-links/main/README.md",
    "https://raw.githubusercontent.com/freefq/free/main/README.md",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/README.md",
    "https://raw.githubusercontent.com/colatiger/v2ray-nodes/main/README.md",
    # Дополнительные источники с большим количеством конфигов
    "https://raw.githubusercontent.com/AirportR/FreeV2ray/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/v2fly/v2ray-examples/main/README.md",
    "https://raw.githubusercontent.com/XTLS/Xray-examples/main/README.md",
    # Прямые ссылки на текстовые файлы с конфигами (часто содержат Trojan)
    "https://raw.githubusercontent.com/ryanreese99/v2ray-configs/main/v2ray.txt",
    "https://raw.githubusercontent.com/zhuxindong/FreeV2Ray/main/v2ray",
]

def load_source_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_source_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def get_country_flag(country_name):
    try:
        country = pycountry.countries.get(name=country_name)
        if not country:
            country = pycountry.countries.get(alpha_2=country_name.upper())
        if country:
            return emoji.emojize(f":{country.alpha_2.lower()}:", language='alias')
    except:
        pass
    return "🏳️"

def parse_config_line(line):
    # Проверяем протокол
    if not any(line.startswith(p + "://") for p in ALLOWED_PROTOCOLS):
        return None
    proto = line.split("://")[0]
    
    # Пытаемся извлечь имя (#...)
    match = re.search(r'#(.+?)(?:\n|$)', line)
    if match:
        raw_name = match.group(1).strip()
        # Убираем эмодзи и лишние символы
        clean_name = re.sub(r'[^\w\s-]', '', raw_name).strip()
        if '-' in clean_name:
            parts = clean_name.split('-')
            country = parts[0].strip()
            city = parts[1].strip() if len(parts) > 1 else "Unknown"
        else:
            # Если нет дефиса, пробуем взять первые слова как страну
            words = clean_name.split()
            if words:
                country = words[0]
                city = " ".join(words[1:]) if len(words) > 1 else "Unknown"
            else:
                country = "Unknown"
                city = "Unknown"
    else:
        # Если нет #, пробуем извлечь страну из домена (грубо)
        match2 = re.search(r'://[^@]+@([^:/]+)', line)
        if match2:
            host = match2.group(1)
            # Пытаемся угадать страну по TLD (очень приблизительно)
            tld = host.split('.')[-1].upper()
            # Простой словарь TLD -> страна (можно расширить)
            tld_country = {
                "US": "United States", "GB": "United Kingdom", "DE": "Germany",
                "FR": "France", "JP": "Japan", "SG": "Singapore", "NL": "Netherlands",
                "CA": "Canada", "AU": "Australia", "IN": "India", "BR": "Brazil",
                "RU": "Russia", "UA": "Ukraine"
            }
            country = tld_country.get(tld, "Unknown")
            city = "Unknown"
        else:
            country = "Unknown"
            city = "Unknown"
    
    if country in EXCLUDED_COUNTRIES:
        return None
    
    flag = get_country_flag(country)
    return {
        "protocol": proto,
        "config": line,
        "country": country,
        "city": city,
        "flag": flag,
        "ping": None
    }

def fetch_lines_from_url(url):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            # Ищем строки, начинающиеся с разрешённых протоколов
            return [l.strip() for l in lines if l.strip() and any(l.startswith(p + "://") for p in ALLOWED_PROTOCOLS)]
    except:
        pass
    return []

def ping_server(config_line):
    try:
        match = re.search(r'://([^:/]+)(?::(\d+))?', config_line)
        if not match:
            return None
        host = match.group(1)
        port = match.group(2) or '80'
        start = time.time()
        # Используем curl для проверки доступности (просто TCP-соединение)
        subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{time_total}", f"http://{host}:{port}"],
            timeout=3, capture_output=True, text=True
        )
        ping_ms = (time.time() - start) * 1000
        return ping_ms if ping_ms < MAX_PING else None
    except:
        return None

def fetch_tor_bridges_dynamic():
    bridges = []
    static_bridges = [
        "socks5://192.168.1.100:9050 # Tor Bridge (локальная сеть)",
        "socks5://127.0.0.1:9050 # Tor Bridge (localhost)"
    ]
    if TOR_BRIDGES_ENABLED:
        bridges.extend(static_bridges)
    return bridges

def build_subscription():
    print("🚀 Запуск сборки подписки...")
    state = load_source_state()
    all_configs = []
    for url in SOURCES:
        if url in state and state[url] >= FAIL_THRESHOLD:
            print(f"⏭️ Источник {url} временно исключён (неудач: {state[url]})")
            continue
        lines = fetch_lines_from_url(url)
        if lines:
            print(f"✅ {url} -> {len(lines)} конфигов")
            all_configs.extend(lines)
            state[url] = 0
        else:
            state[url] = state.get(url, 0) + 1
            print(f"❌ {url} не дал конфигов (неудач: {state[url]})")
    save_source_state(state)
    print(f"📥 Всего получено сырых строк: {len(all_configs)}")

    parsed = []
    for line in all_configs:
        p = parse_config_line(line)
        if p:
            parsed.append(p)
    print(f"🔍 Отфильтровано по протоколам и странам: {len(parsed)} серверов")

    # Проверка пинга (многопоточная)
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_server = {executor.submit(ping_server, s['config']): s for s in parsed}
        for future in concurrent.futures.as_completed(future_to_server):
            server = future_to_server[future]
            ping = future.result()
            if ping:
                server['ping'] = round(ping, 1)

    # Удаляем недоступные (где ping None)
    available = [s for s in parsed if s['ping'] is not None]
    print(f"📶 После проверки пинга: {len(available)} серверов")
    available.sort(key=lambda x: x['ping'])
    selected = available[:MAX_SERVERS]

    # Добавляем Tor-мосты (если пинг < MAX_PING)
    tor_bridges = fetch_tor_bridges_dynamic()
    for tb in tor_bridges:
        match = re.search(r'socks5://([^:/]+)(?::(\d+))?', tb)
        if match:
            host = match.group(1)
            port = match.group(2) or '9050'
            ping = ping_server(f"http://{host}:{port}")
            if ping and ping < MAX_PING:
                selected.append({
                    "protocol": "socks5",
                    "config": tb,
                    "country": "Tor",
                    "city": "Bridge",
                    "flag": "🌐",
                    "ping": ping
                })

    # DNS-тест временно отключён (закомментирован)
    # print("🔍 Проверка DNS-утечек (может занять время)...")
    # dns_ok = []
    # for s in selected:
    #     if check_dns_leak_via_proxy(s['config']):
    #         dns_ok.append(s)
    #     else:
    #         print(f"⚠️ Сервер {s['country']} {s['city']} не прошёл тест DNS-утечки")
    # selected = dns_ok
    # print(f"✅ После DNS-теста осталось: {len(selected)} серверов")

    for s in selected:
        s['name'] = f"{s['country']} {s['city']} {s['flag']}"

    output_lines = []
    for s in selected:
        output_lines.append(f"# {s['name']} | Ping: {s['ping']}ms | {s['protocol']}")
        output_lines.append(s['config'])
    output_lines.append("\n# AdGuard DNS (блокировка рекламы)")
    output_lines.append("dns://94.140.14.14?name=adguard")
    output_lines.append("# Тест утечки DNS: https://www.dnsleaktest.com/")

    with open("subscription.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"✅ Готовая подписка содержит {len(selected)} серверов")
    print("📁 Файл subscription.txt создан")

if __name__ == "__main__":
    build_subscription()