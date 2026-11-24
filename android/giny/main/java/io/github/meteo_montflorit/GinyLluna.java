// SPDX-License-Identifier: AGPL-3.0-or-later
// La Lluna del giny (ADR 0131), com dibuixLluna de web/comu.js: la part
// il·luminada de veritat (a la dreta quan creix) sobre el disc fosc, amb la vora.
package io.github.meteo_montflorit;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;

final class GinyLluna {
    // Els colors de web/estil.css (svg.lluna).
    static final int FOSCA = 0xFF475569;
    static final int CLARA = 0xFFFEF3C7;
    static final int VORA = 0xFF94A3B8;

    /** El dibuix de la Lluna amb l'angle de fase (0 nova, 90 quart creixent, 180 plena, 270 quart minvant). */
    static Bitmap dibuix(double angle, int px) {
        Bitmap b = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888);
        double r = px / 2.0 - 1;
        double c = px / 2.0;
        double k = Math.cos(Math.toRadians(angle));
        boolean creix = angle < 180;
        for (int y = 0; y < px; y++) {
            for (int x = 0; x < px; x++) {
                double dx = x + .5 - c, dy = y + .5 - c;
                if (dx * dx + dy * dy > r * r) continue;
                // La vora del terminador: mitja el·lipse d'amplada |cos angle|.
                double w = Math.sqrt(r * r - dy * dy);
                boolean clara = creix ? dx > k * w : -dx > k * w;
                b.setPixel(x, y, clara ? CLARA : FOSCA);
            }
        }
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(Math.max(1f, px / 24f));
        p.setColor(VORA);
        new Canvas(b).drawCircle((float) c, (float) c, (float) r, p);
        return b;
    }

    private GinyLluna() {}
}
