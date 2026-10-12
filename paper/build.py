"""Assemble the paper (M3.6) into paper/paper.md and fill [placeholders] from reports/*.json.

    python paper/build.py

Sections come from paper/sections/*.md plus Member 2's paper/pipeline_section.md (included
as-is, one heading level down). Each member edits their own source file; re-run this script
to rebuild. Placeholders whose report doesn't exist yet are left as [name] and listed at the end.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
REPORTS = ROOT / "reports"
CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]

ORDER = [
    "sections/00_front.md",
    "sections/01_introduction.md",
    "sections/02_related_work.md",
    "sections/03_dataset.md",
    "sections/04_models.md",
    "pipeline_section.md",  # Member 2
    "sections/06_dashboard.md",
    "sections/07_results.md",
    "sections/08_limitations.md",
    "sections/09_conclusion.md",
]
DEMOTE = {"pipeline_section.md"}  # written with a top-level "#" title
PLACEHOLDER = re.compile(r"\[((?:table:)?[a-z][a-z0-9_]*)\]")


# ---------- formatting ----------

def pct(v, digits=1):
    return f"{100 * v:.{digits}f}%"


def ms(v):
    return f"{v:,.3f}" if v < 10 else f"{v:,.1f}"


def md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def load(name):
    path = REPORTS / name
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except json.JSONDecodeError:
        print(f"warning: {path} is not valid JSON")
        return None


def first(d, *names):
    """First numeric value whose key matches one of `names` (case-insensitive), or None."""
    for k, v in (d or {}).items():
        if str(k).lower() in names and isinstance(v, (int, float)):
            return v
    return None


def key_with(d, *words):
    """First numeric value whose key contains every word in `words`."""
    for k, v in (d or {}).items():
        if all(w in str(k).lower() for w in words) and isinstance(v, (int, float)):
            return v
    return None


def class_dict(d):
    if not isinstance(d, dict):
        return None
    if sum(k in CLASSES for k in d) >= 3:
        return d
    for v in d.values():
        found = class_dict(v)
        if found:
            return found
    return None


# ---------- values from each report ----------

def from_pipeline(values):
    lat = load("pipeline_latency.json")
    if not lat:
        return
    for src, name in (("detect_ms", "detect_ms"), ("explain_ms", "explain_ms"), ("e2e_ms_per_window", "e2e_ms")):
        for q in ("p50", "p95"):
            if lat.get(src, {}).get(q) is not None:
                values[f"{q}_{name}"] = ms(lat[src][q])
    rows = []
    for state, s in lat.get("by_state", {}).items():
        for col in ("scored", "explained"):
            if s.get(f"pct_{col}") is not None:
                values[f"pct_{col}_{state.lower()}"] = f"{s[f'pct_{col}']:.1f}"
        rows.append([state, f"{s.get('windows', 0):,}", f"{s.get('flows', 0):,}",
                     f"{s.get('pct_scored', 0):.1f}%", f"{s.get('pct_explained', 0):.1f}%"])
    if rows:
        values["table:tiering"] = md_table(["State", "Windows", "Flows", "Scored", "Explained"], rows)


def from_results(values):
    data = load("results.json")
    if not isinstance(data, dict):
        return
    models = {"lgbm": data} if any(isinstance(v, (int, float)) for v in data.values()) else data
    per_class = {}
    for name, d in models.items():
        if not isinstance(d, dict):
            continue
        short = "rf" if "rf" in name.lower() or "forest" in name.lower() else "lgbm"
        f1 = key_with(d, "macro", "f1")
        fpr = key_with(d, "fpr")
        if f1 is not None:
            values[f"{short}_macro_f1"] = f"{f1:.3f}"
        if fpr is not None:
            values[f"{short}_benign_fpr"] = pct(fpr, 2)
        cd = class_dict(d) or {}
        per_class[short] = {c: (first(v, "f1", "f1-score", "f1_score") if isinstance(v, dict) else v)
                            for c, v in cd.items()}
    if per_class:
        cols = [m for m in ("lgbm", "rf") if m in per_class]
        names = {"lgbm": "LightGBM", "rf": "Random Forest"}
        rows = [[c] + [f"{per_class[m][c]:.3f}" if isinstance(per_class[m].get(c), (int, float)) else "–"
                       for m in cols] for c in CLASSES if any(c in per_class[m] for m in cols)]
        values["table:per_class_f1"] = md_table(["Class"] + [names[m] for m in cols], rows)


def from_holdout(values):
    data = load("holdout.json")
    if not isinstance(data, dict):
        return
    rows = []
    for cls, d in data.items():
        if not isinstance(d, dict):
            continue
        lg, iff, either = key_with(d, "lgbm"), key_with(d, "iforest"), key_with(d, "either")
        rows.append([cls] + [pct(v) if v is not None else "–" for v in (lg, iff, either)])
        if "holdout_class" not in values:  # the first class goes in the abstract
            values["holdout_class"] = cls
            for key, v in (("lgbm", lg), ("iforest", iff), ("either", either)):
                if v is not None:
                    values[f"holdout_{key}_recall"] = pct(v)
    if rows:
        values["table:holdout"] = md_table(["Held-out class", "LightGBM alone", "Isolation Forest alone", "Either"], rows)


def from_benchmark(values):
    data = load("explain_benchmark.json")
    if not isinstance(data, dict):
        return
    methods = {}
    for k, v in data.items():
        if isinstance(v, dict) and ("tree" in k.lower() or "kernel" in k.lower()):
            methods["tree" if "tree" in k.lower() else "kernel"] = v
    rows = []
    for key, label in (("tree", "TreeSHAP"), ("kernel", "Kernel SHAP")):
        d = methods.get(key)
        if not d:
            continue
        mean = first(d, "mean", "mean_ms")
        p50 = first(d, "p50", "median", "p50_ms", "median_ms")
        p95 = first(d, "p95", "p95_ms")
        n = first(d, "n", "flows", "n_flows")
        if p50 is not None:
            values[f"{key}_p50"] = ms(p50)
        rows.append([label] + [ms(v) if v is not None else "–" for v in (mean, p50, p95)]
                    + [f"{int(n):,}" if n is not None else "–"])
    if rows:
        values["table:shap_benchmark"] = md_table(["Explainer", "Mean", "p50", "p95", "Flows"], rows)
    t, k = methods.get("tree", {}), methods.get("kernel", {})
    t50 = first(t, "p50", "median", "p50_ms", "median_ms") or first(t, "mean", "mean_ms")
    k50 = first(k, "p50", "median", "p50_ms", "median_ms") or first(k, "mean", "mean_ms")
    if t50 and k50:
        values["shap_speedup"] = f"{k50 / t50:,.0f}"


# ---------- assemble ----------

def demote(text):
    return re.sub(r"^(#+) ", r"#\1 ", text, flags=re.M)


def main():
    values = {}
    for fill in (from_pipeline, from_results, from_holdout, from_benchmark):
        fill(values)

    parts = []
    for rel in ORDER:
        path = PAPER / rel
        if not path.exists():
            print(f"warning: missing {rel}")
            continue
        text = path.read_text(encoding="utf-8").strip()
        parts.append(demote(text) if rel in DEMOTE else text)
    paper = "\n\n".join(parts) + "\n"

    paper = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), paper)
    paper = re.sub(r"<!--.*?-->\n?", "", paper, flags=re.S)  # notes to the team stay in the sources
    banner = ("<!-- GENERATED by paper/build.py from paper/sections/*.md and paper/pipeline_section.md. "
              "Edit those files, not this one. -->\n\n")
    (PAPER / "paper.md").write_text(banner + paper, encoding="utf-8")

    missing = sorted(set(PLACEHOLDER.findall(paper)))
    print(f"wrote paper/paper.md ({len(paper.split()):,} words), filled {len(values)} values")
    if missing:
        print(f"{len(missing)} placeholders still open: {', '.join(missing)}")


if __name__ == "__main__":
    main()
