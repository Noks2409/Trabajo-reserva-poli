"""
Base de datos para sistema de reservas de espacios.
Politécnico Grancolombiano


La variable de entorno DATABASE_URL determina cuál usar.
"""

import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Time, ForeignKey, Table, Numeric, Boolean, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session
from datetime import date, time

# ─────────────────────────────────────────────
#  CONFIGURACIÓN BASE
# ─────────────────────────────────────────────

Base = declarative_base()


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///reservas.db")

# Corregir URLs antiguas de Railway: "postgres://" → "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# En entornos serverless (Vercel) el pool de conexiones no funciona bien:
# cada request puede correr en un proceso nuevo y las conexiones del pool
# quedan abiertas pero muertas. NullPool abre y cierra una conexión fresca
# por request, eliminando el error "SSL connection has been closed unexpectedly".
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False)
else:
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={"sslmode": "require"},
        echo=False,
    )

# Fábrica de sesiones
Session = scoped_session(sessionmaker(bind=engine))


# ─────────────────────────────────────────────
#  TABLA INTERMEDIA: Reserva ↔ Espacio (muchos a muchos)
# ─────────────────────────────────────────────

reserva_espacio = Table(
    "reserva_espacio",
    Base.metadata,
    Column("reserva_id", Integer, ForeignKey("reserva.id"), primary_key=True),
    Column("espacio_id", Integer, ForeignKey("espacio.id"), primary_key=True),
)


# ─────────────────────────────────────────────
#  USUARIOS (herencia: una sola tabla con columna 'rol')
# ─────────────────────────────────────────────

class Usuario(Base):
    """
    Clase base para todos los tipos de usuario.
    La columna 'rol' determina qué tipo es: docente, administrativo, externa, admin.
    """
    __tablename__ = "usuario"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    nombre     = Column(String, nullable=False)
    correo     = Column(String, nullable=False, unique=True)
    contrasena = Column(String, nullable=False)
    rol        = Column(String, nullable=False)  # 'docente' | 'administrativo' | 'externa' | 'admin' | 'logistica'

    # Estado y control de cuenta
    activo  = Column(Boolean, default=True, nullable=False)   # False = cuenta desactivada
    strikes = Column(Integer, default=0,    nullable=False)   # Reportes asignados por el admin

    # Campos de Docente
    cod_docente  = Column(String,  nullable=True)
    departamento = Column(String,  nullable=True)

    # Campos de Administrativo
    dependencia = Column(String, nullable=True)

    # Campos de PersonaExterna
    empresa  = Column(String, nullable=True)
    telefono = Column(String, nullable=True)

    # Relaciones
    reservas = relationship("Reserva", back_populates="usuario", foreign_keys="Reserva.usuario_id")
    sanciones_recibidas = relationship(
        "Sancion",
        foreign_keys="Sancion.usuario_id",
        back_populates="usuario",
    )
    sanciones_aplicadas = relationship(
        "Sancion",
        foreign_keys="Sancion.admin_id",
        back_populates="admin",
    )

    # Discriminador de herencia
    __mapper_args__ = {
        "polymorphic_on": rol,
        "polymorphic_identity": "usuario",
    }

    def __repr__(self):
        return f"<Usuario id={self.id} nombre='{self.nombre}' rol='{self.rol}'>"

    # ── Métodos del diagrama ──
    def iniciar_sesion(self, correo: str, contrasena: str) -> bool:
        return self.correo == correo and self.contrasena == contrasena

    def cerrar_sesion(self):
        print(f"{self.nombre} cerró sesión.")

    def consultar_perfil(self):
        return {
            "id": self.id, "nombre": self.nombre,
            "correo": self.correo, "rol": self.rol
        }

    def actualizar_perfil(self, session, **kwargs):
        for campo, valor in kwargs.items():
            if hasattr(self, campo):
                setattr(self, campo, valor)
        session.commit()


