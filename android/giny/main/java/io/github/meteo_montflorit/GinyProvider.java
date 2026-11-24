// SPDX-License-Identifier: AGPL-3.0-or-later
// El giny de la pantalla d'inici (ADR 0131): el que diu la targeta d'«Ara» de
// la web, amb el seu fons i els seus colors. Els textos ja venen fets del NAS
// (giny.json, que surt de giny.js amb el mateix codi de la web), en català i
// en castellà; aquí només es pinten i es torna a escriure el compte enrere de
// la pluja, que depèn de l'hora en què es mira.
package io.github.meteo_montflorit;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.util.SizeF;
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
    // Amb dades de VELLES_H hores o més, el giny diu de quan són i la
    // temperatura es posa en gris (es veu que no és la d'ara).
    static final long VELLES_H = 2;
    // El color de la pastilla del compte enrere de la pluja (web/estil.css, .comenca-pluja).
    static final int AIGUA_FONS = 0xFFDBEAFE;
    static final int AIGUA_TEXT = 0xFF1E40AF;

    // Les quatre formes i la mida (dp) a partir de la qual es fan servir.
    enum Forma {
        FILA(R.layout.giny_fila, 110, 40),
        PETIT(R.layout.giny_petit, 110, 100),
        MITJA(R.layout.giny_mitja, 220, 100),
        GRAN(R.layout.giny_gran, 220, 175);

        final int layout;
        final float ample;
        final float alt;

        Forma(int layout, float ample, float alt) {
            this.layout = layout;
            this.ample = ample;
            this.alt = alt;
        }

        /** La que hi cap en una mida (per a Android 11 o anterior, que no tria sol). */
        static Forma per(float ample, float alt) {
            if (alt < PETIT.alt) return FILA;
            if (ample < MITJA.ample) return PETIT;
            return alt >= GRAN.alt ? GRAN : MITJA;
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
    }

    // --- Les dades.

    static void descarrega(Context context, PendingResult resultat) {
        new Thread(() -> {
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
                    break;
                }
                pintaTots(context);
            } finally {
                if (resultat != null) resultat.finish();
            }
        }).start();
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
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            // Android 12 o posterior tria la forma que hi cap, també en girar el mòbil.
            Map<SizeF, RemoteViews> formes = new HashMap<>();
            for (Forma f : Forma.values()) formes.put(new SizeF(f.ample, f.alt), vista(context, f, d));
            return new RemoteViews(formes);
        }
        Bundle o = manager.getAppWidgetOptions(id);
        // En vertical, l'amplada mínima i l'alçada màxima.
        float ample = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        float alt = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 110);
        return vista(context, Forma.per(ample, alt), d);
    }

    static RemoteViews vista(Context context, Forma forma, JSONObject d) {
        String idioma = context.getString(R.string.giny_idioma);
        JSONObject t = d == null ? null : d.optJSONObject(idioma);
        if (t == null || t.optJSONObject("cel") == null) {
            RemoteViews v = new RemoteViews(context.getPackageName(), R.layout.giny_carregant);
            if (d != null) v.setTextViewText(R.id.giny_avis, context.getString(R.string.giny_sense_dades));
            v.setOnClickPendingIntent(R.id.giny_arrel, obreApp(context));
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
        String titol = forma == Forma.GRAN || forma == Forma.MITJA ? t.optString("titol") : "Montflorit";
        if (velles) titol += " · " + context.getString(R.string.giny_vell, hores);
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

        if (forma == Forma.MITJA || forma == Forma.GRAN) {
            v.setTextViewText(R.id.giny_frase, t.optString("frase"));
            v.setTextColor(R.id.giny_frase, text);
            v.setTextViewText(R.id.giny_quan, dia == null ? "" : dia.optString("quan"));
            v.setTextColor(R.id.giny_quan, suau);
            String compara = dia == null || dia.isNull("compara") ? "" : dia.optString("compara");
            v.setTextViewText(R.id.giny_compara, compara);
            v.setTextColor(R.id.giny_compara, suau);
            v.setViewVisibility(R.id.giny_compara, compara.isEmpty() ? View.GONE : View.VISIBLE);
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
        if (forma == Forma.MITJA || forma == Forma.GRAN) descripcio += " " + t.optString("frase");
        v.setContentDescription(R.id.giny_arrel, descripcio);
        v.setOnClickPendingIntent(R.id.giny_arrel, obreApp(context));
        return v;
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
