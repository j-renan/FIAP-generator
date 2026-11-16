import json
import time

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.fields.choices import SelectChoice
from werkzeug.exceptions import RequestEntityTooLarge

from . import bp
from .forms import StudentForm, StudentImportForm
from .import_service import StudentImportError, parse_student_file, validate_student_rows
from ..extensions import db
from ..models import ClassGroup, Student, StudentImportBatch
from ..services import cleanup_expired_previews


IMPORT_PREVIEW_TTL_SECONDS = 30 * 60


def _set_class_choices(form):
    classes = db.session.scalars(
        select(ClassGroup).order_by(ClassGroup.name)
    ).all()
    form.class_id.choices = [SelectChoice("0", "Selecione uma turma")] + [
        SelectChoice(str(class_group.id), class_group.name)
        for class_group in classes
    ]
    return classes


def _student_rows(students):
    return [
        {
            "id": student.id,
            "values": (student.name, student.class_group.name),
        }
        for student in students
    ]


def _render_students(form, edit_id=None, selected_class_id=None):
    classes = db.session.scalars(
        select(ClassGroup).order_by(ClassGroup.name)
    ).all()
    students = []
    if selected_class_id is not None:
        students = db.session.scalars(
            select(Student)
            .where(Student.class_id == selected_class_id)
            .order_by(Student.name)
        ).all()
    return render_template(
        "students/list.html",
        form=form,
        classes=classes,
        records=students,
        rows=_student_rows(students),
        edit_id=edit_id,
        selected_class_id=selected_class_id,
    )


def _student_name_exists(name, class_id, excluding_id=None):
    statement = select(Student.id, Student.name).where(Student.class_id == class_id)
    if excluding_id is not None:
        statement = statement.where(Student.id != excluding_id)
    return any(
        existing_name.casefold() == name.casefold()
        for _, existing_name in db.session.execute(statement)
    )


def _get_owned_batch(batch_id):
    batch = db.session.scalar(
        select(StudentImportBatch).where(
            StudentImportBatch.id == batch_id,
            StudentImportBatch.user_id == current_user.id,
        )
    )
    if batch is None:
        abort(404)
    return batch


def _existing_names(class_id):
    return db.session.scalars(
        select(Student.name).where(Student.class_id == class_id)
    ).all()


def _load_batch_rows(batch):
    return json.loads(batch.rows_json)


def _update_batch_validation(batch, rows):
    batch.rows_json = json.dumps(rows, ensure_ascii=False)
    batch.has_errors = any(row["error"] for row in rows)


@bp.app_errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    return render_template("students/upload_error.html"), 413


@bp.route("/", methods=["GET", "POST"])
@login_required
def list_students():
    form = StudentForm()
    classes = _set_class_choices(form)
    selected_class_id = request.args.get("class_id", type=int)
    if selected_class_id is not None and selected_class_id not in {
        class_group.id for class_group in classes
    }:
        abort(404)

    if form.validate_on_submit():
        if _student_name_exists(form.name.data, form.class_id.data):
            flash("Este aluno já está cadastrado na turma selecionada.", "error")
        else:
            student = Student(name=form.name.data, class_id=form.class_id.data)
            db.session.add(student)
            try:
                db.session.commit()
                flash("Aluno cadastrado com sucesso.", "success")
                return redirect(
                    url_for("students.list_students", class_id=form.class_id.data)
                )
            except IntegrityError:
                db.session.rollback()
                flash("Este aluno já está cadastrado na turma selecionada.", "error")

    return _render_students(form, selected_class_id=selected_class_id)


