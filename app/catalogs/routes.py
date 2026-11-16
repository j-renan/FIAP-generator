from decimal import Decimal

from flask import flash, redirect, render_template, url_for
from flask_login import login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.fields.choices import SelectChoice

from . import bp
from .forms import ClassForm, CourseForm, CurricularUnitForm
from ..extensions import db
from ..models import ClassGroup, Course, CurricularUnit


def _set_course_choices(form):
    courses = db.session.scalars(select(Course).order_by(Course.name)).all()
    form.course_id.choices = [SelectChoice("0", "Selecione um curso")] + [
        SelectChoice(str(course.id), course.name) for course in courses
    ]


def _render_catalog(
    title,
    description,
    form,
    records,
    columns,
    rows,
    edit_endpoint,
    delete_endpoint,
    edit_id=None,
):
    return render_template(
        "catalogs/list.html",
        title=title,
        description=description,
        form=form,
        records=records,
        columns=columns,
        rows=rows,
        edit_endpoint=edit_endpoint,
        delete_endpoint=delete_endpoint,
        edit_id=edit_id,
    )


def _commit_or_flash(message):
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        flash(message, "error")
        return False


def _course_rows(courses):
    return [{"id": course.id, "values": (course.name,)} for course in courses]


def _unit_rows(units):
    return [
        {
            "id": unit.id,
            "values": (
                unit.name,
                unit.course.name,
                f"{unit.workload_hours} h",
                f"{unit.max_absence_hours.normalize():f} h",
            ),
        }
        for unit in units
    ]


def _update_max_absence_display(form):
    workload_hours = form.workload_hours.data
    form.max_absence_hours.data = (
        f"{Decimal(workload_hours) * Decimal('0.25'):.2f}"
        if workload_hours
        else ""
    )


def _class_rows(classes):
    return [
        {"id": class_group.id, "values": (class_group.name, class_group.course.name)}
        for class_group in classes
    ]


@bp.route("/cursos", methods=["GET", "POST"])
@login_required
def courses():
    form = CourseForm()
    if form.validate_on_submit():
        course = Course(name=form.name.data)
        db.session.add(course)
        if _commit_or_flash("Já existe um curso com esse nome."):
            flash("Curso cadastrado com sucesso.", "success")
            return redirect(url_for("catalogs.courses"))

    records = db.session.scalars(select(Course).order_by(Course.name)).all()
    return _render_catalog(
        "Cursos",
        "Cadastre os cursos oferecidos pela unidade.",
        form,
        records,
        ("Nome do curso",),
        _course_rows(records),
        "catalogs.edit_course",
        "catalogs.delete_course",
    )


@bp.route("/cursos/<int:record_id>/editar", methods=["GET", "POST"])
@login_required
def edit_course(record_id):
    course = db.get_or_404(Course, record_id)
    form = CourseForm(obj=course)
    if form.validate_on_submit():
        course.name = form.name.data
        if _commit_or_flash("Já existe um curso com esse nome."):
            flash("Curso atualizado com sucesso.", "success")
            return redirect(url_for("catalogs.courses"))

    records = db.session.scalars(select(Course).order_by(Course.name)).all()
    return _render_catalog(
        "Cursos",
        "Cadastre os cursos oferecidos pela unidade.",
        form,
        records,
        ("Nome do curso",),
        _course_rows(records),
        "catalogs.edit_course",
        "catalogs.delete_course",
        edit_id=course.id,
    )


@bp.post("/cursos/<int:record_id>/excluir")
@login_required
def delete_course(record_id):
    course = db.get_or_404(Course, record_id)
    if course.curricular_units or course.classes:
        flash("Remova as unidades curriculares e turmas vinculadas antes de excluir o curso.", "error")
    else:
        db.session.delete(course)
        if _commit_or_flash("Não foi possível excluir o curso. Verifique se ele possui registros vinculados."):
            flash("Curso excluído.", "success")
    return redirect(url_for("catalogs.courses"))


@bp.route("/unidades-curriculares", methods=["GET", "POST"])
@login_required
def curricular_units():
    form = CurricularUnitForm()
    _set_course_choices(form)
    _update_max_absence_display(form)
    if form.validate_on_submit():
        max_absence_hours = Decimal(form.workload_hours.data) * Decimal("0.25")
        unit = CurricularUnit(
            name=form.name.data,
            course_id=form.course_id.data,
            workload_hours=form.workload_hours.data,
            max_absence_hours=max_absence_hours,
        )
        db.session.add(unit)
        if _commit_or_flash("Já existe uma unidade curricular com esse nome nesse curso."):
            flash("Unidade curricular cadastrada com sucesso.", "success")
            return redirect(url_for("catalogs.curricular_units"))

    units = db.session.scalars(
        select(CurricularUnit).join(Course).order_by(Course.name, CurricularUnit.name)
    ).all()
    return _render_catalog(
        "Unidades curriculares",
        "Defina as unidades curriculares e suas cargas horárias por curso.",
        form,
        units,
        (
            "Unidade curricular",
            "Curso",
            "Carga horária",
            "Limite máximo de faltas (25%)",
        ),
        _unit_rows(units),
        "catalogs.edit_curricular_unit",
        "catalogs.delete_curricular_unit",
    )


