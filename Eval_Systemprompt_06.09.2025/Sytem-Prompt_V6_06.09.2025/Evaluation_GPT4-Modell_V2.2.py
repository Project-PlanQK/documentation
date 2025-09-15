import json
import pandas as pd
import os
from llama_index.llms.openai import OpenAI
from llama_index.core.evaluation import (
    CorrectnessEvaluator,
    RelevancyEvaluator,
    FaithfulnessEvaluator
)
from dotenv import load_dotenv
load_dotenv()


api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
        raise SystemExit("OPENAI_API_KEY env var not set. Provide via .env or environment.")
    
eval_model = "gpt-4o"  # or your chosen model

llm = OpenAI(
    api_key=api_key,
    model=eval_model,
)

# Initialize evaluators for each metric
correctness_evaluator = CorrectnessEvaluator(llm=llm)
relevance_evaluator = RelevancyEvaluator(llm=llm)
faithfulness_evaluator = FaithfulnessEvaluator(llm=llm)

with open("V2_RAG_Eval_with_responses.json", "r", encoding="utf-8") as f:
    data = json.load(f)["examples"]

# Limit to first 5 inputs for testing
data = data[:40]

results = []

for idx, ex in enumerate(data):
    query = ex["query"]
    response = ex.get("response", "")
    reference = ex.get("reference_answer", "")
    print(f"{idx+1}/{len(data)}: Evaluating...")

    # Helper for cleaner code
    def safe_eval(evaluator, **kwargs):
        try:
            result = evaluator.evaluate(**kwargs)
            # Handle different result types
            if hasattr(result, 'score'):
                score = result.score
                # Ensure score is a reasonable number
                if score is not None and (score < 0 or score > 10):
                    print(f"Warning: Unusual score {score}, setting to None")
                    return None
                return score
            elif hasattr(result, 'passing'):
                return 1.0 if result.passing else 0.0
            else:
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    # Create dummy contexts since we don't have retrieval contexts
    dummy_contexts = [response] if response else [""]
    
    correctness_score = safe_eval(correctness_evaluator, query=query, response=response, contexts=dummy_contexts, reference=reference) if reference else None
    relevance_score = safe_eval(relevance_evaluator, query=query, response=response, contexts=dummy_contexts)
    faithfulness_score = safe_eval(faithfulness_evaluator, query=query, response=response, contexts=dummy_contexts)
    
    print(f"  Scores - Correctness: {correctness_score}, Relevance: {relevance_score}, Faithfulness: {faithfulness_score}")
    
    results.append({
        "index": idx + 1,
        "question": query,
        "response": response,
        "reference_answer": reference,
        "correctness_score": correctness_score,
        "relevance_score": relevance_score,
        "faithfulness_score": faithfulness_score,
    })

df = pd.DataFrame(results)

# Calculate summary statistics for all scores
score_columns = ['correctness_score', 'relevance_score', 'faithfulness_score']
summary_stats = {}

for col in score_columns:
    valid_scores = df[col].dropna()
    if len(valid_scores) > 0:
        summary_stats[f'{col}_mean'] = valid_scores.mean()
        summary_stats[f'{col}_std'] = valid_scores.std()
        summary_stats[f'{col}_min'] = valid_scores.min()
        summary_stats[f'{col}_max'] = valid_scores.max()
        summary_stats[f'{col}_count'] = len(valid_scores)

# Add overall average score - only for rows with valid scores
valid_score_cols = [col for col in score_columns if df[col].notna().any()]
if valid_score_cols:
    # Calculate row-wise mean only for non-null values
    df['overall_average_score'] = df[valid_score_cols].mean(axis=1, skipna=True)
    # Calculate overall mean, excluding NaN values
    overall_scores = df['overall_average_score'].dropna()
    if len(overall_scores) > 0:
        summary_stats['overall_average_mean'] = overall_scores.mean()
        summary_stats['overall_average_std'] = overall_scores.std()
        summary_stats['overall_average_count'] = len(overall_scores)

# Save detailed results with semicolon separator for Excel
df.to_csv("evaluation_results_detailed.csv", index=False, sep=';', encoding='utf-8-sig')

# Save summary statistics with semicolon separator for Excel
summary_df = pd.DataFrame([summary_stats])
summary_df.to_csv("evaluation_summary_stats.csv", index=False, sep=';', encoding='utf-8-sig')

print(f"Evaluation finished!")
print(f"Detailed results saved as evaluation_results_detailed.csv")
print(f"Summary statistics saved as evaluation_summary_stats.csv")
print(f"\nQuick Summary:")
for col in score_columns:
    if f'{col}_mean' in summary_stats:
        print(f"{col}: {summary_stats[f'{col}_mean']:.3f} ± {summary_stats[f'{col}_std']:.3f}")

# ---------------- ADD-ON: Kurzbegründungen pro Metrik speichern ----------------
from typing import Optional

print("[ADD-ON] Starte Feedback-Erzeugung…")
print("[ADD-ON] CWD:", os.getcwd())

