"""Repository générique pour centraliser les opérations CRUD courantes."""
from typing import Generic, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    def __init__(self, model: type[ModelT], db: Session):
        self.model, self.db = model, db

    def list(self, offset: int = 0, limit: int = 100) -> list[ModelT]:
        return list(self.db.scalars(select(self.model).offset(offset).limit(min(limit, 500))))

    def get(self, entity_id: int) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def create(self, values: dict) -> ModelT:
        entity = self.model(**values)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelT, values: dict) -> ModelT:
        for key, value in values.items():
            setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.commit()

