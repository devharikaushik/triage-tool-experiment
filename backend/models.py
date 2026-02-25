from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Centre(Base):
    __tablename__ = "centres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="Default Centre")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    infrastructure = relationship("Infrastructure", back_populates="centre", uselist=False)
    diagnostics = relationship("Diagnostics", back_populates="centre", uselist=False)
    competencies = relationship("Competencies", back_populates="centre", uselist=False)
    medications = relationship(
        "Medication",
        back_populates="centre",
        cascade="all, delete-orphan",
    )


class Infrastructure(Base):
    __tablename__ = "infrastructure"

    centre_id = Column(Integer, ForeignKey("centres.id"), primary_key=True)
    oxygen = Column(Boolean, default=False, nullable=False)
    suction = Column(Boolean, default=False, nullable=False)
    iv_fluids = Column(Boolean, default=False, nullable=False)
    nebulizer = Column(Boolean, default=False, nullable=False)
    power_backup = Column(Boolean, default=False, nullable=False)

    centre = relationship("Centre", back_populates="infrastructure")


class Diagnostics(Base):
    __tablename__ = "diagnostics"

    centre_id = Column(Integer, ForeignKey("centres.id"), primary_key=True)
    blood_glucose = Column(Boolean, default=False, nullable=False)
    hemoglobin = Column(Boolean, default=False, nullable=False)
    urine_test = Column(Boolean, default=False, nullable=False)
    malaria_test = Column(Boolean, default=False, nullable=False)
    ecg = Column(Boolean, default=False, nullable=False)
    xray = Column(Boolean, default=False, nullable=False)
    ultrasound = Column(Boolean, default=False, nullable=False)

    centre = relationship("Centre", back_populates="diagnostics")


class Competencies(Base):
    __tablename__ = "competencies"

    centre_id = Column(Integer, ForeignKey("centres.id"), primary_key=True)
    start_iv = Column(Boolean, default=False, nullable=False)
    give_im = Column(Boolean, default=False, nullable=False)
    manage_airway = Column(Boolean, default=False, nullable=False)
    intubate = Column(Boolean, default=False, nullable=False)
    manage_shock = Column(Boolean, default=False, nullable=False)
    monitor_vitals = Column(Boolean, default=False, nullable=False)

    centre = relationship("Centre", back_populates="competencies")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id"), nullable=False)
    drug_name = Column(String, nullable=False)
    in_stock = Column(Boolean, default=False, nullable=False)

    centre = relationship("Centre", back_populates="medications")
