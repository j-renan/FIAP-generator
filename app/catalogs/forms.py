from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, Length, NumberRange


class CourseForm(FlaskForm):
    name = StringField(
        "Nome do curso",
        validators=[
            DataRequired(message="Informe o nome do curso."),
            Length(max=160, message="O nome deve ter no máximo 160 caracteres."),
        ],
        filters=[lambda value: value.strip() if value else value],
        render_kw={"placeholder": "Ex.: Técnico em Desenvolvimento de Sistemas"},
    )
    submit = SubmitField("Salvar curso")


class CurricularUnitForm(FlaskForm):
    name = StringField(
        "Nome da unidade curricular",
        validators=[
            DataRequired(message="Informe o nome da unidade curricular."),
            Length(max=160, message="O nome deve ter no máximo 160 caracteres."),
        ],
        filters=[lambda value: value.strip() if value else value],
        render_kw={"placeholder": "Ex.: Programação de Aplicativos"},
    )
    course_id = SelectField(
        "Curso",
        coerce=int,
        validators=[DataRequired(message="Selecione um curso.")],
        choices=[SelectChoice("0", "Selecione um curso")],
    )
    workload_hours = IntegerField(
        "Carga horária (horas)",
        validators=[
            DataRequired(message="Informe a carga horária."),
            NumberRange(
                min=1,
                max=10000,
                message="A carga horária deve estar entre 1 e 10.000 horas.",
            ),
        ],
        render_kw={"min": 1, "max": 10000, "placeholder": "Ex.: 80"},
    )
    max_absence_hours = StringField(
        "Limite máximo de faltas (25%)",
        render_kw={"readonly": True, "placeholder": "Calculado pela carga horária"},
    )
    submit = SubmitField("Salvar unidade curricular")


class ClassForm(FlaskForm):
    name = StringField(
        "Nome da turma",
        validators=[
            DataRequired(message="Informe o nome da turma."),
            Length(max=120, message="O nome deve ter no máximo 120 caracteres."),
        ],
        filters=[lambda value: value.strip() if value else value],
        render_kw={"placeholder": "Ex.: 1DSA"},
    )
    course_id = SelectField(
        "Curso",
        coerce=int,
        validators=[DataRequired(message="Selecione um curso.")],
        choices=[SelectChoice("0", "Selecione um curso")],
    )
    submit = SubmitField("Salvar turma")
