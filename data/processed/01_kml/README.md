# KMLs Extraídos

## O que é

Arquivos `.kml` extraídos dos `.kmz` originais para permitir visualização no VS Code via extensão **Geo Data Viewer** (que suporta `.kml` mas não `.kmz`).

## Origem

| Arquivo KMZ de origem | Localização |
|---|---|
| `*_inventory_plots.kmz` (31 arquivos) | `data/raw/inventory/Forest_Inventory_Brazil_2007_.../` |
| `cms_brazil_lidar_tile_inventory.kmz` (1 arquivo) | `data/raw/lidar/LiDAR_Forest_Inventory_Brazil_1644_.../` |

## Script utilizado

```bash
src/extract_kml.sh
```

Itera sobre todos os `.kmz` do inventário e extrai o `doc.kml` interno, renomeando para o nome do site correspondente. O KMZ do LiDAR foi extraído manualmente com `unzip -p`.

## O que foi gerado

- **31 arquivos** `*_inventory_plots.kml` — polígonos das parcelas de inventário por site
- **1 arquivo** `cms_brazil_lidar_tile_inventory.kml` — cobertura espacial de todos os tiles LiDAR

## Como visualizar

Abra qualquer `.kml` no VS Code e use `Ctrl+Shift+P` → **View Map**.
