A coleta LiDAR (NASA/ORNL) está organizada em uma hierarquia:

- **Site (sítio)** — região monitorada (ex.: ANA, DUC, TAP).
- **Área** — recorte catalogado dentro de um site (ex.: A01), sobrevoado em uma ou mais **campanhas** (anos distintos).
- **Tile** — a nuvem de pontos de cada área/campanha **não vem inteira**: ela é subdividida em vários **tiles**, arquivos `.laz` retangulares menores, que são a unidade atômica de dado. O inventário completo da NASA tem **3.152 tiles**.

O cruzamento com o inventário de campo segue três etapas:

1. **Interseção (cobertura ≥ 99,9% por campanha)** — mantemos cada **parcela** de inventário cujo polígono tem **≥ 99,9% da área dentro da cobertura contígua de uma campanha** (tiles vizinhos do mesmo voo, unidos; subcampanhas a/b do mesmo ano contam como uma). Resultado: **553 parcelas** com cobertura, distribuídas por **242 tiles** (somando todas as campanhas).
2. **Menor gap temporal** — como uma mesma parcela costuma coincidir com várias campanhas, escolhemos para cada parcela apenas a campanha de **menor diferença de anos** entre o voo LiDAR e a medição de campo. Esse filtro seleciona **124 tiles** distintos.
3. **Clip** — cada tile selecionado é **recortado ao polígono da parcela**, gerando uma nuvem de pontos por parcela. É o que a métrica **Parcelas clippadas** acompanha (etapa em andamento).
