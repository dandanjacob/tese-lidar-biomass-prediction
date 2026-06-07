# Problemas conhecidos — qualidade de dados

> Última auditoria: 2026-06-07 (recuperação de parcelas — ver §6)

## 1. Parcelas com `Name` repetido nos KMLs (✅ resolvido em 2026-06-04)

### O que era

Vários KMLs de inventário (`data/processed/01_kml/*.kml`) têm o campo `Name`
**não único**: polígonos distintos compartilham o mesmo nome de parcela. O pipeline
usava `Name` como `plot_id` e dissolvia por ele, então quadras distintas eram
tratadas como uma só parcela — colapsando as contagens, recortando só uma sub-parcela
e parerando a AGB de campo com o clip errado.

Sites com mais polígonos do que `Name` distintos:

| Site | Polígonos | `Name` distintos |
|---|---:|---:|
| `CAU_A01_2014_2018` | 176 | 22 |
| `FST_A01_2013` | 40 | 5 |
| `FNA_A01_2013` | 20 | 5 |
| `PAR_A01_2013_2018` | 20 | 10 |
| `TAN_A01_2012` | 20 | 10 |
| `JAM_A02_2013` | 48 | 1 (`"0"`) |
| `JAM_A03_2013` | 16 | 1 (`"0"`) |

### Decisão e correção

**Cada quadra (cada feature do KML) é uma parcela.** A inspeção mostrou que essas
quadras são *features separadas* no KML (não partes de um único multipolígono): no
CAU são 176 features sob 22 nomes; no FST, 40 features sob 5 nomes. Tratá-las como
partes de uma só parcela era o que somava 6,04 ha "espalhados por 4,18 km" no
`JAM_A02_2013`.

A regra de `plot_id` agora vive em **`src/plot_loading.py:assign_plot_ids`** (e é
espelhada em `app/lib/data.py`):

- `Name` único no site → usa o próprio `Name`;
- `Name` repetido (várias quadras com o mesmo nome, ex.: CAU/FST) → `Name_k`
  (`T20_1`, `T20_2`, …);
- `Name` totalmente não informativo (um único valor para todas as features, ex.:
  `JAM_A02_2013`) → índice sequencial `0`..`n-1`.

Os nomes são normalizados com `strip()` antes (uma quadra do FST vinha como `" 1"`
com espaço à esquerda, que de outra forma viraria um `plot_id` distinto de `"1"`).

`find_intersections.py`, `clip_lidar_to_plots.py` e o app passaram a usar essa regra,
e o pipeline foi **re-rodado** (interseções → clips). O dissolve por
`(inventory_file, plot_id)` continua no código, mas agora é inócuo (cada chave tem
uma só geometria) — mantido apenas como garantia de unicidade.

## 2. Critério de cobertura: `within` estrito → ≥ 99,9% da área + união a/b (✅ resolvido em 2026-06-04)

### O que era

A qualificação usava `within` **estrito** da cobertura contígua de uma campanha. Duas
consequências indesejadas:

1. **Toque na fronteira reprovava parcelas 100% cobertas.** Ex.: `JAM_A02_2011` T02
   é coberta integralmente pelos tiles de `JAM_A02a_2014`, mas encosta na borda da
   união → `within = False` → caía como "descartada" mesmo coberta.
2. **Subcampanhas a/b do mesmo ano** (ex.: `JAM_A02a_2014` + `JAM_A02b_2014`,
   `FST_A01a_2014` + `FST_A01b_2014`) eram tratadas como campanhas diferentes, então
   a cobertura ficava fragmentada na fronteira entre as entregas.

### Correção

- O critério passou a ser **≥ 99,9% da área da parcela dentro da cobertura contígua
  de uma campanha** (em vez de `within` estrito). Parcelas-linha sem área (ver item 4)
  caem para um teste topológico de cobertura (`covers`), preservando o comportamento
  antigo.
