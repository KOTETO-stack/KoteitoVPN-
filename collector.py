import asyncio
import aiohttp
import re
import random
from urllib.parse import urlparse, parse_qs, urlencode, quote
import emoji

# ---------- НАСТРОЙКИ ----------
SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
MAX_PING_MS = 500
EXCLUDED_COUNTRIES = {"UA"}
EXCLUDED_KEYWORDS = ["bns", "bnx"]
ALLOWED_PROTOCOLS = {"vless"}   # можно заменить на {"trojan", "hy2"} если нужно
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

REALITY_SETTINGS = {
    "security": "reality",
    "fp": "edge",
    "type": "xhttp",
    "mode": "auto",
    "path": "/",
    "encryption": "none",
}
# ------------------------------

def load_sources():
    with open(SOURCES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

async def fetch_configs(session, url):
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                text = await resp.text()
                # Ищем vless:// ссылки
                configs = re.findall(r'(vless://[^\s]+)', text)
                return configs
    except:
        return []
    return []

def parse_vless_url(url):
    if '#' in url:
        url = url.split('#')[0]
    if not url.startswith("vless://"):
        return None, None, None, {}
    raw = url[8:]
    if '@' not in raw:
        return None, None, None, {}
    uuid, rest = raw.split('@', 1)
    if '?' in rest:
        host_port, query_str = rest.split('?', 1)
    else:
        host_port, query_str = rest, ""
    if ':' in host_port:
        host, port = host_port.split(':', 1)
    else:
        host, port = host_port, None
    query_dict = parse_qs(query_str) if query_str else {}
    query_dict = {k: v[0] if v else "" for k, v in query_dict.items()}
    return uuid, host, port, query_dict

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

def apply_reality_protection(uuid, host, port, query):
    sni = random.choice(SNI_LIST)
    for key, value in REALITY_SETTINGS.items():
        if key not in query or not query[key]:
            query[key] = value
    if "sni" not in query:
        query["sni"] = sni
    if port:
        host_port = f"{host}:{port}"
    else:
        host_port = host
    query_str = urlencode(query, safe="%")
    return f"vless://{uuid}@{host_port}?{query_str}"

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

async def process_with_ping(configs):
    valid = []
    tasks_data = []
    for cfg in configs:
        uuid, host, port, query = parse_vless_url(cfg)
        if not uuid or not host:
            continue
        if any(kw in cfg.lower() for kw in EXCLUDED_KEYWORDS):
            continue
        country_name, country_code = parse_location(host)
        if country_code in EXCLUDED_COUNTRIES:
            continue
        tasks_data.append((cfg, uuid, host, port, query, country_name, country_code))
    if not tasks_data:
        return []
    ping_tasks = [tcp_ping(host, port or 443) for (_, _, host, port, _, _, _) in tasks_data]
    ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
    for (cfg, uuid, host, port, query, country_name, country_code), alive in zip(tasks_data, ping_results):
        if alive is True:
            protected_cfg = apply_reality_protection(uuid, host, port, query)
            name = generate_name(host, country_name, country_code)
            encoded_name = quote(name, safe='')
            final_url = f"{protected_cfg}#{encoded_name}"
            valid.append(final_url)
            if len(valid) >= MAX_SERVERS:
                break
    return valid

def process_without_ping(configs):
    valid = []
    for cfg in configs:
        uuid, host, port, query = parse_vless_url(cfg)
        if not uuid or not host:
            continue
        if any(kw in cfg.lower() for kw in EXCLUDED_KEYWORDS):
            continue
        country_name, country_code = parse_location(host)
        if country_code in EXCLUDED_COUNTRIES:
            continue
        protected_cfg = apply_reality_protection(uuid, host, port, query)
        name = generate_name(host, country_name, country_code)
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
    print(f"Найдено {len(unique)} уникальных vless-конфигов")
    print("🔄 Проверяем пинг (таймаут 5 сек)...")
    valid = await process_with_ping(unique)
    if not valid:
        print("⚠️ Ни один сервер не прошёл пинг. Переключаемся в режим БЕЗ пинга.")
        valid = process_without_ping(unique)
        print(f"✅ Собрано {len(valid)} серверов (без проверки пинга)")
    else:
        print(f"✅ Отобрано {len(valid)} серверов с пингом < {MAX_PING_MS} мс")
    save_subscription(valid)
    print(f"✅ Готово! Результат в {OUTPUT_FILE} (vless:// ссылки с фрагментами)")

if __name__ == "__main__":
    asyncio.run(main())