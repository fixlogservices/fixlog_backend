# models.py
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Numeric, Date, 
    ForeignKey, Index, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from uuid import UUID, uuid4
from decimal import Decimal
from typing import Optional, List, Dict, Any

from database import Base

# ============================================================
# 1. MODELO ASSET
# ============================================================

class Asset(Base):
    __tablename__ = "assets"

    # ---------- ID ----------
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    
    # ---------- Relación con usuario ----------
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # ---------- Datos principales ----------
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'vehicle' o 'home'
    brand: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    identifier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    # ---------- Especificaciones dinámicas (JSONB) ----------
    quick_specs: Mapped[Dict[str, Any]] = mapped_column(
        JSON(none_as_null=True),
        nullable=False,
        default=dict,
        server_default='{}',
    )
    
    # ---------- Último mantenimiento ----------
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_maintenance_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # ---------- Soft delete y timestamps ----------
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ---------- Relaciones ----------
    # Relación inversa con MaintenanceLog
    maintenance_logs: Mapped[List["MaintenanceLog"]] = relationship(
        "MaintenanceLog",
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MaintenanceLog.performed_at.desc()",
    )

    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        Index("idx_assets_user_deleted", "user_id", "is_deleted"),
        Index("idx_assets_user_category", "user_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, name={self.name}, category={self.category})>"


# ============================================================
# 2. MODELO MAINTENANCE LOG
# ============================================================

class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    # ---------- ID ----------
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    
    # ---------- Relación con usuario y asset ----------
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ---------- Datos del mantenimiento ----------
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    current_mileage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    receipt_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # ---------- Fecha del mantenimiento ----------
    performed_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # ---------- Soft delete y timestamps ----------
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ---------- Relaciones ----------
    # Relación con Asset (muchos a uno)
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="maintenance_logs",
        foreign_keys=[asset_id],
    )

    # Índices compuestos para consultas frecuentes
    __table_args__ = (
        Index("idx_logs_asset_deleted", "asset_id", "is_deleted"),
        Index("idx_logs_user_performed", "user_id", "performed_at"),
        Index("idx_logs_asset_performed", "asset_id", "performed_at"),
    )

    def __repr__(self) -> str:
        return f"<MaintenanceLog(id={self.id}, asset_id={self.asset_id}, title={self.title})>"