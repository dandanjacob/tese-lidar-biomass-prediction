# tese-lidar-biomass-prediction

Repositório da dissertação de mestrado em matemática aplicada. O objetivo é estimar biomassa florestal a partir de imagens Landsat, usando dados LiDAR da NASA como substituto de inventário de campo.

## Pipeline

```
LiDAR bruto (ORNL DAAC 1515)
    └── grade 30m sobre cada footprint
        └── métricas LiDAR por célula (altura, cobertura de dossel, densidade)
            └── equação alométrica → biomassa (Mg/ha) por célula
                └── par (bandas Landsat, biomassa) → dataset de treino
                    └── modelo de deep learning
```

## Estrutura

```
data/
  raw/lidar/              # arquivos .las/.laz do ORNL DAAC 1515 (não versionado)
  raw/landsat/            # imagens Landsat brutas (não versionado)
  processed/
    lidar_metrics/        # métricas por célula 30m extraídas da nuvem de pontos
    biomass_grid/         # grade de biomassa estimada via equação alométrica
  training/               # pares (features Landsat, biomassa) prontos para treino

src/
  ingestion/              # download ORNL DAAC e Landsat
  lidar/                  # processamento da nuvem de pontos e extração de métricas
  allometry/              # equações alométricas e aplicação à grade
  model/                  # arquitetura e treino do modelo

config/
  allometry.yaml          # equações e parâmetros alométricos (a definir)
  pipeline.yaml           # resolução da grade, bandas Landsat, splits de treino

notebooks/
  results/                # visualizações e análises exploratórias
```

## Dependências

Gerenciado com [uv](https://github.com/astral-sh/uv). Para instalar o ambiente:

```bash
uv sync
```

## Dados

- **LiDAR**: [ORNL DAAC 1515](https://doi.org/10.3334/ORNLDAAC/1515) — requer conta NASA Earthdata
- **Landsat**: coleção Landsat 8 Collection 2 Level-2 via USGS EarthExplorer — requer conta USGS
