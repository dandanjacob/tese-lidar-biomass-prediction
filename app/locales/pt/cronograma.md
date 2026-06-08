## ✅ O que já foi feito

1. **Coleta e entendimento dos dados** — nuvens de pontos LiDAR aerotransportado
   (NASA / ORNL DAAC) e inventários florestais de campo da Amazônia; exploração de
   estrutura, qualidade e cobertura.
2. **Interseções LiDAR × inventário** — cruzamento espacial das parcelas com cobertura
   LiDAR, incluindo a defasagem de anos entre o voo e a medição de campo.
3. **Biomassa de referência (o alvo)** — AGB por parcela a partir do inventário (DBH,
   altura, densidade da madeira), em três fórmulas (M1 / M2 / M3).
4. **Recuperação do dataset** — deduplicação e correções elevaram as parcelas
   utilizáveis de **383 → 493** (e **325** após remover outliers de área/forma).
5. **Seis modelos, duas variantes** — GBR, Random Forest, ABA (métricas), PointNet e
   CNNs 2D/3D, treinados **com e sem outliers** e avaliados por validação cruzada k-fold.
6. **Diagnóstico por modelo** — predito × observado, resíduos, *learning curve* e
   evolução do treino (RMSE + R²); na nuvem de pontos, sobreposição das árvores do
   inventário (posição, altura, espécie) e a métrica de gap temporal LiDAR × inventário.
7. **Redução de dimensionalidade (experimento)** — GBR com **K quantis de altura**
   (de 8 a 256): o R² satura já com **~16 quantis** (~0,44 sem outliers), confirmando
   que as 1024 alturas originais eram, em boa parte, ruído que alimentava *overfitting*.

## 🎯 O plano (próximos passos)

Leitura até aqui: **poucas features bem escolhidas (ABA / quantis) generalizam melhor
que a nuvem crua de alta dimensão**, e remover outliers ajuda bastante.

1. **Padronizar o *footprint* das parcelas** — recortar todas com área e formato
   parecidos, gerando um dataset maior e mais homogêneo (cada parcela grande vira
   várias unidades menores).
2. **Aprofundar a abordagem por métricas / ABA** e a regularização, já que supera a
   nuvem crua.
3. **Corrigir os modelos PyTorch** — o voxel ainda fica abaixo de prever a média
   (R² < 0): *early stopping* e menos capacidade.
4. **Re-rodar e comparar** tudo sobre o dataset padronizado.

---

> _Página viva: vai sendo atualizada conforme o projeto avança._
