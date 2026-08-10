#!/usr/bin/env python
"""Organize docs/ into manuscript / plans / archive / briefings; write README index."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# dest_subdir -> list of exact filenames currently in docs/
MOVES: dict[str, list[str]] = {
    "manuscript": [
        "manuscript_draft_DD_v0.6.md",
    ],
    "manuscript/archive": [
        "manuscript_draft_DD.md",
        "manuscript_draft_DD_v0.5.md",
        "manuscript_draft_DD.docx",
    ],
    "briefings": [
        "briefing_zh_EDBO_Suzuki_v0.6.docx",
    ],
    "plans": [
        "待处理事项.md",
        "行动方案_主线锁定.md",
        "行动方案_成稿收尾.md",
        "开题与任务定稿.md",
        "可复现性清单.md",
    ],
    "design": [
        "edbo_external_replication_design.md",
        "论文细纲-DigitalDiscovery.md",
        "详细执行方案.md",
        "改进细则-P1P2外部验证.md",
    ],
    "archive": [
        "计划-同库迁移.md",
        "汇报与成文材料清单.md",
        "评审修订回应.md",
    ],
}

# figs: keep all under figs/, but add main/ copies or moves of primary paper figs
MAIN_FIGS = [
    "fig1_same_library_transfer_schematic.png",
    "fig_edbo_suzuki_C1_pair_delta_by_budget.png",
    "fig_edbo_suzuki_C1_pair_delta_by_budget.pdf",
    "fig_edbo_suzuki_s0_vs_main_pair_delta.png",
    "fig_edbo_suzuki_s0_vs_main_pair_delta.pdf",
    "fig_edbo_suzuki_ladder_A1A2A3_B40.png",
    "fig_edbo_suzuki_ladder_A1A2A3_B40.pdf",
]


def resolve_by_stem(directory: Path, wanted: str) -> Path | None:
    """Find file even if console encoding is messy — match by exact name via Path.iterdir."""
    target = directory / wanted
    if target.exists():
        return target
    # fuzzy: match endswith for garbled CN briefing
    if wanted.startswith("本工作说明") or "EDBO_Suzuki_v0.6.docx" in wanted:
        for p in directory.glob("*EDBO_Suzuki_v0.6.docx"):
            if p.name != "briefing_zh_EDBO_Suzuki_v0.6.docx":
                return p
    return None


def move_file(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.resolve() == src.resolve():
        return dest
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return dest


def main() -> int:
    # 1) move top-level docs
    for sub, names in MOVES.items():
        dest_dir = DOCS / sub
        for name in names:
            src = resolve_by_stem(DOCS, name)
            if src is None:
                print("MISSING", name)
                continue
            dest = move_file(src, dest_dir)
            print("MOVE", src.name, "->", dest.relative_to(DOCS))

    # garbled CN briefing if still at root
    for p in DOCS.glob("*.docx"):
        if p.name.startswith("briefing"):
            continue
        if "EDBO_Suzuki" in p.name or p.stat().st_size > 200_000:
            # likely the CN duplicate
            if p.parent == DOCS:
                dest = move_file(p, DOCS / "briefings")
                # rename to clear Chinese name
                nice = DOCS / "briefings" / "本工作说明_EDBO_Suzuki_v0.6.docx"
                if dest != nice:
                    if nice.exists():
                        nice.unlink()
                    dest.rename(nice)
                    print("RENAME ->", nice.relative_to(DOCS))

    # 2) figs/main — move primary paper figures into figs/main (leave rest in figs/)
    figs = DOCS / "figs"
    main = figs / "main"
    main.mkdir(parents=True, exist_ok=True)
    for name in MAIN_FIGS:
        src = figs / name
        if src.exists():
            dest = move_file(src, main)
            print("FIG ", dest.relative_to(DOCS))

    # also keep fig1 v2 in archive figs if present
    arch_figs = figs / "archive_early"
    arch_figs.mkdir(parents=True, exist_ok=True)
    for name in [
        "fig1_same_library_transfer_v2.png",
        "fig3a_heatmap_label_morgan.png",
        "fig3b_heatmap_diversity_morgan.png",
        "fig3c_heatmap_label_drfp.png",
        "fig3d_heatmap_diversity_drfp.png",
        "fig3_chaos_heatmaps_morgan.png",
        "fig4_chaos_pair_forest_morgan.png",
        "fig5_doyle_pairs_and_targets.png",
        "fig5_doyle_target_bars.png",
        "fig6_heldout_gate.png",
    ]:
        src = figs / name
        if src.exists():
            move_file(src, arch_figs)
            print("ARCH", name)

    # 3) write README index
    readme = DOCS / "README.md"
    readme.write_text(
        """# docs/ 目录说明

