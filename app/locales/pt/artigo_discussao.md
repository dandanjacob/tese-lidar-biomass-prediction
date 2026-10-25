### 4.1 O achado central: parcimônia supera profundidade

O resultado mais robusto deste trabalho não é o R² = 0,53 da CNN 2D — é a constatação,
convergente por duas vias independentes (ablação de dimensionalidade, Seção 3.3; e
importância de variáveis do modelo interpretável, Seção 3.4), de que **a distribuição de
altura do dossel, resumida em poucas dezenas de números, carrega quase todo o sinal
preditivo de AGB disponível nesta amostra**. Arquiteturas de maior capacidade
representacional (PointNet sobre nuvem crua, CNN 3D sobre voxels) não convertem essa
riqueza geométrica adicional em desempenho preditivo superior — pelo contrário, a
PointNet é consistentemente a pior de todas, e a CNN 3D só se torna competitiva depois de
um controle de qualidade de dados agressivo. Este é o enquadramento correto da
contribuição do trabalho: não "qual arquitetura é a melhor para AGB por LiDAR", mas **em
que ponto a complexidade do modelo deixa de ajudar e passa a atrapalhar, dado um
orçamento de poucas centenas de parcelas rotuladas** — um regime realista para a maior
parte dos estudos de campo na Amazônia, onde inventários de centenas de parcelas já
representam um esforço logístico considerável.

### 4.2 A limitação mais importante: validação espacialmente ingênua

A validação cruzada k-fold aleatória usada em todos os resultados da Seção 3 particiona
**parcelas**, não **sítios**. É importante separar dois mecanismos distintos pelos
quais isso pode inflar o R² reportado — eles têm força de evidência diferente, e
merecem tratamento diferente.

**(a) Pseudo-replicação dentro de uma mesma quadra/campo — mecanismo que não depende de
heterogeneidade biológica entre sítios.** Muitas das 325 parcelas do conjunto final não
são amostras independentes de "a floresta amazônica": são **subdivisões contíguas de um
mesmo campo original**. Dos 325, **125 (38%) pertencem a um grupo de ≥2 quadras-irmãs**
derivadas do mesmo `Name` de campo (ex.: CAU tem campos como T17–T22 cada um dividido em
4–5 quadras adjacentes; FST tem 4 campos divididos em 5 quadras cada) — e **um único
sítio (CAU) responde por 85 das 325 parcelas (26% da amostra inteira)**. Quadras vizinhas
de um mesmo campo compartilham, literalmente, o mesmo dossel contínuo ou dosséis a
poucas dezenas de metros um do outro: seus vetores de altura são amostras altamente
correlacionadas da mesma realização física de floresta, não realizações independentes
de "estrutura típica da Amazônia". Um modelo pode ajustar o padrão numérico específico
de um campo (treino) e prever bem sua quadra-irmã (teste) sem ter aprendido nada que se
transporte para um hectare genuinamente não amostrado — isso é verdade **mesmo sob a
hipótese de que toda a floresta amazônica fosse biologicamente homogênea**, porque o
problema não é "os sítios são diferentes entre si", é "as unidades de teste e treino,
dentro de um sítio, não são estatisticamente independentes". Esse mecanismo é o mais
sólido dos dois e o que mais pesa nesta ressalva.

**(b) Confundidor de campanha/densidade de varredura — mecanismo condicional, cuja força
depende de quanto os sítios de fato diferem entre si.** Se a floresta amostrada for de
fato aproximadamente homogênea entre sítios (mesmo bioma, mesma faixa de biomassa típica,
sem efeito sistemático de solo/perturbação/região correlacionado com o alvo) e nenhuma
feature identificar o sítio diretamente, este segundo mecanismo é fraco — e a crítica de
que "misturar sítios é um problema" perde força nesse cenário, como argumentado. Mas a
premissa de homogeneidade não é demonstrada pelos próprios dados do projeto: o pipeline
de alometria (`config/allometry.yaml`) usa curvas altura-diâmetro **regionais distintas**
(Amazônia centro-oriental, ocidental, Escudo das Guianas, Escudo Brasileiro) precisamente
porque a relação estrutura↔biomassa varia por região — e a feature `log(nº de pontos)` /
`pt_density`, presente em todos os modelos, captura densidade de varredura, que
correlaciona com campanha de voo e, por acaso, com região. Este mecanismo permanece
**plausível, não testado** (Seção 4.5) — mais fraco que (a), mas não eliminado.

