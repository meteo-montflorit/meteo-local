# SPDX-License-Identifier: AGPL-3.0-or-later
"""Més proves de l'aprenentatge (aprenentatge.py, ADR 0012, 0017, 0047, 0068,
0069 i 0114): el model en ús quan falten fitxers, la correcció del rosada, el
missatge d'un canvi de mètode, la passada diària quan les comprovacions
fallen, el registre de «Si surts» i les ordres. Sense xarxa ni Telegram."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import random
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import aprenentatge as A  # noqa: E402
import config as C  # noqa: E402

RUTES = ("REGISTRE", "DIR", "MODEL", "PROPOSAT", "ATURA", "HISTORIAL", "HISTORIAL_HUMITAT", "AVIS_XV", "SORTIR",
         "MOTO_VELL", "AVIS_SORTIR", "LLINDARS_SORTIR", "PROPOSTA_SORTIR")


def hora(fins, temp=20.0, hr=80, antelacio=3.0, error_rosada=None):
    d = {"fins": fins, "antelacio_h": antelacio, "prob_ens": 0.1, "temperature_2m": temp,
         "relative_humidity_2m": hr, "cloud_cover": 50, "wind_speed_10m": 10, "shortwave_radiation": 300,
         "error_temp_ara": 1.0, "deficit_rosada_ara": 2.0, "error_rosada_ara": error_rosada}
    d.update({f"pluja_{m}": 0.0 for m in C.MODELOS_FINOS})
    return d


class AmbCarpetes(unittest.TestCase):
    """Totes les rutes del NAS dins d'una carpeta temporal, restaurades en acabar."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        reg, apr = os.path.join(self.tmp.name, "registre"), os.path.join(self.tmp.name, "aprenentatge")
        valors = {"REGISTRE": reg, "DIR": apr, "MODEL": os.path.join(apr, "model.json"),
                  "PROPOSAT": os.path.join(apr, "proposat.json"), "ATURA": os.path.join(apr, "atura"),
                  "HISTORIAL": os.path.join(apr, "historial.csv"),
                  "HISTORIAL_HUMITAT": os.path.join(apr, "historial-humitat.csv"),
                  "AVIS_XV": os.path.join(apr, "avis-sant-cugat"), "SORTIR": os.path.join(reg, "sortir.csv"),
                  "MOTO_VELL": os.path.join(reg, "moto.csv"), "AVIS_SORTIR": os.path.join(apr, "avis-sortir"),
                  "LLINDARS_SORTIR": os.path.join(apr, "llindars-sortir.json"),
                  "PROPOSTA_SORTIR": os.path.join(apr, "llindars-sortir-proposta.json")}
        for nom in RUTES:
            p = mock.patch.object(A, nom, valors[nom])
            p.start()
            self.addCleanup(p.stop)
        os.makedirs(reg)
        os.makedirs(apr)


class ModelEnUs(AmbCarpetes):
    def test_variants_de_l_arxiu_absents(self):
        with mock.patch.object(A, "ARXIU_ECMWF", os.path.join(self.tmp.name, "no.json")), \
                mock.patch.object(A, "ARXIU_AVISOS", os.path.join(self.tmp.name, "no.json")):
            self.assertIsNone(A.modelo_arxiu_ecmwf())
            self.assertIsNone(A.modelo_arxiu_avisos())
            self.assertEqual(A.variants_arxiu(), [])

    def test_sense_correccio_de_l_arxiu_queda_buida(self):
        # Un model propi de pluja al NAS i cap fitxer de temperatura: la pluja, la pròpia; la temperatura, cap.
        propi = {"origen": "local", "des_de": "2026-09-01", "rasgos": ["constant"], "w": [0.0]}
        A.guarda(A.MODEL, {"pluja": propi})
        with mock.patch.object(A, "ARXIU_TEMPERATURA", os.path.join(self.tmp.name, "no.json")):
            m = A.carrega()
        self.assertEqual(m["pluja"], propi)
        self.assertIsNone(m["temperatura"])
        self.assertEqual(m["humitat"]["origen"], "arxiu")
        # Sense temperatura corregida, la del model meteorològic.
        self.assertEqual(A.temperatura(m, hora("2026-10-10T12:00", temp=17.5)), 17.5)
        self.assertEqual(A.prob_pluja(m, hora("2026-10-10T12:00")), 0.5)      # w = 0: logística de 0

    def test_resum_de_la_pagina(self):
        m = {"pluja": {"origen": "local", "des_de": "2026-09-01", "w": [1]},
             "temperatura": {"origen": "casa", "des_de": "2026-09-02"},
             "humitat": {"origen": "barri", "des_de": "2026-09-03"}}
        self.assertEqual(A.resum_pagina(m), {"pluja": {"origen": "local", "des_de": "2026-09-01"},
                                             "temperatura": {"origen": "casa", "des_de": "2026-09-02"},
                                             "humitat": {"origen": "barri", "des_de": "2026-09-03"}})
        self.assertEqual(A.resum_pagina(None), {"pluja": None, "temperatura": None, "humitat": None})


