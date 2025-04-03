from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# 테스트용 요청 데이터를 설정합니다.
test_event = {
    "user": {"displayName": "Test User"},
    "message": {"argumentText": "2월 추천도서"},
}

# chat_app 엔드포인트에 POST 요청을 보냅니다.
response = client.post("/chat", json=test_event)

# 응답을 출력합니다.
print("Status Code:", response.status_code)
print("Response JSON:", response.json())