class Docente(Usuario):
    __mapper_args__ = {"polymorphic_identity": "docente"}

    def solicitar_reserva(self, session, **datos) -> "Reserva":
        reserva = Reserva(usuario_id=self.id, estado="pendiente", **datos)
        session.add(reserva)
        session.commit()
        return reserva

    def cancelar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "cancelada"
        session.commit()

    def modificar_fecha_hora_reserva(self, session, reserva: "Reserva",
                                     fecha=None, hora_inicio=None, hora_fin=None):
        if fecha:        reserva.fecha       = fecha
        if hora_inicio:  reserva.hora_inicio = hora_inicio
        if hora_fin:     reserva.hora_fin    = hora_fin
        session.commit()

    def consultar_reservas_propias(self, session):
        return session.query(Reserva).filter_by(usuario_id=self.id).all()

    def registrar_calificacion(self, session, reserva: "Reserva", puntuacion: int,
                               comentario: str) -> "Calificacion":
        cal = Calificacion(reserva_id=reserva.id, puntuacion=puntuacion,
                           comentario=comentario, fecha=date.today())
        session.add(cal)
        session.commit()
        return cal


class Administrativo(Usuario):
    __mapper_args__ = {"polymorphic_identity": "administrativo"}

    def solicitar_reserva(self, session, **datos) -> "Reserva":
        reserva = Reserva(usuario_id=self.id, estado="pendiente", **datos)
        session.add(reserva)
        session.commit()
        return reserva

    def cancelar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "cancelada"
        session.commit()

    def modificar_fecha_hora_reserva(self, session, reserva: "Reserva",
                                     fecha=None, hora_inicio=None, hora_fin=None):
        if fecha:        reserva.fecha       = fecha
        if hora_inicio:  reserva.hora_inicio = hora_inicio
        if hora_fin:     reserva.hora_fin    = hora_fin
        session.commit()

    def consultar_reservas_propias(self, session):
        return session.query(Reserva).filter_by(usuario_id=self.id).all()

    def registrar_calificacion(self, session, reserva: "Reserva", puntuacion: int,
                               comentario: str) -> "Calificacion":
        cal = Calificacion(reserva_id=reserva.id, puntuacion=puntuacion,
                           comentario=comentario, fecha=date.today())
        session.add(cal)
        session.commit()
        return cal


class PersonaExterna(Usuario):
    __mapper_args__ = {"polymorphic_identity": "externa"}


class Institucional(Usuario):
    """
    Usuario con correo @poligran.edu.co.
    Tiene permisos equivalentes a Docente y Administrativo.
    """
    __mapper_args__ = {"polymorphic_identity": "institucional"}
    def solicitar_reserva(self, session, **datos) -> "Reserva":
        reserva = Reserva(usuario_id=self.id, estado="pendiente", **datos)
        session.add(reserva)
        session.commit()
        return reserva

    def cancelar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "cancelada"
        session.commit()

    def modificar_fecha_hora_reserva(self, session, reserva: "Reserva",
                                     fecha=None, hora_inicio=None, hora_fin=None):
        if fecha:        reserva.fecha       = fecha
        if hora_inicio:  reserva.hora_inicio = hora_inicio
        if hora_fin:     reserva.hora_fin    = hora_fin
        session.commit()

    def consultar_reservas_propias(self, session):
        return session.query(Reserva).filter_by(usuario_id=self.id).all()

    def registrar_calificacion(self, session, reserva: "Reserva", puntuacion: int,
                               comentario: str) -> "Calificacion":
        cal = Calificacion(reserva_id=reserva.id, puntuacion=puntuacion,
                           comentario=comentario, fecha=date.today())
        session.add(cal)
        session.commit()
        return cal

    def solicitar_reserva(self, session, **datos) -> "Reserva":
        reserva = Reserva(usuario_id=self.id, estado="pendiente", **datos)
        session.add(reserva)
        session.commit()
        return reserva

    def cancelar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "cancelada"
        session.commit()

    def modificar_fecha_hora_reserva(self, session, reserva: "Reserva",
                                     fecha=None, hora_inicio=None, hora_fin=None):
        if fecha:        reserva.fecha       = fecha
        if hora_inicio:  reserva.hora_inicio = hora_inicio
        if hora_fin:     reserva.hora_fin    = hora_fin
        session.commit()

    def consultar_reservas_propias(self, session):
        return session.query(Reserva).filter_by(usuario_id=self.id).all()

    def registrar_calificacion(self, session, reserva: "Reserva", puntuacion: int,
                               comentario: str) -> "Calificacion":
        cal = Calificacion(reserva_id=reserva.id, puntuacion=puntuacion,
                           comentario=comentario, fecha=date.today())
        session.add(cal)
        session.commit()
        return cal


