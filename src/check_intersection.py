#!/usr/bin/env python3
"""
Verifica a intersecção entre os datasets LiDAR e inventário de campo por código de site.

Extrai o código de site do prefixo dos nomes de arquivo (parte antes do primeiro '_').
Trata a família FN (FN, FN1, FN2, FNA, FNC, FND) como grupo separado além do match exato.

Uso:
  python -m src.data.check_intersection
  python -m src.data.check_intersection --save
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "inventory"

# Descobre automaticamente os subdiretórios dos dois datasets
def _find_dataset_dir(prefix: str) -> Path | None:
    matches = [p for p in RAW.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    return matches[0] if matches else None


def site_code(filename: str) -> str:
    return filename.split("_")[0].upper()


def is_fn_family(code: str) -> bool:
    return bool(re.match(r"^FN[0-9A-Z]?$", code))


def fn_root(code: str) -> str:
    """FN1 → FN, FNA → FN, FN → FN."""
    return "FN" if is_fn_family(code) else code


def collect_sites(directory: Path, extensions: set[str]) -> dict[str, list[str]]:
    """
    Retorna dict: site_code → lista de nomes de arquivo (sem extensões excluídas).
    Ignora arquivos .sha256.
    """
    sites: dict[str, list[str]] = defaultdict(list)
    for f in directory.iterdir():
        if not f.is_file():
            continue
        if f.suffix == ".sha256":
            continue
        if extensions and f.suffix.lower() not in extensions:
            continue
        code = site_code(f.name)
        sites[code].append(f.name)
    return dict(sites)


def print_section(title: str, items: list, indent: int = 2) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for item in items:
        print(" " * indent + item)


def main() -> None:
    parser = argparse.ArgumentParser(description="Intersecção LiDAR × inventário de campo")
    parser.add_argument("--save", action="store_true", help="Salva relatório em data/raw/metadata/intersection_report.txt")
    args = parser.parse_args()

    lidar_dir = _find_dataset_dir("LiDAR_Forest_Inventory_Brazil_1644")
    inv_dir = _find_dataset_dir("Forest_Inventory_Brazil_2007")

    if not lidar_dir:
        raise FileNotFoundError(f"Diretório LiDAR não encontrado em {RAW}")
    if not inv_dir:
        raise FileNotFoundError(f"Diretório de inventário não encontrado em {RAW}")

    print(f"LiDAR dir:      {lidar_dir.name}")
    print(f"Inventário dir: {inv_dir.name}")

    lidar_sites = collect_sites(lidar_dir, {".laz", ".las"})
    inv_sites = collect_sites(inv_dir, {".csv", ".kmz", ".zip"})

    lidar_codes = set(lidar_sites)
    inv_codes = set(inv_sites)

    # --- Intersecção exata ---
    exact = sorted(lidar_codes & inv_codes)

    # --- Intersecção via família FN (ex: FN1/FN2 no LiDAR ↔ FN no inventário) ---
    fn_lidar = {c for c in lidar_codes if is_fn_family(c)}
    fn_inv = {c for c in inv_codes if is_fn_family(c)}
    fn_bridged = sorted(fn_lidar - inv_codes) if fn_inv - lidar_codes else []

    # --- Apenas LiDAR / apenas inventário ---
    lidar_only = sorted(lidar_codes - inv_codes - set(fn_bridged))
    inv_only = sorted(inv_codes - lidar_codes)

    # --- Resumo ---
    lines: list[str] = []

    lines.append("=" * 56)
    lines.append("INTERSECÇÃO LiDAR × INVENTÁRIO DE CAMPO")
    lines.append("=" * 56)

    lines.append(f"\n{'Sites LiDAR únicos:':<30} {len(lidar_codes)}")
    lines.append(f"{'Sites inventário únicos:':<30} {len(inv_codes)}")
    lines.append(f"{'Intersecção exata:':<30} {len(exact)}")
    if fn_bridged:
        lines.append(f"{'Via família FN:':<30} {len(fn_bridged)} (LiDAR) ↔ {sorted(fn_inv - lidar_codes)} (inventário)")

    lines.append("\n--- INTERSECÇÃO EXATA ---")
    for code in exact:
        n_lidar = len(lidar_sites[code])
        n_inv = len(inv_sites[code])
        lines.append(f"  {code:<6}  LiDAR: {n_lidar:>4} arquivos   Inventário: {n_inv:>3} arquivos")

    if fn_bridged:
        lines.append("\n--- FAMÍLIA FN (match por prefixo) ---")
        for code in sorted(fn_lidar):
            matched = sorted(fn_inv) if not lidar_codes >= fn_inv else [code]
            n_lidar = len(lidar_sites[code])
            inv_matches = ", ".join(f"{c}({len(inv_sites[c])})" for c in sorted(fn_inv))
            lines.append(f"  LiDAR {code:<6} ({n_lidar:>3} arq)  ↔  inventário: {inv_matches}")

    lines.append("\n--- APENAS LiDAR (sem inventário correspondente) ---")
    for code in lidar_only:
        lines.append(f"  {code:<6}  {len(lidar_sites[code]):>4} arquivos")

    lines.append("\n--- APENAS INVENTÁRIO (sem LiDAR correspondente) ---")
    for code in inv_only:
        lines.append(f"  {code:<6}  {len(inv_sites[code]):>3} arquivos")

    lines.append("")

    report = "\n".join(lines)
    print(report)

    if args.save:
        out = ROOT / "data" / "raw" / "metadata" / "intersection_report.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"Relatório salvo em: {out}")


if __name__ == "__main__":
    main()