class Correccions(unittest.TestCase):
    def test_temperatura_sense_els_rasgos_que_demana(self):
        # Un model que necessita un rasgo que l'hora no porta: la temperatura del model, sense tocar.
        m = {"temperatura": {"rasgos": ["constant", "inexistent"], "w": [5.0, 1.0]}}
        self.assertEqual(A.temperatura(m, hora("2026-10-10T12:00", temp=21.0)), 21.0)

    def test_rosada_corregida_i_sense_estacio(self):
        h = hora("2026-10-10T12:00", temp=20.0, hr=60, error_rosada=None)
        r = A.rosada_model(h)
        m = {"humitat": {"rasgos": ["constant", "error_rosada_ara_3h"], "w": [9.0, 9.0],
                         "rasgos_sense_estacio": ["constant"], "w_sense_estacio": [1.5]}}
        # Sense l'error que tenia al prever, els pesos sense estació.
        self.assertAlmostEqual(A.rosada(m, h), r - 1.5)
        # Amb l'error, els complets.
        h["error_rosada_ara"] = 0.0
        self.assertAlmostEqual(A.rosada(m, h), r - 9.0)
        # Sense cap conjunt de pesos aplicable, el rosada del model.
        self.assertAlmostEqual(A.rosada({"humitat": {"rasgos": ["inexistent"], "w": [1.0]}}, h), r)
        self.assertIsNone(A.rosada(m, {"fins": "2026-10-10T12:00", "temperature_2m": 20.0}))

    def test_nivell_d_un_mitja_sense_regla(self):
        self.assertEqual(A.nivell_pluja("tren", {"probabilitat": 0.99, "plou_ara": True}), "be")

    def test_wilson_sense_casos(self):
        self.assertEqual(A.wilson(0, 0), (0.0, 1.0))


def mostres_rosada(dies=20, biaix=2.0, amb_temp=True):
    """El model dona el rosada biaix graus més alt que el mesurat al barri."""
    rnd = random.Random(5)
    res = []
    inici = dt.datetime(2026, 9, 1)
    for k in range(dies * 24):
        t = inici + dt.timedelta(hours=k)
        fins = t.strftime("%Y-%m-%dT%H:%M")
        h = hora(fins, temp=15 + 8 * rnd.random(), hr=50 + 40 * rnd.random(), antelacio=2, error_rosada=biaix)
        obs = A.rosada_model(h) - biaix
        res.append({**h, "emes": fins + "+02:00", "obs_rosada": obs, "obs_temp": h["temperature_2m"] if amb_temp else None,
                    "obs_pluja": None})
    return res


