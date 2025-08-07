import time
from fastapi import FastAPI, Path, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import re
import asyncio

app = FastAPI()

SERIAL_REGEX = re.compile(r"^[a-zA-Z0-9]{6,}$")

class EquipmentParams(BaseModel):
    timeoutInSeconds: int = Field(..., ge=1, le=60)
    parameters: dict

@app.post("/api/v1/equipment/cpe/{id}")
async def configure_equipment(
    id: str = Path(..., regex=r"^[a-zA-Z0-9]{6,}$"),
    body: EquipmentParams = None
):
    if not SERIAL_REGEX.match(id):
        raise HTTPException(status_code=404, detail="The requested equipment is not found")
    # Имитация долгой операции
    await asyncio.sleep(60)
    # Здесь можно добавить логику ошибок
    return {"code": 200, "message": "success"}
