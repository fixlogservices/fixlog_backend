# schemas.py
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID, uuid4
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal

# ============================================================
# 1. SCHEMAS PARA ASSETS
# ============================================================

class AssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., pattern="^(vehicle|home)$")
    brand: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=50)
    identifier: Optional[str] = Field(None, max_length=50, description="Matrícula o nº de serie")
    quick_specs: Dict[str, Any] = Field(default_factory=dict, description="Especificaciones dinámicas")
    last_maintenance_date: Optional[date] = None
    last_maintenance_km: Optional[int] = Field(None, ge=0)

class AssetCreate(AssetBase):
    # El ID se genera automáticamente en el backend si no se envía
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None  # Se asigna desde el token
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class AssetResponse(AssetBase):
    id: UUID
    user_id: UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, pattern="^(vehicle|home)$")
    brand: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=50)
    identifier: Optional[str] = Field(None, max_length=50)
    quick_specs: Optional[Dict[str, Any]] = None
    last_maintenance_date: Optional[date] = None
    last_maintenance_km: Optional[int] = Field(None, ge=0)
    is_deleted: Optional[bool] = None

# ============================================================
# 2. SCHEMAS PARA MAINTENANCE LOGS
# ============================================================

class MaintenanceLogBase(BaseModel):
    asset_id: UUID
    title: str = Field(..., min_length=1, max_length=200)
    cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    current_mileage: Optional[int] = Field(None, ge=0)
    provider_name: Optional[str] = Field(None, max_length=100)
    receipt_image_url: Optional[str] = Field(None, max_length=500, description="URL pública de la factura en Supabase")
    performed_at: date

class MaintenanceLogCreate(MaintenanceLogBase):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class MaintenanceLogResponse(MaintenanceLogBase):
    id: UUID
    user_id: UUID
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MaintenanceLogUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    current_mileage: Optional[int] = Field(None, ge=0)
    provider_name: Optional[str] = Field(None, max_length=100)
    receipt_image_url: Optional[str] = Field(None, max_length=500)
    performed_at: Optional[date] = None
    is_deleted: Optional[bool] = None

# ============================================================
# 3. SCHEMA PARA SINCRONIZACIÓN (EL MÁS IMPORTANTE)
# ============================================================

class SyncPayload(BaseModel):
    """
    Payload que el cliente Flutter envía al endpoint /sync.
    Contiene listas de assets y logs que han sido modificados offline.
    """
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    logs: List[Dict[str, Any]] = Field(default_factory=list)

class SyncResponse(BaseModel):
    """
    Respuesta del endpoint /sync.
    El cliente usa esta información para marcar qué elementos se sincronizaron correctamente
    y cuáles generaron conflictos o errores.
    """
    status: str = Field(..., description="success | partial | conflict | failed")
    synced_asset_ids: List[str] = Field(default_factory=list, description="IDs de assets sincronizados correctamente")
    synced_log_ids: List[str] = Field(default_factory=list, description="IDs de logs sincronizados correctamente")
    conflicts: Optional[Dict[str, str]] = Field(
        None, 
        description="Mapa de ID -> mensaje de conflicto (ej: versiones diferentes)"
    )
    errors: Optional[List[str]] = Field(None, description="Lista de errores generales")
    processed_assets: int = Field(0, description="Número total de assets procesados")
    processed_logs: int = Field(0, description="Número total de logs procesados")

    model_config = ConfigDict(from_attributes=True)

# ============================================================
# 4. SCHEMA PARA SUBIDA DE IMÁGENES
# ============================================================

class UploadResponse(BaseModel):
    """
    Respuesta del endpoint /upload/receipt/{asset_id}
    """
    url: str = Field(..., description="URL pública de la imagen en Supabase Storage")
    path: str = Field(..., description="Ruta interna en el bucket")

    model_config = ConfigDict(from_attributes=True)

# ============================================================
# 5. SCHEMAS DE SALUD Y ERRORES
# ============================================================

class HealthResponse(BaseModel):
    status: str = "OK"
    message: str

class ErrorResponse(BaseModel):
    detail: str
    status_code: int