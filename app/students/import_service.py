import csv
import io
import unicodedata
import zipfile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


MAX_IMPORT_ROWS = 1000
MAX_WORKBOOK_UNCOMPRESSED_SIZE = 25 * 1024 * 1024


class StudentImportError(ValueError):
    pass


def _normalize_header(value):
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _is_empty_row(values):
    return all(value is None or (isinstance(value, str) and not value.strip()) for value in values)


def _read_csv(file_bytes):
    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise StudentImportError(
            "O arquivo CSV deve estar codificado em UTF-8."
        ) from error

    try:
        rows = list(csv.reader(io.StringIO(content, newline="")))
    except csv.Error as error:
        raise StudentImportError("Não foi possível interpretar o arquivo CSV.") from error
    return rows


def _read_xlsx(file_bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            uncompressed_size = sum(member.file_size for member in archive.infolist())
            if uncompressed_size > MAX_WORKBOOK_UNCOMPRESSED_SIZE:
                raise StudentImportError(
                    "A planilha excede o limite de conteúdo descompactado permitido."
                )
    except zipfile.BadZipFile as error:
        raise StudentImportError("O arquivo XLSX está corrompido ou é inválido.") from error

    try:
        workbook = load_workbook(
            io.BytesIO(file_bytes),
            read_only=True,
            data_only=True,
            keep_links=False,
        )
    except (
        InvalidFileException,
        KeyError,
        OSError,
        OverflowError,
        ParseError,
        ValueError,
        EOFError,
        zipfile.BadZipFile,
    ) as error:
        raise StudentImportError("Não foi possível abrir o arquivo XLSX.") from error

    try:
        worksheet = workbook.active
        if worksheet is None:
            raise StudentImportError("A planilha não contém uma aba para leitura.")
        if worksheet.max_row and worksheet.max_row > MAX_IMPORT_ROWS + 1:
            raise StudentImportError(
                f"A planilha pode conter no máximo {MAX_IMPORT_ROWS} alunos."
            )
        return [list(row) for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def parse_student_file(upload):
    filename = (upload.filename or "").lower()
    extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    file_bytes = upload.read()

    if extension == "csv":
        source_rows = _read_csv(file_bytes)
    elif extension == "xlsx":
        source_rows = _read_xlsx(file_bytes)
    else:
        raise StudentImportError("Envie uma planilha no formato CSV ou XLSX.")

    if not source_rows:
        raise StudentImportError("A planilha está vazia.")

    header = source_rows[0][0] if source_rows[0] else None
    if _normalize_header(header) not in ("nome", "nome do aluno"):
        raise StudentImportError(
            "A primeira coluna da planilha deve ter o cabeçalho 'nome'."
        )

    students = []
    for row_number, values in enumerate(source_rows[1:], start=2):
        if _is_empty_row(values):
            continue
        if len(students) >= MAX_IMPORT_ROWS:
            raise StudentImportError(
                f"A planilha pode conter no máximo {MAX_IMPORT_ROWS} alunos."
            )

        raw_name = values[0] if values else None
        error = None
        name = ""
        if not isinstance(raw_name, str):
            error = "Informe o nome do aluno como texto."
        else:
            name = raw_name.strip()
            if not name:
                error = "O nome do aluno está vazio."
            elif len(name) > 160:
                name = ""
                error = "O nome ultrapassa o limite de 160 caracteres."

        students.append({"row_number": row_number, "name": name, "error": error})

    if not students:
        raise StudentImportError("A planilha não contém alunos para importar.")
    return students


def validate_student_rows(rows, existing_names):
    existing = {name.casefold() for name in existing_names}
    seen = set()
    validated_rows = []

    for source_row in rows:
        row = dict(source_row)
        name = row["name"]
        if row["error"] or not name:
            validated_rows.append(row)
            continue

        normalized_name = name.casefold()
        if normalized_name in existing:
            row["error"] = "Este aluno já está cadastrado na turma."
        elif normalized_name in seen:
            row["error"] = "Nome duplicado nesta planilha."
        seen.add(normalized_name)
        validated_rows.append(row)

    return validated_rows
