from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from datetime import datetime, date
from sqlalchemy.orm import joinedload # Import para optimizar consultas de relaciones

# Asegúrate que db está inicializado en models.py y que las clases están bien definidas
from models import db, User, Area, Project, TareaGeneral, Subtarea
from forms import LoginForm, ApoyoRegisterForm, ProjectForm, SubtareaForm, TareaGeneralForm # Asegúrate de que SubtareaForm existe
from config import Config

# --- Inicialización de la aplicación ---
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
mail = Mail(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)

@app.context_processor
def inject_now():
    """Inyecta el objeto datetime.utcnow() en todas las plantillas Jinja2."""
    return {'now': datetime.utcnow()}

# --- Autenticación ---
@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario dado su ID para Flask-Login."""
    # SQLAlchemy 2.0 recomienda Session.get() en lugar de Query.get()
    return db.session.get(User, int(user_id))

# --- Funciones auxiliares para verificar el estado de las tareas ---

def es_retrasada_subtarea(subtarea):
    """
    Verifica si una subtarea está retrasada.
    Se considera retrasada si su fecha límite ha pasado y no está en un estado finalizado/suspendido/cancelado.
    """
    if subtarea.fecha_limite is None:
        return False
    # Comparar solo la fecha, ignorando la hora
    return subtarea.fecha_limite < date.today() and subtarea.status.lower() not in ['finalizado', 'suspendido', 'cancelado']

def es_retrasada_tarea_general(tarea_general):
    """
    Verifica si una tarea general está retrasada.
    Esto podría basarse en su propia fecha límite o en si tiene subtareas retrasadas.
    Para este ejemplo, usaremos su propia fecha límite.
    """
    if tarea_general.fecha_limite is None:
        return False
    return tarea_general.fecha_limite < date.today() and tarea_general.status.lower() not in ['finalizado', 'suspendido', 'cancelado']

# --- Rutas principales ---

# ¡CORRECCIÓN IMPORTANTE! No puedes tener dos rutas idénticas ('/')
# Una de ellas debe ser la ruta principal (index) y la otra es redundante o un error.
# He eliminado `welcome` y la he consolidado en `index`.
# He renombrado `welcome.html` a `index.html` como acordamos previamente.

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard')) # Si está logeado, va al dashboard
    return render_template('index.html') # Si no, va a la página de bienvenida (index.html)

# 3. Selección de rol
@app.route('/roles')
def roles():
    return render_template('roles.html')


# app.py


@app.route('/gestionar_usuarios')
@login_required
def gestionar_usuarios():
    # Solo los supervisores pueden acceder a esta página
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden gestionar usuarios.', 'danger')
        return redirect(url_for('dashboard'))

    # Aquí iría tu lógica para obtener y mostrar usuarios
    # Por ejemplo:
    # users = User.query.all()
    # return render_template('gestionar_usuarios.html', users=users)

    # Si aún no tienes esta plantilla, puedes poner un mensaje simple por ahora:
    return "<h1>Página de Gestión de Usuarios (En Construcción)</h1><p>Solo visible para supervisores.</p>"



@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión de los usuarios según rol."""
    # 1) Capturamos el role que venga en la query string
    role_param = request.args.get('role')  # 'supervisor', 'lider_area' o 'apoyo'

    # 2) Mapeo a los roles internos que tienes en la BD
    role_map = {
        'supervisor': 'supervisor',
        'lider_area': 'encargado',  # en create_users.py usas role='encargado'
        'apoyo': 'apoyo'
    }
    target_role = role_map.get(role_param)

    # 3) Si ya está logueado, lo enviamos al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            (User.username == form.username_or_email.data) |
            (User.email    == form.username_or_email.data)
        ).first()

        if user and bcrypt.check_password_hash(user.password, form.password.data):
            # 4) Verificamos que el usuario tenga el role adecuado
            if target_role and user.role != target_role:
                flash(f'No tienes permiso para iniciar sesión como {role_param.replace("_"," ")}.', 'danger')
                return render_template('login.html', form=form, role=role_param)

            # 5) Si todo OK, iniciamos sesión
            login_user(user)
            flash(f'¡Bienvenido, {user.username}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Credenciales inválidas. Verifica usuario/email y contraseña.', 'danger')

    # 6) Renderizamos la plantilla, pasando form y role
    return render_template('login.html', form=form, role=role_param)



