from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from pydantic import BaseModel
from typing import List, Optional
import enum
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = "postgresql://user:password@localhost/dbname" # Replace with your PostgreSQL connection details

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define NoteType as an Enum
class NoteType(str, enum.Enum):
    regular = "regular"
    green = "green"

# Database Models
class CanvasSectionDB(Base):
    __tablename__ = "canvas_sections"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(String, unique=True, index=True) # e.g., 'key-partners'
    title = Column(String)
    notes = relationship("NoteDB", back_populates="section")

class NoteDB(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    type = Column(Enum(NoteType), default=NoteType.regular)
    section_id_fk = Column(Integer, ForeignKey("canvas_sections.id"))
    section = relationship("CanvasSectionDB", back_populates="notes")

Base.metadata.create_all(engine) # Create tables if they don't exist

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Models for API requests and responses
class NoteBase(BaseModel):
    content: str
    type: NoteType = NoteType.regular

class NoteCreate(NoteBase):
    pass

class Note(NoteBase):
    id: int
    section_id_fk: int

    class Config:
        orm_mode = True

class CanvasSectionBase(BaseModel):
    section_id: str
    title: str

class CanvasSectionCreate(CanvasSectionBase):
    pass

class CanvasSection(CanvasSectionBase):
    id: int
    notes: List[Note] = []

    class Config:
        orm_mode = True

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; you should restrict this in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize Canvas Sections (Run this only once or when you need to reset sections)
@app.post("/init_sections/", response_model=List[CanvasSection])
def initialize_sections(db: Session = Depends(get_db)):
    default_sections_data = [
        {"section_id": 'key-partners', "title": 'Key Partners'},
        {"section_id": 'key-activities', "title": 'Key Activities'},
        {"section_id": 'key-resources', "title": 'Key Resources'},
        {"section_id": 'value-proposition', "title": 'Value Proposition'},
        {"section_id": 'customer-relationship', "title": 'Customer Relationship'},
        {"section_id": 'channels', "title": 'Channels'},
        {"section_id": 'customer-segments', "title": 'Customer Segments'},
        {"section_id": 'cost-structure', "title": 'Cost Structure'},
        {"section_id": 'revenue-streams', "title": 'Revenue Streams'}
    ]
    sections = []
    for section_data in default_sections_data:
        db_section = CanvasSectionDB(**section_data)
        db.add(db_section)
        db.commit()
        db.refresh(db_section)
        sections.append(CanvasSection.from_orm(db_section))
    return sections


# Get all Canvas Sections with Notes
@app.get("/canvas/", response_model=List[CanvasSection])
def read_canvas(db: Session = Depends(get_db)):
    sections_db = db.query(CanvasSectionDB).all()
    return [CanvasSection.from_orm(section) for section in sections_db]

# Create a Note for a Section
@app.post("/sections/{section_id}/notes/", response_model=Note)
def create_note_for_section(section_id: str, note: NoteCreate, db: Session = Depends(get_db)):
    db_section = db.query(CanvasSectionDB).filter(CanvasSectionDB.section_id == section_id).first()
    if not db_section:
        raise HTTPException(status_code=404, detail="Section not found")
    db_note = NoteDB(**note.dict(), section_id_fk=db_section.id)
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return Note.from_orm(db_note)

# Read a Note
@app.get("/sections/{section_id}/notes/{note_id}", response_model=Note)
def read_note(section_id: str, note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(NoteDB).join(CanvasSectionDB).filter(
        NoteDB.id == note_id, CanvasSectionDB.section_id == section_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    return Note.from_orm(db_note)


# Update a Note
@app.put("/sections/{section_id}/notes/{note_id}", response_model=Note)
def update_note(section_id: str, note_id: int, note_update: NoteCreate, db: Session = Depends(get_db)):
    db_note = db.query(NoteDB).join(CanvasSectionDB).filter(
        NoteDB.id == note_id, CanvasSectionDB.section_id == section_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    for key, value in note_update.dict().items():
        setattr(db_note, key, value)
    db.commit()
    db.refresh(db_note)
    return Note.from_orm(db_note)

# Delete a Note
@app.delete("/sections/{section_id}/notes/{note_id}", response_model=dict)
def delete_note(section_id: str, note_id: int, db: Session = Depends(get_db)):
    db_note = db.query(NoteDB).join(CanvasSectionDB).filter(
        NoteDB.id == note_id, CanvasSectionDB.section_id == section_id
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(db_note)
    db.commit()
    return {"detail": "Note deleted successfully"}
