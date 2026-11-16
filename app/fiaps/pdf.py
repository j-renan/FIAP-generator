from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = 38
RIGHT = PAGE_WIDTH - LEFT
CONTENT_WIDTH = RIGHT - LEFT
COMMENTS_BOTTOM = 225
LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "img" / "logo_senai.png"
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _wrap_text(value, width, font_name, font_size):
    lines = []
    for paragraph in str(value or "").splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current_line = ""
        for word in words:
            candidate = f"{current_line} {word}".strip()
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
                current_line = candidate
                continue

            if current_line:
                lines.append(current_line)
                current_line = ""

            remaining = word
            while pdfmetrics.stringWidth(remaining, font_name, font_size) > width:
                split_at = 1
                while (
                    split_at < len(remaining)
                    and pdfmetrics.stringWidth(
                        remaining[: split_at + 1], font_name, font_size
                    )
                    <= width
                ):
                    split_at += 1
                lines.append(remaining[:split_at])
                remaining = remaining[split_at:]
            current_line = remaining

        if current_line:
            lines.append(current_line)

    return lines


def _draw_header(pdf, sheet, continuation=False):
    logo = ImageReader(str(LOGO_PATH))
    logo_width, logo_height = logo.getSize()
    display_width = 118
    display_height = display_width * logo_height / logo_width
    pdf.drawImage(
        logo,
        (PAGE_WIDTH - display_width) / 2,
        PAGE_HEIGHT - 22 - display_height,
        width=display_width,
        height=display_height,
        mask="auto",
    )

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawCentredString(
        PAGE_WIDTH / 2,
        PAGE_HEIGHT - 64,
        "FICHA INDIVIDUAL DE AVALIAÇÃO PERIÓDICA",
    )
    pdf.setFont(FONT_BOLD, 8)
    pdf.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 78, f"N° da ficha: {sheet.id}")
    if continuation:
        pdf.setFont(FONT_REGULAR, 7)
        pdf.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 91, "CONTINUAÇÃO")
        return PAGE_HEIGHT - 111
    return PAGE_HEIGHT - 101


def _draw_field_row(pdf, fields, top):
    font_size = 8
    value_size = 8
    line_height = 10
    max_value_lines = 1

    for label, value, x, width in fields:
        pdf.setFont(FONT_BOLD, font_size)
        pdf.drawString(x, top, label)

        lines = _wrap_text(value, width, FONT_REGULAR, value_size)
        max_value_lines = max(max_value_lines, len(lines))
        pdf.setFont(FONT_REGULAR, value_size)
        for index, line in enumerate(lines):
            line_y = top - 13 - index * line_height
            pdf.drawString(x, line_y, line)
            pdf.setLineWidth(0.45)
            pdf.line(x, line_y - 2, x + width, line_y - 2)

    return top - max(27, 18 + (max_value_lines - 1) * line_height)


def _draw_summary(pdf, sheet, top):
    pdf.setFillColorRGB(0, 0, 0)
    top = _draw_field_row(
        pdf,
        [
            ("Nome do Aluno:", sheet.student.name, LEFT, 348),
            ("Turma:", sheet.class_group.name, 400, 157),
        ],
        top,
    )
    top = _draw_field_row(
        pdf,
        [
            ("Empresa:", sheet.company, LEFT, 157),
            ("Docente:", sheet.teacher.name, 207, 175),
            ("Data:", sheet.evaluated_on.strftime("%d/%m/%Y"), 394, 163),
        ],
        top,
    )
    top = _draw_field_row(
        pdf,
        [
            ("Unidade Curricular:", sheet.curricular_unit.name, LEFT, 300),
            ("Carga Horária (total):", f"{sheet.workload_hours} h", 352, 205),
        ],
        top,
    )
    top = _draw_field_row(
        pdf,
        [
            ("Média da Classe:", str(sheet.class_average), LEFT, 214),
            ("Horas/Faltas (limite):", format(sheet.absence_limit_hours, ".2f"), 265, 292),
        ],
        top,
    )
    return _draw_field_row(
        pdf,
        [
            ("Nota do Aluno:", str(sheet.student_grade), LEFT, 214),
            ("Horas/Faltas (total):", str(sheet.absences_hours), 265, 292),
        ],
        top,
    )


def _draw_signatures(pdf):
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setLineWidth(0.55)
    pdf.setFont(FONT_BOLD, 7)

    y = 172
    pdf.drawString(LEFT, y + 3, "Atendido por:")
    pdf.line(LEFT + 62, y, 360, y)
    pdf.drawString(367, y + 3, "Data:")
    pdf.line(397, y, RIGHT, y)

    y = 122
    groups = [
        (LEFT, 121, "NOME DO RESPONSÁVEL"),
        (170, 68, "CPF"),
        (247, 66, "DATA"),
        (322, 85, "ASSINATURA"),
    ]
    for x, width, label in groups:
        pdf.line(x, y, x + width, y)
        pdf.setFont(FONT_REGULAR, 6.5)
        pdf.drawCentredString(x + width / 2, y - 9, label)

    y = 77
    groups = [
        (LEFT, 121, "COORDENAÇÃO"),
        (170, 68, "DATA"),
        (247, 121, "DIREÇÃO"),
        (380, 121, "DATA"),
    ]
    for x, width, label in groups:
        pdf.line(x, y, x + width, y)
        pdf.setFont(FONT_REGULAR, 6.5)
        pdf.drawCentredString(x + width / 2, y - 9, label)

    pdf.setFont(FONT_REGULAR, 6)
    pdf.drawRightString(RIGHT, 24, "FR-5.10-08 v7")


def _draw_comments(pdf, sheet, top):
    sections = (
        ("Principais dificuldades:", sheet.difficulties, 4),
        ("Recomendações do professor ao aluno/responsável:", sheet.recommendations, 5),
        (
            "Providências do professor e da escola para auxiliar o aluno:",
            sheet.school_actions,
            4,
        ),
        ("Outras Observações:", sheet.observations, 3),
    )
    y = top

    for title, text, minimum_lines in sections:
        if y - 28 < COMMENTS_BOTTOM:
            pdf.showPage()
            y = _draw_header(pdf, sheet, continuation=True)

        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont(FONT_BOLD, 8)
        pdf.drawString(LEFT, y, title)
        y -= 14

        lines = _wrap_text(text, CONTENT_WIDTH, FONT_REGULAR, 8)
        line_count = max(minimum_lines, len(lines))
        pdf.setFont(FONT_REGULAR, 8)
        for index in range(line_count):
            if y - 14 < COMMENTS_BOTTOM:
                pdf.showPage()
                y = _draw_header(pdf, sheet, continuation=True)
                pdf.setFont(FONT_BOLD, 8)
                pdf.drawString(LEFT, y, f"{title} (continuação)")
                y -= 14
                pdf.setFont(FONT_REGULAR, 8)

            line = lines[index] if index < len(lines) else ""
            pdf.drawString(LEFT, y, line)
            pdf.setLineWidth(0.45)
            pdf.line(LEFT, y - 2, RIGHT, y - 2)
            y -= 13

    return y


def build_sheet_pdf(sheet):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=0)
    pdf.setTitle(f"FIAP - Ficha {sheet.id}")
    pdf.setAuthor(sheet.teacher.name)
    pdf.setSubject("Ficha Individual de Avaliação Periódica")

    content_top = _draw_header(pdf, sheet)
    content_top = _draw_summary(pdf, sheet, content_top)
    _draw_comments(pdf, sheet, content_top - 7)
    _draw_signatures(pdf)

    pdf.save()
    return output.getvalue()
