### 1.1 Motivação

Cerca de metade da biomassa vegetal é carbono. A Amazônia concentra uma das maiores
reservas terrestres desse elemento, e quantificar sua biomassa acima do solo (*aboveground
biomass*, AGB) com precisão espacial é o que sustenta inventários nacionais de emissões,
mecanismos de compensação como o REDD+, mercados de crédito de carbono e o
acompanhamento de metas do Acordo de Paris. Sem estimativas confiáveis e espacialmente
distribuídas, não é possível distinguir floresta intacta de degradada, dimensionar
perdas por desmatamento, nem validar os modelos do ciclo global de carbono que dependem
desses números como entrada.

O gargalo histórico dessa estimativa é que AGB depende fortemente da **estrutura
vertical** da floresta — altura das árvores, densidade e arquitetura do dossel —,
exatamente a dimensão que sensores ópticos orbitais (Landsat, Sentinel) enxergam mal:
eles registram a reflectância do topo do dossel e saturam em florestas densas de alta
biomassa, como a maior parte da Amazônia intacta. O LiDAR (*Light Detection and
Ranging*) resolve esse problema na origem — pulsos laser penetram o dossel e retornam um
perfil tridimensional da vegetação, medindo diretamente altura e estrutura vertical.
Isso o torna substancialmente mais acurado que índices espectrais em floresta tropical
de alta biomassa e permite calibrar relações alométricas (métricas LiDAR ↔ AGB de campo)
que, em princípio, podem ser estendidas no espaço e no tempo — reduzindo a dependência de
inventários de campo, caros e logisticamente inviáveis na escala da bacia amazônica.

### 1.2 Trabalhos relacionados e o problema em aberto

A biomassa de referência desta tese é calculada pelas mesmas equações alométricas que
sustentam boa parte da literatura de carbono florestal tropical: Chave et al. (2014)
para árvores vivas, Chambers et al. (2000) para árvores mortas em pé e Goodman et al.
(2013) para palmeiras — a mesma base alométrica usada, por exemplo, por Longo et al.
(2016) na Amazônia.

A literatura de estimativa de AGB por LiDAR aerotransportado em floresta tropical é
madura e compartilha um padrão metodológico que vale destacar frente a este trabalho:
Asner & Mascaro (2014) — 804 parcelas de 1 ha em quatro países tropicais, R² = 0,90
usando altura de topo de dossel (TCH) combinada a área basal e densidade de madeira —
validam por **sítio**, não por parcela embaralhada aleatoriamente. Longo et al. (2016),
na Amazônia brasileira (359 parcelas, intacta e degradada), reporta R² ≈ 0,70 por
regressão sobre métricas LiDAR agregadas — mais próximo em escopo e escala deste
trabalho, mas também sem validação k-fold aleatória explícita. Bispo et al. (2020) —
atribuída ao Cerrado, não à Amazônia, após a correção de erro desta auditoria (Seção
4.7) — reporta RMSE = 67,6 Mg/ha, rRMSE = 36,0%, R² = 0,58 usando só métricas LiDAR,
números na mesma ordem de grandeza dos obtidos aqui (RMSE ≈ 73–79 Mg/ha, rRMSE ≈
43–46%, variante sem outliers), apesar do bioma diferente. d'Oliveira et al. (2012), em
floresta manejada no Acre, reporta R² = 0,63–0,72 em escala de **talhão** (1.000 ha) —
suporte espacial muito maior que a parcela individual usada aqui, o que limita a
comparabilidade direta apesar da mesma região amazônica.

Mais recentemente, a literatura passou a incorporar aprendizado profundo diretamente
sobre a nuvem de pontos bruta: Oehmcke et al. (2024), em floresta temperada
dinamarquesa, encontra uma CNN de Minkowski superando PointNet, KPConv e uma abordagem
*area-based* clássica — o oposto do padrão encontrado neste trabalho (Seção 3.2), em
que a abordagem parcimoniosa vence a PointNet por uma margem grande. A leitura mais
provável não é uma contradição entre os dois resultados, mas um efeito de **regime de
amostra**: florestas temperadas manejadas tendem a ter conjuntos de treino bem maiores
e menos heterogêneos estruturalmente que os 325 pares LiDAR-inventário amazônicos
disponíveis aqui, o que é consistente com a hipótese central da Seção 1.3 — capacidade
representacional alta exige volume de dado proporcional para não sobreajustar.

Os produtos orbitais da NASA (GEDI L4A/L4B) operam em escala e sensor distintos — LiDAR
espacial *footprint* (~25 m) ou grade de 1 km, não nuvem aérea densa por parcela — e
servem aqui como baliza de ordem de grandeza, não como comparação direta: a validação
independente do GEDI L4A contra LiDAR aéreo em savana africana (Li et al., 2024) reporta
R² ≈ 0,42, abaixo de todos os modelos desta tese na variante sem outliers, mas sobre um
problema de estimação substancialmente mais difícil (resolução espacial muito menor,
amostra espacialmente esparsa).

