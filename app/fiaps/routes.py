import json
import time
from datetime import date
from io import BytesIO

from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from wtforms.fields.choices import SelectChoice

from . import bp
from .forms import EvaluationForm
from .pdf import build_sheet_pdf
from ..extensions import db
from ..models import (
    ClassGroup,
    CurricularUnit,
    EvaluationDraft,
    EvaluationSheet,
    Student,
)
from ..services import cleanup_expired_previews


PREVIEW_TTL_SECONDS = 30 * 60
TEXT_FIELDS = ("difficulties", "recommendations", "school_actions", "observations")


def _set_form_choices(form):
    classes = db.session.scalars(select(ClassGroup).order_by(ClassGroup.name)).all()
    form.class_id.choices = [SelectChoice("0", "Selecione uma turma")] + [
        SelectChoice(str(class_group.id), class_group.name)
        for class_group in classes
    ]
    selected_class_id = form.class_id.data
    if selected_class_id not in {class_group.id for class_group in classes}:
        selected_class_id = 0
    students = []
    if selected_class_id:
        students = db.session.scalars(
            select(Student)
            .where(Student.class_id == selected_class_id)
            .order_by(Student.name)
        ).all()
    form.student_id.choices = [SelectChoice("0", "Selecione um aluno")] + [
        SelectChoice(str(student.id), student.name) for student in students
    ]
    units = db.session.scalars(
        select(CurricularUnit).join(CurricularUnit.course).order_by(
            CurricularUnit.name
        )
    ).all()
    form.curricular_unit_id.choices = [
        SelectChoice("0", "Selecione uma unidade curricular")
    ] + [
        SelectChoice(
            str(unit.id),
            f"{unit.name} — {unit.course.name} ({unit.workload_hours} h)",
        )
        for unit in units
    ]
    return classes, students, units


def _get_owned_draft(draft_id):
    draft = db.session.scalar(
        select(EvaluationDraft).where(
            EvaluationDraft.id == draft_id,
            EvaluationDraft.user_id == current_user.id,
        )
    )
    if draft is None:
        abort(404)
    return draft


def _load_draft(draft):
    return json.loads(draft.payload_json)


def _association_error(class_id, student_id, unit_id):
    student = db.session.get(Student, student_id)
    unit = db.session.get(CurricularUnit, unit_id)
    if student is None or unit is None:
        return "O aluno ou a unidade curricular não está mais disponível."
    if student.class_id != class_id:
        return "O aluno selecionado não pertence à turma escolhida."
    if student.class_group.course_id != unit.course_id:
        return "A unidade curricular selecionada não pertence ao curso da turma do aluno."
    return None


def _render_form(form, classes, students, units):
    return render_template(
        "fiaps/form.html",
        form=form,
        classes=classes,
        students=students,
        units=units,
        unit_absence_limits={
            str(unit.id): format(unit.max_absence_hours, "f") for unit in units
        },
    )


def _draft_payload(form, student, unit):
    return {
        "student_id": student.id,
        "class_id": form.class_id.data,
        "curricular_unit_id": unit.id,
        "evaluated_on": form.evaluated_on.data.isoformat(),
        "company": form.company.data or "",
        "workload_hours": unit.workload_hours,
        "class_average": form.class_average.data,
        "student_grade": form.student_grade.data,
        "absence_limit_hours": format(unit.max_absence_hours, "f"),
        "absences_hours": form.absences_hours.data,
        **{field: getattr(form, field).data or "" for field in TEXT_FIELDS},
    }


def _detail_context(sheet):
    return {
        "sheet": sheet,
        "student": sheet.student,
        "class_group": sheet.class_group,
        "teacher": sheet.teacher,
        "unit": sheet.curricular_unit,
    }


def _get_owned_sheet(sheet_id):
    sheet = db.session.scalar(
        select(EvaluationSheet).where(
            EvaluationSheet.id == sheet_id,
            EvaluationSheet.teacher_id == current_user.id,
        )
    )
    if sheet is None:
        abort(404)
    return sheet


