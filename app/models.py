from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    student_imports = db.relationship(
        "StudentImportBatch", back_populates="user", passive_deletes=True
    )
    fiap_drafts = db.relationship(
        "EvaluationDraft", back_populates="user", passive_deletes=True
    )
    evaluation_sheets = db.relationship(
        "EvaluationSheet", back_populates="teacher", passive_deletes=True
    )

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True)

    curricular_units = db.relationship(
        "CurricularUnit", back_populates="course", passive_deletes=True
    )
    classes = db.relationship("ClassGroup", back_populates="course", passive_deletes=True)


class CurricularUnit(db.Model):
    __tablename__ = "curricular_units"
    __table_args__ = (
        db.UniqueConstraint("course_id", "name", name="uq_curricular_units_course_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    workload_hours = db.Column(db.Integer, nullable=False)
    max_absence_hours = db.Column(
        db.Numeric(7, 2),
        nullable=False,
        default=lambda context: (
            Decimal(context.get_current_parameters()["workload_hours"])
            * Decimal("0.25")
        ),
    )
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )

    course = db.relationship("Course", back_populates="curricular_units")
    evaluation_sheets = db.relationship(
        "EvaluationSheet", back_populates="curricular_unit", passive_deletes=True
    )


class ClassGroup(db.Model):
    __tablename__ = "classes"
    __table_args__ = (
        db.UniqueConstraint("course_id", "name", name="uq_classes_course_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )

    course = db.relationship("Course", back_populates="classes")
    students = db.relationship(
        "Student", back_populates="class_group", passive_deletes=True
    )
    evaluation_sheets = db.relationship(
        "EvaluationSheet", back_populates="class_group", passive_deletes=True
    )


class Student(db.Model):
    __tablename__ = "students"
    __table_args__ = (
        db.UniqueConstraint("class_id", "name", name="uq_students_class_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    class_id = db.Column(
        db.Integer, db.ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )

    class_group = db.relationship("ClassGroup", back_populates="students")
    evaluation_sheets = db.relationship(
        "EvaluationSheet", back_populates="student", passive_deletes=True
    )


class StudentImportBatch(db.Model):
    __tablename__ = "student_import_batches"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    class_id = db.Column(
        db.Integer, db.ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    rows_json = db.Column(db.Text, nullable=False)
    has_errors = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expires_at = db.Column(db.Integer, nullable=False, index=True)

    user = db.relationship("User", back_populates="student_imports")
    class_group = db.relationship("ClassGroup")


class EvaluationDraft(db.Model):
    __tablename__ = "evaluation_drafts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    payload_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = db.Column(db.Integer, nullable=False, index=True)

    user = db.relationship("User", back_populates="fiap_drafts")


class EvaluationSheet(db.Model):
    __tablename__ = "evaluation_sheets"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    class_id = db.Column(
        db.Integer, db.ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    curricular_unit_id = db.Column(
        db.Integer,
        db.ForeignKey("curricular_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company = db.Column(db.String(200), nullable=False, default="")
    evaluated_on = db.Column(db.Date, nullable=False)
    workload_hours = db.Column(db.Integer, nullable=False)
    class_average = db.Column(db.Integer, nullable=False)
    student_grade = db.Column(db.Integer, nullable=False)
    absence_limit_hours = db.Column(db.Numeric(7, 2), nullable=False)
    absences_hours = db.Column(db.Integer, nullable=False)
    difficulties = db.Column(db.Text, nullable=False, default="")
    recommendations = db.Column(db.Text, nullable=False, default="")
    school_actions = db.Column(db.Text, nullable=False, default="")
    observations = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    student = db.relationship("Student", back_populates="evaluation_sheets")
    class_group = db.relationship("ClassGroup", back_populates="evaluation_sheets")
    teacher = db.relationship("User", back_populates="evaluation_sheets")
    curricular_unit = db.relationship(
        "CurricularUnit", back_populates="evaluation_sheets"
    )
