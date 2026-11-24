// SPDX-License-Identifier: AGPL-3.0-or-later
// Generat per android/giny/recursos.py a partir de web/estil.css: no es toca a mà.
package io.github.meteo_montflorit;

import java.util.HashMap;
import java.util.Map;

/** Els colors de la targeta d'«Ara» per a cada cel: text, text suau, màxima, mínima i si porten vora blanca. */
final class GinyEstil {
    static final Map<String, int[]> C = new HashMap<>();

    static {
        C.put("sere", new int[] {0xFF0D2340, 0xFF17324F, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("poc", new int[] {0xFF0D2340, 0xFF1F3A57, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("nuvol", new int[] {0xFF14202D, 0xFF2A3846, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("cobert", new int[] {0xFF0B121A, 0xFF111A24, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("boira", new int[] {0xFF1B2530, 0xFF33404D, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("pluja", new int[] {0xFFFFFFFF, 0xFFCFDBE7, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("tempesta", new int[] {0xFFFFFFFF, 0xFFD6CDEA, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("nit", new int[] {0xFFFFFFFF, 0xFFC9D8EE, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("nitnuvol", new int[] {0xFFFFFFFF, 0xFFC9D8EE, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("nitcobert", new int[] {0xFFFFFFFF, 0xFFC9D8EE, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("albasere", new int[] {0xFF1D1A33, 0xFF2E2847, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("albapoc", new int[] {0xFF1D1A33, 0xFF2E2847, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("albanuvol", new int[] {0xFF14202D, 0xFF2A3846, 0xFFB91C1C, 0xFF1D4ED8, 1});
        C.put("albacobert", new int[] {0xFFFFFFFF, 0xFFE3E8EE, 0xFFFCA5A5, 0xFF93C5FD, 0});
        C.put("albapluja", new int[] {0xFFFFFFFF, 0xFFCFDBE7, 0xFFFCA5A5, 0xFF93C5FD, 0});
    }

    private GinyEstil() {}
}
