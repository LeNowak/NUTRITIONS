from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from datetime import time as TimeType
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=120)
    token: str = Field(index=True, unique=True, min_length=8, max_length=8)


class Food(SQLModel, table=True):
    __tablename__ = "foods"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=120)
    aliases: Optional[str] = Field(default=None, max_length=500)
    kcal_per_100g: float = Field(ge=0)
    protein_per_100g: float = Field(ge=0)


class Meal(SQLModel, table=True):
    __tablename__ = "meals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    date: DateType = Field(index=True)
    time: Optional[TimeType] = Field(default=None)
    raw_text: str = Field(max_length=5000)
    total_kcal: float = Field(default=0, ge=0)
    total_protein: float = Field(default=0, ge=0)
    created_at: DateTimeType = Field(default_factory=DateTimeType.utcnow, index=True)

    items: List[MealItem] = Relationship(back_populates="meal")


class MealItem(SQLModel, table=True):
    __tablename__ = "meal_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    meal_id: int = Field(foreign_key="meals.id", index=True)
    food_id: int = Field(foreign_key="foods.id", index=True)
    grams: float = Field(gt=0)
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    matched_name: str = Field(max_length=255)

    meal: Meal = Relationship(back_populates="items")
