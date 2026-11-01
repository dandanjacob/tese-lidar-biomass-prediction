**Contexto.** A biomassa acima do solo (AGB) é a variável de referência para quantificar
estoques de carbono florestal, mas sensores ópticos orbitais saturam em florestas
tropicais densas por enxergarem apenas o topo do dossel. O LiDAR aerotransportado mede
diretamente a estrutura vertical da vegetação — a dimensão com maior poder preditivo de
biomassa — e permite calibrar relações entre estrutura e AGB de campo que, em tese, se
estendem a áreas sem inventário.

**Objetivo.** Este trabalho pergunta, especificamente: dentro de um conjunto de parcelas
de inventário florestal amazônico com cobertura LiDAR pareada, qual fração da variância
na AGB medida em campo é explicada pela estrutura do dossel — e uma representação
parcimoniosa dessa estrutura (estatísticas agregadas de altura) generaliza tão bem
quanto arquiteturas de aprendizado profundo aplicadas à geometria bruta da nuvem de
pontos?

**Dados e método.** Cruzaram-se nuvens de pontos LiDAR do programa NASA CMS Brazil
(ORNL DAAC) com inventários florestais de campo em 28 sites amazônicos, resultando em
**493 parcelas pareáveis** (AGB de campo × nuvem de pontos LiDAR) após auditoria e
correção de bugs de geometria e pareamento — **325** após remoção de outliers de área e
forma. A biomassa de referência foi calculada árvore a árvore por equações alométricas
(Chave et al. 2014; Chambers et al. 2000; Goodman et al. 2013) e uma correção do
descompasso temporal entre voo LiDAR e medição de campo. Seis abordagens de modelagem
foram comparadas sob validação cruzada k-fold: um GBR sobre a distribuição completa de
alturas do dossel (1025 atributos), sua variante com redução de dimensionalidade (GBR
sobre *K* quantis, *K* ∈ {8,…,256}), um GBR e um Random Forest sobre 37 métricas
estruturais clássicas (*Area-Based Approach*), uma PointNet sobre a nuvem crua, e duas
CNNs — 2D sobre rasters de altura e 3D sobre voxels de ocupação.

**Resultados.** Testando cada tratamento de pré-processamento isoladamente contra a
mesma nuvem crua — projeção do solo, filtro de altura ≤1,3 m, remoção de outliers
geométricos de parcela, e correção de gap temporal, cada um sozinho, sem empilhar com os
demais (Seção 3.1) — a remoção de outliers isolada se mostrou, disparado, o tratamento
que mais importa: sozinha, já supera o pipeline com todos os tratamentos combinados em
quatro dos sete modelos. Projeção do solo e filtro de altura, isolados, têm efeito
pequeno; a correção de gap temporal isolada é, na maioria dos modelos, mais fraca que
não aplicar tratamento nenhum — ela só "ajuda" quando empilhada em cima da remoção de
outliers, cujo efeito domina. Na melhor variante de cada modelo — que para cinco deles é
justamente a remoção de outliers isolada —, a CNN 2D sobre rasters de altura obteve o
melhor resultado (R² = 0,547; rRMSE ≈ 41,7%), seguida por Random Forest (R² = 0,532),
GBR sobre a distribuição completa de alturas (R² = 0,526), ABA (R² = 0,514) e GBR sobre
quantis de altura (R² = 0,510); a CNN 3D sobre voxels (que só atinge seu melhor resultado
com o pipeline combinado completo, não isolado) ficou abaixo de todas essas (R² = 0,455);
a PointNet sobre a nuvem crua (idem, precisa do pipeline combinado) foi consistentemente
a mais fraca (R² ≈ 0,21). Já na ablação de dimensionalidade, **8 quantis de altura bastam
para superar o vetor completo de 1024 alturas** (R² = 0,43 vs. 0,39–0,42), e o ganho
adicional até 256 quantis é marginal — evidência de que a maior parte da alta dimensão
original era ruído alimentando sobreajuste, não sinal.

**Conclusão.** A estrutura vertical do dossel, resumida de forma simples, explica uma
fração moderada e competitiva (com a literatura de LiDAR aéreo tropical e com o produto
orbital GEDI) da variância em AGB — e fá-lo com modelos ordens de grandeza mais simples
que arquiteturas profundas sobre geometria bruta. Este resultado é lido com uma ressalva
central discutida no corpo do artigo: a validação cruzada aqui empregada é k-fold
aleatório, não *leave-one-site-out*, e portanto mede ajuste dentro da amostra de sítios
já vistos — não generalização para floresta amazônica não amostrada, que é o padrão mais
alto exigido por um uso operacional em contabilidade de carbono.

**Palavras-chave:** biomassa acima do solo; LiDAR aerotransportado; Amazônia;
aprendizado de máquina; redução de dimensionalidade; GEDI.
