"""Apêndice — auditoria de qualidade de dados (docs/known-issues.md)."""

from pathlib import Path

import streamlit as st

from lib.i18n import t

st.title(t("qualidade.title"))
st.caption(t("qualidade.caption"))

_path = Path(__file__).resolve().parent.parent.parent / "docs" / "known-issues.md"
if _path.exists():
    st.markdown(_path.read_text(encoding="utf-8"))
else:
    st.warning(f"Arquivo não encontrado: {_path}")
