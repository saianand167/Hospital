from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.models.history import ClinicalHistoryJSON
from app.models.question import QuestionPrompt
from app.models.patient import LanguageCode
from app.models.consultation import ConsultationSummary
from app.models.answer import AnswerRecord
from app.services.history_service import HistoryService
from app.services.consultation_service import ConsultationService

router = APIRouter(tags=["Clinical Session & Consultation"])

class StartSessionRequest(BaseModel):
    user_id: str = "USR-000001"
    visit_id: Optional[str] = None
    language: LanguageCode = "en"
    initial_complaint: Optional[str] = None

class MessageRequest(BaseModel):
    message: str
    target_field: Optional[str] = None
    question_text: Optional[str] = None
    is_touch_input: bool = False
    touch_value: Optional[str] = None

class SessionResponse(BaseModel):
    history: ClinicalHistoryJSON
    next_question: Optional[QuestionPrompt] = None
    is_completed: bool = False
    transcribed_text: Optional[str] = None

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "MediKiosk Part 1 - Real-Time Multilingual Clinical History & AI Intake",
        "version": "1.0.0"
    }

@router.post("/session/start", response_model=SessionResponse)
def start_session(req: StartSessionRequest):
    history, prompt = HistoryService.start_session(
        user_id=req.user_id,
        visit_id=req.visit_id,
        language=req.language,
        initial_complaint=req.initial_complaint
    )
    return SessionResponse(
        history=history,
        next_question=prompt,
        is_completed=history.metadata.completed
    )

@router.post("/session/{visit_id}/message", response_model=SessionResponse)
async def process_message(visit_id: str, req: MessageRequest):
    history, prompt, is_completed = await HistoryService.process_message(
        visit_id=visit_id,
        patient_message=req.message,
        target_field=req.target_field,
        question_text=req.question_text,
        is_touch_input=req.is_touch_input,
        touch_value=req.touch_value
    )
    return SessionResponse(
        history=history,
        next_question=prompt,
        is_completed=is_completed
    )

@router.post("/session/{visit_id}/audio", response_model=SessionResponse)
async def process_audio(
    visit_id: str,
    file: UploadFile = File(...),
    target_field: Optional[str] = Form(None),
    question_text: Optional[str] = Form(None)
):
    audio_bytes = await file.read()
    transcribed, history, prompt, is_completed = await HistoryService.process_audio(
        visit_id=visit_id,
        audio_bytes=audio_bytes,
        target_field=target_field,
        question_text=question_text
    )
    return SessionResponse(
        history=history,
        next_question=prompt,
        is_completed=is_completed,
        transcribed_text=transcribed
    )

@router.get("/session/{visit_id}/next-question")
def get_next_question(visit_id: str):
    history = HistoryService.get_session(visit_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    from app.clinical.question_engine import ClinicalQuestionEngine
    prompt, is_comp = ClinicalQuestionEngine.get_next_question(history)
    return {
        "visit_id": visit_id,
        "next_question": prompt,
        "is_completed": is_comp
    }

@router.get("/session/{visit_id}/state", response_model=ClinicalHistoryJSON)
def get_session_state(visit_id: str):
    history = HistoryService.get_session(visit_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    return history

@router.get("/session/{visit_id}/history", response_model=List[AnswerRecord])
def get_conversation_history(visit_id: str):
    return HistoryService.get_conversation_history(visit_id)

@router.post("/session/{visit_id}/complete", response_model=ClinicalHistoryJSON)
def complete_session(visit_id: str):
    history = HistoryService.complete_session(visit_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    return history

@router.get("/consultations/{user_id}", response_model=List[ConsultationSummary])
def get_user_consultations(user_id: str):
    return ConsultationService.get_user_consultations(user_id)
