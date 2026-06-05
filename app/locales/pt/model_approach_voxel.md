Aqui a parcela vira um **volume 3D**. Depois de normalizar a altura pro solo, o espaço
é dividido numa grade 16×16×16 (XY da parcela × altura de 0 a 40 m) e cada voxel guarda
o que há ali. Uma **CNN 3D** convolve no volume, enxergando a estrutura **vertical e
horizontal ao mesmo tempo** — é a mais "cheia" das três convolucionais.

Dois canais por voxel:

1. **Ocupação** — 1 se há pelo menos um ponto no voxel;
2. **Densidade** — log do nº de pontos no voxel.

Forma um tensor `16×16×16×2`, processado por uma **CNN 3D** (3 blocos conv3d+BN+ReLU com
pooling → pooling global → cabeça densa). O aumento de dados gira a parcela em 90° **no
plano horizontal** (em torno do eixo vertical) e espelha em X/Y — o eixo de altura nunca
é girado, pois cabeça e base do dossel não são intercambiáveis.

> Convolução 3D é a representação mais completa, mas também a mais pesada e a mais
> propensa a overfit: são muito mais parâmetros para apenas ~380 parcelas.