@bp.route("/<int:record_id>/editar", methods=["GET", "POST"])
@login_required
def edit_student(record_id):
    student = db.get_or_404(Student, record_id)
    form = StudentForm(obj=student)
    _set_class_choices(form)
    if form.validate_on_submit():
        if _student_name_exists(
            form.name.data, form.class_id.data, excluding_id=student.id
        ):
            flash("Este aluno já está cadastrado na turma selecionada.", "error")
        else:
            student.name = form.name.data
            student.class_id = form.class_id.data
            try:
                db.session.commit()
                flash("Aluno atualizado com sucesso.", "success")
                return redirect(
                    url_for("students.list_students", class_id=form.class_id.data)
                )
            except IntegrityError:
                db.session.rollback()
                flash("Este aluno já está cadastrado na turma selecionada.", "error")

    return _render_students(
        form,
        edit_id=student.id,
        selected_class_id=student.class_id,
    )


@bp.post("/<int:record_id>/excluir")
@login_required
def delete_student(record_id):
    student = db.get_or_404(Student, record_id)
    class_id = student.class_id
    if student.evaluation_sheets:
        flash("O aluno possui fichas de avaliação e não pode ser excluído.", "error")
    else:
        db.session.delete(student)
        try:
            db.session.commit()
            flash("Aluno excluído.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível excluir o aluno porque existem registros vinculados.", "error")
    return redirect(url_for("students.list_students", class_id=class_id))


@bp.route("/importar", methods=["GET", "POST"])
@login_required
def import_students():
    cleanup_expired_previews()
    form = StudentImportForm()
    classes = _set_class_choices(form)
    if form.validate_on_submit():
        try:
            rows = parse_student_file(form.file.data)
        except StudentImportError as error:
            flash(str(error), "error")
            return render_template("students/import.html", form=form, classes=classes)

        rows = validate_student_rows(rows, _existing_names(form.class_id.data))
        batch = StudentImportBatch(
            user_id=current_user.id,
            class_id=form.class_id.data,
            rows_json=json.dumps(rows, ensure_ascii=False),
            has_errors=any(row["error"] for row in rows),
            expires_at=int(time.time()) + IMPORT_PREVIEW_TTL_SECONDS,
        )
        db.session.add(batch)
        db.session.commit()
        return redirect(url_for("students.preview_import", batch_id=batch.id))

    return render_template("students/import.html", form=form, classes=classes)


@bp.get("/importar/<string:batch_id>")
@login_required
def preview_import(batch_id):
    cleanup_expired_previews()
    batch = _get_owned_batch(batch_id)
    rows = _load_batch_rows(batch)
    return render_template(
        "students/import.html",
        form=None,
        classes=[],
        batch=batch,
        rows=rows,
    )


@bp.post("/importar/<string:batch_id>/confirmar")
@login_required
def confirm_import(batch_id):
    cleanup_expired_previews()
    batch = _get_owned_batch(batch_id)
    rows = _load_batch_rows(batch)

    if batch.has_errors:
        flash("Corrija os erros da planilha antes de confirmar a importação.", "error")
        return redirect(url_for("students.preview_import", batch_id=batch.id))

    rows = validate_student_rows(rows, _existing_names(batch.class_id))
    _update_batch_validation(batch, rows)
    if batch.has_errors:
        db.session.commit()
        flash("Os dados mudaram desde a prévia. Revise os erros antes de importar.", "error")
        return redirect(url_for("students.preview_import", batch_id=batch.id))

    students = [
        Student(name=row["name"], class_id=batch.class_id)
        for row in rows
    ]
    class_id = batch.class_id
    db.session.add_all(students)
    db.session.delete(batch)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            "Não foi possível importar. Os dados podem ter sido alterados desde a prévia; valide a planilha novamente.",
            "error",
        )
        return redirect(url_for("students.import_students"))

    flash(f"{len(students)} alunos importados com sucesso.", "success")
    return redirect(
        url_for("students.list_students", class_id=class_id)
    )


@bp.post("/importar/<string:batch_id>/descartar")
@login_required
def cancel_import(batch_id):
    cleanup_expired_previews()
    batch = _get_owned_batch(batch_id)
    db.session.delete(batch)
    db.session.commit()
    flash("Pré-visualização descartada.", "info")
    return redirect(url_for("students.import_students"))
