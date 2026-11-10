# ⛽ Sistema de Administración y Operaciones de Estación de Servicio (Gasolinera)

API RESTful desarrollada con **Python**, **FastAPI** y **SQLAlchemy** para la administración de operaciones, inventario de hidrocarburos, dispensarios físicos, transacciones y control de acceso basado en roles (RBAC) de una estación de servicio.

---

## 1. Contexto

Proyecto desarrollado para la materia **Desarrollo Web: Tecnologías Servidor**.

### Integrantes del Equipo

| Nombre | Matrícula |
|---|---|
| Alan Emiliano Palomo Plata | 2048459 |
| Leonardo Daniel Vazquez Meza | 1897973 |
| José Emilio Rivera Reyna | 2013503 |
 
 El sistema resuelve la problemática operativa de una gasolinera:
- Control riguroso de inventario en tanques subterráneos (`Magna`, `Premium`, `Diésel`) para evitar desabasto o derrames.
- Administración y auditoría de dispensarios (bombas) físicas por islas con lecturas de odómetros no regresivos.
- Segregación estricta de funciones entre el personal de pista (**Despachador**), los jefes de turno (**Supervisor**) y la gerencia (**Administrador**).
- Ejecución de un proceso transaccional central con garantías **ACID**: cobro, descuento automático de inventario y avance de odómetros en una sola operación atómica.

---

## 2. Resumen Rápido

* **Arquitectura:** Monolítica modular desacoplada (`core`, `db`, `models`, `schemas`, `services`, `api`, `frontend`).
* **Stack Principal:** Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0, PyJWT, Bcrypt y Poetry.
* **Seguridad:** Autenticación mediante **JWT** (tokens firmados con HS256) y autorización basada en roles (**RBAC**).
* **Módulos Clave:**
  1. **Infraestructura:** CRUD y monitoreo de tanques subterráneos y bombas dispensadoras.
  2. **Proceso Central ACID (Despacho):** Valida bomba activa, existencia de combustible, calcula importe, descuenta litros del tanque, avanza odómetro y genera folio único auditado.
  3. **Suministro:** Recepción y descarga de pipas con validación crítica anti-desbordamiento (sobrecupo).
  4. **Corte y Arqueo:** Conciliación de ventas por método de pago (Efectivo, Tarjeta, Vales) y por combustible, con auditoría de odómetros que detecta litros despachados sin venta registrada.
  5. **Ajustes de Inventario:** Mermas y calibraciones con bitácora de auditoría (usuario, motivo, nivel previo y posterior).
  6. **Frontend Integrado:** Terminal de Punto de Venta (POS) con ticket digital y Panel de Monitoreo (Dashboard) de tanques en tiempo real.
* **Pruebas:** Colección de pruebas en Postman, pruebas manuales en Swagger UI y 10 pruebas básicas con `pytest`.

---

## 3. Cómo Ejecutar el Proyecto

### Prerrequisitos
- Python 3.10 o superior instalado.
- Poetry instalado (o Pip).

---

### Paso 1: Configurar variables de entorno
Crea el archivo `.env` a partir de la plantilla:
```bash
cp .env.example .env
```
*(En Windows PowerShell: `Copy-Item .env.example .env`)*

---

### Paso 2: Instalar dependencias

**Con Poetry (Recomendado):**
```bash
poetry install
```

**O con Pip:**
```bash
pip install -r requirements.txt
```

---

### Paso 3: Poblar la base de datos con datos de prueba
Ejecuta el script de siembra para inicializar las tablas, usuarios demo, tanques y bombas:
```bash
python seed_data.py
```
*(Opcional: agrega `--clean` si deseas reiniciar la base de datos desde cero: `python seed_data.py --clean`)*

---

### Paso 4: Iniciar el servidor
```bash
poetry run uvicorn app.main:app --reload --port 8000
```
O directamente con Python:
```bash
uvicorn app.main:app --reload --port 8000
```

