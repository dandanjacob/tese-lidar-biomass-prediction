## ✅ O que já foi feito

1. **Coleta e entendimento dos dados** — nuvens de pontos LiDAR aerotransportado
   (NASA / ORNL DAAC) e inventários florestais de campo da Amazônia; exploração de
   estrutura, qualidade e cobertura.
2. **Interseções LiDAR × inventário** — cruzamento espacial das parcelas com cobertura
   LiDAR, incluindo a defasagem de anos entre o voo e a medição de campo.
3. **Biomassa de referência (o alvo)** — AGB por parcela a partir do inventário (DBH,
   altura, densidade da madeira), em três fórmulas (M1 / M2 / M3).
4. **Recuperação do dataset** — deduplicação e correções elevaram as parcelas
   utilizáveis de **383 → 493** (e **325** após remover outliers de área/forma).
   Sites de **transecto** (TAP) cujas parcelas eram linhas — não polígonos — foram
   recuperados via buffer em corredor: **24 → 27 sites** processados.
5. **Altura total melhorada** — estimativa em 3 níveis (medida → ajuste H-D local do
   site → Feldpausch regional), recuperando a coluna de data por árvore do inventário.
6. **Correção do gap temporal** — o DBH é "crescido" até o ano do voo LiDAR pelo
   incremento anual (observado por remedição → mediana do site → default) e a altura e a
   biomassa são re-derivadas. Efeito medido: ~1,3% na biomassa média (até ~7–12% nos
   sites de gap de 2–3 anos). Gera colunas novas, sem sobrescrever as originais.
7. **Seis modelos, três variantes** — GBR, Random Forest, ABA (métricas), PointNet e
   CNNs 2D/3D, treinados **com outliers**, **sem outliers** e **com gap + sem outliers**,
   por validação cruzada k-fold. Melhor resultado atual: **CNN 2D de rasters de altura**
   com **R² ≈ 0,53 / rRMSE ≈ 44,5%** (gap + sem outliers) — na faixa do nível de
   *footprint* da missão GEDI da NASA (R² ~0,4–0,5, rRMSE tropical ~47%).
8. **Diagnóstico e visualização** — predito × observado, resíduos, *learning curve* e
   evolução (RMSE + R²); tabela de comparação com **gradiente verde→vermelho** por
   métrica; na nuvem de pontos, seletor entre altura atual × corrigida pelo gap e opção
   de ocultar a nuvem para ver só as alturas.
9. **Redução de dimensionalidade (experimento)** — GBR com **K quantis de altura**
   (de 8 a 256): o R² satura já com **~16 quantis**, confirmando que as 1024 alturas
   originais eram, em boa parte, ruído que alimentava *overfitting*.

## 🎯 O plano (próximos passos)

Leitura até aqui: **poucas features bem escolhidas generalizam melhor que a nuvem crua
de alta dimensão**; remover outliers e corrigir o gap ajudam; e a estrutura horizontal
(rasters) carrega sinal real. Não há como adicionar dados novos — o foco é extrair mais
sinal e avaliar com honestidade.

1. **Ensemble / stacking dos modelos** — uma simples média de raster + RF + voxel já
   mede **R² ≈ 0,59** (acima do melhor isolado, 0,53). É o ganho mais imediato.
2. **Avaliação honesta (LOSO)** — a CV atual é k-fold aleatório (parcelas do mesmo site
   em treino e teste), o que **infla o R²** por correlação espacial. Reportar também o
   *leave-one-site-out* como número de generalização a sites novos.
3. **Melhorar os modelos fracos** — aumento geométrico no PointNet (rotação no eixo
   vertical + jitter; hoje é o pior, R² ~0,17) e modelo **híbrido raster + métricas ABA**.
4. **Qualidade do rótulo** — parcelas minúsculas (~0,02 ha) geram AGB implausível (até
   1552 Mg/ha) e distorcem as métricas; avaliar piso de área e perda robusta.
5. **Padronizar o *footprint* das parcelas** — recortar com área/forma parecidas,
   gerando um dataset mais homogêneo (cada parcela grande vira várias unidades menores).

---

> _Página viva: vai sendo atualizada conforme o projeto avança._
