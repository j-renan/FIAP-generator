from datetime import date
import json
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    ClassGroup,
    Course,
    CurricularUnit,
    EvaluationDraft,
    EvaluationSheet,
    Student,
    User,
)


@pytest.fixture
def authenticated_client(client, app):
    with app.app_context():
        teacher = User(name="Docente FIAP", email="fiap@senai.br")
        teacher.set_password("Senha-segura-123")
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id

    with client.session_transaction() as session:
        session["_user_id"] = str(teacher_id)
        session["_fresh"] = True

    return client


def create_fiap_records(course_name="Curso FIAP", workload_hours=80):
    course = Course(name=course_name)
    class_group = ClassGroup(name="3DSA", course=course)
    student = Student(name="Aluno FIAP", class_group=class_group)
    unit = CurricularUnit(
        name="Desenvolvimento Web",
        workload_hours=workload_hours,
        course=course,
    )
    db.session.add_all([student, unit])
    db.session.commit()
    return student.id, unit.id, class_group.id


def fiap_form_data(student_id, unit_id, class_id, **overrides):
    data = {
        "class_id": str(class_id),
        "student_id": str(student_id),
        "curricular_unit_id": str(unit_id),
        "evaluated_on": "2026-11-16",
        "company": "Empresa Exemplo",
        "class_average": "75",
        "student_grade": "82",
        "absence_limit_hours": "40",
        "absences_hours": "12",
        "difficulties": "Organização das tarefas",
        "recommendations": "Manter rotina de estudos",
        "school_actions": "Acompanhamento quinzenal",
        "observations": "Revisar no próximo período",
    }
    data.update(overrides)
    return data


def test_fiap_preview_does_not_save_until_confirmed(authenticated_client, app):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()

    response = authenticated_client.post(
        "/fiaps/nova", data=fiap_form_data(student_id, unit_id, class_id)
    )
    assert response.status_code == 302
    preview_url = response.headers["Location"]

    with app.app_context():
        assert db.session.scalar(db.select(EvaluationSheet.id)) is None
        draft = db.session.scalar(db.select(EvaluationDraft))
        assert draft is not None
        draft_id = draft.id

    response = authenticated_client.get(preview_url)
    assert response.status_code == 200
    assert b"Revise a ficha" in response.data
    assert b"Turma" in response.data
    assert b"3DSA" in response.data
    assert b"80 h" in response.data
    assert b"Empresa Exemplo" in response.data
    assert b"Docente FIAP" in response.data

    response = authenticated_client.post(f"{preview_url}/salvar")
    assert response.status_code == 302

    with app.app_context():
        sheet = db.session.scalar(db.select(EvaluationSheet))
        assert sheet is not None
        sheet_id = sheet.id
        assert sheet.student_id == student_id
        assert sheet.class_id == class_id
        assert sheet.curricular_unit_id == unit_id
        assert sheet.workload_hours == 80
        assert sheet.class_average == 75
        assert sheet.student_grade == 82
        assert sheet.absence_limit_hours == Decimal("20.00")
        assert sheet.absences_hours == 12
        assert sheet.difficulties == "Organização das tarefas"
        assert sheet.teacher.email == "fiap@senai.br"
        assert db.session.get(EvaluationDraft, draft_id) is None

    response = authenticated_client.get(f"/fiaps/{sheet_id}")
    assert response.status_code == 200
    assert b"Ficha salva" in response.data
    assert b"Exportar PDF" in response.data
    number_text = f"N° da ficha: {sheet_id}".encode()
    page_header = response.data.split(
        b'<header class="page-header">', maxsplit=1
    )[1].split(b"</header>", maxsplit=1)[0]
    document_header = response.data.split(
        b'<header class="fiap-document-header">', maxsplit=1
    )[1].split(b"</header>", maxsplit=1)[0]
    assert number_text not in page_header
    assert document_header.index(
        "FICHA INDIVIDUAL DE AVALIAÇÃO PERIÓDICA".encode()
    ) < document_header.index(number_text)
    response = authenticated_client.get("/fiaps/")
    assert response.status_code == 200
    assert b"Aluno FIAP" in response.data
    assert b"N\xc2\xb0 da ficha" in response.data

    response = authenticated_client.get(f"/fiaps/{sheet_id}/pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        f"attachment; filename=fiap-{sheet_id}.pdf"
    )
    assert response.data.startswith(b"%PDF-")
    assert f"FIAP - Ficha {sheet_id}".encode() in response.data


