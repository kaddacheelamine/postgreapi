from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rushita_user:xHFJdbYFuaPeiiEsPQ4Yc8JafIHaaagq@dpg-cv4ra4qj1k6c738qjsmg-a/rushita")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database models
class CanvasModel(Base):
    __tablename__ = "canvases"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(String)  # ISO format date string
    updated_at = Column(String)  # ISO format date string
    sections = relationship("SectionModel", back_populates="canvas", cascade="all, delete")

class SectionModel(Base):
    __tablename__ = "sections"
    
    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(String, index=True)  # Original section ID from frontend (e.g., 'key-partners')
    title = Column(String)
    canvas_id = Column(Integer, ForeignKey("canvases.id"))
    canvas = relationship("CanvasModel", back_populates="sections")
    notes = relationship("NoteModel", back_populates="section", cascade="all, delete")

class NoteModel(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(String, index=True)  # Original note ID from frontend
    content = Column(Text)
    type = Column(String)  # 'regular' or 'green'
    section_id = Column(Integer, ForeignKey("sections.id"))
    section = relationship("SectionModel", back_populates="notes")

# Create the tables
Base.metadata.create_all(bind=engine)

# Pydantic models for request/response
class NoteBase(BaseModel):
    id: str
    content: str
    type: str

class NoteCreate(NoteBase):
    pass

class Note(NoteBase):
    class Config:
        orm_mode = True

class SectionBase(BaseModel):
    id: str
    title: str
    section: str
    notes: List[NoteBase]

class SectionCreate(SectionBase):
    pass

class Section(SectionBase):
    class Config:
        orm_mode = True

class CanvasBase(BaseModel):
    name: str
    sections: List[SectionBase]

class CanvasCreate(CanvasBase):
    pass

class CanvasUpdate(CanvasBase):
    pass

class Canvas(CanvasBase):
    id: int
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True

class CanvasList(BaseModel):
    id: int
    name: str
    updated_at: str
    
    class Config:
        orm_mode = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create FastAPI app
app = FastAPI(title="Business Model Canvas API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
@app.get("/")
def read_root():
    return {"message": "Business Model Canvas API"}

@app.get("/api/canvases", response_model=List[CanvasList])
def get_canvases(db: Session = Depends(get_db)):
    canvases = db.query(CanvasModel).all()
    return canvases

@app.post("/api/canvases", response_model=Canvas, status_code=status.HTTP_201_CREATED)
def create_canvas(canvas: CanvasCreate, db: Session = Depends(get_db)):
    from datetime import datetime
    
    # Create timestamp
    now = datetime.utcnow().isoformat()
    
    # Create canvas
    db_canvas = CanvasModel(
        name=canvas.name,
        created_at=now,
        updated_at=now
    )
    db.add(db_canvas)
    db.commit()
    db.refresh(db_canvas)
    
    # Create sections
    for section_data in canvas.sections:
        db_section = SectionModel(
            section_id=section_data.id,
            title=section_data.title,
            canvas_id=db_canvas.id
        )
        db.add(db_section)
        db.commit()
        db.refresh(db_section)
        
        # Create notes
        for note_data in section_data.notes:
            db_note = NoteModel(
                note_id=note_data.id,
                content=note_data.content,
                type=note_data.type,
                section_id=db_section.id
            )
            db.add(db_note)
        
    db.commit()
    
    # Return the created canvas with all its data
    return get_canvas(db_canvas.id, db)

@app.get("/api/canvases/{canvas_id}", response_model=Canvas)
def get_canvas(canvas_id: int, db: Session = Depends(get_db)):
    canvas = db.query(CanvasModel).filter(CanvasModel.id == canvas_id).first()
    if canvas is None:
        raise HTTPException(status_code=404, detail="Canvas not found")
    
    # Construct the response
    result = {
        "id": canvas.id,
        "name": canvas.name,
        "created_at": canvas.created_at,
        "updated_at": canvas.updated_at,
        "sections": []
    }
    
    # Add sections and notes
    for section in canvas.sections:
        section_data = {
            "id": section.section_id,
            "title": section.title,
            "section": section.section_id,
            "notes": []
        }
        
        for note in section.notes:
            note_data = {
                "id": note.note_id,
                "content": note.content,
                "type": note.type
            }
            section_data["notes"].append(note_data)
        
        result["sections"].append(section_data)
    
    return result

@app.put("/api/canvases/{canvas_id}", response_model=Canvas)
def update_canvas(canvas_id: int, canvas: CanvasUpdate, db: Session = Depends(get_db)):
    db_canvas = db.query(CanvasModel).filter(CanvasModel.id == canvas_id).first()
    if db_canvas is None:
        raise HTTPException(status_code=404, detail="Canvas not found")
    
    # Update timestamp
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    
    # Update canvas name
    db_canvas.name = canvas.name
    db_canvas.updated_at = now
    
    # Delete all existing sections and notes
    db.query(SectionModel).filter(SectionModel.canvas_id == canvas_id).delete()
    db.commit()
    
    # Create new sections and notes
    for section_data in canvas.sections:
        db_section = SectionModel(
            section_id=section_data.id,
            title=section_data.title,
            canvas_id=db_canvas.id
        )
        db.add(db_section)
        db.commit()
        db.refresh(db_section)
        
        # Create notes
        for note_data in section_data.notes:
            db_note = NoteModel(
                note_id=note_data.id,
                content=note_data.content,
                type=note_data.type,
                section_id=db_section.id
            )
            db.add(db_note)
        
    db.commit()
    
    return get_canvas(canvas_id, db)

@app.delete("/api/canvases/{canvas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_canvas(canvas_id: int, db: Session = Depends(get_db)):
    db_canvas = db.query(CanvasModel).filter(CanvasModel.id == canvas_id).first()
    if db_canvas is None:
        raise HTTPException(status_code=404, detail="Canvas not found")
    
    db.delete(db_canvas)
    db.commit()
    
    return None

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
