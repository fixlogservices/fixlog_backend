# FixLog Backend 🚀

Backend construido con **FastAPI** para la aplicación FixLog. Diseñado con una arquitectura **offline-first**, permite la sincronización masiva de datos y el almacenamiento de comprobantes de mantenimiento.

## 🛠️ Stack Tecnológico

- **Framework:** FastAPI (Asíncrono)
- **Base de Datos:** PostgreSQL (vía Supabase)
- **ORM:** SQLAlchemy 2.0 (Async)
- **Validación:** Pydantic v2
- **Storage:** Supabase Storage (para imágenes)
- **Despliegue:** Render

## 🚀 Configuración Local

1. **Clonar el repositorio:**
   ```bash
   git clone <url-del-repo>
   cd fixlog_backend
   ```

2. **Crear entorno virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   - Copia `.env.example` a `.env`
   - Rellena las variables con tus credenciales de Supabase.

5. **Ejecutar servidor:**
   ```bash
   uvicorn main:app --reload
   ```

## ☁️ Despliegue en Render

Este proyecto está listo para desplegarse en [Render](https://render.com).

1. Conecta tu repositorio de GitHub a Render.
2. Crea un nuevo **Web Service**.
3. Render detectará automáticamente el `render.yaml` y configurará el servicio.
4. **IMPORTANTE**: Configura las variables de entorno en el dashboard de Render (`SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_KEY`).

## 📁 Estructura del Proyecto

- `main.py`: Punto de entrada y definición de endpoints.
- `models.py`: Modelos de la base de datos (SQLAlchemy).
- `schemas.py`: Modelos de validación (Pydantic).
- `database.py`: Configuración de la conexión asíncrona.
- `requirements.txt`: Lista de dependencias.
- `Procfile`: Comando de ejecución para producción.
