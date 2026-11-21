from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from src.multimodal.ocr_service import extract_text, OCRUnavailable

from src.services.analysis_service import analyze_sms

app = FastAPI(title="GramSuraksha AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SMSRequest(BaseModel):
    text: str
    language_override: str | None = None
    model_choice: str = "baseline"


@app.get("/")
def home():
    return {"message": "GramSuraksha AI API is running"}


@app.post("/analyze")
def analyze(request: SMSRequest):
    result = analyze_sms(
        text=request.text,
        language_override=request.language_override,
        model_choice=request.model_choice
    )
    return result
@app.post("/extract-text")
async def extract_sms_text(
    file: UploadFile = File(...),
    language: str = Form("auto")
):
    try:
        image_data = await file.read()

        result = extract_text(
            data=image_data,
            language=language
        )

        return {
            "ok": True,
            "text": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "words": result.words,
            "warnings": result.warnings,
            "needs_review": result.needs_review
        }

    except OCRUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    finally:
        await file.close()

