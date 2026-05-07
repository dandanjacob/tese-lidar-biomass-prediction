.PHONY: help install compile kml intersections clip pipeline notebook

# Mostra este menu de ajuda
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Ambiente ──────────────────────────────────────────────────────────────────

install: ## Instala dependências fixadas em requirements.txt
	uv pip sync requirements.txt

compile: ## Recompila requirements.txt a partir de requirements.in (atualiza versões)
	uv pip compile requirements.in -o requirements.txt

# ── Pipeline de dados ─────────────────────────────────────────────────────────
# Pré-requisito: baixar os dados brutos manualmente no ORNL DAAC (ver README)
#   LiDAR:      data/raw/lidar/
#   Inventário: data/raw/inventory/

kml: ## [Etapa 1] Extrai KMLs dos KMZs do inventário → data/processed/kml/
	bash src/extract_kml.sh

intersections: ## [Etapa 2] Cruza plots de inventário × tiles LiDAR → data/processed/intersections/
	python src/find_intersections.py

clip: ## [Etapa 3] Recorta nuvens de pontos por parcela → data/processed/clipped_lidar/
	python src/clip_lidar_to_plots.py

pipeline: kml intersections clip ## Roda as 3 etapas em sequência (requer dados brutos em data/raw/)

# ── Exploração ────────────────────────────────────────────────────────────────

notebook: ## Abre o JupyterLab
	jupyter lab notebooks/