class Rosada(unittest.TestCase):
    def test_sense_mostres(self):
        self.assertIsNone(A.valida_humitat([], None))
        self.assertIsNone(A.valida_temperatura([{"obs_temp": None}], None))

    def test_la_correccio_apren_el_biaix(self):
        v = A.valida_humitat(mostres_rosada(), None)
        self.assertEqual(v["dies"], 20)
        self.assertAlmostEqual(v["error_abans"], 2.0, places=6)          # el model sense corregir
        self.assertLess(v["error"], 0.05)
        self.assertGreaterEqual(v["seguretat"], 0.95)
        # En punts d'humitat, també millora.
        self.assertLess(v["error_humitat"], v["error_humitat_abans"])
        self.assertEqual(len(v["w"]), len(A.RASGOS_ROSADA))
        self.assertEqual(len(v["w_sense_estacio"]), len(A.RASGOS_ROSADA_SENSE_ESTACIO))

    def test_sense_temperatura_mesurada_no_hi_ha_humitat(self):
        v = A.valida_humitat(mostres_rosada(dies=10, amb_temp=False), None)
        self.assertIsNone(v["error_humitat"])
        self.assertIsNone(v["error_humitat_abans"])

    def test_pocs_dies_no_s_avaluen(self):
        # Amb menys dies dels que calen per entrenar, cap dia s'avalua.
        self.assertIsNone(A.valida_humitat(mostres_rosada(dies=5), None))

    def test_el_candidat_adopta_la_del_barri(self):
        ms = mostres_rosada()
        with mock.patch.object(A, "valida_pluja", return_value=None), \
                mock.patch.object(A, "valida_temperatura", return_value=None):
            model, vp, vt = A.candidat(ms, {"origen": "arxiu"}, None, "2026-09-21", None)
        self.assertIsNone(vp)
        h = model["humitat"]
        self.assertEqual((h["origen"], h["des_de"], h["fins"]), ("barri", "2026-09-01", "2026-09-21"))
        self.assertEqual(model["_vh"]["dies"], 20)
        text = A.explica({"pluja": {"origen": "arxiu"}, "temperatura": None, "humitat": None}, model, vp, vt)
        self.assertIn("Humitat: el rosada es corregeix amb el registre del barri (20 dies)", text)
        self.assertIn("dels remostrejos per dies", text)
        # Amb menys dies dels que calen, no.
        with mock.patch.object(A, "MIN_DIES_HUMITAT", 21), mock.patch.object(A, "valida_pluja", return_value=None), \
                mock.patch.object(A, "valida_temperatura", return_value=None):
            model, _, _ = A.candidat(ms, {"origen": "arxiu"}, None, "2026-09-21", None)
        self.assertIsNone(model["humitat"])


class Explica(unittest.TestCase):
    ARXIU = {"pluja": {"origen": "arxiu"}, "temperatura": {"origen": "arxiu"}, "humitat": {"origen": "arxiu"}}

    def pluja(self, rasgos, **extra):
        return {"origen": "local", "rasgos": rasgos, "mostres": 900, "error": 0.0612, "error_abans": 0.0701, **extra}

    def test_la_pluja_diu_amb_quin_rasgo(self):
        for rasgo, frase in (("sant_cugat", " i la pluja de Sant Cugat"),
                             ("veines", " i la pluja de les estacions veïnes"),
                             ("avis_aemet", " i els avisos oficials")):
            nou = {**self.ARXIU, "pluja": self.pluja(A.RASGOS_PROPIS + [rasgo], seguretat=0.97, error_base=0.0650)}
            text = A.explica(self.ARXIU, nou, None, None)
            self.assertIn(f"Pluja: passa a aprendre de l'estació de casa{frase} (900 mostres).", text)
            self.assertIn("Error 0.0612 en setmanes no vistes, abans 0.0701 (guanya en el 97 %", text)
            self.assertIn("Sense aquest rasgo, a les mateixes hores: 0.0650.", text)
        # El base, sense seguretat ni error de base.
        text = A.explica(self.ARXIU, {**self.ARXIU, "pluja": self.pluja(A.RASGOS_PROPIS)}, None, None)
        self.assertIn("de l'estació de casa (900 mostres). Error 0.0612 en setmanes no vistes, abans 0.0701.", text)
        self.assertNotIn("Sense aquest rasgo", text)
        self.assertTrue(text.startswith("Temps a casa: canvi de mètode"))
        self.assertTrue(text.endswith("Per aturar-ho, demana-ho a Claude abans de demà."))

    def test_tornar_a_l_arxiu(self):
        abans = {"pluja": self.pluja(A.RASGOS_PROPIS), "temperatura": {"origen": "casa"},
                 "humitat": {"origen": "barri"}}
        text = A.explica(abans, {**self.ARXIU, "_vh": None}, None, None)
        self.assertIn("Pluja: torna al model de l'arxiu", text)
        self.assertIn("Temperatura: torna a la correcció de l'arxiu", text)
        self.assertIn("Humitat: torna a la correcció de l'arxiu", text)

    def test_temperatura_sense_seguretat(self):
        vt = {"dies": 15, "error": 0.81, "error_abans": 1.02}
        text = A.explica(self.ARXIU, {**self.ARXIU, "temperatura": {"origen": "casa"}}, None, vt)
        self.assertIn("Temperatura: es corregeix amb el registre propi (15 dies). Error mitjà 0.81 °C, "
                      "amb la correcció de l'arxiu 1.02 °C.", text)
        self.assertNotIn("Pluja:", text)


