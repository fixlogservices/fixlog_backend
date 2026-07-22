from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
import logging
import os
import json

from database import engine, get_db, Base
from models import Asset, MaintenanceLog
from schemas import (
    AssetCreate, AssetResponse,
    MaintenanceLogCreate, MaintenanceLogResponse,
    SyncPayload, SyncResponse
)

# --- Configuración de Supabase Storage (para imágenes) ---
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "❌ SUPABASE_URL o SUPABASE_KEY no están definidas en el entorno. "
        "Asegúrate de configurarlas en Render o en tu archivo .env"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logger = logging.getLogger("fixlog")

# ============================================================
# LIFESPAN (creación de tablas al inicio)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Tablas verificadas/creadas en Supabase.")
    except Exception as e:
        logger.warning(f"⚠️  No se pudo conectar a la BD en el arranque: {e}")
    yield
    # Shutdown
    await engine.dispose()

# ============================================================
# INICIALIZAR APP
# ============================================================
app = FastAPI(
    title="FixLog API",
    description="Backend Offline-First para mantenimiento de vehículos y hogar",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================
# ENDPOINTS DE ASSETS
# ============================================================
@app.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo activo (coche o casa)."""
    user_id = uuid4()  # 🔥 Reemplazar con autenticación real
    new_asset = Asset(**asset.model_dump(), user_id=user_id)
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)
    return new_asset

@app.get("/assets", response_model=List[AssetResponse])
async def list_assets(db: AsyncSession = Depends(get_db)):
    """Lista todos los activos del usuario (sin los eliminados)."""
    user_id = uuid4()  # 🔥 Reemplazar con autenticación real
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.is_deleted == False)
    )
    return result.scalars().all()

@app.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Obtiene un activo específico por ID."""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.is_deleted == False)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return asset

# ============================================================
# ENDPOINTS DE MANTENIMIENTO
# ============================================================
@app.post("/maintenance", response_model=MaintenanceLogResponse, status_code=status.HTTP_201_CREATED)
async def create_maintenance(log: MaintenanceLogCreate, db: AsyncSession = Depends(get_db)):
    """Registra un mantenimiento (con foto de factura opcional)."""
    user_id = uuid4()  # 🔥 Reemplazar con autenticación real
    new_log = MaintenanceLog(**log.model_dump(), user_id=user_id)
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)

    # Actualizar último mantenimiento en el Asset
    await db.execute(
        update(Asset)
        .where(Asset.id == log.asset_id)
        .values(
            last_maintenance_date=log.performed_at,
            last_maintenance_km=log.current_mileage
        )
    )
    await db.commit()

    return new_log