- `campaign_of` (em `find_intersections.py`) **une as subcampanhas a/b do mesmo ano**:
  `JAM_A02a_2014 → JAM_A02_2014`. O app espelha as duas mudanças em
  `app/lib/data.py:_coverage_geom`.

Efeito líquido: T02 e o site inteiro `JAM_A01_2011` passaram a qualificar; nenhum site
coberto antes foi perdido.

## 3. Clips dessincronizados das interseções (✅ corrigido em 2026-06-04)

O recorte (`clip_lidar_to_plots.py`) agora **limpa a pasta de saída** antes de rodar
(os `plot_id` mudaram, então clips antigos seriam órfãos) e **persiste um resumo** em
`03_clipped_lidar/clip_summary.json` (`written`, `plots_no_points`, `corrupt_tiles`,
`missing_tiles`). O backup dos clips antigos está em `03_clipped_lidar.backup.tgz`.

Re-clip de 2026-06-04: **540 clips** escritos · **13 parcelas vazias** (polígono sem
nenhum ponto LiDAR — clip legítimo de tamanho zero) · **1 tile corrompido**
(`FST_A01a_2015_laz_5.laz`, IoError) · 0 faltando. 540 + 13 = 553 parcelas das
interseções, sem órfãos.

## 4. Limitações de exibição conhecidas (abertas — não afetam os dados)

- **`TAP_A01/A04/A05`** — as geometrias do KML são **linhas abertas** (não fecham em
  anel), então não viram retângulo no mapa: aparecem como pin sem polígono. Qualificam
  por cobertura topológica, mas o clip por polígono não extrai pontos (sem interior).
- **`PAR_A01_2018`** — 40 parcelas com **geometria nula** (sem coordenadas no KML):
  nada a desenhar nem a recortar.
- **`FNA_A01_2013`** — linhas que **fecham** em anel: `_ensure_polygon` as converte em
  polígono (vira quadrado no mapa e recorta pontos). Já tratado.

## 5. Biomassa por quadra via posição das árvores (✅ implementada em 2026-06-04)

O inventário de campo (`04_inventory/*.csv`) rotula as árvores por `plot_id` no nível do
`Name` (FST 4, CAU 22, `JAM_A02_2013` 1), mas traz **coordenadas por árvore**
(`utm_easting`/`utm_northing`). Isso permite atribuir cada árvore à **quadra** em que ela
cai, levando a AGB ao mesmo nível dos clips.

`calculate_biomass.py:assign_quadras` faz a atribuição **restrita às quadras do próprio
`Name` de campo da árvore** — o split nunca cruza parcelas-de-campo distintas e, por
construção, a quadra atribuída pertence ao plot medido. Desempate quando as quadras se
sobrepõem: se está dentro de várias, a de centroide mais próximo; se fora de todas, o
polígono mais próximo. Há checagem da zona UTM (derivada do centroide do KML): se <50%
das árvores forem localizadas, o site volta ao nível do `Name`. Nos sites multipartes a
localização foi de **100%**.

Resultado: **402 parcelas (nível quadra)**, contra 150 no nível `Name`. Só os sites com
`Name` repetido expandem (CAU 22→176, FST 4→40, `JAM_A02_2013` 1→48, `JAM_A03_2013` 1→8,
PAR 7→14, TAN 1→2); os demais têm `Name` único por feature e ficam iguais. **383 dessas
402 têm nuvem clipada** → pareáveis AGB de campo × LiDAR no nível da quadra (antes o
pareamento era inválido: AGB sobre a união das partes, clip sobre uma sub-parcela só).

Quatro conjuntos distintos: **589** geométricas · **553** com cobertura LiDAR · **402**
com AGB de campo · **383** pareáveis (AGB + nuvem).

