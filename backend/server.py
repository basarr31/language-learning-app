from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import csv
import io
import math
from .utils import calculate_streak

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Data Models
class VocabularyCard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    word: str
    translation: str
    example: str = ""
    notes: str = ""
    difficulty: str = "medium"  # easy, medium, hard
    language: str = "french"  # french, english
    
    # SRS (SM-2 Algorithm) fields
    ease_factor: float = 2.5
    interval: int = 1  # days
    repetitions: int = 0
    next_review: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())

class VocabularyCardCreate(BaseModel):
    word: str
    translation: str
    example: str = ""
    notes: str = ""
    difficulty: str = "medium"
    language: str = "french"

class VocabularyCardUpdate(BaseModel):
    word: Optional[str] = None
    translation: Optional[str] = None
    example: Optional[str] = None
    notes: Optional[str] = None
    difficulty: Optional[str] = None

class StudyResponse(BaseModel):
    card_id: str
    quality: int  # 0-5 scale (0=fail, 3=pass, 5=perfect)

class StudySession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cards_studied: int
    correct_answers: int
    session_duration: int  # minutes
    study_mode: str  # flashcards, quiz_matching, quiz_cloze, quiz_typing
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())

class StudySessionCreate(BaseModel):
    cards_studied: int
    correct_answers: int
    session_duration: int
    study_mode: str

