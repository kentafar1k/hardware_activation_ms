import uuid
import re
import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, Path, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import aio_pika

app = FastAPI()

SERIAL_REGEX = re.compile(r"^[a-zA-Z0-9]{6,}$")
RABBITMQ_URL = "amqp://user:password@rabbitmq/"
TASK_QUEUE = "equipment_tasks"
RESULT_QUEUE = "equipment_results"

# In-memory хранилище задач
# task_id: {timestamp, id, equipment_id, parameters, status}
tasks = {}

class EquipmentParams(BaseModel):
    timeoutInSeconds: int = Field(..., ge=1, le=60)
    parameters: dict

@app.post("/api/v1/equipment/cpe/{id}")
async def create_task(
    id: str = Path(..., regex=r"^[a-zA-Z0-9]{6,}$"),
    body: EquipmentParams = None
):
    if not SERIAL_REGEX.match(id):
        raise HTTPException(status_code=404, detail="The requested equipment is not found")
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    tasks[task_id] = {
        "timestamp": now,
        "equipment_id": id,
        "parameters": body.parameters if body else {},
        "status": "pending"
    }
    # Отправка задачи в RabbitMQ
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps({
                    "task_id": task_id,
                    "equipment_id": id,
                    "parameters": body.parameters if body else {},
                    "timeoutInSeconds": body.timeoutInSeconds if body else 14
                }).encode()),
                routing_key=TASK_QUEUE
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal provisioning exception")
    return {"code": 200, "taskId": task_id}

@app.get("/api/v1/equipment/cpe/{id}/task/{task}")
async def get_task_status(
    id: str = Path(..., regex=r"^[a-zA-Z0-9]{6,}$"),
    task: str = Path(...)
):
    if not SERIAL_REGEX.match(id):
        raise HTTPException(status_code=404, detail="The requested equipment is not found")
    task_info = tasks.get(task)
    if not task_info:
        raise HTTPException(status_code=404, detail="The requested task is not found")
    if task_info["equipment_id"] != id:
        raise HTTPException(status_code=404, detail="The requested equipment is not found")
    status = task_info["status"]
    if status == "pending":
        return JSONResponse(status_code=204, content={"code": 204, "message": "Task is still running"})
    elif status == "completed":
        return {"code": 200, "message": "Completed"}
    elif status == "failed":
        return JSONResponse(status_code=500, content={"code": 500, "message": "Internal provisioning exception"})
    else:
        return JSONResponse(status_code=500, content={"code": 500, "message": "Unknown status"})

# Фоновая задача для получения результатов из RabbitMQ
@app.on_event("startup")
async def startup_event():
    async def consume_results():
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        queue = await channel.declare_queue(RESULT_QUEUE, durable=True)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        task_id = data.get("task_id")
                        status = data.get("status")
                        if task_id in tasks:
                            tasks[task_id]["status"] = status
                    except Exception:
                        pass
    asyncio.create_task(consume_results())