def test_fiap_uses_exact_25_percent_absence_limit_for_fractional_workload(
    authenticated_client, app
):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records(workload_hours=70)

    response = authenticated_client.get("/fiaps/nova")
    assert response.status_code == 200
    assert b'id="absence_limit_hours"' in response.data
    assert b'readonly' in response.data
    assert b"17.50" in response.data

    response = authenticated_client.post(
        "/fiaps/nova",
        data=fiap_form_data(
            student_id,
            unit_id,
            class_id,
            absence_limit_hours="999",
        ),
    )
    assert response.status_code == 302
    preview_url = response.headers["Location"]
    response = authenticated_client.get(preview_url)
    assert b"<strong>17.50</strong>" in response.data

    response = authenticated_client.post(f"{preview_url}/salvar")
    assert response.status_code == 302
    with app.app_context():
        sheet = db.session.scalar(db.select(EvaluationSheet))
        assert sheet.absence_limit_hours == Decimal("17.50")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("class_average", "101"),
        ("student_grade", "101"),
        ("student_grade", "75.5"),
    ],
)
def test_fiap_grades_must_be_integers_between_zero_and_one_hundred(
    authenticated_client, app, field, value
):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()

    response = authenticated_client.post(
        "/fiaps/nova",
        data=fiap_form_data(student_id, unit_id, class_id, **{field: value}),
    )

    assert response.status_code == 200
    assert b'<span class="field-error">' in response.data
    with app.app_context():
        assert db.session.scalar(db.select(EvaluationDraft.id)) is None
        assert db.session.scalar(db.select(EvaluationSheet.id)) is None


def test_fiap_rejects_unit_from_a_different_course(authenticated_client, app):
    with app.app_context():
        student_id, _, class_id = create_fiap_records("Curso do aluno")
        other_course = Course(name="Outro curso")
        other_unit = CurricularUnit(
            name="Unidade incompatível",
            workload_hours=40,
            course=other_course,
        )
        db.session.add(other_unit)
        db.session.commit()
        unit_id = other_unit.id

    response = authenticated_client.post(
        "/fiaps/nova", data=fiap_form_data(student_id, unit_id, class_id)
    )

    assert response.status_code == 200
    assert b"n\xc3\xa3o pertence ao curso da turma" in response.data
    with app.app_context():
        assert db.session.scalar(db.select(EvaluationDraft.id)) is None
        assert db.session.scalar(db.select(EvaluationSheet.id)) is None


def test_fiap_accepts_zero_scores_and_zero_absences(authenticated_client, app):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()

    response = authenticated_client.post(
        "/fiaps/nova",
        data=fiap_form_data(
            student_id,
            unit_id,
            class_id,
            class_average="0",
            student_grade="0",
            absence_limit_hours="0",
            absences_hours="0",
        ),
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(EvaluationDraft.id)) is not None
        assert db.session.scalar(db.select(EvaluationSheet.id)) is None


def test_fiap_draft_is_private_to_its_teacher(authenticated_client, app):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()
        payload = {
            "student_id": student_id,
            "class_id": class_id,
            "curricular_unit_id": unit_id,
            "evaluated_on": "2026-11-16",
        }
        other_teacher = User(name="Outro Docente", email="outro-fiap@senai.br")
        other_teacher.set_password("Outra-senha-segura-123")
        db.session.add(other_teacher)
        db.session.commit()
        draft = EvaluationDraft(
            user_id=other_teacher.id,
            payload_json=json.dumps(payload),
            expires_at=4102444800,
        )
        db.session.add(draft)
        db.session.commit()
        draft_id = draft.id

    response = authenticated_client.get(f"/fiaps/pre-visualizar/{draft_id}")

    assert response.status_code == 404
    assert b"Aluno FIAP" not in response.data


