from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import consent_core

app = FastAPI(title="X Consent Layer API")

class IssueRequest(BaseModel):
    fractal_id: str
    holder_did: str
    scope: Dict[str, str]
    price_usd: Optional[float] = 0.0
    friends_allowlist: Optional[List[str]] = None
    audience: Optional[List[str]] = None
    expires: Optional[int] = None

@app.post("/fractal-id")
async def fractal_id(file: UploadFile = File(...)):
    data = await file.read()
    try:
        fid = consent_core.fractal_id_from_image(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"fractal_id": fid}

@app.post("/capsule/issue")
async def capsule_issue(req: IssueRequest):
    try:
        token = consent_core.issue_consent_capsule(
            fractal_id=req.fractal_id,
            scope=req.scope,
            holder_did=req.holder_did,
            price_usd=req.price_usd or 0.0,
            friends_allowlist=req.friends_allowlist,
            audience=req.audience,
            expires=req.expires
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"capsule_token": token}

class CheckRequest(BaseModel):
    prompt: str
    capsule_token: Optional[str] = None
    requester_fid: Optional[str] = None

@app.post("/check")
async def check_endpoint(file: UploadFile = File(...), prompt: str = Form(...), capsule_token: Optional[str] = Form(None), requester_fid: Optional[str] = Form(None)):
    img = await file.read()
    try:
        res = consent_core.check_generation_allowed(
            capsule_token=capsule_token,
            reference_image_bytes=img,
            prompt=prompt,
            requester_fid=requester_fid
        )
    except Exception as e:
        return JSONResponse(status_code=400, content={"allowed": False, "reason": str(e), "price": 0.0})
    return res

@app.post("/capsule/revoke/{capsule_id}")
async def revoke(capsule_id: str):
    try:
        consent_core.revoke_capsule(capsule_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"revoked": capsule_id}
