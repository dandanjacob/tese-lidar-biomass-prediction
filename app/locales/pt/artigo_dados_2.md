A definição de **parcela** (`plot_id`) merece nota metodológica: auditorias sobre os
KMLs de inventário revelaram parcelas com o campo `Name` não único — polígonos distintos
(quadras) compartilhando o mesmo nome —, o que levava o pipeline original a dissolver
quadras diferentes numa só, colapsando contagens e pareando AGB de campo com o clip de
LiDAR errado. A correção (documentada in extenso no apêndice de qualidade de dados)
define o `plot_id` por uma regra hierárquica: nome único → usa o nome; nome repetido →
sufixo sequencial (`T20_1`, `T20_2`, …); nome não informativo → índice sequencial. Essa
correção, mais a remoção de feições geometricamente duplicadas e a recuperação de
parcelas indevidamente descartadas por bugs de leitura de coordenadas, elevou o conjunto
de parcelas treináveis de 383 para as 493 finais — um ganho de 29% no tamanho da amostra
de treino, obtido inteiramente por correção de bugs, sem novos dados brutos.

O critério de qualificação espacial usa **≥ 99,9% da área da parcela dentro da cobertura
contígua de uma campanha** (tiles vizinhos do mesmo voo, unidos; subcampanhas do mesmo
ano tratadas como uma só), em vez de um teste `within` estrito — o que evitava que
parcelas 100% cobertas, mas tocando a borda da união de tiles, fossem indevidamente
descartadas.

### 2.3 Números do dataset

| Métrica | Valor |
|---|---:|
| Tiles no inventário LiDAR da NASA | 3.152 |
| Sites de inventário (total) | 28 |
| Tiles LiDAR distintos efetivamente usados | 242 |
| Parcelas no inventário (uma por quadra, pós-deduplicação) | 581 |
| Pares parcela × tile | 1.287 |
| Parcelas com cobertura LiDAR (≥ 99,9% da área) | 553 |
| Parcelas com AGB de campo calculável (nível quadra) | 509 |
| **Parcelas treináveis — AGB × LiDAR pareados** | **493** |
| Parcelas treináveis após remoção de outliers geométricos | 325 |

*Fonte: auditoria de dados do projeto (última varredura registrada), reproduzida
integralmente na página de Apêndice — Qualidade de Dados.*

### 2.4 Biomassa de referência (alvo)

A AGB de campo é calculada árvore a árvore e agregada por parcela, sob três fórmulas
alométricas candidatas que diferem na especificidade da densidade de madeira (ρ) e no
tratamento de árvores mortas e palmeiras:

| Fórmula | Equações usadas | Densidade de madeira (ρ) |
|---|---|---|
| **M1 — Chave uniforme** | Chave et al. (2014) para todas as árvores | ρ = 0,6 g/cm³ (média global) |
| **M2 — Chave por tipo** | Chave (2014, vivas) · Chambers (2000, mortas) · Goodman (2013, palmeiras) | ρ = 0,6 g/cm³ (média global) |
| **M3 — Chave por tipo + ρ específica** | Mesmas equações de M2 | ρ por espécie (GWDD Zanne/Chave; *fallback* gênero → site → 0,6) |

Equações de carbono individual (fração de carbono f_C = 0,5):

- Árvores vivas: `IAGC = 0,0673 × 0,5 × (ρ × DBH² × H)^0,976` — Chave et al. (2014), Eq. 7
- Árvores mortas: `IAGC = 0,1007 × 0,5 × 0,40 × DBH² × H^0,818` — Chambers et al. (2000)
- Palmeiras vivas: `IAGC = 0,03781 × 0,5 × DBH^2,7483` — Goodman et al. (2013)

com AGB = 2 × AGC (unidade final: Mg/ha). **Este trabalho usa M1 como alvo de treino
para todos os modelos.** Essa escolha — e o fato de não haver, nesta versão, uma análise
de sensibilidade dos resultados a M2/M3 — é revisitada criticamente na Seção 4.3.

Adicionalmente, corrige-se o **descompasso temporal** entre o ano do voo LiDAR e o ano da
medição de campo: o DBH é "crescido" até o ano do voo pelo incremento anual observado
(por remedição, quando disponível; senão pela mediana do site; senão um valor *default*),
e altura e biomassa são re-derivadas a partir do DBH ajustado. O efeito médio é pequeno
(~1,3% na biomassa média), mas chega a 7–12% nos sites com gap de 2–3 anos entre voo e
medição — não desprezível para parcelas individuais, mesmo que pequeno em média.

### 2.5 Abordagens de modelagem comparadas

