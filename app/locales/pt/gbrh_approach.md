Mesma ideia do **GBR — alturas ordenadas**, mas reduzindo a dimensionalidade. Em vez
de 1024 alturas amostradas e ordenadas (1025 atributos para 493 parcelas — muito mais
atributos que amostras, o que leva o modelo a *decorar* o treino), cada parcela vira
apenas **K quantis igualmente espaçados** da distribuição de altura do dossel:

1. **Altura sobre o solo** — solo estimado localmente (mínimo de Z numa grade de 1 m) e subtraído.
2. **Filtro de dossel** — descartam-se retornos abaixo de 1,3 m (chão e sub-bosque).
3. **K quantis** — calcula-se o perfil de altura em K pontos igualmente espaçados (determinístico, sem amostragem aleatória). É o mesmo estilo das métricas ABA.
4. **Densidade** — acrescenta-se `log(nº de pontos)` — total **K + 1 atributos**.

Treinando o mesmo GBR (mesmos hiperparâmetros, mesma validação cruzada) para
`K ∈ {8, 16, 32, 64, 128, 256}`, monta-se uma curva **CV R² × nº de alturas**: se o
desempenho não cai (ou melhora) com menos atributos, confirma-se que as 1024 alturas
originais eram, em boa parte, ruído que só alimentava o overfitting.
