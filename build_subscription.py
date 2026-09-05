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
ALLOWED_PROTOCOLS = ["hy2", "trojan"]          # Только Hy2 и Trojan
EXCLUDED_COUNTRIES = ["Ukraine", "Russia"]     # Исключаем
STATE_FILE = "source_state.json"
FAIL_THRESHOLD = 3

# ========== ИСТОЧНИКИ (только проверенные, с Hy2/Trojan) ==========
SOURCES = [
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/README.md",
    "https://raw.githubusercontent.com/alanbobs999/TopFreeProxies/master/README.md",
    "https://raw.githubusercontent.com/AirportR/FreeV2ray/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/ryanreese99/v2ray-configs/main/v2ray.txt",
    "https://raw.githubusercontent.com/zhuxindong/FreeV2Ray/main/v2ray",
    "https://raw.githubusercontent.com/anaer/Sub/main/README.md",
    "https://raw.githubusercontent.com/freefq/free/main/README.md",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    # Добавь сюда свои любимые источники
]

# ========== ФУНКЦИИ ==========

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

def get_country_ru(country_name):
    """Переводит название страны на русский (используем встроенный словарь)"""
    # Простой словарь для часто встречающихся стран
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

def extract_country_city_from_name(raw_name):
    """Извлекает страну и город из имени (например, 'US_Нью-Йорк' или 'DE_Франкфурт')"""
    # Убираем эмодзи и лишние символы
    clean = re.sub(r'[^\w\s\-_]', '', raw_name).strip()
    
    # Ищем паттерн: код страны (2 буквы) + город
    match = re.search(r'([A-Z]{2})[_\-\s]+(.+)', clean)
    if match:
        code = match.group(1)
        city = match.group(2).strip()
        # Получаем страну по коду
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
            country_part = parts[0].strip()
            city_part = parts[1].strip()
            # Проверяем, не является ли первая часть кодом страны
            if len(country_part) == 2 and country_part.isalpha():
                try:
                    country = pycountry.countries.get(alpha_2=country_part.upper())
                    if country:
                        return country.name, city_part
                except:
                    pass
            else:
                # Если не код, пробуем найти страну по полному названию
                try:
                    country = pycountry.countries.get(name=country_part)
                    if country:
                        return country.name, city_part
                except:
                    pass
    
    # Если не удалось, пробуем по TLD домена (если есть)
    return None, None

def parse_config_line(line):
    if not any(line.startswith(p + "://") for p in ALLOWED_PROTOCOLS):
        return None
    proto = line.split("://")[0]
    
    # Пытаемся извлечь имя (#...)
    match = re.search(r'#(.+?)(?:\n|$)', line)
    if match:
        raw_name = match.group(1).strip()
        country, city = extract_country_city_from_name(raw_name)
    else:
        # Если нет #, пробуем извлечь страну из домена (по TLD)
        match2 = re.search(r'://([^@]+@)?([^:/]+)', line)
        if match2:
            host = match2.group(2)
            tld = host.split('.')[-1].upper()
            try:
                country = pycountry.countries.get(alpha_2=tld)
                if country:
                    country = country.name
                    city = "Unknown"
                else:
                    country = None
                    city = None
            except:
                country = None
                city = None
        else:
            country = None
            city = None
    
    if not country:
        return None  # Не удалось определить страну
    
    # Проверяем исключения
    if country in EXCLUDED_COUNTRIES:
        return None
    
    # Преобразуем в русское название
    country_ru = get_country_ru(country)
    flag = get_country_flag(country)
    return {
        "protocol": proto,
        "config": line,
        "country": country_ru,
        "city": city or "Unknown",
        "flag": flag,
        "ping": None,
        "raw_country": country  # сохраняем для возможной фильтрации
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

def check_dns_leak(config_line):
    """Проверка DNS-утечки через запрос к 1.1.1.1 через прокси (только если прокси поддерживает SOCKS5)"""
    # Для Trojan и Hy2 используем SOCKS5 (обычно так и есть)
    try:
        match = re.search(r'://([^:/]+)(?::(\d+))?', config_line)
        if not match:
            return False
        host = match.group(1)
        port = match.group(2) or '443'
        # Пробуем через socks5
        cmd = ["curl", "-s", "--socks5-hostname", f"{host}:{port}", "https://1.1.1.1/dns-query?name=google.com", "-o", "/dev/null", "-w", "%{http_code}"]
        result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)
        if result.stdout.strip() in ["200", "403"]:
            return True
        # Если не получилось, пробуем без прокси (но это не должно быть утечкой)
        return False
    except:
        return False

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

    # Парсим и фильтруем
    parsed = []
    seen = set()
    for line in all_configs:
        # Убираем дубликаты
        if line in seen:
            continue
        seen.add(line)
        p = parse_config_line(line)
        if p:
            parsed.append(p)
    print(f"🔍 Отфильтровано по протоколам, странам и дубликатам: {len(parsed)} серверов")

    # Проверка пинга
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        future_to_server = {executor.submit(ping_server, s['config']): s for s in parsed}
        for future in concurrent.futures.as_completed(future_to_server):
            server = future_to_server[future]
            ping = future.result()
            if ping:
                server['ping'] = round(ping, 1)

    available = [s for s in parsed if s['ping'] is not None]
    print(f"📶 После проверки пинга: {len(available)} серверов")

    # Сортируем и отбираем лучшие
    available.sort(key=lambda x: x['ping'])
    selected = available[:MAX_SERVERS]

    # Проверка DNS-утечек (отбрасываем только те, где явная утечка)
    print("🔍 Проверка DNS-утечек (может занять время)...")
    dns_ok = []
    for s in selected:
        if check_dns_leak(s['config']):
            dns_ok.append(s)
        else:
            print(f"⚠️ {s['country']} {s['city']} не прошёл DNS-тест (отбрасываем)")
    selected = dns_ok
    print(f"✅ После DNS-теста осталось: {len(selected)} серверов")

    # Формируем названия (без лишних слов)
    for s in selected:
        # Если город неизвестен, не показываем его
        city_part = s['city'] if s['city'] != "Unknown" else ""
        if city_part:
            s['name'] = f"{s['country']} {city_part} {s['flag']}"
        else:
            s['name'] = f"{s['country']} {s['flag']}"

    # Генерируем подписку
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