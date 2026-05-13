"""
Sistema de Reservas de Espacios — Sprint 3
Módulo de autenticación + gestión de perfil + frontend por rol
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import crear_base_de_datos, Session as DBSession, Usuario, Admin, Docente, Administrativo, PersonaExterna
from datetime import date

app = Flask(__name__)
app.secret_key = "clave_secreta_reservas_2025"   # Cambia esto en producción

db = DBSession()

# ─── Helpers ───────────────────────────────────────────────────────────────

def usuario_logueado():
    """Retorna el objeto Usuario si hay sesión activa, o None."""
    uid = session.get("usuario_id")
    if uid:
        return db.get(Usuario, uid)
    return None

def requiere_login(f):
    """Decorador: redirige al login si no hay sesión."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not usuario_logueado():
            flash("Debes iniciar sesión primero.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def requiere_admin(f):
    """Decorador: solo permite acceso a admins."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = usuario_logueado()
        if not u or u.rol != "admin":
            flash("No tienes permiso para acceder a esa página.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


# ─── Rutas públicas ────────────────────────────────────────────────────────

@app.route("/")
def index():
    if usuario_logueado():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if usuario_logueado():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        correo     = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "").strip()

        usuario = db.query(Usuario).filter_by(correo=correo).first()
        if usuario and usuario.contrasena == contrasena:
            session["usuario_id"] = usuario.id
            flash(f"Bienvenido, {usuario.nombre}.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Correo o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("login"))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre     = request.form.get("nombre", "").strip()
        correo     = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "").strip()
        rol        = request.form.get("rol", "").strip()

        # Verificar si el correo ya existe
        if db.query(Usuario).filter_by(correo=correo).first():
            flash("Ese correo ya está registrado.", "danger")
            return render_template("registro.html")

        tipos = {
            "docente":        Docente,
            "administrativo": Administrativo,
            "externa":        PersonaExterna,
            "admin":          Admin,
        }
        if rol not in tipos:
            flash("Tipo de usuario inválido.", "danger")
            return render_template("registro.html")

        kwargs = {"nombre": nombre, "correo": correo, "contrasena": contrasena}
        if rol == "docente":
            kwargs["cod_docente"]  = request.form.get("cod_docente", "").strip()
            kwargs["departamento"] = request.form.get("departamento", "").strip()
        elif rol == "administrativo":
            kwargs["dependencia"]  = request.form.get("dependencia", "").strip()
        elif rol == "externa":
            kwargs["empresa"]  = request.form.get("empresa", "").strip()
            kwargs["telefono"] = request.form.get("telefono", "").strip()

        try:
            nuevo = tipos[rol](**kwargs)
            db.add(nuevo)
            db.commit()
            flash("Usuario registrado exitosamente. Inicia sesión.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.rollback()
            flash(f"Error al registrar: {e}", "danger")

    return render_template("registro.html")


# ─── Rutas protegidas ──────────────────────────────────────────────────────

@app.route("/dashboard")
@requiere_login
def dashboard():
    u = usuario_logueado()
    return render_template("dashboard.html", usuario=u)


@app.route("/perfil")
@requiere_login
def perfil():
    u = usuario_logueado()
    return render_template("perfil.html", usuario=u)


@app.route("/perfil/editar", methods=["GET", "POST"])
@requiere_login
def editar_perfil():
    u = usuario_logueado()

    if request.method == "POST":
        u.nombre     = request.form.get("nombre", u.nombre).strip()
        u.contrasena = request.form.get("contrasena", u.contrasena).strip() or u.contrasena

        if u.rol == "docente":
            u.cod_docente  = request.form.get("cod_docente", u.cod_docente).strip()
            u.departamento = request.form.get("departamento", u.departamento).strip()
        elif u.rol == "administrativo":
            u.dependencia = request.form.get("dependencia", u.dependencia).strip()
        elif u.rol == "externa":
            u.empresa  = request.form.get("empresa", u.empresa).strip()
            u.telefono = request.form.get("telefono", u.telefono).strip()

        db.commit()
        flash("Perfil actualizado correctamente.", "success")
        return redirect(url_for("perfil"))

    return render_template("editar_perfil.html", usuario=u)


# ─── Rutas solo Admin ──────────────────────────────────────────────────────

@app.route("/admin/usuarios")
@requiere_login
@requiere_admin
def admin_usuarios():
    u     = usuario_logueado()
    rol   = request.args.get("rol", "")
    query = db.query(Usuario)
    if rol:
        query = query.filter_by(rol=rol)
    usuarios = query.all()
    return render_template("admin_usuarios.html", usuario=u, usuarios=usuarios, filtro_rol=rol)


# ─── Inicio ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    crear_base_de_datos()
    print("✅ Base de datos lista.")
    print("🌐 Abre tu navegador en: http://127.0.0.1:5000")
    app.run(debug=True)
