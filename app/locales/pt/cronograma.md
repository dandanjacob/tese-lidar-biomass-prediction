## ✅ O que já foi feito

1. **Coleta dos dados** — nuvens de pontos LiDAR aerotransportado (NASA / ORNL DAAC) e
   inventários florestais de campo da Amazônia.
2. **Entendimento dos dados** — exploração da estrutura, qualidade e cobertura de cada
   fonte, e organização do pipeline de processamento.
3. **Interseções LiDAR × inventário** — cruzamento espacial para descobrir quais parcelas
   de campo têm cobertura LiDAR (e com qual defasagem de anos entre o voo e a medição).
4. **Biomassa dos inventários de campo** — cálculo da AGB por parcela a partir do
   inventário (DBH, altura, densidade da madeira), em três variantes de fórmula
   (M1 / M2 / M3). É o **alvo** que os modelos tentam prever.
5. **Primeiros modelos "às cegas"** — jogando a nuvem de pontos (crua ou resumida) direto
   no modelo, **sem padronizar** as parcelas: GBR, Random Forest, PointNet e CNNs 2D/3D.

## 🎯 O plano (próximos passos)

Os primeiros modelos **renderam pouco** — sinal de que o dado de entrada está
heterogêneo demais (parcelas com áreas, formatos e densidades muito diferentes).

1. **Padronizar as nuvens de pontos** — recortar todas com **área e formato mais
   parecidos** (um *footprint* regular). A vantagem é dupla:
   - gera um **dataset bem maior**, já que cada parcela grande pode virar várias
     unidades menores;
   - cada unidade fica **mais precisa**, por representar uma área menor e mais homogênea.
2. **Re-rodar os modelos** com essas parcelas **melhor categorizadas** e comparar com a
   rodada "às cegas".
3. **Estudar mais modelos** sobre esse dataset padronizado.
4. **Plano B — métricas no lugar da nuvem crua:** se os modelos que recebem a **nuvem de
   pontos como entrada** continuarem ruins, migrar para modelos alimentados por
   **métricas extraídas das nuvens** (altura máxima, percentis, densidade, etc.) — a
   abordagem por área (ABA).

---

> _Página viva: vai sendo atualizada conforme o projeto avança._