class Diari(AmbCarpetes):
    """La passada diària: cada comprovació que falla es diu i no atura la resta."""

    def nou(self):
        return {"pluja": {"origen": "arxiu"}, "temperatura": {"origen": "casa", "des_de": "2026-09-01"},
                "humitat": None, "_vh": None}

    def vp(self):
        xv = {"hores_pluja": A.MIN_HORES_PLUJA, "error": 0.05, "error_base": 0.06, "error_abans": 0.07}
        return {"mostres": 100, "hores_pluja": 40, "error": 0.06, "error_abans": 0.07, "xv": xv, "avis": None}

    def executa(self, **patches):
        import fi_pluja
        import llum
        import nuvols
        import radar_fonts
        import smp
        import trens
        import vent_veines
        falla = OSError("caigut")
        with contextlib.ExitStack() as pila:
            for modul, nom in ((radar_fonts, "verifica"), (nuvols, "verifica"), (smp, "comprova"),
                               (llum, "comprova"), (trens, "comprova"), (vent_veines, "apren")):
                pila.enter_context(mock.patch.object(modul, nom, side_effect=falla))
            pila.enter_context(mock.patch.object(fi_pluja, "verifica", return_value="Final de la pluja: 5 episodis."))
            run = pila.enter_context(mock.patch.object(A.subprocess, "run"))
            pila.enter_context(mock.patch.object(A, "modelo_arxiu_humitat", side_effect=ValueError("malmès")))
            pila.enter_context(mock.patch.object(A, "candidat", return_value=(self.nou(), self.vp(), {"dies": 20,
                                                 "error": 0.8, "error_abans": 1.0, "seguretat": 0.99})))
            for nom, valor in patches.items():
                pila.enter_context(mock.patch.object(A, nom, **valor))
            out = pila.enter_context(contextlib.redirect_stdout(io.StringIO()))
            A.diari("2026-10-20", avisa=True)
        return out.getvalue(), run

    def test_les_fallades_es_diuen_i_el_canvi_es_proposa(self):
        text, run = self.executa(verifica_sortir={"side_effect": OSError("sortir.csv")})
        for frase in ("No he pogut comparar els radars: caigut", "No he pogut comparar els núvols: caigut",
                      "Final de la pluja: 5 episodis.", "No he pogut comprovar els avisos de Meteocat: caigut",
                      "No he pogut comprovar el mapa de talls de llum: caigut",
                      "No he pogut comprovar l'API d'avisos de Rodalies: caigut",
                      "No he pogut verificar Si surts: sortir.csv",
                      "No he pogut aprendre el vent de les veïnes: caigut"):
            self.assertIn(frase, text)
        # Sant Cugat ja té prou hores de pluja: s'avisa un cop; i el canvi de mètode, també.
        missatges = [c.args[0][-1] for c in run.call_args_list]
        self.assertEqual(len(missatges), 2)
        self.assertIn("hores de pluja amb la dada de Sant Cugat", missatges[0])
        self.assertIn("Ajuda: si vols", missatges[0])
        self.assertIn("Temperatura: es corregeix amb el registre propi (20 dies)", missatges[1])
        with open(A.PROPOSAT, encoding="utf-8") as f:
            proposat = json.load(f)
        self.assertEqual(proposat["dia"], "2026-10-20")
        self.assertEqual(proposat["model"]["temperatura"]["origen"], "casa")
        self.assertIsNone(proposat["model"]["pluja"])                    # el de l'arxiu no es desa
        self.assertNotIn("_vh", proposat["model"])
        self.assertTrue(os.path.exists(A.HISTORIAL))
        self.assertTrue(os.path.exists(A.HISTORIAL_HUMITAT))

    def test_els_resums_de_si_surts_es_mostren(self):
        text, run = self.executa(verifica_sortir={"return_value": 3},
                                 avis_sortir={"return_value": "Si surts, comprovació"},
                                 aprén_sortir={"return_value": "Si surts, llindars de pluja: canvi"})
        self.assertIn("Si surts: hores noves verificades: 3", text)
        self.assertIn("Si surts, comprovació", text)
        self.assertIn("Si surts, llindars de pluja: canvi", text)
        # L'avís de Sant Cugat no es repeteix.
        _, run = self.executa(verifica_sortir={"return_value": 0}, avis_sortir={"return_value": None},
                              aprén_sortir={"return_value": None})
        self.assertFalse(any("Sant Cugat" in c.args[0][-1] for c in run.call_args_list))