class DailyProgress(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str  # YYYY-MM-DD format
    cards_studied: int = 0
    new_cards: int = 0
    review_cards: int = 0
    correct_rate: float = 0.0  # proportion of correct answers (0-1)
    study_time: int = 0  # minutes
    streak_count: int = 0

# SM-2 Algorithm Implementation
def calculate_sm2(quality: int, ease_factor: float, interval: int, repetitions: int):
    """
    SM-2 Algorithm for spaced repetition
    Quality: 0-5 scale (0=complete blackout, 5=perfect response)
    """
    if quality < 3:
        # Failed - reset repetitions and set interval to 1
        repetitions = 0
        interval = 1
    else:
        # Passed - increase repetitions and calculate new interval
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = round(interval * ease_factor)
    
    # Update ease factor
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    
    # Ensure ease factor doesn't go below 1.3
    if ease_factor < 1.3:
        ease_factor = 1.3
    
    return ease_factor, interval, repetitions

# Routes
@api_router.get("/")
async def root():
    return {"message": "Language Learning App API"}

# Vocabulary Management
@api_router.post("/vocabulary", response_model=VocabularyCard)
async def create_vocabulary_card(card: VocabularyCardCreate):
    card_dict = card.dict()
    card_obj = VocabularyCard(**card_dict)
    await db.vocabulary_cards.insert_one(card_obj.dict())
    return card_obj

@api_router.get("/vocabulary", response_model=List[VocabularyCard])
async def get_vocabulary_cards(language: Optional[str] = None, limit: int = 100):
    filter_dict = {}
    if language:
        filter_dict["language"] = language
    
    cards = await db.vocabulary_cards.find(filter_dict).limit(limit).to_list(length=limit)
    return [VocabularyCard(**card) for card in cards]

@api_router.get("/vocabulary/{card_id}", response_model=VocabularyCard)
async def get_vocabulary_card(card_id: str):
    card = await db.vocabulary_cards.find_one({"id": card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return VocabularyCard(**card)

@api_router.put("/vocabulary/{card_id}", response_model=VocabularyCard)
async def update_vocabulary_card(card_id: str, card_update: VocabularyCardUpdate):
    update_dict = {k: v for k, v in card_update.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.utcnow()
    
    result = await db.vocabulary_cards.update_one(
        {"id": card_id}, 
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    
    updated_card = await db.vocabulary_cards.find_one({"id": card_id})
    return VocabularyCard(**updated_card)

@api_router.delete("/vocabulary/{card_id}")
async def delete_vocabulary_card(card_id: str):
    result = await db.vocabulary_cards.delete_one({"id": card_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"message": "Card deleted successfully"}

# CSV Import
@api_router.post("/vocabulary/import")
async def import_vocabulary_csv(file: UploadFile = File(...), language: str = "french"):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        imported_cards = []
        for row in csv_reader:
            # Expected columns: Word, Translation, Example, Notes, Difficulty
            card_data = {
                "word": row.get("Word", "").strip(),
                "translation": row.get("Translation", "").strip(),
                "example": row.get("Example", "").strip(),
                "notes": row.get("Notes", "").strip(),
                "difficulty": row.get("Difficulty", "medium").lower().strip(),
                "language": language
            }
            
            if card_data["word"] and card_data["translation"]:
                card_obj = VocabularyCard(**card_data)
                await db.vocabulary_cards.insert_one(card_obj.dict())
                imported_cards.append(card_obj)
        
        return {"message": f"Successfully imported {len(imported_cards)} cards", "count": len(imported_cards)}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")

# Study System - Get cards due for review
@api_router.get("/study/due", response_model=List[VocabularyCard])
async def get_due_cards(language: Optional[str] = None, limit: int = 20):
    filter_dict = {"next_review": {"$lte": datetime.utcnow()}}
    if language:
        filter_dict["language"] = language
    
    cards = await db.vocabulary_cards.find(filter_dict).limit(limit).to_list(length=limit)
    return [VocabularyCard(**card) for card in cards]

@api_router.get("/study/new", response_model=List[VocabularyCard])
async def get_new_cards(language: Optional[str] = None, limit: int = 10):
    filter_dict = {"repetitions": 0}
    if language:
        filter_dict["language"] = language
    
    cards = await db.vocabulary_cards.find(filter_dict).limit(limit).to_list(length=limit)
    return [VocabularyCard(**card) for card in cards]

# Study Response - Update card based on SM-2 algorithm
@api_router.post("/study/response")
async def record_study_response(response: StudyResponse):
    card = await db.vocabulary_cards.find_one({"id": response.card_id})
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Calculate new SRS values using SM-2 algorithm
    ease_factor, interval, repetitions = calculate_sm2(
        response.quality,
        card["ease_factor"], 
        card["interval"],
        card["repetitions"]
    )
    
    # Calculate next review date
    next_review = datetime.utcnow() + timedelta(days=interval)
    
    # Update card
    update_dict = {
        "ease_factor": ease_factor,
        "interval": interval,
        "repetitions": repetitions,
        "next_review": next_review,
        "updated_at": datetime.utcnow()
    }
    
    await db.vocabulary_cards.update_one(
        {"id": response.card_id},
        {"$set": update_dict}
    )
    
    return {"message": "Response recorded", "next_review": next_review}

# Study Sessions
@api_router.post("/study/session", response_model=StudySession)
async def create_study_session(session: StudySessionCreate):
    session_obj = StudySession(**session.dict())
    await db.study_sessions.insert_one(session_obj.dict())
    
    # Update daily progress
    today = datetime.utcnow().date().isoformat()
    existing_progress = await db.daily_progress.find_one({"date": today})

    if existing_progress:
        # Update existing progress and recompute correct answer rate
        previous_cards = existing_progress.get("cards_studied", 0)
        previous_correct = existing_progress.get("correct_rate", 0) * previous_cards

        new_total_cards = previous_cards + session.cards_studied
        new_correct_answers = previous_correct + session.correct_answers
        new_correct_rate = (
            new_correct_answers / new_total_cards if new_total_cards > 0 else 0
        )

        await db.daily_progress.update_one(
            {"date": today},
            {
                "$inc": {
                    "cards_studied": session.cards_studied,
                    "study_time": session.session_duration,
                },
                "$set": {"correct_rate": new_correct_rate},
            },
        )
    else:
        # Create new progress entry
        progress = DailyProgress(
            date=today,
            cards_studied=session.cards_studied,
            study_time=session.session_duration,
            correct_rate=session.correct_answers / session.cards_studied if session.cards_studied > 0 else 0
        )
        await db.daily_progress.insert_one(progress.dict())
    
    return session_obj

# Progress and Statistics
@api_router.get("/progress/daily")
async def get_daily_progress(days: int = 7):
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days-1)
    
    progress_data = await db.daily_progress.find({
        "date": {
            "$gte": start_date.isoformat(),
            "$lte": end_date.isoformat()
        }
    }).to_list(length=days)
    
    return [DailyProgress(**progress) for progress in progress_data]

@api_router.get("/progress/stats")
async def get_statistics():
    total_cards = await db.vocabulary_cards.count_documents({})
    due_cards = await db.vocabulary_cards.count_documents({"next_review": {"$lte": datetime.utcnow()}})
    new_cards = await db.vocabulary_cards.count_documents({"repetitions": 0})
    
    # Get current streak
    today = datetime.utcnow().date()
    recent_progress = await db.daily_progress.find({}).sort("date", -1).limit(30).to_list(length=30)

    streak = calculate_streak(recent_progress, today)

    return {
        "total_cards": total_cards,
        "due_cards": due_cards,
        "new_cards": new_cards,
        "current_streak": streak
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()