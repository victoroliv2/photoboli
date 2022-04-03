from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy import func

Base = declarative_base()

class Photo(Base):
    __tablename__ = 'photo'
    hash_     = Column(String(64), primary_key=True)
    path      = Column(String(250), nullable=False)
    date      = Column(DateTime, nullable=True)
    latitude  = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    city      = Column(String(250), nullable=True)
    region1   = Column(String(250), nullable=True)
    region2   = Column(String(250), nullable=True)

    @hybrid_method
    def intersects(self, other):
        if self.latitude and self.longitude and other.latitude and other.longitude:
            vx = func.abs(self.latitude - other.latitude) < 20 
            vy = func.abs(self.longitude - other.longitude) < 20
            return vx & vy
        else:
            return false

class PhotoExtra(Base):
    __tablename__ = 'photoextra'
    photo_id  = Column(String(64), ForeignKey('photo.hash_'), primary_key=True)
    cat = Column(Float, nullable=True)

class Face(Base):
    __tablename__ = 'face'
    id = Column(Integer, primary_key=True)
    photo_id  = Column(String(64), ForeignKey('photo.hash_'), primary_key=True)
    person_id  = Column(Integer, ForeignKey('person.id'), nullable=True)
    x0  = Column(Float)
    y0  = Column(Float)
    x1  = Column(Float)
    y1  = Column(Float)
    encoding = Column(String(1386))

class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=True)