def _extract_textual_feedback(result_obj) -> Optional[str]:
    """
    Versucht, eine knappe Begründung/Erklärung aus dem Evaluator-Result zu lesen.
    Fällt auf generische Texte zurück, wenn nichts vorhanden ist.
    """
    if result_obj is None:
        return "no evaluation possible"

    # Kandidatenfelder (je nach LlamaIndex-Version):
    for attr in ("feedback", "reason", "explanation", "details", "message", "raw_response"):
        if hasattr(result_obj, attr):
            val = getattr(result_obj, attr)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # Manche Implementationen legen Begründungen in einer metadata-Dict ab
    if hasattr(result_obj, "metadata") and isinstance(result_obj.metadata, dict):
        for k in ("feedback", "reason", "explanation"):
            val = result_obj.metadata.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()

    # Als Fallback eine knappe Aussage basierend auf passing/score
    parts = []
    if hasattr(result_obj, "passing"):
        parts.append("passed" if result_obj.passing else "not passed")
    if hasattr(result_obj, "score") and result_obj.score is not None:
        parts.append(f"score={result_obj.score}")
    if parts:
        return ", ".join(parts)

    return "no feedback available from evaluator"

def _eval_with_feedback(evaluator, **kwargs):
    """
    Führt evaluator.evaluate() aus und gibt (score, feedback_text) zurück.
    Bricht kontrolliert auf 'no evaluation possible' herunter, falls Fehler auftreten.
    """
    try:
        res = evaluator.evaluate(**kwargs)
        # Score holen (falls vorhanden/valide)
        score = getattr(res, "score", None)
        if score is not None and (score < 0 or score > 10):
            # Ungewöhnliche Skala -> belasse Feedback, setze Score auf None
            score = None
        feedback = _extract_textual_feedback(res)
        # Kürzen für CSV-Übersichtlichkeit (optional)
        if isinstance(feedback, str) and len(feedback) > 500:
            feedback = feedback[:500] + " ..."
        return score, feedback
    except Exception as e:
        print(f"[ADD-ON] Evaluationsfehler: {type(e).__name__}: {e}")
        return None, "no evaluation possible"

# Zusätzliche Evaluatoren nur für das Feedback, falls 'provide_feedback' unterstützt wird
def _mk_eval_with_feedback(cls):
    try:
        return cls(llm=llm, provide_feedback=True)  # neuere LlamaIndex-Versionen
    except TypeError:
        return cls(llm=llm)  # Fallback

correctness_evaluator_fb  = _mk_eval_with_feedback(CorrectnessEvaluator)
relevance_evaluator_fb    = _mk_eval_with_feedback(RelevancyEvaluator)
faithfulness_evaluator_fb = _mk_eval_with_feedback(FaithfulnessEvaluator)

# Auf Basis der bereits erzeugten df (mit question/response/reference_answer)
# führen wir eine zweite Evaluationsrunde nur für Feedback durch.
feedback_rows = []
total_rows = len(df)
print(f"[ADD-ON] Erzeuge Feedback für {total_rows} Zeilen...")

for i, row in df.reset_index(drop=True).iterrows():
    q = row.get("question", "")
    resp = row.get("response", "")
    ref = row.get("reference_answer", "")
    ctx = [resp] if isinstance(resp, str) and resp else [""]

    # Correctness nur ausführen, wenn Referenz vorhanden
    if isinstance(ref, str) and ref.strip():
        c_score_fb, c_fb = _eval_with_feedback(
            correctness_evaluator_fb,
            query=q, response=resp, contexts=ctx, reference=ref
        )
    else:
        c_fb = "no evaluation possible"
        c_score_fb = None

    r_score_fb, r_fb = _eval_with_feedback(
        relevance_evaluator_fb,
        query=q, response=resp, contexts=ctx
    )

    f_score_fb, f_fb = _eval_with_feedback(
        faithfulness_evaluator_fb,
        query=q, response=resp, contexts=ctx
    )

    feedback_rows.append({
        "correctness_feedback": c_fb,
        "relevance_feedback": r_fb,
        "faithfulness_feedback": f_fb,
    })

    if (i + 1) % 10 == 0 or (i + 1) == total_rows:
        print(f"[ADD-ON] Fortschritt: {i + 1}/{total_rows}")

df_feedback = pd.DataFrame(feedback_rows)

# Zusammenführen: Original df + Feedback-Spalten (Scores bleiben unverändert)
df_with_feedback = pd.concat([df.reset_index(drop=True), df_feedback], axis=1)

# Separate Datei schreiben (damit deine bisherigen Exporte unberührt bleiben)
outfile = os.path.abspath("evaluation_results_with_feedback.csv")
df_with_feedback.to_csv(
    outfile,
    index=False, sep=';', encoding='utf-8-sig'
)

print(f"[ADD-ON] Fertig. Feedback-Datei geschrieben: {outfile}")
# ---------------- END ADD-ON ----------------
