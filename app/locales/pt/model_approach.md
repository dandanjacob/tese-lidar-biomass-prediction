> **Input:** 1025 atributos por parcela — 1024 alturas do dossel ordenadas + log(nº de pontos total).

O modelo prevê a **biomassa acima do solo (AGB)** de uma parcela a partir da sua
**nuvem de pontos LiDAR clipada** — o inventário de campo não entra na previsão, só
fornece o alvo de treino. Para cada parcela, a nuvem vira um vetor de tamanho fixo:

1. **Altura sobre o solo** — o solo é estimado localmente (mínimo de Z numa grade de 1 m) e subtraído de cada ponto.
2. **Filtro de dossel** — descartam-se retornos abaixo de 2 m (chão e sub-bosque).
3. **Amostragem** — sorteiam-se 1024 pontos de dossel (completa com zeros se houver menos).
4. **Ordenação** — as 1024 alturas são ordenadas, formando um vetor invariante à ordem dos pontos.
5. **Densidade** — acrescenta-se `log(nº de pontos)` como atributo, capturando a densidade do escaneamento.

Resultado: **1025 atributos** por parcela; o alvo é a **AGB pela fórmula M1** (Mg/ha).
