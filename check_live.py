# -*- coding: utf-8 -*-
"""
直播源检测脚本
从 https://10694.kstore.space/live/autoIP.txt 提取IP模板并生成实际地址进行检测
"""

import re
import requests
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse

SOURCE_URL = "https://10694.kstore.space/live/autoIP.txt"
TIMEOUT = 5
MAX_WORKERS = 200

# 请求头（模拟常见客户端）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def fetch_source():
    """获取源文本"""
    print(f"[*] 拉取源文件: {SOURCE_URL}")
    r = requests.get(SOURCE_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    # 尝试多种编码
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            r.encoding = enc
            text = r.text
            if text and "Please Input" not in text:
                return text
        except Exception:
            continue
    return r.text


def expand_template(line):
    """
    将带有 (a-b) 变量的模板展开成具体 URL 列表
    支持类似: http://115.44.165.(1-256):18180TV...@HHZT
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return []

    # 找出所有 (数字-数字) 变量
    pattern = re.compile(r"\((\d+)\s*[-–]\s*(\d+)\)")
    matches = list(pattern.finditer(line))

    if not matches:
        return [line]  # 没有变量，直接返回原行

    # 递归展开
    def expand(s, idx):
        if idx >= len(matches):
            return [s]
        results = []
        start, end = int(matches[idx].group(1)), int(matches[idx].group(2))
        # 每次重新在当前字符串中找第一个变量（因为替换后位置会变化）
        m = pattern.search(s)
        if not m:
            return [s]
        results = []
        for v in range(start, end + 1):
            new_s = s[:m.start()] + str(v) + s[m.end():]
            results.extend(expand(new_s, idx + 1))
        return results

    return expand(line, 0)


def check_url(url):
    """检测单个URL是否可访问"""
    try:
        # 先尝试 HEAD，若不允许再 GET
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code < 700:
            return (url, True, r.status_code)
        # 回退用 GET（流媒体大多不支持 HEAD）
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)
        code = r.status_code
        r.close()
        return (url, code < 700, code)
    except Exception as e:
        return (url, False, str(e))


def main():
    start_time = datetime.now()
    print(f"[*] 开始时间: {start_time}")

    text = fetch_source()
    lines = text.splitlines()
    print(f"[*] 源文件行数: {len(lines)}")

    # 展开所有模板
    all_urls = []
    for line in lines:
        urls = expand_template(line)
        all_urls.extend(urls)

    # 去重
    all_urls = list(dict.fromkeys(all_urls))
    print(f"[*] 展开后URL总数: {len(all_urls)}")

    if not all_urls:
        print("[!] 没有解析到任何URL，请检查源文件格式")
        with open("summary.txt", "w", encoding="utf-8") as f:
            f.write("No URLs parsed.\n")
        return

    # 并发检测
    valid, invalid = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(check_url, u): u for u in all_urls}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            url, ok, info = fut.result()
            done += 1
            if ok:
                valid.append(url)
                print(f"[✓] {url}  ({info})")
            else:
                invalid.append(url)
            if done % 200 == 0:
                print(f"[*] 进度: {done}/{len(all_urls)}  有效: {len(valid)}")

    # 输出结果
    with open("valid.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(valid))
    with open("invalid.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(invalid))

    end_time = datetime.now()
    summary = (
        f"检测时间: {start_time} ~ {end_time}\n"
        f"总URL数: {len(all_urls)}\n"
        f"有效: {len(valid)}\n"
        f"无效: {len(invalid)}\n"
    )
    with open("summary.txt", "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n" + summary)


if __name__ == "__main__":
    main()
