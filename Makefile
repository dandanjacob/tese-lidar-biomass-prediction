.PHONY: compile install check-intersection notebook

## Resolve o requirements.in e grava os hashes/versões fixadas em requirements.txt
compile:
	uv pip compile requirements.in -o requirements.txt

## Instala as dependências fixadas no requirements.txt
install:
	uv pip sync requirements.txt

## Mostra quais sites têm tanto LiDAR quanto inventário de campo (sem instalar nada extra)
check-intersection:
	python -m src.data.check_intersection

## Igual ao anterior, mas salva o relatório em data/raw/metadata/intersection_report.txt
check-intersection-save:
	python -m src.data.check_intersection --save

## Abre o JupyterLab no notebook de EDA
notebook:
	jupyter lab notebooks/01_eda.ipynb
