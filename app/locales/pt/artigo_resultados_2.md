### 3.2 Comparação entre arquiteturas, na melhor configuração

Restringindo a comparação à melhor variante de CADA modelo individualmente (*n* = 325) —
e não assumindo de antemão que essa variante é sempre a gap-corrigida, já que a Seção
3.1 mostrou que a correção de gap tem efeito pequeno e às vezes negativo —, a variante
líder é **"sem outliers" (sem correção de gap) para cinco dos seis modelos**; só a
PointNet melhora com o gap. A ordem que emerge é: **CNN 2D sobre rasters de altura
(R²=0,527) > Random Forest (0,524) > ABA (0,506) ≈ GBR sobre 32 quantis de altura
(0,504) > GBR sobre a distribuição completa de 1024 alturas (0,480) > CNN 3D sobre
voxels (0,455) ≫ PointNet sobre a nuvem crua (0,212, único caso em que a variante
gap-corrigida vence).** (Esta ordem usa a fórmula alométrica de referência M1; a Seção
4.4 mostra que ela não é robusta à troca para M3 — o Random Forest assume a liderança.)

Essa ordem corrige uma leitura anterior deste texto, que agrupava Random Forest e CNN 3D
como equivalentes: usando a variante correta por modelo, a CNN 3D fica **abaixo** de
todos os modelos estruturais/estatísticos (ABA, GBR em ambas as representações), não
empatada com o Random Forest. A CNN 2D ainda vence por uma margem modesta sobre Random
Forest (diferença de R² ≈ 0,003 — dentro da variabilidade esperada de um k-fold de 5
dobras; a Seção 4.5 reporta um teste pareado formal entre CNN 2D, Random Forest e CNN 3D
que não rejeita a hipótese de diferença nula entre as três), o que sugere que a
estrutura **horizontal** do dossel capturada pelo raster (clareiras, agrupamento de
copas — informação que o ABA e o GBR de alturas descartam por trabalhar só com a
distribuição vertical agregada) carrega sinal real, mas marginal frente à estrutura
vertical já capturada pelas abordagens mais simples.

O resultado mais informativo da tabela, porém, é o **fracasso relativo da PointNet**:
mesmo na sua melhor configuração, R² ≈ 0,21 — pior que *todos* os outros cinco modelos,
incluindo o GBR mais simples da comparação. A PointNet recebe a representação mais rica
em princípio (a nuvem de pontos crua, sem nenhuma agregação), mas é também a que mais
depende de volume de dados para aprender uma função de agregação útil via max-pooling —
e 325 parcelas de treino são, evidentemente, poucas para isso.

**Figura 2 — Predito × observado, melhor modelo (CNN 2D, gap-corrigido, sem
outliers).** A dispersão em torno da diagonal 1:1 mostra o padrão típico de um modelo
com R² moderado: tendência central capturada, mas variância residual substancial,
sobretudo nas parcelas de AGB mais alta — o regime onde erros absolutos (Mg/ha) pesam
mais para qualquer aplicação de contabilidade de carbono.
