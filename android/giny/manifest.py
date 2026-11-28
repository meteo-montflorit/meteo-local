#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Posa el giny (ADR 0131) a l'AndroidManifest.xml que genera Bubblewrap: el
receptor, el permís d'internet i l'activitat que el posa d'un toc (PosaGiny). «bubblewrap update» torna a escriure el
manifest i els treu; construeix.sh ho crida abans de compilar. Si ja hi són,
no fa res.

    python3 android/giny/manifest.py
"""
import pathlib

MANIFEST = pathlib.Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "AndroidManifest.xml"

PERMIS = '<uses-permission android:name="android.permission.INTERNET"/>'
ACTIVITAT = """
        <!-- Posa el giny d'un toc des de la web (ADR 0131): el posa android/giny/manifest.py. -->
        <activity android:name="PosaGiny"
            android:exported="true"
            android:theme="@android:style/Theme.Translucent.NoTitleBar"
            android:excludeFromRecents="true"
            android:noHistory="true"
            android:taskAffinity="">
            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="montflorit" android:host="posa-giny" />
            </intent-filter>
        </activity>
"""
RECEPTOR = """
        <!-- El giny de la pantalla d'inici (ADR 0131): el posa android/giny/manifest.py. -->
        <receiver android:name="GinyProvider"
            android:label="@string/giny_nom"
            android:exported="false">
            <intent-filter>
                <action android:name="android.appwidget.action.APPWIDGET_UPDATE" />
                <action android:name="android.intent.action.LOCALE_CHANGED" />
            </intent-filter>
            <meta-data android:name="android.appwidget.provider"
                android:resource="@xml/giny_info" />
        </receiver>
"""


def posa(text):
    if PERMIS not in text:
        text = text.replace("<application", f"{PERMIS}\n\n    <application", 1)
    if 'android:name="GinyProvider"' not in text:
        text = text.replace("</application>", RECEPTOR + "    </application>", 1)
    if 'android:name="PosaGiny"' not in text:
        text = text.replace("</application>", ACTIVITAT + "    </application>", 1)
    return text


if __name__ == "__main__":
    abans = MANIFEST.read_text(encoding="utf-8")
    despres = posa(abans)
    if despres != abans:
        MANIFEST.write_text(despres, encoding="utf-8")
        print("giny posat al manifest")
