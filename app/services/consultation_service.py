from typing import List, Optional
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.answer_repository import AnswerRepository
from app.models.consultation import ConsultationSummary
from app.models.answer import AnswerRecord

class ConsultationService:
    @staticmethod
    def get_user_consultations(user_id: str) -> List[ConsultationSummary]:
        return ConsultationRepository.get_by_user(user_id)

    @staticmethod
    def get_consultation_details(visit_id: str) -> Optional[dict]:
        c_data = ConsultationRepository.get_by_visit_id(visit_id)
        if not c_data:
            return None
        history_json = ConsultationRepository.get_final_history(visit_id)
        answers = AnswerRepository.get_by_visit_id(visit_id)
        return {
            "consultation": c_data,
            "final_history": history_json,
            "answers": [a.model_dump() for a in answers]
        }