Ressalvas: quadras são pequenas (~0,13 ha) → densidade de AGB mais ruidosa que no nível
`Name` (~1 ha); o split do `JAM_A02_2013` (campo só tem `"0"`) é espacialmente defensável
mas sem rótulo de campo para conferir; sites sem `plot_id` de campo (ex.: `SFX_A02`)
permanecem agregados.

> **Atualização 2026-06-07:** após a recuperação descrita em §6, esses números subiram para
> **509 parcelas com AGB** e **493 pareáveis (AGB + nuvem)**. Os modelos foram re-treinados
> sobre os 493 pares.

## 6. Recuperação de parcelas indevidamente descartadas (✅ 2026-06-07)

Auditoria das parcelas "vermelhas" (cruzam o LiDAR, mas sem rótulo utilizável) revelou que
a maioria era recuperável — o dado existia, mas era descartado por bugs de leitura/pareamento.
Corrigidos quatro bugs de dados e um bug do app. **Parcelas treináveis (verdes): 383 → 493
(+110, +29%).** Partição do mapa de cobertura: verde 493 · vermelho 60 · cinza 36 (era
383/170/36). Os pares já existentes ficaram idênticos (a regeneração só somou).

| # | Bug | Sites | Correção |
|---|---|---|---|
| A | Coluna UTM com espaço/sem separador (`UTM Easting`) não casava | `SFX_A01/02/03`, `TAP_A03` | match de coluna robusto a separador |
| B | Filtro usava `plot_id` corrigido (`T01_1`) vs. atribuição por `Name` (`T01`) → multiparte zerava | `CAU`, `PAR`, `TAN`, `FST` | aceitar nome-base no filtro |
| C | Coordenadas lat/lon trocadas | `DUC_A01_2016` | testar as duas ordens, escolher a que cai dentro |
| D | KML como `LineString` (sem área) → ponto-em-polígono e área falham | `FNA`, `TAP_A0x` (anel fechado) | polygonizar em `prepare_inventory` e `calculate_biomass` |
| — | `_usability` contava linha com AGB nulo como "usável" (app) | (app) | filtrar `agb_m1_Mg_ha` não-nulo |

### Resíduo (60 vermelhas na recuperação; 52 após o dedup do §7) — limitação genuína de dado

- **`TAP_A01_2009`** (6): coordenadas não caem nos polígonos.
- **`TAP_A04`/`TAP_A05`** (6): geometria do KML é **`MultiLineString` aberta** (não fecha em
  anel → `_ensure_polygon` não polygoniza) **e** o `Name` está corrompido (floats tipo
  `499.998`, `500.000` — KML malformado). Cruzam tiles LiDAR (por isso aparecem como **pin
  vermelho** no mapa), mas não há polígono a desenhar nem interior a recortar (sem clip, sem
  AGB). Ver §4.
- **`FN_2015`** (1): coordenadas UTM corrompidas no CSV — recuperável por parsing (ver §8).
- **`JAM_A03_2013`** (8): eram **feições duplicadas**, não vermelhas reais — corrigido no §7.
- O restante (`TAC`, `HUM`, `SAN`…) são parcelas individuais sem árvore medida dentro,
  em sites que já funcionam — não são bug, são parcelas vazias.

Clips **não** foram refeitos: as parcelas recuperadas já tinham `.laz` (eram "vermelhas" =
cobertas e clipadas, só faltava o rótulo). Interseções e clips são geométricos e não mudaram.

## 7. Feições duplicadas no `JAM_A03_2013` (✅ 2026-06-07)

O KML do `JAM_A03_2013` traz **16 feições que são, na verdade, 8 parcelas** — cada uma
**repetida** (sobreposição 100%, distância de centroide 0,0 m; confirmado: plot 0≡8, 1≡9,
…, 7≡15). Como o `Name` é não informativo (tudo `"0"`), o `assign_plot_ids` numerava 0..15,
inflando a contagem. As árvores eram atribuídas à 1ª cópia (vira **verde**); a duplicata
ficava sem AGB → **8 parcelas-fantasma vermelhas**. Varredura global de geometrias idênticas:
**só o `JAM_A03_2013`** tinha o problema (8 duplicatas no total).