def test_saved_fiap_is_only_visible_to_its_teacher(authenticated_client, app):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()
        other_teacher = User(name="Outro Docente", email="outro-docente@senai.br")
        other_teacher.set_password("Outra-senha-segura-123")
        db.session.add(other_teacher)
        db.session.commit()
        sheet = EvaluationSheet(
            student_id=student_id,
            class_id=class_id,
            teacher_id=other_teacher.id,
            curricular_unit_id=unit_id,
            evaluated_on=date(2026, 11, 16),
            workload_hours=80,
            class_average=75,
            student_grade=82,
            absence_limit_hours=40,
            absences_hours=12,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id

    response = authenticated_client.get(f"/fiaps/{sheet_id}")

    assert response.status_code == 404
    response = authenticated_client.get(f"/fiaps/{sheet_id}/pdf")
    assert response.status_code == 404


def test_saved_fiap_prevents_deleting_its_linked_records(
    authenticated_client, app
):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()
        teacher = db.session.scalar(
            db.select(User).where(User.email == "fiap@senai.br")
        )
        sheet = EvaluationSheet(
            student_id=student_id,
            class_id=class_id,
            teacher_id=teacher.id,
            curricular_unit_id=unit_id,
            evaluated_on=date(2026, 11, 16),
            workload_hours=80,
            class_average=75,
            student_grade=82,
            absence_limit_hours=40,
            absences_hours=12,
        )
        db.session.add(sheet)
        db.session.commit()

    for path in (
        f"/alunos/{student_id}/excluir",
        f"/cadastros/unidades-curriculares/{unit_id}/excluir",
        f"/cadastros/turmas/{class_id}/excluir",
    ):
        response = authenticated_client.post(path)
        assert response.status_code == 302

    with app.app_context():
        assert db.session.get(Student, student_id) is not None
        assert db.session.get(CurricularUnit, unit_id) is not None
        assert db.session.get(ClassGroup, class_id) is not None
        assert db.session.query(EvaluationSheet).count() == 1


def test_fiap_pages_require_authentication(client):
    response = client.get("/fiaps/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_fiap_students_endpoint_returns_only_students_from_selected_class(
    authenticated_client, app
):
    with app.app_context():
        student_id, _, class_id = create_fiap_records()
        other_course = Course(name="Curso de Outra Turma")
        other_class = ClassGroup(name="Outra turma", course=other_course)
        other_student = Student(name="Outro aluno", class_group=other_class)
        db.session.add(other_student)
        db.session.commit()

    response = authenticated_client.get(
        f"/fiaps/alunos-da-turma?class_id={class_id}"
    )

    assert response.status_code == 200
    assert response.json == [{"id": student_id, "name": "Aluno FIAP"}]


def test_pdf_export_keeps_long_comments_on_continuation_pages(
    authenticated_client, app
):
    with app.app_context():
        student_id, unit_id, class_id = create_fiap_records()
        teacher = db.session.scalar(
            db.select(User).where(User.email == "fiap@senai.br")
        )
        sheet = EvaluationSheet(
            student_id=student_id,
            class_id=class_id,
            teacher_id=teacher.id,
            curricular_unit_id=unit_id,
            evaluated_on=date(2026, 11, 16),
            workload_hours=80,
            class_average=75,
            student_grade=82,
            absence_limit_hours=20,
            absences_hours=12,
            observations=f"{'comentario longo ' * 225}FINALCHUNK",
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id

    response = authenticated_client.get(f"/fiaps/{sheet_id}/pdf")

    assert response.status_code == 200
    assert response.data.count(b"/Type /Page\n") > 1
    assert b"FINALCHUNK" in response.data
