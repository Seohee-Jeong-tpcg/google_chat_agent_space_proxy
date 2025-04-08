## 배포방법

### Docker 이미지 빌드

docker build -t gcr.io/tpcg-ark-ai/agent-space-middleware/agent-space-middleware:latest .

### Docker 이미지 푸시

docker push gcr.io/tpcg-ark-ai/agent-space-middleware/agent-space-middleware:latest

### Cloud Run 배포

gcloud run deploy agent-space-middleware \
 --image gcr.io/tpcg-ark-ai/agent-space-middleware/agent-space-middleware:latest \
 --platform managed \
 --region us-central1 \
 --allow-unauthenticated
