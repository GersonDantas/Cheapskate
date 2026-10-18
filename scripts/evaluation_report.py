"""Report only eligible, human-reviewed pairs as token comparisons."""

import argparse
import json
from pathlib import Path


def comparison(before, after, review=None):
    reasons = []
    if any(item.get("status") != "completed" for item in (before, after)):
        reasons.append("incomplete_pair")
    models = before.get("observed_models", [])
    if len(models) != 1 or models != after.get("observed_models", []):
        reasons.append("resolved_model_unconfirmed_or_different")
    for key in ("host", "client_version", "model_requested", "effort_requested", "prompt_sha256", "scope"):
        if before.get(key) is None or before.get(key) != after.get(key):
            reasons.append("different_" + key)
    totals = [(item.get("usage") or {}).get("total") for item in (before, after)]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in totals):
        reasons.append("usage_unavailable")
    elif totals[0] == 0:
        reasons.append("zero_baseline")
    if any(item.get("tool_calls_observed") for item in (before, after)):
        reasons.append("tools_used_in_text_scenario")
    if any(item.get("text_scope_confirmed") is not True for item in (before, after)):
        reasons.append("text_scope_unconfirmed")
    reviewed = bool(review and review.get("status") == "passed"
                    and review.get("before_answer_sha256") == before.get("answer_sha256")
                    and review.get("after_answer_sha256") == after.get("answer_sha256")
                    and before.get("answer_sha256") and after.get("answer_sha256"))
    if not reviewed:
        reasons.append("quality_pending_or_invalid_review")
    eligible = not reasons
    return {"eligible": eligible, "reasons": reasons,
            "before_total_tokens": totals[0], "after_total_tokens": totals[1],
            "token_reduction_percent": round(100 * (totals[0] - totals[1]) / totals[0], 2)
            if eligible and totals[0] else None}


def generate(run_root):
    run_root = Path(run_root)
    reviews_path = run_root / "reviews.json"
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else {}
    pairs = []
    for pair_path in sorted(run_root.glob("*/*/*/pair-run.json")):
        record = json.loads(pair_path.read_text())
        host = record["host"]
        arms = []
        for label in ("before", "after"):
            path = pair_path.parent / f"{host}-{label}-metrics.json"
            arms.append(json.loads(path.read_text()) if path.exists() else {"status": "missing"})
        key = f"{record['case']}/{record['repetition']}/{host}"
        pairs.append({"case": record["case"], "host": host, "repetition": record["repetition"],
                      "status": record["status"], "arms": arms,
                      "comparison": comparison(*arms, reviews.get(key))})
    report = {"schema": 1, "scope": "text-instructions",
              "interpretation": "instrument_validation_not_representative_savings",
              "pair_count": len(pairs), "pairs": pairs,
              "client_executions_attempted": sum(bool(arm.get("client_inference_attempted"))
                                                 for pair in pairs for arm in pair["arms"])}
    (run_root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Relatório de avaliação textual", "", "Escopo: instruções e respostas, sem RTK ou grafos integrados.",
             "Os dados validam a coleta. Uma amostra pequena não demonstra economia representativa.", "",
             "| Caso | Cliente | Repetição | Estado | Tokens antes | Tokens depois | Comparação |",
             "|---|---|---:|---|---:|---:|---|"]
    for pair in pairs:
        result = pair["comparison"]
        outcome = (str(result["token_reduction_percent"]) + "%") if result["eligible"] else "Pendente: " + ", ".join(result["reasons"])
        values = [pair["case"], pair["host"], pair["repetition"], pair["status"],
                  result["before_total_tokens"], result["after_total_tokens"], outcome]
        lines.append("| " + " | ".join(str(value) if value is not None else "indisponível" for value in values) + " |")
    lines += ["", "Valores ausentes permanecem desconhecidos. Cache e custo informado pelo cliente não equivalem a cobrança verificada.",
              "A revisão humana deve validar os hashes das respostas antes de liberar uma comparação."]
    (run_root / "report.md").write_text("\n".join(lines) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    args = parser.parse_args()
    generate(args.run_root)
