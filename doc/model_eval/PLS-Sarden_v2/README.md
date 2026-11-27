# Evaluasi model PLS-Sarden v2

Set uji terpisah: 9 OK, 16 NG (manifest `/home/pn/.local/share/simonpro/data/manifests/PLS-Sarden.csv`).

| Ukuran | Nilai | Target | Status |
|---|---|---|---|
| Recall NG (K2) | 100.0% | ≥ 90% | Lulus |
| Specificity (K3) | 66.7% | ≥ 85% | Belum |
| Latensi inferensi p95 (AI-04) | 275.9 ms | ≤ 500 ms | Lulus |
| AUROC | 1.0000 | — | — |

Ambang batas 0.2110 (ternormalisasi), perangkat: cpu.
Confusion: TP=16 FN=0 TN=6 FP=3.

![confusion](confusion.png) ![scores](scores.png)

## Salah klasifikasi (3)

- `c006_20261127T211006535881.jpg` aktual OK , skor 0.520
- `c006_20261127T211012010597.jpg` aktual OK , skor 0.252
- `c006_20261127T211028727407.jpg` aktual OK , skor 0.229
