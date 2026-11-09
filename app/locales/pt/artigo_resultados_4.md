### 3.5 Posição frente à literatura e ao GEDI

O melhor resultado desta tese (R² = 0,547; rRMSE ≈ 41,7%; CNN 2D, parcela, variante só
outliers isolada) situa-se
**abaixo** dos trabalhos de referência em LiDAR aéreo tropical com metodologia mais
madura — Asner & Mascaro (2014), R² = 0,90 sobre 804 parcelas de 1 ha em quatro países
tropicais e Havaí; Longo et al. (2016), R² = 0,70 sobre 359 parcelas amazônicas — e
também **abaixo** de Bispo et al. (2020): R² = 0,93 / rRMSE = 13% para o modelo
só-LiDAR (R² = 0,89 / rRMSE = 43% no modelo multissensor). *Nota: Bispo et al. (2020)
estuda o Cerrado brasileiro (bacia do Rio Vermelho), não a Amazônia — versões
anteriores deste texto atribuíam o estudo à Amazônia e citavam R² = 0,58 / rRMSE =
36,0%, que não correspondem à fonte; ambos os erros foram corrigidos após verificação
adversarial direta contra o artigo original.* Frente ao produto orbital **GEDI L4A**
(*footprint* ~25 m), a validação independente em savanas do sul da África (Li et al.,
2024 — não Naidoo et al., que é coautor, não autor líder; ver correção em
<code>artigo_referencias.md</code>) reporta R² ≈ 0,42 — nesse critério específico, o
resultado desta tese é **competitivo**, apesar de operar em escala de parcela (mais
exigente) em vez de *footprint* de 25 m. d'Oliveira et al. (2012), com suporte espacial
menor (50 parcelas de 0,25 ha, Acre) e instrumentação mais antiga, reporta R² = 0,63–0,72
— o mais baixo do conjunto de referências — e foi mantido na lista de referências sem
entrar nesta comparação direta por essas duas diferenças de desenho.

Essas comparações exigem duas ressalvas, detalhadas na Seção 4.7: (i) as escalas
espaciais não são diretamente comparáveis (parcela vs. *footprint* vs. grade de 1 km);
(ii), mais importante, os números desta tese vêm de k-fold aleatório, enquanto boa
parte da literatura citada usa validação cruzada por sítio ou validação independente —
um padrão de generalização mais exigente que o empregado aqui (Seção 4.2). A
verificação adversarial dos números da literatura — conferência linha a linha contra a
fonte primária, antes pendente — foi concluída; ver Seção 4.7 para o detalhe por fonte.

Quanto ao LiDAR orbital da NASA — GEDI e ICESat-2 —, não foi encontrada, mesmo após
busca e verificação direta contra a fonte primária, nenhuma validação de R²/RMSE
calculada isoladamente para a Amazônia brasileira (nem do GEDI, nem do ICESat-2) com
desenho comparável a parcela ou k-fold aleatório. O benchmark publicado mais próximo é
Duncanson et al. (2022): o modelo oficial de biomassa do GEDI, no estrato *Evergreen
Broadleaf Trees* — América do Sul (classe dominante na Amazônia, mas estrato
continental, não um recorte amazônico), reporta R² = 0,66 e %RMSE = 42,2% por validação
cruzada geográfica — portanto nem k-fold aleatório, nem especificamente amazônico, mas é
o melhor proxy disponível para "GEDI num bioma análogo à Amazônia", na mesma faixa de
rRMSE desta tese (41,7%). Já o ICESat-2 (ATL08), quando validado contra LiDAR
aerotransportado em floresta tropical (Mesoamérica, Gabão e Guiana Francesa — nunca a
bacia amazônica isolada), degrada fortemente frente ao desempenho em floresta boreal:
erro de altura de dossel de 5–7 m em floresta tropical contra 3,19 m em condições
boreais ideais (Liu, Gong & Shi, 2026) — reforçando que mesmo o LiDAR orbital mais
recente da NASA perde precisão em dossel tropical denso, um argumento a favor da
abordagem aerotransportada adotada nesta tese. O trabalho de deep learning mais próximo
publicado em 2023–2025 usando a mesma linhagem de dados (LiDAR aerotransportado do
programa NASA CMS Brasil/EBA) na Amazônia é Wagner et al. (2025, pré-print): uma U-Net
treinada com esse mesmo tipo de levantamento para mapear altura de dossel (não AGB) a
partir de imagens Planet NICFI, com MAE = 3,68 m em validação espacialmente
estratificada — uma comparação metodológica (arquitetura de rede) mais honesta que uma
comparação direta de métrica de erro, já que a variável-alvo difere da desta tese.
