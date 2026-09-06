#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Генератор VPN-подписки для Karing (iOS)
Собирает конфиги Trojan и Hysteria2 из открытых источников,
фильтрует, проверяет пинг, добавляет названия с флагами,
маскирует под Яндекс, исключает Украину, определяет "Неизвестно".
"""

import requests
import re
import json
import socket
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple

# ---------- НАСТРОЙКИ ----------
MAX_SERVERS = 150
MAX_PING_MS = 500
ONLY_PROTOCOLS = ('trojan', 'hysteria2')
EXCLUDED_COUNTRIES = {'Ukraine', 'Belarus'}  # можно добавить другие
SNI_MASK = 'yandex.ru'
ADGUARD_DNS = 'dns.adguard.com'

# ---------- ИСТОЧНИКИ (более 12 надёжных публичных агрегаторов) ----------
SOURCES = [
    'https://raw.githubusercontent.com/Argh94/Proxy-List/main/trojan/trojan.txt',
    'https://raw.githubusercontent.com/Argh94/Proxy-List/main/hysteria/hysteria.txt',
    'https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/trojan.txt',
    'https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/hysteria2.txt',
    'https://raw.githubusercontent.com/Subzio/subzio/main/HYSTERIA2.txt',
    'https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/1.txt',
    'https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/2.txt',
    'https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/3.txt',
    'https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/4.txt',
    'https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/5.txt',
    'https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/list/trojan.txt',
    'https://raw.githubusercontent.com/liMilCo/v2r/main/pro/trojan.txt',
    'https://raw.githubusercontent.com/Sage-77/V2ray-configs/main/trojan.txt',
    'https://raw.githubusercontent.com/Sage-77/V2ray-configs/main/hysteria2.txt',
]

# Словарь перевода стран (дополняйте)
COUNTRY_MAP = {
    'Russia': ('Россия', '🇷🇺'),
    'United States': ('США', '🇺🇸'),
    'Germany': ('Германия', '🇩🇪'),
    'France': ('Франция', '🇫🇷'),
    'United Kingdom': ('Великобритания', '🇬🇧'),
    'Netherlands': ('Нидерланды', '🇳🇱'),
    'Singapore': ('Сингапур', '🇸🇬'),
    'Japan': ('Япония', '🇯🇵'),
    'Canada': ('Канада', '🇨🇦'),
    'Australia': ('Австралия', '🇦🇺'),
    'India': ('Индия', '🇮🇳'),
    'Brazil': ('Бразилия', '🇧🇷'),
    'South Korea': ('Южная Корея', '🇰🇷'),
    'Italy': ('Италия', '🇮🇹'),
    'Spain': ('Испания', '🇪🇸'),
    'Switzerland': ('Швейцария', '🇨🇭'),
    'Poland': ('Польша', '🇵🇱'),
    'Sweden': ('Швеция', '🇸🇪'),
    'Norway': ('Норвегия', '🇳🇴'),
    'Finland': ('Финляндия', '🇫🇮'),
    'Denmark': ('Дания', '🇩🇰'),
    'Belgium': ('Бельгия', '🇧🇪'),
    'Austria': ('Австрия', '🇦🇹'),
    'Czechia': ('Чехия', '🇨🇿'),
    'Greece': ('Греция', '🇬🇷'),
    'Portugal': ('Португалия', '🇵🇹'),
    'Ireland': ('Ирландия', '🇮🇪'),
    'Luxembourg': ('Люксембург', '🇱🇺'),
    'Hungary': ('Венгрия', '🇭🇺'),
    'Romania': ('Румыния', '🇷🇴'),
    'Bulgaria': ('Болгария', '🇧🇬'),
    'Slovakia': ('Словакия', '🇸🇰'),
    'Croatia': ('Хорватия', '🇭🇷'),
    'Serbia': ('Сербия', '🇷🇸'),
    'Turkey': ('Турция', '🇹🇷'),
    'UAE': ('ОАЭ', '🇦🇪'),
    'Saudi Arabia': ('Саудовская Аравия', '🇸🇦'),
    'Israel': ('Израиль', '🇮🇱'),
    'South Africa': ('ЮАР', '🇿🇦'),
    'Mexico': ('Мексика', '🇲🇽'),
    'Argentina': ('Аргентина', '🇦🇷'),
    'Chile': ('Чили', '🇨🇱'),
    'Colombia': ('Колумбия', '🇨🇴'),
    'Peru': ('Перу', '🇵🇪'),
    'Venezuela': ('Венесуэла', '🇻🇪'),
}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------

def fetch_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        return resp.text if resp.status_code == 200 else None
    except:
        return None

def parse_uri(line: str) -> Optional[Dict]:
    line = line.strip()
    if not line:
        return None
    if not (line.startswith('trojan://') or line.startswith('hysteria2://')):
        return None
    parsed = urllib.parse.urlparse(line)
    proto = parsed.scheme.lower()
    if proto not in ONLY_PROTOCOLS:
        return None
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return None
    params = dict(urllib.parse.parse_qsl(parsed.query))
    if 'sni' not in params:
        params['sni'] = SNI_MASK
    if 'dns' not in params:
        params['dns'] = ADGUARD_DNS
    if proto == 'trojan' and parsed.password:
        params['password'] = parsed.password
    new_query = urllib.parse.urlencode(params)
    new_uri = urllib.parse.urlunparse((proto, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    return {
        'protocol': proto,
        'host': host,
        'port': port,
        'params': params,
        'uri': new_uri,
        'raw': line
    }

def get_geo_info(host: str) -> Tuple[str, str, str]:
    try:
        ip = socket.gethostbyname(host)
        resp = requests.get(f'http://ip-api.com/json/{ip}?fields=country,countryCode,city', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            country = data.get('country', 'Unknown')
            city = data.get('city', 'Unknown')
            country_code = data.get('countryCode', '').upper()
            flag = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in country_code) if country_code else '🏳️'
            return country, city, flag
    except:
        pass
    return 'Unknown', 'Unknown', '🏳️'

def translate_country(country: str) -> str:
    if country == 'Unknown':
        return 'Неизвестно'
    for eng, (rus, _) in COUNTRY_MAP.items():
        if country.lower() == eng.lower():
            return rus
    return country

def ping_host(host: str, port: int, timeout: float = 2.0) -> Optional[float]:
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = (time.time() - start) * 1000
            return elapsed
    except:
        return None

def is_server_working(server: Dict) -> bool:
    ping = ping_host(server['host'], server['port'])
    if ping is None or ping > MAX_PING_MS:
        return False
    server['ping'] = ping
    return True

# ---------- ОСНОВНАЯ ЛОГИКА ----------

def collect_servers() -> List[Dict]:
    all_uris = []
    print("Сбор конфигов из источников...")
    for url in SOURCES:
        text = fetch_text(url)
        if not text:
            continue
        # Попытка JSON
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        all_uris.append(item)
                    elif isinstance(item, dict) and 'url' in item:
                        all_uris.append(item['url'])
            elif isinstance(data, dict):
                for key in ['servers', 'configs', 'urls']:
                    if key in data and isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, str):
                                all_uris.append(item)
            continue
        except json.JSONDecodeError:
            pass
        # Иначе построчный разбор
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                all_uris.append(line)

    print(f"Найдено сырых записей: {len(all_uris)}")

    parsed = []
    seen = set()
    for uri in all_uris:
        config = parse_uri(uri)
        if not config:
            continue
        key = (config['host'], config['port'], config['protocol'])
        if key in seen:
            continue
        seen.add(key)
        country, city, flag = get_geo_info(config['host'])
        if country in EXCLUDED_COUNTRIES:
            continue
        config['country'] = country
        config['city'] = city
        config['flag'] = flag
        parsed.append(config)

    print(f"После парсинга и фильтрации стран: {len(parsed)}")

    print("Проверка доступности серверов...")
    working = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_server = {executor.submit(is_server_working, s): s for s in parsed}
        for future in as_completed(future_to_server):
            server = future_to_server[future]
            try:
                if future.result():
                    working.append(server)
            except:
                pass

    print(f"Рабочих серверов (пинг < {MAX_PING_MS} мс): {len(working)}")
    working.sort(key=lambda x: x.get('ping', float('inf')))
    selected = working[:MAX_SERVERS]
    print(f"Итоговое количество серверов в подписке: {len(selected)}")
    return selected

def generate_subscription(servers: List[Dict]) -> str:
    lines = []
    for srv in servers:
        country_rus = translate_country(srv['country'])
        city = srv['city']
        flag = srv['flag']
        ping = srv.get('ping', 0)
        name = f"{country_rus} {city} {flag}"
        lines.append(f"# {name} (пинг {int(ping)} мс)")
        lines.append(srv['uri'])
        lines.append("")
    return "\n".join(lines)

def main():
    print("Начинаем генерацию подписки...")
    servers = collect_servers()
    if not servers:
        print("Не найдено ни одного рабочего сервера. Проверьте источники.")
        return
    content = generate_subscription(servers)
    output_file = "subscription.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Подписка сохранена в {output_file}. Количество серверов: {len(servers)}")

if __name__ == "__main__":
    main()