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

Ao remover outliers geométricos (parcelas de área > 0,5 ha ou compacidade < 0,6 — em
geral parcelas-transecto lineares ou fragmentos malformados) e corrigir o gap temporal,
**todos os seis modelos melhoram substancialmente**, e a CNN 3D deixa de ser instável
(R² salta de negativo para ≈ 0,50). Este é o primeiro resultado do trabalho, e não é
sutil: a qualidade da curadoria geométrica dos dados de entrada domina a escolha de
arquitetura em magnitude de efeito.

**Tabela 1 — Comparação entre modelos e variantes de pré-processamento** (RMSE em
Mg/ha; rRMSE em %; R² adimensional; maior R² e menor RMSE/rRMSE são melhores):
