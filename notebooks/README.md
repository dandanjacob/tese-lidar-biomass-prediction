# Notebooks

Análise exploratória e visualizações do pipeline de predição de biomassa.

| Notebook | Descrição |
|---|---|
| `02_lidar_analysis.ipynb` | Análise dos tiles LiDAR: distribuição por site/UTM, densidade de pontos, visualização de nuvem de pontos |
| `03_inventory_analysis.ipynb` | Análise do inventário florestal: DAP, espécies, mortalidade, estimativa de biomassa (Brown 1997) |
| `04_intersection_example.ipynb` | Exemplo detalhado de um plot: LiDAR clippado + árvores do inventário lado a lado |
| `05_intersection_analysis.ipynb` | Análise das interseções: cobertura por site, melhor match temporal, distribuição de gaps |

## Como executar

```bash
source .venv/bin/activate
jupyter lab
```

Os notebooks devem ser executados a partir da pasta raiz do projeto (o kernel detecta o `ROOT` automaticamente via `Path("..")`).
