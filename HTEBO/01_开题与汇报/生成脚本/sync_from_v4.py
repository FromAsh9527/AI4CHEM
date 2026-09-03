#!/usr/bin/env python3
"""若本地存在 v4 开题报告，则提取正文并与 v5 传统综述句式合并后重生 docx/md。

用法（在仓库根目录或 HTEBO/01_开题与汇报 下执行）：
    python3 生成脚本/sync_from_v4.py

查找顺序：
    1. 开题报告_*修订版v4.md
    2. 开题报告_*修订版v4.docx
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V4_MD_PATTERNS = sorted(ROOT.glob("开题报告_*修订版v4.md"))
V4_DOCX_PATTERNS = sorted(ROOT.glob("开题报告_*修订版v4.docx"))
BUILD_V5 = Path(__file__).resolve().parent / "_build_proposal_olefination_v5.py"
OUT_MD = sorted(ROOT.glob("开题报告_*修订版v5.md"))


def read_v4_md() -> str | None:
    if not V4_MD_PATTERNS:
        return None
    return V4_MD_PATTERNS[0].read_text(encoding="utf-8")


def read_v4_docx() -> str | None:
    if not V4_DOCX_PATTERNS:
        return None
    try:
        from docx import Document
    except ImportError:
        print("未安装 python-docx，跳过 v4 docx 读取")
        return None
    doc = Document(str(V4_DOCX_PATTERNS[0]))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_section(text: str, start_pat: str, end_pat: str | None) -> str | None:
    m = re.search(start_pat, text, flags=re.MULTILINE)
    if not m:
        return None
    start = m.start()
    if end_pat:
        m2 = re.search(end_pat, text[m.end() :], flags=re.MULTILINE)
        if m2:
            return text[start : m.end() + m2.start()].strip()
    return text[start:].strip()


def merge_v4_tail(v4_text: str) -> bool:
    """若 v4 含第 2–5 章且比 v5 更完整，写回 v5 生成脚本中的对应段落（仅当 v4.md 存在）。"""
    # 仅同步第 2 章及以后到临时补丁文件，供人工 diff；自动合并不改 py 内嵌大段正文，避免误覆盖综述。
    tail = extract_section(v4_text, r"^##?\s*2[\s　]", r"^##?\s*参考文献")
    if not tail:
        tail = extract_section(v4_text, r"^2[\s　]研究内容", r"^参考文献")
    if not tail or len(tail) < 500:
        return False
    patch = ROOT / "_v4_chapters_2_to_5_patch.md"
    patch.write_text(tail + "\n", encoding="utf-8")
    print(f"已从 v4 导出第 2–5 章补丁：{patch}")
    print("请对照该文件与 v5 正文；如需全自动合并，可将补丁内容告知 Agent 或手动粘贴进生成脚本 SECTIONS。")
    return True


def main() -> int:
    v4_text = read_v4_md()
    source = "md" if v4_text else None
    if not v4_text:
        v4_text = read_v4_docx()
        source = "docx" if v4_text else None

    if v4_text:
        print(f"检测到 v4 源文件（{source}），尝试导出第 2–5 章补丁…")
        merge_v4_tail(v4_text)
    else:
        print("未找到 v4 的 .md 或 .docx，将仅按 v5 生成脚本重建 docx/md。")
        print(f"请将本地文件复制到：{ROOT}/")
        print("  开题报告_新_无导向Pd烯基化区域选择性预测_修订版v4.md（推荐）")

    print("运行 v5 生成脚本…")
    subprocess.check_call([sys.executable, str(BUILD_V5)], cwd=BUILD_V5.parent)

    if OUT_MD:
        body = OUT_MD[0].read_text(encoding="utf-8")
        if "（待填）" in body:
            print("提示：封面姓名/学号/导师仍为待填。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
