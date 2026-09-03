// Build TransferBO2.0 report PPT with pptxgenjs (16:9, 14 slides).
// Same content as docs/26 v2 main-text draft; figures from results/presentation.
const pptxgen = require("pptxgenjs");
const P = new pptxgen();
P.defineLayout({ name: "W16x9", width: 13.333, height: 7.5 });
P.layout = "W16x9";
P.author = "TransferBO2.0";
P.title = "TransferBO2.0 report";

const DARK = "1F3A5F";
const ACCENT = "1F77B4";
const RED = "D62728";
const GREEN = "2CA02C";
const GRAY = "595959";
const LIGHT = "F2F5F9";
const WHITE = "FFFFFF";
const GOLD = "FFD966";

const FIG = "results/presentation/";
const slide = (title, subtitle) => {
  const s = P.addSlide();
  s.background = { color: WHITE };
  if (title) {
    s.addShape("rect", { x: 0, y: 0, w: 13.333, h: 0.9, fill: { color: DARK }, line: { type: "none" } });
    s.addText(title, { x: 0.45, y: 0.1, w: 12.4, h: 0.7, fontSize: 22, bold: true, color: WHITE, fontFace: "Microsoft YaHei", valign: "middle" });
  }
  if (subtitle) s.addText(subtitle, { x: 0.45, y: 0.95, w: 12.5, h: 0.4, fontSize: 12, color: GRAY, fontFace: "Microsoft YaHei" });
  return s;
};
const txt = (s, x, y, w, h, items, opts = {}) =>
  s.addText(items, { x, y, w, h, fontFace: "Microsoft YaHei", valign: "top", lineSpacing: 22, ...opts });
const T = (text, size, bold, color) => ({ text, options: { fontSize: size, bold, color, fontFace: "Microsoft YaHei", breakLine: false } });

