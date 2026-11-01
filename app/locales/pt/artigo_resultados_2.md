### 3.2 Comparação entre arquiteturas, na melhor configuração

Restringindo a comparação à melhor variante de CADA modelo individualmente (*n* = 325) —
e não assumindo de antemão qual tratamento essa variante usa, já que a Seção 3.1 mostrou
que cada tratamento isolado tem efeito muito diferente —, a variante líder é **"só
outliers" (isolada, sem solo/filtro/gap) para cinco dos seis modelos**; CNN 3D e
PointNet são as exceções, precisando do pipeline combinado completo para atingir seu
melhor resultado. A ordem que emerge é: **CNN 2D sobre rasters de altura (R²=0,547) >
Random Forest (0,532) > GBR sobre a distribuição completa de 1024 alturas (0,526) > ABA
(0,514) ≈ GBR sobre 32 quantis de altura (0,510) > CNN 3D sobre voxels (0,455, pipeline
combinado) ≫ PointNet sobre a nuvem crua (0,212, pipeline combinado, único caso em que a
variante gap-corrigida vence).** (Esta ordem usa a fórmula alométrica de referência M1;
a Seção 4.4 mostra que ela não é robusta à troca para M3 — o Random Forest assume a
liderança, embora essa análise de sensibilidade ainda não tenha sido refeita sobre as
variantes isoladas identificadas aqui, ver ressalva ao final da Seção 4.4.)

Essa ordem corrige uma leitura anterior deste texto, que agrupava Random Forest e CNN 3D
como equivalentes: usando a variante correta por modelo, a CNN 3D fica **abaixo** de
todos os modelos estruturais/estatísticos (ABA, GBR em ambas as representações), não
empatada com o Random Forest. A CNN 2D ainda vence por uma margem modesta sobre Random
Forest (diferença de R² ≈ 0,015 — dentro da variabilidade esperada de um k-fold de 5
dobras; a Seção 4.5 reporta um teste pareado formal entre CNN 2D, Random Forest e CNN 3D,
cada um na sua própria melhor variante, que não rejeita a hipótese de diferença nula
entre as três), o que sugere que a estrutura **horizontal** do dossel capturada pelo
raster (clareiras, agrupamento de copas — informação que o ABA e o GBR de alturas
descartam por trabalhar só com a distribuição vertical agregada) carrega sinal real, mas
marginal frente à estrutura vertical já capturada pelas abordagens mais simples.

O resultado mais informativo da tabela, porém, é o **fracasso relativo da PointNet**:
mesmo na sua melhor configuração, R² ≈ 0,21 — pior que *todos* os outros cinco modelos,
incluindo o GBR mais simples da comparação. A PointNet recebe a representação mais rica
em princípio (a nuvem de pontos crua, sem nenhuma agregação), mas é também a que mais
depende de volume de dados para aprender uma função de agregação útil via max-pooling —
e 325 parcelas de treino são, evidentemente, poucas para isso.

**Figura 2 — Predito × observado, melhor modelo (CNN 2D, só outliers, isolado).** A
dispersão em torno da diagonal 1:1 mostra o padrão típico de um modelo
com R² moderado: tendência central capturada, mas variância residual substancial,
sobretudo nas parcelas de AGB mais alta — o regime onde erros absolutos (Mg/ha) pesam
mais para qualquer aplicação de contabilidade de carbono.
