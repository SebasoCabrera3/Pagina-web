from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date


db = SQLAlchemy()

class Area(db.Model):
    __tablename__ = 'area'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    codigo = db.Column(db.String(16), unique=True, nullable=False)

    # Relación bidireccional con User
    # 'users' es el nombre que usaremos para acceder a los usuarios desde un objeto Area (e.g., area.users)
    # 'area' es el nombre del atributo en la clase User que apunta a un objeto Area
    users = db.relationship('User', back_populates='area', lazy=True)

    # Relación bidireccional con Project
    # 'projects' está aquí porque Area puede tener proyectos si así lo defines.
    # Si un proyecto tiene UN área, pero un área puede tener VARIOS proyectos.
    projects = db.relationship('Project', back_populates='area', lazy=True)

    # Relación bidireccional con TareaGeneral
    tareas_generales = db.relationship('TareaGeneral', back_populates='area', lazy=True)

    def __repr__(self):
        return f"<Area {self.name} | Código: {self.codigo}>"


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='apoyo')

    # Relación bidireccional con Area
    # 'area_id' es la Foreign Key
    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True) # Los usuarios pueden no tener área al inicio (ej. supervisor global)
    # 'area' es el objeto Area accesible desde User (e.g., user.area)
    # 'users' es el nombre del atributo en la clase Area que apunta a una lista de Users
    area = db.relationship('Area', back_populates='users')

    # Relación de líderes y apoyos (autorelación bidireccional)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # 'leader' es el objeto User que es el líder de este usuario
    leader = db.relationship('User', remote_side=[id], back_populates='apoyos')
    # 'apoyos' es la lista de usuarios que este usuario lidera
    apoyos = db.relationship('User', back_populates='leader', lazy=True) # Nombre 'apoyos' para evitar conflicto

    is_active = db.Column(db.Boolean, default=True)
    confirmed = db.Column(db.Boolean, default=False)

    # Relaciones bidireccionales con otras tablas
    created_projects = db.relationship('Project', back_populates='creator', lazy=True, foreign_keys='Project.creator_id')
    tareas_generales_creadas = db.relationship('TareaGeneral', back_populates='creator', lazy=True, foreign_keys='TareaGeneral.creator_id')
    subtareas_asignadas = db.relationship('Subtarea', back_populates='assigned_user', lazy=True, foreign_keys='Subtarea.assigned_user_id')
    subtareas_creadas = db.relationship('Subtarea', back_populates='creator', lazy=True, foreign_keys='Subtarea.creator_id')

    def __repr__(self):
        return f"<User {self.username} ({self.role}) - Área: {self.area.name if self.area else 'N/A'}>"


class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True) # Hice la descripción nullable=True, es buena práctica
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='En ejecución')

    # RELACIÓN CRÍTICA: area_id ahora es nullable=True
    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True) # <-- CORREGIDO: Ahora puede ser NULL
    area = db.relationship('Area', back_populates='projects')

    # Relación bidireccional con User (creador)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='created_projects', foreign_keys=[creator_id])

    # Relación bidireccional con TareaGeneral
    tareas_generales = db.relationship('TareaGeneral', back_populates='project', lazy=True, cascade="all, delete-orphan")

    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def current_display_status(self):
        estados = {
            'pendiente': 'Pendiente',
            'en ejecucion': 'En Ejecución',
            'en ejecución': 'En Ejecución',
            'finalizado': 'Finalizado',
            'retrasado': 'Retrasado'
        }
        return estados.get(self.status.lower(), self.status.title())

    @property
    def is_delayed(self):
        if self.end_date and self.status.lower() not in ['finalizado', 'cancelado']:
            return self.end_date < date.today()
        return False

    def __repr__(self):
        # Asegúrate de manejar el caso donde self.area es None
        return f"<Project {self.name} | Área: {self.area.name if self.area else 'No Asignada'}>"


# La clase Task ha sido eliminada por completo, ya que no se utiliza y causaba errores.
# Si necesitas una clase "Task" distinta de TareaGeneral/Subtarea, deberías reevaluar su propósito y cómo se relaciona.

class TareaGeneral(db.Model):
    __tablename__ = 'tarea_general'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    fecha_limite = db.Column(db.Date, nullable=True)
    prioridad = db.Column(db.String(20), default='Media')
    status = db.Column(db.String(50), default='Pendiente')
    porcentaje_avance = db.Column(db.Float, default=0.0)

    # Relación bidireccional con Project
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    project = db.relationship('Project', back_populates='tareas_generales')

    # Relación bidireccional con Area
    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=False) # Tarea General SIEMPRE debe tener un área
    area = db.relationship('Area', back_populates='tareas_generales')

    # Relación bidireccional con User (creador)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='tareas_generales_creadas', foreign_keys=[creator_id])

    # Relación bidireccional con Subtarea
    subtareas = db.relationship('Subtarea', back_populates='tarea_general', lazy=True, cascade="all, delete-orphan")

    def calculate_and_update_progress(self):
        if not self.subtareas:
            self.porcentaje_avance = 0
            return

        total = len(self.subtareas)
        completadas = len([s for s in self.subtareas if s.status.lower() == 'finalizado'])
        self.porcentaje_avance = (completadas / total) * 100

    @property
    def is_delayed(self):
        if self.fecha_limite and self.status.lower() not in ['finalizado', 'cancelado']:
            return self.fecha_limite < date.today()
        return False

    def __repr__(self):
        return f"<TareaGeneral {self.title} - Área: {self.area.name if self.area else 'N/A'}>"


class Subtarea(db.Model):
    __tablename__ = 'subtarea'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Pendiente')
    prioridad = db.Column(db.String(20), nullable=False, default='Media')
    fecha_limite = db.Column(db.Date, nullable=True)

    # Relación bidireccional con TareaGeneral
    tarea_general_id = db.Column(db.Integer, db.ForeignKey('tarea_general.id'), nullable=False)
    tarea_general = db.relationship('TareaGeneral', back_populates='subtareas')

    # Relación bidireccional con User (asignado)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Una subtarea podría no estar asignada al inicio
    assigned_user = db.relationship('User', back_populates='subtareas_asignadas', foreign_keys=[assigned_user_id])

    # Relación bidireccional con User (creador)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='subtareas_creadas', foreign_keys=[creator_id])

    @property
    def is_delayed(self):
        if self.fecha_limite and self.status.lower() not in ['finalizado', 'cancelado']:
            return self.fecha_limite < date.today()
        return False

    def __repr__(self):
        return f"<Subtarea {self.title} - Estado {self.status}>"