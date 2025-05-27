# forms.py

from flask_wtf import FlaskForm 
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField,
    DateField, FloatField, SubmitField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField

from models import Area, User

### FORMULARIO DE REGISTRO PARA APOYO (por código de área) ###
class ApoyoRegisterForm(FlaskForm):
    username = StringField(
        'Nombre de usuario',
        validators=[DataRequired(), Length(min=2, max=20)]
    )
    email = StringField(
        'Correo electrónico',
        validators=[
            DataRequired(),
            Email(message="Introduce un correo válido")
        ]
    )
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirmar contraseña',
        validators=[DataRequired(), EqualTo('password', message="Las contraseñas deben coincidir")]
    )
    area_codigo = StringField(
        'Código de área',
        validators=[DataRequired(), Length(min=4, max=16)]
    )
    submit = SubmitField('Registrarme como Apoyo')

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError('Ese nombre de usuario ya existe.')

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('Ese correo ya está registrado.')

### FORMULARIO DE LOGIN ###
class LoginForm(FlaskForm):
    username_or_email = StringField('Usuario o correo', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar sesión')

### FORMULARIO PARA PROYECTOS ###
class ProjectForm(FlaskForm):
    name = StringField(
        'Nombre del proyecto',
        validators=[
            DataRequired(message="El nombre es obligatorio"),
            Length(min=4, max=300, message="Debe tener entre 4 y 300 caracteres")
        ]
    )
    description = TextAreaField(
        'Descripción',
        validators=[Optional(), Length(max=500)]
    )
    start_date = DateField(
        'Fecha de inicio (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    end_date = DateField(
        'Fecha de fin (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    status = SelectField(
        'Estado',
        choices=[
            ('En ejecución', 'En ejecución'),
            ('Finalizado',     'Finalizado'),
            ('Suspendido',     'Suspendido'),
            ('Cancelado',      'Cancelado')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Guardar proyecto')

### FORMULARIO PARA TAREAS GENERALES ###
class TareaGeneralForm(FlaskForm):
    title        = StringField(
        'Título de la Tarea General',
        validators=[DataRequired(), Length(min=4, max=100)]
    )
    description  = TextAreaField(
        'Descripción (opcional)',
        validators=[Optional(), Length(max=500)]
    )
    fecha_limite = DateField(
        'Fecha límite (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    prioridad    = SelectField(
        'Prioridad',
        choices=[('Alta','Alta'), ('Media','Media'), ('Baja','Baja')],
        validators=[DataRequired()]
    )
    area_id      = QuerySelectField(
        'Área asignada',
        query_factory=lambda: Area.query.all(),
        get_label='name',
        allow_blank=False
    )
    submit       = SubmitField('Guardar Tarea General')

### FORMULARIO PARA SUBTAREAS ###
class SubtareaForm(FlaskForm):
    title         = StringField(
        'Título de la Subtarea',
        validators=[DataRequired(), Length(min=2, max=200)]
    )
    description   = TextAreaField(
        'Descripción',
        validators=[Optional(), Length(max=500)]
    )
    fecha_limite  = DateField(
        'Fecha límite (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    status        = SelectField(
        'Estado',
        choices=[
            ('Pendiente',   'Pendiente'),
            ('En ejecución','En ejecución'),
            ('Finalizado',  'Finalizado'),
            ('Suspendido',  'Suspendido'),
            ('Cancelado',   'Cancelado'),
            ('Retrasado',   'Retrasado')
        ],
        validators=[DataRequired()]
    )
    prioridad     = SelectField(
        'Prioridad',
        choices=[('Alta','Alta'), ('Media','Media'), ('Baja','Baja')],
        validators=[DataRequired()]
    )
    assigned_user = QuerySelectField(
        'Asignar a',
        query_factory=lambda: User.query.all(),
        get_label='username',
        allow_blank=True,
        blank_text='-- Sin asignar --'
    )
    submit        = SubmitField('Guardar Subtarea')

# Nota: Si encuentras el error:
#   Exception: Install 'email_validator' for email validation support.
# ejecuta en tu entorno:
#   pip install email_validator