---

### Enlaces de Acceso Rápido

Una vez iniciado el servidor en `http://127.0.0.1:8000`:

| Recurso | URL | Descripción |
|---|---|---|
| **Frontend Web (POS & Dashboard)** | [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app) | Terminal del despachador, ticket térmico y monitoreo de tanques en vivo. |
| **Documentación Swagger UI** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | Documentación interactiva de todos los endpoints de la API. |
| **Documentación ReDoc** | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) | Especificación OpenAPI detallada. |
| **Health Check** | [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) | Verificación de estado del servidor. |

---

### Usuarios y Credenciales de Demostración

| Rol | Correo Electrónico | Contraseña | Permisos Principales |
|---|---|---|---|
| **ADMIN** | `admin@gasolinera.com` | `admin123` | Control total del sistema, empleados e infraestructura. |
| **SUPERVISOR** | `supervisor@gasolinera.com` | `supervisor123` | Recepción de pipas, corte de caja y mantenimiento de bombas. |
| **DESPACHADOR** | `despachador@gasolinera.com` | `despachador123` | Despacho y cobro de combustible en terminal POS. |

*(Nota: En el Frontend web `/app` puedes cambiar de usuario con 1 solo clic usando el selector superior).*

---

### Ejecutar Pruebas Automatizadas
Para correr las pruebas básicas (usan una base de datos de prueba aparte):
```bash
poetry run pytest -v
```
Para pruebas con Postman, importa los archivos [`postman_collection.json`](postman_collection.json) y [`postman_environment.json`](postman_environment.json) incluidos en la raíz del proyecto.

---

## 4. Reglas de Negocio Implementadas

| Regla | Respuesta |
|---|---|
| Solo se despacha en bombas `ACTIVA` y habilitadas, conectadas a un tanque activo | 400 |
| No se vende más combustible del disponible en el tanque | 409 |
| Litros, precios y capacidades deben ser mayores a 0 | 422 |
| El nivel de un tanque nunca supera su capacidad (alta, ajustes y pipas) ni queda negativo | 400 / 422 |
| El precio de venta nunca es menor al costo de compra (alta, edición y recepción de pipa) | 400 / 422 |
| El odómetro de una bomba no puede retroceder | 400 |
| Folio de remisión, número de tanque, número de bomba y correo son únicos | 409 |
| No se eliminan tanques/bombas con historial (se desactivan para conservar la trazabilidad) | 409 |
| Un administrador no puede desactivarse ni quitarse el rol a sí mismo | 400 |
| Un usuario desactivado pierde el acceso de inmediato, aunque su token siga vigente | 403 |

## 5. Seguridad

- JWT firmado (HS256) con expiración; el rol se consulta en la BD en cada petición.
- Contraseñas con bcrypt (costo 12); límite de 72 bytes validado; login con tiempo constante (anti-enumeración).
- RBAC por dependencias de FastAPI (`require_role`).
- CORS restringido a orígenes configurados; errores 500 genéricos (el detalle solo va a los logs).
- En `ENVIRONMENT=production` la app no arranca si `SECRET_KEY` es la de ejemplo o tiene menos de 32 caracteres.
- Bloqueo de filas (`SELECT ... FOR UPDATE` en PostgreSQL) en ventas, pipas y ajustes para evitar condiciones de carrera.

## 6. Despliegue (Render)

1. Sube el repositorio a GitHub.
2. En Render: **New → Blueprint** y selecciona el repositorio; `render.yaml` crea la base PostgreSQL y el servicio web.
3. Render genera `SECRET_KEY` automáticamente y conecta `DATABASE_URL`. El health check usa `/health`.
4. Al arrancar se crean las tablas y los datos demo. Abre `https://<tu-servicio>.onrender.com/app`.

También se incluye `Dockerfile` (usuario sin privilegios + healthcheck) para Railway, Fly.io u otros.
