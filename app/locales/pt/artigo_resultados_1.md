### 3.1 Efeito do controle de qualidade dos dados

Antes de comparar arquiteturas entre si, é preciso isolar um efeito que domina os
resultados: o pré-processamento. Empilhar tratamentos uns sobre os outros (como em
versões anteriores deste texto) não permite separar o que cada etapa individualmente
contribui — um ganho visto na combinação "solo + filtro + outliers" pode vir inteiro de
um único desses três, com os outros dois sendo irrelevantes ou até prejudiciais. Para
resolver isso, cada tratamento foi testado **isoladamente**, sempre contra a mesma
nuvem crua (`raw`), sem empilhar com os demais: projeção do solo sozinha, filtro ≤1,3 m
sozinho (sobre o deslocamento mínimo de Z, sem o relevo local), remoção de outliers
geométricos sozinha, e correção de gap temporal sozinha no alvo. Uma sexta coluna,
"tudo combinado", aplica os quatro tratamentos juntos — o pipeline completo. A Tabela 1
reporta as seis colunas para os sete modelos.

**Remoção de outliers geométricos é, disparado, o tratamento que mais importa** — e o
único que, sozinho, já entrega quase todo o ganho visto na combinação completa. Nos três
modelos com as duas variantes disponíveis para comparação direta (ABA, Random Forest e
CNN 2D), o outlier isolado iguala ou **supera** a combinação "tudo junto": CNN 2D vai de
R²≈0,25 (nuvem crua) para **0,55** só removendo outliers — mais alto que os 0,48 da
combinação completa (solo+filtro+outliers+gap). Random Forest (0,53 isolado vs. 0,51
combinado) e ABA (0,51 vs. 0,49) têm o mesmo padrão. Isso indica que solo, filtro e gap,
no pipeline combinado, não estavam contribuindo — ou estavam discretamente atrapalhando
— e o ganho inteiro vinha da geometria das parcelas. O GBR de 32 quantis confirma a
mesma magnitude isolada (R²=0,51 só com outliers, Tabela 1), ainda que sem uma variante
"tudo combinado" treinada para comparação direta.

**Projeção do solo e filtro ≤1,3 m, isolados, têm efeito pequeno e inconsistente entre
arquiteturas.** Só a projeção do solo (sem filtro) move o R² em poucos centésimos na
maioria dos modelos (ex.: ABA 0,320→0,328, Random Forest 0,283→0,286) — exceção é a CNN
3D (voxel), que sai de R² negativo (−0,13) para positivo (0,09), sugerindo que a
estrutura vertical bruta (Z absoluto, sem corrigir relevo) é especialmente ruim pra
arquiteturas que processam o volume 3D diretamente. O filtro ≤1,3 m isolado (sobre o
mesmo deslocamento mínimo de Z do baseline cru, sem acionar a projeção de relevo
completa) tem efeito ainda menor: piora levemente ABA, Random Forest, o modelo de
alturas ordenadas e a PointNet (R² cai alguns centésimos em cada caso — PointNet
0,125→0,118) e ajuda discretamente só a CNN 2D e a CNN 3D, que parecem se beneficiar de
qualquer redução no ruído vertical bruto, mesmo pequena.

**Correção de gap temporal isolada é, na maioria dos modelos, mais fraca que não fazer
nada.** Em cinco dos seis modelos com baseline cru comparável, o gap isolado fica abaixo
da nuvem crua sem nenhum tratamento — exceção é a CNN 3D, onde o gap isolado (R²=−0,05)
é menos ruim que a própria nuvem crua (−0,13), embora ainda negativo. Isso contrasta com
o papel do gap na combinação completa, onde ele aparece "ajudando" — mas como visto
acima, o ganho ali vem majoritariamente da remoção de outliers que o acompanha, não do
gap em si. A correção de gap é mantida no pipeline por ser metodologicamente correta
(alinhar DBH/altura do inventário à data do voo LiDAR, evitando viés sistemático de
subestimar biomassa quando o LiDAR é mais recente que o censo), não porque eleve o R².

Em suma: **a qualidade da curadoria geométrica das parcelas (outliers) domina a escolha
de arquitetura em magnitude de efeito** — nenhuma combinação de solo, filtro ou gap
chega perto do ganho de simplesmente descartar as parcelas de geometria ruim. Este é o
primeiro resultado do trabalho, e não é sutil.

**Tabela 1 — Comparação entre modelos e variantes de pré-processamento** (RMSE em
Mg/ha; rRMSE em %; R² adimensional; maior R² e menor RMSE/rRMSE são melhores). Colunas
"Só X" são tratamentos isolados contra a mesma nuvem crua; "Tudo combinado" empilha os
quatro juntos:
