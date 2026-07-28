# -*- coding: utf-8 -*-
"""
EDBO 向导式操作界面（Streamlit）— BOUSE 主优化器 UI

启动::

    conda activate edbo
    cd BOUSE/edbo
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
BOUSE = ROOT.parent
SRC = ROOT / "src"
for p in (SRC, BOUSE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backfill import measurement_template, merge_results  # noqa: E402
from domain_builder import build_domain  # noqa: E402
from factors import FactorSpec, factor_keys  # noqa: E402
from handoff import (  # noqa: E402
    check_descriptor_df,
    check_workspace_descriptors,
    chemical_descriptor_factors,
    import_descriptor,
    list_descriptor_outputs,
)
from recommend import recommend_bo, recommend_nomodel  # noqa: E402
from templates import TEMPLATES, apply_template, template_choices  # noqa: E402
from workspace import (  # noqa: E402
    create_project,
    descriptor_path,
    get_factors,
    levels_path,
    list_projects,
    load_config,
    load_history,
    load_recommendations,
    project_dir,
    save_config,
    save_history,
    save_recommendations,
    sanitize_project_id,
)

STEPS = ["项目与目标", "定义搜索域", "推荐下一轮", "回填结果"]
ACQ_OPTIONS = ["EI", "TS", "UCB", "PI"]
NOMODEL_OPTIONS = {
    "lhs": "拉丁超立方 (LHS)",
    "random": "随机",
    "sobol": "Sobol",
    "maximin": "极大极小距离",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _init_state():
    ss = st.session_state
    ss.setdefault("step", 0)
    ss.setdefault("project_id", None)
    ss.setdefault("cfg", None)
    ss.setdefault("last_info", None)


def _ws() -> Path | None:
    pid = st.session_state.project_id
    if not pid:
        return None
    return project_dir(ROOT, pid)


def _reload_cfg():
    ws = _ws()
    if ws is None:
        return
    st.session_state.cfg = load_config(ws)


def _save_cfg():
    ws = _ws()
    if ws is None or st.session_state.cfg is None:
        return
    save_config(ws, st.session_state.cfg)


def _history() -> pd.DataFrame:
    ws = _ws()
    cfg = st.session_state.cfg
    if ws is None or cfg is None:
        return pd.DataFrame()
    keys = factor_keys(get_factors(cfg))
    return load_history(ws, cfg.get("target_column", "yield"), keys)


def _domain_preview() -> dict | None:
    ws = _ws()
    cfg = st.session_state.cfg
    if ws is None or cfg is None:
        return None
    factors = get_factors(cfg)
    if not factors:
        return None
    try:
        _, _, info = build_domain(ws, factors)
        return info
    except Exception as e:
        return {"error": str(e)}


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.title("EDBO 向导")
    st.sidebar.caption("经典单目标 · conda: **`edbo`** · :8501")
    st.sidebar.caption("勿与 EDBO+（`edbo_plus` / :8503）混用")
    projects = list_projects(ROOT)
    pid = st.session_state.project_id

    if projects:
        idx = projects.index(pid) if pid in projects else 0
        choice = st.sidebar.selectbox("当前项目", projects, index=idx)
        if choice != pid:
            st.session_state.project_id = choice
            _reload_cfg()
            st.session_state.step = 0
            st.rerun()
    else:
        st.sidebar.info("还没有项目，请先在步骤 1 创建。")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**进度**")
    for i, name in enumerate(STEPS):
        mark = "●" if i == st.session_state.step else ("○" if i > st.session_state.step else "✓")
        label = f"{mark} {i + 1}. {name}"
        if st.sidebar.button(label, key=f"nav_{i}", use_container_width=True):
            if st.session_state.project_id is None and i > 0:
                st.sidebar.warning("请先创建或打开项目")
            else:
                st.session_state.step = i
                st.rerun()

    cfg = st.session_state.cfg
    hist = _history()
    st.sidebar.markdown("---")
    st.sidebar.metric("历史实验", len(hist) if hist is not None else 0)
    info = _domain_preview()
    if info and "domain_size" in info:
        st.sidebar.metric("搜索域大小", f"{info['domain_size']:,}")
        st.sidebar.caption(f"特征维数: {info.get('n_features', '-')}")
    elif info and "error" in info:
        st.sidebar.caption(f"域未就绪: {info['error'][:80]}")
    if cfg:
        st.sidebar.caption(f"目标列: `{cfg.get('target_column', 'yield')}`")

    ws = _ws()
    if ws is not None:
        st.sidebar.markdown("---")
        st.sidebar.markdown("**描述符对接**")
        items = chemical_descriptor_factors(ws)
        if not items:
            st.sidebar.caption("无化学描述符因子")
        else:
            ready = sum(1 for x in items if x["status"] == "ready")
            st.sidebar.caption(f"{ready}/{len(items)} 已就绪")
            for x in items:
                mark = "✓" if x["status"] == "ready" else "✗"
                st.sidebar.caption(f"{mark} `{x['key']}`")
        st.sidebar.caption("描述符界面：`../descriptors` → streamlit run app.py")


# ---------------------------------------------------------------------------
# step 1
# ---------------------------------------------------------------------------

def step_project():
    st.header("步骤 1 · 项目与目标")
    st.write("创建或打开一个项目，设定单目标列名。推荐使用「条件优化」模板。")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("打开已有项目")
        projects = list_projects(ROOT)
        if projects:
            sel = st.selectbox("项目列表", projects, key="open_sel")
            if st.button("打开项目", type="primary"):
                st.session_state.project_id = sel
                _reload_cfg()
                st.success(f"已打开：{sel}")
                st.session_state.step = 1
                st.rerun()
        else:
            st.caption("暂无项目")

    with col2:
        st.subheader("新建项目")
        name = st.text_input("项目名称", value="my_reaction")
        choices = template_choices()
        labels = [c[1] for c in choices]
        ids = [c[0] for c in choices]
        ti = st.selectbox(
            "反应类型模板",
            range(len(ids)),
            format_func=lambda i: labels[i],
            index=0,
        )
        tid = ids[ti]
        st.caption(TEMPLATES[tid]["description"])
        target = st.text_input("目标列名", value="yield")
        if st.button("创建项目"):
            try:
                cfg = apply_template(tid)
                cfg["target_column"] = target.strip() or "yield"
                pid = create_project(ROOT, name, cfg)
                st.session_state.project_id = pid
                _reload_cfg()
                st.success(f"已创建：{pid}")
                st.session_state.step = 1
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if st.session_state.project_id and st.session_state.cfg:
        st.markdown("---")
        cfg = st.session_state.cfg
        st.write(f"当前项目：**{st.session_state.project_id}**")
        new_target = st.text_input("修改目标列名", value=cfg.get("target_column", "yield"), key="tgt_edit")
        if st.button("保存目标列名"):
            cfg["target_column"] = new_target.strip() or "yield"
            _save_cfg()
            st.success("已保存")
        if st.button("下一步：定义搜索域 →"):
            st.session_state.step = 1
            st.rerun()


# ---------------------------------------------------------------------------
# step 2
# ---------------------------------------------------------------------------

def _edit_factor_form(f: FactorSpec, idx: int) -> FactorSpec:
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        key = st.text_input("因子名 key", value=f.key, key=f"fk_{idx}")
    with c2:
        kind = st.selectbox(
            "类型",
            ["chemical", "numeric"],
            index=0 if f.kind == "chemical" else 1,
            key=f"kind_{idx}",
        )
    with c3:
        if kind == "chemical":
            enc = st.selectbox(
                "编码",
                ["descriptor", "ohe"],
                index=0 if f.encoding == "descriptor" else 1,
                format_func=lambda x: "描述符 CSV" if x == "descriptor" else "独热 (OHE)",
                key=f"enc_{idx}",
            )
        else:
            enc = "descriptor"
            mode = st.selectbox(
                "数值模式",
                ["list", "linspace", "arange"],
                index=["list", "linspace", "arange"].index(f.numeric_mode)
                if f.numeric_mode in ("list", "linspace", "arange")
                else 0,
                key=f"nm_{idx}",
            )

    nf = FactorSpec(
        key=sanitize_project_id(key) if key else f.key,
        kind=kind,
        encoding=enc if kind == "chemical" else f.encoding,
        id_column="molecule_id",
        levels=list(f.levels),
        numeric_mode=f.numeric_mode,
        values=list(f.values),
        linspace_min=f.linspace_min,
        linspace_max=f.linspace_max,
        linspace_n=f.linspace_n,
        arange_min=f.arange_min,
        arange_max=f.arange_max,
        arange_step=f.arange_step,
    )

    ws = _ws()
    if kind == "chemical":
        st.caption("化学因子 id 列固定为 `molecule_id`；描述符也可在「描述符生成」界面算好后导入。")
        if nf.encoding == "descriptor":
            _dock_descriptor_for_factor(ws, nf.key, idx)
        else:
            levels_text = st.text_area(
                "独热水平（每行一个 molecule_id）",
                value="\n".join(f.levels),
                key=f"lv_{idx}",
                height=100,
            )
            nf.levels = [x.strip() for x in levels_text.splitlines() if x.strip()]
            up = st.file_uploader(
                f"或上传 levels CSV（含 molecule_id）— {nf.key}",
                type=["csv"],
                key=f"up_lv_{idx}",
            )
            if up is not None and ws is not None:
                raw = pd.read_csv(up)
                if "molecule_id" not in raw.columns:
                    st.error("CSV 必须包含 molecule_id 列")
                else:
                    path = levels_path(ws, nf.key)
                    raw.to_csv(path, index=False)
                    nf.levels = raw["molecule_id"].astype(str).tolist()
                    st.success(f"已保存 {path.name}")
    else:
        nf.numeric_mode = mode  # type: ignore[name-defined]
        if nf.numeric_mode == "list":
            txt = st.text_input(
                "数值列表（逗号分隔）",
                value=",".join(str(v) for v in f.values),
                key=f"vals_{idx}",
            )
            try:
                nf.values = [float(x.strip()) for x in txt.split(",") if x.strip()]
            except ValueError:
                st.warning("数值列表解析失败")
        elif nf.numeric_mode == "linspace":
            a, b, c = st.columns(3)
            nf.linspace_min = a.number_input("min", value=float(f.linspace_min or 0), key=f"ls0_{idx}")
            nf.linspace_max = b.number_input("max", value=float(f.linspace_max or 1), key=f"ls1_{idx}")
            nf.linspace_n = int(c.number_input("点数", value=int(f.linspace_n or 5), min_value=2, key=f"ls2_{idx}"))
        else:
            a, b, c = st.columns(3)
            nf.arange_min = a.number_input("min", value=float(f.arange_min or 0), key=f"ar0_{idx}")
            nf.arange_max = b.number_input("max", value=float(f.arange_max or 1), key=f"ar1_{idx}")
            nf.arange_step = c.number_input("step", value=float(f.arange_step or 0.1), key=f"ar2_{idx}")
    return nf


def _dock_descriptor_for_factor(ws: Path | None, factor_key: str, idx: int) -> None:
    """单个化学因子：上传 / 从 descriptors/output 选取 / 显示状态。"""
    if ws is None:
        return
    path = descriptor_path(ws, factor_key)
    if path.is_file():
        try:
            df = pd.read_csv(path)
            errs = check_descriptor_df(df)
            if errs:
                st.warning(f"已有 `{path.name}` 但校验未通过: " + "; ".join(errs[:3]))
            else:
                st.success(
                    f"已对接 `{path.name}` · {len(df)} 分子 · {df.shape[1]-1} 特征"
                )
        except Exception as e:
            st.error(f"读取 `{path.name}` 失败: {e}")
    else:
        st.info(f"尚未对接：需要 `{path.name}`")

    tab_up, tab_pick = st.tabs(["上传 CSV", "从描述符模块选取"])
    with tab_up:
        up = st.file_uploader(
            f"上传描述符（需含 molecule_id）— {factor_key}",
            type=["csv"],
            key=f"up_desc_{idx}",
        )
        force = st.checkbox("覆盖已有文件", value=False, key=f"force_up_{idx}")
        if up is not None and st.button("校验并导入", key=f"btn_up_{idx}"):
            try:
                raw = pd.read_csv(up)
                dest = import_descriptor(raw, ws, factor_key, force=force or not path.is_file())
                st.success(f"已导入 {dest.name}")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    with tab_pick:
        outs = list_descriptor_outputs()
        if not outs:
            st.caption("descriptors/output/ 下暂无 CSV。请先在描述符界面生成。")
        else:
            labels = [p.name for p in outs]
            choice = st.selectbox(
                "descriptors/output 文件",
                range(len(outs)),
                format_func=lambda i: labels[i],
                key=f"pick_desc_{idx}",
            )
            force2 = st.checkbox("覆盖已有文件", value=False, key=f"force_pick_{idx}")
            if st.button("导入所选文件", key=f"btn_pick_{idx}"):
                try:
                    dest = import_descriptor(
                        outs[choice], ws, factor_key, force=force2 or not path.is_file()
                    )
                    st.success(f"已导入 {dest.name}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def step_domain():
    st.header("步骤 2 · 定义搜索域")
    st.write("配置因子与编码。化学因子需对接描述符 CSV（本步上传，或从描述符模块导入）。")
    cfg = st.session_state.cfg
    if cfg is None:
        st.warning("请先完成步骤 1")
        return

    ws = _ws()
    if ws is not None:
        with st.expander("描述符对接总览", expanded=True):
            items = chemical_descriptor_factors(ws)
            if not items:
                st.caption("当前没有「化学 + 描述符」因子。")
            else:
                rows = [
                    {
                        "因子": x["key"],
                        "状态": {"ready": "已就绪", "missing": "缺失", "broken": "损坏"}.get(
                            x["status"], x["status"]
                        ),
                        "分子数": x["n_rows"],
                        "特征数": x["n_features"],
                        "文件": x["path"].name,
                    }
                    for x in items
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            errs = check_workspace_descriptors(ws)
            if errs:
                st.warning("对接未完成：\n" + "\n".join(f"- {e}" for e in errs))
            else:
                st.success("所有化学描述符因子已对接且通过校验。")

    factors = get_factors(cfg)
    edited: list[FactorSpec] = []
    remove_idx = None

    for i, f in enumerate(factors):
        with st.expander(f"因子 {i + 1}: {f.key} ({f.kind})", expanded=(i < 2)):
            nf = _edit_factor_form(f, i)
            edited.append(nf)
            if st.button("删除此因子", key=f"del_{i}"):
                remove_idx = i

    if remove_idx is not None:
        edited.pop(remove_idx)
        cfg["factors"] = [f.to_dict() for f in edited]
        _save_cfg()
        st.rerun()

    if st.button("添加因子"):
        edited.append(FactorSpec(key=f"factor_{len(edited)+1}", kind="chemical", encoding="descriptor"))
        cfg["factors"] = [f.to_dict() for f in edited]
        _save_cfg()
        st.rerun()

    if st.button("保存搜索域", type="primary"):
        cfg["factors"] = [f.to_dict() for f in edited]
        _save_cfg()
        st.success("已保存")

    # 始终把当前表单写回内存，便于预览（未点保存则以已存为准；点保存后刷新）
    # 预览用磁盘配置
    info = _domain_preview()
    st.markdown("---")
    st.subheader("域预览")
    if info is None:
        st.caption("请先添加因子并上传描述符/水平")
    elif "error" in info:
        st.warning(info["error"])
    else:
        st.write(
            f"搜索域 **{info['domain_size']:,}** 点 · "
            f"{info['n_factors']} 个因子 · {info['n_features']} 维特征"
        )
        st.json(info.get("level_sizes", {}))
        if info["domain_size"] > 300_000:
            st.warning("域较大（>300,000），推荐与训练可能较慢。")

    c1, c2 = st.columns(2)
    if c1.button("← 上一步"):
        st.session_state.step = 0
        st.rerun()
    if c2.button("下一步：推荐 →"):
        cfg["factors"] = [f.to_dict() for f in edited]
        _save_cfg()
        st.session_state.step = 2
        st.rerun()


# ---------------------------------------------------------------------------
# step 3
# ---------------------------------------------------------------------------

def step_recommend():
    st.header("步骤 3 · 推荐下一轮")
    cfg = st.session_state.cfg
    ws = _ws()
    if cfg is None or ws is None:
        st.warning("请先完成步骤 1–2")
        return

    hist = _history()
    n_hist = len(hist)
    factors = get_factors(cfg)
    target = cfg.get("target_column", "yield")

    if n_hist == 0:
        st.info("还没有实验结果，建议先用**无模型选点**开局。有历史后可直接贝叶斯推荐。")
        default_mode = "nomodel"
    else:
        st.success(f"已有 **{n_hist}** 条历史，可直接进行**贝叶斯推荐**。")
        default_mode = "bo"

    mode = st.radio(
        "推荐模式",
        ["bo", "nomodel"],
        index=0 if default_mode == "bo" else 1,
        format_func=lambda x: "贝叶斯优化 (GP)" if x == "bo" else "无模型选点",
        horizontal=True,
    )
    if mode == "bo" and n_hist == 0:
        st.error("当前无历史，无法贝叶斯推荐。请改用无模型选点，或先到步骤 4 回填结果。")

    batch = st.number_input("本批实验数 batch_size", min_value=1, max_value=50, value=int(cfg.get("batch_size", 5)))
    cfg["batch_size"] = int(batch)

    nomodel_method = "lhs"
    nomodel_seed = 0
    with st.expander("高级选项", expanded=False):
        if mode == "bo":
            acq = st.selectbox(
                "采集函数",
                ACQ_OPTIONS,
                index=ACQ_OPTIONS.index(cfg.get("acquisition_function", "EI"))
                if cfg.get("acquisition_function", "EI") in ACQ_OPTIONS
                else 0,
            )
            cfg["acquisition_function"] = acq
            cfg["training_iters"] = int(
                st.number_input("GP 训练轮数", min_value=20, max_value=500, value=int(cfg.get("training_iters", 100)))
            )
            cfg["noise_constraint"] = float(
                st.number_input(
                    "噪声下限 noise_constraint",
                    min_value=1e-6,
                    max_value=1.0,
                    value=float(cfg.get("noise_constraint", 0.01)),
                    format="%.4f",
                )
            )
        else:
            nomodel_method = st.selectbox(
                "无模型方法",
                list(NOMODEL_OPTIONS.keys()),
                format_func=lambda k: NOMODEL_OPTIONS[k],
                index=0,
            )
            nomodel_seed = int(st.number_input("随机种子", min_value=0, value=0))

    if st.button("生成推荐", type="primary", disabled=(mode == "bo" and n_hist == 0)):
        _save_cfg()
        try:
            with st.spinner("正在计算推荐…"):
                if mode == "nomodel":
                    rec, info = recommend_nomodel(
                        ws,
                        factors,
                        hist,
                        batch_size=int(batch),
                        method=nomodel_method,
                        seed=nomodel_seed,
                    )
                else:
                    rec, info = recommend_bo(
                        ws,
                        factors,
                        hist,
                        target_col=target,
                        batch_size=int(batch),
                        acquisition_function=cfg.get("acquisition_function", "EI"),
                        training_iters=int(cfg.get("training_iters", 100)),
                        noise_constraint=float(cfg.get("noise_constraint", 0.01)),
                        domain_cap=int(cfg.get("domain_cap", 2500)),
                    )
            save_recommendations(ws, rec)
            st.session_state.last_info = info
            st.success(f"已生成 {len(rec)} 条推荐")
        except Exception as e:
            st.exception(e)

    rec = load_recommendations(ws)
    if rec is not None and not rec.empty:
        st.subheader("本轮待做实验")
        st.dataframe(rec, use_container_width=True)
        st.download_button(
            "下载推荐 CSV",
            data=_to_csv_bytes(rec),
            file_name="recommendations.csv",
            mime="text/csv",
        )
        if st.session_state.last_info:
            with st.expander("运行信息"):
                st.json(st.session_state.last_info)

        if n_hist > 0 and target in hist.columns:
            with st.expander("简要分析：历史目标", expanded=False):
                st.line_chart(hist[target].astype(float).reset_index(drop=True))
                st.caption(f"历史最优 {target} = {hist[target].astype(float).max():.4g}")

    c1, c2 = st.columns(2)
    if c1.button("← 上一步"):
        st.session_state.step = 1
        st.rerun()
    if c2.button("下一步：回填结果 →"):
        st.session_state.step = 3
        st.rerun()


# ---------------------------------------------------------------------------
# step 4
# ---------------------------------------------------------------------------

def step_backfill():
    st.header("步骤 4 · 回填结果")
    st.write("完成本轮实验后，把目标值填回，写入历史，即可回到步骤 3 继续推荐。")
    cfg = st.session_state.cfg
    ws = _ws()
    if cfg is None or ws is None:
        st.warning("请先完成前面步骤")
        return

    factors = get_factors(cfg)
    keys = factor_keys(factors)
    target = cfg.get("target_column", "yield")
    rec = load_recommendations(ws)

    if rec is not None and not rec.empty:
        tmpl = measurement_template(rec, target)
        st.download_button(
            "下载回填模板（基于本轮推荐）",
            data=_to_csv_bytes(tmpl),
            file_name="measurement_template.csv",
            mime="text/csv",
        )
    else:
        st.caption("尚无本轮推荐；也可直接上传含全部因子列 + 目标列的 CSV。")

    replace = st.checkbox("同条件覆盖旧记录（否则追加）", value=False)
    up = st.file_uploader("上传结果 CSV", type=["csv"])
    manual = st.data_editor(
        measurement_template(rec, target) if rec is not None and not rec.empty
        else pd.DataFrame(columns=keys + [target]),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_backfill",
    )

    if st.button("写入历史", type="primary"):
        try:
            if up is not None:
                new_df = pd.read_csv(up)
            else:
                new_df = manual.copy()
            hist = _history()
            merged = merge_results(hist, new_df, factors, target, replace=replace)
            save_history(ws, merged)
            st.success(f"历史已更新，共 {len(merged)} 条")
        except Exception as e:
            st.error(str(e))

    hist = _history()
    if not hist.empty:
        st.subheader("当前历史")
        st.dataframe(hist, use_container_width=True)

    c1, c2 = st.columns(2)
    if c1.button("← 上一步"):
        st.session_state.step = 2
        st.rerun()
    if c2.button("回到步骤 3 继续推荐", type="primary"):
        st.session_state.step = 2
        st.rerun()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="EDBO 向导 · BOUSE", page_icon="⚗️", layout="wide")
    from env_check import check_classic_edbo

    ok, msg = check_classic_edbo()
    if not ok:
        st.error("环境校验失败（经典 EDBO 需要 conda **`edbo`**，不要用 `edbo_plus`）")
        st.code(msg)
        st.stop()
    with st.sidebar.expander("环境", expanded=False):
        st.caption(msg)

    _init_state()
    if st.session_state.project_id and st.session_state.cfg is None:
        _reload_cfg()

    render_sidebar()
    step = st.session_state.step
    if step == 0:
        step_project()
    elif step == 1:
        step_domain()
    elif step == 2:
        step_recommend()
    else:
        step_backfill()


if __name__ == "__main__":
    main()
