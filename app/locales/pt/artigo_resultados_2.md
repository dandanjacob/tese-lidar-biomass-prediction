### 3.2 Comparação entre arquiteturas, na melhor configuração

Restringindo a comparação à melhor variante de cada modelo (gap-corrigido, sem
outliers, *n* = 325), emerge uma ordem clara: **CNN 2D sobre rasters de altura > Random
Forest ≈ CNN 3D sobre voxels > ABA/GBR estrutural > GBR sobre a distribuição completa de
alturas ≫ PointNet sobre a nuvem crua.**

A CNN 2D vence por uma margem modesta sobre Random Forest e CNN 3D (diferença de R² da
ordem de 0,02–0,03 — dentro da variabilidade esperada de um k-fold de 5 dobras), o que
sugere que a estrutura **horizontal** do dossel capturada pelo raster (clareiras,
agrupamento de copas — informação que o ABA e o GBR de alturas descartam por trabalhar
só com a distribuição vertical agregada) carrega sinal real, mas marginal frente à
estrutura vertical já capturada pelas abordagens mais simples.

O resultado mais informativo da tabela, porém, é o **fracasso relativo da PointNet**:
mesmo na sua melhor configuração, R² ≤ 0,20 — pior que *todos* os outros cinco modelos,
incluindo o GBR mais simples da comparação. A PointNet recebe a representação mais rica
em princípio (a nuvem de pontos crua, sem nenhuma agregação), mas é também a que mais
depende de volume de dados para aprender uma função de agregação útil via max-pooling —
e 325 parcelas de treino são, evidentemente, poucas para isso.

**Figura 2 — Predito × observado, melhor modelo (CNN 2D, gap-corrigido, sem
outliers).** A dispersão em torno da diagonal 1:1 mostra o padrão típico de um modelo
com R² moderado: tendência central capturada, mas variância residual substancial,
sobretudo nas parcelas de AGB mais alta — o regime onde erros absolutos (Mg/ha) pesam
mais para qualquer aplicação de contabilidade de carbono.
