# 사용하려는 베이스 이미지를 선택합니다.
FROM python:3.13.3-slim

# 작업 디렉터리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y libpq-dev gcc

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# Uvicorn으로 FastAPI 애플리케이션 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
