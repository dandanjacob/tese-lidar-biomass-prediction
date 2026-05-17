# Interseções LiDAR × Inventário

## O que é

Tabela de cruzamento espacial entre as parcelas de inventário florestal e os tiles LiDAR disponíveis.

## Script utilizado

```bash
src/find_intersections.py
```

## Entradas

- Bounding boxes dos tiles LiDAR: `data/raw/lidar/.../cms_brazil_lidar_tile_inventory.csv`
- Polígonos das parcelas: `data/processed/01_kml/*_inventory_plots.kml`

## Método

1. Constrói geometrias retangulares (box) para cada tile a partir do CSV do LiDAR
2. Lê os polígonos de cada parcela dos KMLs de inventário
3. Spatial join (`intersects`) via geopandas

**Nota:** a interseção é puramente geométrica — não filtra por ano de coleta. Uma parcela pode estar pareada com tiles de campanhas LiDAR de anos diferentes. Ver `intersections_temporal.csv` para análise com gap temporal.

## Arquivos gerados

### `lidar_inventory_intersections.csv`

Um registro por par (parcela × tile). Colunas:

| Coluna | Descrição |
|---|---|
| `inventory_file` | Nome do KML de inventário (identifica site + período) |
| `plot_id` | ID da parcela dentro do site |
| `laz_file` | Nome do arquivo `.laz` que cobre essa parcela |

### `intersections_temporal.csv`

Mesmos pares com colunas adicionais de ano e gap temporal. Um registro por par (parcela × tile). Permite selecionar o LiDAR de ano mais próximo ao inventário.

### `map_intersections.png` / `map_intersections.html`

Visualizações das interseções sobre mapa do Brasil. O HTML é interativo (zoom, tooltip por parcela).

## Estatísticas

| Métrica | Valor |
|---|---|
| Total de pares (parcela × tile) | 1.362 |
| Parcelas únicas com cobertura LiDAR | **294** (combinação site + plot_id) |
| Parcelas de inventário sem cobertura | 365 de 659 |
| Sites de inventário cobertos | 27 de 31 |
| Tiles LAZ utilizados | 252 de 3.152 |

> **Como contar parcelas únicas:** o `plot_id` (ex. "1", "2") é único apenas dentro de cada site. A contagem correta usa o par `(inventory_file, plot_id)`.