Seis representações do sinal LiDAR foram comparadas, da mais compacta à mais rica em
graus de liberdade — todas treinadas sobre o **mesmo conjunto de parcelas**, com o mesmo
protocolo de validação cruzada, para que a diferença de desempenho seja atribuível à
representação e ao modelo, não ao dado de treino:

| # | Abordagem | Entrada | Modelo |
|---|---|---|---|
| 1 | GBR — alturas ordenadas | 1024 alturas de dossel amostradas e ordenadas + log(n pontos) — 1025 atributos | Gradient Boosting |
| 2 | GBR — *K* quantis | *K* quantis igualmente espaçados da altura + log(n pontos) — *K*+1 atributos, *K* ∈ {8,16,32,64,128,256} | Gradient Boosting |
| 3 | ABA (*Area-Based Approach*) | 37 métricas estruturais — percentis de altura, densidade vertical, rugosidade convolucional do CHM | Gradient Boosting |
| 4 | Random Forest estrutural | As mesmas 37 métricas do ABA | Random Forest (*bagging*) |
| 5 | PointNet | Nuvem de pontos crua (x, y, altura), até 8192 pontos/parcela, 2048 amostrados por passo | PointNet (MLP compartilhado + max-pool) |
| 6 | CNN 2D — raster | Grade 32×32, 4 canais (altura máx., altura média, densidade log, desvio-padrão) | CNN 2D (3 blocos conv+BN+ReLU) |
| 7 | CNN 3D — voxel | Volume 16×16×16, 2 canais (ocupação, densidade log) | CNN 3D (3 blocos conv3d+BN+ReLU) |

As abordagens 3 e 4 compartilham exatamente as mesmas 37 features de entrada — a única
diferença é *bagging* (Random Forest) vs. *boosting* (Gradient Boosting) —, isolando o
efeito do algoritmo de ensemble do efeito da representação. As abordagens 5–7 recebem
representações geometricamente crescentes em riqueza (nuvem crua → grade 2D → volume 3D)
e, com isso, em número de parâmetros e propensão a sobreajuste com poucas amostras.

### 2.6 Protocolo de validação

Todos os modelos são avaliados por **validação cruzada k-fold aleatória (5 folds)**,
com o alvo transformado em log1p. ABA e Random Forest usam os mesmos hiperparâmetros de
Gradient Boosting (`n_estimators=300, max_depth=4, learning_rate=0,05, subsample=0,8`)
para que a comparação isole o efeito do algoritmo. Reporta-se RMSE (Mg/ha), R² e rRMSE
(RMSE relativo à média observada, %) — agregados sobre as previsões *out-of-fold* de
todos os folds (métrica "global"), não a média simples das métricas por fold.

Cada modelo é avaliado em **seis variantes do conjunto de treino, cada uma testando UM
tratamento isoladamente contra a mesma nuvem crua** — não empilhadas umas sobre as
outras, para que o efeito de cada tratamento possa ser atribuído a ele mesmo, não à
combinação (Seção 3.1): **sem processamento** (`raw`, baseline), **só projeção do solo**
(`ground_only` — relevo local célula-a-célula, sem filtro), **só filtro ≤1,3 m**
(`filter_only` — remoção dos retornos até a altura do peito, aplicada sobre o mesmo
deslocamento mínimo de Z do baseline cru, sem acionar a projeção de relevo completa),
**só remoção de outliers** (`outliers_only` — parcelas com área > 0,5 ha ou compacidade
< 0,6 removidas, sem nenhum tratamento na nuvem), **só correção de gap temporal**
(`gap_only` — alvo realinhado à data do voo LiDAR, sem nenhum tratamento na nuvem) e
**tudo combinado** (`gap_corrected_noout` — os quatro tratamentos juntos, o pipeline
completo). Variantes intermediárias empilhadas (solo+filtro, +outliers, +gap) também
foram treinadas e permanecem disponíveis nos dados, mas a análise principal da Seção 3.1
usa as seis variantes isoladas como evidência primária, por permitirem atribuir o ganho
de desempenho a um tratamento específico em vez de a uma combinação.

> **Nota de escopo (ver Seção 4.2):** o k-fold aqui é aleatório sobre parcelas, não sobre
> sítios — parcelas do mesmo site de inventário podem cair em treino e teste no mesmo
> fold. Isso é adequado para medir o ajuste do modelo à distribuição de estrutura do
> dossel presente na amostra, mas **infla a métrica de generalização espacial** por
> autocorrelação entre parcelas vizinhas do mesmo sítio — a leitura correta dos números
> desta seção é "quanto da variância intra-amostra é explicada", não "quão bem isto
> generaliza para floresta amazônica não amostrada".
