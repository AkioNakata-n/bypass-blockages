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


def get_server_name(line):
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
    output_file = config.get("output", "rjsxrd-filter.txt")

    source = download_source(source_url)

    lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip()
    ]

    priority = []
    others = []
    seen = set()

    for line in lines:
        # Убираем точные дубликаты
        if line in seen:
            continue

        seen.add(line)

        name = get_server_name(line)

        # Полностью исключаем сервер
        if contains_any(name, exclude):
            continue

        # Подходящий сервер → наверх
        if contains_any(name, include):
            priority.append(line)
        else:
            # Остальные → вниз
            others.append(line)

    output = []

    # Метаданные
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

    if metadata.get("announce"):
        output.append(
            f"#announce: {metadata['announce']}"
        )

    output.append("")

    # Сначала приоритетные
    output.extend(priority)

    # Затем остальные
    output.extend(others)

    Path(output_file).write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    print(f"Всего исходных серверов: {len(lines)}")
    print(f"Приоритетных: {len(priority)}")
    print(f"Остальных: {len(others)}")
    print(f"Итоговых: {len(priority) + len(others)}")
    print(f"Записано в: {output_file}")


if __name__ == "__main__":
    main()
