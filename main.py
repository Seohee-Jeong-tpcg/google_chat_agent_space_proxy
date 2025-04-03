from typing import Any, Mapping
from fastapi import FastAPI, Request, HTTPException
import requests
import google.auth
import google.auth.transport.requests

app = FastAPI()


def get_access_token() -> str:
    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def search_vertex(query: str) -> dict:
    access_token = get_access_token()
    url = (
        "https://discoveryengine.googleapis.com/v1alpha/"
        "projects/661430115304/locations/global/collections/default_collection/"
        "engines/engine-agentspace_1741937659246/"
        "servingConfigs/default_search:search"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "pageSize": 5,
        "session": "projects/661430115304/locations/global/collections/default_collection/engines/engine-agentspace_1741937659246/sessions/-",
        "spellCorrectionSpec": {"mode": "AUTO"},
        "languageCode": "ko",
        "relevanceScoreSpec": {"returnRelevanceScore": True},
        "contentSearchSpec": {"snippetSpec": {"returnSnippet": True}},
        "naturalLanguageQueryUnderstandingSpec": {
            "filterExtractionCondition": "ENABLED"
        },
    }

    print("[DEBUG] Search Payload:", payload)

    response = requests.post(url, headers=headers, json=payload)
    print("[DEBUG] Search Responses : ", response)

    try:
        response.raise_for_status()
        print("[DEBUG] Search Responses : ", response.json())
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Search API Error: {e}")
        raise HTTPException(status_code=response.status_code, detail="Search API Error")


def generate_answer(query: str, session: str, query_id: str) -> dict:
    access_token = get_access_token()
    url = (
        "https://discoveryengine.googleapis.com/v1alpha/"
        "projects/661430115304/locations/global/collections/default_collection/"
        "engines/engine-agentspace_1741937659246/"
        "servingConfigs/default_search:answer"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": {"text": query, "queryId": query_id},
        "session": session,
        "relatedQuestionsSpec": {"enable": False},
        "answerGenerationSpec": {
            "ignoreAdversarialQuery": False,
            "ignoreNonAnswerSeekingQuery": False,
            "ignoreLowRelevantContent": False,
            "multimodalSpec": {},
            "includeCitations": True,
        },
    }

    print("[DEBUG] Answer Payload:", payload)

    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Answer API Error: {e}")
        raise HTTPException(status_code=response.status_code, detail="Answer API Error")


def create_answer_card(
    user: Mapping[str, Any], query: str, answer: Mapping[str, Any]
) -> Mapping[str, Any]:
    display_name = user.get("displayName", "User")
    answer_text = answer.get("answerText", "❌ 답변이 없습니다.")
    references = answer.get("references", [])

    widgets = [
        {"textParagraph": {"text": f"<b>❓ 질문:</b><br>{query}"}},
        {"textParagraph": {"text": f"<b>💡 답변:</b><br>{answer_text}"}},
    ]

    if references:
        widgets.append({"divider": {}})
        widgets.append({"textParagraph": {"text": "<b>📚 인용 문서:</b>"}})
        for ref in references:
            doc = ref.get("chunkInfo", {}).get("documentMetadata", {})
            title = doc.get("title", "No Title")
            uri = doc.get("uri", "")
            widgets.append(
                {
                    "decoratedText": {
                        "text": f"{title}",
                        "button": {
                            "text": "바로가기",
                            "onClick": {"openLink": {"url": uri}},
                        },
                    }
                }
            )
    response_data = {
        "text": f"{display_name}님의 질문에 대한 답변입니다.",
        "cardsV2": [
            {
                "cardId": "answerCard",
                "card": {
                    "name": "Answer Card",
                    "header": {
                        "title": f"Hello, {display_name}!",
                    },
                    "sections": [{"widgets": widgets}],
                },
            }
        ],
    }

    print("DEBUG :: RESPONSE CHAT FORM", response_data)

    return response_data


@app.post("/chat")
async def chat_app(req: Request) -> Mapping[str, Any]:
    event = await req.json()
    print("[DEBUG] Incoming request JSON:", event)

    if not event or "user" not in event or "message" not in event:
        raise HTTPException(status_code=400, detail="유효하지 않은 요청입니다.")

    user = event["user"]
    query = event["message"].get("argumentText", "").strip()

    search_response = search_vertex(query)
    print("[DEBUG] Search response:", search_response)

    session = search_response.get("sessionInfo", {}).get("name", "")
    query_id = search_response.get("sessionInfo", {}).get("queryId", "")

    if not session or not query_id:
        return create_answer_card(
            user,
            query,
            {"answerText": "⚠️ 검색 결과에서 세션 정보를 가져올 수 없습니다."},
        )

    answer_response = generate_answer(query, session, query_id)
    print("[DEBUG] Answer response:", answer_response)

    return create_answer_card(user, query, answer_response.get("answer", {}))
