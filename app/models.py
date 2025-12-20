import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from app.db import Base
import enum

class RequestType(enum.Enum):
    WAITLIST = "waitlist"
    INDIVIDUAL = "individual"
    COUPLE = "couple"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    NEGOTIATING = "negotiating"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

class SenderType(enum.Enum):
    ADMIN = "admin"
    CLIENT = "client"

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)  # Telegram ID
    language = Column(String(2), default='ru')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    requests = relationship("Request", back_populates="user")

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    availability_on = Column(Boolean, default=True)
    individual_price = Column(String, default="50 USD / 60 min")
    couple_price = Column(String, default="70 USD / 60 min")

class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_uuid = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, ForeignKey('users.id'))
    
    type = Column(Enum(RequestType))
    onsite = Column(Boolean, nullable=True)
    timezone = Column(String, nullable=True)
    desired_time = Column(String, nullable=True)
    problem = Column(Text, nullable=True)
    address_name = Column(String, nullable=True)
    preferred_comm = Column(String, nullable=True)
    
    status = Column(Enum(RequestStatus), default=RequestStatus.PENDING)
    final_time = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="requests")
    negotiations = relationship("Negotiation", back_populates="request")

class Negotiation(Base):
    __tablename__ = 'negotiations'
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey('requests.id'))
    sender = Column(Enum(SenderType))
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    request = relationship("Request", back_populates="negotiations")