@app.get("/assets/{asset_id}/maintenance", response_model=List[MaintenanceLogResponse])
async def get_maintenance_history(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Obtiene el historial completo de mantenimientos de un activo."""
    result = await db.execute(
        select(MaintenanceLog)
        .where(MaintenanceLog.asset_id == asset_id, MaintenanceLog.is_deleted == False)
        .order_by(MaintenanceLog.performed_at.desc())
    )
    return result.scalars().all()

# ============================================================
# 🔥 ENDPOINT DE SINCRONIZACIÓN (El más importante)
# ============================================================
@app.post("/sync", response_model=SyncResponse)
async def sync_data(payload: SyncPayload, db: AsyncSession = Depends(get_db)):
    """
    Recibe todos los datos creados/modificados OFFLINE.
    Hace UPSERT (inserta o actualiza) de manera masiva.
    Devuelve listas de IDs sincronizados y conflictos si los hay.
    """
    user_id = uuid4()  # 🔥 Reemplazar con autenticación real
    synced_asset_ids = []
    synced_log_ids = []
    errors = []
    conflicts = {}

    # ============================================================
    # 1. Sincronizar Assets (UPSERT)
    # ============================================================
    for asset_data in payload.assets:
        try:
            # Convertir datos al formato de la BD (incluir user_id)
            asset_data['user_id'] = str(user_id)
            asset_data['updated_at'] = datetime.now(timezone.utc)

            # Verificar si el asset ya existe y si hubo cambios en el servidor
            # (aquí podrías implementar detección de conflictos por updated_at)
            # Por simplicidad, el cliente siempre gana.

            stmt = insert(Asset).values(**asset_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'name': stmt.excluded.name,
                    'category': stmt.excluded.category,
                    'brand': stmt.excluded.brand,
                    'model': stmt.excluded.model,
                    'identifier': stmt.excluded.identifier,
                    'quick_specs': stmt.excluded.quick_specs,
                    'last_maintenance_date': stmt.excluded.last_maintenance_date,
                    'last_maintenance_km': stmt.excluded.last_maintenance_km,
                    'is_deleted': stmt.excluded.is_deleted,
                    'updated_at': stmt.excluded.updated_at,
                    'user_id': stmt.excluded.user_id
                }
            )
            await db.execute(stmt)
            synced_asset_ids.append(str(asset_data['id']))

        except Exception as e:
            error_msg = f"Asset {asset_data.get('id')}: {str(e)}"
            errors.append(error_msg)
            # Si es un conflicto de integridad, lo clasificamos como conflicto
            if "duplicate" in str(e).lower() or "conflict" in str(e).lower():
                conflicts[str(asset_data.get('id'))] = "Conflicto de integridad en el servidor"

    # ============================================================
    # 2. Sincronizar Maintenance Logs
    # ============================================================
    for log_data in payload.logs:
        try:
            log_data['user_id'] = str(user_id)
            log_data['updated_at'] = datetime.now(timezone.utc)

            # Verificar que el asset padre existe (opcional)
            # Si no existe, podríamos crear un conflicto
            stmt = insert(MaintenanceLog).values(**log_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'title': stmt.excluded.title,
                    'cost': stmt.excluded.cost,
                    'current_mileage': stmt.excluded.current_mileage,
                    'provider_name': stmt.excluded.provider_name,
                    'receipt_image_url': stmt.excluded.receipt_image_url,
                    'performed_at': stmt.excluded.performed_at,
                    'is_deleted': stmt.excluded.is_deleted,
                    'updated_at': stmt.excluded.updated_at,
                    'user_id': stmt.excluded.user_id
                }
            )
            await db.execute(stmt)
            synced_log_ids.append(str(log_data['id']))

        except Exception as e:
            error_msg = f"Log {log_data.get('id')}: {str(e)}"
            errors.append(error_msg)
            if "duplicate" in str(e).lower() or "conflict" in str(e).lower():
                conflicts[str(log_data.get('id'))] = "Conflicto de integridad en el servidor"

    # ============================================================
    # 3. Commit final
    # ============================================================
    await db.commit()

    # ============================================================
    # 4. Determinar estado de la respuesta
    # ============================================================
    if errors and not synced_asset_ids and not synced_log_ids:
        status = "failed"
    elif errors:
        status = "partial"
    else:
        status = "success"

    # ============================================================
    # 5. Devolver respuesta estructurada para el cliente
    # ============================================================
    return SyncResponse(
        status=status,
        synced_asset_ids=synced_asset_ids,
        synced_log_ids=synced_log_ids,
        conflicts=conflicts if conflicts else None,
        errors=errors if errors else None,
        processed_assets=len(synced_asset_ids),
        processed_logs=len(synced_log_ids),
    )

# ============================================================
# 🖼️ SUBIDA DE IMÁGENES A SUPABASE STORAGE
# ============================================================
@app.post("/upload/receipt/{asset_id}")
async def upload_receipt(
    asset_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Sube la foto de una factura a Supabase Storage y devuelve la URL pública.
    """
    try:
        # 1. Generar nombre único
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        file_path = f"receipts/{asset_id}/{timestamp}.{file_ext}"

        # 2. Leer contenido del archivo
        content = await file.read()

        # 3. Subir a Supabase Storage (bucket "fixlog")
        # Asegúrate de que el bucket existe y tiene políticas públicas
        supabase.storage.from_("fixlog").upload(file_path, content)

        # 4. Obtener URL pública (válida para siempre)
        public_url = supabase.storage.from_("fixlog").get_public_url(file_path)

        # 5. (Opcional) Guardar la URL en la BD para el log correspondiente
        # Podrías actualizar el campo receipt_image_url del MaintenanceLog
        # await db.execute(
        #     update(MaintenanceLog)
        #     .where(MaintenanceLog.asset_id == asset_id)
        #     .where(MaintenanceLog.created_at == ...) # necesitas identificar el log
        #     .values(receipt_image_url=public_url)
        # )
        # await db.commit()

        return {"url": public_url, "path": file_path}

    except Exception as e:
        logger.error(f"Error subiendo imagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# ENDPOINT DE SALUD
# ============================================================
@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "FixLog API funcionando con presupuesto cero 🚀"}