| Fórmula | Equações usadas | Densidade de madeira (ρ) |
|---|---|---|
| **M1 — Chave uniforme** | Chave et al. 2014 para todas as árvores | ρ = 0,6 g/cm³ (média global) |
| **M2 — Chave por tipo** | Chave 2014 (vivas) · Chambers 2000 (mortas) · Goodman 2013 (palmeiras) | ρ = 0,6 g/cm³ (média global) |
| **M3 — Chave por tipo + ρ espécie** | Mesmas equações de M2 | ρ específica por espécie (GWDD Zanne/Chave; fallback: gênero → site → 0,6) |

**Equações de carbono individual (f_C = 0,5):**
- Árvores vivas: `IAGC = 0,0673 × 0,5 × (ρ × DBH² × H)^0.976` — Chave et al. (2014) Eq. 7
- Árvores mortas: `IAGC = 0,1007 × 0,5 × 0,40 × DBH² × H^0.818` — Chambers et al. (2000)
- Palmeiras vivas: `IAGC = 0,03781 × 0,5 × DBH^2.7483` — Goodman et al. (2013)

AGB = 2 × AGC (f_C = 0,5). Unidade final: **Mg/ha**.
