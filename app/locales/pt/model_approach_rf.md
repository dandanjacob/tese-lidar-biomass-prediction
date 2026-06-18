> **Input:** as mesmas 37 métricas estruturais do ABA — percentis de altura, cobertura de dossel, rugosidade do CHM e densidade vertical.

Usa **exatamente as mesmas 37 métricas estruturais** da abordagem ABA (distribuição
de altura, densidade vertical e métricas convolucionais do CHM), mas troca o
**Gradient Boosting** por um **Random Forest**.

A diferença é o jeito de combinar árvores:

- **Random Forest** (aqui) — *bagging*: centenas de árvores fundas treinadas em
  amostras e subconjuntos de variáveis diferentes, com a previsão sendo a **média**.
  Reduz variância, é robusto e quase não precisa de ajuste fino.
- **Gradient Boosting** (ABA) — *boosting*: árvores rasas em sequência, cada uma
  corrigindo o erro da anterior.

Treina-se sobre o **mesmo dataset** (cada parcela peso 1, sem distinção de site,
k-fold aleatório) e com o **alvo em log1p**, então os dois são diretamente
comparáveis — a diferença de desempenho vem só do algoritmo, não das features.

> Serve para responder: sobre estas métricas, *bagging* ou *boosting* generaliza
> melhor? A tabela de importância (mais abaixo) mostra quais métricas o Random Forest
> mais usa.