整理日期：2026-08-07

## 快速入口

| 用途 | 路径 |
|---|---|
| **当前英文主稿 v0.6** | [`manuscript/manuscript_draft_DD_v0.6.md`](manuscript/manuscript_draft_DD_v0.6.md) |
| **中文工作说明 Word** | [`briefings/briefing_zh_EDBO_Suzuki_v0.6.docx`](briefings/briefing_zh_EDBO_Suzuki_v0.6.docx) |
| **待办** | [`plans/待处理事项.md`](plans/待处理事项.md) |
| **成稿收尾方案** | [`plans/行动方案_成稿收尾.md`](plans/行动方案_成稿收尾.md) |
| **主线锁定（A0–A3）** | [`plans/行动方案_主线锁定.md`](plans/行动方案_主线锁定.md) |
| **开题 / 任务定稿** | [`plans/开题与任务定稿.md`](plans/开题与任务定稿.md) |
| **可复现性清单** | [`plans/可复现性清单.md`](plans/可复现性清单.md) |
| **主张 / 数字 SSOT** | [`../results/paper_stats/FROZEN_CLAIMS.md`](../results/paper_stats/FROZEN_CLAIMS.md) · [`../results/paper_stats/EXPERIMENT_SUMMARY.md`](../results/paper_stats/EXPERIMENT_SUMMARY.md) |
| **主文图 Fig1–4** | [`figs/main/`](figs/main/) |
| **EDBO 其余图（ESI）** | [`figs/`](figs/)（`fig_edbo_suzuki_*`） |
| **早期 CHAOS/Doyle 图** | [`figs/archive_early/`](figs/archive_early/) |

## 目录结构

```text
docs/
  README.md                 ← 本索引
  manuscript/               ← 当前主稿
    archive/                ← v0.4c / v0.5 旧稿与旧 docx
  briefings/                ← 中文说明 Word
  plans/                    ← 行动方案、开题、可复现、待办
  design/                   ← EDBO 设计锁、细纲、执行方案
  archive/                  ← 过期计划 / 评审回应等
  figs/
    main/                   ← 主文 Fig1–4
    archive_early/          ← 早期编号图
    fig_edbo_suzuki_*       ← ESI / 补充图（留在 figs 根下）
```

## 图路径提示

