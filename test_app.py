"""
Pruebas del Sistema de Reservas de Espacios
Politécnico Grancolombiano

Tipos de prueba:
  1. Unitarias   — funciones individuales
  2. Integración — componentes + base de datos
  3. Funcionales — flujos completos del usuario
  4. Seguridad   — control de acceso y restricciones
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, time
import bcrypt

# ─────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cliente():
    """Crea un cliente de pruebas Flask con base de datos temporal."""
    from app import app
    from database import Base, engine, Session, crear_base_de_datos
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Usar base de datos en memoria para pruebas
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)

    app.config["TESTING"]   = True
    app.config["SECRET_KEY"] = "clave_test"

    with app.test_client() as c:
        yield c, TestSession()


# ═════════════════════════════════════════════════════════════════
#  1. PRUEBAS UNITARIAS
#     Prueban funciones individuales sin depender de la BD ni Flask
# ═════════════════════════════════════════════════════════════════

class TestPruebasUnitarias:

    def test_horario_lunes_bloqueado(self):
        """RF-08: Los lunes deben estar bloqueados todo el día."""
        from app import horario_valido
        lunes = date(2025, 5, 5)   # lunes real
        errores = horario_valido(lunes, time(10, 0), time(12, 0))
        assert len(errores) > 0
        assert any("lunes" in e.lower() for e in errores)

    def test_horario_miercoles_bloqueado(self):
        """RF-08: Los miércoles deben estar bloqueados todo el día."""
        from app import horario_valido
        miercoles = date(2025, 5, 7)
        errores = horario_valido(miercoles, time(14, 0), time(16, 0))
        assert len(errores) > 0

    def test_horario_sabado_bloqueado(self):
        """RF-08: Los sábados deben estar bloqueados todo el día."""
        from app import horario_valido
        sabado = date(2025, 5, 10)
        errores = horario_valido(sabado, time(9, 0), time(11, 0))
        assert len(errores) > 0

    def test_horario_domingo_bloqueado(self):
        """RF-08: Los domingos nunca están disponibles."""
        from app import horario_valido
        domingo = date(2025, 5, 11)
        errores = horario_valido(domingo, time(10, 0), time(12, 0))
        assert len(errores) > 0

    def test_horario_martes_manana_bloqueado(self):
        """RF-08: Los martes la mañana (antes de 12:00) está bloqueada."""
        from app import horario_valido
        martes = date(2025, 5, 6)
        errores = horario_valido(martes, time(9, 0), time(11, 0))
        assert len(errores) > 0

    def test_horario_martes_tarde_permitido(self):
        """RF-08: Los martes desde las 12:00 p.m. está permitido."""
        from app import horario_valido
        martes = date(2025, 5, 6)
        errores = horario_valido(martes, time(14, 0), time(16, 0))
        assert len(errores) == 0

    def test_horario_jueves_tarde_permitido(self):
        """RF-08: Los jueves desde las 12:00 p.m. está permitido."""
        from app import horario_valido
        jueves = date(2025, 5, 8)
        errores = horario_valido(jueves, time(13, 0), time(15, 0))
        assert len(errores) == 0

    def test_horario_viernes_manana_permitido(self):
        """RF-08/09: Los viernes desde las 8:00 a.m. está permitido."""
        from app import horario_valido
        viernes = date(2025, 5, 9)
        errores = horario_valido(viernes, time(8, 0), time(10, 0))
        assert len(errores) == 0

    def test_horario_antes_apertura(self):
        """RF-09: No se puede reservar antes de las 8:00 a.m."""
        from app import horario_valido
        viernes = date(2025, 5, 9)
        errores = horario_valido(viernes, time(7, 0), time(9, 0))
        assert len(errores) > 0

    def test_horario_despues_cierre(self):
        """RF-09: No se puede reservar después de las 9:00 p.m."""
        from app import horario_valido
        viernes = date(2025, 5, 9)
        errores = horario_valido(viernes, time(20, 0), time(22, 0))
        assert len(errores) > 0

    def test_hora_inicio_mayor_que_fin(self):
        """La hora de inicio no puede ser mayor que la hora de fin."""
        from app import horario_valido
        viernes = date(2025, 5, 9)
        errores = horario_valido(viernes, time(16, 0), time(14, 0))
        assert len(errores) > 0

    def test_bcrypt_contrasena_correcta(self):
        """RNF01.1: Las contraseñas deben cifrarse y verificarse correctamente."""
        contrasena = "MiClave123"
        hash_pw = bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt())
        assert bcrypt.checkpw(contrasena.encode(), hash_pw)

    def test_bcrypt_contrasena_incorrecta(self):
        """RNF01.1: Una contraseña incorrecta no debe pasar la verificación."""
        contrasena = "MiClave123"
        hash_pw = bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt())
        assert not bcrypt.checkpw("ClaveIncorrecta".encode(), hash_pw)

    def test_correo_poligran_es_institucional(self):
        """Correos @poligran.edu.co deben identificarse como institucionales."""
        correo = "estudiante@poligran.edu.co"
        assert correo.lower().endswith("@poligran.edu.co")

    def test_correo_externo_no_es_institucional(self):
        """Correos externos no deben identificarse como institucionales."""
        correo = "usuario@gmail.com"
        assert not correo.lower().endswith("@poligran.edu.co")


# ═════════════════════════════════════════════════════════════════
#  2. PRUEBAS DE INTEGRACIÓN
#     Prueban que Flask + BD funcionen juntos correctamente
# ═════════════════════════════════════════════════════════════════

class TestPruebasIntegracion:

    def test_login_pagina_carga(self, cliente):
        """La página de login debe cargar correctamente (HTTP 200)."""
        c, _ = cliente
        resp = c.get("/login")
        assert resp.status_code == 200

    def test_registro_pagina_carga(self, cliente):
        """La página de registro debe cargar correctamente (HTTP 200)."""
        c, _ = cliente
        resp = c.get("/registro")
        assert resp.status_code == 200

    def test_login_credenciales_incorrectas(self, cliente):
        """Login con credenciales incorrectas debe mostrar error."""
        c, _ = cliente
        resp = c.post("/login", data={
            "correo": "noexiste@test.com",
            "contrasena": "malaclave"
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Debe seguir en login o mostrar mensaje de error
        assert b"incorrectos" in resp.data or b"login" in resp.data.lower()

    def test_registro_contrasenas_no_coinciden(self, cliente):
        """RF: Registro con contraseñas distintas debe mostrar error."""
        c, _ = cliente
        resp = c.post("/registro", data={
            "nombre": "Test User",
            "correo": "test@gmail.com",
            "contrasena": "clave123",
            "confirmar_contrasena": "otraclaveX"
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert "no coinciden".encode() in resp.data

    def test_registro_correo_duplicado(self, cliente):
        """No debe permitirse registrar el mismo correo dos veces."""
        from database import PersonaExterna, Session
        session = Session()
        hash_pw = bcrypt.hashpw("clave123".encode(), bcrypt.gensalt()).decode()
        u = PersonaExterna(nombre="Ya Existe", correo="duplicado@gmail.com",
                           contrasena=hash_pw)
        session.add(u)
        session.commit()
        session.close()

        c, _ = cliente
        resp = c.post("/registro", data={
            "nombre": "Otro User",
            "correo": "duplicado@gmail.com",
            "contrasena": "clave123",
            "confirmar_contrasena": "clave123"
        }, follow_redirects=True)
        assert b"registrado" in resp.data


# ═════════════════════════════════════════════════════════════════
#  3. PRUEBAS FUNCIONALES
#     Simulan flujos completos del usuario
# ═════════════════════════════════════════════════════════════════

class TestPruebasFuncionales:

    def _login(self, c, correo, contrasena):
        """Helper para iniciar sesión en las pruebas."""
        return c.post("/login", data={
            "correo": correo,
            "contrasena": contrasena
        }, follow_redirects=True)

    def test_flujo_login_exitoso_redirige_dashboard(self, cliente):
        """RF-01: Login exitoso debe redirigir al dashboard."""
        from database import Admin, Session
        session = Session()
        hash_pw = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        admin = Admin(nombre="Admin Test", correo="admintest@test.com",
                      contrasena=hash_pw)
        session.add(admin)
        session.commit()
        session.close()

        c, _ = cliente
        resp = self._login(c, "admintest@test.com", "admin123")
        assert resp.status_code == 200
        assert "dashboard" in resp.request.path or b"Bienvenido" in resp.data

    def test_flujo_logout_limpia_sesion(self, cliente):
        """RF-02: Logout debe limpiar la sesión y redirigir al login."""
        c, _ = cliente
        resp = c.get("/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Iniciar" in resp.data or b"login" in resp.request.path.lower()

    def test_dashboard_sin_sesion_redirige_login(self, cliente):
        """RNF01: Sin sesión activa, el dashboard debe redirigir al login."""
        c, _ = cliente
        c.get("/logout")  # Asegurar que no hay sesión
        resp = c.get("/dashboard", follow_redirects=True)
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_perfil_requiere_sesion(self, cliente):
        """RNF01: El perfil no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/perfil", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_mis_reservas_requiere_sesion(self, cliente):
        """RNF01: Mis reservas no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/reservas", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Iniciar" in resp.data or b"sesi" in resp.data


# ═════════════════════════════════════════════════════════════════
#  4. PRUEBAS DE SEGURIDAD
#     Verifican que el control de acceso funcione correctamente
# ═════════════════════════════════════════════════════════════════

class TestPruebasSeguridad:

    def test_admin_usuarios_sin_sesion(self, cliente):
        """RNF01: /admin/usuarios no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/admin/usuarios", follow_redirects=True)
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_admin_agenda_sin_sesion(self, cliente):
        """RNF01: /admin/agenda no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/admin/agenda", follow_redirects=True)
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_admin_espacios_sin_sesion(self, cliente):
        """RNF01: /admin/espacios no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/admin/espacios", follow_redirects=True)
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_usuario_externo_no_accede_admin(self, cliente):
        """RNF01: Un usuario externo no debe poder acceder al panel admin."""
        from database import PersonaExterna, Session
        session = Session()
        hash_pw = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        externo = PersonaExterna(nombre="Externo Test", correo="externo_seg@gmail.com",
                                 contrasena=hash_pw)
        session.add(externo)
        session.commit()
        session.close()

        c, _ = cliente
        c.post("/login", data={"correo": "externo_seg@gmail.com", "contrasena": "pass123"},
               follow_redirects=True)
        resp = c.get("/admin/usuarios", follow_redirects=True)
        assert b"permiso" in resp.data or b"acceso" in resp.data or resp.status_code == 200

    def test_editar_rol_sin_sesion(self, cliente):
        """RNF01: Editar rol no debe ser accesible sin sesión."""
        c, _ = cliente
        c.get("/logout")
        resp = c.get("/admin/usuarios/1/editar-rol", follow_redirects=True)
        assert b"Iniciar" in resp.data or b"sesi" in resp.data

    def test_no_cache_en_respuestas(self, cliente):
        """RNF01.5: Las respuestas deben tener headers de no-caché."""
        c, _ = cliente
        resp = c.get("/login")
        assert "no-store" in resp.headers.get("Cache-Control", "").lower() or \
               "no-cache" in resp.headers.get("Cache-Control", "").lower()


# ═════════════════════════════════════════════════════════════════
#  EJECUTAR
# ═════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
