"""
schemas.py
==========
Pydantic models describing the exact shape of data flowing between modules.

WHY THIS FILE EXISTS (beginner explanation):
LLMs return JSON, but JSON has no guarantees - a field could be missing,
misspelled, or the wrong type. Pydantic models act as a "contract": after
an LLM responds, we validate its output against these models. If something
is missing or malformed, we catch it immediately with a clear error
instead of silently passing broken data down the pipeline (or crashing
later, in a confusing place).

Every module's output model mirrors one "slice" of the final
knowledge_graph.json file. knowledge_graph_builder.py assembles all these
slices together into the KnowledgeGraph model at the end.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ======================================================================
# 1. Document Classification
# ======================================================================
class DocumentClassification(BaseModel):
    subject: str = Field(..., description="e.g. Physics, Computer Science")
    chapter: str = Field(..., description="e.g. Motion, Deep Learning Backpropagation")
    topic: str = Field(..., description="Main topic of the document")
    difficulty_level: str = Field(..., description="Beginner / Intermediate / Advanced")
    educational_domain: str = Field(..., description="e.g. STEM, Humanities, Computer Science")
    learning_objectives: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)


# ======================================================================
# 2. Topics & Concept Relationships
# ======================================================================
class Subtopic(BaseModel):
    name: str
    description: str


class ConceptRelationship(BaseModel):
    from_concept: str
    to_concept: str
    relationship: str = Field(..., description="e.g. 'leads to', 'depends on', 'causes'")


class TopicExtraction(BaseModel):
    main_topics: List[str]
    subtopics: List[Subtopic]
    concept_relationships: List[ConceptRelationship]


# ======================================================================
# 3. Key Concepts, Keywords, Definitions, Misconceptions
# ======================================================================
class Concept(BaseModel):
    name: str
    explanation: str
    difficulty: str = Field(..., description="Easy / Medium / Hard")
    practical_application: str


class Definition(BaseModel):
    term: str
    definition: str
    source_page: Optional[int] = None


class Misconception(BaseModel):
    misconception: str
    clarification: str


class ConceptExtraction(BaseModel):
    key_concepts: List[Concept]
    keywords: List[str]
    definitions: List[Definition]
    misconceptions: List[Misconception]


# ======================================================================
# 4. Summaries & Important Points
# ======================================================================
class ImportantPoints(BaseModel):
    most_important: List[str]
    revision_points: List[str]
    exam_points: List[str]


class SummaryOutput(BaseModel):
    short_summary: str
    detailed_summary: str
    student_friendly_explanation: str
    important_points: ImportantPoints


# ======================================================================
# 5. Teacher Explanations
# ======================================================================
class SimplifiedParagraph(BaseModel):
    page_number: int
    original_text: str
    simple_explanation: str


class TeacherExplanationOutput(BaseModel):
    simplified_paragraphs: List[SimplifiedParagraph]


# ======================================================================
# 6. Learning Flow
# ======================================================================
class LearningFlowStep(BaseModel):
    order: int
    stage: str = Field(..., description="e.g. Introduction, Definition, Example, Diagram, Equation, Application, Quiz")
    description: str


class LearningFlowOutput(BaseModel):
    learning_flow: List[LearningFlowStep]


# ======================================================================
# 7. Equation Understanding
# ======================================================================
class EquationExplanation(BaseModel):
    formula: str
    variables: List[str]
    meaning: str
    units: str
    real_life_explanation: str
    suggested_animation: str
    source_page: Optional[int] = None


class EquationUnderstandingOutput(BaseModel):
    equations: List[EquationExplanation]


# ======================================================================
# 8. Image Understanding
# ======================================================================
class ImageExplanation(BaseModel):
    file: str
    description: str
    educational_purpose: str
    suggested_explanation: str
    source_page: Optional[int] = None


class ImageUnderstandingOutput(BaseModel):
    image_explanations: List[ImageExplanation]


# ======================================================================
# 9. Table Understanding
# ======================================================================
class TableExplanation(BaseModel):
    table_summary: str
    natural_language_explanation: str
    source_page: Optional[int] = None


class TableUnderstandingOutput(BaseModel):
    table_explanations: List[TableExplanation]


# ======================================================================
# 10. Question Generation
# ======================================================================
class MCQ(BaseModel):
    question: str
    options: List[str]
    correct_answer: str


class QuestionSet(BaseModel):
    mcqs: List[MCQ]
    short_answer_questions: List[str]
    long_answer_questions: List[str]
    true_false: List[str]
    fill_in_the_blanks: List[str]


# ======================================================================
# 11. Flashcards
# ======================================================================
class Flashcard(BaseModel):
    question: str
    answer: str


class FlashcardOutput(BaseModel):
    flashcards: List[Flashcard]


# ======================================================================
# 12. Scene Plan / Narration / Timing (for future video generation)
# ======================================================================
class Scene(BaseModel):
    scene_number: int
    title: str
    description: str
    narration: str
    estimated_seconds: int


class SceneOutput(BaseModel):
    scene_plan: List[Scene]


# ======================================================================
# 13. Storyboard / Visual Assets / Voiceover / Video
# ======================================================================
class StoryboardScene(BaseModel):
    scene_number: int
    title: str
    description: str
    narration: str
    estimated_seconds: int
    visual_prompt: str
    asset_hint: str


class StoryboardOutput(BaseModel):
    scene_plan: List[StoryboardScene]


class VisualAsset(BaseModel):
    scene_number: int
    title: str
    file_name: str
    file_path: str
    asset_type: str
    prompt: str


class VisualAssetOutput(BaseModel):
    assets: List[VisualAsset]


class VoiceoverOutput(BaseModel):
    voiceover_file: str
    manifest_file: str
    script: str


class VideoOutput(BaseModel):
    preview_file: str
    manifest_file: str
    manifest: dict


# ======================================================================
# FINAL ASSEMBLED KNOWLEDGE GRAPH
# ======================================================================
class KnowledgeGraph(BaseModel):
    """
    This is the final, complete knowledge_graph.json contract.
    knowledge_graph_builder.py populates this by merging the outputs of
    every other module.
    """
    document_name: str
    subject: str
    chapter: str
    topic: str
    difficulty_level: str
    educational_domain: str
    learning_objectives: List[str]
    prerequisites: List[str]

    summary: SummaryOutput

    topics: TopicExtraction
    concepts: ConceptExtraction

    teacher_explanations: List[SimplifiedParagraph]
    learning_flow: List[LearningFlowStep]

    equations: List[EquationExplanation]
    image_explanations: List[ImageExplanation]
    table_explanations: List[TableExplanation]

    questions: QuestionSet
    flashcards: List[Flashcard]

    scene_plan: List[Scene]
    storyboard: StoryboardOutput
    visual_assets: VisualAssetOutput
    voiceover: VoiceoverOutput
    video: VideoOutput