v0.6 主稿中的相对路径原先为 `figs/...`（相对 `docs/`）。  
整理后主文图在 `figs/main/`；若预览断图，将链接改为 `figs/main/...`，或从 `manuscript/` 写作时使用 `../figs/main/...`。
""",
        encoding="utf-8",
    )
    print("WRITE", readme.relative_to(DOCS))

    # 4) fix links in moved active files
    replacements = [
        # from plans/*
        (
            DOCS / "plans" / "待处理事项.md",
            [
                ("`](行动方案_成稿收尾.md)`", "`](行动方案_成稿收尾.md)`"),  # same dir ok
                (
                    "`](manuscript_draft_DD_v0.6.md)`",
                    "`](../manuscript/manuscript_draft_DD_v0.6.md)`",
                ),
                ("`docs/figs/fig_edbo_suzuki_*`", "`docs/figs/` + `docs/figs/main/`"),
            ],
        ),
        (
            DOCS / "manuscript" / "manuscript_draft_DD_v0.6.md",
            [
                (
                    "[`manuscript_draft_DD_v0.5.md`](manuscript_draft_DD_v0.5.md)",
                    "[`manuscript_draft_DD_v0.5.md`](archive/manuscript_draft_DD_v0.5.md)",
                ),
                (
                    "[`行动方案_成稿收尾.md`](行动方案_成稿收尾.md)",
                    "[`行动方案_成稿收尾.md`](../plans/行动方案_成稿收尾.md)",
                ),
                ("(figs/", "(../figs/main/"),
                # ESI figs still in figs root — fix over-aggressive main/ for non-main
            ],
        ),
    ]

    # careful fig path fix for v0.6: only the four main figs go to main/
    ms = DOCS / "manuscript" / "manuscript_draft_DD_v0.6.md"
    if ms.exists():
        text = ms.read_text(encoding="utf-8")
        text = text.replace(
            "[`manuscript_draft_DD_v0.5.md`](manuscript_draft_DD_v0.5.md)",
            "[`manuscript_draft_DD_v0.5.md`](archive/manuscript_draft_DD_v0.5.md)",
        )
        text = text.replace(
            "[`行动方案_成稿收尾.md`](行动方案_成稿收尾.md)",
            "[`行动方案_成稿收尾.md`](../plans/行动方案_成稿收尾.md)",
        )
        # figure links: docs/manuscript -> ../figs/main/
        for stem in [
            "fig1_same_library_transfer_schematic.png",
            "fig_edbo_suzuki_C1_pair_delta_by_budget.png",
            "fig_edbo_suzuki_s0_vs_main_pair_delta.png",
            "fig_edbo_suzuki_ladder_A1A2A3_B40.png",
        ]:
            text = text.replace(f"(figs/{stem})", f"(../figs/main/{stem})")
            text = text.replace(f"`figs/{stem}`", f"`../figs/main/{stem}`")
        # figure map table at end
        text = text.replace("| 1 | `figs/", "| 1 | `../figs/main/")
        text = text.replace("| 2 | `figs/", "| 2 | `../figs/main/")
        text = text.replace("| 3 | `figs/", "| 3 | `../figs/main/")
        text = text.replace("| 4 | `figs/", "| 4 | `../figs/main/")
        text = text.replace(
            "- Figures: `docs/figs/fig_edbo_suzuki_*`, `fig1_same_library_transfer_schematic.png`",
            "- Figures: `docs/figs/main/` (Fig1–4); ESI: `docs/figs/fig_edbo_suzuki_*`",
        )
        text = text.replace(
            "**Figures:** `docs/figs/` (Fig. 1–4 mapped below).",
            "**Figures:** `docs/figs/main/` (Fig. 1–4); ESI under `docs/figs/`.",
        )
        ms.write_text(text, encoding="utf-8")
        print("PATCH", ms.relative_to(DOCS))

    todo = DOCS / "plans" / "待处理事项.md"
    if todo.exists():
        t = todo.read_text(encoding="utf-8")
        t = t.replace(
            "[`manuscript_draft_DD_v0.6.md`](manuscript_draft_DD_v0.6.md)",
            "[`manuscript_draft_DD_v0.6.md`](../manuscript/manuscript_draft_DD_v0.6.md)",
        )
        t = t.replace(
            "| Fig1–4 | `docs/figs/fig_edbo_suzuki_*` + schematic |",
            "| Fig1–4 | `docs/figs/main/` |",
        )
        # paper_stats links: from plans/ need ../../results
        t = t.replace("`](../results/paper_stats/", "`](../../results/paper_stats/")
        todo.write_text(t, encoding="utf-8")
        print("PATCH", todo.relative_to(DOCS))

    for plan in ["行动方案_成稿收尾.md", "行动方案_主线锁定.md", "开题与任务定稿.md", "可复现性清单.md"]:
        p = DOCS / "plans" / plan
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        t2 = t.replace("`](../results/paper_stats/", "`](../../results/paper_stats/")
        # cross-links among plans stay same-dir
        if "开题" in plan or "可复现" in plan:
            t2 = t2.replace(
                "`](edbo_external_replication_design.md)`",
                "`](../design/edbo_external_replication_design.md)`",
            )
            t2 = t2.replace(
                "[`edbo_external_replication_design.md`](edbo_external_replication_design.md)",
                "[`edbo_external_replication_design.md`](../design/edbo_external_replication_design.md)",
            )
            t2 = t2.replace(
                "`](manuscript_draft_DD.md)`",
                "`](../manuscript/archive/manuscript_draft_DD.md)`",
            )
            t2 = t2.replace(
                "`](manuscript_draft_DD_v0.5.md)`",
                "`](../manuscript/archive/manuscript_draft_DD_v0.5.md)`",
            )
            t2 = t2.replace(
                "docs/manuscript_draft_DD.md",
                "docs/manuscript/archive/manuscript_draft_DD.md",
            )
            t2 = t2.replace(
                "docs/manuscript_draft_DD_v0.5.md",
                "docs/manuscript/archive/manuscript_draft_DD_v0.5.md",
            )
            t2 = t2.replace(
                "`docs/待处理事项.md`",
                "`docs/plans/待处理事项.md`",
            )
            t2 = t2.replace(
                "`docs/开题与任务定稿.md`",
                "`docs/plans/开题与任务定稿.md`",
            )
            t2 = t2.replace(
                "`docs/可复现性清单.md`",
                "`docs/plans/可复现性清单.md`",
            )
            t2 = t2.replace(
                "`docs/论文细纲-DigitalDiscovery.md`",
                "`docs/design/论文细纲-DigitalDiscovery.md`",
            )
            t2 = t2.replace(
                "`docs/edbo_external_replication_design.md`",
                "`docs/design/edbo_external_replication_design.md`",
            )
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("PATCH", p.relative_to(DOCS))

    # export script path update for briefing
    exp = ROOT / "scripts" / "export_zh_briefing_docx.py"
    if exp.exists():
        et = exp.read_text(encoding="utf-8")
        et2 = et.replace(
            'OUT = ROOT / "docs" / "briefing_zh_EDBO_Suzuki_v0.6.docx"',
            'OUT = ROOT / "docs" / "briefings" / "briefing_zh_EDBO_Suzuki_v0.6.docx"',
        ).replace(
            'OUT_CN = ROOT / "docs" / "本工作说明_EDBO_Suzuki_v0.6.docx"',
            'OUT_CN = ROOT / "docs" / "briefings" / "本工作说明_EDBO_Suzuki_v0.6.docx"',
        )
        if et2 != et:
            exp.write_text(et2, encoding="utf-8")
            print("PATCH scripts/export_zh_briefing_docx.py")

    # EXPERIMENT_SUMMARY / FROZEN paths to docs
    for rel in [
        "results/paper_stats/EXPERIMENT_SUMMARY.md",
        "results/paper_stats/FROZEN_CLAIMS.md",
    ]:
        p = ROOT / rel
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        t2 = (
            t.replace("../../docs/行动方案_成稿收尾.md", "../../docs/plans/行动方案_成稿收尾.md")
            .replace("../../docs/行动方案_主线锁定.md", "../../docs/plans/行动方案_主线锁定.md")
            .replace("docs/figs/fig_edbo_suzuki_", "docs/figs/…; main: docs/figs/main/")
            .replace("`docs/figs/fig1_same_library_transfer_schematic.png`", "`docs/figs/main/fig1_same_library_transfer_schematic.png`")
            .replace(
                "| Fig1 | Problem + protocol schematic | `docs/figs/fig1_same_library_transfer_schematic.png` | (existing) |",
                "| Fig1 | Problem + protocol schematic | `docs/figs/main/fig1_same_library_transfer_schematic.png` | (existing) |",
            )
            .replace(
                "| Fig2 | C1 three-rep pair Δfrac by budget | `docs/figs/fig_edbo_suzuki_C1_pair_delta_by_budget.{png,pdf}` | `scripts/plot_edbo_c1_pair_budget.py` |",
                "| Fig2 | C1 three-rep pair Δfrac by budget | `docs/figs/main/fig_edbo_suzuki_C1_pair_delta_by_budget.{png,pdf}` | `scripts/plot_edbo_c1_pair_budget.py` |",
            )
            .replace(
                "| Fig3 | S0 vs Main init robustness | `docs/figs/fig_edbo_suzuki_s0_vs_main_pair_delta.{png,pdf}` | `scripts/plot_edbo_s0_vs_main.py` |",
                "| Fig3 | S0 vs Main init robustness | `docs/figs/main/fig_edbo_suzuki_s0_vs_main_pair_delta.{png,pdf}` | `scripts/plot_edbo_s0_vs_main.py` |",
            )
            .replace(
                "| Fig4 | A1–A3 ladder @ B=40 vs S0 cold | `docs/figs/fig_edbo_suzuki_ladder_A1A2A3_B40.{png,pdf}` | `scripts/plot_edbo_ladder_a0a3.py` |",
                "| Fig4 | A1–A3 ladder @ B=40 vs S0 cold | `docs/figs/main/fig_edbo_suzuki_ladder_A1A2A3_B40.{png,pdf}` | `scripts/plot_edbo_ladder_a0a3.py` |",
            )
        )
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
            print("PATCH", rel)

    # plot scripts FIG output dir -> figs/main for the three new ones
    for script, stems in [
        ("scripts/plot_edbo_c1_pair_budget.py", None),
        ("scripts/plot_edbo_s0_vs_main.py", None),
        ("scripts/plot_edbo_ladder_a0a3.py", None),
    ]:
        sp = ROOT / script
        if not sp.exists():
            continue
        st = sp.read_text(encoding="utf-8")
        if 'FIGS = ROOT / "docs" / "figs"' in st and "figs/main" not in st:
            st = st.replace(
                'FIGS = ROOT / "docs" / "figs"',
                'FIGS = ROOT / "docs" / "figs" / "main"',
            )
            sp.write_text(st, encoding="utf-8")
            print("PATCH", script)

    print("\nDone. Top-level docs now:")
    for p in sorted(DOCS.iterdir()):
        print(" ", p.name + ("/" if p.is_dir() else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
