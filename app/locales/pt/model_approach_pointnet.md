Este modelo recebe a **nuvem de pontos crua** — sem extrair métricas, sem filtro de
dossel, sem ordenar. A única transformação é a que o escopo aceita:

1. **Altura sobre o solo** — o solo é estimado localmente (mínimo de Z numa grade de 1 m) e subtraído; cada ponto vira (x, y, altura).
2. **Referencial local** — XY centrado no centroide da parcela; os valores são divididos por uma escala fixa só para ficarem na ordem de 1.

Os pontos `(x, y, z)` entram direto na rede. Uma **PointNet** é invariante à ordem por
construção: um MLP compartilhado processa cada ponto, um **max-pool** agrega o conjunto
inteiro num vetor, e uma cabeça de regressão estima a AGB. Não há índice de ponto a
casar — por isso não precisa ordenar.

> Por limite de memória/CPU (não por engenharia de feature), guarda-se no máximo 8192
> pontos por parcela e sorteiam-se 2048 a cada passo. Sem ordenação e sem filtro: é a
> nuvem crua. Com poucas parcelas e sem GPU, é esperado que sobreajuste.
