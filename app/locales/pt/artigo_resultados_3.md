### 3.3 Ablação de dimensionalidade: o achado central

A comparação mais direta com a pergunta de pesquisa deste trabalho não é entre
arquiteturas, mas entre **quantidade de informação de altura** fornecida ao mesmo
algoritmo (Gradient Boosting). A Figura 3 mostra o R² de validação cruzada em função do
número de quantis de altura usados como atributo, de 8 a 256, com o vetor completo de
1024 alturas ordenadas como referência.

O padrão contraria a intuição de que "mais informação bruta é sempre melhor": **o vetor
completo de 1024 alturas (R² ≈ 0,39–0,42) é superado já pela representação mais
grosseira da ablação, 8 quantis (R² ≈ 0,43)** — menos de 1% da dimensionalidade original
captura mais sinal preditivo, não menos. O ganho de 8 para 16 quantis é real e
consistente (R² 0,426 → 0,442); daí em diante, até 64 quantis, o desempenho **satura**
(R² oscila entre 0,441 e 0,444, dentro do ruído do k-fold); só volta a subir de forma
perceptível em 256 quantis (R² ≈ 0,455) — um ganho pequeno pelo custo de 16× mais
atributos que o ponto de saturação.

**Figura 3 — R² de validação cruzada vs. número de quantis de altura (escala log em x).**

A leitura estatística é direta: com 325 parcelas de treino e um vetor de 1024 atributos
altamente correlacionados entre si (alturas vizinhas de uma distribuição ordenada), o
modelo tem mais graus de liberdade que sinal identificável — o excesso de dimensão é
absorvido como ruído de treino (sobreajuste), não como capacidade preditiva adicional.
Reduzir para algumas dezenas de quantis não é perda de informação relevante; é remoção
de ruído correlacionado que atrapalhava a otimização.

### 3.4 O que o modelo interpretável revela

A única abordagem desta comparação que expõe explicitamente **quais propriedades da
floresta** sustentam a previsão é o ABA (GBR sobre 37 métricas estruturais nomeadas). A
Figura 4 mostra a importância das 10 variáveis mais relevantes no modelo ABA
gap-corrigido/sem-outliers.

**Figura 4 — Importância de variáveis, modelo ABA (top 10).**

Os percentis de altura do dossel (p05, p75, p50, p10, p25) dominam a importância
agregada — reforçando, por uma via distinta da ablação de dimensionalidade, que a
distribuição de altura por si só já carrega a maior parte do sinal preditivo de AGB
nesta amostra. As demais variáveis relevantes — entropia da densidade vertical
(`vfd_entropy`), rugosidade convolucional do dossel (`lap_roughness`, derivada de um
Laplaciano 3×3 sobre o CHM) e densidade de pontos (`pt_density`) — carregam informação
complementar sobre heterogeneidade estrutural que os percentis sozinhos não capturam, e
ajudam a explicar por que o raster 2D (que também enxerga heterogeneidade horizontal)
supera marginalmente o ABA puro.
