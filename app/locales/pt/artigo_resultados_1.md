### 3.1 Efeito do controle de qualidade dos dados

Antes de comparar arquiteturas entre si, é preciso isolar um efeito que domina os
resultados: o pré-processamento. A Tabela 1 mostra o desempenho de cada modelo através
das cinco variantes do conjunto de treino (Seção 2.6), da mais crua à mais tratada.

O padrão é consistente entre todas as arquiteturas: **sem remoção de outliers e sem
correção de gap temporal, o desempenho é baixo e instável** — R² entre 0,11 e 0,30 na
maioria dos modelos, e a CNN 3D (voxel) chega a **R² negativo** (−0,03 a −0,09) nas
variantes `raw`/`full`/`ground_only`, o que significa, literalmente, que prever a AGB
média do conjunto de treino é uma estimativa melhor do que a saída do modelo. Isso é o
retrato de um modelo de alta capacidade (uma CNN 3D tem ordens de grandeza mais
parâmetros que um Gradient Boosting sobre 37 métricas) tentando ajustar ruído de rótulo
e de geometria — o mesmo ruído que as correções de outlier e gap existem para remover.

Decompondo as duas correções — que a Tabela 1 reporta separadamente, mas que descrições
anteriores deste texto tratavam como um efeito único — fica claro que elas não têm o
mesmo peso. Ao remover outliers geométricos (parcelas de área > 0,5 ha ou compacidade <
0,6 — em geral parcelas-transecto lineares ou fragmentos malformados), **todos os seis
modelos melhoram substancialmente** sozinhos, sem qualquer correção de gap: a CNN 3D
deixa de ser instável (R² de ≈ 0,08 para ≈ 0,45), a CNN 2D vai de 0,30 para 0,53 e o
Random Forest de 0,29 para 0,52. A correção do gap temporal, aplicada por cima do
conjunto já sem outliers, tem efeito **pequeno e inconsistente** entre arquiteturas —
leve queda na ABA, no Random Forest, na CNN 2D e na CNN 3D (R² cai alguns centésimos em
cada caso), leve ganho só na PointNet. Ou seja: o salto de desempenho relatado nesta
seção vem quase inteiramente da remoção de outliers geométricos, não da correção
temporal — que ainda assim é mantida como parte do pipeline por ser metodologicamente
correta (alinhar DBH/altura à data do voo LiDAR), não porque eleve o R². Este é o
primeiro resultado do trabalho, e não é sutil: a qualidade da curadoria geométrica dos
dados de entrada domina a escolha de arquitetura em magnitude de efeito.

**Tabela 1 — Comparação entre modelos e variantes de pré-processamento** (RMSE em
Mg/ha; rRMSE em %; R² adimensional; maior R² e menor RMSE/rRMSE são melhores):
