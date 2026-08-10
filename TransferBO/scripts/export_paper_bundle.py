#!/usr/bin/env python
"""Export a paper / report-ready bundle of curated tables and freeze artifacts.

Safe to re-run; overwrites curated copies under exports/paper_bundle/.
Does not delete raw JSON grids.

Example:
  python scripts/export_paper_bundle.py
  python scripts/export_paper_bundle.py --stamp  # also write dated snapshot
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def copy_if(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    ensure(dst.parent)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def rebuild_heldout(out_root: Path) -> dict:
    """Aggregate whatever held-out JSONs exist (partial OK)."""
    rows = []
    for p in sorted(out_root.glob("*.json")):
        if p.name.startswith("summary") or p.name.startswith("gate_"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        meta = d.get("meta") or {}
        gb = d.get("global_best")
        bf = d.get("best_final")
        rows.append(
            {
                "source_plate": d.get("source_plate"),
                "target_plate": d.get("target_plate"),
                "strategy": d.get("strategy"),
                "representation": d.get("representation"),
                "seed": d.get("seed"),
                "frac_of_opt": (bf / gb) if gb and bf is not None else None,
                "best_final": bf,
                "global_best": gb,
                "queries_to_top5": (d.get("metrics") or {}).get("queries_to_top5"),
                "queries_to_top1": (d.get("metrics") or {}).get("queries_to_top1"),
                "gate_mode": meta.get("gate_mode"),
                "gate_strategy": meta.get("gate_strategy"),
                "gate_score": meta.get("gate_score"),
                "gate_reason": meta.get("gate_reason"),
                "delegated_strategy": meta.get("delegated_strategy"),
            }
        )
    info = {"n_json": len(rows), "complete": False}
    if not rows:
        return info
    df = pd.DataFrame(rows)
    df.to_csv(out_root / "heldout_results.csv", index=False)

    summary = (
        df.groupby(["strategy", "representation", "source_plate"], dropna=False)
        .agg(
            frac_mean=("frac_of_opt", "mean"),
            frac_std=("frac_of_opt", "std"),
            q5_median=("queries_to_top5", "median"),
            n=("frac_of_opt", "count"),
        )
        .reset_index()
    )
    summary.to_csv(out_root / "heldout_summary.csv", index=False)

    g = df[df["strategy"] == "transfer_gate"]
    if not g.empty:
        g["gate_mode"].value_counts(dropna=False).rename("count").to_csv(
            out_root / "gate_mode_counts.csv"
        )
        # per source mode distribution
        (
            g.groupby(["source_plate", "gate_mode"])
            .size()
            .rename("count")
            .reset_index()
            .to_csv(out_root / "gate_mode_by_source.csv", index=False)
        )

    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby("representation")["frac_of_opt"]
        .mean()
    )
    cmp_rows = []
    for strat in ["diversity_warm", "label_warm", "multitask", "transfer_gate"]:
        sub = df[df["strategy"] == strat]
        if sub.empty:
            continue
        for (rep, src), gmean in (
            sub.groupby(["representation", "source_plate"])["frac_of_opt"].mean().items()
        ):
            c = cold.get(rep, float("nan"))
            cmp_rows.append(
                {
                    "strategy": strat,
                    "representation": rep,
                    "source_plate": src,
                    "frac_mean": gmean,
                    "cold_frac": c,
                    "delta_vs_cold": gmean - c if pd.notna(c) else None,
                    "n": int(
                        sub[
                            (sub["representation"] == rep) & (sub["source_plate"] == src)
                        ].shape[0]
                    ),
                }
            )
    if cmp_rows:
        pd.DataFrame(cmp_rows).to_csv(out_root / "gate_vs_baselines.csv", index=False)

    # negative-transfer counts vs cold (seed-level): frac < cold_mean - 0? use seed paired if possible
    # simpler: mean delta < 0 counts as negative pair
    if cmp_rows:
        cmp = pd.DataFrame(cmp_rows)
        neg = (
            cmp.assign(is_neg=cmp["delta_vs_cold"] < -0.02)
            .groupby("strategy")["is_neg"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "n_neg_pairs", "count": "n_pairs"})
        )
        neg.to_csv(out_root / "neg_transfer_pairs.csv", index=False)

    expected = 260  # morgan held-out design
    info["complete"] = len(rows) >= expected
    info["n_by_strategy"] = df["strategy"].value_counts().to_dict()
    info["expected"] = expected
    return info


def write_leaderboard(bundle: Path, heldout_info: dict) -> None:
    lines = [
        "# TransferBO leaderboard (curated)",
        "",
        f"Exported: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Development fold (plates 1–3) — transfer vs cold",
        "",
        "Source: `tables/transfer_delta20_summary.csv`",
        "",
    ]
    delta_path = ROOT / "results/transfer_grid/transfer_delta20_summary.csv"
    if delta_path.exists():
        d = pd.read_csv(delta_path)
        # overall by strategy
        ov = (
            d.groupby("strategy")
            .agg(delta_mean=("delta_mean", "mean"), frac_mean=("frac_mean", "mean"), n=("n", "sum"))
            .reset_index()
            .sort_values("delta_mean", ascending=False)
        )
        lines.append("| strategy | mean Δfrac vs cold | mean frac | n_cells×seeds |")
        lines.append("|---|---:|---:|---:|")
        for _, r in ov.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['delta_mean']:.3f} | {r['frac_mean']:.3f} | {int(r['n'])} |"
            )
        lines.append("")
        # strongest + / -
        best = d.loc[d["delta_mean"].idxmax()]
        worst = d.loc[d["delta_mean"].idxmin()]
        lines.append(
            f"- Strongest positive: `{best['strategy']}` {best['source']}→{best['target']} "
            f"{best['rep']} Δ={best['delta_mean']:.3f}"
        )
        lines.append(
            f"- Strongest negative: `{worst['strategy']}` {worst['source']}→{worst['target']} "
            f"{worst['rep']} Δ={worst['delta_mean']:.3f}"
        )
        lines.append("")

    lines += [
        "## Held-out plate_4 (frozen Gate eval)",
        "",
        f"Status: {'COMPLETE' if heldout_info.get('complete') else 'PARTIAL'} "
        f"({heldout_info.get('n_json', 0)}/{heldout_info.get('expected', '?')} JSON)",
        "",
    ]
    vs = bundle / "tables" / "heldout_gate_vs_baselines.csv"
    if vs.exists():
        h = pd.read_csv(vs)
        lines.append("| strategy | source | mean frac | Δ vs cold | n |")
        lines.append("|---|---|---:|---:|---:|")
        for _, r in h.sort_values(["strategy", "source_plate"]).iterrows():
            lines.append(
                f"| {r['strategy']} | {r['source_plate']} | {r['frac_mean']:.3f} | "
                f"{r['delta_vs_cold']:.3f} | {int(r['n'])} |"
            )
        lines.append("")
    neg = bundle / "tables" / "heldout_neg_transfer_pairs.csv"
    if neg.exists():
        lines.append("Negative pairs (mean Δfrac < −0.02):")
        lines.append("")
        neg_df = pd.read_csv(neg)
        try:
            lines.append(neg_df.to_markdown(index=False))
        except Exception:
            lines.append(neg_df.to_string(index=False))
        lines.append("")

    base = ROOT / "results/baseline/suite/baseline_20seeds_summary.csv"
    if base.exists():
        lines += ["## Single-plate baselines (dev)", "", f"See `tables/baseline_20seeds_summary.csv`", ""]

    (bundle / "LEADERBOARD.md").write_text("\n".join(lines), encoding="utf-8")


def try_heatmaps(bundle: Path) -> None:
    """Optional PNG heatmaps for slides."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        (bundle / "figs" / "README.txt").write_text(
            f"matplotlib unavailable ({e}); CSVs only.\n", encoding="utf-8"
        )
        return

    fig_dir = ensure(bundle / "figs")
    delta = ROOT / "results/transfer_grid/transfer_delta20_summary.csv"
    if not delta.exists():
        return
    df = pd.read_csv(delta)
    for (strat, rep), g in df.groupby(["strategy", "rep"]):
        plates = sorted(set(g["source"]) | set(g["target"]))
        mat = pd.DataFrame(index=plates, columns=plates, dtype=float)
        for _, r in g.iterrows():
            mat.loc[r["source"], r["target"]] = r["delta_mean"]
        fig, ax = plt.subplots(figsize=(4.2, 3.6))
        data = mat.to_numpy(dtype=float)
        im = ax.imshow(data, cmap="RdBu_r", vmin=-0.4, vmax=0.4)
        ax.set_xticks(range(len(plates)))
        ax.set_yticks(range(len(plates)))
        ax.set_xticklabels(plates, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(plates, fontsize=8)
        ax.set_xlabel("target")
        ax.set_ylabel("source")
        ax.set_title(f"Δfrac vs cold\n{strat} / {rep}", fontsize=10)
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                v = data[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(fig_dir / f"heatmap_delta20_{strat}_{rep}.png", dpi=160)
        plt.close(fig)

    # held-out bar if available
    vs = bundle / "tables" / "heldout_gate_vs_baselines.csv"
    if vs.exists():
        h = pd.read_csv(vs)
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        labels = [f"{r.strategy}\n{r.source_plate}" for r in h.itertuples()]
        ax.bar(range(len(h)), h["delta_vs_cold"], color=["#c44e52" if v < 0 else "#4c72b0" for v in h["delta_vs_cold"]])
        ax.axhline(0, color="k", lw=0.8)
        ax.set_xticks(range(len(h)))
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
        ax.set_ylabel("Δ frac_of_opt vs cold")
        ax.set_title("Held-out plate_4 (morgan)")
        fig.tight_layout()
        fig.savefig(fig_dir / "heldout_delta_vs_cold.png", dpi=160)
        plt.close(fig)


def write_manifest(bundle: Path, heldout_info: dict) -> None:
    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "project": "TransferBO / TransferGate",
        "protocol": "configs/protocol.yaml",
        "held_out_target": "plate_4",
        "dev_targets": ["plate_1", "plate_2", "plate_3"],
        "main_acquisition": "ei",
        "main_budget": 100,
        "main_n_init": 20,
        "n_seeds": 20,
        "max_warm_points": 150,
        "heldout_status": heldout_info,
        "paper_figure_map": {
            "Fig2_baselines": "tables/baseline_20seeds_summary.csv",
            "Fig3_transfer_heatmaps": "figs/heatmap_delta20_*.png + tables/heatmap_delta20_*.csv",
            "Fig4_what_to_transfer": "tables/transfer_delta20_summary.csv",
            "Fig5_gate_calibration": "tables/gate_train.csv + freeze_W8/",
            "Fig6_neg_transfer": "tables/heldout_neg_transfer_pairs.csv",
            "Gate_freeze": "freeze_W8/",
        },
        "raw_roots_do_not_delete": [
            "results/baseline/",
            "results/transfer_grid/",
            "results/gate/heldout_P4/",
            "results/gate/freeze_W8/",
            "data/processed/additives_four_plates.csv",
        ],
    }
    (bundle / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "exports" / "paper_bundle")
    ap.add_argument("--stamp", action="store_true", help="Also copy to dated snapshot folder")
    args = ap.parse_args()

    bundle = ensure(args.out)
    tables = ensure(bundle / "tables")
    configs = ensure(bundle / "configs")
    notes = ensure(bundle / "notes")
    freeze = ensure(bundle / "freeze_W8")
    meta = ensure(bundle / "meta")

    # Rebuild held-out aggregates from raw JSON (partial-safe)
    held_root = ROOT / "results/gate/heldout_P4"
    heldout_info = {"n_json": 0}
    if held_root.exists():
        heldout_info = rebuild_heldout(held_root)

    # Curated table copies
    copies = [
        (ROOT / "results/transfer_grid/grid_results.csv", tables / "transfer_grid_results.csv"),
        (ROOT / "results/transfer_grid/transfer_delta20_summary.csv", tables / "transfer_delta20_summary.csv"),
        (ROOT / "results/transfer_grid/transfer_delta_frac.csv", tables / "transfer_delta_frac.csv"),
        (ROOT / "results/transfer_grid/transfer_gain_queries.csv", tables / "transfer_gain_queries.csv"),
        (ROOT / "results/baseline/suite/baseline_20seeds_summary.csv", tables / "baseline_20seeds_summary.csv"),
        (ROOT / "results/baseline/suite/baseline_all_reps_summary.csv", tables / "baseline_all_reps_summary.csv"),
        (ROOT / "results/baseline/suite/init_mode_comparison.csv", tables / "init_mode_comparison.csv"),
        (ROOT / "results/baseline/suite/baseline_index.csv", tables / "baseline_index.csv"),
        (ROOT / "results/gate/train.csv", tables / "gate_train.csv"),
        (ROOT / "results/gate/heldout_P4/heldout_results.csv", tables / "heldout_results.csv"),
        (ROOT / "results/gate/heldout_P4/heldout_summary.csv", tables / "heldout_summary.csv"),
        (ROOT / "results/gate/heldout_P4/gate_vs_baselines.csv", tables / "heldout_gate_vs_baselines.csv"),
        (ROOT / "results/gate/heldout_P4/gate_mode_counts.csv", tables / "heldout_gate_mode_counts.csv"),
        (ROOT / "results/gate/heldout_P4/gate_mode_by_source.csv", tables / "heldout_gate_mode_by_source.csv"),
        (ROOT / "results/gate/heldout_P4/neg_transfer_pairs.csv", tables / "heldout_neg_transfer_pairs.csv"),
        (ROOT / "results/stats/transfer_dev_stats.csv", tables / "transfer_dev_stats.csv"),
        (ROOT / "results/stats/transfer_dev_overall.csv", tables / "transfer_dev_overall.csv"),
        (ROOT / "results/stats/si_ucb_vs_ei.csv", tables / "si_ucb_vs_ei.csv"),
        (ROOT / "results/stats/si_source_frac.csv", tables / "si_source_frac.csv"),
        (ROOT / "results/stats/si_budget50.csv", tables / "si_budget50.csv"),
        (ROOT / "results/stats/si_ninit10.csv", tables / "si_ninit10.csv"),
        (ROOT / "results/stats/STATS_REPORT.md", bundle / "STATS_REPORT.md"),
        (ROOT / "results/si/ucb_summary.csv", tables / "si_ucb_summary.csv"),
        (ROOT / "results/si/source_frac_summary.csv", tables / "si_source_frac_summary.csv"),
        (ROOT / "results/si/budget50_summary.csv", tables / "si_budget50_summary.csv"),
        (ROOT / "results/si/ninit10_summary.csv", tables / "si_ninit10_summary.csv"),
        (ROOT / "results/meta/data_card.md", meta / "data_card.md"),
        (ROOT / "configs/protocol.yaml", configs / "protocol.yaml"),
        (ROOT / "configs/default.yaml", configs / "default.yaml"),
        (ROOT / "configs/gate.yaml", configs / "gate.yaml"),
        (ROOT / "docs/详细执行方案.md", bundle / "详细执行方案.md"),
        (ROOT / "方向三-TransferBO纯计算方案.md", bundle / "方向三-TransferBO纯计算方案.md"),
    ]
    for src, dst in copies:
        copy_if(src, dst)

    # heatmaps csv
    for p in (ROOT / "results/transfer_grid").glob("heatmap_delta20_*.csv"):
        copy_if(p, tables / p.name)

    # notes
    for p in (ROOT / "notes").glob("*.md"):
        copy_if(p, notes / p.name)

    # freeze snapshot (model + meta; critical for reproducibility)
    freeze_src = ROOT / "results/gate/freeze_W8"
    if freeze_src.exists():
        for p in freeze_src.iterdir():
            copy_if(p, freeze / p.name)

    write_leaderboard(bundle, heldout_info)
    try_heatmaps(bundle)
    write_manifest(bundle, heldout_info)

    readme = f"""# Paper / report bundle

导出时间：{datetime.now().isoformat(timespec='seconds')}

本目录是**汇报/投稿用精选副本**，不替代原始实验结果。
原始大文件仍在 `results/`（请勿删）。

## 怎么用

| 需求 | 打开 |
|---|---|
| 一页数字总览 | `LEADERBOARD.md` |
| 画迁移热图 | `tables/transfer_delta20_summary.csv` 或 `figs/*.png` |
| 单板基线 | `tables/baseline_*.csv` |
| Gate 训练与冻结 | `tables/gate_train.csv` + `freeze_W8/` |
| Held-out P4 | `tables/heldout_*.csv`（可能 PARTIAL） |
| 协议锁死项 | `configs/protocol.yaml` |
| 数据说明 | `meta/data_card.md` |

## Held-out 状态

- JSON 数：{heldout_info.get('n_json')} / {heldout_info.get('expected', '?')}
- 完成：{heldout_info.get('complete')}
- 按策略：{heldout_info.get('n_by_strategy')}

Held-out 跑完后请再执行：

```bash
python scripts/export_paper_bundle.py --stamp
```

## 原始结果位置（备份清单）

- `results/baseline/suite/` — 单板基线
- `results/transfer_grid/` — W3 全网格 JSON + 汇总 CSV（840）
- `results/gate/freeze_W8/` — 冻结 Gate
- `results/gate/heldout_P4/` — P4 评测原始 JSON
- `data/processed/additives_four_plates.csv` — 四板数据
"""
    (bundle / "README.md").write_text(readme, encoding="utf-8")

    if args.stamp:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap = ROOT / "exports" / f"paper_bundle_{stamp}"
        if snap.exists():
            shutil.rmtree(snap)
        shutil.copytree(bundle, snap)
        print(f"Snapshot -> {snap}")

    print(f"Bundle -> {bundle}")
    print(f"Held-out: {heldout_info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