# --------------------------------------------------
# LOGOUT → volvemos a 'roles' como solicitaste
# --------------------------------------------------
@app.route('/logout')
@login_required
def logout():
    """Cierra la sesión del usuario y vuelve a la pantalla de roles."""
    logout_user()
    flash('Sesión cerrada exitosamente.', 'info')
    return redirect(url_for('roles'))


# --------------------------------------------------
# REGISTER APOYO → al registrarse, redirige al login con role=apoyo
# --------------------------------------------------
@app.route('/register-apoyo', methods=['GET', 'POST'])
def register_apoyo():
    """Maneja el registro de nuevos usuarios con rol 'apoyo'."""
    # Si un usuario ya logueado intenta registrarse, lo mandamos al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = ApoyoRegisterForm()
    if form.validate_on_submit():
        area = Area.query.filter_by(codigo=form.area_codigo.data).first()
        if not area:
            flash('Código de área inválido. Por favor, verifica el código de tu área.', 'danger')
            return render_template('register_apoyo.html', form=form)

        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password,
            role='apoyo',
            area=area
        )
        db.session.add(user)
        db.session.commit()

        flash('Registro exitoso. Ahora puedes iniciar sesión cuando tu cuenta sea aprobada.', 'success')
        # Redirigimos al login y pasamos role=apoyo para que muestre el enlace de "Regístrate"
        return redirect(url_for('login', role='apoyo'))

    return render_template('register_apoyo.html', form=form)


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Muestra el panel de control del usuario.
    Adapta la vista según el rol del usuario (supervisor, encargado, apoyo).
    Prepara los datos para el sidebar jerárquico y la tabla principal.
    """
    subtareas_retrasadas = []
    proyectos_para_sidebar = []
    main_projects = []

    # === NUEVO: Lógica para pasar la variable al template ===
    # Verifica si la ruta 'gestionar_usuarios' existe en tu aplicación
    # (Asumimos que la crearás si aún no existe, o que la función tiene ese nombre)
    has_gestionar_usuarios_route = 'gestionar_usuarios' in app.view_functions
    # ========================================================

    if current_user.role == 'supervisor':
        # ... (Tu lógica existente para supervisor) ...
        projects_query_sidebar = Project.query.options(
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.area).joinedload(Area.users),
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.subtareas).joinedload(Subtarea.assigned_user)
        ).order_by(Project.end_date.desc())

        proyectos_db_sidebar = projects_query_sidebar.all()

        for project_db in proyectos_db_sidebar:
            proyecto_data = {
                'id': project_db.id,
                'nombre': project_db.name,
                'tareas_generales': []
            }
            for tg_db in project_db.tareas_generales:
                area_data = None
                apoyos_area = []
                if tg_db.area:
                    apoyos_area = [{'id': a.id, 'username': a.username} for a in tg_db.area.users if a.role == 'apoyo']
                    area_data = {'id': tg_db.area.id, 'nombre': tg_db.area.name, 'apoyos': apoyos_area}

                subtareas_data = [{'id': s.id, 'nombre': s.title, 'fecha_limite': s.fecha_limite, 'status': s.status,
                                   'proyecto_nombre': project_db.name, 'asignado_a_nombre': s.assigned_user.username if s.assigned_user else 'Sin asignar'}
                                  for s in tg_db.subtareas]

                tarea_general_data = {
                    'id': tg_db.id,
                    'nombre': tg_db.title,
                    'area': area_data,
                    'subtareas': subtareas_data
                }
                proyecto_data['tareas_generales'].append(tarea_general_data)

                for s_data in subtareas_data:
                    temp_subtarea = type('obj', (object,), s_data)()
                    if es_retrasada_subtarea(temp_subtarea):
                        subtareas_retrasadas.append(s_data)

            proyectos_para_sidebar.append(proyecto_data)

            # Proyectos para la tabla principal (objetos Project directos)
            main_projects = Project.query.order_by(Project.end_date.desc()).all()


    elif current_user.role == 'encargado':
        # ... (Tu lógica existente para encargado) ...
        # Proyectos para el sidebar (estructura anidada)
        projects_query_sidebar = Project.query.options(
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.area).joinedload(Area.users),
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.subtareas).joinedload(Subtarea.assigned_user)
        ).order_by(Project.end_date.desc())

        proyectos_db_sidebar = projects_query_sidebar.all()

        for project_db in proyectos_db_sidebar:
            proyecto_data = {
                'id': project_db.id,
                'nombre': project_db.name,
                'tareas_generales': []
            }
            for tg_db in project_db.tareas_generales:
                if tg_db.area_id == current_user.area_id: # Filtrar por área del encargado
                    area_data = None
                    apoyos_area = []
                    if tg_db.area:
                        apoyos_area = [{'id': a.id, 'username': a.username} for a in tg_db.area.users if a.role == 'apoyo']
                        area_data = {'id': tg_db.area.id, 'nombre': tg_db.area.name, 'apoyos': apoyos_area}

                    subtareas_data = [{'id': s.id, 'nombre': s.title, 'fecha_limite': s.fecha_limite, 'status': s.status,
                                       'proyecto_nombre': project_db.name, 'asignado_a_nombre': s.assigned_user.username if s.assigned_user else 'Sin asignar'}
                                      for s in tg_db.subtareas]

                    tarea_general_data = {
                        'id': tg_db.id,
                        'nombre': tg_db.title,
                        'area': area_data,
                        'subtareas': subtareas_data
                    }
                    proyecto_data['tareas_generales'].append(tarea_general_data)

                    for s_data in subtareas_data:
                        temp_subtarea = type('obj', (object,), s_data)()
                        if es_retrasada_subtarea(temp_subtarea):
                            subtareas_retrasadas.append(s_data)

            if proyecto_data['tareas_generales']:
                proyectos_para_sidebar.append(proyecto_data)

            # Proyectos para la tabla principal (solo los de su área si los hay)
            main_projects_query = Project.query.join(TareaGeneral).filter(TareaGeneral.area_id == current_user.area_id).distinct()
            main_projects = main_projects_query.order_by(Project.end_date.desc()).all()


    elif current_user.role == 'apoyo':
        # ... (Tu lógica existente para apoyo) ...
        # Proyectos para el sidebar (estructura anidada)
        proyectos_con_subtareas_asignadas_sidebar = Project.query.join(TareaGeneral).join(Subtarea).filter(
            Subtarea.assigned_user_id == current_user.id
        ).options(
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.area).joinedload(Area.users),
            joinedload(Project.tareas_generales).joinedload(TareaGeneral.subtareas).joinedload(Subtarea.assigned_user)
        ).distinct().order_by(Project.end_date.desc()).all()

        for project_db in proyectos_con_subtareas_asignadas_sidebar:
            proyecto_data = {
                'id': project_db.id,
                'nombre': project_db.name,
                'tareas_generales': []
            }
            for tg_db in project_db.tareas_generales:
                subtareas_filtradas_por_apoyo = [
                    s for s in tg_db.subtareas if s.assigned_user_id == current_user.id
                ]

                if subtareas_filtradas_por_apoyo:
                    area_data = None
                    apoyos_area = []
                    if tg_db.area:
                        apoyos_area = [{'id': a.id, 'username': a.username} for a in tg_db.area.users if a.role == 'apoyo']
                        area_data = {'id': tg_db.area.id, 'nombre': tg_db.area.name, 'apoyos': apoyos_area}

                    subtareas_data = [{'id': s.id, 'nombre': s.title, 'fecha_limite': s.fecha_limite, 'status': s.status,
                                       'proyecto_nombre': project_db.name, 'asignado_a_nombre': s.assigned_user.username if s.assigned_user else 'Sin asignar'}
                                      for s in subtareas_filtradas_por_apoyo]

                    tarea_general_data = {
                        'id': tg_db.id,
                        'nombre': tg_db.title,
                        'area': area_data,
                        'subtareas': subtareas_data
                    }
                    proyecto_data['tareas_generales'].append(tarea_general_data)

                    for s_data in subtareas_data:
                        temp_subtarea = type('obj', (object,), s_data)()
                        if es_retrasada_subtarea(temp_subtarea):
                            subtareas_retrasadas.append(s_data)

            if proyecto_data['tareas_generales']:
                proyectos_para_sidebar.append(proyecto_data)

        # Proyectos para la tabla principal (solo los que tienen subtareas asignadas a este apoyo)
        main_projects_query = Project.query.join(TareaGeneral).join(Subtarea).filter(Subtarea.assigned_user_id == current_user.id).distinct()
        main_projects = main_projects_query.order_by(Project.end_date.desc()).all()


    # Mensaje flash para subtareas retrasadas (contenido principal del dashboard)
    if subtareas_retrasadas:
        flash(f'¡Atención! Tienes {len(subtareas_retrasadas)} subtarea(s) retrasada(s).', 'danger')

    # Contadores para el resumen del dashboard
    total_proyectos_activos = Project.query.filter_by(status='En ejecución').count()
    total_tareas_pendientes = TareaGeneral.query.filter_by(status='Pendiente').count()


    return render_template('dashboard.html',
                           proyectos=proyectos_para_sidebar,
                           main_projects=main_projects,
                           subtareas_retrasadas=subtareas_retrasadas,
                           total_proyectos_activos=total_proyectos_activos,
                           total_tareas_pendientes=total_tareas_pendientes,
                           user_role=current_user.role,
                           has_gestionar_usuarios_route=has_gestionar_usuarios_route) # <-- ¡PASADO A LA PLANTILLA!


@app.route('/crear_proyecto', methods=['GET', 'POST'])
@login_required
def crear_proyecto():
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden crear proyectos.', 'danger')
        return redirect(url_for('dashboard'))
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            description=form.description.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status='En ejecución',
            creator_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        flash('Proyecto creado exitosamente.', 'success')
        return redirect(url_for('dashboard'))

    # === NUEVO: Pasa la variable aquí también ===
    has_gestionar_usuarios_route = 'gestionar_usuarios' in app.view_functions
    return render_template('crear_proyecto.html', form=form, has_gestionar_usuarios_route=has_gestionar_usuarios_route)


# Rutas para ver detalles (simples redirecciones por ahora, necesitarás plantillas detalladas)


@app.route('/proyecto/<int:project_id>')
@login_required
def ver_proyecto(project_id):
    """Muestra los detalles de un proyecto específico y sus tareas generales."""
    project = Project.query.get_or_404(project_id)

    # Lógica de permisos similar a la de dashboard para `project_details.html`
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and project.area_id == current_user.area_id:
        can_view = True
    elif current_user.role == 'apoyo':
        # Verifica si el apoyo tiene alguna subtarea en este proyecto
        has_subtask_in_project = Subtarea.query.join(TareaGeneral).filter(
            Subtarea.assigned_user_id == current_user.id,
            TareaGeneral.project_id == project_id
        ).first()
        if has_subtask_in_subtask_in_project:
            can_view = True

    if not can_view:
        flash('No tienes permiso para ver este proyecto.', 'danger')
        return redirect(url_for('dashboard'))

    tareas_generales = TareaGeneral.query.filter_by(project_id=project_id).order_by(TareaGeneral.fecha_limite.desc()).all()

    # Si es usuario de apoyo, solo mostrar las tareas generales que contengan subtareas suyas
    if current_user.role == 'apoyo':
        filtered_tareas_generales = []
        for tg in tareas_generales:
            if Subtarea.query.filter_by(tarea_general_id=tg.id, assigned_user_id=current_user.id).first():
                filtered_tareas_generales.append(tg)
        tareas_generales = filtered_tareas_generales

    # === AÑADIDO: Lógica para pasar la variable al template ===
    has_gestionar_usuarios_route = 'gestionar_usuarios' in app.view_functions
    # ========================================================

    # Pasa el proyecto y las tareas generales a la plantilla `project_details.html`
    # Asegúrate de crear este archivo de plantilla para los detalles del proyecto.
    return render_template('project_details.html',
                           project=project,
                           tareas_generales=tareas_generales,
                           user_role=current_user.role,  # <-- Pasa el rol del usuario
                           has_gestionar_usuarios_route=has_gestionar_usuarios_route, # <-- Pasa la variable para el sidebar
                           # También puedes pasar la lista de proyectos para el sidebar aquí
                           # si quieres que el sidebar se actualice con la misma lógica del dashboard.
                           # Esto puede requerir duplicar la lógica de carga de proyectos o refactorizarla.
                           # Por ahora, solo pasamos el user_role y has_gestionar_usuarios_route.
                           # Si `proyectos` en el sidebar debe ser dinámico en cada página,
                           # tendrás que cargar `proyectos_para_sidebar` como en la función `dashboard()`.
                           # Si el sidebar de proyectos es estático o no necesitas que refleje siempre los
                           # proyectos filtrados de la página actual, no es estrictamente necesario.
                           # Asumo que para 'ver_proyecto', el sidebar de proyectos ya se llenará si el `base.html`
                           # es lo suficientemente inteligente para no depender de `proyectos` específicamente en cada vista,
                           # o que el `base.html` usa una variable global (que no es lo que estamos haciendo aquí)
                           # o que `proyectos` es un valor pasado solo en el dashboard.
                           # Si necesitas que la lista de proyectos en el sidebar sea dinámica en esta página,
                           # deberías cargar `proyectos_para_sidebar` de forma similar a como lo haces en `dashboard()`.
                           )

@app.route('/editar_proyecto/<int:project_id>', methods=['GET', 'POST'])
@login_required
def editar_proyecto(project_id):
    proyecto = Project.query.get_or_404(project_id)
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden editar proyectos.', 'danger')
        return redirect(url_for('dashboard'))

    form = ProjectForm(obj=proyecto)
    if form.validate_on_submit():
        form.populate_obj(proyecto)
        db.session.commit()
        flash('Proyecto actualizado exitosamente.', 'success')
        return redirect(url_for('ver_proyecto', project_id=project_id))

    return render_template('crear_proyecto.html',
                           form=form,
                           project=proyecto,
                           action="Editar")

@app.route('/eliminar_proyecto/<int:project_id>', methods=['POST'])
@login_required
def eliminar_proyecto(project_id):
    """Elimina un proyecto (solo para supervisores)."""
    proyecto = Project.query.get_or_404(project_id)
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden eliminar proyectos.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Eliminar subtareas y tareas generales asociadas antes de eliminar el proyecto
    for tg in proyecto.tareas_generales:
        for s in tg.subtareas:
            db.session.delete(s)
        db.session.delete(tg)
    
    db.session.delete(proyecto)
    db.session.commit()
    flash('Proyecto eliminado exitosamente.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/proyecto/<int:project_id>/nueva_tarea_general', methods=['GET', 'POST'])
@login_required
def nueva_tarea_general(project_id):
    """Maneja la creación de una nueva tarea general dentro de un proyecto."""
    project = Project.query.get_or_404(project_id)

    # Permisos: Solo supervisores pueden crear tareas generales
    if current_user.role != 'supervisor':
        flash('Solo los supervisores pueden crear tareas generales.', 'danger')
        return redirect(url_for('dashboard'))

    form = TareaGeneralForm()
    
    # La QuerySelectField para Area debe tener una query_factory que filtre si es necesario
    # Por ejemplo, si un supervisor solo puede asignar a ciertas áreas.
    # Si la QuerySelectField de `area_id` se define en `forms.py` usando `query_factory=lambda: Area.query.all()`,
    # entonces el formulario ya manejará la carga de áreas.
    
    if form.validate_on_submit():
        assigned_area = form.area_id.data # QuerySelectField ya devuelve el objeto Area seleccionado
        
        # Validar si el área existe y es válida (aunque QuerySelectField ya lo hace hasta cierto punto)
        if assigned_area:
            nueva_tg = TareaGeneral(
                title=form.title.data,
                description=form.description.data,
                fecha_limite=form.fecha_limite.data,
                prioridad=form.prioridad.data,
                status='Pendiente',
                project=project,
                area=assigned_area, # Asigna el objeto Area
                creator=current_user
            )
            db.session.add(nueva_tg)
            db.session.commit()
            flash('Tarea general creada exitosamente.', 'success')
            return redirect(url_for('ver_proyecto', project_id=project.id))
        else:
            flash('Error: El área asignada es inválida o no fue seleccionada.', 'danger')

    return render_template('crear_tarea_general.html', form=form, proyecto=project, action="Crear")

@app.route('/tarea_general/<int:tarea_general_id>')
@login_required
def ver_tarea_general(tarea_general_id):
    """Muestra los detalles de una tarea general y sus subtareas."""
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)
    
    # Lógica de permisos para ver la tarea general
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and current_user.area_id == tarea_general.area_id:
        can_view = True
    elif current_user.role == 'apoyo':
        # Un usuario de apoyo solo puede ver una tarea general si tiene alguna subtarea asignada a él dentro de esa TG.
        if Subtarea.query.filter_by(tarea_general_id=tarea_general_id, assigned_user_id=current_user.id).first():
            can_view = True

    if not can_view:
        flash("No tienes permiso para ver esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    subtareas = Subtarea.query.filter_by(tarea_general_id=tarea_general_id).order_by(Subtarea.fecha_limite.asc()).all()

    # Si es usuario de apoyo, solo mostrarle sus propias subtareas
    if current_user.role == 'apoyo':
        subtareas = [s for s in subtareas if s.assigned_user_id == current_user.id]

    return render_template('tarea_general_details.html',
                           tarea_general=tarea_general,
                           subtareas=subtareas,
                           es_retrasada_subtarea=es_retrasada_subtarea) # Pasa la función a la plantilla

@app.route('/tarea_general/<int:tarea_general_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tarea_general(tarea_general_id):
    """Maneja la edición de una tarea general."""
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permisos para editar tarea general
    if current_user.role != 'supervisor' and \
       (current_user.role != 'encargado' or current_user.area_id != tarea_general.area_id):
        flash("No tienes permiso para editar esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    form = TareaGeneralForm(obj=tarea_general) # Pre-llena el formulario con los datos existentes
    
    if form.validate_on_submit():
        tarea_general.title = form.title.data
        tarea_general.description = form.description.data
        tarea_general.fecha_limite = form.fecha_limite.data
        tarea_general.prioridad = form.prioridad.data
        tarea_general.area = form.area_id.data # Esto asigna el objeto Area seleccionado
        db.session.commit()
        flash("Tarea general actualizada exitosamente.", "success")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))

    return render_template('crear_tarea_general.html',
                           form=form,
                           proyecto=tarea_general.project,
                           tarea_general=tarea_general, # Pasa la tarea general para mostrar datos si es necesario
                           action="Editar")

@app.route('/tarea_general/<int:tarea_general_id>/eliminar', methods=['POST'])
@login_required
def eliminar_tarea_general(tarea_general_id):
    """Elimina una tarea general y sus subtareas asociadas."""
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permisos para eliminar tarea general
    if current_user.role != 'supervisor' and \
       (current_user.role != 'encargado' or current_user.area_id != tarea_general.area_id):
        flash("No tienes permiso para eliminar esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    proyecto_id_asociado = tarea_general.project_id
    
    # Eliminar subtareas antes de eliminar la tarea general
    for subtarea in tarea_general.subtareas:
        db.session.delete(subtarea)

    db.session.delete(tarea_general)
    db.session.commit()
    flash("Tarea general eliminada exitosamente.", "success")
    # Redirige al proyecto si existía, de lo contrario al dashboard
    if proyecto_id_asociado:
        return redirect(url_for('ver_proyecto', project_id=proyecto_id_asociado))
    else:
        return redirect(url_for('dashboard'))


# --- Rutas para Subtareas (Crear, Editar, Eliminar) ---

@app.route('/tarea_general/<int:tarea_general_id>/nueva_subtarea', methods=['GET', 'POST'])
@login_required
def nueva_subtarea(tarea_general_id):
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permisos: Supervisores pueden crear subtareas para cualquier Tarea General.
    # Encargados pueden crear subtareas para Tareas Generales de su área.
    if current_user.role == 'apoyo' or \
       (current_user.role == 'encargado' and current_user.area_id != tarea_general.area_id):
        flash('No tienes permiso para crear subtareas en esta tarea general.', 'danger')
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))

    form = SubtareaForm()
    # Filtrar usuarios asignables en el QuerySelectField para 'assigned_user_id'
    # Solo se deben mostrar usuarios con rol 'apoyo' y que pertenezcan al área de la tarea general
    form.assigned_user_id.query_factory = lambda: User.query.filter_by(
        role='apoyo',
        area_id=tarea_general.area_id # Asigna apoyos del área de la tarea general
    ).order_by(User.username).all()

    if form.validate_on_submit():
        assigned_user = form.assigned_user_id.data # QuerySelectField ya devuelve el objeto User
        
        # Validación extra: Asegurar que el usuario asignado sea de rol 'apoyo' y del área correcta
        if not assigned_user or assigned_user.role != 'apoyo' or assigned_user.area_id != tarea_general.area_id:
            flash('Error: El usuario asignado es inválido o no es un apoyo del área correcta.', 'danger')
            return render_template('crear_subtarea.html', form=form, tarea_general=tarea_general, project=tarea_general.project, action="Crear")

        nueva_sub = Subtarea(
            title=form.title.data,
            description=form.description.data,
            fecha_limite=form.fecha_limite.data,
            prioridad=form.prioridad.data,
            status='Pendiente',
            tarea_general=tarea_general,
            assigned_user=assigned_user, # Asigna el objeto User
            creator=current_user
        )
        db.session.add(nueva_sub)
        db.session.commit()
        flash('Subtarea creada exitosamente.', 'success')
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))
    
    return render_template('crear_subtarea.html', form=form, tarea_general=tarea_general, project=tarea_general.project, action="Crear")

@app.route('/subtarea/<int:subtarea_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_subtarea(subtarea_id):
    subtarea = Subtarea.query.get_or_404(subtarea_id)

    # Permisos:
    # Supervisor: puede editar cualquier subtarea
    # Encargado: puede editar subtareas de tareas generales de su área
    # Apoyo: puede editar sus propias subtareas
    can_edit = False
    if current_user.role == 'supervisor':
        can_edit = True
    elif current_user.role == 'encargado' and current_user.area_id == subtarea.tarea_general.area_id:
        can_edit = True
    elif current_user.role == 'apoyo' and subtarea.assigned_user_id == current_user.id:
        can_edit = True
    
    if not can_edit:
        flash("No tienes permiso para editar esta subtarea.", "danger")
        return redirect(url_for('ver_tarea_general', tarea_general_id=subtarea.tarea_general.id))

    form = SubtareaForm(obj=subtarea)

    # Filtrar usuarios asignables para el QuerySelectField
    # Solo usuarios de rol 'apoyo' del área de la tarea general.
    # Si el usuario actual es 'apoyo', solo se puede ver a sí mismo.
    if current_user.role == 'apoyo':
        form.assigned_user_id.query_factory = lambda: User.query.filter_by(id=current_user.id).all()
        # Puedes hacer el campo de solo lectura para apoyos si no deben cambiarlo
        # form.assigned_user_id.render_kw = {'disabled': True} # Esto debe manejarse en el template preferiblemente
    else: # Supervisor o Encargado
        form.assigned_user_id.query_factory = lambda: User.query.filter_by(
            role='apoyo',
            area_id=subtarea.tarea_general.area_id
        ).order_by(User.username).all()

    if form.validate_on_submit():
        assigned_user = form.assigned_user_id.data
        
        # Validar que el usuario asignado pertenezca al área de la tarea general si el current_user es encargado o supervisor
        # Para apoyos, la validación se asegura con el query_factory
        if (current_user.role == 'supervisor' or current_user.role == 'encargado') and \
           assigned_user and (assigned_user.role != 'apoyo' or assigned_user.area_id != subtarea.tarea_general.area_id):
            flash('No puedes asignar esta subtarea a un usuario fuera del rol de apoyo o del área correcta.', 'danger')
            return render_template('crear_subtarea.html', form=form, subtarea=subtarea, tarea_general=subtarea.tarea_general, project=subtarea.tarea_general.project, action="Editar")

        form.populate_obj(subtarea) # Actualiza el objeto subtarea con los datos del formulario
        db.session.commit()
        flash('Subtarea actualizada exitosamente.', 'success')
        return redirect(url_for('ver_tarea_general', tarea_general_id=subtarea.tarea_general.id))

    return render_template('crear_subtarea.html',
                           form=form,
                           subtarea=subtarea,
                           tarea_general=subtarea.tarea_general,
                           project=subtarea.tarea_general.project,
                           action="Editar")

@app.route('/subtarea/<int:subtarea_id>/eliminar', methods=['POST'])
@login_required
def eliminar_subtarea(subtarea_id):
    subtarea = Subtarea.query.get_or_404(subtarea_id)

    # Permisos para eliminar
    # Supervisor: puede eliminar cualquier subtarea
    # Encargado: puede eliminar subtareas de tareas generales de su área
    can_delete = False
    if current_user.role == 'supervisor':
        can_delete = True
    elif current_user.role == 'encargado' and current_user.area_id == subtarea.tarea_general.area_id:
        can_delete = True
    
    if not can_delete:
        flash("No tienes permiso para eliminar esta subtarea.", "danger")
        return redirect(url_for('ver_tarea_general', tarea_general_id=subtarea.tarea_general.id))

    tarea_general_id = subtarea.tarea_general.id
    db.session.delete(subtarea)
    db.session.commit()
    flash('Subtarea eliminada exitosamente.', 'success')
    return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general_id))

# --- Rutas para ver detalles de áreas (Nueva ruta requerida por la jerarquía del sidebar) ---
@app.route('/area/<int:area_id>')
@login_required
def ver_area(area_id):
    area = Area.query.get_or_404(area_id)
    # Lógica de permisos: un supervisor o el encargado del área puede verla.
    # Un apoyo puede verla si pertenece a esa área.
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and current_user.area_id == area_id:
        can_view = True
    elif current_user.role == 'apoyo' and current_user.area_id == area_id:
        can_view = True
    
    if not can_view:
        flash("No tienes permiso para ver los detalles de esta área.", "danger")
        return redirect(url_for('dashboard'))

    # Puedes obtener proyectos, tareas generales, y usuarios (líderes/apoyos) asociados a esta área
    # y pasarlos a una plantilla `area_details.html`
    
    # Usuarios en esta área (asumiendo que User tiene una relación con Area)
    users_in_area = User.query.filter_by(area_id=area_id).all()
    
    # Tareas generales directamente asignadas a esta área
    tareas_generales_area = TareaGeneral.query.filter_by(area_id=area_id).all()

    return render_template('area_details.html', area=area, users_in_area=users_in_area, tareas_generales_area=tareas_generales_area)

# --- Ruta para ver perfil de usuario (líder o apoyo) ---
@app.route('/user_profile/<int:user_id>')
@login_required
def ver_perfil_usuario(user_id):
    user_profile = User.query.get_or_404(user_id)
    
    # Lógica de permisos para ver perfiles:
    # Supervisor: puede ver cualquier perfil
    # Encargado: puede ver perfiles de usuarios en su área
    # Apoyo: solo puede ver su propio perfil
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and user_profile.area_id == current_user.area_id:
        can_view = True
    elif current_user.role == 'apoyo' and user_profile.id == current_user.id:
        can_view = True

    if not can_view:
        flash("No tienes permiso para ver este perfil de usuario.", "danger")
        return redirect(url_for('dashboard'))
    
    # También puedes pasar las subtareas asignadas a este usuario si es un "apoyo" o "encargado"
    subtasks_assigned = []
    if user_profile.role == 'apoyo' or user_profile.role == 'encargado':
        subtasks_assigned = Subtarea.query.filter_by(assigned_user_id=user_profile.id).order_by(Subtarea.fecha_limite).all()

    return render_template('user_profile.html', user_profile=user_profile, subtasks_assigned=subtasks_assigned)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)