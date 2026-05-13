"""
Sistema de Reservas de Espacios
Programa principal con menú interactivo
"""

from database import (
    crear_base_de_datos, Session,
    Admin, Docente, Administrativo, PersonaExterna,
    Espacio, Reserva, AgendaSemestral, Calificacion
)
from datetime import date, time


# ── Helpers ────────────────────────────────────────────────────────────────

def limpiar():
    print("\n" + "─" * 50)

def pausar():
    input("\nPresiona Enter para continuar...")

def pedir_fecha(mensaje):
    while True:
        try:
            texto = input(f"{mensaje} (AAAA-MM-DD): ")
            año, mes, dia = texto.strip().split("-")
            return date(int(año), int(mes), int(dia))
        except:
            print("  ⚠ Formato incorrecto. Usa AAAA-MM-DD, ej: 2025-06-15")

def pedir_hora(mensaje):
    while True:
        try:
            texto = input(f"{mensaje} (HH:MM): ")
            h, m = texto.strip().split(":")
            return time(int(h), int(m))
        except:
            print("  ⚠ Formato incorrecto. Usa HH:MM, ej: 08:00")

def pedir_int(mensaje):
    while True:
        try:
            return int(input(mensaje))
        except:
            print("  ⚠ Ingresa un número entero.")


# ── Sesión global ──────────────────────────────────────────────────────────

session = Session()
usuario_actual = None   # Quién está logueado


# ══════════════════════════════════════════════════════════════════════════
#  MÓDULO: USUARIOS
# ══════════════════════════════════════════════════════════════════════════

def registrar_usuario():
    limpiar()
    print("👤 REGISTRAR NUEVO USUARIO")
    print("Tipos: 1) Docente  2) Administrativo  3) Persona Externa  4) Admin")
    opcion = input("Tipo de usuario: ").strip()

    nombre     = input("Nombre completo: ").strip()
    correo     = input("Correo electrónico: ").strip()
    contrasena = input("Contraseña: ").strip()

    tipos = {"1": Docente, "2": Administrativo, "3": PersonaExterna, "4": Admin}
    if opcion not in tipos:
        print("⚠ Opción inválida.")
        return

    kwargs = {"nombre": nombre, "correo": correo, "contrasena": contrasena}

    if opcion == "1":
        kwargs["cod_docente"]  = input("Código docente: ").strip()
        kwargs["departamento"] = input("Departamento: ").strip()
    elif opcion == "2":
        kwargs["dependencia"] = input("Dependencia: ").strip()
    elif opcion == "3":
        kwargs["empresa"]  = input("Empresa: ").strip()
        kwargs["telefono"] = input("Teléfono: ").strip()

    try:
        nuevo = tipos[opcion](**kwargs)
        session.add(nuevo)
        session.commit()
        print(f"\n✅ Usuario '{nombre}' registrado exitosamente.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")

    pausar()


def iniciar_sesion():
    global usuario_actual
    limpiar()
    print("🔐 INICIAR SESIÓN")
    correo     = input("Correo: ").strip()
    contrasena = input("Contraseña: ").strip()

    from database import Usuario
    usuario = session.query(Usuario).filter_by(correo=correo).first()

    if usuario and usuario.contrasena == contrasena:
        usuario_actual = usuario
        print(f"\n✅ Bienvenido, {usuario.nombre} ({usuario.rol})")
    else:
        print("❌ Correo o contraseña incorrectos.")
    pausar()


def ver_perfil():
    limpiar()
    print("👤 MI PERFIL")
    u = usuario_actual
    print(f"  ID        : {u.id}")
    print(f"  Nombre    : {u.nombre}")
    print(f"  Correo    : {u.correo}")
    print(f"  Rol       : {u.rol}")
    if u.rol == "docente":
        print(f"  Código    : {u.cod_docente}")
        print(f"  Depto.    : {u.departamento}")
    elif u.rol == "administrativo":
        print(f"  Dependencia: {u.dependencia}")
    elif u.rol == "externa":
        print(f"  Empresa   : {u.empresa}")
        print(f"  Teléfono  : {u.telefono}")
    pausar()


# ══════════════════════════════════════════════════════════════════════════
#  MÓDULO: ESPACIOS
# ══════════════════════════════════════════════════════════════════════════

def registrar_espacio():
    limpiar()
    print("🏫 REGISTRAR ESPACIO")
    nombre    = input("Nombre del espacio (ej: Salón A-101): ").strip()
    capacidad = pedir_int("Capacidad (personas): ")

    espacio = Espacio(nombre=nombre, capacidad=capacidad)
    session.add(espacio)
    session.commit()
    print(f"\n✅ Espacio '{nombre}' registrado con capacidad {capacidad}.")
    pausar()


