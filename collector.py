import asyncio
import aiohttp
import re
import random
import os
from urllib.parse import urlparse, parse_qs, urlencode, quote
from datetime import datetime
import emoji

# ---------- НАСТРОЙКИ ----------
SOURCES_FILE = "sources.txt"
PRIVATE_FILE = "private.txt"   # опционально – свои сервера
OUTPUT_FILE = "ready.txt"
MAX_SERVERS = 150
MAX_PING_MS = 500
EXCLUDED_COUNTRIES = {"UA"}
EXCLUDED_KEYWORDS = ["bns", "bnx"]
ALLOWED_PROTOCOLS = {"vless", "trojan", "hy2", "vmess"}  # все основные
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

# Общие настройки для Reality (для vless) и TLS (для остальных)
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
# ------------------------------

def load_sources():
    with open(SOURCES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def load_private():
    if os.path.exists(PRIVATE_FILE):
        with open(PRIVATE_FILE, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []

async def fetch_configs(session, url):
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                text = await resp.text()
                # Ищем все известные протоколы
                configs = re.findall(r'(vless://[^\s]+|trojan://[^\s]+|hy2://[^\s]+|vmess://[^\s]+)', text)
                return configs
    except:
        return []
    return []

def parse_proxy_url(url):
    """Универсальный парсер для vless, trojan, hy2, vmess"""
    if url.startswith("vless://"):
        return parse_vless(url)
    elif url.startswith("trojan://"):
        return parse_trojan(url)
    elif url.startswith("hy2://"):
        return parse_hy2(url)
    elif url.startswith("vmess://"):
        return parse_vmess(url)
    else:
        return None, None, None, {}

def parse_vless(url):
    # Аналогично предыдущей версии
    if '#' in url:
        url = url.split('#')[0]
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
    query = parse_qs(query_str) if query_str else {}
    query = {k: v[0] if v else "" for k, v in query.items()}
    return ("vless", uuid, host, port, query)

def parse_trojan(url):
    # trojan://password@host:port?params
    raw = url[9:]
    if '@' not in raw:
        return None, None, None, {}
    password, rest = raw.split('@', 1)
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
    return ("trojan", password, host, port, query)

def parse_hy2(url):
    # hy2://host:port?params
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
    return ("hy2", None, host, port, query)

def parse_vmess(url):
    # vmess://base64
    try:
        import base64
        raw = url[8:]
        # Декодируем base64
        decoded = base64.b64decode(raw).decode('utf-8')
        import json
        data = json.loads(decoded)
        host = data.get('add', '')
        port = str(data.get('port', ''))
        uuid = data.get('id', '')
        query = {
            "security": data.get('scy', 'auto'),
            "fp": "chrome",
            "encryption": "none",
        }
        return ("vmess", uuid, host, port, query)
    except:
        return None, None, None, {}

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

def check_expiry(query):
    if "expiry" in query:
        try:
            expiry = int(query["expiry"])
            if expiry < int(datetime.now().timestamp()):
                return False
        except:
            pass
    return True

def apply_protection(proto, secret, host, port, query):
    # Добавляем защитные параметры в зависимости от протокола
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
    # Если нет порта – ставим 443
    if not port:
        port = "443"
    if ':' in host:
        host_port = f"[{host}]:{port}"
    else:
        host_port = f"{host}:{port}"
    # Собираем URL
    query_str = urlencode(query, safe="%")
    if proto == "vless":
        return f"vless://{secret}@{host_port}?{query_str}"
    elif proto == "trojan":
        return f"trojan://{secret}@{host_port}?{query_str}"
    elif proto == "hy2":
        return f"hy2://{host_port}?{query_str}"
    elif proto == "vmess":
        # Для vmess проще оставить как есть, но мы уже добавили параметры
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

async def process_configs(configs, private=False):
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
        if not check_expiry(query):
            continue
        tasks_data.append((cfg, proto, secret, host, port, query, country_name, country_code))
    # Проверка пинга
    if tasks_data:
        ping_tasks = [tcp_ping(host, port or 443) for (_, _, _, host, port, _, _, _) in tasks_data]
        ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
        for (cfg, proto, secret, host, port, query, country_name, country_code), alive in zip(tasks_data, ping_results):
            if alive is True or private:  # приватные добавляем всегда (если не хотим проверять)
                name = generate_name(host, country_name, country_code)
                # Добавляем название как remark
                query["remark"] = name
                protected_cfg = apply_protection(proto, secret, host, port, query)
                if protected_cfg:
                    valid.append(protected_cfg)
                if len(valid) >= MAX_SERVERS:
                    break
    return valid

async def main():
    # Загружаем приватные сервера (если есть)
    private = load_private()
    if private:
        print(f"🔒 Загружено {len(private)} приватных серверов")
    # Загружаем публичные источники
    sources = load_sources()
    print(f"📡 Загружаем конфиги из {len(sources)} источников...")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_configs(session, url) for url in sources]
        results = await asyncio.gather(*tasks)
    all_configs = []
    for r in results:
        all_configs.extend(r)
    unique = list(set(all_configs))
    print(f"Найдено {len(unique)} уникальных публичных конфигов")
    # Сначала обрабатываем приватные (они приоритетнее)
    valid = []
    if private:
        private_valid = await process_configs(private, private=True)
        valid.extend(private_valid)
        print(f"✅ Добавлено {len(private_valid)} приватных серверов")
    # Потом публичные
    if len(valid) < MAX_SERVERS:
        print("🔄 Проверяем публичные сервера (пинг)...")
        public_valid = await process_configs(unique, private=False)
        # Если публичных не прошло пинг – берем без пинга (fallback)
        if not public_valid:
            print("⚠️ Ни один публичный сервер не прошёл пинг. Переключаемся в режим БЕЗ пинга.")
            # Повторно собираем без пинга (упрощённо)
            public_valid = await process_configs(unique, private=True)  # private=True отключает пинг
            print(f"✅ Собрано {len(public_valid)} публичных серверов (без проверки пинга)")
        else:
            print(f"✅ Отобрано {len(public_valid)} публичных серверов с пингом < {MAX_PING_MS} мс")
        # Добавляем публичные, пока не наберём 150
        for item in public_valid:
            if len(valid) >= MAX_SERVERS:
                break
            valid.append(item)
    # Сохраняем
    content = "\n".join(valid)
    with open(OUTPUT_FILE, "w") as f:
        f.write(content)
    print(f"✅ Готово! Результат в {OUTPUT_FILE} (всего {len(valid)} серверов)")

if __name__ == "__main__":
    asyncio.run(main())