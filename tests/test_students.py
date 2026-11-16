from io import BytesIO
import time

import pytest
from openpyxl import Workbook

from app.extensions import db
from app.models import ClassGroup, Course, Student, StudentImportBatch, User
from app.models import EvaluationDraft


@pytest.fixture
def authenticated_client(client, app):
    with app.app_context():
        teacher = User(name="Docente Teste", email="alunos@senai.br")
        teacher.set_password("Senha-segura-123")
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id

    with client.session_transaction() as session:
        session["_user_id"] = str(teacher_id)
        session["_fresh"] = True

    return client


def create_class():
    course = Course(name="Curso de Alunos")
    class_group = ClassGroup(name="1DSA", course=course)
    db.session.add(class_group)
    db.session.commit()
    return class_group.id


def create_xlsx(rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Nome do Aluno"])
    for row in rows:
        worksheet.append([row])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_student_registration_links_class_and_rejects_case_insensitive_duplicate(
    authenticated_client, app
):
    with app.app_context():
        class_id = create_class()

    response = authenticated_client.post(
        "/alunos/", data={"name": "  Ana Silva ", "class_id": str(class_id)}
    )
    assert response.status_code == 302

    response = authenticated_client.post(
        "/alunos/", data={"name": "ana silva", "class_id": str(class_id)}
    )
    assert response.status_code == 200
    assert b"Este aluno j\xc3\xa1 est\xc3\xa1 cadastrado" in response.data

    with app.app_context():
        students = db.session.scalars(db.select(Student)).all()
        assert len(students) == 1
        assert students[0].name == "Ana Silva"
        assert students[0].class_id == class_id


def test_student_pages_require_authentication(client):
    response = client.get("/alunos/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_student_list_loads_only_after_selecting_a_class(authenticated_client, app):
    with app.app_context():
        course = Course(name="Curso da Lista")
        first_class = ClassGroup(name="Turma A", course=course)
        second_class = ClassGroup(name="Turma B", course=course)
        db.session.add_all(
            [
                Student(name="Aluna Turma A", class_group=first_class),
                Student(name="Aluno Turma B", class_group=second_class),
            ]
        )
        db.session.commit()
        first_class_id = first_class.id

    response = authenticated_client.get("/alunos/")
    assert response.status_code == 200
    assert b"Selecione uma turma para carregar a lista" in response.data
    assert b"Aluna Turma A" not in response.data
    assert b"Aluno Turma B" not in response.data

    response = authenticated_client.get(f"/alunos/?class_id={first_class_id}")
    assert response.status_code == 200
    assert b"Aluna Turma A" in response.data
    assert b"Aluno Turma B" not in response.data


def test_csv_import_requires_preview_then_confirmation(authenticated_client, app):
    with app.app_context():
        class_id = create_class()

    response = authenticated_client.post(
        "/alunos/importar",
        data={
            "class_id": str(class_id),
            "file": (BytesIO("nome\nAna Silva\nBruno Souza\n".encode()), "alunos.csv"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    preview_url = response.headers["Location"]

    with app.app_context():
        assert db.session.scalar(db.select(Student.id)) is None
        batch = db.session.scalar(db.select(StudentImportBatch))
        assert batch is not None
        batch_id = batch.id

    response = authenticated_client.get(preview_url)
    assert response.status_code == 200
    assert b"Pronto para importar" in response.data
    assert b"Ana Silva" in response.data

    response = authenticated_client.post(f"{preview_url}/confirmar")
    assert response.status_code == 302

    with app.app_context():
        students = db.session.scalars(
            db.select(Student).order_by(Student.name)
        ).all()
        assert [student.name for student in students] == ["Ana Silva", "Bruno Souza"]
        assert db.session.get(StudentImportBatch, batch_id) is None


def test_xlsx_preview_blocks_existing_and_repeated_names(authenticated_client, app):
    with app.app_context():
        class_id = create_class()
        db.session.add(Student(name="Ana Silva", class_id=class_id))
        db.session.commit()

    response = authenticated_client.post(
        "/alunos/importar",
        data={
            "class_id": str(class_id),
            "file": (create_xlsx(["ana silva", "Bruno Souza", "BRUNO SOUZA"]), "alunos.xlsx"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    preview_url = response.headers["Location"]

    response = authenticated_client.get(preview_url)
    assert response.status_code == 200
    assert b"Corrija os erros antes de importar" in response.data
    assert b"Este aluno j\xc3\xa1 est\xc3\xa1 cadastrado na turma." in response.data
    assert b"Nome duplicado nesta planilha." in response.data
    assert b"Confirmar importa" not in response.data

    response = authenticated_client.post(f"{preview_url}/confirmar")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.query(Student).count() == 1


def test_invalid_csv_header_does_not_create_preview(authenticated_client, app):
    with app.app_context():
        class_id = create_class()

    response = authenticated_client.post(
        "/alunos/importar",
        data={
            "class_id": str(class_id),
            "file": (BytesIO("estudante\nAna Silva\n".encode()), "alunos.csv"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert b"A primeira coluna da planilha deve ter o cabe\xc3\xa7alho" in response.data
    with app.app_context():
        assert db.session.scalar(db.select(StudentImportBatch.id)) is None


def test_import_preview_is_private_and_expires(authenticated_client, app):
    with app.app_context():
        class_id = create_class()
        owner = db.session.scalar(
            db.select(User).where(User.email == "alunos@senai.br")
        )
        batch = StudentImportBatch(
            user_id=owner.id,
            class_id=class_id,
            rows_json='[{"row_number": 2, "name": "Aluno confidencial", "error": null}]',
            has_errors=False,
            expires_at=int(time.time()) + 600,
        )
        db.session.add(batch)
        db.session.commit()
        batch_id = batch.id
        batch.expires_at = int(time.time()) - 1
        db.session.commit()

    response = authenticated_client.get(f"/alunos/importar/{batch_id}")

    assert response.status_code == 404
    with app.app_context():
        assert db.session.get(StudentImportBatch, batch_id) is None


def test_import_preview_cannot_be_accessed_by_another_teacher(
    authenticated_client, app
):
    with app.app_context():
        class_id = create_class()
        other_teacher = User(name="Outra Docente", email="outra@senai.br")
        other_teacher.set_password("Outra-senha-segura-123")
        db.session.add(other_teacher)
        db.session.commit()
        batch = StudentImportBatch(
            user_id=other_teacher.id,
            class_id=class_id,
            rows_json='[{"row_number": 2, "name": "Aluno confidencial", "error": null}]',
            has_errors=False,
            expires_at=int(time.time()) + 600,
        )
        db.session.add(batch)
        db.session.commit()
        batch_id = batch.id

    response = authenticated_client.get(f"/alunos/importar/{batch_id}")

    assert response.status_code == 404
    assert b"Aluno confidencial" not in response.data


def test_cleanup_command_deletes_only_expired_previews(app):
    with app.app_context():
        class_id = create_class()
        teacher = User(name="Docente Limpeza", email="limpeza@senai.br")
        teacher.set_password("Senha-segura-123")
        db.session.add(teacher)
        db.session.commit()
        expired = StudentImportBatch(
            user_id=teacher.id,
            class_id=class_id,
            rows_json="[]",
            expires_at=int(time.time()) - 1,
        )
        active = StudentImportBatch(
            user_id=teacher.id,
            class_id=class_id,
            rows_json="[]",
            expires_at=int(time.time()) + 600,
        )
        expired_draft = EvaluationDraft(
            user_id=teacher.id,
            payload_json="{}",
            expires_at=int(time.time()) - 1,
        )
        db.session.add_all([expired, active, expired_draft])
        db.session.commit()
        active_id = active.id

    result = app.test_cli_runner().invoke(args=["cleanup-student-imports"])

    assert result.exit_code == 0
    with app.app_context():
        assert db.session.query(StudentImportBatch).count() == 1
        assert db.session.query(EvaluationDraft).count() == 0
        assert db.session.get(StudentImportBatch, active_id) is not None


def test_student_edit_and_delete(authenticated_client, app):
    with app.app_context():
        class_id = create_class()
        student = Student(name="Nome Inicial", class_id=class_id)
        db.session.add(student)
        db.session.commit()
        student_id = student.id

    response = authenticated_client.post(
        f"/alunos/{student_id}/editar",
        data={"name": "Nome Atualizado", "class_id": str(class_id)},
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Student, student_id).name == "Nome Atualizado"

    response = authenticated_client.post(f"/alunos/{student_id}/excluir")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Student, student_id) is None
