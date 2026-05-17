# LiDAR Biomass Prediction

Repositório complementar à dissertação de mestrado em matemática aplicada (FGV). Objetivo: estimar a biomassa da floresta amazônica a partir de dados LiDAR coletados pela NASA, cruzados com inventários florestais de campo.

## Pipeline

```
Dados brutos (baixados manualmente)
        │
        ├── Inventário florestal (.csv, .kmz)   →  data/raw/inventory/
        └── Nuvem de pontos LiDAR (.laz)        →  data/raw/lidar/
                │
                ▼
        Extração de KMLs para visualização      →  data/processed/01_kml/
        (src/extract_kml.sh)
                │
                ▼
        Cruzamento espacial LiDAR × inventário  →  data/processed/02_intersections/
        (src/find_intersections.py)
                │
                ▼
        Recorte do LiDAR por parcela            →  data/processed/03_clipped_lidar/
        (src/clip_lidar_to_plots.py)
                │
                ▼
        Extração de métricas LiDAR              →  (a implementar)
        (altura do dossel, densidade, etc.)
                │
                ▼
        Modelagem e predição de biomassa        →  src/models/, notebooks/
```

## Estrutura do repositório

```
data/
  raw/
    inventory/      ← inventário de campo baixado do ORNL DAAC
    lidar/          ← tiles LiDAR (.laz) baixados do ORNL DAAC
  processed/
    kml/            ← KMLs extraídos dos KMZs (para visualização)
    intersections/  ← tabela de cruzamento spatial LiDAR × parcelas
    clipped_lidar/  ← nuvens de pontos recortadas por parcela
notebooks/          ← análise exploratória e experimentos
src/                ← scripts de processamento
```

## Documentação detalhada

| Pasta | README |
|---|---|
| `data/raw/inventory/` | [Inventário florestal bruto](data/raw/inventory/README.md) |
| `data/raw/lidar/` | [Dados LiDAR brutos](data/raw/lidar/README.md) |
| `data/processed/01_kml/` | [KMLs extraídos](data/processed/01_kml/README.md) |
| `data/processed/02_intersections/` | [Cruzamento espacial](data/processed/02_intersections/README.md) |
| `data/processed/03_clipped_lidar/` | [LiDAR recortado por parcela](data/processed/03_clipped_lidar/README.md) |

## Ambiente

```bash
# Instalar dependências
uv pip install -r requirements.txt

# Ou recompilar o lock file
uv pip compile requirements.in -o requirements.txt
```

Principais bibliotecas: `geopandas`, `laspy`, `shapely`, `pyproj`, `pandas`, `numpy`.
