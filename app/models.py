from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    characters = relationship("Character", back_populates="owner")

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    master_id = Column(Integer, ForeignKey("users.id"))
    master = relationship("User")

class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    name = Column(String, default="")
    age = Column(Integer, default=30)
    occupation = Column(String, default="")
    birthplace = Column(String, default="")
    avatar_url = Column(String, default="")

    str_val = Column(Integer, default=50)
    con_val = Column(Integer, default=50)
    pow_val = Column(Integer, default=50)
    dex_val = Column(Integer, default=50)
    app_val = Column(Integer, default=50)
    siz_val = Column(Integer, default=50)
    int_val = Column(Integer, default=50)
    edu_val = Column(Integer, default=50)

    hp_current = Column(Integer, default=10)
    sanity_current = Column(Integer, default=50)
    mp_current = Column(Integer, default=10)
    luck = Column(Integer, default=50)

    skills_json = Column(Text, default="{}")

    ideology = Column(String, default="")
    significant_people = Column(String, default="")
    meaningful_locations = Column(String, default="")
    treasured_possessions = Column(String, default="")
    traits = Column(String, default="")
    phobias = Column(String, default="")
    mythos = Column(String, default="")

    owner = relationship("User", back_populates="characters")