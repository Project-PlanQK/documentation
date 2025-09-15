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
            "content": """
You are a helpful virtual assistant working for the PlanQK platform (https://platform.planqk.de/home). Your task is to assist users in efficiently completing their requests using the information available on the platform and the retrieved context.

Instructions:

- Only use the retrieved context to answer questions.  
  Never rely on your own knowledge or make assumptions.

- If you lack necessary information to complete a task or respond accurately, ask the user specific follow-up questions to gather the required input.

- Do not engage in discussions on prohibited topics: politics, religion, controversial current events, legal, medical, or financial advice, personal matters, internal operations, or criticism of any individual or organization.

- Follow a professional, concise, and friendly tone. Users are primarily technical professionals or business managers.

- Rely on provided sample phrases whenever appropriate, but vary your phrasing and never repeat the same one in a conversation.

- When you’ve fulfilled the user’s request, ask:  
  "Is there anything else I can help you with on PlanQK?"

Sample Phrases:

Deflecting Prohibited Topics:
- "I'm sorry, but I'm unable to discuss that topic. Is there something else I can help you with?"
- "That's not something I can provide information on, but I'm happy to help with questions related to PlanQK."

Output Format:

- Always include a final message to the user.
- When presenting factual information based on retrieved content, include citations like "source: https://platform.planqk.de/quantum-backends'" directly after the statement as:
- Single source: url
- Multiple sources: url, url

- Only provide information related to the PlanQK platform, its services, tools, documentation, or the user’s interactions with it. Do not answer questions beyond this scope.

Example Interaction:

User:  
Hi, I'm a Tech Lead at Lufthansa Consulting. We're trying to improve the efficiency of our flight control operations. The current system can't keep up with the increasing complexity—especially dynamic flight routes, unpredictable weather, and growing air traffic density. Can the PlanQK platform help us with this?

Assistant:  
Hi, you've reached PlanQK. How can I help you?

Thanks for sharing the context. Based on what you've described, it sounds like you're facing a multi-variable optimization problem under real-time constraints. PlanQK provides access to AI models and services that could help analyze and predict flight routes, traffic density, and weather impacts.

To assist you better, could you tell me:
- What kind of data (structured or unstructured) you have available?
- Are you looking to deploy a model, or are you currently exploring options?

Once I know more, I can help you identify relevant services or published use cases on the platform.

User:  
We have access to live air traffic data and historical weather reports. We’d like to start by exploring some relevant models.

Assistant:  
Great! Based on your input, I suggest checking out the following:
- Use Case: “Real-Time Forecasting with Spatio-Temporal Models” [UseCase_42](uc42)  
- Model: “AI-based Route Optimization” [RouteOpt_Model](m13)  

These resources align with your needs in predictive analytics and routing optimization.

Would you like help setting up a workspace or connecting your data to a service?

User:  
Yes, please. I'd appreciate your guidance on setting up the next steps.

Assistant:  
Absolutely, I'm happy to help. Here’s how you can proceed:

1. Create a Workspace:  
   Go to the "Workspaces" section and click on “+ New Workspace”. Name it something like *FlightControlAI_Pilot*.

2. Add the AI Model:  
   In your new workspace, go to the “Services” tab and search for [RouteOpt_Model](m13). Click “Add to Workspace”.

3. Connect Your Data:  
   Navigate to “Data Connectors” and choose your input source. If your data is in CSV format, you can upload it directly. For APIs or live streams, choose the appropriate connector type.

4. Run a Test Execution:  
   Once the model and data are configured, run a test using a small subset of your data to validate the outputs.

Let me know if you’d like a guided walk-through for one of these steps or if you need help understanding model input formats.

User:  
No, thank you. It is all I want to know for the moment.

Assistant:  
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
                    wait_time = 15  # Wait 15  seconds for rate limit
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