def listar_espacios():
    limpiar()
    print("🏫 ESPACIOS DISPONIBLES")
    espacios = session.query(Espacio).all()
    if not espacios:
        print("  (No hay espacios registrados)")
    for e in espacios:
        print(f"  [{e.id}] {e.nombre} — Capacidad: {e.capacidad} personas")
    pausar()


# ══════════════════════════════════════════════════════════════════════════
#  MÓDULO: RESERVAS
# ══════════════════════════════════════════════════════════════════════════

def solicitar_reserva():
    limpiar()
    print("📋 SOLICITAR RESERVA")

    # Mostrar espacios disponibles
    espacios = session.query(Espacio).all()
    if not espacios:
        print("⚠ No hay espacios registrados. Pídele a un Admin que los agregue.")
        pausar()
        return

    print("\nEspacios disponibles:")
    for e in espacios:
        print(f"  [{e.id}] {e.nombre} (cap. {e.capacidad})")

    espacio_id = pedir_int("\nID del espacio que deseas reservar: ")
    espacio = session.get(Espacio, espacio_id)
    if not espacio:
        print("❌ Espacio no encontrado.")
        pausar()
        return

    tipo_evento  = input("Tipo de evento: ").strip()
    finalidad    = input("Finalidad: ").strip()
    indumentaria = input("Indumentaria requerida (o deja vacío): ").strip()
    cant_personas = pedir_int("Cantidad de personas: ")
    fecha        = pedir_fecha("Fecha del evento")
    hora_inicio  = pedir_hora("Hora de inicio")
    hora_fin     = pedir_hora("Hora de fin")

    # Verificar disponibilidad
    if not espacio.consultar_disponibilidad(session, fecha, hora_inicio, hora_fin):
        print("❌ El espacio NO está disponible en ese horario.")
        pausar()
        return

    reserva = Reserva(
        usuario_id=usuario_actual.id,
        cant_personas=cant_personas,
        tipo_evento=tipo_evento,
        finalidad=finalidad,
        indumentaria=indumentaria if indumentaria else None,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        estado="pendiente",
    )
    reserva.espacios.append(espacio)
    session.add(reserva)
    session.commit()

    print(f"\n✅ Reserva enviada (ID: {reserva.id}). Estado: pendiente — esperando aprobación del Admin.")
    pausar()


def mis_reservas():
    limpiar()
    print("📋 MIS RESERVAS")
    reservas = session.query(Reserva).filter_by(usuario_id=usuario_actual.id).all()
    if not reservas:
        print("  (No tienes reservas aún)")
    for r in reservas:
        espacios_nombres = ", ".join(e.nombre for e in r.espacios)
        print(f"\n  [{r.id}] {r.tipo_evento}")
        print(f"       Fecha   : {r.fecha}  {r.hora_inicio} - {r.hora_fin}")
        print(f"       Espacio : {espacios_nombres}")
        print(f"       Estado  : {r.estado}")
    pausar()


def calificar_reserva():
    limpiar()
    print("⭐ CALIFICAR RESERVA")
    mis_reservas_aprobadas = (
        session.query(Reserva)
        .filter_by(usuario_id=usuario_actual.id, estado="aprobada")
        .all()
    )
    sin_calificar = [r for r in mis_reservas_aprobadas if r.calificacion is None]

    if not sin_calificar:
        print("  (No tienes reservas aprobadas sin calificar)")
        pausar()
        return

    for r in sin_calificar:
        print(f"  [{r.id}] {r.tipo_evento} — {r.fecha}")

    reserva_id = pedir_int("\nID de la reserva a calificar: ")
    reserva = next((r for r in sin_calificar if r.id == reserva_id), None)
    if not reserva:
        print("❌ Reserva no encontrada o ya calificada.")
        pausar()
        return

    puntuacion = pedir_int("Puntuación (1 a 5): ")
    comentario = input("Comentario (opcional): ").strip()

    cal = Calificacion(
        reserva_id=reserva.id,
        puntuacion=puntuacion,
        comentario=comentario if comentario else None,
        fecha=date.today()
    )
    session.add(cal)
    session.commit()
    print("✅ Calificación registrada.")
    pausar()


# ══════════════════════════════════════════════════════════════════════════
#  MÓDULO: ADMIN
# ══════════════════════════════════════════════════════════════════════════

