import base64
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import unquote, unquote_plus


CONFIG_FILE = "rjsxrd-filter-reserve-config.json"


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
    "awg://",
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


def add_base64_padding(text):
    return text + "=" * (-len(text) % 4)


def try_base64_decode(text):
    """
    Пытается декодировать строку как обычный или URL-safe Base64.
    Возвращает строку или None.
    """

    text = text.strip()

    if not text:
        return None

    try:
        decoded = base64.b64decode(
            add_base64_padding(text),
            validate=False
        )

        result = decoded.decode("utf-8")

        # Защита от случайного мусора
        if result and sum(c.isprintable() or c.isspace() for c in result) / len(result) > 0.85:
            return result

    except Exception:
        pass

    try:
        decoded = base64.urlsafe_b64decode(
            add_base64_padding(text)
        )

        result = decoded.decode("utf-8")

        if result and sum(c.isprintable() or c.isspace() for c in result) / len(result) > 0.85:
            return result

    except Exception:
        pass

    return None


def extract_json_strings(obj):
    """
    Рекурсивно достаёт все строки из JSON.
    """

    result = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            result.append(str(key))
            result.extend(extract_json_strings(value))

    elif isinstance(obj, list):
        for item in obj:
            result.extend(extract_json_strings(item))

    elif isinstance(obj, str):
        result.append(obj)

    return result


def decode_server_data(line):
    """
    Пытается получить максимум читаемого содержимого
    из серверной ссылки.

    Ничего не изменяет в самой ссылке.
    """

    decoded_parts = []

    # ---------------------------------------------------------
    # 1. Сама строка
    # ---------------------------------------------------------

    decoded_parts.append(line)

    # URL-decoding
    url_decoded = unquote(line)

    if url_decoded != line:
        decoded_parts.append(url_decoded)

    # ---------------------------------------------------------
    # 2. VMess
    # ---------------------------------------------------------

    if line.lower().startswith("vmess://"):

        payload = line[len("vmess://"):].strip()

        decoded = try_base64_decode(payload)

        if decoded:
            decoded_parts.append(decoded)

            try:
                data = json.loads(decoded)

                decoded_parts.extend(
                    extract_json_strings(data)
                )

            except json.JSONDecodeError:
                pass

    # ---------------------------------------------------------
    # 3. SS / другие ссылки с Base64 внутри
    # ---------------------------------------------------------

    # Разбиваем строку на потенциальные Base64-фрагменты.
    #
    # Это позволяет дополнительно обнаруживать текст,
    # который спрятан внутри URL.

    candidates = re.split(r"[/?:#@=&\s]+", line)

    for candidate in candidates:

        candidate = unquote(candidate).strip()

        if len(candidate) < 8:
            continue

        # Base64 обычно состоит из этих символов.
        if not re.fullmatch(r"[A-Za-z0-9+/_=-]+", candidate):
            continue

        decoded = try_base64_decode(candidate)

        if decoded:
            decoded_parts.append(decoded)

            # Если внутри оказался JSON
            try:
                data = json.loads(decoded)

                decoded_parts.extend(
                    extract_json_strings(data)
                )

            except json.JSONDecodeError:
                pass

    # ---------------------------------------------------------
    # 4. Дополнительный URL decode
    # ---------------------------------------------------------

    extra_parts = []

    for part in decoded_parts:

        decoded = unquote_plus(part)

        if decoded != part:
            extra_parts.append(decoded)

    decoded_parts.extend(extra_parts)

    # ---------------------------------------------------------
    # Убираем дубликаты
    # ---------------------------------------------------------

    result = []

    seen = set()

    for part in decoded_parts:

        if not part:
            continue

        if part in seen:
            continue

        seen.add(part)
        result.append(part)

    return "\n".join(result)


def get_server_name(line):
    """
    Пытается определить название сервера.

    Сначала проверяем стандартный #remark.
    Затем декодированное содержимое.

    Возвращается текст, по которому можно выполнять фильтрацию.
    """

    decoded = decode_server_data(line)

    return decoded


def contains_any(text, patterns):
    """
    Проверяет, содержит ли текст хотя бы один
    непустой шаблон.

    Поиск регистронезависимый.
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

    output_file = config.get(
        "output",
        "rjsxrd-filter-reserve.txt"
    )

    print("Скачивание источника...")

    source = download_source(source_url)

    raw_lines = source.splitlines()

    priority = []

    seen = set()

    total_source_lines = len(raw_lines)
    total_servers = 0
    matched_servers = 0
    excluded_servers = 0
    duplicate_servers = 0
    skipped_lines = 0

    for raw_line in raw_lines:

        line = raw_line.strip()

        if not line:
            continue

        # Только серверные ссылки
        if not is_server(line):

            skipped_lines += 1
            continue

        total_servers += 1

        # Точные дубликаты
        if line in seen:

            duplicate_servers += 1
            continue

        seen.add(line)

        # -----------------------------------------------------
        # Получаем декодированное содержимое
        # -----------------------------------------------------

        decoded_data = get_server_name(line)

        # -----------------------------------------------------
        # EXCLUDE
        # -----------------------------------------------------

        if contains_any(
            decoded_data,
            exclude
        ):

            excluded_servers += 1
            continue

        # -----------------------------------------------------
        # INCLUDE = ФИЛЬТР
        #
        # Если include заполнен, сервер обязан содержать
        # хотя бы один из указанных вариантов.
        # -----------------------------------------------------

        if include and not contains_any(
            decoded_data,
            include
        ):

            excluded_servers += 1
            continue

        # -----------------------------------------------------
        # Сервер подходит
        # -----------------------------------------------------

        priority.append(line)

        matched_servers += 1

    # ---------------------------------------------------------
    # Формируем результат
    # ---------------------------------------------------------

    output = []

    metadata = config.get(
        "metadata",
        {}
    )

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

    # Оригинальные ссылки
    output.extend(priority)

    Path(output_file).write_text(
        "\n".join(output) + "\n",
        encoding="utf-8"
    )

    # ---------------------------------------------------------
    # Статистика
    # ---------------------------------------------------------

    print()
    print("Готово.")
    print()
    print(f"Всего строк в источнике: {total_source_lines}")
    print(f"Найдено серверов:        {total_servers}")
    print(f"Подошло по фильтру:      {matched_servers}")
    print(f"Исключено:                {excluded_servers}")
    print(f"Дубликатов:               {duplicate_servers}")
    print(f"Metadata/прочих строк:    {skipped_lines}")
    print(f"Итоговых серверов:        {len(priority)}")
    print()
    print(f"Файл: {output_file}")


if __name__ == "__main__":
    main()
