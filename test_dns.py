#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import subprocess
import sys

def check_dns_leak(config_line):
    """Проверяет DNS-утечку через прокси (аналогично основному скрипту)"""
    try:
        match = re.search(r'://([^:/]+)(?::(\d+))?', config_line)
        if not match:
            return False
        host = match.group(1)
        port = match.group(2) or '443'
        
        # Проверяем через socks5-hostname
        cmd = ["curl", "-s", "--socks5-hostname", f"{host}:{port}", 
               "https://1.1.1.1/dns-query?name=google.com", 
               "-o", "/dev/null", "-w", "%{http_code}"]
        result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)
        if result.stdout.strip() in ["200", "403"]:
            return True
        
        # Проверяем через HTTP прокси
        cmd = ["curl", "-s", "--proxy", f"http://{host}:{port}", 
               "https://1.1.1.1/dns-query?name=google.com", 
               "-o", "/dev/null", "-w", "%{http_code}"]
        result = subprocess.run(cmd, timeout=5, capture_output=True, text=True)
        if result.stdout.strip() in ["200", "403"]:
            return True
        
        return False
    except:
        return False

def main():
    print("🔍 Проверка DNS-утечек на серверах из subscription.txt")
    try:
        with open("subscription.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("❌ Файл subscription.txt не найден. Сначала запусти сборку.")
        sys.exit(1)

    # Извлекаем все строки, начинающиеся с протокола
    configs = []
    for line in lines:
        line = line.strip()
        if line.startswith(("vless://", "trojan://", "hy2://")):
            configs.append(line)

    if not configs:
        print("❌ В subscription.txt нет серверов.")
        sys.exit(1)

    print(f"📦 Найдено {len(configs)} серверов. Проверяем...")
    ok = 0
    fail = 0
    for i, cfg in enumerate(configs, 1):
        if check_dns_leak(cfg):
            ok += 1
            print(f"✅ {i}. DNS не утекает")
        else:
            fail += 1
            print(f"❌ {i}. DNS утекает (или проверка не удалась)")

    print(f"\n📊 Итог: {ok} OK, {fail} FAIL")

if __name__ == "__main__":
    main()