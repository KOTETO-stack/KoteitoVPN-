import asyncio
import aiohttp
import re
import random
from urllib.parse import parse_qs, urlencode, quote
import emoji

SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
MAX_PING_MS = 500
EXCLUDED_COUNTRIES = {"UA"}
EXCLUDED_KEYWORDS = ["bns", "bnx"]
ALLOWED_PROTOCOLS = {"vless", "trojan"}  # только эти два, они наиболее стабильны
PING_TIMEOUT = 5.0

SNI_LIST = [
    "cdn7-54.yahoo.com",
    "www.yandex.ru",
    "www.google.com",
    "www.microsoft.com",
    "www.apple.com",
    "www.amazon.com",
    "www.cloudflare.com",
]

# Настройки для vless (Reality)
REALITY_SETTINGS = {
    "security": "reality",
    "fp": "edge",
    "type": "xhttp",
    "mode": "auto",
    "path": "/",
    "encryption": "none",
}

# Настройки для trojan (TLS)
TLS_SETTINGS = {
    "security": "tls",
    "fp": "chrome",
    "encryption": "none",
}

def load_sources():
    with open(SOURCES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

async def fetch_configs(session, url):
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                text = await resp.text()
                # Ищем vless и trojan
                configs = re.findall(r'(vless://[^\s]+|trojan://[^\s]+)', text)
                return configs
    except:
        return []
    return []

def parse_proxy_url(url):
    """Универсальный парсер для vless и trojan, всегда возвращает 5 значений"""
    if url.startswith("vless://"):
        return parse_vless(url)
    elif url.startswith("trojan://"):
        return parse_trojan(url)
    else:
        return None, None, None, None, {}

def parse_vless(url):
    if '#' in url:
        url = url.split('#')[0]
    raw = url[8:]  # убираем vless://
    if '@' not in raw:
        return None, None, None, None, {}
    secret, rest = raw.split('@', 1)
    if '?' in rest:
        host_port, query_str = rest.split('?', 1)
    else:
        host_port, query_str = rest, ""
    if ':' in host_port:
        host, port = host_port.split(':', 1)
    else:
        host, port = host_port, None
    query = parse_qs(query_str) if query_str else {}
    query = {k: v[0] if v else "" for k, v in query.items()}
    return "vless", secret, host, port, query

def parse_trojan(url):
    if '#' in url:
        url = url.split('#')[0]
    raw = url[9:]  # убираем trojan://
    if '@' not in raw:
        return None, None, None, None, {}
    secret, rest = raw.split('@', 1)
    if '?' in rest:
        host_port, query_str = rest.split('?', 1)
    else:
        host_port, query_str = rest, ""
    if ':' in host_port:
        host, port = host_port.split(':', 1)
    else:
        host, port = host_port, None
    query = parse_qs(query_str) if query_str else {}
    query = {k: v[0] if v else "" for k, v in query.items()}
    return "trojan", secret, host, port, query

def parse_location(host):
    country_map = {
        "ru": "Россия", "us": "США", "de": "Германия", "fr": "Франция",
        "nl": "Нидерланды", "sg": "Сингапур", "jp": "Япония", "gb": "Великобритания",
        "ca": "Канада", "au": "Австралия", "it": "Италия", "es": "Испания",
        "br": "Бразилия", "in": "Индия", "kr": "Южная Корея", "tr": "Турция",
        "ae": "ОАЭ", "sa": "Саудовская Аравия", "se": "Швеция", "ch": "Швейцария"
    }
    match = re.search(r'\.([a-z]{2})(?:\.|$)', host)
    if match:
        code = match.group(1).upper()
        if code in country_map:
            return country_map[code], code
    return "Неизвестно", ""

def generate_name(host, country_name, country_code):
    city_match = re.search(r'[.-]([a-z]{3,4})(?:[.-]|$)', host)
    city = city_match.group(1).upper() if city_match else ""
    flag = emoji.emojize(f":{country_code.lower()}:", language='alias') if country_code else "🏳️"
    return f"{country_name} {city} {flag}".strip()

def apply_protection(proto, secret, host, port, query):
    sni = random.choice(SNI_LIST)
    if proto == "vless":
        for key, value in REALITY_SETTINGS.items():
            if key not in query or not query[key]:
                query[key] = value
        if "sni" not in query:
            query["sni"] = sni
    elif proto == "trojan":
        for key, value in TLS_SETTINGS.items():
            if key not in query or not query[key]:
                query[key] = value
        if "sni" not in query:
            query["sni"] = sni
    # Если порт не указан, ставим 443
    if not port:
        port = "443"
    if ':' in host:
        host_port = f"[{host}]:{port}"
    else:
        host_port = f"{host}:{port}"
    query_str = urlencode(query, safe="%")
    return f"{proto}://{secret}@{host_port}?{query_str}"

async def tcp_ping(host, port, timeout=PING_TIMEOUT):
    try:
        if not port:
            port = 443
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, int(port)),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

async def process_configs(configs, skip_ping=False):
    valid = []
    tasks_data = []
    for cfg in configs:
        proto, secret, host, port, query = parse_proxy_url(cfg)
        if not proto or not host:
            continue
        if any(kw in cfg.lower() for kw in EXCLUDED_KEYWORDS):
            continue
        country_name, country_code = parse_location(host)
        if country_code in EXCLUDED_COUNTRIES:
            continue
        tasks_data.append((cfg, proto, secret, host, port, query, country_name, country_code))
    if not tasks_data:
        return []
    # Проверка пинга (если не skip_ping)
    if not skip_ping:
        ping_tasks = [tcp_ping(host, port or 443) for (_, _, _, host, port, _, _, _) in tasks_data]
        ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
    else:
        ping_results = [True] * len(tasks_data)
    for (cfg, proto, secret, host, port, query, country_name, country_code), alive in zip(tasks_data, ping_results):
        if alive is True:
            name = generate_name(host, country_name, country_code)
            protected_cfg = apply_protection(proto, secret, host, port, query)
            encoded_name = quote(name, safe='')
            final_url = f"{protected_cfg}#{encoded_name}"
            valid.append(final_url)
            if len(valid) >= MAX_SERVERS:
                break
    return valid

def save_subscription(urls):
    content = "\n".join(urls)
    with open(OUTPUT_FILE, "w") as f:
        f.write(content)

async def main():
    sources = load_sources()
    print(f"📡 Загружаем конфиги из {len(sources)} источников...")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_configs(session, url) for url in sources]
        results = await asyncio.gather(*tasks)
    all_configs = []
    for r in results:
        all_configs.extend(r)
    unique = list(set(all_configs))
    print(f"Найдено {len(unique)} уникальных конфигов")
    print("🔄 Проверяем пинг (таймаут 5 сек)...")
    valid = await process_configs(unique, skip_ping=False)
    if not valid:
        print("⚠️ Ни один сервер не прошёл пинг. Переключаемся в режим БЕЗ пинга.")
        valid = await process_configs(unique, skip_ping=True)
        print(f"✅ Собрано {len(valid)} серверов (без проверки пинга)")
    else:
        print(f"✅ Отобрано {len(valid)} серверов с пингом < {MAX_PING_MS} мс")
    save_subscription(valid)
    print(f"✅ Готово! Результат в {OUTPUT_FILE} (vless/trojan с #)")

if __name__ == "__main__":
    asyncio.run(main())