@bp.route("/unidades-curriculares/<int:record_id>/editar", methods=["GET", "POST"])
@login_required
def edit_curricular_unit(record_id):
    unit = db.get_or_404(CurricularUnit, record_id)
    form = CurricularUnitForm(obj=unit)
    _set_course_choices(form)
    _update_max_absence_display(form)
    if form.validate_on_submit():
        unit.name = form.name.data
        unit.course_id = form.course_id.data
        unit.workload_hours = form.workload_hours.data
        unit.max_absence_hours = (
            Decimal(form.workload_hours.data) * Decimal("0.25")
        )
        if _commit_or_flash("Já existe uma unidade curricular com esse nome nesse curso."):
            flash("Unidade curricular atualizada com sucesso.", "success")
            return redirect(url_for("catalogs.curricular_units"))

    units = db.session.scalars(
        select(CurricularUnit).join(Course).order_by(Course.name, CurricularUnit.name)
    ).all()
    return _render_catalog(
        "Unidades curriculares",
        "Defina as unidades curriculares e suas cargas horárias por curso.",
        form,
        units,
        (
            "Unidade curricular",
            "Curso",
            "Carga horária",
            "Limite máximo de faltas (25%)",
        ),
        _unit_rows(units),
        "catalogs.edit_curricular_unit",
        "catalogs.delete_curricular_unit",
        edit_id=unit.id,
    )


@bp.post("/unidades-curriculares/<int:record_id>/excluir")
@login_required
def delete_curricular_unit(record_id):
    unit = db.get_or_404(CurricularUnit, record_id)
    if unit.evaluation_sheets:
        flash("A unidade curricular está vinculada a fichas e não pode ser excluída.", "error")
    else:
        db.session.delete(unit)
        if _commit_or_flash("Não foi possível excluir a unidade curricular."):
            flash("Unidade curricular excluída.", "success")
    return redirect(url_for("catalogs.curricular_units"))


@bp.route("/turmas", methods=["GET", "POST"])
@login_required
def classes():
    form = ClassForm()
    _set_course_choices(form)
    if form.validate_on_submit():
        class_group = ClassGroup(
            name=form.name.data, course_id=form.course_id.data
        )
        db.session.add(class_group)
        if _commit_or_flash("Já existe uma turma com esse nome nesse curso."):
            flash("Turma cadastrada com sucesso.", "success")
            return redirect(url_for("catalogs.classes"))

    records = db.session.scalars(
        select(ClassGroup).join(Course).order_by(Course.name, ClassGroup.name)
    ).all()
    return _render_catalog(
        "Turmas",
        "Organize as turmas vinculadas a cada curso.",
        form,
        records,
        ("Nome da turma", "Curso"),
        _class_rows(records),
        "catalogs.edit_class",
        "catalogs.delete_class",
    )


@bp.route("/turmas/<int:record_id>/editar", methods=["GET", "POST"])
@login_required
def edit_class(record_id):
    class_group = db.get_or_404(ClassGroup, record_id)
    form = ClassForm(obj=class_group)
    _set_course_choices(form)
    if form.validate_on_submit():
        class_group.name = form.name.data
        class_group.course_id = form.course_id.data
        if _commit_or_flash("Já existe uma turma com esse nome nesse curso."):
            flash("Turma atualizada com sucesso.", "success")
            return redirect(url_for("catalogs.classes"))

    records = db.session.scalars(
        select(ClassGroup).join(Course).order_by(Course.name, ClassGroup.name)
    ).all()
    return _render_catalog(
        "Turmas",
        "Organize as turmas vinculadas a cada curso.",
        form,
        records,
        ("Nome da turma", "Curso"),
        _class_rows(records),
        "catalogs.edit_class",
        "catalogs.delete_class",
        edit_id=class_group.id,
    )


@bp.post("/turmas/<int:record_id>/excluir")
@login_required
def delete_class(record_id):
    class_group = db.get_or_404(ClassGroup, record_id)
    if class_group.students or class_group.evaluation_sheets:
        flash("Exclua os alunos vinculados à turma antes de removê-la.", "error")
    else:
        db.session.delete(class_group)
        if _commit_or_flash("Não foi possível excluir a turma. Verifique se há prévias vinculadas."):
            flash("Turma excluída.", "success")
    return redirect(url_for("catalogs.classes"))
