#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BNS (Блокировка нежелательных сайтов) тест
Проверяет, блокирует ли подписка доступ к нежелательным ресурсам
и нет ли утечки DNS.
"""

import subprocess
import re
import time

# Список доменов для проверки
TEST_DOMAINS = [
    "google.com",           # Должен быть доступен
    "youtube.com",          # Должен быть доступен
    "telegram.org",         # Должен быть доступен
    "tiktok.com",           # Должен быть доступен
    "whatsapp.com",         # Должен быть доступен
    "wechat.com",           # Должен быть доступен
    "facebook.com",         # Может быть заблокирован (проверяем)
    "twitter.com",          # Может быть заблокирован (проверяем)
    "instagram.com",        # Может быть заблокирован (проверяем)
    "dnsleaktest.com",      # Для проверки утечки DNS
]

# Сомнительные домены (должны блокироваться)
BLOCKED_DOMAINS = [
    "bns.com",
    "bns.ru",
    "bns.org",
    "badware.com",
    "malware-site.com",
]

def test_dns_leak():
    """Проверяет утечку DNS через стандартные DNS-серверы"""
    print("🔍 Проверка DNS-утечки...")
    
    # Проверяем, какой DNS используется
    result = subprocess.run(["nslookup", "google.com"], capture_output=True, text=True)
    if "Server:" in result.stdout:
        server_line = [line for line in result.stdout.split('\n') if "Server:" in line]
        print(f"🌐 Текущий DNS: {server_line[0].strip()}")
    
    # Проверяем через curl
    try:
        cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://1.1.1.1/dns-query?name=google.com"]
        result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)
        if result.stdout.strip() in ["200", "403"]:
            print("✅ DNS через Cloudflare работает (1.1.1.1)")
        else:
            print("⚠️ DNS через Cloudflare не отвечает")
    except:
        print("❌ Ошибка при проверке DNS через Cloudflare")

def test_domain_access(url):
    """Проверяет доступность домена"""
    try:
        cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url]
        result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return None

def test_blocked_domains():
    """Проверяет, блокируются ли сомнительные домены"""
    print("\n🚫 Проверка блокировки сомнительных доменов:")
    for domain in BLOCKED_DOMAINS:
        url = f"https://{domain}"
        status = test_domain_access(url)
        if status and status not in ["000", "001"]:
            print(f"❌ Домен {domain} ДОСТУПЕН (код {status}) - нужно добавить в чёрный список!")
        else:
            print(f"✅ Домен {domain} заблокирован (недоступен)")

def test_good_domains():
    """Проверяет, доступны ли легальные сервисы"""
    print("\n🌍 Проверка доступности легальных сервисов:")
    for domain in TEST_DOMAINS:
        url = f"https://{domain}"
        status = test_domain_access(url)
        if status in ["200", "301", "302", "403"]:
            print(f"✅ {domain} доступен (код {status})")
        else:
            print(f"⚠️ {domain} не отвечает (код {status})")

def main():
    print("=" * 60)
    print("🛡️ BNS Тест - проверка утечки DNS и блокировки")
    print("=" * 60)
    
    test_dns_leak()
    test_good_domains()
    test_blocked_domains()
    
    print("\n" + "=" * 60)
    print("📊 Рекомендации:")
    print("1. Если DNS отличается от 1.1.1.1 или 94.140.14.14 - есть утечка")
    print("2. Если сомнительные домены доступны - добавьте их в чёрный список")
    print("3. Проверьте, что AdGuard DNS (94.140.14.14) работает")
    print("=" * 60)

if __name__ == "__main__":
    main()