A consequência prática: mesmo que (b) se revele desprezível após a análise estratificada
por campanha (Seção 4.5, ainda pendente), o mecanismo (a) por si só já é suficiente para
que os números da Seção 3 devam ser lidos como "quanto da variância é explicada quando
se permite reaproveitar informação de quadras vizinhas do mesmo campo" — não "quão bem
isto generaliza para um hectare novo da Amazônia", que é a pergunta que a motivação do
trabalho (Seção 1.1) coloca. Fechar essa lacuna exige reportar uma validação agrupada por
sítio (ou, de forma ainda mais conservadora, por campo/`Name` de origem da quadra) como
métrica principal, não como nota de rodapé — com a ressalva prática de que os 18 sítios
do conjunto final têm tamanhos muito desiguais (de 4 a 85 parcelas), então um
*leave-one-site-out* ingênuo produzirá folds de variância muito heterogênea e deve ser
reportado por sítio, não só agregado. É esperável que o R² caia sob esse protocolo mais
exigente. Isto não invalida o achado central da Seção 4.1 (a relação entre
dimensionalidade e desempenho deve se manter qualitativamente, já que ambos os mecanismos
acima afetam todos os modelos comparados de forma semelhante), mas invalida qualquer
leitura dos números absolutos de R²/RMSE como medida de prontidão operacional.

### 4.3 Ausência de quantificação de incerteza

A motivação declarada deste trabalho — contabilidade de carbono, REDD+, mercados de
crédito — é um domínio em que uma estimativa pontual de AGB sem intervalo de predição
tem utilidade limitada: qualquer aplicação de compensação ou relatório de emissões exige
saber não só o valor central, mas o **intervalo de confiança** da estimativa por parcela
ou por pixel. As métricas reportadas neste artigo (R², RMSE, rRMSE) descrevem o
comportamento agregado do modelo sobre o conjunto de teste; nenhuma delas produz, por
si só, um intervalo de predição individual. Preencher essa lacuna — por *bootstrap*,
predição conforme (*conformal prediction*), ou propagação do erro alométrico da Seção 2.4
até o alvo de treino — é pré-condição para qualquer uso além da pesquisa exploratória.

### 4.4 O alvo de treino é, ele mesmo, um modelo

A AGB de campo usada como alvo de treino não é uma medição direta: é a saída de uma
equação alométrica (Seção 2.4) aplicada a medições de campo (DBH, altura, espécie), e
essa equação tem incerteza própria, documentada na literatura que a origina (Chave et
al., 2014). Este trabalho usa exclusivamente **M1** (densidade de madeira uniforme, ρ =
0,6 g/cm³) como alvo, descartando as variantes M2 (densidade por tipo de árvore) e M3
(densidade específica por espécie) sem uma análise de sensibilidade que avalie o quanto
os resultados da Seção 3 mudam sob um alvo diferente. Como as três fórmulas convergem
para valores distintos de AGB por parcela, a escolha de M1 é, na prática, uma decisão
metodológica com efeito não quantificado sobre os números reportados — e uma fonte de
incerteza que não está sendo propagada (Seção 4.3).

### 4.5 Confundidores de campanha e densidade de varredura

As nuvens de pontos usadas neste trabalho vêm de campanhas de voo distintas — anos
diferentes, sensores possivelmente distintos, densidades de varredura variáveis — e uma
das features usadas por praticamente todas as abordagens (`log(nº de pontos)` ou
`pt_density`) captura diretamente essa densidade de aquisição, não uma propriedade da
floresta. Isso abre a possibilidade de que parte do R² reportado reflita o modelo
aprendendo a **identificar a campanha** (que pode estar correlacionada com a região e,
por acaso, com a biomassa típica daquela região) em vez de aprender a relação estrutura
↔ biomassa que se pretende generalizar. Nenhuma análise de desempenho estratificada por
campanha foi conduzida nesta versão para descartar essa hipótese.