class PersonalLogistica(Usuario):
    """
    Personal operativo creado y administrado exclusivamente por un administrador.
    No crea, modifica ni elimina reservas; solo consulta las que tenga asignadas.

    Herencia de tabla separada (joined table inheritance): la fila principal
    va en 'usuario' y el id se replica en 'logistica' para satisfacer la FK
    que PostgreSQL/Railway tiene desde el esquema original del proyecto.
    """
    __tablename__ = "logistica"
    id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "logistica"}

    reservas_logistica = relationship(
        "Reserva",
        foreign_keys="Reserva.logistica_id",
        back_populates="logistica",
    )

    def consultar_reservas_asignadas(self, session):
        return session.query(Reserva).filter_by(logistica_id=self.id).all()


class Admin(Usuario):
    __mapper_args__ = {"polymorphic_identity": "admin"}

    def consultar_listado_usuarios(self, session):
        return session.query(Usuario).all()

    def filtrar_usuarios(self, session, rol: str):
        return session.query(Usuario).filter_by(rol=rol).all()

    def crear_agenda_semestral(self, session, semestre: str,
                               fecha_inicio: date, fecha_fin: date) -> "AgendaSemestral":
        agenda = AgendaSemestral(semestre=semestre,
                                 fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
        session.add(agenda)
        session.commit()
        return agenda

    def aprobar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "aprobada"
        session.commit()

    def rechazar_reserva(self, session, reserva: "Reserva"):
        reserva.estado = "rechazada"
        session.commit()

    def crear_reserva(self, session, **datos) -> "Reserva":
        reserva = Reserva(**datos)
        session.add(reserva)
        session.commit()
        return reserva

    def actualizar_reserva(self, session, reserva: "Reserva", **datos):
        for campo, valor in datos.items():
            if hasattr(reserva, campo):
                setattr(reserva, campo, valor)
        session.commit()

    def eliminar_reserva(self, session, reserva: "Reserva"):
        session.delete(reserva)
        session.commit()

    def consultar_historial_reservas(self, session):
        return session.query(Reserva).all()

    def generar_reporte(self, session, tipo: str) -> "Reporte":
        reporte = Reporte(tipo=tipo, fecha_generacion=date.today())
        session.add(reporte)
        session.commit()
        return reporte

    def exportar_csv(self, session, nombre_archivo: str = "reporte.csv"):
        import csv
        reservas = session.query(Reserva).all()
        with open(nombre_archivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "tipo_evento", "fecha", "estado", "usuario_id"])
            for r in reservas:
                writer.writerow([r.id, r.tipo_evento, r.fecha, r.estado, r.usuario_id])
        print(f"Exportado a {nombre_archivo}")


# ─────────────────────────────────────────────
#  RESERVA
# ─────────────────────────────────────────────

class Reserva(Base):
    __tablename__ = "reserva"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    cant_personas = Column(Integer, nullable=False)
    tipo_evento   = Column(String,  nullable=False)
    finalidad     = Column(String,  nullable=True)
    indumentaria          = Column(String, nullable=True)
    servicios_adicionales = Column(String, nullable=True)  # RF-11: sonido, video, sillas, etc.
    justificacion_rechazo = Column(String, nullable=True)  # Razón del rechazo (obligatoria al rechazar)
    fecha        = Column(Date,     nullable=False)
    hora_inicio  = Column(Time,     nullable=False)
    hora_fin     = Column(Time,     nullable=False)
    estado       = Column(String,   nullable=False, default="pendiente")
    # Estado puede ser: 'pendiente' | 'aprobada' | 'rechazada' | 'cancelada'

    usuario_id   = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    logistica_id = Column(Integer, ForeignKey("logistica.id"), nullable=True)

    # Relaciones
    usuario            = relationship("Usuario",               foreign_keys=[usuario_id], back_populates="reservas")
    logistica          = relationship("PersonalLogistica",     foreign_keys=[logistica_id], back_populates="reservas_logistica")
    espacios           = relationship("Espacio",               secondary=reserva_espacio, back_populates="reservas")
    calificacion       = relationship("Calificacion",          back_populates="reserva", uselist=False)
    personas_externas  = relationship("PersonaExternaReserva", back_populates="reserva",
                                      cascade="all, delete-orphan")
    sanciones          = relationship("Sancion", back_populates="reserva")

    def __repr__(self):
        return f"<Reserva id={self.id} evento='{self.tipo_evento}' estado='{self.estado}'>"

    def solicitar(self, session):
        self.estado = "pendiente"
        session.commit()

    def cancelar(self, session):
        self.estado = "cancelada"
        session.commit()

    def modificar_fecha_hora(self, session, fecha=None, hora_inicio=None, hora_fin=None):
        if fecha:        self.fecha       = fecha
        if hora_inicio:  self.hora_inicio = hora_inicio
        if hora_fin:     self.hora_fin    = hora_fin
        session.commit()

    def consultar(self):
        return {
            "id": self.id, "tipo_evento": self.tipo_evento,
            "fecha": self.fecha, "estado": self.estado
        }

    def actualizar(self, session, **datos):
        for campo, valor in datos.items():
            if hasattr(self, campo):
                setattr(self, campo, valor)
        session.commit()

    def eliminar(self, session):
        session.delete(self)
        session.commit()


