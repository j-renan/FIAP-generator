from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


class EvaluationForm(FlaskForm):
    class_id = SelectField(
        "Turma",
        coerce=int,
        validators=[DataRequired(message="Selecione uma turma.")],
        choices=[SelectChoice("0", "Selecione uma turma")],
    )
    student_id = SelectField(
        "Nome do aluno",
        coerce=int,
        validators=[DataRequired(message="Selecione um aluno.")],
        choices=[SelectChoice("0", "Selecione um aluno")],
    )
    curricular_unit_id = SelectField(
        "Unidade curricular",
        coerce=int,
        validators=[DataRequired(message="Selecione uma unidade curricular.")],
        choices=[SelectChoice("0", "Selecione uma unidade curricular")],
    )
    evaluated_on = DateField(
        "Data",
        format="%Y-%m-%d",
        default=date.today,
        validators=[DataRequired(message="Informe a data da avaliação.")],
    )
    company = StringField(
        "Empresa",
        validators=[Optional(), Length(max=200)],
        filters=[lambda value: value.strip() if value else ""],
        render_kw={"placeholder": "Nome da empresa, se aplicável"},
    )
    class_average = IntegerField(
        "Média da classe (0–100)",
        validators=[
            InputRequired(message="Informe a média da classe."),
            NumberRange(min=0, max=100, message="Informe um número inteiro de 0 a 100."),
        ],
        render_kw={"min": 0, "max": 100, "step": 1},
    )
    student_grade = IntegerField(
        "Nota do aluno (0–100)",
        validators=[
            InputRequired(message="Informe a nota do aluno."),
            NumberRange(min=0, max=100, message="Informe um número inteiro de 0 a 100."),
        ],
        render_kw={"min": 0, "max": 100, "step": 1},
    )
    absence_limit_hours = StringField(
        "Limite de horas/faltas",
        render_kw={"readonly": True, "placeholder": "Calculado pela unidade curricular"},
    )
    absences_hours = IntegerField(
        "Horas/faltas atingidas",
        validators=[
            InputRequired(message="Informe as horas/faltas atingidas."),
            NumberRange(min=0, max=10000, message="Informe um valor entre 0 e 10.000."),
        ],
        render_kw={"min": 0, "max": 10000, "step": 1},
    )
    difficulties = TextAreaField(
        "Principais dificuldades",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3, "maxlength": 4000},
    )
    recommendations = TextAreaField(
        "Recomendações do professor ao aluno/responsável",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3, "maxlength": 4000},
    )
    school_actions = TextAreaField(
        "Providências do professor e da escola para auxiliar o aluno",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3, "maxlength": 4000},
    )
    observations = TextAreaField(
        "Outras observações",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3, "maxlength": 4000},
    )
    submit = SubmitField("Pré-visualizar ficha")
