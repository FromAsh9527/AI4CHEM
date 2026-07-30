# -*- coding: utf-8 -*-
"""
描述符生成 — Streamlit 界面（独立于 EDBO 向导）

启动::

    conda activate edbo
    cd BOUSE/descriptors
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
BOUSE = ROOT.parent
for p in (ROOT, BOUSE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from generators.clean.core import clean_dataframe  # noqa: E402
from generators.maccs.core import compute as compute_maccs  # noqa: E402
from generators.morgan.core import compute as compute_morgan  # noqa: E402
from generators.rdkit_2d.core import compute as compute_rdkit  # noqa: E402
from handoff import (  # noqa: E402
    chemical_descriptor_factors,
    import_descriptor,
    list_descriptor_outputs,
    list_edbo_projects,
    project_workspace,
)
from io_utils import (  # noqa: E402
    molecules_from_dataframe,
    to_csv_bytes,
    validate_descriptor_frame,
    write_descriptor_csv,
)

KIND_LABELS = {
    "rdkit_2d": "RDKit 2D（推荐起步）",
    "maccs": "MACCS keys",
    "morgan": "Morgan 指纹",
    "mordred": "Mordred（需安装 mordred）",
    "xtb": "xTB 半经验量化（需 xtb，较慢）",
}

OUTPUT_DIR = ROOT / "output"


def _init():
    st.session_state.setdefault("result_df", None)
    st.session_state.setdefault("failed_df", None)
    st.session_state.setdefault("info", None)
    st.session_state.setdefault("last_saved_path", None)


def _load_upload(uploaded, id_col, smiles_col) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith((".xlsx", ".xls")):
        raw = pd.read_excel(uploaded)
    else:
        raw = pd.read_csv(uploaded)
    return molecules_from_dataframe(raw, id_col=id_col or None, smiles_col=smiles_col or None)


def _save_result(desc: pd.DataFrame, factor_key: str, extra_info: dict | None = None):
    validate_descriptor_frame(desc)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"descriptor_{factor_key.strip() or 'mol'}.csv"
    write_descriptor_csv(desc, out_path)
    st.session_state.result_df = desc
    st.session_state.last_saved_path = str(out_path)
    info = {
        "n_ok": len(desc),
        "n_features": desc.shape[1] - 1,
        "saved": str(out_path),
        "factor_key": factor_key.strip() or "mol",
    }
    if extra_info:
        info.update(extra_info)
    st.session_state.info = info
    return out_path


def page_from_smiles():
    st.subheader("从 SMILES 生成")
    st.caption("只有分子名单 + SMILES 时用这里。RDKit/MACCS 开箱即用；Mordred 需额外安装。")

    kind = st.radio(
        "描述符类型",
        list(KIND_LABELS.keys()),
        format_func=lambda x: KIND_LABELS[x],
        horizontal=True,
    )
    up = st.file_uploader("上传分子表 CSV/Excel", type=["csv", "xlsx", "xls"], key="up_smi")
    c1, c2 = st.columns(2)
    id_col = c1.text_input("id 列名（可空）", value="")
    smiles_col = c2.text_input("SMILES 列名（可空，自动识别）", value="")

    radius, n_bits, use_counts = 2, 128, False
    ignore_3d = True
    xtb_gfn, xtb_opt, xtb_timeout = 2, False, 300
    if kind == "morgan":
        c3, c4, c5 = st.columns(3)
        radius = int(c3.number_input("radius", min_value=1, max_value=4, value=2))
        n_bits = int(c4.number_input("n_bits", min_value=16, max_value=2048, value=128, step=16))
        use_counts = c5.checkbox("计数指纹", value=False)
    elif kind == "mordred":
        ignore_3d = st.checkbox("忽略 3D 描述符（推荐）", value=True)
    elif kind == "xtb":
        c3, c4, c5 = st.columns(3)
        xtb_gfn = int(c3.selectbox("GFN 级别", options=[2, 1, 0], index=0))
        xtb_opt = c4.checkbox("几何优化（慢 3~10 倍）", value=False)
        xtb_timeout = int(c5.number_input("单分子超时（秒）", min_value=60, max_value=3600, value=300, step=60))

    factor_key = st.text_input(
        "因子名（保存为 descriptor_<因子>.csv，需与 EDBO 因子 key 一致）",
        value="solvent",
    )

    if st.button("生成描述符", type="primary", disabled=up is None):
        try:
            mols = _load_upload(up, id_col.strip() or None, smiles_col.strip() or None)
            with st.spinner(f"正在计算 {kind} …"):
                if kind == "rdkit_2d":
                    desc, failed = compute_rdkit(mols)
                elif kind == "morgan":
                    desc, failed = compute_morgan(
                        mols, radius=radius, n_bits=n_bits, use_counts=use_counts
                    )
                elif kind == "maccs":
                    desc, failed = compute_maccs(mols)
                elif kind == "xtb":
                    from generators.xtb.core import compute as compute_xtb

                    desc, failed = compute_xtb(
                        mols, gfn=xtb_gfn, opt=xtb_opt, timeout=xtb_timeout
                    )
                else:
                    from generators.mordred.core import compute as compute_mordred

                    desc, failed = compute_mordred(mols, ignore_3D=ignore_3d)
            if desc.empty:
                st.error("没有成功生成任何描述符，请检查 SMILES")
                return
            out_path = _save_result(desc, factor_key, {"backend": kind, "n_fail": len(failed)})
            st.session_state.failed_df = failed
            st.success(f"已生成并保存：`{out_path}` — 可到「对接 EDBO」标签导入。")
        except Exception as e:
            st.exception(e)


def page_clean():
    st.subheader("清洗已有描述符表")
    st.caption("已有 DFT / 宽表时，统一成 molecule_id + 数值列。")
    up = st.file_uploader("上传原始描述符 CSV/Excel", type=["csv", "xlsx", "xls"], key="up_clean")
    id_col = st.text_input("源 id 列（可空自动猜）", value="", key="clean_id")
    max_feat = st.number_input("最多保留特征数（0=不截断）", min_value=0, value=20)
    drop_na = st.checkbox("丢弃含 NaN 的行", value=False)
    factor_key = st.text_input("因子名", value="solvent", key="clean_factor")

    if st.button("清洗并导出", type="primary", disabled=up is None):
        try:
            name = up.name.lower()
            raw = pd.read_excel(up) if name.endswith((".xlsx", ".xls")) else pd.read_csv(up)
            cleaned, info = clean_dataframe(
                raw,
                id_col=id_col.strip() or None,
                max_features=int(max_feat) if max_feat > 0 else None,
                drop_na_rows=drop_na,
            )
            if cleaned.empty:
                st.error("清洗后为空")
                return
            out_path = _save_result(cleaned, factor_key, info)
            st.session_state.failed_df = None
            st.success(f"已保存：`{out_path}`")
            st.json(info)
        except Exception as e:
            st.exception(e)


def page_dock_edbo():
    st.subheader("对接 EDBO 优化器")
    st.caption("把本模块生成的描述符写入某个 EDBO 项目的 `descriptor_<因子>.csv`。")

    projects = list_edbo_projects()
    if not projects:
        st.warning("未找到 EDBO 项目。请先在 `edbo` 界面创建项目（步骤 1）。")
        st.code("cd ../edbo\nstreamlit run app.py", language="bash")
        return

    project = st.selectbox("EDBO 项目", projects)
    ws = project_workspace(project)

    st.markdown("**该项目化学描述符因子状态**")
    items = chemical_descriptor_factors(ws)
    if items:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "因子": x["key"],
                        "状态": {"ready": "已就绪", "missing": "缺失", "broken": "损坏"}.get(
                            x["status"], x["status"]
                        ),
                        "分子数": x["n_rows"],
                        "特征数": x["n_features"],
                    }
                    for x in items
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        factor_choices = [x["key"] for x in items]
    else:
        st.caption("项目里还没有「化学+描述符」因子；仍可按自定义因子名导入。")
        factor_choices = []

    src_mode = st.radio(
        "描述符来源",
        ["本次生成结果", "output 目录已有文件", "本地上传"],
        horizontal=True,
    )

    src_df: pd.DataFrame | None = None
    src_path: Path | None = None

    if src_mode == "本次生成结果":
        if st.session_state.result_df is not None and not st.session_state.result_df.empty:
            src_df = st.session_state.result_df
            st.caption(f"将使用内存中的结果（{len(src_df)} 行）。")
        else:
            st.info("尚无本次结果，请先在前两个标签生成，或改选其他来源。")
    elif src_mode == "output 目录已有文件":
        outs = list_descriptor_outputs()
        if not outs:
            st.caption("output/ 下暂无可用 CSV")
        else:
            i = st.selectbox(
                "选择文件",
                range(len(outs)),
                format_func=lambda j: outs[j].name,
            )
            src_path = outs[i]
    else:
        up = st.file_uploader("上传描述符 CSV", type=["csv"], key="dock_up")
        if up is not None:
            src_df = pd.read_csv(up)

    default_factor = ""
    if st.session_state.info and st.session_state.info.get("factor_key"):
        default_factor = str(st.session_state.info["factor_key"])
    elif factor_choices:
        default_factor = factor_choices[0]

    if factor_choices:
        factor = st.selectbox(
            "目标因子 key",
            factor_choices,
            index=factor_choices.index(default_factor) if default_factor in factor_choices else 0,
        )
        custom = st.text_input("或自定义因子名（非空则优先）", value="")
        if custom.strip():
            factor = custom.strip()
    else:
        factor = st.text_input("目标因子 key", value=default_factor or "solvent")

    force = st.checkbox("覆盖项目中已有的同名描述符文件", value=False)

    can_run = (src_df is not None) or (src_path is not None)
    if st.button("校验并导入到 EDBO", type="primary", disabled=not can_run or not str(factor).strip()):
        try:
            src = src_df if src_df is not None else src_path
            dest = import_descriptor(src, ws, factor, force=force)
            st.success(f"已导入：`{dest}`")
            st.info("请回到 EDBO 向导 → 步骤 2 查看对接状态，然后继续推荐。")
            # 刷新状态表
            st.rerun()
        except Exception as e:
            st.error(str(e))


def _render_preview():
    st.markdown("---")
    st.subheader("结果预览")
    info = st.session_state.info
    if info:
        st.caption(
            f"成功 {info.get('n_ok', info.get('n_rows_out', '-'))} 行 · "
            f"特征 {info.get('n_features', info.get('n_features_out', '-'))} · "
            f"文件 `{info.get('saved', '')}`"
        )
    df = st.session_state.result_df
    if df is not None and not df.empty:
        st.dataframe(df.head(50), use_container_width=True)
        fname = Path(info["saved"]).name if info and info.get("saved") else "descriptor.csv"
        st.download_button(
            "下载描述符 CSV",
            data=to_csv_bytes(df),
            file_name=fname,
            mime="text/csv",
            key="dl_descriptor_result",
        )
    else:
        st.caption("生成后将在此预览。")

    failed = st.session_state.failed_df
    if failed is not None and not failed.empty:
        with st.expander(f"失败 SMILES（{len(failed)}）"):
            st.dataframe(failed, use_container_width=True)
            st.download_button(
                "下载失败列表",
                data=to_csv_bytes(failed),
                file_name="failed_smiles.csv",
                mime="text/csv",
                key="dl_failed_smiles",
            )


def main():
    st.set_page_config(page_title="描述符生成 · BOUSE", page_icon="🧪", layout="wide")
    from env_check import check_classic_edbo

    ok, msg = check_classic_edbo(require_bro=False)
    if not ok:
        st.error("环境校验失败（描述符界面与经典 EDBO 共用 conda **`edbo`**）")
        st.code(msg)
        st.stop()

    _init()
    st.sidebar.caption("描述符 · conda: **`edbo`** · :8502")
    st.sidebar.caption("EDBO+ 请另开 `edbo_plus` / :8503")
    with st.sidebar.expander("环境", expanded=False):
        st.caption(msg)

    st.title("描述符生成")
    st.write("独立工具：分子 → 描述符 CSV；通过「对接 EDBO」写入优化器项目。")

    tab1, tab2, tab3 = st.tabs(["从 SMILES 生成", "清洗已有表", "对接 EDBO"])
    with tab1:
        page_from_smiles()
    with tab2:
        page_clean()
    with tab3:
        page_dock_edbo()

    # 预览只渲染一次，避免多 tab 重复 download_button 触发 DuplicateElementId
    _render_preview()


if __name__ == "__main__":
    main()
