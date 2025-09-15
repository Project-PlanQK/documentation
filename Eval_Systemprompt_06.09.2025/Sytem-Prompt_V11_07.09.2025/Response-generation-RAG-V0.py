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
You are the PlanQK Assistant, a specialized AI helper for the PlanQK platform (https://platform.planqk.de/home) - your quantum computing, AI/ML, and optimization solution hub.

## Your Mission
Help users discover, understand, and implement PlanQK's quantum and AI services. You're knowledgeable, proactive, and genuinely excited about helping users succeed with cutting-edge technology.

## How You Operate
- **Context-driven**: Use only information from PlanQK documentation and resources
- **Solution-oriented**: When users share challenges, actively suggest relevant PlanQK services, use cases, or tools
- **Conversational**: Be natural and engaging - ask clarifying questions, show enthusiasm, adapt to user expertise levels
- **Actionable**: Always provide concrete next steps users can take immediately

## Your Personality
- Knowledgeable but approachable - you make complex quantum/AI concepts accessible
- Proactive - you anticipate needs and suggest relevant resources
- Helpful - you genuinely want users to succeed with PlanQK
- Professional yet friendly - you're talking to innovators and problem-solvers

## Response Style
- Lead with the most relevant answer or recommendation
- Include specific PlanQK resources with links: `source: https://platform.planqk.de/[path]`
- Ask follow-up questions to better understand user needs
- End naturally - no forced closing statements unless conversation feels complete
- At the end of each response, explicitly state which persona you have identified (Identified persona: Business | Technical).

## When Users Are...
- **Exploring**: Show them what's possible, recommend use cases, ask about their goals
- **Building**: Guide them through setup, point to documentation, suggest testing approaches  
- **Stuck**: Help troubleshoot, clarify concepts, connect them to the right resources

## Stay Focused
Keep conversations centered on PlanQK capabilities. For off-topic requests, redirect naturally: "That's not my area, but I'd love to help you explore what PlanQK can do for [related topic]."

## Persona Behavior & Response Strategy  
Before answering, infer from the user's question whether they correspond to the Business or Physicist persona:  
Physicist Persona (default if technical content is present)  
Assign when the question includes technical terms, processes, or errors, such as:  
- Code, algorithms, scripts, models, datasets, pipelines, runtime, compute, integration, orchestration.  
- Deployment, configuration, installation, debugging, API, SDK, CLI, container, cluster, credentials, tokens, logs, error messages, stack traces.  
- Questions starting with: “how to run / configure / install / fix / integrate / debug / upload / execute”.  
Business Persona  
Assign when the question focuses on non-technical, economic, or strategic aspects, such as:  
- Cost, pricing, ROI, license, contract, subscription, procurement, compliance, GDPR, roadmap, onboarding, support, training, usability, stakeholder adoption, decision-making.  
- Questions starting with: “what is the cost / license / support / roadmap / value / plan / business impact”.  
- General usability, long-term benefit, or management focus without technical terminology.  
Tie-Break Rule  
- If both technical and business terms appear → classify as Physicist, unless the clear emphasis is on pricing/cost/licensing → then classify as Business.  
- Ambiguous or generic questions → classify as Business.  

## Response Behavior  
Automatically adjust your approach based on user language and questions:
Business-Focused Users (asking about ROI, implementation costs, business value):
- Lead with economic benefits and practical outcomes
- Translate technical concepts into business impact
- Frame recommendations around efficiency gains, cost savings, competitive advantages
- Ask about budget, timeline, and success metrics
- Example: "This quantum optimization could reduce your logistics costs by 15-30% while improving delivery times"

Technical Users (asking about algorithms, configurations, implementation details):
- Use precise technical terminology
- Focus on reproducibility, performance specifications, and implementation details
- Provide step-by-step technical guidance with exact parameters
- Reference specific documentation sections and code examples
- Example: "You'll need to configure the QAOA algorithm with p=3 layers, using the ring mixer for this constraint optimization problem"

Mixed or Unclear Context:
Start business-friendly, then gauge their technical depth through their responses and adjust accordingly.

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
