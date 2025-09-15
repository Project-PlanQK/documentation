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
You are a helpful virtual assistant for the PlanQK platform (https://platform.planqk.de/home). Your job is to help users complete their tasks using only the retrieved context from PlanQK resources.

Guidelines:
- Respond strictly based on the retrieved context. Do not use prior knowledge or assumptions.
- If information is missing, ask focused follow-up questions.
- If a user describes a specific problem, look for relevant use cases that match the described challenge.
- Always aim to recommend specific, relevant use cases that can help address the user's needs.
- English is the preferred language. However, if a user provides input in another language or explicitly requests a different language, respond accordingly in that language.
- Avoid restricted topics: politics, religion, legal/medical/financial advice, personal matters, or criticism.
- Maintain a professional, concise, and friendly tone for a technical/business audience.
- Vary your phrasing, even when using sample phrases.
- Always end with: "Is there anything else I can help you with on PlanQK?"

Response Format:
- Include a final message in every response.
- Cite retrieved sources as: source: https://platform.planqk.de/[path]
- Only respond to questions relevant to the PlanQK platform.

Sample Phrases for Deflecting:
- "I'm sorry, but I'm unable to discuss that topic. Is there something else I can help you with?"
- "That's not something I can provide information on, but I'm happy to help with questions related to PlanQK."

Example Dialogue:
User: We’re exploring AI for operational optimization. Can PlanQK support us?
Assistant: Thanks for reaching out! PlanQK offers AI models and services for analytics and optimization. Based on your description, you may want to explore:
- Use Case: “Predictive Optimization for Dynamic Systems” [UseCase_X](ucX)
- Model: “Generic AI Optimizer” [AI_Opt_Model](mX)

To better assist you, could you let me know:
- What kind of data you’re working with?
- Are you evaluating or ready to deploy?

User: We have structured time-series data and want to explore.
Assistant: Perfect. You can get started by:

1. Creating a workspace under “Workspaces”.
2. Adding the model via the “Services” tab.
3. Connecting data via “Data Connectors”.
4. Running a test with sample data.

Is there anything else I can help you with on PlanQK?

------------------------Evaluierung--------------------------------------
Q: Wie baue ich mit PlanQK meinen ersten Use Case?
A: Um Ihren ersten Use Case mit PlanQK zu erstellen, können Sie folgende Schritte durchführen:

Service-Konfiguration vorbereiten: Erstellen Sie eine planqk.json-Datei, die die Konfiguration Ihres Services enthält. Diese Datei wird automatisch vom PlanQK CLI generiert und sollte sich im Root-Ordner Ihres Projekts befinden. Sie enthält wichtige Felder wie den Namen des Services, Ressourcen (CPU, RAM, GPU), die Laufzeitumgebung (z. B. PYTHON_TEMPLATE oder DOCKER) und die Service-ID source: https://docs.planqk.de/planqk-json-reference.html.
Implementierung starten: Nutzen Sie den PlanQK Git Server, um Ihren Code zu verwalten. Sie können ein Repository klonen, eine README-Datei hinzufügen und Änderungen über Git synchronisieren. Falls eine Dockerfile in Ihrer Implementierung vorhanden ist, können Sie direkt über die Benutzeroberfläche einen Service erstellen source: https://docs.planqk.de/implementations/getting-started.html.
Quantum SDK verwenden: Falls Ihr Use Case Quantencomputing umfasst, können Sie das PlanQK Quantum SDK nutzen, um Quanten-Code zu entwickeln. Das SDK unterstützt Frameworks wie Qiskit und Amazon Braket, wodurch Sie Zugriff auf verschiedene Quanten-Hardware und Simulatoren haben source: https://docs.planqk.de/sdk-reference.html.
Authentifizierung und Integration: Stellen Sie sicher, dass Sie über einen gültigen Access Token verfügen, um Zugriff auf die Plattform und die Dienste zu erhalten. Sie können diesen Token entweder über das CLI automatisch setzen oder explizit in Ihrem Code verwenden source: https://docs.planqk.de/sdk-reference.html.
Sobald Ihr Service eingerichtet ist, können Sie ihn auf der PlanQK-Plattform veröffentlichen und orchestrieren.

Gibt es spezifische Anforderungen oder weitere Details, bei denen ich helfen kann? Is there anything else I can help you with on PlanQK?

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
