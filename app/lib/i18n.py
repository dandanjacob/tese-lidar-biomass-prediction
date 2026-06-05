"""
Internacionalização (i18n).

Texto da interface fica em dois lugares, ambos editáveis ao vivo:

1. Strings curtas (labels, títulos, métricas) → app/locales/<lang>.json
   Uso: t("home.title"), t("intersections.all_subheader", n=42)

2. Textos longos em markdown (prosa, tabelas) → app/locales/<lang>/<chave>.md
   Uso: md("geometry_help")  → carrega locales/pt/geometry_help.md
   Escreva markdown normal, com quebras de linha reais — sem escape.

Ambos fazem fallback para o idioma padrão e recarregam no navegador ao salvar
(cache invalidado por mtime + watcher dos arquivos).
"""

import json
import re
from pathlib import Path

import streamlit as st

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LANG = "pt"

# Idiomas disponíveis: code → nome exibido no seletor.
# Para adicionar um idioma, crie locales/<code>.json e registre-o aqui.
LANGUAGES = {"pt": "Português", "en": "English"}


@st.cache_data
def _read_locale(lang: str, mtime: float) -> dict:
    # mtime entra na chave de cache: editar o JSON muda o mtime e invalida o cache,
    # então o texto novo aparece sem precisar reiniciar o app.
    path = LOCALES_DIR / f"{lang}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_locale(lang: str) -> dict:
    path = LOCALES_DIR / f"{lang}.json"
    return _read_locale(lang, path.stat().st_mtime)


@st.cache_data
def _read_md(path: str, mtime: float) -> str:
    # mtime na chave de cache → editar o .md invalida o cache (recarga ao vivo).
    with open(path, encoding="utf-8") as f:
        return f.read()


def md(key: str) -> str:
    """Carrega o markdown longo de locales/<lang>/<key>.md.

    Faz fallback para o idioma padrão e, por fim, sinaliza arquivo faltante.
    """
    lang = get_lang()
    path = LOCALES_DIR / lang / f"{key}.md"
    if not path.exists() and lang != DEFAULT_LANG:
        path = LOCALES_DIR / DEFAULT_LANG / f"{key}.md"
    if not path.exists():
        return f"_(markdown faltando: {key})_"
    return _read_md(str(path), path.stat().st_mtime)


_LIVE_RELOAD_STARTED = False


def enable_live_reload():
    """Faz o navegador recarregar sozinho ao salvar um locales/*.json.

    O watcher nativo do Streamlit só observa arquivos .py; aqui registramos os
    .json e .md de locales/ e disparamos um rerun das sessões ativas quando algum
    deles muda. Best-effort: usa APIs internas do Streamlit, então qualquer falha
    é ignorada (o texto novo ainda aparece no próximo rerun via cache por mtime).
    """
    global _LIVE_RELOAD_STARTED
    if _LIVE_RELOAD_STARTED:
        return
    try:
        from streamlit.runtime.runtime import Runtime
        from streamlit.watcher.path_watcher import watch_file
    except Exception:
        return

    def _on_change(_path):
        try:
            rt = Runtime.instance()
            for info in rt._session_mgr.list_active_sessions():
                info.session.request_rerun(None)
        except Exception:
            pass

    for f in [*LOCALES_DIR.glob("*.json"), *LOCALES_DIR.glob("*/*.md")]:
        try:
            watch_file(str(f), _on_change)
        except Exception:
            pass
    _LIVE_RELOAD_STARTED = True


def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def _dig(data: dict, key: str):
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def t(key: str, **kwargs) -> str:
    """Retorna o texto da chave no idioma atual.

    Faz fallback para o idioma padrão e, por fim, para a própria chave (útil
    para identificar traduções faltantes). kwargs são interpolados via str.format.
    """
    lang = get_lang()
    val = _dig(_load_locale(lang), key)
    if val is None and lang != DEFAULT_LANG:
        val = _dig(_load_locale(DEFAULT_LANG), key)
    if val is None:
        return key
    if kwargs and isinstance(val, str):
        return val.format(**kwargs)
    return val


def _glossary() -> dict:
    """Mapa sigla → forma por extenso (chave 'glossary' no JSON do idioma)."""
    return (_dig(_load_locale(get_lang()), "glossary")
            or _dig(_load_locale(DEFAULT_LANG), "glossary") or {})


def _wrap_acronyms(segment: str, glo: dict) -> str:
    # casa siglas mais longas primeiro (ex.: "REDD+" antes de "RE"); usa limites
    # próprios em vez de \b porque há siglas com + e / (REDD+, Mg/ha).
    keys = sorted(glo, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w])")

    def repl(m):
        s = m.group(1)
        full = glo[s].replace('"', "'")
        return (f'<abbr title="{full}" style="cursor:help; text-decoration:none;">{s}'
                f'<sup style="font-size:0.7em; opacity:0.55; margin-left:1px;">ⓘ</sup></abbr>')

    return pattern.sub(repl, segment)


def with_acronyms(text: str) -> str:
    """Marca cada sigla do glossário com um ícone ⓘ e tooltip (forma por extenso).

    Renderize o resultado com unsafe_allow_html=True, ex.:
        st.markdown(with_acronyms(md("home_intro")), unsafe_allow_html=True)
        st.caption(with_acronyms(t("biomass.caption")), unsafe_allow_html=True)

    Trechos de código (entre crases ` ou cercas ```) são preservados intactos.
    """
    glo = _glossary()
    if not glo:
        return text
    parts = re.split(r"(```.*?```|`[^`]*`)", text, flags=re.DOTALL)
    return "".join(p if p.startswith("`") else _wrap_acronyms(p, glo) for p in parts)


def language_selector():
    """Seletor de idioma na sidebar. Persiste a escolha em st.session_state['lang']."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = DEFAULT_LANG
    st.sidebar.selectbox(
        t("common.language"),
        options=list(LANGUAGES.keys()),
        format_func=lambda c: LANGUAGES[c],
        key="lang",
    )