# ─────────────────────────────────────────────
#  ESPACIO
# ─────────────────────────────────────────────

# Mapa de conflictos físicos: si X está reservado, estos espacios quedan inhabilitados
CONFLICTOS = {
    "Sala B1":               ["Sala B3", "Auditorio Completo"],
    "Sala B2":               ["Sala B3", "Auditorio Completo"],
    "Sala B3":               ["Sala B1", "Sala B2", "Auditorio Completo"],
    "Sala de Música y Baile": ["Auditorio Completo"],
    "Auditorio Completo":    ["Sala B1", "Sala B2", "Sala B3", "Sala de Música y Baile"],
}


class Espacio(Base):
    __tablename__ = "espacio"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    nombre    = Column(String,  nullable=False)
    capacidad = Column(Integer, nullable=False)
    costo_externo = Column(Numeric(12, 2), nullable=True)
    # costo_externo: valor en COP que paga una Persona Externa por reservar este espacio
    # None = sin costo (docentes, administrativos, institucionales no pagan)

    reservas  = relationship("Reserva", secondary=reserva_espacio, back_populates="espacios")

    def __repr__(self):
        return f"<Espacio id={self.id} nombre='{self.nombre}' cap={self.capacidad}>"

    def registrar(self, session):
        session.add(self)
        session.commit()

    def consultar_disponibilidad(self, session, fecha: date, hora_inicio: time, hora_fin: time):
        """Retorna True si el espacio está libre en ese horario considerando conflictos físicos."""
        # Espacios a verificar: este mismo + todos los que comparten estructura física
        nombres_a_verificar = [self.nombre] + CONFLICTOS.get(self.nombre, [])
        for nombre in nombres_a_verificar:
            esp = session.query(Espacio).filter_by(nombre=nombre).first()
            if not esp:
                continue
            ocupadas = (
                session.query(Reserva)
                .filter(
                    Reserva.espacios.contains(esp),
                    Reserva.fecha == fecha,
                    Reserva.estado.in_(["aprobada", "pendiente"]),
                    Reserva.hora_inicio < hora_fin,
                    Reserva.hora_fin   > hora_inicio,
                )
                .count()
            )
            if ocupadas > 0:
                return False
        return True


# ─────────────────────────────────────────────
#  PERSONA EXTERNA DE RESERVA
# ─────────────────────────────────────────────

class PersonaExternaReserva(Base):
    """
    Persona externa asociada a una reserva.
    El responsable es siempre el usuario que creó la reserva.
    """
    __tablename__ = "persona_externa_reserva"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nombre        = Column(String, nullable=False)
    cedula        = Column(String, nullable=False)
    fecha_ingreso = Column(Date,   nullable=True)
    fecha_salida  = Column(Date,   nullable=True)

    reserva_id = Column(Integer, ForeignKey("reserva.id"), nullable=False)
    reserva    = relationship("Reserva", back_populates="personas_externas")

    def __repr__(self):
        return f"<PersonaExternaReserva id={self.id} nombre='{self.nombre}' reserva_id={self.reserva_id}>"


# ─────────────────────────────────────────────
#  CALIFICACIÓN
# ─────────────────────────────────────────────