def escriu_registre(reg, files_casa, hores):
    with open(os.path.join(reg, "estacio-casa.csv"), "w", encoding="utf-8") as f:
        f.write("fins,pluja_mm,temperatura,humitat,rosada,pressio,solar\n" + "".join(l + "\n" for l in files_casa))
    with open(os.path.join(reg, "casa-2026-10.jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"emes": "2026-10-08T09:00+02:00", "hores": hores}) + "\n")


class SortirRegistre(AmbCarpetes):
    def mostrat(self, fins, antelacio=2):
        return {**hora(fins, antelacio=antelacio), "avis_pluja": 0.0,
                "mostrat": {"probabilitat": 0.5, "pluja_mm": 1.2, "temperatura": 18, "ratxa": 20}}

    def test_hores_sense_cap_mesura_no_s_apunten(self):
        # Les 11 h tenen pluja mesurada; de les 12 h no hi ha res mesurat: no es pot jutjar.
        escriu_registre(A.REGISTRE, ["2026-10-08T11:00,1.5,18,80,15,1013,0"],
                        [self.mostrat("2026-10-08T11:00"), self.mostrat("2026-10-08T12:00")])
        ara = dt.datetime(2026, 10, 8, 20, 0).astimezone()
        self.assertEqual(A.verifica_sortir(ara), 1)
        with open(A.SORTIR, encoding="utf-8") as f:
            (fila,) = list(csv.DictReader(f))
        self.assertEqual((fila["fins"], fila["termini"], fila["pluja_obs"], fila["probabilitat"]),
                         ("2026-10-08T11:00", "sortida", "1.5", "0.5"))
        # Tampoc no compten a les mostres de l'aprenentatge.
        self.assertEqual([m["fins"] for m in A.mostres()], ["2026-10-08T11:00"])

    def test_un_registre_d_abans_es_posa_al_dia(self):
        # sortir.csv sense «pluja_3h» (abans de la 3.139.0): es reescriu amb les columnes d'ara.
        vells = [c for c in A.CAMPS_SORTIR if c != "pluja_3h"]
        with open(A.SORTIR, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=vells)
            w.writeheader()
            w.writerow({**dict.fromkeys(vells, ""), "fins": "2026-10-07T10:00", "termini": "sortida",
                        "probabilitat": "0.2"})
        escriu_registre(A.REGISTRE, ["2026-10-08T11:00,0.0,18,80,15,1013,0"], [self.mostrat("2026-10-08T11:00")])
        self.assertEqual(A.verifica_sortir(dt.datetime(2026, 10, 8, 20, 0).astimezone()), 1)
        with open(A.SORTIR, encoding="utf-8") as f:
            r = csv.DictReader(f)
            files = list(r)
        self.assertEqual(r.fieldnames, A.CAMPS_SORTIR)
        self.assertEqual([(x["fins"], x["probabilitat"], x["pluja_3h"]) for x in files],
                         [("2026-10-07T10:00", "0.2", ""), ("2026-10-08T11:00", "0.5", "")])
        # Una segona passada no torna a apuntar la mateixa hora.
        self.assertEqual(A.verifica_sortir(dt.datetime(2026, 10, 8, 20, 0).astimezone()), 0)

    def test_resum_d_un_registre_buit(self):
        with open(A.SORTIR, "w", encoding="utf-8") as f:
            f.write(",".join(A.CAMPS_SORTIR) + "\n")
        self.assertIsNone(A.resum_sortir())
        self.assertIsNone(A.avis_sortir(avisa=True))

    def test_l_avis_del_resum_s_envia(self):
        r = {"dies": A.DIES_RESUM_SORTIR}
        with mock.patch.object(A, "resum_sortir", return_value=r), \
                mock.patch.object(A, "text_resum_sortir", return_value="Si surts, comprovació"), \
                mock.patch.object(A.subprocess, "run") as run:
            self.assertEqual(A.avis_sortir(avisa=True), "Si surts, comprovació")
            self.assertIsNone(A.avis_sortir(avisa=True))                 # una sola vegada
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-1], "Si surts, comprovació")

    def test_la_proposta_de_llindars_s_envia(self):
        mostres = {"curt": [(0.5, True)] * 40, "llarg": []}
        with mock.patch.object(A, "mostres_sortir", return_value=mostres), \
                mock.patch.object(A, "apren_llindars", side_effect=lambda m: {"pluja": 0.5, "risc": 0.05} if m else None), \
                mock.patch.object(A.subprocess, "run") as run:
            text = A.aprén_sortir("2026-10-20", avisa=True)
        self.assertIn("«millor no» des del 40 % al 50 %, «compte» des del 10 % al 5 % (40 hores, 40 amb pluja)", text)
        run.assert_called_once()
        with open(A.PROPOSTA_SORTIR, encoding="utf-8") as f:
            proposta = json.load(f)
        self.assertEqual(proposta["llindars"]["curt"], {"pluja": 0.5, "risc": 0.05})
        self.assertEqual(proposta["llindars"]["llarg"], C.SORTIR_LLINDARS_PLUJA["llarg"])