**Correção:** `plot_loading.drop_duplicate_geometries` remove feições com geometria idêntica
a uma anterior do mesmo arquivo (mantém a 1ª ocorrência, então os `plot_id` seguem batendo
com biomassa/clips já gerados). Aplicada nos quatro pontos que leem KML —
`plot_loading.load_plots` (→ interseções e clips), `app/lib/data.py` (→ mapa/cobertura),
`calculate_biomass.quadra_geoms` e `outlier_filter.plot_geometry`.

Efeito: **total 589 → 581 · vermelhas 60 → 52**; **verdes seguem 493** (as fantasmas eram
todas vermelhas) → **não exige retreino**. No mapa, o que parecia "vermelho cobrindo o verde"
era a duplicata empilhada no mesmo ponto; colapsada, sobra só a parcela verde correta.

## 8. Biomassa ausente/baixa no gráfico por parcela — `FN`/`FNA` (parcial)

Sintoma: no gráfico de AGB por parcela (página Biomassa, ordenado por AGB) parcelas de
`FN`/`FNA` aparecem no fim, aparentemente sem estimativa. Dois casos distintos:

- **`FNA_A01_2013`** (✅ não é bug): **tem** AGB, mas **baixa** (4–35 Mg/ha) — DBH a partir de
  5,3 cm e média ~22 cm (nas demais a média é ~36 e começa em 10 cm), compatível com
  **floresta secundária/jovem**. Barras curtas no fim do gráfico, não ausência de valor.
- **`FN_A01_2015`** (🔴 aberto, recuperável): 1 linha `unknown`, **683 árvores, AGB nulo**.
  As coordenadas UTM no CSV estão **corrompidas com pontos de milhar**
  (`utm_easting = "70.661.811.988.124"` em vez de `706618.12`; idem northing). Sem coordenada
  numérica → árvores não entram em nenhuma quadra → sem área → AGB/ha nulo. DBH/altura estão
  OK, então é recuperável por parsing (como o bug A): reinterpretar o separador decimal.
  **Ainda não corrigido** — recuperá-lo adicionaria parcela(s) treinável(is) e exigiria novo
  retreino.

## Números de referência (auditoria 2026-06-07, pós-recuperação + dedup)

Conferidos contra os arquivos regerados; consistentes entre as páginas do app:

| Métrica | Valor | Onde aparece |
|---|---:|---|
| Tiles no inventário LiDAR da NASA | 3.152 | Organização |
| Parcelas no inventário (cada quadra = 1, pós-dedup §7) | 581 | Cobertura |
| Sites de inventário (total) | 28 | — |
| Tiles LiDAR distintos usados | 242 | Home, Mapa |
| Sites de inventário com cobertura | 27 | — |
| Pares parcela × tile | 1.287 | Interseções |
| Parcelas com LiDAR (cobertura ≥ 99,9%) | 553 | Home, Mapa, Interseções |
| Parcelas descartadas (sobrepõem, < 99,9%) | 17 | Cobertura |
| Parcelas sem sobreposição LiDAR | 19 | Cobertura |
| Parcelas sem LiDAR (17 + 19) | 36 | Mapa |
| Tiles distintos no melhor casamento temporal | 124 | Organização |
| Clips no disco | 540 (553 − 13 vazias) | Home |
| Parcelas com AGB de campo (nível quadra) | 509 | Biomassa |
| Parcelas treináveis / pareáveis AGB × LiDAR (verdes) | 493 | Mapa, Modelos |
| Parcelas vermelhas (cruzam LiDAR, sem rótulo, pós-dedup §7) | 52 | Mapa |
| Parcelas treináveis sem outliers (área > 0,5 ha ou comp. < 0,6 removidas) | 325 | Modelos |
</content>
</invoke>