class Calificacion(Base):
    __tablename__ = "calificacion"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    puntuacion = Column(Integer, nullable=False)   # 1 a 5 estrellas
    comentario = Column(String,  nullable=True)
    fecha      = Column(Date,    nullable=False)
    # Respuesta del administrador a la calificación del usuario
    respuesta_admin = Column(String, nullable=True)

    reserva_id = Column(Integer, ForeignKey("reserva.id"), unique=True, nullable=False)
    reserva    = relationship("Reserva", back_populates="calificacion")

    def __repr__(self):
        return f"<Calificacion id={self.id} puntuacion={self.puntuacion}>"

    def registrar(self, session):
        session.add(self)
        session.commit()

    def consultar(self):
        return {"puntuacion": self.puntuacion, "comentario": self.comentario, "fecha": self.fecha}


# ─────────────────────────────────────────────
#  AGENDA SEMESTRAL
# ─────────────────────────────────────────────

class Sancion(Base):
    __tablename__ = "sancion"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    tipo        = Column(String, nullable=False, default="advertencia")
    descripcion = Column(String, nullable=False)
    fecha       = Column(Date, nullable=False, default=date.today)

    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    reserva_id = Column(Integer, ForeignKey("reserva.id"), nullable=True)
    admin_id   = Column(Integer, ForeignKey("usuario.id"), nullable=False)

    usuario = relationship(
        "Usuario",
        foreign_keys=[usuario_id],
        back_populates="sanciones_recibidas",
    )
    reserva = relationship("Reserva", back_populates="sanciones")
    admin   = relationship(
        "Usuario",
        foreign_keys=[admin_id],
        back_populates="sanciones_aplicadas",
    )

    def __repr__(self):
        return f"<Sancion id={self.id} usuario_id={self.usuario_id} tipo='{self.tipo}'>"

    def registrar(self, session):
        session.add(self)
        session.commit()


class AgendaSemestral(Base):
    __tablename__ = "agenda_semestral"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    semestre               = Column(String,  nullable=False)   # ej. '2025-1'
    fecha_inicio           = Column(Date,    nullable=False)
    fecha_fin              = Column(Date,    nullable=False)
    restricciones_aplicadas = Column(String, nullable=True)   # Texto descriptivo de restricciones

    bloques = relationship("BloqueHorario", back_populates="agenda")

    def __repr__(self):
        return f"<AgendaSemestral semestre='{self.semestre}'>"

    def crear(self, session):
        session.add(self)
        session.commit()

    def aplicar_restricciones(self):
        print(f"Aplicando restricciones a la agenda {self.semestre}")

    def bloquear_dia(self, session, fecha: date, hora_inicio: time, hora_fin: time):
        bloque = BloqueHorario(
            agenda_id=self.id, fecha=fecha,
            hora_inicio=hora_inicio, hora_fin=hora_fin
        )
        session.add(bloque)
        session.commit()
        return bloque


# ─────────────────────────────────────────────
#  BLOQUE HORARIO
# ─────────────────────────────────────────────

class BloqueHorario(Base):
    __tablename__ = "bloque_horario"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    fecha       = Column(Date, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin    = Column(Time, nullable=False)

    agenda_id   = Column(Integer, ForeignKey("agenda_semestral.id"), nullable=False)
    agenda      = relationship("AgendaSemestral", back_populates="bloques")

    def __repr__(self):
        return f"<BloqueHorario fecha={self.fecha} {self.hora_inicio}-{self.hora_fin}>"

    def bloquear(self, session):
        session.add(self)
        session.commit()

    def consultar(self):
        return {"fecha": self.fecha, "hora_inicio": self.hora_inicio, "hora_fin": self.hora_fin}


# ─────────────────────────────────────────────
#  REPORTE
# ─────────────────────────────────────────────

class Reporte(Base):
    __tablename__ = "reporte"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    tipo             = Column(String, nullable=False)
    fecha_generacion = Column(Date,   nullable=False)

    def __repr__(self):
        return f"<Reporte id={self.id} tipo='{self.tipo}'>"

    def generar(self):
        print(f"Generando reporte tipo '{self.tipo}' del {self.fecha_generacion}")

    def exportar_csv(self, nombre_archivo: str = "reporte_exportado.csv"):
        import csv
        with open(nombre_archivo, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "tipo", "fecha_generacion"])
            writer.writerow([self.id, self.tipo, self.fecha_generacion])
        print(f"Reporte exportado a {nombre_archivo}")


