import csv
import io
import re
from datetime import date
from decimal import Decimal


def decode_file_content(file_content):
    """
    Decode uploaded file content using common encodings.
    """
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ]

    for encoding in encodings:
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("Unable to decode file.")


def parse_santander_amount(raw):
    """
    Parse Santander positional signed amount.
    """
    sign = raw[0]
    digits = raw[1:]

    value = Decimal(digits) / Decimal("100")

    if sign == "-":
        value *= -1

    return value


def parse_santander_positional_line(line):
    """
    Parse one Santander positional statement line.
    """
    line = line.strip()

    if not line.startswith("030"):
        return None

    signed_values = re.findall(r"[+-]\d{18}", line)

    if not signed_values:
        return None

    amount = parse_santander_amount(signed_values[-1])

    dates = []

    for match in re.finditer(r"20\d{6}", line):
        try:
            parsed_date = date(
                int(match.group()[0:4]),
                int(match.group()[4:6]),
                int(match.group()[6:8]),
            )
            dates.append(
                (
                    parsed_date,
                    match.end(),
                )
            )
        except ValueError:
            continue

    if not dates:
        return None

    movement_date, description_start = dates[-1]

    next_number = re.search(
        r"[+-]\d{18}",
        line[description_start:],
    )

    if next_number:
        description_end = description_start + next_number.start()
        description = line[description_start:description_end].strip()
    else:
        description = line[description_start:].strip()

    return {
        "date": movement_date,
        "description": description,
        "amount": amount,
    }


def parse_santander_positional_statement(content):
    """
    Parse Santander positional TXT statement.
    """
    transactions = []
    total = 0
    invalid = 0

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()

        if not line.startswith("030"):
            continue

        total += 1

        parsed = parse_santander_positional_line(line)

        if parsed:
            parsed["line_number"] = line_number
            parsed["raw_line"] = raw_line
            transactions.append(parsed)
        else:
            invalid += 1

    return {
        "transactions": transactions,
        "total_lines": total,
        "invalid_lines": invalid,
    }


def parse_csv_statement(content):
    """
    Parse CSV statement with expected columns:
    data, descricao, montante, saldo.
    """
    csv_file = io.StringIO(content)
    reader = csv.DictReader(csv_file, delimiter=";")

    transactions = []
    total = 0
    invalid = 0

    if not reader.fieldnames:
        return {
            "transactions": transactions,
            "total_lines": total,
            "invalid_lines": invalid,
        }

    reader.fieldnames = [
        field.strip().lower()
        for field in reader.fieldnames
    ]

    for line_number, row in enumerate(reader, start=2):
        total += 1

        raw_date = row.get("data")
        raw_description = row.get("descricao") or row.get("descrição") or ""
        raw_amount = row.get("montante")

        if not raw_date or not raw_amount:
            invalid += 1
            continue

        try:
            day, month, year = raw_date.strip().split("/")

            movement_date = date(
                int(year),
                int(month),
                int(day),
            )

            amount = Decimal(
                raw_amount.strip().replace(".", "").replace(",", ".")
            )

        except (ValueError, TypeError):
            invalid += 1
            continue

        transactions.append(
            {
                "date": movement_date,
                "description": raw_description.strip(),
                "amount": amount,
                "line_number": line_number,
                "raw_line": str(row),
            }
        )

    return {
        "transactions": transactions,
        "total_lines": total,
        "invalid_lines": invalid,
    }


def parse_bank_statement(content):
    """
    Parse supported bank statement formats.
    """
    stripped_content = content.lstrip()

    if stripped_content.startswith("010") or stripped_content.startswith("030"):
        return parse_santander_positional_statement(content)

    return parse_csv_statement(content)