"""Helpers de gráficos reutilizáveis."""

import json

import plotly.express as px
import plotly.graph_objects as go

from lib.i18n import t, with_acronyms


def hist_with_stats(df, col, color, title, xlabel, bin_size=None):
    """Histograma plotly com linhas de média e mediana bem posicionadas.

    bin_size: largura fixa de classe (eixo X). Se None, usa 30 classes automáticas.
    """
    mean_val = df[col].mean()
    median_val = df[col].median()
    fig = px.histogram(df, x=col, nbins=30, color_discrete_sequence=[color],
                       labels={col: xlabel, "count": t("charts.frequency")})
    if bin_size:
        fig.update_traces(xbins=dict(start=0, size=bin_size))
    fig.add_vline(x=mean_val, line_dash="solid", line_color="#c0392b", line_width=2)
    fig.add_vline(x=median_val, line_dash="dash", line_color="#2c3e50", line_width=2)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="#c0392b", width=2, dash="solid"),
                             name=f"{t('charts.mean')}: {mean_val:.3f}"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="#2c3e50", width=2, dash="dash"),
                             name=f"{t('charts.median')}: {median_val:.3f}"))
    fig.update_layout(title=title, height=380, margin=dict(t=50),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig


def plot_shape(geom, color, axis_range=None, height=300):
    """Desenha o contorno de uma parcela (polígono) centrado, com eixos em metros
    e proporção 1:1. Aceita Polygon ou MultiPolygon; axis_range fixa a escala."""
    parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    cx, cy = geom.centroid.x, geom.centroid.y
    fig = go.Figure()
    for part in parts:
        xs, ys = part.exterior.xy
        fig.add_trace(go.Scatter(
            x=[x - cx for x in xs], y=[y - cy for y in ys],
            fill="toself", mode="lines", line=dict(color=color, width=2),
            fillcolor=color, opacity=0.35, showlegend=False,
        ))
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis_title="m", yaxis_title="m")
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    if axis_range:
        fig.update_xaxes(range=axis_range)
        fig.update_yaxes(range=axis_range, scaleanchor="x", scaleratio=1)
    return fig


# Posição (x%, y%) de cada nó no diagrama e as ligações entre eles (DAG ramificado).
# São estruturais — não dependem do idioma. Os textos vêm do JSON, casados por id.
PIPELINE_LAYOUT = {
    "lidar":        (11, 20),
    "inventario":   (11, 70),
    "kml":          (29, 48),
    "biomassa":     (33, 84),
    "interseccoes": (47, 33),
    "clip":         (67, 28),
    "modelo":       (90, 58),
}
PIPELINE_EDGES = [
    ("lidar", "interseccoes"),
    ("inventario", "kml"),
    ("inventario", "biomassa"),
    ("kml", "interseccoes"),
    ("interseccoes", "clip"),
    ("clip", "modelo"),
    ("biomassa", "modelo"),
]
# ordem em que as setas ◀ ▶ percorrem o fluxo
PIPELINE_ORDER = ["lidar", "inventario", "kml", "interseccoes", "clip",
                  "biomassa", "modelo"]


def _edge_path(x1, y1, x2, y2):
    """Linha reta entre dois nós (estilo do mockup, sem curvatura)."""
    return f"M {x1} {y1} L {x2} {y2}"


def pipeline_flow_html(steps):
    """HTML/SVG autônomo do pipeline ramificado, com navegação e transições suaves.

    Componente independente (roda no próprio iframe): clicar nas setas/bolas troca
    a etapa em destaque com animação CSS, sem disparar rerun do Streamlit. As demais
    etapas ficam esmaecidas; a descrição da etapa ativa aparece abaixo, sem caixa.
    """
    by_id = {s["id"]: s for s in steps}
    order = [i for i in PIPELINE_ORDER if i in by_id]
    nodes = [{
        "id": sid,
        "title": by_id[sid]["title"],
        "desc": with_acronyms(by_id[sid]["desc"]),
        "x": PIPELINE_LAYOUT[sid][0],
        "y": PIPELINE_LAYOUT[sid][1],
    } for sid in order]

    edges_svg = "".join(
        f'<path class="edge" data-a="{a}" data-b="{b}" '
        f'd="{_edge_path(*PIPELINE_LAYOUT[a], *PIPELINE_LAYOUT[b])}" />'
        for a, b in PIPELINE_EDGES
        if a in PIPELINE_LAYOUT and b in PIPELINE_LAYOUT
    )

    return (_FLOW_TEMPLATE
            .replace("__EDGES__", edges_svg)
            .replace("__STEPS__", json.dumps(nodes, ensure_ascii=False)))