Um ponto, porém, permanece pouco caracterizado
empiricamente para o contexto amazônico: **a relação entre a complexidade
representacional de um modelo e sua capacidade de generalizar quando o número de
parcelas rotuladas é pequeno** (nesta tese, no máximo 493 parcelas, 325 após controle de
qualidade geométrica) — um regime de amostra reduzida em relação à dimensionalidade de
uma nuvem de pontos LiDAR bruta, que facilmente ultrapassa milhares de pontos por
parcela.

### 1.3 Pergunta de pesquisa

Este trabalho investiga uma pergunta específica, deliberadamente mais restrita do que a
aspiração de "mapear a biomassa da Amazônia":

> **Dentre as parcelas de inventário florestal amazônico com cobertura LiDAR
> aerotransportado pareada (mesmo conjunto de campanhas e sítios), qual fração da
> variância na AGB medida em campo é explicada pela estrutura vertical do dossel — e uma
> representação parcimoniosa dessa estrutura (estatísticas agregadas de altura) captura
> tanto sinal quanto arquiteturas de aprendizado profundo aplicadas à geometria bruta da
> nuvem de pontos?**

A hipótese de trabalho, motivada pela teoria estatística clássica de viés-variância sob
alta dimensionalidade e poucas amostras, é que representações de alta capacidade
(PointNet sobre nuvem crua, CNN 3D sobre voxels) sofrem desproporcionalmente mais de
sobreajuste que representações parcimoniosas (estatísticas agregadas de altura),
independentemente da riqueza estrutural que a geometria bruta, em princípio, carrega.

Essa pergunta se desdobra em quatro objetivos específicos, cada um respondido numa
subseção dedicada dos Resultados (Seção 3):

1. Isolar o efeito do controle de qualidade geométrica das parcelas e da correção do
   gap temporal entre voo LiDAR e medição de campo sobre o desempenho dos modelos,
   separando os dois efeitos em vez de tratá-los como uma correção única (**§3.1**).
2. Comparar, sob o mesmo protocolo de validação, seis abordagens de modelagem que vão
   de estatísticas agregadas interpretáveis (ABA, Random Forest) a aprendizado profundo
   sobre a geometria bruta (PointNet, CNN 2D, CNN 3D), identificando qual representação
   generaliza melhor neste regime de amostra pequena (**§3.2**).
3. Medir como o desempenho do GBR varia com a dimensionalidade da representação de
   altura do dossel (de 8 a 1024 atributos), para testar se mais informação bruta
   realmente se traduz em mais sinal preditivo ou se é absorvida como ruído de
   sobreajuste (**§3.3**).
4. Identificar, através do único modelo desta comparação com importância de variável
   interpretável (ABA), quais propriedades estruturais do dossel mais sustentam a
   previsão de AGB (**§3.4**).

### 1.4 Escopo e o que este artigo não responde

Por rigor, delimita-se explicitamente o que **não** está dentro do escopo do resultado
central: a validação aqui é k-fold aleatório, não *leave-one-site-out* — portanto mede
ajuste dentro da amostra de sítios já vistos no treino, não generalização espacial para
floresta amazônica não amostrada. Há, agora, um intervalo de predição por parcela
(conformal prediction sobre resíduos out-of-fold, Seção 4.3) — mas ele cobre só a
incerteza do modelo estrutura→AGB, não o erro alométrico da fórmula de referência nem a
incerteza de medição de campo propagados até o alvo de treino. Uma análise de
sensibilidade (Seção 4.4) mostra, além disso, que o próprio resultado "CNN 2D é a melhor
arquitetura" não é robusto à escolha da fórmula alométrica de referência — sob densidade
de madeira específica por espécie (M3) em vez de uniforme (M1), o Random Forest assume a
liderança. Essas lacunas são discutidas com profundidade na
Seção 4 e não são triviais: são precisamente o que separa "a estrutura do dossel explica
biomassa nesta amostra" de "este pipeline está pronto para mapear a Amazônia" — a segunda
afirmação é mais forte do que os dados aqui sustentam.

### 1.5 Estrutura do artigo

A Seção 2 descreve a proveniência dos dados, o pipeline de pré-processamento auditado, a
biomassa de referência e as seis abordagens de modelagem comparadas. A Seção 3 apresenta
os resultados: o efeito do controle de qualidade geométrica e da correção de gap
temporal, a comparação entre arquiteturas, o diagnóstico do melhor modelo e a ablação de
dimensionalidade que motiva o argumento central do trabalho. A Seção 4 discute
criticamente os resultados — incluindo suas limitações de validação — e os posiciona
frente à literatura e ao produto orbital GEDI da NASA.
