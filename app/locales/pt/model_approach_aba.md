> **Input:** 37 métricas estruturais do dossel — percentis de altura, cobertura de dossel, rugosidade do CHM e densidade vertical.

A parcela vira um **vetor de métricas estruturais** — não a nuvem em si. É a
abordagem clássica da literatura de LiDAR florestal (*Area-Based Approach*, ABA) e,
ao contrário das redes, deixa explícito **quais propriedades da floresta** sustentam
a previsão.

Depois de normalizar a altura pro solo (mínimo de Z numa grade de 1 m), extraem-se
**37 métricas** em três famílias:

1. **Distribuição de altura** — máxima, média, desvio, CV, percentis (p05…p99),
   assimetria, curtose e *canopy relief ratio*.
2. **Densidade vertical / cobertura** — fração de retornos acima de 2 m, deciles de
   densidade (D0…D9), entropia vertical e densidade de pontos.
3. **Convolucionais (espaciais)** — a parcela vira um **CHM** (grade 1 m) e aplica-se
   um **Laplaciano 3×3** para medir a rugosidade/textura do dossel, além de
   *gap fraction* e heterogeneidade espacial da densidade de pontos.

Essas 37 métricas alimentam um **Gradient Boosting** (mesmos hiperparâmetros e
leave-one-site-out das demais abordagens, para comparação justa).

> É a abordagem com **melhor desempenho** aqui — e a única **interpretável**: a tabela
> de importância mostra que a rugosidade convolucional do dossel e os deciles de
> densidade são os atributos que mais pesam.