class Ordres(AmbCarpetes):
    def test_estat_mostra_el_model_i_l_historial(self):
        with open(A.HISTORIAL, "w", encoding="utf-8") as f:
            f.write("".join(f"linia {k}\n" for k in range(8)))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            A.estat()
        linies = out.getvalue().splitlines()
        self.assertEqual(json.loads(linies[0])["pluja"]["origen"], "arxiu")
        self.assertEqual(linies[1:], [f"linia {k}" for k in range(3, 8)])     # només les 5 últimes

    def executa(self, *args):
        entorn = {"REGISTRE_DIR": A.REGISTRE, "APRENENTATGE_DIR": A.DIR}
        with mock.patch.dict(os.environ, entorn), mock.patch.object(sys, "argv", ["aprenentatge.py", *args]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            runpy.run_path(os.path.join(ARREL, "aprenentatge.py"), run_name="__main__")
        return out.getvalue()

    def test_ordres(self):
        self.assertEqual(self.executa("sortir"), "Encara no hi ha cap hora verificada.\n")
        self.assertEqual(self.executa("moto"), "Encara no hi ha cap hora verificada.\n")
        self.assertIn('"pluja": {"origen": "arxiu"', self.executa("estat"))
        self.assertIn("Uso:", self.executa())


if __name__ == "__main__":
    unittest.main()