### 4.6 Qualidade do rótulo e heterogeneidade de área

A auditoria de dados (Apêndice — Qualidade de Dados) documenta parcelas de área muito
pequena (~0,02 ha) gerando AGB por hectare implausivelmente alta — acima de 1500 Mg/ha,
mais que o dobro do teto fisicamente plausível para floresta tropical densa —, um
artefato estatístico de dividir uma contagem pequena de árvores por uma área minúscula.
O critério de remoção de outliers usado nesta versão (área > 0,5 ha OU compacidade < 0,6)
mitiga parte do problema, mas parcelas de 0,02 ha a 1 ha permanecem misturadas no
conjunto de treino, e uma AGB por hectare estimada sobre poucas árvores tem variância
amostral estruturalmente maior que a mesma métrica sobre uma parcela de 1 ha — o que
significa que as métricas agregadas de RMSE/R² da Seção 3 não são igualmente confiáveis
para todas as parcelas do conjunto, mas isto não é reportado de forma estratificada.

### 4.7 Números da literatura: verificação concluída (três erros corrigidos)

A comparação da Seção 3.5 usava, em versões anteriores deste texto, valores extraídos
de fontes primárias por pesquisa automatizada sem verificação adversarial linha a
linha. Essa verificação foi concluída e encontrou três erros, já corrigidos no texto
atual: (i) Bispo et al. (2020) estava atribuído à Amazônia com R² = 0,58 / rRMSE =
36,0% — o estudo é sobre o Cerrado brasileiro e os valores reais são R² = 0,93 / rRMSE
= 13% (modelo só-LiDAR); (ii) o DOI citado para Asner & Mascaro (2014) apontava para um
artigo diferente (albedo boreal, mesma revista/volume); (iii) o número do GEDI L4A em
savana africana (R² ≈ 0,42, correto) estava atribuído a "Naidoo et al." — o autor
líder correto é Li et al. (2024), com Naidoo como coautor. Longo et al. (2016) e
Oehmcke et al. (2024) foram confirmados sem ressalva. Esta correção ilustra exatamente
o risco que a versão anterior deste parágrafo já havia antecipado: um número mal
transcrito — ou, neste caso, três — compromete a credibilidade de toda a comparação
até ser verificado.

### 4.8 Síntese e trabalho futuro

Em ordem de prioridade para que este trabalho evolua de exploração metodológica para
resultado defensável de dissertação:

1. **Validação LOSO** (Seção 4.2) como métrica principal, k-fold aleatório rebaixado a
   referência otimista secundária.
2. **Intervalos de predição** (Seção 4.3) — bootstrap ou conformal, com cobertura
   empírica reportada.
3. **Análise de sensibilidade alométrica** (Seção 4.4) — resultados da Seção 3 repetidos
   sob M2 e M3.
4. ~~**Verificação adversarial da literatura** (Seção 4.7) antes de qualquer citação em
   versão final.~~ Concluída — três erros corrigidos (ver Seção 4.7).
5. **Estratificação por campanha e por tamanho de parcela** (Seções 4.5–4.6) para
   descartar confundidores e reportar honestamente onde o modelo é, e não é, confiável.
6. Avaliar formalmente o *ensemble* (média simples de raster + RF + voxel, que a
   exploração preliminar do projeto situa acima de qualquer modelo isolado) sob o mesmo
   protocolo LOSO — um ganho medido sob k-fold aleatório pode não sobreviver ao protocolo
   mais exigente.

Nenhum desses pontos invalida o achado central da Seção 4.1. Pelo contrário: se a
relação entre parcimônia e desempenho se mantiver sob validação LOSO — o teste mais
rigoroso disponível com os dados atuais —, ela se torna uma contribuição metodológica
transferível para outros contextos de estimativa de biomassa por LiDAR com amostras de
campo reduzidas, para além do caso amazônico específico deste trabalho.
