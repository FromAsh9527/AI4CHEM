#!/usr/bin/env python
"""Plot best-so-far curves and optional transfer heatmaps from result folders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_best_so_far(summary_csv: Path, out_png: Path, title: str = "Best-so-far") -> None:
    df = pd.read_csv(summary_csv)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df["query"], df["mean"], label="mean")
    if "std" in df.columns:
        ax.fill_between(
            df["query"],
            df["mean"] - df["std"],
            df["mean"] + df["std"],
            alpha=0.25,
            label="±1 std",
        )
    ax.set_xlabel("Query")
    ax.set_ylabel("Best response so far")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_heatmap(csv_path: Path, out_png: Path, title: str = "Transfer gain") -> None:
    df = pd.read_csv(csv_path, index_col=0)
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(df, annot=True, fmt=".2f", cmap="RdBu_r", center=1.0, ax=ax)
    ax.set_title(title)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, help="best_so_far_summary.csv")
    parser.add_argument("--heatmap", type=Path, help="heatmap_*.csv from grid runner")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", type=str, default=None)
    args = parser.parse_args()

    if args.summary:
        plot_best_so_far(args.summary, args.out, title=args.title or "Best-so-far")
    elif args.heatmap:
        plot_heatmap(args.heatmap, args.out, title=args.title or "Transfer gain")
    else:
        raise SystemExit("Provide --summary or --heatmap")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
