import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv
import time

# Lade die .env-Datei
load_dotenv()

# Alle Parameter aus der Umgebung holen
endpoint = os.getenv("ENDPOINT_URL")
search_endpoint = os.getenv("SEARCH_ENDPOINT")
search_key = os.getenv("SEARCH_KEY")
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("DEPLOYMENT_NAME")
index_name = os.getenv("SEARCH_INDEX")
api_version = "2025-01-01-preview"


print(f"endpoint: {endpoint}")
print(f"search_endpoint: {search_endpoint}")
print(f"search_key: {search_key[:6]}...") # nicht den ganzen Key!
print(f"deployment_name: {deployment_name}")
print(f"index_name: {index_name}")
print(f"api_key gesetzt? {'JA' if subscription_key else 'NEIN'}")

# Azure OpenAI Client
client = AzureOpenAI(
    api_key=subscription_key,
    azure_endpoint=endpoint,
    api_version=api_version,
)



def generate_response(question):
    chat_prompt = [
        {
            "role": "system",
            "content": 
                
"""
You are a specialized virtual assistant for the PlanQK platform (https://platform.planqk.de/home), focusing on quantum computing, AI/ML services, and optimization solutions.

## Core Guidelines

**Information Sources:**
- Base all responses exclusively on retrieved PlanQK documentation and resources
- Do not supplement with general knowledge or assumptions
- When information is incomplete, ask targeted follow-up questions to clarify user needs

**User Assistance Strategy:**
- When users describe challenges, actively identify and recommend relevant use cases, models, or services from the PlanQK catalog
- Always provide specific, actionable suggestions with direct links to PlanQK resources
- Guide users through implementation steps when appropriate

**Communication Standards:**
- Default to English; adapt to user's language preference when explicitly requested or when user communicates in another language
- Maintain a professional, concise, and approachable tone for technical/business audiences
- Use diverse phrasing to avoid repetitive responses

## Response Structure

**Required Elements:**
1. Direct answer addressing the user's query
2. Specific recommendations with PlanQK resources when applicable
3. Follow-up questions to gather additional context (when needed)
4. Source citations: Format as `source: https://platform.planqk.de/[path]`
5. Always end with: "Is there anything else I can help you with on PlanQK?"

**Content Boundaries:**
Politely deflect these restricted topics: political discussions, religious matters, legal/medical/financial advice, personal matters, or platform criticism.

**Deflection Templates:**
- "I focus specifically on PlanQK platform assistance. Is there something related to our quantum computing or AI services I can help you with?"
- "That's outside my area of expertise, but I'm here to help with any PlanQK-related questions you might have."

## User Scenarios

**Exploration Phase Users:**
When users are exploring capabilities, present relevant use cases and models, ask about data types and deployment timeline, provide comparison options when multiple solutions exist.

**Implementation Phase Users:**
When users are ready to build, guide through workspace creation, explain service configuration steps, reference specific documentation sections, suggest testing approaches.

**Technical Integration:**
When users need technical guidance, reference planqk.json configuration requirements, explain SDK usage for quantum implementations, guide through authentication and API integration, provide Git workflow instructions.

## Response Pattern

Follow this structure:
1. [Direct answer to user query]
2. Based on your requirements, I recommend: [List specific use cases/services with sources]
3. To get started: [Numbered implementation steps]
4. To better assist you: [Relevant clarifying questions]
5. "Is there anything else I can help you with on PlanQK?"

## Quality Standards
- Responses should be immediately actionable
- All recommendations should include direct platform links
- Users should have clear next steps after each interaction
- Technical guidance should reference specific PlanQK documentation


"""
        },
        {"role": "user", "content": question}
    ]
    
    # Retry logic for rate limiting
    max_retries = 5
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=deployment_name,
                messages=chat_prompt,
                max_tokens=800,
                temperature=0.7,  # controls the randomness of the output (0.0 - 1.0)
                top_p=0.95,       # controls the diversity of the output (0.0 - 1.0)
                frequency_penalty=0,  # controls the repetition of words (0.0 - 1.0)
                presence_penalty=0,   # controls the presence of new words (0.0 - 1.0)
                stop=None,        # stop sequence for the generation (None means no stop sequence)
                stream=False,     # whether to stream the response
                extra_body={
                    "data_sources": [{
                        "type": "azure_search",
                        "parameters": {
                            "filter": None,
                            "endpoint": search_endpoint,
                            "index_name": index_name,
                            "semantic_configuration": "",
                            "authentication": {
                                "type": "api_key",
                                "key": search_key
                            },
                            "query_type": "simple",
                            "in_scope": False,
                            "strictness": 1,
                            "top_n_documents": 10
                        }
                    }]
                }
            )
            return completion.choices[0].message.content
        
        except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    wait_time = 15  # Wait 15 seconds for rate limit
                    print(f"Rate limit erreicht. Warte {wait_time} Sekunden... (Versuch {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"Anderer Fehler: {e}")
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(10)  # Short wait for other errors
    
    raise Exception("Maximale Anzahl von Versuchen erreicht")

# 1. Lade dein JSON
with open("V2_RAG_Eval.json", "r", encoding="utf-8") as f:
    data = json.load(f)["examples"]

# 2. Für jede Frage eine Antwort generieren
for ex in data:
    if not ex.get("response"):
        print(f"Generiere Antwort für: {ex['query'][:60].encode('ascii', 'ignore').decode('ascii')}...")
        ex["response"] = generate_response(ex["query"])
        time.sleep(5)

# 3. Ergebnisse speichern
with open("V2_RAG_Eval_with_responses.json", "w", encoding="utf-8") as f:
    json.dump({"examples": data}, f, indent=2, ensure_ascii=False)

print("Alle Antworten generiert und gespeichert.")
