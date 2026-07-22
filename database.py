# database.py
import os
import logging
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, text
from dotenv import load_dotenv

# ============================================================
# 1. CARGA DE VARIABLES DE ENTORNO
# ============================================================
load_dotenv()  # Busca .env en la raíz del proyecto

logger = logging.getLogger("fixlog")

# ============================================================
# 2. CONFIGURACIÓN DE CONEXIÓN A SUPABASE
# ============================================================
#
# ⚠️ OPCIONES DE CONEXIÓN EN SUPABASE:
#
#   ❌ Direct (solo IPv6) → Falla en Windows y muchos entornos:
#      postgresql+asyncpg://postgres:PWD@db.xxx.supabase.co:5432/postgres
#
#   ❌ Transaction Pooler (también IPv6) → Mismo problema:
#      postgresql+asyncpg://postgres.xxx:PWD@aws-0-REGION.pooler.supabase.com:6543/postgres
#
#   ✅ Session Pooler (IPv4 — LA ÚNICA QUE FUNCIONA en Windows):
#      postgresql+asyncpg://postgres.xxx:PWD@aws-0-REGION.pooler.supabase.com:5432/postgres
#
# ➡️  Ve a Supabase → Settings → Database → Connection string
#     Copia la URL del "Session pooler" y pégala en la variable de entorno.
#

# Obtener URL desde variable de entorno (obligatorio)
DATABASE_URL = os.getenv("SUPABASE_DB_URL")

if not DATABASE_URL:
    raise ValueError(
        "❌ SUPABASE_DB_URL no está definida en el entorno. "
        "Crea un archivo .env o establece la variable de entorno."
    )

# Configuración del pool (ajustable desde .env)
POOL_SIZE = int(os.getenv("SUPABASE_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("SUPABASE_MAX_OVERFLOW", "20"))
POOL_RECYCLE = int(os.getenv("SUPABASE_POOL_RECYCLE", "3600"))  # segundos
POOL_TIMEOUT = int(os.getenv("SUPABASE_POOL_TIMEOUT", "30"))    # segundos
ECHO_SQL = os.getenv("SUPABASE_ECHO", "false").lower() == "true"

# ============================================================
# 3. CREACIÓN DEL MOTOR ASÍNCRONO
# ============================================================
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=ECHO_SQL,
    pool_pre_ping=True,          # Verifica conexiones antes de usarlas (evita "connection lost")
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,   # Recicla conexiones viejas para evitar timeouts
    pool_timeout=POOL_TIMEOUT,   # Timeout al obtener una conexión del pool
    connect_args={
        "server_settings": {
            "application_name": "fixlog_backend",  # Identifica la app en Supabase logs
        }
    }
)

# ============================================================
# 4. FÁBRICA DE SESIONES
# ============================================================
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,      # Los objetos siguen vivos después del commit
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
)

# ============================================================
# 5. BASE PARA MODELOS (compartida con models.py)
# ============================================================
# Configurar convención de nombres para claves foráneas e índices
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

Base = declarative_base(metadata=MetaData(naming_convention=convention))

# ============================================================
# 6. DEPENDENCIA PARA FASTAPI (get_db)
# ============================================================
async def get_db() -> AsyncSession:
    """
    Dependencia que proporciona una sesión de base de datos para cada endpoint.
    Se encarga de:
        - Abrir la sesión
        - Manejar excepciones y hacer rollback si es necesario
        - Cerrar la sesión al finalizar
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Error en sesión de base de datos: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# ============================================================
# 7. FUNCIÓN PARA PROBAR LA CONEXIÓN (opcional, para debug)
# ============================================================
async def test_connection():
    """
    Función de prueba para verificar que la conexión a Supabase funciona.
    Útil durante el desarrollo.
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            logger.info("✅ Conexión a Supabase establecida correctamente.")
            return True
    except Exception as e:
        logger.error(f"❌ Error al conectar a Supabase: {e}")
        return False

# ============================================================
# 8. CIERRE DEL ENGINE (para graceful shutdown)
# ============================================================
async def close_db_connections():
    """
    Cierra el pool de conexiones de forma ordenada.
    Llamar en el shutdown de la aplicación (FastAPI lifespan).
    """
    await engine.dispose()
    logger.info("✅ Pool de conexiones cerrado correctamente.")