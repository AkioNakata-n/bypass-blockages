import json
import urllib.request
from pathlib import Path
from urllib.parse import unquote


CONFIG_FILE = "rjsxrd-filter-config.json"


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
    """
    Проверяем, является ли строка серверной конфигурацией.
    """

    protocols = (
        "vless://",
        "vmess://",
        "ss://",
        "trojan://",
        "hysteria://",
        "hysteria2://",
        "tuic://",
        "socks://",
        "http://",
        "https://"
    )

    return line.lower().startswith(protocols)


def get_server_name(line):
    """
    Получаем часть после # и декодируем URL-кодирование.

    Например:

    #🇳🇱 Join+Telegram:@SolVPN 🇳🇱%20t.me%2Frjsxrd

    превращается примерно в:

    🇳🇱 Join+Telegram:@SolVPN 🇳🇱 t.me/rjsxrd
    """

    if "#" not in line:
        return ""

    name = line.split("#", 1)[1]

    return unquote(name).strip()


def contains_any(text, patterns):
    text = text.lower()

    return any(
        pattern.lower() in text
        for pattern in patterns
    )


def main():
    config = load_config()

    source_url = config["source"]
    include = config.get("include", [])
    exclude = config.get("exclude", [])
    output_file = config.get("output", "filtered.txt")

    print("Скачивание исходной подписки...")
    source = download_source(source_url)

    raw_lines = source.splitlines()

    priority = []
    others = []

    seen = set()

    total_server_lines = 0
    skipped_lines = 0

    for raw_line in raw_lines:

        line = raw_line.strip()

        if not line:
            continue

        # Metadata и комментарии исходной подписки пропускаем
        if not is_server(line):
            skipped_lines += 1
            continue

        total_server_lines += 1

        # Убираем только точные дубликаты
        if line in seen:
            continue

        seen.add(line)

        # Название сервера
        name = get_server_name(line)

        # Exclude → полностью удаляем
        if contains_any(name, exclude):
            continue

        # Include → приоритет
        if contains_any(name, include):
            priority.append(line)
        else:
            others.append(line)

    output = []

    # -------------------------------------------------
    # СОБСТВЕННЫЕ METADATA
    # -------------------------------------------------

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

    # -------------------------------------------------
    # СЕРВЕРЫ
    # -------------------------------------------------

    output.extend(priority)
    output.extend(others)

    Path(output_file).write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    # -------------------------------------------------
    # СТАТИСТИКА
    # -------------------------------------------------

    print()
    print(f"Всего строк в источнике: {len(raw_lines)}")
    print(f"Найдено серверов: {total_server_lines}")
    print(f"Приоритетных: {len(priority)}")
    print(f"Остальных: {len(others)}")
    print(f"Итоговых: {len(priority) + len(others)}")
    print(f"Пропущено metadata/прочих строк: {skipped_lines}")
    print(f"Записано в: {output_file}")


if __name__ == "__main__":
    main()
