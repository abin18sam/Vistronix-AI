from pydantic import BaseModel, Field, model_validator


class Chunk(BaseModel):
    chunk_id: str
    page_numbers: list[int]
    text: str = Field(min_length=1)
    heading: str | None = None


class SummaryResult(BaseModel):
    summary: str
    key_points: list[str] = Field(default_factory=list)


class Entity(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    description: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class EntitiesResult(BaseModel):
    entities: list[Entity]


class Claim(BaseModel):
    claim_id: str
    text: str
    source_chunk_ids: list[str] = Field(default_factory=list)


class ClaimsResult(BaseModel):
    claims: list[Claim]


class Relationship(BaseModel):
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship: str
    source_chunk_ids: list[str] = Field(default_factory=list)


class RelationshipsResult(BaseModel):
    relationships: list[Relationship]


class LearningObjectivesResult(BaseModel):
    prerequisites: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)


class KnowledgeGraph(BaseModel):
    document_id: str
    summary: SummaryResult
    entities: list[Entity]
    claims: list[Claim]
    relationships: list[Relationship]
    prerequisites: list[str]
    learning_objectives: list[str]

    @model_validator(mode="after")
    def validate_relationship_targets(self):
        entity_ids = {entity.entity_id for entity in self.entities}
        if len(entity_ids) != len(self.entities):
            raise ValueError("Entity IDs must be unique")
        invalid = [
            relationship.relationship_id
            for relationship in self.relationships
            if relationship.source_entity_id not in entity_ids
            or relationship.target_entity_id not in entity_ids
        ]
        if invalid:
            raise ValueError(f"Relationships reference missing entities: {invalid}")
        return self