_FLOW_TEMPLATE = """
<div id="flow">
  <div class="diagram">
    <svg class="edges" viewBox="0 0 100 100" preserveAspectRatio="none">__EDGES__</svg>
    <div id="nodes"></div>
  </div>
  <div id="desc"><div id="desc-title"></div><div id="desc-text"></div></div>
</div>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@600;700&display=swap');
  #flow{font-family:"Source Sans Pro",-apple-system,system-ui,sans-serif;color:#1a1a1a;padding:6px 4px 0;}
  /* alturas/tamanhos escalam com a largura (vw) para não sobrepor as bolas no celular */
  .diagram{position:relative;width:100%;height:clamp(250px,62vw,340px);}
  svg.edges{position:absolute;inset:0;width:100%;height:100%;overflow:visible;}
  .edge{fill:none;stroke:#4a4a4a;stroke-width:1.5;vector-effect:non-scaling-stroke;
        transition:stroke .45s ease,stroke-width .45s ease;}
  .edge.active{stroke:#111;stroke-width:2.5;}
  .node{position:absolute;transform:translate(-50%,-50%);cursor:pointer;z-index:1;}
  .node.active{z-index:3;}
  .bubble{width:clamp(44px,13vw,86px);height:clamp(44px,13vw,86px);border-radius:50%;
          display:flex;align-items:center;justify-content:center;text-align:center;box-sizing:border-box;
          padding:clamp(3px,1vw,8px);background:#a7adb3;color:#fff;
          font-size:clamp(8px,2.4vw,11px);line-height:1.16;transition:width .45s ease,height .45s ease,
          background .45s ease,font-size .45s ease,box-shadow .45s ease;}
  .node.dim .bubble{background:#bcc1c6;}
  .node.active .bubble{width:clamp(56px,17vw,120px);height:clamp(56px,17vw,120px);background:#141414;
                       font-size:clamp(10px,3vw,14px);font-weight:600;box-shadow:0 10px 28px rgba(0,0,0,.28);}
  #desc{min-height:150px;margin-top:6px;transition:opacity .25s ease;}
  #desc-title{font-family:"Oswald","Arial Narrow",sans-serif;font-weight:700;font-size:clamp(26px,7vw,40px);
              line-height:1.04;letter-spacing:.2px;color:#111;margin:0 0 10px;}
  #desc-text{font-size:15px;line-height:1.6;color:#3a3f45;max-width:760px;}
  #desc-text abbr{cursor:help;text-decoration:none;}
</style>
<script>
  const STEPS=__STEPS__;
  let active=0;
  const nodesEl=document.getElementById('nodes');
  const descEl=document.getElementById('desc');
  const titleEl=document.getElementById('desc-title');
  const textEl=document.getElementById('desc-text');

  STEPS.forEach((s,i)=>{
    const n=document.createElement('div');
    n.className='node';n.style.left=s.x+'%';n.style.top=s.y+'%';
    n.innerHTML='<div class="bubble"></div>';
    n.querySelector('.bubble').textContent=s.title;
    n.addEventListener('click',()=>setActive(i));
    nodesEl.appendChild(n);
  });
  const nodeEls=[...nodesEl.children];
  const edgeEls=[...document.querySelectorAll('.edge')];

  function paint(){
    const id=STEPS[active].id;
    nodeEls.forEach((el,i)=>{el.classList.toggle('active',i===active);el.classList.toggle('dim',i!==active);});
    edgeEls.forEach(e=>e.classList.toggle('active',e.dataset.a===id||e.dataset.b===id));
  }
  function fillDesc(){titleEl.textContent=STEPS[active].title;textEl.innerHTML=STEPS[active].desc;}
  function setActive(i){
    i=Math.max(0,Math.min(STEPS.length-1,i));
    if(i===active)return;
    active=i;paint();
    descEl.style.opacity=0;
    setTimeout(()=>{fillDesc();descEl.style.opacity=1;},180);
  }
  paint();fillDesc();
</script>
"""
