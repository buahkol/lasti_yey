"""Screen based UI scale, similar to Tailwind breakpoints.

The design is drawn for a 1920 x 1080 screen. On smaller laptop screens the
whole interface (fonts, spacing, icons and charts) is scaled down with Qt's
QT_SCALE_FACTOR so nothing gets cut off and proportions stay the same.

Tiers use the available desktop area in logical pixels (after Windows
display scaling):

    width >= 1760 and height >= 960   1.00   (1920 x 1080 at 100%)
    width >= 1500 and height >= 840   0.90   (1600 x 900, 1920 x 1080 at 125%)
    width >= 1300 and height >= 700   0.85   (1366 x 768, 1440 x 900)
    smaller                            0.80   (1280 x 720, 1920 x 1080 at 150%)

Set the SIMONPRO_SCALE environment variable (for example 0.9) to override.
"""

import os

TIERS = (
    (1760, 960, 1.0),
    (1500, 840, 0.9),
    (1300, 700, 0.85),
)
MIN_SCALE = 0.8


def choose_scale(width: int, height: int) -> float:
    override = os.environ.get("SIMONPRO_SCALE")
    if override:
        try:
            return max(0.5, min(2.0, float(override)))
        except ValueError:
            pass
    for min_w, min_h, scale in TIERS:
        if width >= min_w and height >= min_h:
            return scale
    return MIN_SCALE
