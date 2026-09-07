import asyncio
import aiohttp
import re
import random
from urllib.parse import parse_qs, urlencode, quote
import emoji

SOURCES_FILE = "sources.txt"
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
EXCLUDED_COUNTRIES = {"UA"}
EXCLUDED_KEYWORDS = ["bns", "bnx"]
ALLOWED_PROTOCOLS = {"vless", "trojan", "hy2", "vmess"}
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
                configs = re.findall(r'(vless://[^\s]+|trojan://[^\s]+|hy2://[^\s]+|vmess://[^\s]+)', text)
                return configs
    except:
        return []
    return []

def parse_proxy_url(url):
    if url.startswith("vless://"):
        return parse_vless(url)
    elif url.startswith("trojan://"):
        return parse_trojan(url)
    elif url.startswith("hy2://"):
        return parse_hy2(url)
    elif url.startswith("vmess://"):
        return parse_vmess(url)
    else:
        return None, None, None, None, {}

def parse_vless(url):
    if '#' in url:
        url = url.split('#')[0]
    raw = url[8:]
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
    raw = url[9:]
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

def parse_hy2(url):
    if '#' in url:
        url = url.split('#')[0]
    raw = url[5:]
    if '?' in raw:
        host_port, query_str = raw.split('?', 1)
    else:
        host_port, query_str = raw, ""
    if ':' in host_port:
        host, port = host_port.split(':', 1)
    else:
        host, port = host_port, None
    query = parse_qs(query_str) if query_str else {}
    query = {k: v[0] if v else "" for k, v in query.items()}
    return "hy2", None, host, port, query

def parse_vmess(url):
    try:
        import base64 as b64
        import json
        raw = url[8:]
        decoded = b64.b64decode(raw).decode('utf-8')
        data = json.loads(decoded)
        host = data.get('add', '')
        port = str(data.get('port', ''))
        secret = data.get('id', '')
        query = {
            "security": data.get('scy', 'auto'),
            "fp": "chrome",
            "encryption": "none",
        }
        return "vmess", secret, host, port, query
    except:
        return None, None, None, None, {}

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
    elif proto in ("trojan", "hy2", "vmess"):
        for key, value in TLS_SETTINGS.items():
            if key not in query or not query[key]:
                query[key] = value
        if "sni" not in query:
            query["sni"] = sni
    if not port:
        port = "443"
    if ':' in host:
        host_port = f"[{host}]:{port}"
    else:
        host_port = f"{host}:{port}"
    query_str = urlencode(query, safe="%")
    if proto == "vless":
        return f"vless://{secret}@{host_port}?{query_str}"
    elif proto == "trojan":
        return f"trojan://{secret}@{host_port}?{query_str}"
    elif proto == "hy2":
        return f"hy2://{host_port}?{query_str}"
    elif proto == "vmess":
        return f"vmess://{secret}@{host_port}?{query_str}"
    return None

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
        tasks_data.append((proto, secret, host, port, query, country_name, country_code))
    if not tasks_data:
        return []
    if not skip_ping:
        ping_tasks = [tcp_ping(host, port or 443) for (_, _, host, port, _, _, _) in tasks_data]
        ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
    else:
        ping_results = [True] * len(tasks_data)
    for (proto, secret, host, port, query, country_name, country_code), alive in zip(tasks_data, ping_results):
        if alive is True:
            name = generate_name(host, country_name, country_code)
            protected_cfg = apply_protection(proto, secret, host, port, query)
            if protected_cfg:
                # Добавляем название как фрагмент # и параметр remark для совместимости
                encoded_name = quote(name, safe='')
                final_url = f"{protected_cfg}&remark={encoded_name}#{encoded_name}"
                valid.append(final_url)
            if len(valid) >= MAX_SERVERS:
                break
    return valid

def save_subscription(valid):
    content = "\n".join(valid)
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
        print(f"✅ Отобрано {len(valid)} серверов с пингом < 500 мс")
    save_subscription(valid)
    print(f"✅ Готово! Результат в {OUTPUT_FILE} (ссылки с # и remark)")

if __name__ == "__main__":
    asyncio.run(main())