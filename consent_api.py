from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Optional

from consent_core import (
    fractal_id_from_image,
    issue_capsule,
    revoke_capsule,
    verify_and_enforce,
)

app = FastAPI(title="X Identity Shield — Consent Layer")

class CapsuleRequest(BaseModel):
    fractal_id: str
    scope: Dict[str, str]
    expires_in: Optional[int] = 3600

class CheckRequest(BaseModel):
    fractal_id: str
    prompt: str
    capsule: Optional[str] = None

@app.post("/fractal-id")
async def generate_fractal_id(file: UploadFile = File(...)):
    image_bytes = await file.read()
    return {"fractal_id": fractal_id_from_image(image_bytes)}

@app.post("/capsule/issue")
def issue(req: CapsuleRequest):
    token = issue_capsule(
        fractal_id=req.fractal_id,
        scope=req.scope,
        expires_in=req.expires_in,
    )
    return {"capsule": token}

@app.post("/check")
def check(req: CheckRequest):
    return verify_and_enforce(
        fractal_id=req.fractal_id,
        prompt=req.prompt,
        capsule_token=req.capsule,
    )

@app.post("/capsule/revoke/{capsule_id}")
def revoke(capsule_id: str):
    revoke_capsule(capsule_id)
    return {"revoked": capsule_id}
