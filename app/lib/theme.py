"""Paleta de cores, configuração de página e camada visual "vidro" compartilhadas."""

import streamlit as st

from lib.i18n import t

# Paleta ancorada no assunto: verde-dossel (acento), azul-ardósia (tiles LiDAR),
# âmbar/ferrugem para os estados de aviso/crítico — mesmo vocabulário do mapa de
# cobertura (verde=usável, vermelho=sem rótulo, cinza=sem LiDAR).
C_CANOPY = "#2E6B4E"
C_LIDAR = "#3E6E9E"
C_AMBER = "#B0781E"
C_RUST = "#B5432F"

# Compatibilidade com nomes antigos usados nas páginas (azul/vermelho dos gráficos
# e suas variantes claras, usadas em bandas/áreas de destaque).
C_BLUE = C_LIDAR
C_RED = C_RUST
C_LIGHT = "#a8d4f5"
C_PINK = "#f5a8a8"


def page_config():
    st.set_page_config(page_title=t("common.page_title"), page_icon="🌳", layout="wide")
    _inject_glass_css()


def _inject_glass_css():
    """Vidro (blur) nas superfícies flutuantes — sidebar, métricas, botões, expanders.

    O corpo do texto permanece em branco puro (convenção acadêmica); o efeito de
    vidro só existe sobre um wash de gradiente quase imperceptível no fundo do app
    — sem esse wash por baixo, o backdrop-filter não tem o que desfocar.
    """
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background-image:
            radial-gradient(120% 60% at 85% -5%, rgba(46,107,78,0.055), transparent 60%),
            radial-gradient(90% 50% at 5% 8%, rgba(62,110,158,0.045), transparent 55%);
        background-attachment: fixed;
    }

    [data-testid="stSidebar"] {
        background: rgba(255,255,255,0.55);
        border-right: 1px solid rgba(255,255,255,0.7);
        backdrop-filter: blur(18px) saturate(170%);
        -webkit-backdrop-filter: blur(18px) saturate(170%);
    }

    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.55);
        border: 1px solid rgba(255,255,255,0.75);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        backdrop-filter: blur(16px) saturate(160%);
        -webkit-backdrop-filter: blur(16px) saturate(160%);
        box-shadow: 0 8px 24px rgba(24,40,30,0.07);
    }

    .stButton > button, .stDownloadButton > button {
        background: rgba(255,255,255,0.6);
        border: 1px solid rgba(255,255,255,0.8);
        border-radius: 12px;
        backdrop-filter: blur(12px) saturate(160%);
        -webkit-backdrop-filter: blur(12px) saturate(160%);
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(24,40,30,0.12);
    }
    .stButton > button[kind="primary"] {
        background: rgba(46,107,78,0.92);
        border: 1px solid rgba(46,107,78,1);
    }

    [data-testid="stExpander"] {
        background: rgba(255,255,255,0.5);
        border: 1px solid rgba(255,255,255,0.7);
        border-radius: 14px;
        backdrop-filter: blur(14px) saturate(160%);
        -webkit-backdrop-filter: blur(14px) saturate(160%);
    }

    div[data-baseweb="select"] > div, div[data-baseweb="segmented-control"] {
        background: rgba(255,255,255,0.6);
        border-radius: 10px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }

    /* trilha de leitura fica mais estreita em telas largas — legibilidade do texto corrido */
    .prose-col { max-width: 74ch; }
    </style>
    """, unsafe_allow_html=True)
