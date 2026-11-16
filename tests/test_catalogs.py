from decimal import Decimal

import pytest

from app.extensions import db
from app.models import ClassGroup, Course, CurricularUnit, User


@pytest.fixture
def authenticated_client(client, app):
    with app.app_context():
        teacher = User(name="Docente Teste", email="catalogos@senai.br")
        teacher.set_password("Senha-segura-123")
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id

    with client.session_transaction() as session:
        session["_user_id"] = str(teacher_id)
        session["_fresh"] = True

    return client


def create_course(name="Curso de Teste"):
    course = Course(name=name)
    db.session.add(course)
    db.session.commit()
    return course


@pytest.mark.parametrize(
    "path",
    [
        "/cadastros/cursos",
        "/cadastros/unidades-curriculares",
        "/cadastros/turmas",
    ],
)
def test_catalog_pages_require_authentication(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_course_page_renders_and_creates_course(authenticated_client):
    response = authenticated_client.get("/cadastros/cursos")

    assert response.status_code == 200
    assert b"Novo cadastro" in response.data

    response = authenticated_client.post(
        "/cadastros/cursos", data={"name": "  Curso de Sistemas  "}
    )

    assert response.status_code == 302
    with authenticated_client.application.app_context():
        course = db.session.scalar(
            db.select(Course).where(Course.name == "Curso de Sistemas")
        )
        assert course is not None


def test_curricular_unit_requires_course_and_positive_workload(
    authenticated_client, app
):
    with app.app_context():
        course = create_course()
        course_id = course.id

    response = authenticated_client.post(
        "/cadastros/unidades-curriculares",
        data={
            "name": "Programação",
            "course_id": str(course_id),
            "workload_hours": "0",
        },
    )
    assert response.status_code == 200
    assert b'<span class="field-error">' in response.data
    with app.app_context():
        assert db.session.scalar(db.select(CurricularUnit.id)) is None

    response = authenticated_client.post(
        "/cadastros/unidades-curriculares",
        data={
            "name": "Programação",
            "course_id": str(course_id),
            "workload_hours": "80",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        unit = db.session.scalar(
            db.select(CurricularUnit).where(CurricularUnit.name == "Programação")
        )
        assert unit is not None
        assert unit.course_id == course_id
        assert unit.workload_hours == 80
        assert unit.max_absence_hours == Decimal("20.00")

    response = authenticated_client.get("/cadastros/unidades-curriculares")
    assert b'id="max_absence_hours"' in response.data
    assert b'readonly' in response.data
    assert b"20 h" in response.data


def test_class_is_linked_to_course_and_course_cannot_be_deleted(
    authenticated_client, app
):
    with app.app_context():
        course = create_course()
        course_id = course.id

    response = authenticated_client.post(
        "/cadastros/turmas",
        data={"name": "1DSA", "course_id": str(course_id)},
    )
    assert response.status_code == 302

    with app.app_context():
        class_group = db.session.scalar(
            db.select(ClassGroup).where(ClassGroup.name == "1DSA")
        )
        assert class_group is not None
        assert class_group.course_id == course_id

    response = authenticated_client.post(f"/cadastros/cursos/{course_id}/excluir")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Course, course_id) is not None


def test_duplicate_course_is_reported_without_creating_duplicate(
    authenticated_client, app
):
    with app.app_context():
        create_course("Curso Duplicado")

    response = authenticated_client.post(
        "/cadastros/cursos", data={"name": "Curso Duplicado"}
    )

    assert response.status_code == 200
    assert b"J\xc3\xa1 existe um curso com esse nome." in response.data
    with app.app_context():
        assert db.session.query(Course).filter_by(name="Curso Duplicado").count() == 1


def test_catalogs_support_edit_and_delete(authenticated_client, app):
    with app.app_context():
        course = create_course("Curso Original")
        course_id = course.id

    response = authenticated_client.post(
        f"/cadastros/cursos/{course_id}/editar",
        data={"name": "Curso Atualizado"},
    )
    assert response.status_code == 302

    with app.app_context():
        unit = CurricularUnit(
            name="Unidade Original", course_id=course_id, workload_hours=40
        )
        class_group = ClassGroup(name="Turma Original", course_id=course_id)
        db.session.add_all([unit, class_group])
        db.session.commit()
        unit_id = unit.id
        class_id = class_group.id
        assert unit.max_absence_hours == Decimal("10.00")

    response = authenticated_client.post(
        f"/cadastros/unidades-curriculares/{unit_id}/editar",
        data={
            "name": "Unidade Atualizada",
            "course_id": str(course_id),
            "workload_hours": "60",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        unit = db.session.get(CurricularUnit, unit_id)
        assert unit.workload_hours == 60
        assert unit.max_absence_hours == Decimal("15.00")

    response = authenticated_client.post(
        f"/cadastros/turmas/{class_id}/editar",
        data={"name": "Turma Atualizada", "course_id": str(course_id)},
    )
    assert response.status_code == 302

    for path in (
        "/cadastros/cursos",
        "/cadastros/unidades-curriculares",
        "/cadastros/turmas",
    ):
        response = authenticated_client.get(path)
        assert response.status_code == 200
        assert b"Editar" in response.data

    response = authenticated_client.post(
        f"/cadastros/unidades-curriculares/{unit_id}/excluir"
    )
    assert response.status_code == 302
    response = authenticated_client.post(f"/cadastros/turmas/{class_id}/excluir")
    assert response.status_code == 302

    with app.app_context():
        assert db.session.get(CurricularUnit, unit_id) is None
        assert db.session.get(ClassGroup, class_id) is None
        assert db.session.get(Course, course_id).name == "Curso Atualizado"
