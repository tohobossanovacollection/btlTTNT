from pathlib import Path
import sys
import time

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.reasoning_service import run_reasoning_retrieval


def main():
    question = (
        "Thuế thu nhập cá nhân áp dụng cho lương và thu nhập khác; ví dụ: "
        "lương 10.000.000 đồng, cách tính thế nào?"
    )

    print("Settings:", "RAG_TOP_K=", settings.RAG_TOP_K, "RAT_STEP_TOP_K=", settings.RAT_STEP_TOP_K)

    t0 = time.time()
    result = run_reasoning_retrieval(question)
    t1 = time.time()

    print("Mode:", result.get("mode"))
    print("Elapsed (s):", round(t1 - t0, 3))

    evidence = result.get("evidence") or []
    print("Evidence returned:", len(evidence))
    for i, ev in enumerate(evidence, start=1):
        name = ev.get("law_name") or "<unknown>"
        article = ev.get("article") or ""
        score = ev.get("_final_score")
        print(f"{i}. {name} {article} score={score}")


if __name__ == "__main__":
    main()
