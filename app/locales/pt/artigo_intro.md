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

### 1.2 O problema em aberto

A literatura de estimativa de AGB por LiDAR aerotransportado é madura (Asner & Mascaro,
2014; d'Oliveira et al., 2012; Longo et al., 2016; Bispo et al., 2020) e, mais
recentemente, passou a incorporar aprendizado profundo diretamente sobre a nuvem de
pontos bruta (Oehmcke et al., 2024). Um ponto, porém, permanece pouco caracterizado
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

### 1.4 Escopo e o que este artigo não responde

Por rigor, delimita-se explicitamente o que **não** está dentro do escopo do resultado
central: a validação aqui é k-fold aleatório, não *leave-one-site-out* — portanto mede
ajuste dentro da amostra de sítios já vistos no treino, não generalização espacial para
floresta amazônica não amostrada. Também não há, nesta versão, quantificação formal de
incerteza por predição, nem análise de sensibilidade da escolha da fórmula alométrica de
referência (M1, entre três candidatas). Essas lacunas são discutidas com profundidade na
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
