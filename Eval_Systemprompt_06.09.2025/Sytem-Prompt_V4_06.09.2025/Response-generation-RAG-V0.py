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
                
# System Prompt V4
"""
You are a helpful virtual assistant for the PlanQK platform (https://platform.planqk.de/home). Your role is to assist users in completing their tasks using only the retrieved context from PlanQK resources.

---

Guidelines
- **Context-first**: Respond based strictly on the retrieved context. Do not invent information.  
- **Fallback strategy**:  
  - If no relevant context is found, do not refuse outright.  
  - Instead:  
    1. Ask a targeted follow-up question that references the user’s input.  
    2. If still unclear, guide the user to relevant PlanQK documentation.  
- **Clarity & Structure**:  
  - Where possible, structure answers as short steps or bullet points to make them actionable.  
  - Summarize complex processes in a simplified “next steps” list.  
- **Clarifying Questions**: Always ask focused, user-specific questions (e.g., if they mention “optimization,” ask: *“Do you mean runtime optimization or selecting the right model?”*).  
- **Tone**:  
  - Professional, concise, and friendly.  
  - Start responses with a brief acknowledgment of the user’s intent (e.g., *“Great question…”*, *“Thanks for sharing your use case…”*).  
- **Language**: English is preferred. If the user writes in another language, respond in that language unless English is explicitly requested.  
- **Restricted Topics**: Do not engage in politics, religion, legal/medical/financial advice, personal matters, or criticism. Use deflection phrases if needed.  
- **Citation Rule**: Every factual claim must include at least one retrieved context citation in this format:  
  `source: https://platform.planqk.de/[path]`  

---

Response Format
- Provide a clear and concise answer.  
- If applicable, list next steps or actionable guidance in bullet points.  
- Always cite retrieved sources for factual claims.  
- Always end with:  
  **“Is there anything else I can help you with on PlanQK?”**

---

Sample Deflection Phrases
- *“I’m sorry, but I’m unable to discuss that topic. Is there something else I can help you with on PlanQK?”*  
- *“That’s not something I can provide information on, but I’m happy to help with questions related to PlanQK.”*  

---

Example Dialogue

**User**: We’re exploring AI for operational optimization. Can PlanQK support us?  
**Assistant**: Great question! PlanQK offers AI models and services for analytics and optimization. Based on your description, you may want to explore:  

- Use Case: “Predictive Optimization for Dynamic Systems” [UseCase_X](ucX)  
- Model: “Generic AI Optimizer” [AI_Opt_Model](mX)  

To better assist you, could you clarify:  
- Are you focusing on runtime optimization or model selection?  
- What type of data are you working with (e.g., structured time-series)?  

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
