// SPDX-License-Identifier: AGPL-3.0-or-later
package io.github.meteo_montflorit;

import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.os.Build;
import android.os.Bundle;

/**
 * Posa el giny a la pantalla d'inici d'un toc (ADR 0131, 28-11-2026). La web,
 * dins de l'app, hi porta amb «montflorit://posa-giny» quan es toca
 * «Afegeix-lo»; Android ensenya el seu quadre amb el giny i qui el vol el posa.
 * No té pantalla: demana el giny i plega.
 */
public class PosaGiny extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try {
                AppWidgetManager gestor = AppWidgetManager.getInstance(this);
                if (gestor.isRequestPinAppWidgetSupported()) {
                    gestor.requestPinAppWidget(new ComponentName(this, GinyProvider.class), null, null);
                }
            } catch (RuntimeException e) {
                // Si el llançador no ho deixa, no passa res: la web ja diu com fer-ho a mà.
            }
        }
        finish();
    }
}
