# app.py
print("--- DEBUG: Cargando app.py ---")

from flask import Flask, render_template, url_for, redirect, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from datetime import datetime, date # Importar 'date' para db.Date y DateField
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Optional, Length, Email, EqualTo, ValidationError # Importar ValidationError
# No necesitas importar generate_password_hash ni check_password_hash si usas Flask-Bcrypt
# from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from sqlalchemy import asc # Importar asc para ordenar con nulos al final

# Si tus modelos y formularios están en archivos separados (models.py, forms.py), impórtalos así:
# from .models import db, User, Project, Task, Area # Ajusta la importación según tu estructura de carpetas
# from .forms import RegistrationForm, TaskForm # Ajusta la importación

# Si tus modelos y formularios están definidos directamente en este archivo app.py, no necesitas las importaciones de arriba.

app = Flask(__name__)
app.config['SECRET_KEY'] = '021203272324110823' # Asegurate de usar una clave secreta fuerte y ÚNICA en producción

# *** BASE DE DATOS ***
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# *** FIN CONFIGURACIÓN DE LA BASE DE DATOS ***


# *** INICIALIZAR BCRYPT ***
bcrypt = Bcrypt(app)
# *** FIN INICIALIZAR BCRYPT ***

# *** CONFIGURACIÓN DE FLASK-LOGIN ***
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'iniciar_sesion'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'
# *** FIN CONFIGURACIÓN DE FLASK-LOGIN ***

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'jscproyectosvirtual@gmail.com'
app.config['MAIL_PASSWORD'] = 'pbgxmztermvsbvae' # <--- ¡PEGA AQUÍ LA CONTRASEÑA DE APLICACIÓN REAL!
app.config['MAIL_DEFAULT_SENDER'] = 'jscproyectosvirtual@gmail.com'
mail = Mail(app)

# ***MODELOS***
# Si tus modelos están en models.py, elimina estas definiciones de aquí y usa la importación de arriba.
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='encargado')

    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True)
    area = db.relationship('Area', backref=db.backref('users', lazy=True))

    # Relaciones inversas para tareas y proyectos creados/asignados/modificados
    # creadas = db.relationship('Task', foreign_keys='Task.creator_id', backref='creator', lazy=True) # Ya definidas en Task con backref
    # asignadas = db.relationship('Task', foreign_keys='Task.assigned_user_id', backref='assigned_user', lazy=True) # Ya definidas en Task con backref
    # proyectos_creados = db.relationship('Project', foreign_keys='Project.user_id', backref='creator', lazy=True) # Ya definidas en Project con backref
    # tareas_modificadas = db.relationship('Task', foreign_keys='Task.last_updated_by_id', backref='last_updated_by', lazy=True) # Ya definidas en Task con backref
    # proyectos_modificados = db.relationship('Project', foreign_keys='Project.last_updated_by_id', backref='last_updated_by', lazy=True) # Ya definidas en Project con backref


    def __repr__(self):
        area_name = self.area.name if self.area else 'N/A'
        return f"User('{self.username}', '{self.email}', '{self.role}', Area: {area_name})"

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    manager_name = db.Column(db.String(100), nullable=True)

    start_date = db.Column(db.Date, nullable=True) # Cambiado a Date
    end_date = db.Column(db.Date, nullable=True)   # Cambiado a Date
    status = db.Column(db.String(50), nullable=False, default='En ejecución')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Creador del proyecto
    creator = db.relationship('User', backref=db.backref('created_projects', lazy=True), foreign_keys=[user_id])

    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True)
    area = db.relationship('Area', backref=db.backref('projects_assigned', lazy=True))

    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_updated_by = db.relationship('User', backref=db.backref('modified_projects', lazy=True), foreign_keys=[last_updated_by_id])

    # Relación de Project a Task (Un proyecto tiene muchas tareas)
    # backref='project' crea la propiedad .project en el modelo Task
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        start_str = f"Start: {self.start_date.strftime('%Y-%m-%d')}" if self.start_date else "Start: N/A"
        end_str = f"End: {self.end_date.strftime('%Y-%m-%d')}" if self.end_date else "End: N/A"
        manager_str = f"Manager: {self.manager_name}" if self.manager_name else "Manager: N/A"
        area_str = f"Area: {self.area.name}" if self.area else "Area: N/A"
        return f"Project('{self.name}', {area_str}, {manager_str}, 'Status: {self.status}', {start_str}, {end_str})"


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    due_date = db.Column(db.Date, nullable=True) # <-- Es crucial que este sea db.Date para que coincida con DateField
    status = db.Column(db.String(50), nullable=False, default='Pendiente')

    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id], backref=db.backref('assigned_tasks', lazy=True))

    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    # La relación inversa 'project' ya está en Project gracias al backref en la relación 'tasks' de Project.
    # No necesitas definir db.relationship('Project', ...) aquí si ya está en Project con backref='project'.
    # Si la defines aquí, debe ser sin backref para evitar conflictos.
    # project = db.relationship('Project', foreign_keys=[project_id]) # Si la quieres explícita sin backref

    # --- AÑADE ESTAS LÍNEAS NUEVAS (si no las tenías) ---
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('created_tasks', lazy=True))

    last_updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_updated_by = db.relationship('User', foreign_keys=[last_updated_by_id], backref=db.backref('updated_tasks', lazy=True))
    last_updated_at = db.Column(db.DateTime, nullable=True) # <--- Fecha de última actualización
    # --- FIN DE LAS LÍNEAS NUEVAS ---


    def __repr__(self):
        return f"Task('{self.title}', 'Project ID: {self.project_id}', 'Status: {self.status}')"

