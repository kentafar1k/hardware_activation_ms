import aio_pika
import asyncio
import json
import aiohttp
import os

RABBITMQ_URL = "amqp://user:password@rabbitmq/"
TASK_QUEUE = "equipment_tasks"
RESULT_QUEUE = "equipment_results"
SERVICE_A_URL = os.environ.get("SERVICE_A_URL", "http://service_a:8000/api/v1/equipment/cpe/")

async def process_task(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body.decode())
            task_id = data["task_id"]
            equipment_id = data["equipment_id"]
            parameters = data["parameters"]
            timeout = data.get("timeoutInSeconds", 14)
            # Вызов сервиса A
            url = f"{SERVICE_A_URL}{equipment_id}"
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json={"timeoutInSeconds": timeout, "parameters": parameters}, timeout=timeout+5) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            status = "completed"
                        elif resp.status == 404:
                            status = "failed"
                        else:
                            status = "failed"
                except Exception as e:
                    status = "failed"
            # Публикация результата
            result_msg = {
                "task_id": task_id,
                "status": status
            }
            await message.channel.default_exchange.publish(
                aio_pika.Message(body=json.dumps(result_msg).encode()),
                routing_key=RESULT_QUEUE
            )
        except Exception as e:
            # Логировать ошибку, не подтверждать сообщение для повторной обработки
            print(f"Worker error: {e}")
            raise

async def main():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue(TASK_QUEUE, durable=True)
    await queue.consume(process_task, no_ack=False)
    print("Worker started. Waiting for tasks...")
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
