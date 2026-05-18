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
        Normalização do inventário              →  data/processed/04_inventory/
        (src/prepare_inventory.py)
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
    01_kml/         ← KMLs extraídos dos KMZs (para visualização)
    02_intersections/ ← tabela de cruzamento espacial LiDAR × parcelas
    03_clipped_lidar/ ← nuvens de pontos recortadas por parcela
notebooks/          ← análise exploratória e experimentos
src/                ← scripts de processamento
```

## Ferramentas externas

| Ferramenta | Uso no projeto | Download |
|---|---|---|
| **CloudCompare** | Inspecionar nuvens de pontos `.laz` em 3D — visualizar altura, densidade, verificar se o clip de uma parcela ficou correto | Linux: `flatpak install flathub org.cloudcompare.CloudCompare` · outros: [cloudcompare.org](https://cloudcompare.org/release/index.html) |
| **QGIS** | Visualizar geometrias em contexto geográfico 2D — sobrepor polígonos do inventário com tiles LiDAR no mapa, validar interseções | [qgis.org](https://qgis.org/download) |

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
