# Interseções LiDAR × Inventário

## O que é

Tabela de cruzamento espacial entre as parcelas de inventário florestal e os tiles LiDAR disponíveis.

## Script utilizado

```bash
src/find_intersections.py
```

## Entradas

- Bounding boxes dos tiles LiDAR: `data/raw/lidar/.../cms_brazil_lidar_tile_inventory.csv`
- Polígonos das parcelas: `data/processed/kml/*_inventory_plots.kml`

## Método

1. Constrói geometrias retangulares (box) para cada tile a partir do CSV do LiDAR
2. Lê os polígonos de cada parcela dos KMLs de inventário
3. Spatial join (`intersects`) via geopandas

## Arquivo gerado

`lidar_inventory_intersections.csv` — colunas:

| Coluna | Descrição |
|---|---|
| `inventory_file` | Nome do KML de inventário (= site) |
| `plot_id` | ID da parcela dentro do site |
| `laz_file` | Nome do arquivo `.laz` que cobre essa parcela |

## Estatísticas

| Métrica | Valor |
|---|---|
| Total de pares (plot × tile) | 1.362 |
| Parcelas com cobertura LiDAR | 108 de 659 |
| Sites cobertos | 27 de 31 |
| Tiles LAZ utilizados | 252 de 3.152 |
