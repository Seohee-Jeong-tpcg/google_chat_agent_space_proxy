from datetime import timedelta
from typing import Any, Mapping
from fastapi import FastAPI, Request, HTTPException
import requests
import google.auth
import google.auth.transport.requests
from google.cloud import storage
from google.oauth2 import service_account

app = FastAPI()
PROJECT_ID = "tpcg-ark-ai"
PROJECT_NUMBER = "661430115304"
LOCATION = "global"
COLLECTION = "default_collection"
APP_ID = "connect-arkai-agentspace-t_1744609813251"
ENGINE_VERSION = "v1alpha"


def get_access_token() -> str:
    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def make_api_request(endpoint: str, payload: dict, access_token: str) -> dict:
    """
    Helper function to make a POST request to the Discovery Engine API.

    Args:
        endpoint (str): The API endpoint (e.g., "default_search:search", "cx_assistant:assist", "default_search:answer").
        payload (dict): The request payload.
        access_token (str): The access token for authentication.

    Returns:
        dict: The JSON response from the API.
    """
    url = (
        f"https://discoveryengine.googleapis.com/{ENGINE_VERSION}/"
        f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/collections/{COLLECTION}/"
        f"engines/{APP_ID}/{endpoint}"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload)

    try:
        response.raise_for_status()
        print(f"[DEBUG] {endpoint} Response JSON:", response.json())
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] {endpoint} API Error: {e}")
        raise HTTPException(
            status_code=response.status_code, detail=f"{endpoint} API Error"
        )


def default_search(query: str) -> dict:
    """
    Perform a default search using the Discovery Engine API.

    Args:
        query (str): The search query.

    Returns:
        dict: The search results.
    """
    access_token = get_access_token()
    payload = {
        "query": query,
        "pageSize": 5,
        "session": f"projects/{PROJECT_NUMBER}/locations/{LOCATION}/collections/{COLLECTION}/engines/{APP_ID}/sessions/-",
        "spellCorrectionSpec": {"mode": "AUTO"},
        "languageCode": "ko",
        "relevanceScoreSpec": {"returnRelevanceScore": True},
        "contentSearchSpec": {"snippetSpec": {"returnSnippet": True}},
        "naturalLanguageQueryUnderstandingSpec": {
            "filterExtractionCondition": "ENABLED"
        },
    }
    return make_api_request(
        "servingConfigs/default_search:search", payload, access_token
    )


def assistant_search(query: str) -> dict:
    """
    Perform an assistant search using the Discovery Engine API.

    Args:
        query (str): The search query.

    Returns:
        dict: The assistant search results.
    """

    access_token = get_access_token()
    payload = {
        "query": {"text": query},
    }
    return make_api_request("assistants/cx_assistant:assist", payload, access_token)


def generate_with_answer_api(query: str, session: str, query_id: str) -> dict:
    """
    Generate an answer using the Discovery Engine API.

    Args:
        query (str): The query text.
        session (str): The session ID.
        query_id (str): The query ID.

    Returns:
        dict: The generated answer.
    """
    access_token = get_access_token()
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
    return make_api_request(
        "servingConfigs/default_search:answer", payload, access_token
    )


@app.post("/chat")
async def chat_app(req: Request) -> Mapping[str, Any]:
    event = await req.json()
    print("[DEBUG] Incoming request JSON:", event)

    if not event or "user" not in event or "message" not in event:
        raise HTTPException(status_code=400, detail="유효하지 않은 요청입니다.")

    user = event["user"]
    query = event["message"].get("argumentText", "").strip()
    session = ""
    print("[DEBUG] User:", user)

    search_response = default_search(query)
    print("[DEBUG] Search response:", search_response)
    session = search_response.get("sessionInfo", {}).get("name", "")
    query_id = search_response.get("sessionInfo", {}).get("queryId", "")

    response_data = {
        "user": user,
        "query": query,
        "response_data": {"answerText": "⚠️ Assistant search에서 오류가 발생했습니다."},
    }

    if search_response.get("results") is not None:
        # default_search에서 결과가 있을 경우 answer 생성

        if not session or not query_id:
            response_data["response_data"][
                "answerText"
            ] = "⚠️ 검색 결과에서 세션 정보를 가져올 수 없습니다."
            return response_data
        else:
            answer_response = generate_with_answer_api(query, session, query_id)
            answer_response = answer_response.get(
                "answer",
                {"answerText": "⚠️ 검색 결과가 없습니다. 다른 질문을 해보세요."},
            )
            print("[DEBUG] Answer response:", answer_response)

    else:
        # default_search에서 결과가 없을 경우 assistant_search로 대체
        query_arr = [
            '{ "user_id" : "',
            user["email"],
            ' " , ',
            '"query" : "',
            query,
            '" }',
        ]
        formatted_query = "".join(query_arr)
        try:
            search_response = assistant_search(formatted_query)
            print("[DEBUG] Assistant search response:", search_response)
            replies = search_response.get("answer", {}).get("replies", [])
        except Exception as e:
            print("[ERROR] Assistant search error:", e)
            return {
                "user": user,
                "query": query,
                "response_data": {
                    "answerText": "⚠️ Assistant search에서 오류가 발생했습니다."
                },
            }
        answer_text = "⚠️ 검색 결과가 없습니다. 다른 질문을 해보세요."
        if replies:
            answer_text = ""
            for reply in replies:
                grounded_content = (
                    reply.get("groundedContent", {}).get("content", {}).get("text")
                )
                answer_text += f"{grounded_content} "
        answer_response = {"answerText": answer_text}
        response_data["response_data"] = answer_response

    return response_data


def generate_signed_url(bucket_name, blob_name, expiration_hours=1):
    """
    Generate a signed URL for a GCS object.

    Args:
        bucket_name (str): The name of the GCS bucket.
        blob_name (str): The name of the GCS object (file).
        expiration_hours (int): The expiration time of the signed URL in hours. Default is 1 hour.

    Returns:
        str: The signed URL for the GCS object.
    """
    # Initialize the Google Cloud Storage client with the service account credentials
    client = storage.Client(
        credentials=service_account.Credentials.from_service_account_file(
            "gcs_key.json"
        ),
        project="tpcg-ark-ai",
    )

    # Get the bucket and blob (file)
    bucket = client.get_bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Generate the signed URL for the blob (file)
    signed_url = blob.generate_signed_url(
        expiration=timedelta(hours=expiration_hours),  # Set the expiration time
        method="GET",  # Allows GET requests to download the file
    )

    return signed_url