const main = async () => {
  // ---- 1 cover ----
  let s = P.addSlide();
  s.background = { color: DARK };
  s.addText("Throw most of it away", { x: 0.9, y: 1.4, w: 11.5, h: 1.0, fontSize: 40, bold: true, color: WHITE, fontFace: "Microsoft YaHei" });
  s.addText("历史 HTE 数据通过五条件清单（而非迁移模型）加速新底物贝叶斯优化", { x: 0.9, y: 2.5, w: 11.5, h: 0.7, fontSize: 20, color: "BDD7EE", fontFace: "Microsoft YaHei" });
  s.addText("TransferBO 2.0 · 方法学研究汇报", { x: 0.9, y: 3.6, w: 11, h: 0.5, fontSize: 20, bold: true, color: ACCENT, fontFace: "Microsoft YaHei" });
  s.addText("四库 + 一维边界验证 · 71 项任务 · 2,130 条主协议 LOSO 轨迹 · 冻结协议与双对照\n2026-08-24 · 证据冻结 / 叙事校正版", { x: 0.9, y: 4.2, w: 11.5, h: 0.9, fontSize: 13, color: "BDD7EE", fontFace: "Microsoft YaHei" });
  s.addText([
    { text: "核心结论：", options: { fontSize: 15, bold: true, color: GOLD, fontFace: "Microsoft YaHei" } },
    { text: "历史数据最可靠的用法是给出跨底物排序保持的高价值条件清单；", options: { fontSize: 15, color: WHITE, fontFace: "Microsoft YaHei" } },
    { text: "历史产率标签不应默认迁入目标 BO 模型；初始化与续跑是两个独立、可选、可弃权的决策。", options: { fontSize: 15, color: WHITE, fontFace: "Microsoft YaHei" } },
  ], { x: 0.9, y: 5.5, w: 11.5, h: 1.3, fontFace: "Microsoft YaHei" });

  // ---- 2 question ----
  s = slide("研究问题：历史 HTE 数据能否、以及如何加速新底物优化？");
  txt(s, 0.7, 1.5, 12.2, 2.9, [
    T("问题 1", 16, true, ACCENT), T(" 新底物优化成本高：即使有 HTE，新底物通常需数十次实验才能到好结果", 16, false, DARK),
    T("问题 2", 16, true, ACCENT), T(" 历史库充足：同一模板 × 多个底物的稠密条件–产率矩阵随处可见", 16, false, DARK),
    T("问题 3", 16, true, ACCENT), T(" 答案并非显然为正：历史测在「别人」身上，底物自身反应活性会移动产率水平", 16, false, DARK),
    T("问题 4", 16, true, ACCENT), T(" 文献给出了很多「用法」，但很少在同一冻结协议下、跨多库比较：哪种形式可靠有益？", 16, false, DARK),
  ]);
  txt(s, 0.7, 4.7, 12.2, 1.7, [
    T("我们的定位：不是检验「冷启动 BO 是否强于随机」，而是找一个「正增益的历史数据应用策略」。", 17, true, DARK),
    T("评价口径：主指标 = 优化 AUC（Σ best-so-far，20 步）；双对照 = vs 冷启动 和 vs 随机。", 15, false, GRAY),
  ]);

  // ---- 3 1.0 lesson ----
  s = slide("切入点教训：单源 pair 迁移为负 → 2.0 从设计上改为多源池化");
  txt(s, 0.7, 1.4, 12.2, 1.3, [
    T("TransferBO 1.0：单源底物对迁移（一个源 → 一个靶），在 Suzuki 模板上效应为负。", 18, true, RED),
    T("原因：单源不仅携带模板通用的条件排序，还携带该底物的特异响应——迁移的「知识」含有噪声。", 15, false, GRAY),
  ]);
  txt(s, 0.7, 3.0, 12.2, 2.8, [
    T("2.0 立项即多源 LOSO（留一底物交叉验证）：对每个靶，历史 = 库内全部其他底物。", 18, true, DARK),
    T("两个事实（如实陈述）：", 16, true, ACCENT),
    T("① pair 负效应是 1.0 的遗留结果——2.0 没有重跑 pair（pair 轨配置但默认不跑）；", 15, false, DARK),
    T("② 本工作回答的不是「历史有没有用」，而是「多源历史以什么形式进入回路」：", 15, false, DARK),
    T("    作为代理模型标签？作为先验（条件清单）？还是完全不用？", 15, false, DARK),
  ]);

  // ---- 4 protocol ----
  s = slide("冻结协议（五库完全一致，预注册后不改）");
  const rows = [
    ["评价单位", "leave-one-substrate-out：目标底物外全部底物 = 历史池（多源）"],
    ["初始点", "n_init = 5（前 5 步 = 清单 init；清单 = 历史跨源产率均值 top-5）"],
    ["优化器", "GP (Matern-2.5 ARD) + EI；target-only（历史不经 GP）"],
    ["预算", "B = 20（5 init + 15 续跑）；seeds 0–4"],
    ["指标", "主指标 AUC@20；诊断 AUC@5 / init_best / final_best / 命中 top-5%"],
    ["统计", "seed 平均 → 靶级 → 配对 bootstrap 95% CI（B=5000）；双对照"],
  ];
  s.addTable(rows.map((r) => r.map((c, j) => ({ text: c, options: { fontSize: 13, bold: j === 0, color: j === 0 ? ACCENT : DARK, fill: { color: j === 0 ? LIGHT : WHITE } } }))), {
    x: 0.7, y: 1.5, w: 12.0, colW: [2.2, 9.8], rowH: 0.55, fontFace: "Microsoft YaHei", border: { type: "solid", color: "CCCCCC", pt: 0.5 }, valign: "middle",
  });
  txt(s, 0.7, 5.8, 12.2, 1.0, [
    T("数据：胺化 15×260（Pd C–N）· 硼化 33×46（Ni C–B）· EDBO Suzuki 12×308（Pd C–C）· HiTEA 11×41–48（Pfizer 独立源）· CHAOS 4×720（一维边界）", 13, false, GRAY),
  ]);

  // ---- 5 main finding ----
  s = slide("主发现：池化 top-5 清单是唯一跨库一致的正策略", "Table 1：四库 × 双对照的 AUC@20 差异（配对标靶 bootstrap 95% CI）");
  s.addImage({ path: FIG + "fig1_main_forest.png", x: 0.6, y: 1.5, w: 12.1 });
  txt(s, 0.7, 5.8, 12.2, 1.3, [
    T("四个库方向全为正；两个完整网格库（胺化 +160、硼化 +108）CI 排除 0，87–91% 靶为正。", 15, true, DARK),
    T("EDBO Suzuki vs random 较弱（+92，CI 含 0）——因为该模板冷启动 BO 本身不可靠（随机会更强），属于「可部署性受限」而非「无效」。", 13, false, GRAY),
  ]);

  // ---- 6 BSF ----
  s = slide("增益是「更快」，不是「更高」：第 1 轮即拉开差距", "胺化 best-so-far 曲线（靶级均值，20 步）");
  s.addImage({ path: FIG + "fig2_bsf_amination.png", x: 0.7, y: 1.5, w: 7.6 });
  txt(s, 8.7, 1.7, 4.3, 4.5, [
    T("清单把「第 1 轮（前 5 步）」的最好结果直接抬到约 62→66 产率", 15, true, DARK),
    T("init_best 差异（vs cold）：胺化 +12.3 · 硼化 +8.6（均排除 0）", 13, false, DARK),
    T("final_best 差异（20 步终点，vs cold）：胺化 +2.2 · 硼化 +0.3（CI 含 0，≈ 拉平）", 13, false, DARK),
    T("历史的价值 = 更好的起点；终点基本不变——「更快到达同一目标」。", 15, true, DARK),
  ]);

  // ---- 7 faster not higher ----
  s = slide("价值位置是库相关的：init 通道 vs 续跑通道", "Table 3 分解（vs cold，AUC@20）；EDBO Suzuki 例外——优势在后段");
  s.addImage({ path: FIG + "fig3_init_final.png", x: 0.6, y: 1.5, w: 8.6 });
  txt(s, 9.4, 1.8, 3.7, 4.2, [
    T("init 主导型", 14, true, ACCENT), T("：胺化、硼化——清单即结论，EI 续跑增益弱（C1 含 0）", 13, false, DARK),
    T("后段主导型", 14, true, RED), T("：EDBO Suzuki——清单起点弱（init CI 含 0），但 EI 续跑吃下交互结构（final +5.3 排除 0）", 13, false, DARK),
    T("两通道皆弱", 14, true, GRAY), T("：HiTEA 小空间+高噪声，总效应 +26 方向正但 CI 含 0", 13, false, DARK),
  ]);

  // ---- 8 what fails ----
  s = slide("什么无效：把历史产率迁入代理模型（null 或有害）");
  s.addImage({ path: FIG + "fig5_four_arms.png", x: 0.6, y: 1.5, w: 8.9 });
  txt(s, 9.7, 1.7, 3.5, 4.6, [
    T("sim_weighted（相似度加权）", 14, true, DARK), T("：胺化 +19.3，CI 含 0——null", 13, false, DARK),
    T("safe_gate（Spearman 门）", 14, true, DARK), T("：胺化 +11.5，CI 含 0——null", 13, false, DARK),
    T("warm 续跑（四臂实验，n=23）", 14, true, RED), T("：历史 warm 点不占预算，却显著变差（B vs A −59.1）", 13, false, DARK),
    T("匹配 init 审计（胺化）", 14, true, ACCENT), T("：给定 top-5 起点后 EI 边际仅 +26（含 0）——历史管起点，优化器管精修", 13, false, DARK),
  ]);

  // ---- 9 mechanism ----
  s = slide("机制：多源池化 = 排序聚合；排序可迁移，数值不可迁移");
  s.addImage({ path: FIG + "fig4_rank_pres.png", x: 0.6, y: 1.6, w: 6.9 });
  txt(s, 7.9, 1.6, 5.2, 5.0, [
    T("化学根源", 16, true, ACCENT),
    T("条件好坏排序 ← 配体（位阻/供电子性）与碱（碱性/溶解性）——对模板内所有底物一致", 14, false, DARK),
    T("产率水平 ← 底物自身反应活性（芳卤电子效应/位阻）——底物特异", 14, false, DARK),
    T("因此：排序跨底物保持（ρ 全部为正），数值不可比；极端位阻冲突使保持「部分」化 → 只取顶部 5 个", 14, true, DARK),
    T("池化的意义：跨底物排序投票 = 平均掉特异噪声，留下模板通用主效应——这就是「分离通用性质与底物特异性质」的实现", 14, true, DARK),
    T("额外证据：CHAOS 一维边界 0.694（五库最高），4/4 靶正——机制不依赖多维条件结构", 13, false, GRAY),
  ]);

  // ---- 10 dual channel ----
  s = slide("双通道机制：初始化价值 × 续跑价值 = 独立的两个决策");
  s.addImage({ path: FIG + "fig6_quadrant.png", x: 0.6, y: 1.5, w: 6.6 });
  s.addTable([
    ["初始化价值", "续跑价值", "部署建议"],
    ["高", "高", "清单 init + target-only BO（两库都做）"],
    ["高", "低", "只做清单一轮，少续跑/不续跑"],
    ["低", "高", "冷启动/多样化 init + BO"],
    ["低", "低", "弃权：不用这份历史，重新建模或扩大设计空间"],
  ].map((r) => r.map((c, j) => ({ text: c, options: { fontSize: j === 0 ? 12 : 11, bold: j === 0, color: (j === 2 && c === "弃权：不用这份历史，重新建模或扩大设计空间") ? RED : DARK, fill: { color: j === 0 ? DARK : (c.startsWith("弃") ? "FDECEA" : WHITE) } } }))), {
    x: 7.5, y: 1.6, w: 5.3, colW: [1.5, 1.5, 2.3], rowH: 0.62, fontFace: "Microsoft YaHei", border: { type: "solid", color: DARK, pt: 0.75 }, valign: "middle",
  });
  txt(s, 7.5, 4.9, 5.5, 1.6, [
    T("事前预测续跑价值（additive R² 分档）已被证伪——暂无可靠事前规则；", 13, false, GRAY),
    T("续跑决策按库型选：init 型库 EI 可选，Suzuki 类 EI 必选；探针测量排序保持是下一步。", 13, false, GRAY),
  ]);

  // ---- 11 rejected strategies ----
  s = slide("被 AUC@20 否决的策略（负证据与正证据同框）", "Table 3：每个「自然的直觉」都让数据给出了答案");
  const rejRows = [
    ["相似度加权 pooled GP", "相似底物共享产率水平", "胺化 null（+19.3，CI 含 0）", "不默认使用"],
    ["Spearman 安全门", "少量目标响应可信", "胺化 null（+11.5，CI 含 0）", "当前版不可部署"],
    ["rank 中位数清单", "聚合抗尺度变化", "pooled +1.5（CI 含 0），仅 Suzuki 类边缘", "默认保持 mean"],
    ["历史 warm 进续跑 GP", "更多历史 → 更好后验", "显著变差（B vs A −59.1）", "历史只用于 init"],
    ["additive-R² 续跑规则", "表面结构预测续跑价值", "分档失败（p=0.69）", "无可靠事前规则"],
    ["元特征预测迁移增益", "任务属性可判别增益", "跨库判别 AUC ≈ 0.47（随机）", "不能自动选策略"],
    ["最近邻单源迁移", "最相似底物是最好的供体", "从未超过池化", "池化，不要挑单个"],
  ];
  s.addTable([
    ["策略/假设", "最初动机", "AUC@20 结果", "结论"],
    ...rejRows.map((r) => r.map((c, j) => ({ text: c, options: { fontSize: 11, bold: j === 3, color: j === 3 ? RED : DARK, fill: { color: (j === 3) ? "FDECEA" : (j === 0 ? LIGHT : WHITE) } } }))),
  ], {
    x: 0.6, y: 1.55, w: 12.1, colW: [2.9, 3.2, 3.4, 2.6], rowH: 0.62, fontFace: "Microsoft YaHei", border: { type: "solid", color: "BBBBBB", pt: 0.5 }, valign: "middle",
  });

  // ---- 12 boundaries ----
  s = slide("边界与局限（如实收窄）");
  const bounds = [
    ["跨反应类与跨源", "四库 = 3 个反应类 + 2 个独立数据源（Doyle / Pfizer）；方向一致，但 n=4 库级统计力有限", "强"],
    ["回顾性，非前瞻", "全部为 LOSO 回放；湿实验前瞻验证已预注册（SNAr 模板，128 条件空间）", "中"],
    ["排序保持是相关不是因果", "库级机制支持 + 一维边界一致；尚无靶级可靠预测器", "中"],
    ["未做 plate/batch 校正", "plate_id 是逻辑任务标签；HiTEA 仅一个跨批次样本 → 跨板迁移列为未来工作", "弱"],
    ["统计边界", "5 seeds、单次测量、无噪声重放；靶级 CI 全程报告", "中"],
  ];
  bounds.forEach((r, i) => {
    const y = 1.5 + i * 1.05;
    txt(s, 0.7, y, 3.0, 0.9, [T(r[0], 15, true, DARK)]);
    txt(s, 3.8, y, 7.9, 0.9, [T(r[1], 14, false, GRAY)]);
    txt(s, 11.8, y, 1.2, 0.5, [T("证据: " + r[2], 13, true, r[2] === "强" ? GREEN : r[2] === "弱" ? RED : ACCENT)]);
  });

  // ---- 13 deployment ----
  s = slide("部署规则（可执行默认）");
  const rules = [
    ["1", "源数门槛", "历史底物 ≥3 才启用池化；≥5 推荐；n=1 单源清单不稳定（Jaccard ≈ 0.17）"],
    ["2", "清单", "跨源产率均值排序取 top-5（默认 mean 规则）"],
    ["3", "报告", "逐条件报 source coverage（清单跨源稳定性 0.11–0.40，必须透明）"],
    ["4", "续跑", "按库型：init 型库 EI 可选（清单够用）；Suzuki 类 EI 必选（后段是价值所在）"],
    ["5", "弃权", "两通道都不为正时，不迁移（abstain 是合法默认）"],
    ["6", "口径", "相对指标：AUC@k / 命中 top-5% / 轮次；禁止承诺绝对产率"],
  ];
  rules.forEach((r, i) => {
    const y = 1.5 + i * 0.88;
    s.addShape("ellipse", { x: 0.7, y, w: 0.5, h: 0.5, fill: { color: ACCENT }, line: { type: "none" } });
    s.addText(r[0], { x: 0.7, y, w: 0.5, h: 0.5, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: "Microsoft YaHei" });
    txt(s, 1.4, y + 0.02, 2.2, 0.5, [T(r[1], 16, true, DARK)]);
    txt(s, 3.6, y + 0.02, 9.3, 0.6, [T(r[2], 14, false, GRAY)]);
  });

  // ---- 14 conclusion ----
  s = P.addSlide();
  s.background = { color: DARK };
  s.addText("结论：扔掉大部分历史，留下五个条件", { x: 0.9, y: 0.7, w: 11.5, h: 0.9, fontSize: 30, bold: true, color: WHITE, fontFace: "Microsoft YaHei" });
  txt(s, 0.9, 1.9, 11.6, 2.9, [
    T("1. 唯一可靠的正增益做法：多源池化 top-5 条件清单作第 1 轮 + target-only EI（+160 / +108 AUC vs cold，CI 排除 0）", 17, false, WHITE),
    T("2. 历史产率迁入代理模型：null 或负；warm 续跑显著负——初始化与「喂标签」是两个不同的干预", 17, false, WHITE),
    T("3. 化学根基：同一模板内排序由配体/碱的本征性质决定（通用），水平由底物活性决定（特异）→ 排序可迁移、数值不可", 17, false, WHITE),
    T("4. 应用：≥3/≥5 源池化、报 coverage、按库型选续跑、两通道皆弱时弃权", 17, false, WHITE),
  ]);
  txt(s, 0.9, 5.3, 11.6, 1.6, [
    T("一句定位：TransferBO 2.0 的贡献不是更复杂的 surrogate 迁移模型，", 15, true, GOLD),
    T("而是在多库序贯优化中证明：历史反应数据最稳健的用途是形成跨底物排序保持的高价值条件清单。", 15, true, GOLD),
    T("下一步：湿实验前瞻验证（已预注册）· SI 表格 · 正文终稿", 14, false, "BDD7EE"),
  ]);

  await P.writeFile({ fileName: "results/presentation/TransferBO2_report.pptx" });
  console.log("saved results/presentation/TransferBO2_report.pptx");
};

main().catch((e) => { console.error(e); process.exit(1); });
