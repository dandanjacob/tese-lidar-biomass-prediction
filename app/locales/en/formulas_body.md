| Formula | Equations used | Wood density (ρ) |
|---|---|---|
| **M1 — Uniform Chave** | Chave et al. 2014 for all trees | ρ = 0.6 g/cm³ (global mean) |
| **M2 — Chave by type** | Chave 2014 (live) · Chambers 2000 (dead) · Goodman 2013 (palms) | ρ = 0.6 g/cm³ (global mean) |
| **M3 — Chave by type + species ρ** | Same equations as M2 | species-specific ρ (GWDD Zanne/Chave; fallback: genus → site → 0.6) |

**Individual carbon equations (f_C = 0.5):**
- Live trees: `IAGC = 0.0673 × 0.5 × (ρ × DBH² × H)^0.976` — Chave et al. (2014) Eq. 7
- Dead trees: `IAGC = 0.1007 × 0.5 × 0.40 × DBH² × H^0.818` — Chambers et al. (2000)
- Live palms: `IAGC = 0.03781 × 0.5 × DBH^2.7483` — Goodman et al. (2013)

AGB = 2 × AGC (f_C = 0.5). Final unit: **Mg/ha**.
