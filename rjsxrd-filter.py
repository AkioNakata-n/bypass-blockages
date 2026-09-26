import json
import urllib.request
from pathlib import Path
from urllib.parse import unquote


CONFIG_FILE = "rjsxrd-config.json"


# Поддерживаемые протоколы серверов
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
    """Проверяет, является ли строка серверной конфигурацией."""
    return line.lower().startswith(PROTOCOLS)


def get_server_name(line):
    """
    Получает название сервера после #.
    URL-кодирование декодируется.

    Например:
    %F0%9F%87%B3%F0%9F%87%B1
    ->
    🇳🇱
    """

    if "#" not in line:
        return ""

    name = line.split("#", 1)[1]

    return unquote(name).strip()


def contains_any(text, patterns):
    """
    Проверяет, содержит ли текст хотя бы один
    из указанных шаблонов.
    """

    if not patterns:
        return False

    text = text.lower()

    for pattern in patterns:
        if pattern.lower() in text:
            return True

    return False


def main():

    # ============================================
    # CONFIG
    # ============================================

    config = load_config()

    source_url = config["source"]

    include = config.get("include", [])
    exclude = config.get("exclude", [])

    output_file = config.get(
        "output",
        "rjsxrd-filter.txt"
    )

    # ============================================
    # DOWNLOAD
    # ============================================

    print("Скачивание источника...")

    source = download_source(source_url)

    raw_lines = source.splitlines()

    # ============================================
    # SERVER COLLECTION
    # ============================================

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

        # Пустые строки
        if not line:
            continue

        # ----------------------------------------
        # Проверяем сервер
        # ----------------------------------------

        if not is_server(line):
            skipped_lines += 1
            continue

        total_servers += 1

        # ----------------------------------------
        # Удаляем точные дубликаты
        # ----------------------------------------

        if line in seen:
            duplicate_servers += 1
            continue

        seen.add(line)

        # ----------------------------------------
        # Получаем имя сервера
        # ----------------------------------------

        name = get_server_name(line)

        # ----------------------------------------
        # EXCLUDE
        # ----------------------------------------

        if contains_any(name, exclude):
            excluded_servers += 1
            continue

        # ----------------------------------------
        # INCLUDE
        # ----------------------------------------

        if contains_any(name, include):
            priority.append(line)
        else:
            others.append(line)

    # ============================================
    # OUTPUT
    # ============================================

    output = []

    metadata = config.get("metadata", {})

    # --------------------------------------------
    # Metadata
    # --------------------------------------------

    if metadata.get("profile-title"):
        output.append(
            f"#profile-title: "
            f"{metadata['profile-title']}"
        )

    if metadata.get("profile-update-interval"):
        output.append(
            f"#profile-update-interval: "
            f"{metadata['profile-update-interval']}"
        )

    if metadata.get("support-url"):
        output.append(
            f"#support-url: "
            f"{metadata['support-url']}"
        )

    if metadata.get("profile-web-page-url"):
        output.append(
            f"#profile-web-page-url: "
            f"{metadata['profile-web-page-url']}"
        )

    if metadata.get("announce"):
        output.append(
            f"#announce: "
            f"{metadata['announce']}"
        )

    if metadata.get("announce-url"):
        output.append(
            f"#announce-url: "
            f"{metadata['announce-url']}"
        )

    output.append("")

    # --------------------------------------------
    # Сначала приоритетные
    # --------------------------------------------

    output.extend(priority)

    # --------------------------------------------
    # Затем остальные
    # --------------------------------------------

    output.extend(others)

    # ============================================
    # WRITE FILE
    # ============================================

    Path(output_file).write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    # ============================================
    # STATISTICS
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
