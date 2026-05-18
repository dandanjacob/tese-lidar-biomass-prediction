# Inventário Florestal Processado

## O que é

CSVs de inventário normalizados, filtrados para os plots com cobertura LiDAR completa (critério `within`). Um arquivo por site de inventário.

## Script utilizado

```bash
src/prepare_inventory.py
# ou
make inventory
```

## Entradas

- CSVs brutos: `data/raw/inventory/.../`
- KMLs dos plots: `data/processed/01_kml/`
- Tabela de interseções: `data/processed/02_intersections/lidar_inventory_intersections.csv`

## Método

1. Detecta encoding (latin-1) e separador (`,` ou `;`) de cada CSV
2. Normaliza nomes de colunas para schema consistente
3. Atribui `plot_id` a cada árvore via point-in-polygon usando coordenadas UTM/lon-lat da árvore e polígonos do KML — robusto a inconsistências de nomenclatura entre CSV e KML
4. Filtra para apenas os plots presentes nas interseções (critério `within`)
5. Salva em UTF-8

## Schema de saída

| Coluna | Descrição |
|---|---|
| `site` | Código do site de inventário |
| `plot_id` | ID da parcela (do KML) |
| `tree_id` | ID da árvore dentro da parcela |
| `scientific_name` | Nome científico da espécie |
| `family_name` | Família botânica |
| `dbh_{ano}` | DAP — diâmetro à altura do peito (cm) |
| `htot_{ano}` | Altura total (m) — frequentemente ausente |
| `hcom_{ano}` | Altura comercial (m) — frequentemente ausente |
| `type_{ano}` | `O` = árvore, `P` = palmeira |
| `dead_{ano}` | `True`/`False` — árvore morta |
| `wsd` | Densidade da madeira (g/cm³) — apenas FST_A01 |
| `agb_source` | AGB pré-calculada no CSV original — apenas FST_A01 |
| `utm_easting` | Coordenada leste (UTM ou lon decimal) |
| `utm_northing` | Coordenada norte (UTM ou lat decimal) |

Sites com múltiplos anos de medição terão colunas `dbh_2015`, `dbh_2018`, etc.

## Estatísticas

| Métrica | Valor |
|---|---|
| Sites processados | 21 |
| Total de árvores | 20.597 |
| Sites sem árvores (falsos positivos ou IDs corrompidos) | 5 |
