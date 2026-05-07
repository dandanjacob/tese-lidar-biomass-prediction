# Relatório de Cobertura: LiDAR × Inventário Florestal

Gerado a partir de `data/processed/intersections/lidar_inventory_intersections.csv`
e `data/processed/clipped_lidar/`.

---

## Visão geral

| Métrica | Valor |
|---|---|
| Plots de inventário (total) | 659 |
| Plots com interseção LiDAR | 108 |
| Plots com pontos após clip | 274 |
| Plots vazios após clip (falsos positivos) | 20 |
| Sites cobertos | 22 |
| Tiles LiDAR utilizados | 252 de 3.152 |
| **Total de pontos LiDAR clippados** | **49.863.345** |
| Tamanho total (clipped_lidar/) | 218 MB |

> **Nota:** 274 > 108 porque vários sites têm dois inventários separados
> (ex.: `TAC_A01_2014` e `TAC_A01_2015`), cada um gerando arquivos distintos.

---

## Cobertura por site

| Site | Plots (interseção) | Tiles distintos | Plots clippados | Total pts | Mediana pts/plot | MB | Anos LiDAR |
|---|---|---|---|---|---|---|---|
| ANA_A01 | 32 | 13 | 32 | 3.322.651 | 98.397 | 14,8 | 2017, 2018 |
| AND_A01 | 20 | 9 | 20 | 4.428.342 | 215.807 | 20,0 | 2013, 2017 |
| CAU_A01 | 22 | 26 | 21 | 3.234.612 | 123.860 | 12,8 | 2012, 2014 |
| DUC_A01 | 22 | 20 | 22 | 6.764.958 | ~400.000 | 28,4 | 2008, 2017 |
| FN_A01  | 1  | 1  | 1  | 22.064    | 22.064  | 0,1 | 2017 |
| FNA_A01 | 5  | 8  | 0  | —         | —       | —   | 2013, 2018 |
| FST_A01 | 5  | 21 | 5  | 5.220.590 | 1.276.504 | 24,1 | 2013, 2014, 2015 |
| HUM_A01 | 20 | 7  | 20 | 3.233.412 | 151.174 | 14,5 | 2013, 2018 |
| JAM_A01 | 2  | 2  | 2  | 500.429   | 250.215 | 2,2 | 2011 |
| JAM_A02 | 7  | 39 | 7  | 8.650.499 | ~500.000 | 38,6 | 2011, 2013, 2014, 2015 |
| JAM_A03 | 1  | 2  | 1  | 38.464    | 38.464  | 0,2 | 2013 |
| PAR_A01 | 10 | 12 | 10 | 1.983.752 | 203.689 | 9,4 | 2013 |
| SAN_A01 | 16 | 8  | 23 | 2.743.172 | ~135.000 | 11,6 | 2014 |
| SAN_A02 | 14 | 4  | 14 | 1.183.278 | 28.258  | 5,0 | 2014 |
| SFX_A01 | 9  | 3  | 9  | 563.931   | 61.594  | 2,4 | 2012 |
| SFX_A02 | 22 | 5  | 22 | 918.640   | 42.433  | 3,8 | 2012 |
| TAC_A01 | 39 | 13 | 39 | 1.229.470 | 22.365  | 5,3 | 2013 |
| TAN_A01 | 9  | 10 | 8  | 683.100   | 90.600  | 3,2 | 2012, 2014 |
| TAP_A01 | 15 | 16 | 9  | 2.092.672 | 263.655 | 8,6 | 2008, 2012 |
| TAP_A03 | 10 | 16 | 9  | 3.049.309 | 340.439 | 13,2 | 2012, 2013, 2016, 2018 |
| TAP_A04 | 4  | 13 | 0  | —         | —       | —   | 2008, 2018 |
| TAP_A05 | 2  | 4  | 0  | —         | —       | —   | 2008, 2018 |

> Sites com 0 plots clippados (FNA_A01, TAP_A04, TAP_A05): interseção existia
> mas nenhum ponto LiDAR caiu dentro dos polígonos exatos dos plots.

---

## Distribuição de tiles por plot

| Tiles cobrindo o plot | Nº de plots |
|---|---|
| 1 tile  | 106 |
| 2 tiles | 67  |
| 3+ tiles | 121 |
| **Mediana** | **2** |
| **Máximo** | **187** (JAM_A02 — ver aviso abaixo) |

---

## Distribuição de pontos por plot (clippado)

| Métrica | Valor |
|---|---|
| Mínimo | 2.763 pts |
| Mediana | 116.600 pts |
| Máximo | 2.089.259 pts |
| Densidade mediana estimada | ~11,7 pts/m² (plot 100×100 m) |

---

## Avisos

### JAM_A02 — 187 tiles num único plot
O plot 0 de `JAM_A02_2013` intersecta 187 tiles LiDAR — muito acima de qualquer
outro plot (próximo é FST_A01 com ~30). O polígono no KML provavelmente está
errado (muito grande ou abrangendo a área inteira do site). **Recomendação:**
inspecionar o KML de JAM_A02 e excluir plot 0 do dataset de treino até
confirmar a geometria.

### Tile corrompido — FST_A01a_2015_laz_5.laz
Arquivo truncado (download incompleto). Pulado automaticamente pelo script.
Os plots de FST_A01 que dependiam exclusivamente desse tile podem ter menos
pontos do que o esperado.

### Sites com 0 plots clippados (FNA_A01, TAP_A04, TAP_A05)
A interseção bbox detectou cobertura, mas após clip ponto-a-ponto nenhum ponto
caiu dentro dos polígonos. Possíveis causas: polígonos KML em projeção errada,
ou tiles com cobertura incompleta nas bordas.
