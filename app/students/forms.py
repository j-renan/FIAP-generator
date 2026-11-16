from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SelectField, StringField, SubmitField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, Length


class StudentForm(FlaskForm):
    name = StringField(
        "Nome do aluno",
        validators=[
            DataRequired(message="Informe o nome do aluno."),
            Length(max=160, message="O nome deve ter no máximo 160 caracteres."),
        ],
        filters=[lambda value: value.strip() if value else value],
        render_kw={"placeholder": "Nome completo do aluno"},
    )
    class_id = SelectField(
        "Turma",
        coerce=int,
        validators=[DataRequired(message="Selecione uma turma.")],
        choices=[SelectChoice("0", "Selecione uma turma")],
    )
    submit = SubmitField("Salvar aluno")


class StudentImportForm(FlaskForm):
    class_id = SelectField(
        "Turma de destino",
        coerce=int,
        validators=[DataRequired(message="Selecione uma turma.")],
        choices=[SelectChoice("0", "Selecione uma turma")],
    )
    file = FileField(
        "Planilha de alunos",
        validators=[
            FileRequired(message="Selecione um arquivo CSV ou XLSX."),
            FileAllowed(
                ["csv", "xlsx"],
                message="Envie uma planilha no formato CSV ou XLSX.",
            ),
        ],
    )
    submit = SubmitField("Validar planilha")
