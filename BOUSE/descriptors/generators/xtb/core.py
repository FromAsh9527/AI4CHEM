# -*- coding: utf-8 -*-
"""xTB 半经验量子化学描述符（GFN-xTB，需 xtb 可执行文件）。

产出特征（每分子一行）::

    xtb_total_energy_eh   总能量（Hartree）
    xtb_homo_ev           HOMO 能量（eV）
    xtb_lumo_ev           LUMO 能量（eV）
    xtb_gap_ev            HOMO-LUMO 能隙（eV）
    xtb_dipole_debye      偶极矩（Debye）
    xtb_alpha_au          静态偶极极化率 α(0)（a.u.）
    xtb_q_min/q_max       Mulliken 原子电荷极值（e）
    xtb_q_mean_abs        原子电荷绝对值均值（e）
    xtb_q_std             原子电荷标准差（e）
    xtb_n_atoms           重原子+氢总数

xtb 可执行文件查找顺序::

    1) compute(..., xtb=显式路径) / CLI --xtb
    2) 环境变量 XTB_EXE
    3) PATH 中的 xtb
    4) <AI-Pharmacy>/third_party/ 下的官方发行版（glob xtb.exe）
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generators.common import drop_all_nan_features, mol_from_smiles  # noqa: E402
from io_utils import ID_COL  # noqa: E402

_XTB_SEARCH_ROOT = Path(__file__).resolve().parents[5] / "third_party"

_RE_ORB_LINE = re.compile(
    r"^\s*(\d+)\s+(\d\.\d{3,5})\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$"
)
_RE_HOMO_EV = re.compile(r"^\s*\d+\s+[\d.]+\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\(HOMO\)", re.M)
_RE_LUMO_EV = re.compile(r"^\s*\d+\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\(LUMO\)", re.M)
_RE_TOTAL_E = [
    re.compile(r"::\s*total energy\s+(-?[\d.]+)", re.IGNORECASE),
    re.compile(r"TOTAL ENERGY\s+(-?[\d.]+)\s*Eh", re.IGNORECASE),
]
_RE_GAP = [
    re.compile(r"HL-Gap\s+[\d.]+\s*Eh\s+(-?[\d.]+)", re.IGNORECASE),
    re.compile(r"HOMO\s*-\s*LUMO\s+GAP[^\d-]*(-?[\d.]+)", re.IGNORECASE),
    re.compile(r"HOMO-LUMO gap[^\d-]*(-?[\d.]+)", re.IGNORECASE),
]
_RE_ALPHA = re.compile(r"\(0\)\s*/au\s*:\s*(-?[\d.]+)")
_RE_DIPOLE = re.compile(
    r"full:\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", re.IGNORECASE
)


def find_xtb(xtb: str | Path | None = None) -> Path:
    """按优先级定位 xtb 可执行文件。"""
    if xtb:
        p = Path(xtb)
        if p.is_file():
            return p
        raise FileNotFoundError(f"指定的 xtb 不存在: {p}")
    env_exe = os.environ.get("XTB_EXE")
    if env_exe and Path(env_exe).is_file():
        return Path(env_exe)
    on_path = shutil.which("xtb") or shutil.which("xtb.exe")
    if on_path:
        return Path(on_path)
    if _XTB_SEARCH_ROOT.is_dir():
        hits = sorted(_XTB_SEARCH_ROOT.glob("**/xtb.exe")) or sorted(
            _XTB_SEARCH_ROOT.glob("**/xtb")
        )
        if hits:
            return hits[0]
    raise FileNotFoundError(
        "找不到 xtb 可执行文件。请：\n"
        "  1) 下载官方 Windows 版解压到 third_party/xtb/（grimme-lab/xtb releases）；或\n"
        "  2) 设环境变量 XTB_EXE 指向 xtb.exe；或\n"
        "  3) 用 CLI 参数 --xtb 显式指定。"
    )


def _xtb_env(exe: Path) -> dict:
    """设置参数文件搜索路径（官方发行版 share/xtb 与 bin/ 同级）。"""
    env = dict(os.environ)
    share = exe.parent.parent / "share" / "xtb"
    if share.is_dir():
        prev = env.get("XTBPATH", "")
        env["XTBPATH"] = str(share) + (os.pathsep + prev if prev else "")
    return env


def _smiles_to_xyz(smi: str) -> tuple[str | None, str | None]:
    """SMILES → 3D XYZ 文本（ETKDG 构象 + MMFF/UFF 预优化）。失败返回 (None, 原因)。"""
    mol = mol_from_smiles(smi)
    if mol is None:
        return None, "invalid_smiles"
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(mol, params) != 0:
        return None, "embed_failed"
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=200)
    except Exception:
        pass  # 预优化失败仍可用原始构象
    return Chem.MolToXYZBlock(mol), None


def _parse_orbitals(text: str) -> tuple[float | None, float | None]:
    """取 HOMO/LUMO（eV）：优先读显式 (HOMO)/(LUMO) 标记，否则走轨道表推算。"""
    m_homo = _RE_HOMO_EV.search(text)
    m_lumo = _RE_LUMO_EV.search(text)
    if m_homo and m_lumo:
        return float(m_homo.group(2)), float(m_lumo.group(2))
    homo = lumo = None
    for m in _RE_ORB_LINE.finditer(text):
        occ, ev = float(m.group(2)), float(m.group(4))
        if occ >= 1.0:
            homo = ev  # 持续后移，末值即 HOMO
        elif homo is not None and lumo is None:
            lumo = ev
            break
    return homo, lumo


def _parse_first(patterns: list[re.Pattern], text: str) -> float | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _parse_charges(path: Path, n_atoms: int) -> dict[str, float]:
    if not path.is_file():
        return {}
    vals = []
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            vals.append(float(line.split()[0]))
        except ValueError:
            continue
    if n_atoms and len(vals) != n_atoms:
        return {}
    q = np.asarray(vals)
    return {
        "xtb_q_min": float(q.min()),
        "xtb_q_max": float(q.max()),
        "xtb_q_mean_abs": float(np.abs(q).mean()),
        "xtb_q_std": float(q.std()),
    }


def _run_one(
    exe: Path,
    smi: str,
    *,
    gfn: int,
    opt: bool,
    charge: int,
    uhf: int,
    timeout: int,
    env: dict,
) -> tuple[dict | None, str | None]:
    """单分子 xTB 计算。成功返回 (特征 dict, None)，失败返回 (None, 原因)。"""
    xyz, err = _smiles_to_xyz(smi)
    if err:
        return None, err
    n_atoms = len(xyz.strip().splitlines()) - 2

    with tempfile.TemporaryDirectory(prefix="bouse_xtb_") as scratch:
        mol_file = Path(scratch) / "mol.xyz"
        mol_file.write_text(xyz, encoding="utf-8")
        cmd = [str(exe), "mol.xyz", "--gfn", str(gfn), "--chrg", str(charge), "--uhf", str(uhf)]
        if opt:
            cmd.append("--opt")
        try:
            proc = subprocess.run(
                cmd,
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return None, f"timeout>{timeout}s"

        out = proc.stdout or ""
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
            return None, f"xtb_rc{proc.returncode}: {tail[:200]}"

        total_e = _parse_first(_RE_TOTAL_E, out)
        if total_e is None:
            return None, "parse_failed(total_energy)"
        homo, lumo = _parse_orbitals(out)
        gap = (lumo - homo) if (homo is not None and lumo is not None) else _parse_first(_RE_GAP, out)
        dip = _RE_DIPOLE.search(out)
        alpha = _RE_ALPHA.search(out)

        feat = {
            "xtb_total_energy_eh": total_e,
            "xtb_homo_ev": homo if homo is not None else float("nan"),
            "xtb_lumo_ev": lumo if lumo is not None else float("nan"),
            "xtb_gap_ev": gap if gap is not None else float("nan"),
            "xtb_dipole_debye": float(dip.group(4)) if dip else float("nan"),
            "xtb_alpha_au": float(alpha.group(1)) if alpha else float("nan"),
            "xtb_n_atoms": float(n_atoms),
        }
        feat.update(_parse_charges(Path(scratch) / "charges", n_atoms))
        return feat, None


def compute(
    molecules: pd.DataFrame,
    *,
    xtb: str | Path | None = None,
    gfn: int = 2,
    opt: bool = False,
    timeout: int = 300,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    SMILES → xTB 描述符表。

    Parameters
    ----------
    xtb :   xtb 可执行文件路径（默认按 find_xtb 顺序查找）
    gfn :   GFN 级别 0/1/2（默认 2）
    opt :   True 时先 GFN-xTB 几何优化再取性质（慢 3~10 倍）
    timeout : 单分子超时秒数
    """
    if ID_COL not in molecules.columns or "smiles" not in molecules.columns:
        raise ValueError("molecules 需含 molecule_id 与 smiles")
    if gfn not in (0, 1, 2):
        raise ValueError("gfn 必须是 0/1/2")

    exe = find_xtb(xtb)
    env = _xtb_env(exe)

    has_charge = "charge" in molecules.columns
    has_uhf = "uhf" in molecules.columns

    rows, failed = [], []
    total = len(molecules)
    for i, (_, r) in enumerate(molecules.iterrows(), 1):
        mid, smi = str(r[ID_COL]), str(r["smiles"])
        charge = int(r["charge"]) if has_charge and pd.notna(r["charge"]) else 0
        if has_uhf and pd.notna(r["uhf"]):
            uhf = int(r["uhf"])
        else:
            mol = mol_from_smiles(smi)
            uhf = int(Descriptors.NumRadicalElectrons(mol)) if mol is not None else 0
        feat, err = _run_one(
            exe, smi, gfn=gfn, opt=opt, charge=charge, uhf=uhf, timeout=timeout, env=env
        )
        if err:
            failed.append({ID_COL: mid, "smiles": smi, "reason": err})
        else:
            feat[ID_COL] = mid
            rows.append(feat)
        if i % 10 == 0 or i == total:
            print(f"  xtb 进度 {i}/{total}（失败 {len(failed)}）", flush=True)

    if not rows:
        return pd.DataFrame(), pd.DataFrame(failed)
    desc = drop_all_nan_features(pd.DataFrame(rows))
    feat_cols = [c for c in desc.columns if c != ID_COL]
    desc = desc[[ID_COL] + feat_cols]
    return desc, pd.DataFrame(failed)
