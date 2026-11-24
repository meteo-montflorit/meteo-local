// SPDX-License-Identifier: AGPL-3.0-or-later
// El giny de la pantalla d'inici (ADR 0131): el que diu la targeta d'«Ara» de
// la web, amb el seu fons i els seus colors. Els textos ja venen fets del NAS
// (giny.json, que surt de giny.js amb el mateix codi de la web), en català i
// en castellà; aquí només es pinten i es torna a escriure el compte enrere de
// la pluja, que depèn de l'hora en què es mira.
package io.github.meteo_montflorit;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.StaticLayout;
import android.text.TextPaint;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.util.SizeF;
import android.util.TypedValue;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;

public class GinyProvider extends AppWidgetProvider {
    // On es publica: IONOS, i la còpia de la web a GitHub si IONOS no respon.
    static final String[] FONTS = {
        "https://bilateria.org/app/meteo-local/giny.json",
        "https://meteo-montflorit.github.io/giny.json",
    };
    static final String PREFS = "giny";
    static final String ACCIO_REFRESCA = "io.github.meteo_montflorit.GINY_REFRESCA";
    // Si no es pot descarregar (sense connexió), es torna a provar al cap de REINTENT_MIN minuts,
    // sense esperar la mitja hora d'Android.
    static final long REINTENT_MIN = 10;
    // Amb dades de VELLES_H hores o més, el giny diu de quan són i la
    // temperatura es posa en gris (es veu que no és la d'ara).
    static final long VELLES_H = 2;
    // A partir d'aquesta alçada (dp), el giny d'una fila porta també la gota de la pluja.
    static final float FILA_AMB_GOTA = 70;
    // A partir d'aquesta alçada (dp), el giny petit porta també la frase.
    static final float PETIT_AMB_FRASE = 260;
    // L'amplada (dp) del dibuix del cel al 4×2: el núvol, que és ample, s'hi fa gran; la mínima, si
    // al costat hi ha la pluja i la Lluna.
    static final float CEL_MIN = 56;
    static final float CEL_MAX = 100;
    // El color de la pastilla del compte enrere de la pluja (web/estil.css, .comenca-pluja).
    static final int AIGUA_FONS = 0xFFDBEAFE;
    static final int AIGUA_TEXT = 0xFF1E40AF;

    // Les formes i la mida (dp) a partir de la qual es fan servir. Mesures d'un Pixel
    // (24-11-2026): el 4×1 fa uns 290×90 dp; el 2×2, 140×185; el 4×2, 290×185, i el 4×3, 290×280.
    enum Forma {
        FILA(R.layout.giny_fila, 110, 40),
        PETIT(R.layout.giny_petit, 110, 125),
        MITJA(R.layout.giny_mitja, 220, 125),
        ALT(R.layout.giny_alt, 220, 170),
        GRAN(R.layout.giny_gran, 220, 250);

        final int layout;
        final float ample;
        final float alt;

        Forma(int layout, float ample, float alt) {
            this.layout = layout;
            this.ample = ample;
            this.alt = alt;
        }

        boolean ambFrase() {
            return this == MITJA || this == ALT || this == GRAN;
        }