class Area(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f"Area('{self.name}')"

# Si tus modelos estaban en models.py, elimina estas definiciones de aquí.

# *** FORMULARIOS ***
# Si tus formularios están en forms.py, elimina estas definiciones de aquí y usa la importación de arriba.
class TaskForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Descripción', validators=[Optional(), Length(max=500)])
    due_date = DateField('Fecha Límite (YYYY-MM-DD)', format='%Y-%m-%d', validators=[Optional()])
    status = SelectField('Estado', choices=[
        ('Pendiente', 'Pendiente'),
        ('En ejecución', 'En ejecución'),
        ('Finalizado', 'Finalizado'),
        ('Suspendido', 'Suspendido'),
        ('Cancelado', 'Cancelado')
    ], validators=[DataRequired()])
    assigned_user = SelectField('Asignado a', coerce=int, validators=[Optional()])
    submit = SubmitField('Guardar Tarea')

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        # Puedes filtrar por roles si solo algunos usuarios pueden ser asignados a tareas
        assignable_users = User.query.filter(User.role.in_(['encargado', 'supervisor'])).order_by(User.username).all() # Ajusta los roles si es necesario
        self.assigned_user.choices = [(0, 'Sin asignar')] + \
                                     [(u.id, u.username) for u in assignable_users]

class RegistrationForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Rol', choices=[('encargado', 'Encargado'), ('supervisor', 'Supervisor')], validators=[DataRequired()]) # Ajusta los roles si es necesario
    area = SelectField('Área', coerce=int, validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.area.choices = [(0, 'Sin área')] + [(a.id, a.name) for a in Area.query.order_by(Area.name).all()]

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ese nombre de usuario ya está en uso. Por favor, elige uno diferente.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Ese email ya está en uso. Por favor, elige uno diferente.')

# Si tus formularios estaban en forms.py, elimina estas definiciones de aquí.
# FIN FORMULARIOS ***

# Función user_loader requerida por Flask-Login
@login_manager.user_loader
def load_user(user_id):
    # Asegúrate de que User.query está disponible (depende de cómo inicializaste db)
    return User.query.get(int(user_id))

# *** RUTAS ***

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('Ya estás logueado.', 'info')
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        area_id_to_assign = form.area.data if form.area.data != 0 else None
        user = User(username=form.username.data, email=form.email.data,
                    password=hashed_password, role=form.role.data, area_id=area_id_to_assign)
        db.session.add(user)
        db.session.commit()
        flash('¡Tu cuenta ha sido creada exitosamente! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('iniciar_sesion'))
    return render_template('register.html', title='Registro', form=form)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/iniciar_sesion', methods=['GET', 'POST'])
def iniciar_sesion():
    if current_user.is_authenticated:
        flash('Ya estás logueado.', 'info')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')

        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            # next_page = request.args.get('next') # Si quieres redirigir a la página anterior
            # return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado tu sesión exitosamente.', 'success')
    return redirect(url_for('index'))


@app.route('/proyecto/crear', methods=['GET', 'POST'])
@login_required
def crear_proyecto():
    # Puedes añadir lógica de permisos aquí si solo ciertos roles pueden crear proyectos
    if current_user.role not in ['supervisor']: # Ajusta los roles que pueden crear proyectos
         flash('No tienes permiso para crear proyectos.', 'danger')
         return redirect(url_for('dashboard'))

    if request.method == 'POST':
        project_name = request.form.get('name')
        project_description = request.form.get('description')
        manager_name = request.form.get('manager_name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        status = request.form.get('status')

        if not project_name:
            flash('El nombre del proyecto es obligatorio.', 'danger')
            return render_template('create_project.html')

        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() # Convertir a date
            except ValueError:
                flash('Formato de Fecha de Inicio inválido.', 'danger')
                return render_template('create_project.html')

        end_date = None
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() # Convertir a date
            except ValueError:
                flash('Formato de Fecha Estimada de Finalización inválido.', 'danger')
                return render_template('create_project.html')

        new_project = Project(
            name=project_name,
            description=project_description,
            manager_name=manager_name,
            start_date=start_date,
            end_date=end_date,
            status=status,
            user_id=current_user.id, # El creador del proyecto es el usuario actual
            last_updated_by_id=current_user.id
        )

        db.session.add(new_project)
        db.session.commit()

        flash(f'El proyecto "{project_name}" ha sido creado exitosamente.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_project.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user_role = current_user.role
    print(f"--- DEBUG: Usuario '{current_user.username}' ({user_role}) accediendo al dashboard ---")
    print(f"--- DEBUG: Valor exacto de user_role antes de if/elif: '{user_role}' (Tipo: {type(user_role)}) ---")

    data_for_template = {}
    data_for_template['user_role'] = user_role

    if user_role == 'supervisor':
        print("--- DEBUG: Preparando datos para Supervisor ---")
        try:
            create_project_url = url_for('crear_proyecto')
            print(f"--- DEBUG: URL 'crear_proyecto' generada en backend: {create_project_url} ---")
        except Exception as e:
            print(f"--- DEBUG: ERROR al generar URL 'crear_proyecto' en backend: {e} ---")
            create_project_url = "#error-generating-url"
        data_for_template['create_project_url'] = create_project_url

        all_projects = Project.query.all()
        data_for_template['proyectos'] = all_projects

        all_tasks = Task.query.all() # Supervisor ve todas las tareas
        data_for_template['tareas'] = all_tasks

        # TODO: Añadir logica aqui para obtener datos de avance agregado (semanal, mensual, anual)
        data_for_template['avance_resumen_semanal'] = "Datos de avance semanal (Supervisor)"
        data_for_template['tareas_proximas_vencer'] = "Lista de tareas proximas a vencer en todos los proyectos (Supervisor)"

    elif user_role == 'encargado':
        print("--- DEBUG: Preparando datos para Encargado (Lider) ---")

        # Obtener proyectos donde el usuario es el creador O el manager
        all_projects = Project.query.filter(
            (Project.user_id == current_user.id) |
            (Project.manager_name == current_user.username)
        ).distinct().all()
        data_for_template['proyectos'] = all_projects

        # Obtener tareas asignadas al usuario
        # O tareas que pertenecen a proyectos donde el usuario es el creador
        # O tareas que pertenecen a proyectos donde el usuario es el manager
        # Usamos project_id.in_([p.id for p in all_projects]) para incluir tareas de proyectos relevantes
        all_tasks = Task.query.filter(
            (Task.assigned_user_id == current_user.id) |  # Tareas directamente asignadas a este encargado
            (Task.project_id.in_([p.id for p in all_projects])) # Tareas de CUALQUIERA de sus proyectos relevantes
        ).distinct().order_by(Task.due_date.asc().nullslast()).all() # Ordenamos por fecha límite, nulos al final
        data_for_template['tareas'] = all_tasks

        data_for_template['tareas_de_mi_equipo_resumen'] = "Resumen de tareas de mi equipo (Encargado)"
        data_for_template['reporte_semanal_pendiente'] = "Area para enviar reporte semanal al Supervisor (Encargado)"

    else:
        print(f"--- DEBUG: Rol '{user_role}' no soportado para dashboard ---")
        flash(f'Tu rol ({user_role}) no tiene acceso al dashboard.', 'warning')
        return redirect(url_for('index'))

    return render_template('dashboard.html', **data_for_template)


@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Lógica de permisos para ver el proyecto y sus tareas
    has_permission = False
    if current_user.role == 'supervisor':
        has_permission = True
    elif project.user_id == current_user.id: # Creador del proyecto
        has_permission = True
    elif current_user.role == 'encargado' and project.manager_name and project.manager_name == current_user.username:
        has_permission = True
    # Opcional: Permitir ver si el usuario tiene tareas asignadas en este proyecto
    # elif Task.query.filter_by(project_id=project.id, assigned_user_id=current_user.id).first():
    #    has_permission = True


    if not has_permission:
        flash('No tienes permiso para ver los detalles de este proyecto.', 'danger')
        abort(403) # Acceso Denegado

    # Recupera las tareas asociadas a este proyecto y las ordena
    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.due_date.asc().nullslast()).all()

    print(f"--- DEBUG (view_project): Para el Proyecto '{project.name}' (ID: {project.id}), se cargaron {len(tasks)} tareas.")
    for task in tasks:
        # Asegúrate de que task.assigned_user y task.creator no sean None antes de acceder a username/id
        assigned_user_info = f"{task.assigned_user.username} (ID: {task.assigned_user_id})" if task.assigned_user else "Sin asignar (ID: None)"
        creator_info = f"{task.creator.username} (ID: {task.creator_id})" if task.creator else "N/A (ID: None)"
        print(f"--- DEBUG (view_project):   - Tarea ID: {task.id}, Título: {task.title}, Status: {task.status}, Project ID asociado: {task.project_id}, Asignado a: {assigned_user_info}, Creador: {creator_info}")


    return render_template('project_details.html', project=project, tasks=tasks)


@app.route('/project/<int:project_id>/add_task', methods=['GET', 'POST'])
@login_required
def add_task(project_id):
    print(f"--- Entrando a add_task para project_id: {project_id} ---")
    project = Project.query.get_or_404(project_id)
    form = TaskForm()

    # Lógica de permisos para añadir tareas: Solo el creador del proyecto, un supervisor o el encargado del proyecto
    has_permission = False
    if current_user.role == 'supervisor':
        has_permission = True
    elif project.user_id == current_user.id: # Creador del proyecto
        has_permission = True
    elif current_user.role == 'encargado' and project.manager_name and project.manager_name == current_user.username:
        has_permission = True

    if not has_permission:
        flash('No tienes permiso para añadir tareas a este proyecto.', 'danger')
        return redirect(url_for('view_project', project_id=project.id))

    # Rellenar la lista de usuarios asignables para el formulario
    # Ajusta los roles si es necesario
    form.assigned_user.choices = [(0, 'Sin asignar')] + [(user.id, user.username) for user in User.query.filter(User.role.in_(['encargado', 'supervisor'])).order_by(User.username).all()]


    print(f"Método de la solicitud: {request.method}")

    if form.validate_on_submit():
        print("--- form.validate_on_submit() es TRUE ---")
        try:
            title = form.title.data
            description = form.description.data
            due_date = form.due_date.data
            status = form.status.data
            assigned_user_id = form.assigned_user.data

            final_assigned_user_id = assigned_user_id if assigned_user_id != 0 else None

            print(f"Datos del formulario: Título={title}, Descripción={description}, Fecha={due_date}, Estado={status}, Asignado a ID={final_assigned_user_id}")
            print(f"DEBUG: El project_id al que se asociará la tarea es: {project.id}")
            print(f"DEBUG: El usuario actual (creador) es: {current_user.username} (ID: {current_user.id})")
            print(f"DEBUG: Valor final de assigned_user_id antes de guardar: {final_assigned_user_id}") # <-- DEBUG ADICIONAL


            new_task = Task(
                title=title,
                description=description,
                due_date=due_date,
                status=status,
                project_id=project.id,
                assigned_user_id=final_assigned_user_id,
                creator_id=current_user.id, # <--- ¡AÑADE ESTO!
                last_updated_by_id=current_user.id,
                last_updated_at=datetime.utcnow()
            )
            db.session.add(new_task)
            db.session.commit()
            print(f"--- Tarea '{new_task.title}' (ID: {new_task.id}) guardada exitosamente con project_id: {new_task.project_id}, creator_id: {new_task.creator_id}, assigned_user_id: {new_task.assigned_user_id} ---")

            flash('Tarea guardada exitosamente!', 'success')
            return redirect(url_for('view_project', project_id=project.id))

        except Exception as e:
            db.session.rollback() # Deshacer la transacción si hay un error
            print(f"--- ERROR AL GUARDAR TAREA: {e} ---")
            flash(f'Error al guardar la tarea: {e}', 'error')
            # Renderiza de nuevo para ver errores
            return render_template('add_task.html', form=form, action="Añadir", project=project)

    else:
        print("--- form.validate_on_submit() es FALSE o es GET ---")
        if request.method == 'POST':
            print("--- Solicitud POST, pero el formulario no es válido. Errores: ---")
            for field, errors in form.errors.items():
                for error in errors:
                    print(f"Error en campo '{field}': {error}")
            flash('Por favor, corrige los errores del formulario.', 'error')

    # Si es GET o si la validación falla (POST)
    return render_template('add_task.html', form=form, action="Añadir", project=project)


@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Permiso para eliminar: solo el creador del proyecto o un supervisor
    if project.user_id != current_user.id and current_user.role != 'supervisor':
        flash('No tienes permiso para eliminar este proyecto.', 'danger')
        return redirect(url_for('view_project', project_id=project.id))

    try:
        # Debido a 'cascade="all, delete-orphan"' en la relación Project.tasks,
        # las tareas asociadas se eliminarán automáticamente con el proyecto.
        db.session.delete(project)
        db.session.commit()
        flash(f'El proyecto "{project.name}" y todas sus tareas asociadas han sido eliminados con éxito.', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el proyecto "{project.name}". Por favor, inténtalo de nuevo. Detalles: {e}', 'danger')
        print(f"Error detallado al eliminar proyecto ID {project_id}: {e}")
        return redirect(url_for('view_project', project_id=project.id))


# VER TAREA
@app.route('/task/<int:task_id>')
@login_required
def view_task(task_id):
    task = Task.query.get_or_404(task_id)

    # Lógica de permisos para ver la tarea:
    # 1. Supervisor siempre puede ver.
    # 2. Creador del proyecto al que pertenece la tarea.
    # 3. Encargado del proyecto al que pertenece la tarea.
    # 4. Usuario asignado directamente a la tarea.
    # 5. Creador de la tarea.

    has_permission = False

    if current_user.role == 'supervisor':
        has_permission = True
    elif task.project and task.project.user_id == current_user.id: # Creador del proyecto (verifica task.project)
        has_permission = True
    elif current_user.role == 'encargado' and task.project and task.project.manager_name and task.project.manager_name == current_user.username: # Encargado del proyecto (verifica task.project)
        has_permission = True
    elif task.assigned_user_id == current_user.id: # Usuario asignado a esta tarea
        has_permission = True
    elif task.creator_id == current_user.id: # Creador de la tarea
         has_permission = True


    if not has_permission:
        flash('No tienes permiso para ver los detalles de esta tarea.', 'danger')
        # Redirigir a la vista del proyecto si no tiene permiso para la tarea, o al dashboard.
        # Asegúrate de que task.project no sea None antes de acceder a task.project.id
        redirect_url = url_for('dashboard')
        if task.project:
             redirect_url = url_for('view_project', project_id=task.project.id)
        return redirect(redirect_url)

    return render_template('task_details.html', task=task)


# EDITAR TAREA
@app.route("/task/<int:task_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)

    # Lógica de permisos para editar tarea
    # Permitir editar solo a:
    # 1. Supervisor
    # 2. El creador original de la tarea (si aplica este permiso)
    # 3. NOTA: Se elimina el permiso para encargados (incluso si gestionan el proyecto o están asignados)
    has_permission = False
    if current_user.role == 'supervisor':
        has_permission = True
    # Si quieres que el creador de la tarea (sin importar su rol) pueda editarla:
    # elif task.creator_id == current_user.id:
    #     has_permission = True

    # Si el usuario actual es un encargado, NO tiene permiso para editar según el nuevo requisito.
    if current_user.role == 'encargado':
        has_permission = False # Sobrescribir cualquier permiso anterior si es encargado

    # Asegurar que el supervisor siempre tenga permiso (redundante pero seguro)
    if current_user.role == 'supervisor':
         has_permission = True


    if not has_permission:
        flash('No tienes permiso para editar esta tarea.', 'danger')
        # Redirigir a la vista del proyecto o dashboard si no tiene permiso
        redirect_url = url_for('dashboard')
        if task.project:
             redirect_url = url_for('view_project', project_id=task.project.id)
        return redirect(redirect_url)


    form = TaskForm(obj=task) # Carga los datos existentes de la tarea en el formulario

    # Rellenar la lista de usuarios asignables para el formulario
    # Ajusta los roles si es necesario
    form.assigned_user.choices = [(0, 'Sin asignar')] + [(user.id, user.username) for user in User.query.filter(User.role.in_(['encargado', 'supervisor'])).order_by(User.username).all()]


    if form.validate_on_submit():
        try:
            task.title = form.title.data
            task.description = form.description.data
            task.status = form.status.data
            task.due_date = form.due_date.data # DateField ya maneja esto como objeto datetime.date

            # Asignar/desasignar usuario basado en la selección del formulario
            if form.assigned_user.data and form.assigned_user.data != 0:
                assigned_user_obj = User.query.get(form.assigned_user.data)
                if assigned_user_obj:
                    task.assigned_user = assigned_user_obj # Asigna el objeto User
                else:
                    task.assigned_user = None # Si el ID no existe (raro si se llena desde la BBDD), desasigna
            else:
                task.assigned_user = None # Si se selecciona 'Sin asignar' (0) o no se selecciona nada

            task.last_updated_by_id = current_user.id # Quien actualizó la tarea
            task.last_updated_at = datetime.utcnow() # Registrar la fecha de la última actualización

            db.session.commit()
            flash('¡Tarea actualizada exitosamente!', 'success')
            return redirect(url_for('view_task', task_id=task.id)) # Redirigir a la vista de la tarea actualizada

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la tarea: {e}', 'danger')
            # Renderiza de nuevo el formulario de edición
            return render_template('edit_task.html', form=form, action='Editar', task=task, project=project) # Pasa project también


    elif request.method == 'GET':
        # Precargar el valor del select para el usuario asignado
        form.assigned_user.data = task.assigned_user_id if task.assigned_user_id else 0

    # Renderiza el formulario de edición (para GET o si la validación falla en POST)
    return render_template('edit_task.html', form=form, action='Editar', task=task, project=project) # Pasa project también


@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Permisos para editar proyecto: Creador del proyecto, Supervisor, o encargado del proyecto
    if project.user_id != current_user.id and current_user.role != 'supervisor':
        if not (current_user.role == 'encargado' and project.manager_name and project.manager_name == current_user.username):
            flash('No tienes permiso para editar este proyecto.', 'danger')
            return redirect(url_for('view_project', project_id=project.id))

    if request.method == 'GET':
        # Pasar los datos del proyecto a la plantilla para pre-llenar el formulario
        # Asegúrate de que tu plantilla edit_project.html use el objeto 'project'
        return render_template('edit_project.html', title=f'Editar Proyecto: {project.name}', project=project)

    elif request.method == 'POST':
        # Procesar los datos del formulario enviado
        project_name = request.form.get('name')
        project_description = request.form.get('description')
        manager_name = request.form.get('manager_name')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        status = request.form.get('status')

        if not project_name:
            flash('El nombre del proyecto es obligatorio.', 'danger')
            return redirect(url_for('edit_project', project_id=project.id)) # Redirige de vuelta con el error

        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() # Convertir a date
            except ValueError:
                flash('Formato de Fecha de Inicio inválido.', 'danger')
                return redirect(url_for('edit_project', project_id=project.id)) # Redirige de vuelta con el error

        end_date = None
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() # Convertir a date
            except ValueError:
                flash('Formato de Fecha Estimada de Finalización inválido.', 'danger')
                return redirect(url_for('edit_project', project_id=project.id)) # Redirige de vuelta con el error

        # Actualizar los campos del proyecto con los datos del formulario
        project.name = project_name
        project.description = project_description
        project.manager_name = manager_name
        project.start_date = start_date
        project.end_date = end_date
        project.status = status
        project.last_updated_by_id = current_user.id # Quien lo edito
        # project.last_updated = datetime.utcnow() # La columna 'last_updated' ya tiene onupdate=datetime.utcnow

        try:
            db.session.commit()
            flash(f'El proyecto "{project.name}" ha sido actualizado con éxito.', 'success')
            return redirect(url_for('view_project', project_id=project.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el proyecto "{project.name}". Por favor, inténtalo de nuevo. Detalles: {e}', 'danger')
            print(f"Error detallado actualizando proyecto ID {project_id}: {e}")
            return redirect(url_for('edit_project', project_id=project.id)) # Redirige de vuelta con el error

    # Si el método no es GET ni POST (debería ser imposible con methods=['GET', 'POST'])
    return abort(405) # Método no permitido


# ELIMINAR TAREA
@app.route("/task/<int:task_id>/delete", methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)

    # Lógica de permisos para eliminar tarea
    # Permitir eliminar solo a:
    # 1. Supervisor
    # 2. El creador original de la tarea (si aplica este permiso)
    # 3. NOTA: Se elimina el permiso para encargados
    has_permission = False
    if current_user.role == 'supervisor':
        has_permission = True
    # Si quieres que el creador de la tarea (sin importar su rol) pueda eliminarla:
    # elif task.creator_id == current_user.id:
    #     has_permission = True

    # Si el usuario actual es un encargado, NO tiene permiso para eliminar según el nuevo requisito.
    if current_user.role == 'encargado':
        has_permission = False # Sobrescribir cualquier permiso anterior si es encargado

    # Asegurar que el supervisor siempre tenga permiso (redundante pero seguro)
    if current_user.role == 'supervisor':
         has_permission = True


    if not has_permission:
        flash('No tienes permiso para eliminar esta tarea.', 'danger')
        # Redirigir a la vista del proyecto o dashboard si no tiene permiso
        redirect_url = url_for('dashboard')
        if task.project:
             redirect_url = url_for('view_project', project_id=task.project.id)
        return redirect(redirect_url)

    try:
        db.session.delete(task)
        db.session.commit()
        flash('¡Tarea eliminada exitosamente!', 'success')
        # Redirigir a la vista del proyecto de la tarea eliminada, o al dashboard
        redirect_url = url_for('dashboard')
        if task.project:
             redirect_url = url_for('view_project', project_id=task.project.id)
        return redirect(redirect_url)

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la tarea: {e}', 'danger')
        # Redirigir a la vista de la tarea o dashboard si falla
        redirect_url = url_for('dashboard')
        if task.project:
             redirect_url = url_for('view_project', project_id=task.project.id)
        return redirect(redirect_url)


@app.route("/some_action_that_sends_email")
@login_required
def send_email_example():
    # Asegúrate de que sender sea el mismo que MAIL_USERNAME si usas Gmail con TLS
    msg = Message('Asunto de Prueba',
                    sender='jscproyectosvirtual@gmail.com', # Debe coincidir con MAIL_USERNAME
                    recipients=['destinatario@example.com']) # Cambia esto al email real del destinatario
    msg.body = "Este es un mensaje de prueba enviado desde tu aplicación Flask."
    msg.html = "<b>Este es un mensaje de prueba</b> enviado desde tu aplicación Flask con <i>HTML</i>."

    try:
        mail.send(msg)
        flash('Correo de prueba enviado!', 'success')
    except Exception as e:
        flash(f'Error al enviar correo: {e}', 'danger')

    return redirect(url_for('dashboard'))


@app.route("/test_email")
def test_email():
    # Esta ruta no requiere login_required si quieres probar el email sin iniciar sesión
    # @login_required # Descomenta si quieres que solo usuarios logueados puedan probar
    try:
        msg = Message("Prueba de Correo desde JSC Proyectos Flask",
                      sender='jscproyectosvirtual@gmail.com', # Debe coincidir con MAIL_USERNAME
                      recipients=['jaircabrera@unimayor.edu.co']) # CAMBIA ESTO A TU EMAIL PARA PROBAR
        msg.body = "Hola,\n\nEste es un correo de prueba enviado desde tu aplicación Flask de JSC Proyectos."
        msg.html = """
        <html>
            <body>
                <h1>¡Prueba de Correo Exitosa!</h1>
                <p>Este es un correo de prueba enviado desde tu aplicación <strong>JSC Proyectos Flask</strong>.</p>
                <p>Si recibiste esto, la configuración de Flask-Mail es correcta.</p>
                <p>Saludos,<br>Tu Aplicación de Proyectos</p>
            </body>
        </html>
        """
        mail.send(msg)
        flash('Correo de prueba enviado con éxito!', 'success')
    except Exception as e:
        flash(f'Error al enviar correo de prueba: {e}', 'danger')
        print(f"DEBUG: Error al enviar correo de prueba: {e}")

    # Redirige a alguna página después de enviar el correo
    # Asegúrate de que 'dashboard' es una ruta accesible (requiere login si tiene @login_required)
    # Si quieres probar sin login, redirige a una ruta pública como 'index'
    return redirect(url_for('dashboard'))


# Este bloque solo inicia el servidor de desarrollo
# La creación de la base de datos y los datos iniciales DEBEN estar en un script separado (create_db.py)
if __name__ == '__main__':
    app.run(debug=True)