# ─────────────────────────────────────────────
#  FECHAS BLOQUEADAS (administradas por el admin)
# ─────────────────────────────────────────────

class FechaBloqueada(Base):
    """
    Fecha específica bloqueada manualmente por un administrador.
    Las fechas bloqueadas impiden crear nuevas reservas ese día.
    Solo el administrador puede desbloquearlas.
    """
    __tablename__ = "fecha_bloqueada"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    fecha    = Column(Date,    nullable=False, unique=True)
    motivo   = Column(String,  nullable=True)
    admin_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)

    admin = relationship("Usuario", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<FechaBloqueada {self.fecha} motivo='{self.motivo}'>"


# ─────────────────────────────────────────────
#  CREAR TABLAS EN LA BASE DE DATOS
# ─────────────────────────────────────────────

def crear_base_de_datos():
    """Crea todas las tablas en el archivo reservas.db y aplica migraciones incrementales."""
    Base.metadata.create_all(engine)
    _migrar_esquema()
    _migrar_esquema_postgres()
    print("[OK] Base de datos lista.")


def _migrar_esquema():
    """
    
    Agrega columnas nuevas a las tablas existentes sin perder datos.
    """
    import sqlite3
    import os
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not DATABASE_URL.startswith("sqlite"):
        return  # PostgreSQL: usar Alembic en producción
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # ── Tabla: calificacion ──────────────────────────────────────
        cur.execute("PRAGMA table_info(calificacion)")
        cols_cal = {row[1] for row in cur.fetchall()}
        if "respuesta_admin" not in cols_cal:
            cur.execute("ALTER TABLE calificacion ADD COLUMN respuesta_admin TEXT")
            print("[MIGRACIÓN] 'calificacion.respuesta_admin' agregada.")

        # ── Tabla: usuario ───────────────────────────────────────────
        cur.execute("PRAGMA table_info(usuario)")
        cols_usr = {row[1] for row in cur.fetchall()}
        if "activo" not in cols_usr:
            cur.execute("ALTER TABLE usuario ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
            print("[MIGRACIÓN] 'usuario.activo' agregada.")
        if "strikes" not in cols_usr:
            cur.execute("ALTER TABLE usuario ADD COLUMN strikes INTEGER NOT NULL DEFAULT 0")
            print("[MIGRACIÓN] 'usuario.strikes' agregada.")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sancion'")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE sancion (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo        TEXT NOT NULL DEFAULT 'advertencia',
                    descripcion TEXT NOT NULL,
                    fecha       DATE NOT NULL,
                    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
                    reserva_id  INTEGER REFERENCES reserva(id),
                    admin_id    INTEGER NOT NULL REFERENCES usuario(id)
                )
            """)
            print("[MIGRACIÓN] Tabla 'sancion' creada.")

        # ── Tabla: reserva ───────────────────────────────────────────
        # (Las columnas eliminadas como cant_utileros se mantienen en la BD por
        #  compatibilidad pero ya no se usan en la aplicación.)
        cur.execute("PRAGMA table_info(reserva)")
        cols_reserva = {row[1] for row in cur.fetchall()}
        if "logistica_id" not in cols_reserva:
            cur.execute("ALTER TABLE reserva ADD COLUMN logistica_id INTEGER REFERENCES logistica(id)")
            print("[MIGRACIÓN] 'reserva.logistica_id' agregada.")

        # ── Tabla: persona_externa_reserva ───────────────────────────
        # La tabla se crea automáticamente por create_all si no existe.
        # Migración defensiva por si la BD fue creada antes:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='persona_externa_reserva'")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE persona_externa_reserva (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre        TEXT NOT NULL,
                    cedula        TEXT NOT NULL,
                    fecha_ingreso DATE,
                    fecha_salida  DATE,
                    reserva_id    INTEGER NOT NULL REFERENCES reserva(id)
                )
            """)
            print("[MIGRACIÓN] Tabla 'persona_externa_reserva' creada.")

        # ── Tabla: agenda_semestral ──────────────────────────────────
        cur.execute("PRAGMA table_info(agenda_semestral)")
        cols_ag = {row[1] for row in cur.fetchall()}
        if "restricciones_aplicadas" not in cols_ag:
            cur.execute("ALTER TABLE agenda_semestral ADD COLUMN restricciones_aplicadas TEXT")
            print("[MIGRACIÓN] 'agenda_semestral.restricciones_aplicadas' agregada.")

        con.commit()
        con.close()
    except Exception as e:
        print(f"[MIGRACIÓN] Error: {e}")