        /** La que hi cap en una mida (per a Android 11 o anterior, que no tria sol). */
        static Forma per(float ample, float alt) {
            if (alt < PETIT.alt) return FILA;
            if (ample < MITJA.ample) return PETIT;
            return alt >= GRAN.alt ? GRAN : alt >= ALT.alt ? ALT : MITJA;
        }
    }

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        // Primer, el que ja es té (el compte enrere al dia); després, les dades noves.
        pintaTots(context);
        descarrega(context, goAsync());
    }

    @Override
    public void onAppWidgetOptionsChanged(Context context, AppWidgetManager manager, int id, Bundle opcions) {
        manager.updateAppWidget(id, vistes(context, manager, id));
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        // En canviar l'idioma del mòbil, el giny canvia d'idioma.
        if (Intent.ACTION_LOCALE_CHANGED.equals(intent.getAction())) pintaTots(context);
        // Tocar-lo sense dades, o el reintent després d'una descàrrega fallida.
        if (ACCIO_REFRESCA.equals(intent.getAction())) descarrega(context, goAsync());
    }

    // --- Les dades.

    static void descarrega(Context context, PendingResult resultat) {
        new Thread(() -> {
            boolean fet = false;
            try {
                for (String font : FONTS) {
                    String text = baixa(font);
                    if (text == null) continue;
                    try {
                        new JSONObject(text);
                    } catch (Exception e) {
                        continue;
                    }
                    context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                        .putString("dades", text).apply();
                    fet = true;
                    break;
                }
                pintaTots(context);
                if (!fet) reintenta(context);
            } finally {
                if (resultat != null) resultat.finish();
            }
        }).start();
    }

    static PendingIntent refresca(Context context) {
        Intent i = new Intent(context, GinyProvider.class).setAction(ACCIO_REFRESCA);
        return PendingIntent.getBroadcast(context, 1, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** Un altre intent d'aquí a REINTENT_MIN minuts (una alarma inexacta, que no demana cap permís). */
    static void reintenta(Context context) {
        AlarmManager alarmes = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarmes == null) return;
        alarmes.set(AlarmManager.ELAPSED_REALTIME, SystemClock.elapsedRealtime() + REINTENT_MIN * 60_000, refresca(context));
    }

    static String baixa(String adreca) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(adreca + "?t=" + System.currentTimeMillis()).openConnection();
            c.setConnectTimeout(8000);
            c.setReadTimeout(8000);
            c.setRequestProperty("Cache-Control", "no-cache");
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] b = new byte[8192];
                int n;
                while ((n = in.read(b)) > 0) {
                    out.write(b, 0, n);
                    if (out.size() > 200_000) return null;
                }
                return out.toString(StandardCharsets.UTF_8.name());
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    static JSONObject dades(Context context) {
        String text = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("dades", null);
        if (text == null) return null;
        try {
            return new JSONObject(text);
        } catch (Exception e) {
            return null;
        }
    }

    // --- El dibuix.

    static void pintaTots(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        for (int id : manager.getAppWidgetIds(new ComponentName(context, GinyProvider.class))) {
            manager.updateAppWidget(id, vistes(context, manager, id));
        }
    }

    static RemoteViews vistes(Context context, AppWidgetManager manager, int id) {
        JSONObject d = dades(context);
        Bundle o = manager.getAppWidgetOptions(id);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // Android 12 o posterior: una forma per a cada mida que pot tenir el giny (en vertical i
            // en horitzontal), que tria el sistema. Amb la mida de debò, el giny pot mesurar si una
            // línia hi cap.
            ArrayList<SizeF> mides = o.getParcelableArrayList(AppWidgetManager.OPTION_APPWIDGET_SIZES);
            Map<SizeF, RemoteViews> formes = new HashMap<>();
            if (mides != null) {
                for (SizeF m : mides) formes.put(m, vista(context, Forma.per(m.getWidth(), m.getHeight()), d, m.getWidth(), m.getHeight()));
            }
            // I les de cada forma, per si el giny canvia de mida abans que arribin les noves.
            for (Forma f : Forma.values()) {
                SizeF m = new SizeF(f.ample, f.alt);
                if (!formes.containsKey(m)) formes.put(m, vista(context, f, d, f.ample, f.alt));
            }
            return new RemoteViews(formes);
        }
        // En vertical, l'amplada mínima i l'alçada màxima.
        float ample = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        float alt = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 110);
        return vista(context, Forma.per(ample, alt), d, ample, alt);
    }

    static RemoteViews vista(Context context, Forma forma, JSONObject d, float ampleDp, float altDp) {
        String idioma = context.getString(R.string.giny_idioma);
        JSONObject t = d == null ? null : d.optJSONObject(idioma);
        if (t == null || t.optJSONObject("cel") == null) {
            RemoteViews v = new RemoteViews(context.getPackageName(), R.layout.giny_carregant);
            if (d != null) v.setTextViewText(R.id.giny_avis, context.getString(R.string.giny_sense_dades));
            // Sense dades, tocar-lo les torna a demanar; si les dades no tenen la targeta, obre l'app.
            v.setOnClickPendingIntent(R.id.giny_arrel, d == null ? refresca(context) : obreApp(context));
            return v;
        }
        RemoteViews v = new RemoteViews(context.getPackageName(), forma.layout);
        JSONObject cel = t.optJSONObject("cel");
        String fons = cel.optString("fons", "nuvol");
        int[] c = GinyEstil.C.containsKey(fons) ? GinyEstil.C.get(fons) : GinyEstil.C.get("nuvol");
        int text = c[0], suau = c[1], max = c[2], min = c[3];
        boolean vora = c[4] == 1;

        v.setImageViewResource(R.id.giny_fons, recurs(context, "giny_fons_" + fons));
        v.setImageViewResource(R.id.giny_cel, recurs(context, "giny_cel_" + cel.optString("dibuix", "cloudy").replace('-', '_')));

        // El títol: el lloc i, si les dades són velles, de quan són.
        long hores = horesDesDe(d.optString("generat"));
        boolean velles = hores >= VELLES_H;
        String titol = forma.ambFrase() ? t.optString("titol") : "Montflorit";
        if (velles) titol += " · " + context.getString(forma.ambFrase() ? R.string.giny_vell : R.string.giny_vell_curt, hores);
        v.setTextViewText(R.id.giny_titol, titol);
        v.setTextColor(R.id.giny_titol, suau);

        v.setTextViewText(R.id.giny_temp, t.optString("temperatura", "–"));
        v.setTextColor(R.id.giny_temp, velles ? (suau & 0x00FFFFFF) | 0xA0000000 : text);

        // La màxima i la mínima, en vermell i en blau; sobre els cels clars, amb vora blanca (com a la web).
        JSONObject dia = t.optJSONObject("dia");
        SpannableStringBuilder extrems = new SpannableStringBuilder();
        if (dia != null && !dia.optString("max").isEmpty()) {
            afegeix(extrems, dia.optString("max"), max);
            afegeix(extrems, ", ", suau);
            afegeix(extrems, dia.optString("min"), min);
        }
        v.setTextViewText(R.id.giny_extrems, extrems);
        v.setTextViewText(R.id.giny_extrems_vora, extrems);
        v.setViewVisibility(R.id.giny_extrems, vora ? View.GONE : View.VISIBLE);
        v.setViewVisibility(R.id.giny_extrems_vora, vora ? View.VISIBLE : View.GONE);

        if (forma.ambFrase()) {
            v.setTextViewText(R.id.giny_frase, t.optString("frase"));
            v.setTextColor(R.id.giny_frase, text);
            String quan = dia == null ? "" : dia.optString("quan");
            v.setTextViewText(R.id.giny_quan, quan);
            v.setTextColor(R.id.giny_quan, suau);
            String compara = dia == null || dia.isNull("compara") ? "" : dia.optString("compara");
            // Al gran, la comparació va a sota; al mitjà, darrere la màxima i la mínima, com a la web
            // («Avui: màx. 15°, mín. 5° · semblant a ahir»), si hi cap; si no, a la línia de sota
            // (a l'alt) o no hi va (al baix, que no té lloc).
            String mateixa = "", sota = "";
            if (!compara.isEmpty()) {
                if (forma == Forma.GRAN) mateixa = compara;
                else if (hiCap(context, quan + " " + extrems + " · " + compara, ampleDp - 30)) mateixa = " · " + compara;
                else if (forma == Forma.ALT) sota = compara;
            }
            v.setTextViewText(R.id.giny_compara, mateixa);
            v.setTextColor(R.id.giny_compara, suau);
            v.setViewVisibility(R.id.giny_compara, mateixa.isEmpty() ? View.GONE : View.VISIBLE);
            if (forma == Forma.ALT || forma == Forma.MITJA) sota = disposa(context, v, forma, t, sota, ampleDp, altDp, suau, min);
            v.setTextViewText(R.id.giny_compara2, sota);
            v.setTextColor(R.id.giny_compara2, suau);
            v.setViewVisibility(R.id.giny_compara2, sota.isEmpty() ? View.GONE : View.VISIBLE);
        }

        // La gota: la pluja en curt («19 h · 22 %», «Plou»), on no hi ha la línia sencera (al gran sí).
        // Al 4×2 (l'alt i el mitjà), la col·loca disposa, amb la Lluna.
        if (forma == Forma.FILA || forma == Forma.PETIT) {
            String gota = t.isNull("gota") ? "" : t.optString("gota");
            boolean ambGota = !gota.isEmpty() && (forma != Forma.FILA || altDp >= FILA_AMB_GOTA);
            v.setViewVisibility(R.id.giny_pluja, ambGota ? View.VISIBLE : View.GONE);
            if (ambGota) {
                v.setTextViewText(R.id.giny_pluja_text, gota);
                v.setTextColor(R.id.giny_pluja_text, suau);
                // El blau de la mínima de cada cel, que es llegeix sobre el fons.
                v.setInt(R.id.giny_gota, "setColorFilter", min);
            }
        }

        // El petit alt (2×3 o més) té lloc per a la frase.
        if (forma == Forma.PETIT && altDp >= PETIT_AMB_FRASE) {
            v.setTextViewText(R.id.giny_frase, t.optString("frase"));
            v.setTextColor(R.id.giny_frase, text);
            v.setViewVisibility(R.id.giny_frase, View.VISIBLE);
        }

        if (forma == Forma.GRAN) {
            v.setTextViewText(R.id.giny_linia, linia(t));
            v.setTextColor(R.id.giny_linia, suau);
            JSONArray pastilles = t.optJSONArray("pastilles");
            String p = pastilles == null ? "" : uneix(pastilles);
            v.setTextViewText(R.id.giny_pastilles, p);
            v.setTextColor(R.id.giny_pastilles, suau);
            v.setViewVisibility(R.id.giny_pastilles, p.isEmpty() ? View.GONE : View.VISIBLE);
            String sol = t.isNull("sol") ? "" : t.optString("sol");
            v.setTextViewText(R.id.giny_sol, sol);
            v.setTextColor(R.id.giny_sol, suau);
            v.setViewVisibility(R.id.giny_sol, sol.isEmpty() ? View.GONE : View.VISIBLE);
            JSONObject lluna = t.optJSONObject("lluna");
            if (lluna != null) {
                v.setTextViewText(R.id.giny_lluna_text, lluna.optString("text"));
                v.setTextColor(R.id.giny_lluna_text, suau);
                v.setImageViewBitmap(R.id.giny_lluna_dibuix, GinyLluna.dibuix(lluna.optDouble("angle", 180), 48));
                v.setViewVisibility(R.id.giny_lluna, View.VISIBLE);
            } else {
                v.setViewVisibility(R.id.giny_lluna, View.GONE);
            }
        }

        String descripcio = t.optString("titol") + ". " + t.optString("temperatura") + ".";
        if (forma.ambFrase()) descripcio += " " + t.optString("frase");
        v.setContentDescription(R.id.giny_arrel, descripcio);
        v.setOnClickPendingIntent(R.id.giny_arrel, obreApp(context));
        return v;
    }

    /**
     * El 4×2 (l'alt i, més petit, el mitjà), amb la mida de debò (24-11-2026, Juanjo: «hay mucho espacio vacío en la tarjeta.
     * La nube es diminuta y cabría perfectamente lo de la lluvia y la luna»). La gota i la Lluna van al
     * costat de la temperatura, tocant el dibuix, si hi caben d'ample (els mòbils amples); si no, a
     * una línia a sota. El dibuix fa l'alçada que queda. Per l'alçada, mana la frase sencera (fins a
     * tres línies); després, la línia de sota i, si encara hi ha lloc, la comparació amb ahir que no
     * cap darrere la màxima i la mínima. Torna la comparació que hi va a sota ("" si no hi cap).
     */
    static String disposa(Context context, RemoteViews v, Forma forma, JSONObject t, String compara, float ampleDp,
                          float altDp, int suau, int blau) {
        boolean alt = forma == Forma.ALT;
        float tempSp = alt ? 44 : 34, fraseSp = alt ? 16 : 14;
        float celMin = alt ? CEL_MIN : 48, celMax = alt ? CEL_MAX : 72, celXml = alt ? 88 : 64;
        float contingut = ampleDp - 30;
        String gota = t.isNull("gota") ? "" : t.optString("gota");
        JSONObject lluna = t.optJSONObject("lluna");
        String llunaText = lluna == null ? "" : lluna.optString("text");
        float tempW = ampla(context, t.optString("temperatura", "–"), tempSp, "sans-serif", false);
        // Cada element, amb el dibuix (13 dp i el marge) i un marge de seguretat.
        float gotaW = gota.isEmpty() ? 0 : 23 + ampla(context, gota, 13, "sans-serif-medium", false);
        float llunaW = llunaText.isEmpty() ? 0 : 23 + ampla(context, llunaText, 13, "sans-serif", false);
        // L'espai del costat, amb el dibuix a l'amplada mínima (abans d'Android 12, la fixa de l'XML).
        boolean variable = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S;
        float lliure = contingut - tempW - 16 - (variable ? celMin : celXml);
        boolean gotaCostat = !gota.isEmpty() && gotaW <= lliure;
        boolean llunaCostat = !llunaText.isEmpty() && (gota.isEmpty() || gotaCostat) && llunaW <= lliure;
        boolean gotaSota = !gota.isEmpty() && !gotaCostat;
        boolean llunaSota = !llunaText.isEmpty() && !llunaCostat
            && (gotaSota ? gotaW + 14 + llunaW : llunaW) <= contingut;

        // L'alçada: el títol, la frase, la fila de la temperatura i la màxima i la mínima. La frase,
        // sencera si hi cap i mai en menys de dues línies (com abans); el que no hi cap, fora.
        float linia = alcada(context, 13, "sans-serif", true);
        float liniaFrase = alcada(context, fraseSp, "sans-serif", true) * 1.05f;
        float tempH = alcadaXifres(context, tempSp);
        float fixa = altDp - (alt ? 24 : 20) - alcada(context, 12, "sans-serif-medium", true) - 2 - linia;
        int linies = Math.min(alt ? 3 : 2, liniesFrase(context, t.optString("frase"), fraseSp, contingut));
        while (linies > 2 && fixa - linies * liniaFrase < tempH) linies--;
        // L'alçada de la fila de la temperatura, on van el dibuix i el que hi ha al costat.
        float fila = fixa - linies * liniaFrase;
        // Al costat, la gota i la Lluna una sobre l'altra: si no hi caben d'alt, la Lluna baixa.
        // (Dues línies juntes, sense el marge de dalt i de baix de cada una.)
        if (gotaCostat && llunaCostat && fila < 2 * alcada(context, 13, "sans-serif", false) + 3) {
            llunaCostat = false;
            llunaSota = llunaW <= contingut;
        }
        if ((gotaSota || llunaSota) && fila - linia - 2 < tempH) {
            gotaSota = false;
            llunaSota = false;
        }
        if (gotaSota || llunaSota) fila -= linia + 2;
        if (!compara.isEmpty() && fila - linia < tempH) compara = "";
        v.setInt(R.id.giny_frase, "setMaxLines", linies);

        posaGota(v, gota, gotaCostat, R.id.giny_pluja, R.id.giny_pluja_text, R.id.giny_gota, suau, blau);
        posaGota(v, gota, gotaSota, R.id.giny_pluja2, R.id.giny_pluja_text2, R.id.giny_gota2, suau, blau);
        posaLluna(v, lluna, llunaCostat, R.id.giny_lluna, R.id.giny_lluna_text, R.id.giny_lluna_dibuix, suau);
        posaLluna(v, lluna, llunaSota, R.id.giny_lluna2, R.id.giny_lluna_text2, R.id.giny_lluna_dibuix2, suau);
        v.setViewVisibility(R.id.giny_sota, gotaSota || llunaSota ? View.VISIBLE : View.GONE);

        // El dibuix, tan ample com deixa el costat (Android 12 o posterior; abans, la capsa de l'XML).
        if (variable) {
            float costat = Math.max(gotaCostat ? gotaW : 0, llunaCostat ? llunaW : 0);
            float cel = Math.max(celMin, Math.min(celMax, contingut - tempW - 16 - costat));
            v.setViewLayoutWidth(R.id.giny_cel, cel, TypedValue.COMPLEX_UNIT_DIP);
        }
        return compara;
    }

    static void posaGota(RemoteViews v, String gota, boolean hi, int bloc, int text, int dibuix, int suau, int blau) {
        v.setViewVisibility(bloc, hi ? View.VISIBLE : View.GONE);
        if (!hi) return;
        v.setTextViewText(text, gota);
        v.setTextColor(text, suau);
        // El blau de la mínima de cada cel, que es llegeix sobre el fons.
        v.setInt(dibuix, "setColorFilter", blau);
    }

    static void posaLluna(RemoteViews v, JSONObject lluna, boolean hi, int bloc, int text, int dibuix, int suau) {
        v.setViewVisibility(bloc, hi ? View.VISIBLE : View.GONE);
        if (!hi) return;
        v.setTextViewText(text, lluna.optString("text"));
        v.setTextColor(text, suau);
        v.setImageViewBitmap(dibuix, GinyLluna.dibuix(lluna.optDouble("angle", 180), 48));
    }

    static TextPaint pintura(Context context, float sp, String lletra, boolean negreta) {
        TextPaint p = new TextPaint(TextPaint.ANTI_ALIAS_FLAG);
        p.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, sp, context.getResources().getDisplayMetrics()));
        p.setTypeface(Typeface.create(lletra, negreta ? Typeface.BOLD : Typeface.NORMAL));
        return p;
    }

    /** L'amplada d'un text en dp. */
    static float ampla(Context context, String text, float sp, String lletra, boolean negreta) {
        return pintura(context, sp, lletra, negreta).measureText(text) / context.getResources().getDisplayMetrics().density;
    }

    /** L'alçada d'una línia de text en dp, amb el marge de la lletra (el de TextView per defecte) o sense. */
    static float alcada(Context context, float sp, String lletra, boolean ambMarge) {
        Paint.FontMetrics m = pintura(context, sp, lletra, false).getFontMetrics();
        return (ambMarge ? m.bottom - m.top : m.descent - m.ascent) / context.getResources().getDisplayMetrics().density;
    }

    /** L'alçada de la temperatura en dp: les xifres no baixen de la línia, i el que queda a sota no cal. */
    static float alcadaXifres(Context context, float sp) {
        return -pintura(context, sp, "sans-serif", false).getFontMetrics().ascent / context.getResources().getDisplayMetrics().density;
    }

    /** Quantes línies fa la frase (en negreta) en una amplada en dp. */
    static int liniesFrase(Context context, String frase, float sp, float ampleDp) {
        int px = Math.max(1, (int) (ampleDp * context.getResources().getDisplayMetrics().density));
        return StaticLayout.Builder.obtain(frase, 0, frase.length(), pintura(context, sp, "sans-serif", true), px)
            .setLineSpacing(0, 1.05f).build().getLineCount();
    }

    /** La línia de sota la frase, amb el compte enrere tornat a calcular i, si és de pluja, en una pastilla blava. */
    static CharSequence linia(JSONObject t) {
        JSONArray trossos = t.optJSONArray("linia");
        SpannableStringBuilder s = new SpannableStringBuilder();
        if (trossos == null) return s;
        JSONObject textos = t.optJSONObject("textos");
        for (int i = 0; i < trossos.length(); i++) {
            Object tros = trossos.opt(i);
            if (tros instanceof JSONObject) {
                JSONObject compte = (JSONObject) tros;
                String txt = " " + textCompte(compte.optString("compte"), compte.optBoolean("hores"), textos) + " ";
                int inici = s.length();
                s.append(txt);
                if (t.optBoolean("linia_pluja")) {
                    s.setSpan(new BackgroundColorSpan(AIGUA_FONS), inici, s.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                    s.setSpan(new ForegroundColorSpan(AIGUA_TEXT), inici, s.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                }
            } else {
                s.append(String.valueOf(tros));
            }
        }
        return s;
    }

    /** El mateix que textCompte de web/casa.js, amb els textos que porta el JSON. */
    static String textCompte(String iso, boolean perHores, JSONObject textos) {
        Date quan = llegeix(iso);
        if (quan == null || textos == null) return "";
        long min = Math.max(0, Math.round((quan.getTime() - System.currentTimeMillis()) / 60000.0));
        if (perHores) {
            long h = Math.round(min / 60.0);
            return h < 1 ? textos.optString("menys_hora") : h == 1 ? textos.optString("una_hora")
                : textos.optString("hores").replace("{0}", String.valueOf(h));
        }
        if (min < 1) return textos.optString("ara");
        if (min < 60) {
            return min == 1 ? textos.optString("un_minut") : textos.optString("minuts").replace("{0}", String.valueOf(min));
        }
        long h = min / 60, m = min % 60;
        return m != 0 ? textos.optString("h_min").replace("{0}", String.valueOf(h)).replace("{1}", String.valueOf(m))
            : textos.optString("h").replace("{0}", String.valueOf(h));
    }

    /** Hores senceres des d'un moment ISO («2026-11-24T09:00+01:00»). */
    static long horesDesDe(String iso) {
        Date d = llegeix(iso);
        if (d == null) return 99;
        return Math.max(0, TimeUnit.MILLISECONDS.toHours(System.currentTimeMillis() - d.getTime()));
    }

    static Date llegeix(String iso) {
        if (iso == null || iso.length() < 16) return null;
        try {
            // «2026-11-24T09:00+01:00» → «2026-11-24T09:00+0100»: Android 7 no llegeix «XXX».
            String s = iso.substring(0, 16) + iso.substring(16).replace(":", "");
            return new SimpleDateFormat("yyyy-MM-dd'T'HH:mmZ", Locale.ROOT).parse(s);
        } catch (Exception e) {
            return null;
        }
    }

    /** Si un text de 13 sp (GinySuau) cap en una amplada en dp, amb la lletra mitjana, la més ampla. */
    static boolean hiCap(Context context, String text, float ampleDp) {
        float densitat = context.getResources().getDisplayMetrics().density;
        TextPaint p = new TextPaint();
        p.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 13, context.getResources().getDisplayMetrics()));
        p.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return p.measureText(text) <= ampleDp * densitat;
    }

    static void afegeix(SpannableStringBuilder s, String text, int color) {
        int inici = s.length();
        s.append(text);
        s.setSpan(new ForegroundColorSpan(color), inici, s.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    static String uneix(JSONArray a) {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < a.length(); i++) {
            if (s.length() > 0) s.append(" · ");
            s.append(a.optString(i));
        }
        return s.toString();
    }

    static int recurs(Context context, String nom) {
        int id = context.getResources().getIdentifier(nom, "drawable", context.getPackageName());
        return id != 0 ? id : R.drawable.giny_fons_nuvol;
    }

    static PendingIntent obreApp(Context context) {
        Intent i = new Intent(context, LauncherActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return PendingIntent.getActivity(context, 0, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
