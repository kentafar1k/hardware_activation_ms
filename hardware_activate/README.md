# Hardware Activate

## Описание

Система для асинхронной активации оборудования через два сервиса и очередь сообщений RabbitMQ.

- **Service A** — синхронная заглушка для конфигурации оборудования
- **Service B** — асинхронный сервис для постановки задач
- **Worker** — воркер, обрабатывающий задачи из очереди

## Архитектура

```
Client <-> Service B <-> RabbitMQ <-> Worker <-> Service A
                                 ^         |
                                 |         v
                              (results)  (HTTP)
```

- Service B создает задачи и кладет их в очередь RabbitMQ
- Worker читает задачи, вызывает Service A, отправляет результат обратно в очередь
- Service B подписан на очередь результатов и обновляет статус задачи

## Запуск через Docker Compose

```bash
docker-compose up --build
```

## Переменные окружения
- SERVICE_A_URL (для воркера, по умолчанию http://service_a:8000/api/v1/equipment/cpe/)

## Сервисы
- Service A: http://localhost:8001
- Service B: http://localhost:8002
- RabbitMQ: http://localhost:15672 (user/password)

## Примеры запросов

### Создать задачу (Service B)
```
POST /api/v1/equipment/cpe/ABC123
{
  "timeoutInSeconds": 14,
  "parameters": {
    "username": "admin",
    "password": "admin",
    "vlan": 534,
    "interfaces": [1,2,3,4]
  }
}
```
Ответ:
```
{
  "code": 200,
  "taskId": "..."
}
```

### Проверить статус задачи (Service B)
```
GET /api/v1/equipment/cpe/ABC123/task/{taskId}
```
Ответы:
- 200: `{ "code": 200, "message": "Completed" }`
- 204: `{ "code": 204, "message": "Task is still running" }`
- 404/500: ошибки

### Прямой вызов Service A (заглушка)
```
POST /api/v1/equipment/cpe/ABC123
{
  "timeoutInSeconds": 14,
  "parameters": { ... }
}
```
Ответ через 60 секунд:
```
{
  "code": 200,
  "message": "success"
}
```

## Тестирование

Можно использовать Postman или curl для ручных запросов. Пример:
```
curl -X POST http://localhost:8002/api/v1/equipment/cpe/ABC123 -H "Content-Type: application/json" -d '{"timeoutInSeconds": 14, "parameters": {"username": "admin", "password": "admin"}}'
```