def _migrar_esquema_postgres():
    """
    Migraciones específicas para PostgreSQL (Railway).

    Problema histórico: 'PersonalLogistica' usó herencia de tabla separada
    con __tablename__ = 'logistica'. La tabla 'logistica' existe en la BD y
    la FK reserva.logistica_id apunta a ella.  Cuando se refactorizó a
    herencia de una sola tabla, los usuarios nuevos de logística solo se
    insertaban en 'usuario', nunca en 'logistica', rompiendo la FK.

    Esta migración copia a 'logistica' los usuarios que ya existen en
    'usuario' con rol='logistica' pero que aún no tienen fila en 'logistica'.
    Es idempotente: puede ejecutarse varias veces sin daño.
    """
    if DATABASE_URL.startswith("sqlite"):
        return  # Solo aplica a PostgreSQL

    try:
        with engine.connect() as conn:
            # Verificar si la tabla logistica existe
            existe = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'logistica'
                )
            """)).scalar()

            if not existe:
                # Tabla nueva: create_all ya la creó con la estructura correcta
                print("[MIGRACIÓN PG] Tabla 'logistica' recién creada por create_all, nada que sincronizar.")
                return

            # Insertar en logistica los usuarios con rol='logistica' que faltan
            result = conn.execute(text("""
                INSERT INTO logistica (id)
                SELECT u.id
                FROM usuario u
                LEFT JOIN logistica l ON l.id = u.id
                WHERE u.rol = 'logistica'
                  AND l.id IS NULL
                ON CONFLICT DO NOTHING
            """))
            conn.commit()
            filas = result.rowcount
            if filas > 0:
                print(f"[MIGRACIÓN PG] {filas} usuario(s) de logística sincronizados a tabla 'logistica'.")
            else:
                print("[MIGRACIÓN PG] Tabla 'logistica' ya estaba sincronizada.")
    except Exception as e:
        print(f"[MIGRACIÓN PG] Error: {e}")


# ─────────────────────────────────────────────
#  EJEMPLO DE USO
# ─────────────────────────────────────────────

def ejemplo_de_uso():
    crear_base_de_datos()
    session = Session()

    # 1. Crear un Admin
    admin = Admin(nombre="Carlos Admin", correo="admin@uni.edu", contrasena="admin123")
    session.add(admin)
    session.commit()

    # 2. Crear un Docente
    docente = Docente(nombre="María López", correo="mlopez@uni.edu",
                      contrasena="pass456", cod_docente="DOC-001", departamento="Ingeniería")
    session.add(docente)
    session.commit()

    # 3. Crear un Espacio
    salon = Espacio(nombre="Salón A-101", capacidad=30)
    session.add(salon)
    session.commit()

    # 4. El docente solicita una reserva
    reserva = docente.solicitar_reserva(
        session,
        cant_personas=20,
        tipo_evento="Clase magistral",
        finalidad="Presentación de proyecto",
        fecha=date(2025, 6, 15),
        hora_inicio=time(8, 0),
        hora_fin=time(10, 0),
    )

    # 5. Asociar el espacio a la reserva
    reserva.espacios.append(salon)
    session.commit()

    # 6. El admin aprueba la reserva
    admin.aprobar_reserva(session, reserva)

    # 7. El docente califica la reserva
    docente.registrar_calificacion(session, reserva,
                                   puntuacion=5, comentario="Excelente espacio")

    # 8. Mostrar resultados
    print(f"\nReserva: {reserva}")
    print(f"Estado:  {reserva.estado}")
    print(f"Espacio: {reserva.espacios[0].nombre}")
    print(f"Calificación: {reserva.calificacion.puntuacion}/5")
    print(f"Disponibilidad salón mañana: "
          f"{salon.consultar_disponibilidad(session, date(2025, 6, 16), time(8,0), time(10,0))}")

    session.close()


# ─────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ─────────────────────────────────────────────

if __name__ == "__main__":
    ejemplo_de_uso()
