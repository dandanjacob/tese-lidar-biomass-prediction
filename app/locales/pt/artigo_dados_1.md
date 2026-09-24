### 2.1 Proveniência dos dados

Duas fontes brutas independentes alimentam o pipeline:

- **LiDAR aerotransportado** — nuvens de pontos `.laz` do programa *NASA Carbon
  Monitoring System (CMS) Brazil*, distribuídas pelo ORNL DAAC. O inventário completo de
  tiles disponibilizado pela missão soma **3.152 tiles**, cobrindo múltiplas campanhas de
  voo (diferentes anos e regiões) sobre a Amazônia brasileira.
- **Inventário florestal de campo** — arquivos `.csv` com medições árvore a árvore
  (diâmetro à altura do peito, altura, espécie) e `.kmz` com a geometria das parcelas,
  cobrindo **28 sites** de inventário distribuídos pela Amazônia.

As duas fontes são coletadas, processadas e cruzadas de forma independente uma da
outra até a etapa de interseção espacial — nenhuma delas é derivada da outra.

### 2.2 Pipeline de pré-processamento

O cruzamento entre as duas fontes segue seis etapas, ilustradas na **Figura 1**:
