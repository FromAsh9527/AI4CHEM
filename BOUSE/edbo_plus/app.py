# -*- coding: utf-8 -*-
"""
EDBO+ 向导式界面（Streamlit）— 多目标贝叶斯优化

启动::

    conda activate edbo_plus
    cd BOUSE/edbo_plus
    streamlit run app.py --server.port 8503
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backfill import apply_backfill, pending_suggestions  # noqa: E402
from runner import generate_scope, import_scope_csv, run_round, scope_summary  # noqa: E402
from workspace import (  # noqa: E402
    DEFAULT_CONFIG,
    create_project,
    load_config,
    load_reaction,
    list_projects,
    parse_levels_text,
    pred_path,
    project_dir,
    reaction_path,
    save_config,
    suggested_mask,
)

STEPS = ["项目与目标", "定义搜索域", "推荐下一轮", "回填结果"]
INIT_METHODS = {
    "cvt": "CVT（推荐）",
    "lhs": "拉丁超立方 (LHS)",
    "random": "随机",
}
ACQ_OPTIONS = {
    "NoisyEHVI": "NoisyEHVI（多目标默认；单目标自动退化为 EI）",
    "EHVI": "EHVI（超体积改进）",
}


def _init_state():
    ss = st.session_state
    ss.setdefault("step", 0)
    ss.setdefault("project_id", None)
    ss.setdefault("cfg", None)


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


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def render_sidebar():
    st.sidebar.title("EDBO+ 向导")
    st.sidebar.caption("多目标 BO · conda: **`edbo_plus`** · :8503")
    st.sidebar.caption("勿与经典 EDBO（`edbo` / :8501）混用")
    projects = list_projects(ROOT)
    pid = st.session_state.project_id

    if projects:
        idx = projects.index(pid) if pid in projects else 0
        choice = st.sidebar.selectbox("当前项目", projects, index=idx)
        if choice != pid:
            st.session_state.project_id = choice
            _reload_cfg()
            st.session_state.step = 0
            st.experimental_rerun()
    else:
        st.sidebar.info("还没有项目，请先在步骤 1 创建。")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**进度**")
    for i, name in enumerate(STEPS):
        mark = "●" if i == st.session_state.step else ("○" if i > st.session_state.step else "✓")
        if st.sidebar.button(f"{mark} {i + 1}. {name}", key=f"nav_{i}"):
            if st.session_state.project_id is None and i > 0:
                st.sidebar.warning("请先创建或打开项目")
            else:
                st.session_state.step = i
                st.experimental_rerun()

    ws = _ws()
    cfg = st.session_state.cfg
    if ws is not None and cfg is not None:
        info = scope_summary(ws, cfg)
        st.sidebar.markdown("---")
        st.sidebar.metric("搜索域", f"{info.get('n_rows', 0):,}")
        st.sidebar.metric("已观测", info.get("n_observed", 0))
        st.sidebar.metric("待做 (priority=1)", info.get("n_suggested", 0))
        objs = cfg.get("objectives") or []
        modes = cfg.get("objective_mode") or []
        st.sidebar.caption(
            "目标: " + ", ".join(f"{o}({m})" for o, m in zip(objs, modes))
        )


def step_project():
    st.header("步骤 1 · 项目与目标")
    st.write(
        "创建项目并设定**一个或多个目标**（每个目标可选最大化/最小化）。"
        "这是 EDBO+ 相对经典 EDBO 的核心能力。"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("打开已有项目")
        projects = list_projects(ROOT)
        if projects:
            sel = st.selectbox("项目列表", projects, key="open_sel")
            if st.button("打开项目"):
                st.session_state.project_id = sel
                _reload_cfg()
                st.success(f"已打开：{sel}")
                st.session_state.step = 1
                st.experimental_rerun()
        else:
            st.caption("暂无项目")

    with col2:
        st.subheader("新建项目")
        name = st.text_input("项目名称", value="plus_demo")
        st.caption("默认：yield↑ + cost↓，小规模条件网格（步骤 2 可改）。")
        if st.button("创建项目"):
            try:
                pid = create_project(ROOT, name, dict(DEFAULT_CONFIG))
                st.session_state.project_id = pid
                _reload_cfg()
                st.success(f"已创建：{pid}")
                st.session_state.step = 1
                st.experimental_rerun()
            except Exception as e:
                st.error(str(e))

    if not (st.session_state.project_id and st.session_state.cfg):
        return

    st.markdown("---")
    cfg = st.session_state.cfg
    st.write(f"当前项目：**{st.session_state.project_id}**")

    st.subheader("目标列表")
    st.caption("每行一个：`目标名,方向`；方向为 max 或 min。示例：`yield,max`")
    objs = list(cfg.get("objectives") or [])
    modes = list(cfg.get("objective_mode") or [])
    default_lines = "\n".join(
        f"{o},{m}" for o, m in zip(objs, modes)
    ) or "yield,max\ncost,min"
    obj_text = st.text_area("目标定义", value=default_lines, height=120)

    c1, c2, c3 = st.columns(3)
    with c1:
        batch = st.number_input("每轮 batch", min_value=1, max_value=50, value=int(cfg.get("batch") or 3))
    with c2:
        seed = st.number_input("随机种子", min_value=0, max_value=10_000, value=int(cfg.get("seed") or 0))
    with c3:
        init_keys = list(INIT_METHODS.keys())
        init_cur = cfg.get("init_sampling_method") or "cvt"
        init_i = init_keys.index(init_cur) if init_cur in init_keys else 0
        init_m = st.selectbox(
            "无历史时的初采样",
            init_keys,
            index=init_i,
            format_func=lambda k: INIT_METHODS[k],
        )

    acq_keys = list(ACQ_OPTIONS.keys())
    acq_cur = cfg.get("acquisition_function") or "NoisyEHVI"
    acq_i = acq_keys.index(acq_cur) if acq_cur in acq_keys else 0
    acq = st.selectbox(
        "采集函数",
        acq_keys,
        index=acq_i,
        format_func=lambda k: ACQ_OPTIONS[k],
        help="≥2 目标用 NoisyEHVI/EHVI；单目标时上游对 NoisyEHVI 自动改用 EI。",
    )

    with st.expander("高级：目标阈值（可选）"):
        st.caption("对应 `objective_thresholds`。留空=自动；填写则与目标一一对应，空位写 none。")
        thr = cfg.get("objective_thresholds")
        thr_text = ""
        if isinstance(thr, list):
            thr_text = ", ".join("none" if x is None else str(x) for x in thr)
        thr_in = st.text_input("阈值（逗号分隔）", value=thr_text)

    if st.button("保存目标与参数"):
        new_objs, new_modes = [], []
        for line in obj_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2:
                st.error(f"格式错误：{line}（应为 名称,max|min）")
                return
            name, mode = parts[0], parts[1].lower()
            if mode not in ("max", "min"):
                st.error(f"非法方向：{mode}")
                return
            new_objs.append(name)
            new_modes.append(mode)
        if not new_objs:
            st.error("至少保留一个目标")
            return
        if len(set(new_objs)) != len(new_objs):
            st.error("目标列名不能重复")
            return

        thresholds = None
        if thr_in.strip():
            parts = [p.strip() for p in thr_in.split(",")]
            if len(parts) != len(new_objs):
                st.error("阈值个数必须与目标个数一致")
                return
            thresholds = []
            for p in parts:
                if p.lower() in ("", "none", "null"):
                    thresholds.append(None)
                else:
                    thresholds.append(float(p))

        cfg["objectives"] = new_objs
        cfg["objective_mode"] = new_modes
        cfg["objective_thresholds"] = thresholds
        cfg["batch"] = int(batch)
        cfg["seed"] = int(seed)
        cfg["init_sampling_method"] = init_m
        cfg["acquisition_function"] = acq
        _save_cfg()
        st.success("已保存")

    if st.button("下一步：定义搜索域 →"):
        st.session_state.step = 1
        st.experimental_rerun()


def _parse_components_text(text: str) -> dict:
    comps = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, levels_text = line.split(":", 1)
        key = key.strip()
        levels = parse_levels_text(levels_text)
        if not key or not levels:
            continue
        comps[key] = levels
    if not comps:
        raise ValueError("请按 `因子: 水平1, 水平2, ...` 每行一个填写")
    return comps


def step_scope():
    st.header("步骤 2 · 定义搜索域")
    st.write(
        "EDBO+ 搜索域是一张**组合表 CSV**。"
        "可用因子水平生成笛卡尔积，或上传已有 scope（可含描述符列）。"
        "类别列优化时自动 One-Hot；数值列按数值使用。"
    )
    ws = _ws()
    cfg = st.session_state.cfg
    if ws is None or cfg is None:
        st.warning("请先打开项目")
        return

    info = scope_summary(ws, cfg)
    if info.get("exists"):
        st.info(
            f"当前 scope：{info['n_rows']} 行 × {info['n_factors']} 因子；"
            f"已观测 {info['n_observed']}；待做 {info['n_suggested']}"
        )
        df = load_reaction(ws, cfg)
        st.dataframe(df.head(20))
        st.download_button(
            "下载完整 reaction.csv",
            data=_to_csv_bytes(df),
            file_name=reaction_path(ws, cfg).name,
            mime="text/csv",
        )

    tab_gen, tab_up = st.tabs(["按因子生成", "上传 CSV"])

    with tab_gen:
        comps = cfg.get("components") or DEFAULT_CONFIG["components"]
        default = "\n".join(f"{k}: {', '.join(str(x) for x in v)}" for k, v in comps.items())
        text = st.text_area(
            "因子定义（每行：`因子名: 水平1, 水平2, ...`）",
            value=default,
            height=160,
        )
        overwrite = st.checkbox("允许覆盖已有 reaction.csv", value=False)
        if st.button("生成搜索域"):
            try:
                if reaction_path(ws, cfg).exists() and not overwrite:
                    st.error("已存在 reaction.csv。勾选「允许覆盖」后再生成。")
                else:
                    components = _parse_components_text(text)
                    df, n = generate_scope(ws, components, cfg)
                    _reload_cfg()
                    st.success(f"已生成 scope：{n} 个组合")
                    st.dataframe(df.head(20))
            except Exception as e:
                st.error(str(e))

    with tab_up:
        st.caption(
            "CSV 应含因子列。若含目标列/priority，导入时会去掉，"
            "由步骤 3 的 `run()` 按官方逻辑重建 PENDING。"
        )
        up = st.file_uploader("上传 scope CSV", type=["csv"], key="scope_up")
        if up is not None and st.button("导入为 reaction.csv"):
            try:
                raw = pd.read_csv(up)
                clean = import_scope_csv(ws, raw, cfg)
                st.success(f"已导入 {len(clean)} 行，{len(clean.columns)} 列因子")
                st.dataframe(clean.head(20))
            except Exception as e:
                st.error(str(e))

    if st.button("下一步：推荐 →"):
        st.session_state.step = 2
        st.experimental_rerun()


def step_recommend():
    st.header("步骤 3 · 推荐下一轮")
    ws = _ws()
    cfg = st.session_state.cfg
    if ws is None or cfg is None:
        st.warning("请先打开项目")
        return

    info = scope_summary(ws, cfg)
    if not info.get("exists"):
        st.warning("尚未生成搜索域，请先完成步骤 2。")
        return

    objs = cfg.get("objectives") or []
    modes = cfg.get("objective_mode") or []
    st.write(
        f"域大小 **{info['n_rows']}** · 已观测 **{info['n_observed']}** · "
        f"batch={cfg.get('batch')} · 初采样=`{cfg.get('init_sampling_method')}` · "
        f"采集=`{cfg.get('acquisition_function')}`"
    )
    st.caption("目标: " + ", ".join(f"`{o}` ({m})" for o, m in zip(objs, modes)))

    if info["n_observed"] == 0:
        st.info(
            "还没有实测结果：本次 `run()` 会做**初采样**（CVT/LHS/random），"
            "标记 `priority=1`，目标列写入 `PENDING`。"
        )
    else:
        st.info(
            "已有观测：本次 `run()` 会训练代理模型并用 EHVI/NoisyEHVI（或单目标 EI）推荐下一批。"
        )

    if st.button("运行 EDBO+"):
        try:
            with st.spinner("正在调用 EDBOplus.run() …"):
                df = run_round(ws, cfg)
            sug = df[suggested_mask(df)] if "priority" in df.columns else df.head(0)
            st.success(f"完成。建议实验数：{len(sug)}")
            show_cols = [c for c in df.columns if c in (["priority"] + info["factor_cols"] + objs)]
            st.subheader("建议实验（priority = 1）")
            st.dataframe(sug[show_cols] if len(show_cols) else sug)
            st.download_button(
                "下载建议 CSV",
                data=_to_csv_bytes(sug[show_cols] if len(show_cols) else sug),
                file_name="edboplus_suggestions.csv",
                mime="text/csv",
            )
            pp = pred_path(ws, cfg)
            if pp.exists():
                st.caption(f"预测明细已写入 `{pp.name}`")
                st.download_button(
                    "下载 pred_*.csv",
                    data=_to_csv_bytes(pd.read_csv(pp)),
                    file_name=pp.name,
                    mime="text/csv",
                    key="dl_pred",
                )
        except Exception as e:
            st.error(str(e))

    df = load_reaction(ws, cfg)
    if not df.empty and "priority" in df.columns:
        with st.expander("查看完整 reaction.csv"):
            st.dataframe(df)

    if st.button("下一步：回填结果 →"):
        st.session_state.step = 3
        st.experimental_rerun()


def step_backfill():
    st.header("步骤 4 · 回填结果")
    st.write(
        "把建议行目标从 `PENDING` 改成实测数值并保存，再回到步骤 3。"
        "推荐：下载模板 → 填数 → 上传；或直接在下方按行填写。"
    )
    ws = _ws()
    cfg = st.session_state.cfg
    if ws is None or cfg is None:
        st.warning("请先打开项目")
        return

    pending = pending_suggestions(ws, cfg)
    if pending.empty:
        st.info("当前没有待回填的建议。请先在步骤 3 运行推荐。")
        if st.button("← 回到推荐"):
            st.session_state.step = 2
            st.experimental_rerun()
        return

    objectives = list(cfg.get("objectives") or [])
    st.caption(f"待回填 {len(pending)} 行；目标：{', '.join(objectives)}")
    st.dataframe(pending)

    st.download_button(
        "下载回填模板（含 _row）",
        data=_to_csv_bytes(pending),
        file_name="backfill_template.csv",
        mime="text/csv",
    )

    st.subheader("按行填写")
    values = {}
    for i, row in pending.iterrows():
        rid = int(row["_row"])
        label = " | ".join(
            f"{c}={row[c]}" for c in pending.columns if c not in ("_row", "priority", *objectives)
        )
        st.markdown(f"**行 {rid}** — {label}")
        cols = st.columns(len(objectives))
        for j, obj in enumerate(objectives):
            with cols[j]:
                values[(rid, obj)] = st.text_input(
                    obj, value="", key=f"bf_{rid}_{obj}", placeholder="数值"
                )

    up = st.file_uploader("或上传填好的回填 CSV", type=["csv"], key="bf_up")

    if st.button("保存回填到 reaction.csv"):
        try:
            if up is not None:
                edits = pd.read_csv(up)
            else:
                records = []
                for rid in pending["_row"].astype(int):
                    rec = {"_row": int(rid)}
                    ok = True
                    for obj in objectives:
                        # 优先读 session_state（带 key 的 text_input），避免空表丢列
                        raw = st.session_state.get(f"bf_{rid}_{obj}", values.get((rid, obj), ""))
                        raw = ("" if raw is None else str(raw)).strip()
                        if not raw:
                            ok = False
                            break
                        rec[obj] = float(raw)
                    if ok:
                        records.append(rec)
                if not records:
                    st.warning("没有可保存的行：请把每行目标都填成数值，或上传含 `_row` 的 CSV。")
                    edits = None
                else:
                    edits = pd.DataFrame(records)
            if edits is not None:
                n = apply_backfill(ws, edits, cfg)
                if n == 0:
                    st.warning("没有写入任何行（目标是否都填成了数值？`_row` 是否对应？）")
                else:
                    st.success(f"已写入 {n} 条观测。可回到步骤 3 继续推荐。")
        except Exception as e:
            st.error(str(e))

    if st.button("← 回到推荐（再跑一轮）"):
        st.session_state.step = 2
        st.experimental_rerun()


def main():
    st.set_page_config(page_title="EDBO+ · BOUSE", layout="wide")
    _init_state()

    # BOUSE/env_check.py
    bouse = ROOT.parent
    if str(bouse) not in sys.path:
        sys.path.insert(0, str(bouse))
    from env_check import check_edbo_plus

    ok, msg = check_edbo_plus()
    if not ok:
        st.error("环境校验失败（EDBO+ 需要 conda **`edbo_plus`**，不要用经典 `edbo`）")
        st.code(msg)
        st.stop()

    render_sidebar()
    with st.sidebar.expander("环境", expanded=False):
        st.caption(msg)

    step = st.session_state.step
    if step == 0:
        step_project()
    elif step == 1:
        step_scope()
    elif step == 2:
        step_recommend()
    else:
        step_backfill()


if __name__ == "__main__":
    main()