def admin_gestionar_reservas():
    limpiar()
    print("🛠  GESTIÓN DE RESERVAS (Admin)")
    pendientes = session.query(Reserva).filter_by(estado="pendiente").all()
    if not pendientes:
        print("  (No hay reservas pendientes)")
        pausar()
        return

    for r in pendientes:
        espacios_nombres = ", ".join(e.nombre for e in r.espacios)
        print(f"\n  [{r.id}] {r.tipo_evento}")
        print(f"       Solicitante: Usuario ID {r.usuario_id}")
        print(f"       Fecha      : {r.fecha}  {r.hora_inicio} - {r.hora_fin}")
        print(f"       Espacio    : {espacios_nombres}")
        print(f"       Personas   : {r.cant_personas}")

    reserva_id = pedir_int("\nID de la reserva a gestionar (0 para cancelar): ")
    if reserva_id == 0:
        return

    reserva = session.get(Reserva, reserva_id)
    if not reserva or reserva.estado != "pendiente":
        print("❌ Reserva no encontrada o ya procesada.")
        pausar()
        return

    accion = input("¿Aprobar o rechazar? (a/r): ").strip().lower()
    if accion == "a":
        reserva.estado = "aprobada"
        session.commit()
        print("✅ Reserva aprobada.")
    elif accion == "r":
        reserva.estado = "rechazada"
        session.commit()
        print("✅ Reserva rechazada.")
    else:
        print("⚠ Acción no reconocida.")
    pausar()


def admin_ver_todos_usuarios():
    limpiar()
    print("👥 TODOS LOS USUARIOS")
    from database import Usuario
    usuarios = session.query(Usuario).all()
    for u in usuarios:
        print(f"  [{u.id}] {u.nombre} — {u.correo} ({u.rol})")
    pausar()


def admin_exportar_csv():
    limpiar()
    print("📊 EXPORTAR RESERVAS A CSV")
    nombre = input("Nombre del archivo (ej: reporte.csv): ").strip()
    if not nombre.endswith(".csv"):
        nombre += ".csv"
    usuario_actual.exportar_csv(session, nombre)
    print(f"✅ Archivo guardado como '{nombre}'")
    pausar()


# ══════════════════════════════════════════════════════════════════════════
#  MENÚS
# ══════════════════════════════════════════════════════════════════════════

def menu_admin():
    while True:
        limpiar()
        print(f"  ✦ Menú Admin — {usuario_actual.nombre}")
        print("  1. Ver todas las reservas pendientes")
        print("  2. Ver todos los usuarios")
        print("  3. Registrar espacio")
        print("  4. Listar espacios")
        print("  5. Exportar reservas a CSV")
        print("  6. Ver mi perfil")
        print("  0. Cerrar sesión")
        opcion = input("\nOpción: ").strip()

        if   opcion == "1": admin_gestionar_reservas()
        elif opcion == "2": admin_ver_todos_usuarios()
        elif opcion == "3": registrar_espacio()
        elif opcion == "4": listar_espacios()
        elif opcion == "5": admin_exportar_csv()
        elif opcion == "6": ver_perfil()
        elif opcion == "0": break


def menu_usuario():
    while True:
        limpiar()
        print(f"  ✦ Menú Usuario — {usuario_actual.nombre}")
        print("  1. Solicitar reserva")
        print("  2. Ver mis reservas")
        print("  3. Calificar reserva")
        print("  4. Ver espacios disponibles")
        print("  5. Ver mi perfil")
        print("  0. Cerrar sesión")
        opcion = input("\nOpción: ").strip()

        if   opcion == "1": solicitar_reserva()
        elif opcion == "2": mis_reservas()
        elif opcion == "3": calificar_reserva()
        elif opcion == "4": listar_espacios()
        elif opcion == "5": ver_perfil()
        elif opcion == "0": break


def menu_principal():
    global usuario_actual
    while True:
        limpiar()
        print("═" * 50)
        print("   🏛  SISTEMA DE RESERVAS DE ESPACIOS")
        print("═" * 50)
        print("  1. Iniciar sesión")
        print("  2. Registrar nuevo usuario")
        print("  0. Salir")
        opcion = input("\nOpción: ").strip()

        if opcion == "1":
            iniciar_sesion()
            if usuario_actual:
                if usuario_actual.rol == "admin":
                    menu_admin()
                else:
                    menu_usuario()
                usuario_actual = None  # reset al cerrar sesión

        elif opcion == "2":
            registrar_usuario()

        elif opcion == "0":
            print("\n👋 ¡Hasta pronto!\n")
            break


# ══════════════════════════════════════════════════════════════════════════
#  INICIO
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    crear_base_de_datos()   # Crea reservas.db si no existe
    menu_principal()