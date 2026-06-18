> **Input:** grade 2D 32×32 — 4 canais por célula: altura máxima, média, densidade (log) e desvio-padrão.

Aqui a parcela vira uma **"imagem" vista de cima**. Depois de normalizar a altura pro
solo, os pontos são jogados numa grade 32×32 e cada célula guarda estatísticas de
altura — captando também a **estrutura horizontal** (clareiras, agrupamento de copas)
que o GBR e o PointNet descartam.

Quatro canais por célula:

1. **Altura máxima** (CHM — modelo de altura do dossel);
2. **Altura média**;
3. **Densidade** (log do nº de pontos na célula);
4. **Desvio-padrão** da altura.

Isso forma um raster `32×32×4` (uma "imagem multicanal"), processado por uma **CNN 2D
pequena** (3 blocos conv+BN+ReLU com pooling → pooling global → cabeça densa). Como a
vista de cima é invariante a rotações/espelhamentos, treino com **aumento de dados**
(rot90 + flips) — barato e ajuda contra o overfit com poucas parcelas.

> É a única das três abordagens que enxerga o arranjo **horizontal** da floresta, não só
> o perfil de altura. Mais parâmetros que os outros → também a mais sensível ao tamanho
> da amostra.
