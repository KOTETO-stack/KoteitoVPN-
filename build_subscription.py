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
ALLOWED_PROTOCOLS = ["vless", "trojan", "hy2"]   # Добавил VLESS
EXCLUDED_COUNTRIES = ["Ukraine", "Russia"]
STATE_FILE = "source_state.json"
FAIL_THRESHOLD = 3

# ========== МНОГО ИСТОЧНИКОВ ==========
SOURCES = [
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
    "https://raw.githubusercontent.com/ryanreese99/v2ray-configs/main/v2ray.txt",
    "https://raw.githubusercontent.com/zhuxindong/FreeV2Ray/main/v2ray",
    "https://raw.githubusercontent.com/AirportR/FreeV2ray/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/v2fly/v2ray-examples/main/README.md",
    "https://raw.githubusercontent.com/XTLS/Xray-examples/main/README.md",
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
    if country_name == "Unknown":
        return "🏳️"
    try:
        country = pycountry.countries.get(name=country_name)
        if not country:
            country = pycountry.countries.get(alpha_2=country_name.upper())
        if country:
            return emoji.emojize(f":{country.alpha_2.lower()}:", language='alias')
    except:
        pass
    return "🏳️"

def get_country_ru(country_name):
    if country_name == "Unknown":
        return "Unknown"
    ru_names = {
        "United States": "США",
        "United Kingdom": "Великобритания",
        "Germany": "Германия",
        "France": "Франция",
        "Japan": "Япония",
        "Singapore": "Сингапур",
        "Netherlands": "Нидерланды",
        "Canada": "Канада",
        "Australia": "Австралия",
        "India": "Индия",
        "Brazil": "Бразилия",
        "Italy": "Италия",
        "Spain": "Испания",
        "Turkey": "Турция",
        "Poland": "Польша",
        "South Korea": "Южная Корея",
        "Taiwan": "Тайвань",
        "Hong Kong": "Гонконг",
        "Macao": "Макао",
        "Switzerland": "Швейцария",
        "Austria": "Австрия",
        "Belgium": "Бельгия",
        "Sweden": "Швеция",
        "Norway": "Норвегия",
        "Denmark": "Дания",
        "Finland": "Финляндия",
        "Israel": "Израиль",
        "Malaysia": "Малайзия",
        "Vietnam": "Вьетнам",
        "Philippines": "Филиппины",
        "New Zealand": "Новая Зеландия"
    }
    return ru_names.get(country_name, country_name)

def extract_country_city(raw_name):
    """Пытается извлечь страну и город, возвращает (страна, город) или (None, None)"""
    # Удаляем все эмодзи (включая флаги)
    clean = re.sub(r'[^\w\s\-_]', '', raw_name).strip()
    # Ищем двухбуквенный код в начале
    match = re.search(r'^([A-Z]{2})[_\-\s]+(.+)', clean)
    if match:
        code = match.group(1)
        city = match.group(2).strip()
        try:
            country = pycountry.countries.get(alpha_2=code)
            if country:
                return country.name, city
        except:
            pass
    # Если есть дефис, пробуем разделить
    if '-' in clean:
        parts = clean.split('-')
        if len(parts) >= 2:
            first = parts[0].strip()
            second = parts[1].strip()
            if len(first) == 2 and first.isalpha():
                try:
                    country = pycountry.countries.get(alpha_2=first.upper())
                    if country:
                        return country.name, second
                except:
                    pass
            else:
                try:
                    country = pycountry.countries.get(name=first)
                    if country:
                        return country.name, second
                except:
                    pass
    # Если не удалось, пробуем взять первое слово как код страны
    words = clean.split()
    if words and len(words[0]) == 2 and words[0].isalpha():
        try:
            country = pycountry.countries.get(alpha_2=words[0].upper())
            if country:
                city = " ".join(words[1:]) if len(words) > 1 else "Unknown"
                return country.name, city
        except:
            pass
    return None, None

def parse_config_line(line):
    if not any(line.startswith(p + "://") for p in ALLOWED_PROTOCOLS):
        return None
    proto = line.split("://")[0]
    
    # Ищем имя #...
    match = re.search(r'#(.+?)(?:\n|$)', line)
    raw_name = match.group(1).strip() if match else ""
    
    country = None
    city = None
    if raw_name:
        country, city = extract_country_city(raw_name)
    
    # Если не удалось определить страну, пробуем по TLD домена (из конфига)
    if not country:
        match2 = re.search(r'://([^@]+@)?([^:/]+)', line)
        if match2:
            host = match2.group(2)
            tld = host.split('.')[-1].upper()
            try:
                country_obj = pycountry.countries.get(alpha_2=tld)
                if country_obj:
                    country = country_obj.name
                    city = "Unknown"
            except:
                pass
    
    # Если всё равно не определили, ставим Unknown
    if not country:
        country = "Unknown"
        city = "Unknown"
    
    # Исключаем нежелательные страны
    if country in EXCLUDED_COUNTRIES:
        return None
    
    country_ru = get_country_ru(country)
    flag = get_country_flag(country)
    return {
        "protocol": proto,
        "config": line,
        "country": country_ru,
        "city": city or "Unknown",
        "flag": flag,
        "ping": None
    }

def fetch_lines_from_url(url):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
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
        subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{time_total}", f"http://{host}:{port}"],
            timeout=3, capture_output=True, text=True
        )
        ping_ms = (time.time() - start) * 1000
        return ping_ms if ping_ms < MAX_PING else None
    except:
        return None

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

    # Считаем протоколы для отладки
    proto_counts = {}
    for line in all_configs:
        proto = line.split("://")[0]
        proto_counts[proto] = proto_counts.get(proto, 0) + 1
    print(f"📊 Протоколы: {proto_counts}")

    # Парсим и удаляем дубликаты
    seen = set()
    parsed = []
    for line in all_configs:
        if line in seen:
            continue
        seen.add(line)
        p = parse_config_line(line)
        if p:
            parsed.append(p)
    print(f"🔍 После парсинга и фильтрации: {len(parsed)} серверов")

    if not parsed:
        print("⚠️ Нет ни одного сервера после парсинга. Проверьте имена в источниках.")
        # Для отладки выведем первые 3 строки (но в логах Actions это будет видно)
        for i, line in enumerate(all_configs[:3]):
            print(f"Пример строки {i+1}: {line[:100]}...")
        return

    # Проверка пинга
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_server = {executor.submit(ping_server, s['config']): s for s in parsed}
        for future in concurrent.futures.as_completed(future_to_server):
            server = future_to_server[future]
            ping = future.result()
            if ping:
                server['ping'] = round(ping, 1)

    available = [s for s in parsed if s['ping'] is not None]
    print(f"📶 После пинга: {len(available)} серверов")
    available.sort(key=lambda x: x['ping'])
    selected = available[:MAX_SERVERS]

    # Формируем названия
    for s in selected:
        city_part = s['city'] if s['city'] != "Unknown" else ""
        if city_part:
            s['name'] = f"{s['country']} {city_part} {s['flag']}"
        else:
            s['name'] = f"{s['country']} {s['flag']}"

    # Запись подписки
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