import json
import urllib.request
from pathlib import Path
from urllib.parse import unquote


CONFIG_FILE = "rjsxrd-filter-config.json"


PROTOCOLS = (
    "vless://",
    "vmess://",
    "ss://",
    "trojan://",
    "hysteria://",
    "hysteria2://",
    "tuic://",
    "socks://",
    "http://",
    "https://",
)


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def download_source(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def is_server(line):
    return line.lower().startswith(PROTOCOLS)


def get_server_name(line):
    if "#" not in line:
        return ""

    name = line.split("#", 1)[1]

    return unquote(name).strip()


def contains_any(text, patterns):
    """
    True, если text содержит хотя бы один
    непустой шаблон из patterns.
    """

    if not patterns:
        return False

    text = text.lower()

    for pattern in patterns:
        if not pattern:
            continue

        if pattern.lower() in text:
            return True

    return False


def main():

    config = load_config()

    source_url = config["source"]
    include = config.get("include", [])
    exclude = config.get("exclude", [])
    output_file = config.get("output", "rjsxrd-filter.txt")

    print("Скачивание источника...")

    source = download_source(source_url)
    raw_lines = source.splitlines()

    priority = []
    others = []

    seen = set()

    total_source_lines = len(raw_lines)
    total_servers = 0
    excluded_servers = 0
    duplicate_servers = 0
    skipped_lines = 0

    for raw_line in raw_lines:

        line = raw_line.strip()

        if not line:
            continue

        # Только реальные серверные строки
        if not is_server(line):
            skipped_lines += 1
            continue

        total_servers += 1

        # Точные дубликаты
        if line in seen:
            duplicate_servers += 1
            continue

        seen.add(line)

        # Название/remark сервера
        name = get_server_name(line)

        # EXCLUDE
        if contains_any(name, exclude):
            excluded_servers += 1
            continue

        # INCLUDE = приоритет, а не фильтр
        if contains_any(name, include):
            priority.append(line)
        else:
            others.append(line)

    # ============================================
    # METADATA
    # ============================================

    output = []

    metadata = config.get("metadata", {})

    if metadata.get("profile-title"):
        output.append(
            f"#profile-title: {metadata['profile-title']}"
        )

    if metadata.get("profile-update-interval"):
        output.append(
            f"#profile-update-interval: "
            f"{metadata['profile-update-interval']}"
        )

    if metadata.get("support-url"):
        output.append(
            f"#support-url: {metadata['support-url']}"
        )

    if metadata.get("profile-web-page-url"):
        output.append(
            f"#profile-web-page-url: "
            f"{metadata['profile-web-page-url']}"
        )

    if metadata.get("announce"):
        output.append(
            f"#announce: {metadata['announce']}"
        )

    if metadata.get("announce-url"):
        output.append(
            f"#announce-url: {metadata['announce-url']}"
        )

    output.append("")

    # ============================================
    # СЕРВЕРЫ
    # ============================================

    # Сначала Германия / Нидерланды / Финляндия
    output.extend(priority)

    # Потом все остальные
    output.extend(others)

    # ============================================
    # СОХРАНЕНИЕ
    # ============================================

    Path(output_file).write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    # ============================================
    # СТАТИСТИКА
    # ============================================

    final_count = len(priority) + len(others)

    print()
    print("========== РЕЗУЛЬТАТ ==========")
    print(f"Всего строк в источнике: {total_source_lines}")
    print(f"Найдено серверов: {total_servers}")
    print(f"Приоритетных: {len(priority)}")
    print(f"Остальных: {len(others)}")
    print(f"Исключено: {excluded_servers}")
    print(f"Дубликатов: {duplicate_servers}")
    print(f"Metadata/прочих строк: {skipped_lines}")
    print(f"Итоговых серверов: {final_count}")
    print(f"Файл: {output_file}")
    print("================================")


if __name__ == "__main__":
    main()
