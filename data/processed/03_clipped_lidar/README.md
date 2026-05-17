# LiDAR Recortado por Parcela

## O que é

Nuvens de pontos LiDAR recortadas aos polígonos exatos de cada parcela de inventário florestal. Um arquivo `.laz` por parcela.

## Script utilizado

```bash
src/clip_lidar_to_plots.py
```

## Entradas

- Tabela de interseções: `data/processed/02_intersections/lidar_inventory_intersections.csv`
- Tiles LAZ originais: `data/raw/lidar/LiDAR_Forest_Inventory_Brazil_1644_.../`
- Polígonos das parcelas: `data/processed/01_kml/*_inventory_plots.kml`

## Método

1. Agrupa os tiles por arquivo LAZ (cada tile é lido apenas uma vez)
2. Reprojecta o polígono da parcela (WGS84) para a zona UTM do tile
3. Filtra pontos dentro do polígono com `shapely.contains_xy` (vetorizado)
4. Concatena pontos de múltiplos tiles quando a parcela cobre mais de um
5. Escreve o resultado como `.laz` mantendo o formato e escala originais

## Estrutura

```
clipped_lidar/
  {inventory_file}/
    plot_{id}.laz
```

## Próximo passo

Extrair métricas LiDAR de cada parcela (percentis de altura, densidade de copa, etc.) para alimentar o modelo de predição de biomassa.
