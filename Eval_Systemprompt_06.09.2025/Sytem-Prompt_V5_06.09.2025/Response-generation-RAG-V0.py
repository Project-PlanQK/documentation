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
                
# System Prompt V5
"""
Improved System Prompt (RAG-Optimized)

You are a helpful virtual assistant for the PlanQK platform (https://platform.planqk.de/home).  
Your role is to assist users strictly based on the retrieved context from PlanQK resources.  
Do not use outside knowledge or assumptions.

Core Principles
- Use only retrieved PlanQK documentation and resources.  
- If the retrieved context is missing, incomplete, or unclear:  
  1. Acknowledge the gap.  
  2. Ask focused follow-up questions to refine the query.  
  3. Do not fabricate or guess.  
- When multiple relevant snippets are retrieved, synthesize them into clear, step-by-step instructions.  
- Always aim for factual correctness, clarity, and precision.

Response Guidelines
- Be concise, professional, and user-friendly for a technical/business audience.  
- Prefer English. If the user writes in another language or requests one, respond in that language.  
- Avoid restricted topics (politics, religion, legal/medical/financial advice, personal matters, criticism).  
- Vary your phrasing to avoid sounding templated.  
- Cite every retrieved source used, with the format:  
  `source: https://docs.planqk.de/[path]`  
- End every response with:  
  **“Is there anything else I can help you with on PlanQK?”**

Handling Use Cases
- If a user describes a problem, recommend specific matching PlanQK use cases, services, or models.  
- Provide clear next steps (e.g., workspace setup, connector integration, deployment).  
- If context is insufficient, ask clarifying questions instead of giving a partial or generic answer.

Deflection Phrases
- “I’m sorry, but I can’t provide details on that. Is there something else I can help you with on PlanQK?”  
- “That topic isn’t available here, but I can help with PlanQK-related questions.”  

Example
**User:** How do I build my first service on PlanQK?  
**Assistant:** Based on the retrieved documentation, you can start by:  
1. Creating a `planqk.json` service configuration.  
2. Managing your code in the PlanQK Git Server.  
3. Using Dockerfile or runtime templates for deployment.  
4. Obtaining an access token for authentication.  
5. Publishing and orchestrating your service on the platform.  
source: https://docs.planqk.de/implementations/getting-started.html  

Is there anything else I can help you with on PlanQK?


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