@bp.get("/")
@login_required
def list_sheets():
    sheets = db.session.scalars(
        select(EvaluationSheet)
        .where(EvaluationSheet.teacher_id == current_user.id)
        .order_by(EvaluationSheet.evaluated_on.desc(), EvaluationSheet.id.desc())
    ).all()
    return render_template("fiaps/list.html", sheets=sheets)


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def create_sheet():
    form = EvaluationForm()
    classes, students, units = _set_form_choices(form)

    if form.validate_on_submit():
        error = _association_error(
            form.class_id.data,
            form.student_id.data,
            form.curricular_unit_id.data,
        )
        if error:
            flash(error, "error")
            return _render_form(form, classes, students, units)

        student = db.session.get(Student, form.student_id.data)
        unit = db.session.get(CurricularUnit, form.curricular_unit_id.data)
        draft = EvaluationDraft(
            user_id=current_user.id,
            payload_json=json.dumps(
                _draft_payload(form, student, unit),
                ensure_ascii=False,
            ),
            expires_at=int(time.time()) + PREVIEW_TTL_SECONDS,
        )
        db.session.add(draft)
        db.session.commit()
        return redirect(url_for("fiaps.preview_sheet", draft_id=draft.id))

    return _render_form(form, classes, students, units)


@bp.get("/alunos-da-turma")
@login_required
def students_for_class():
    class_id = request.args.get("class_id", type=int)
    if class_id is None or class_id < 1:
        abort(400)
    db.get_or_404(ClassGroup, class_id)
    students = db.session.scalars(
        select(Student)
        .where(Student.class_id == class_id)
        .order_by(Student.name)
    ).all()
    return jsonify([{"id": student.id, "name": student.name} for student in students])


@bp.get("/pre-visualizar/<string:draft_id>")
@login_required
def preview_sheet(draft_id):
    cleanup_expired_previews()
    draft = _get_owned_draft(draft_id)
    payload = _load_draft(draft)
    student = db.get_or_404(Student, payload["student_id"])
    unit = db.get_or_404(CurricularUnit, payload["curricular_unit_id"])
    class_group = db.get_or_404(ClassGroup, payload["class_id"])
    return render_template(
        "fiaps/preview.html",
        draft=draft,
        payload=payload,
        student=student,
        unit=unit,
        class_group=class_group,
        evaluated_on=date.fromisoformat(payload["evaluated_on"]),
    )


@bp.post("/pre-visualizar/<string:draft_id>/salvar")
@login_required
def save_sheet(draft_id):
    cleanup_expired_previews()
    draft = _get_owned_draft(draft_id)
    payload = _load_draft(draft)
    error = _association_error(
        payload["class_id"],
        payload["student_id"],
        payload["curricular_unit_id"],
    )
    if error:
        db.session.delete(draft)
        db.session.commit()
        flash(error, "error")
        return redirect(url_for("fiaps.create_sheet"))

    sheet = EvaluationSheet(
        student_id=payload["student_id"],
        class_id=payload["class_id"],
        teacher_id=current_user.id,
        curricular_unit_id=payload["curricular_unit_id"],
        evaluated_on=date.fromisoformat(payload["evaluated_on"]),
        company=payload["company"],
        workload_hours=payload["workload_hours"],
        class_average=payload["class_average"],
        student_grade=payload["student_grade"],
        absence_limit_hours=payload["absence_limit_hours"],
        absences_hours=payload["absences_hours"],
        **{field: payload[field] for field in TEXT_FIELDS},
    )
    db.session.add(sheet)
    db.session.delete(draft)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível salvar a ficha. Verifique os cadastros associados.", "error")
        return redirect(url_for("fiaps.create_sheet"))

    flash("Ficha salva com sucesso.", "success")
    return redirect(url_for("fiaps.sheet_detail", sheet_id=sheet.id))


@bp.post("/pre-visualizar/<string:draft_id>/descartar")
@login_required
def discard_sheet(draft_id):
    cleanup_expired_previews()
    draft = _get_owned_draft(draft_id)
    db.session.delete(draft)
    db.session.commit()
    flash("Pré-visualização descartada.", "info")
    return redirect(url_for("fiaps.create_sheet"))


@bp.get("/<int:sheet_id>")
@login_required
def sheet_detail(sheet_id):
    sheet = _get_owned_sheet(sheet_id)
    return render_template("fiaps/detail.html", **_detail_context(sheet))


@bp.get("/<int:sheet_id>/pdf")
@login_required
def export_sheet_pdf(sheet_id):
    sheet = _get_owned_sheet(sheet_id)
    return send_file(
        BytesIO(build_sheet_pdf(sheet)),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"fiap-{sheet.id}.pdf",
        max_age=0,
    )
