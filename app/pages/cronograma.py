"""Cronograma — o que já foi feito no projeto e o plano dos próximos passos."""

import streamlit as st

from lib.i18n import md, t, with_acronyms

st.title(t("cronograma.title"))
st.caption(with_acronyms(t("cronograma.caption")), unsafe_allow_html=True)
st.markdown(with_acronyms(md("cronograma")), unsafe_allow_html=True)
