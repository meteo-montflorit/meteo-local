# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del aprendizaje de la página de casa (sin red ni Telegram)."""
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aprenentatge as A  # noqa: E402
import config as C  # noqa: E402


def hora(fins, mm=0.0, temp=20.0, antelacio=3.0, error_ara=1.0):
    d = {"fins": fins, "antelacio_h": antelacio, "prob_ens": 0.1, "temperature_2m": temp,
         "relative_humidity_2m": 80, "cloud_cover": 50, "wind_speed_10m": 10,
         "shortwave_radiation": 300, "error_temp_ara": error_ara, "deficit_rosada_ara": 2.0}
    d.update({f"pluja_{m}": mm for m in C.MODELOS_FINOS})
    return d


class Rasgos(unittest.TestCase):
    def test_vector_y_persistencia(self):
        d = {**hora("2026-10-05T18:00", mm=1.0), "pluja_1h_emes": 2.0}
        x = A.rasgos(d, A.RASGOS_PROPIS)
        self.assertEqual(len(x), len(A.RASGOS_PROPIS))
        self.assertAlmostEqual(x[A.RASGOS_PROPIS.index("persistencia")], 1.0986, places=3)
        # Lejos en el tiempo, la lluvia medida al prever ya no cuenta.
        lejos = A.rasgos({**d, "antelacio_h": 10}, A.RASGOS_PROPIS)
        self.assertEqual(lejos[A.RASGOS_PROPIS.index("persistencia")], 0.0)
        # Falta un modelo: no hay vector.
        self.assertIsNone(A.rasgos({**d, "pluja_icon_eu": None}, A.RASGOS_PROPIS))
        # Aire seco al prever: cuenta en las primeras horas; sin dato, no hay vector.
        self.assertAlmostEqual(x[A.RASGOS_PROPIS.index("sequedat")], 0.2)
        self.assertEqual(lejos[A.RASGOS_PROPIS.index("sequedat")], 0.0)
        self.assertIsNone(A.rasgos({**d, "deficit_rosada_ara": None}, A.RASGOS_PROPIS))
        # La lluvia de Sant Cugat al prever, como la persistencia; sin dato, no hay vector (ADR 0042).
        xv = A.rasgos({**d, "pluja_1h_xv": 2.0}, A.RASGOS_PROPIS_XV)
        self.assertAlmostEqual(xv[A.RASGOS_PROPIS_XV.index("sant_cugat")], 1.0986, places=3)
        self.assertEqual(A.rasgos({**d, "pluja_1h_xv": 2.0, "antelacio_h": 10}, A.RASGOS_PROPIS_XV)[-1], 0.0)
        self.assertIsNone(A.rasgos(d, A.RASGOS_PROPIS_XV))
        self.assertIsNotNone(A.rasgos(d, A.RASGOS_PROPIS))     # sin el rasgo, el vector de siempre
        # Lo oficial de la hora (ADR 0047): sin dato, no hay vector de esa variante.
        av = A.rasgos({**d, "avis_pluja": 1.0, "pla_inuncat": 0.0}, A.RASGOS_PROPIS_AVIS)
        self.assertEqual(av[-2:], [1.0, 0.0])
        self.assertIsNone(A.rasgos(d, A.RASGOS_PROPIS_AVIS))

    def test_la_hora_es_la_del_sol(self):
        # ADR 0090: las 15 h de verano y las 14 h de invierno, la misma hora
        # de sol; las dos horas de 2 a 3 del 25-10, distintas.
        noms = ["hora_sin", "hora_cos"]
        estiu = A.rasgos({"fins": "2026-10-24T15:00"}, noms)
        hivern = A.rasgos({"fins": "2026-10-26T14:00"}, noms)
        self.assertEqual(estiu, hivern)
        self.assertAlmostEqual(estiu[0], math.sin(2 * math.pi * 13 / 24))
        self.assertNotEqual(A.rasgos({"fins": "2026-10-25T02:00+02:00"}, noms),
                            A.rasgos({"fins": "2026-10-25T02:00+01:00"}, noms))

    def test_modelos_que_dan_lluvia_y_coinciden(self):
        # ADR 0021: que un modelo dé algo de lluvia cuenta por sí mismo, y
        # también cuántos coinciden.
        d = hora("2026-10-05T18:00", antelacio=12)
        d.update(pluja_meteofrance_arome_france_hd=0.0, pluja_meteofrance_arome_france=0.1,
                 pluja_icon_eu=0.3)
        x = dict(zip(A.RASGOS_ARXIU, A.rasgos(d, A.RASGOS_ARXIU)))
        self.assertEqual([x["plou_arome_hd"], x["plou_arome"], x["plou_icon_eu"]], [0.0, 1.0, 1.0])
        self.assertEqual([x["dos_models"], x["tres_models"]], [1.0, 0.0])
        self.assertAlmostEqual(x["icon_eu_antelacio"], x["icon_eu"] * 0.5)
        self.assertEqual([x["algun_antelacio"], x["tres_antelacio"]], [0.5, 0.0])

    def test_un_solo_modelo_con_poca_lluvia_no_es_casi_cero(self):
        # El caso del 06-10-2026: solo ICON-EU daba 0,2 mm y la página decía
        # un 2 %; en el archivo, con solo ICON-EU dando 0,2 mm llovió una de
        # cada diez horas (729 horas). Y cuantos más coinciden, más probabilidad.
        m = {"pluja": A.modelo_arxiu()}

        def prob(hd, arome, icon):
            d = hora("2026-10-06T16:00", antelacio=3)
            d.update(pluja_meteofrance_arome_france_hd=hd, pluja_meteofrance_arome_france=arome,
                     pluja_icon_eu=icon)
            return A.prob_pluja(m, d)
        nada, uno, dos, tres = prob(0, 0, 0), prob(0, 0, 0.2), prob(0.2, 0, 0.2), prob(0.2, 0.2, 0.2)
        self.assertLess(nada, 0.02)
        self.assertGreater(uno, 0.06)
        self.assertLess(uno, 0.15)
        self.assertGreater(dos, uno)
        self.assertGreater(tres, dos)

    def test_ecmwf_com_un_model_mes(self):
        # ADR 0086: si la pasada tiene ECMWF, se usa el modelo del archivo con él.
        d = hora("2026-10-13T15:00", mm=0.0, antelacio=24)
        self.assertIsNone(A.rasgos(d, A.RASGOS_ARXIU_ECMWF))
        sense = A.prob_pluja({"pluja": A.modelo_arxiu()}, d)
        d[f"pluja_{C.MODEL_ECMWF}"] = 2.0
        x = dict(zip(A.RASGOS_ARXIU_ECMWF, A.rasgos(d, A.RASGOS_ARXIU_ECMWF)))
        self.assertEqual((x["plou_ecmwf"], x["nomes_ecmwf"], x["quatre_models"]), (1.0, 1.0, 0.0))
        self.assertAlmostEqual(x["ecmwf_antelacio"], math.log1p(2.0))
        amb = A.prob_pluja({"pluja": A.modelo_arxiu()}, d)
        self.assertNotEqual(amb, sense)
        # Que solo lo vea ECMWF sube la probabilidad, sin pasar de lo que dan los cuatro.
        tots = hora("2026-10-13T15:00", mm=2.0, antelacio=24)
        tots[f"pluja_{C.MODEL_ECMWF}"] = 2.0
        self.assertGreater(amb, sense)
        self.assertGreater(A.prob_pluja({"pluja": A.modelo_arxiu()}, tots), amb)
        # El modelo guardado se ajustó con ECMWF y mejora a un día vista.
        me = A.modelo_arxiu_ecmwf()
        self.assertEqual(me["rasgos"], A.RASGOS_ARXIU_ECMWF)
        self.assertGreaterEqual(me["validacio"]["un_dia_abans"]["millora_pct"], 5)
        # Con un modelo propio en uso, no cambia nada.
        propi = {"origen": "propi", "rasgos": A.RASGOS_ARXIU, "w": A.modelo_arxiu()["w"]}
        self.assertAlmostEqual(A.prob_pluja({"pluja": propi}, d), A.prob_pluja({"pluja": propi}, hora("2026-10-13T15:00", antelacio=24)))

    def test_modelo_con_avisos_solo_si_esta_adoptado(self):
        # ADR 0097: el aviso es una señal más, con el peso aprendido, y solo
        # cuenta si la validación adoptó el modelo y la pasada tiene el dato.
        d = hora("2026-10-17T16:00", mm=0.0, antelacio=24)
        d[f"pluja_{C.MODEL_ECMWF}"] = 0.5
        me = A.modelo_arxiu_ecmwf()
        sense = A.prob_pluja({"pluja": A.modelo_arxiu()}, d)
        vell = A.ARXIU_AVISOS
        with tempfile.TemporaryDirectory() as dir_:
            A.ARXIU_AVISOS = os.path.join(dir_, "avisos.json")
            try:
                model = {"rasgos": A.RASGOS_ARXIU_ECMWF_AVISOS, "w": me["w"] + [2.0], "adoptat": False}
                with open(A.ARXIU_AVISOS, "w") as f:
                    json.dump(model, f)
                d["avis_pluja"] = 1.0
                self.assertAlmostEqual(A.prob_pluja({"pluja": A.modelo_arxiu()}, d), sense)
                model["adoptat"] = True
                with open(A.ARXIU_AVISOS, "w") as f:
                    json.dump(model, f)
                self.assertGreater(A.prob_pluja({"pluja": A.modelo_arxiu()}, d), sense)
                # Sin el dato del aviso (no se pudo leer), el modelo con ECMWF.
                d["avis_pluja"] = None
                self.assertAlmostEqual(A.prob_pluja({"pluja": A.modelo_arxiu()}, d), sense)
            finally:
                A.ARXIU_AVISOS = vell

    def test_fiabilidad_del_modelo_del_archivo(self):
        # La comprobación guardada con el modelo: en cada tramo de
        # probabilidad con bastantes horas, lo dado y lo que llovió no se
        # separan más de 5 puntos, a corto plazo y un día antes.
        v = A.modelo_arxiu()["validacio"]
        for clave in ("curt_termini", "un_dia_abans"):
            self.assertLess(v[clave]["error"], 0.95 * v[clave]["error_abans"])
            for f in v[clave]["fiabilitat"]:
                if f["hores"] >= 150:
                    self.assertLess(abs(f["donada"] - f["va_ploure"]), 0.05, (clave, f))

    def test_error_al_prever_se_apaga_con_la_antelacion(self):
        i = A.RASGOS_TEMPERATURA.index("error_ara_3h")
        cerca = A.rasgos(hora("2026-10-05T18:00", antelacio=0, error_ara=2.0), A.RASGOS_TEMPERATURA)
        lejos = A.rasgos(hora("2026-10-05T18:00", antelacio=12, error_ara=2.0), A.RASGOS_TEMPERATURA)
        self.assertAlmostEqual(cerca[i], 2.0)
        self.assertLess(lejos[i], 0.05)
        self.assertGreater(lejos[i + 1], 1.0)        # la parte lenta dura más

    def test_modelo_del_archivo(self):
        # Más lluvia prevista, más probabilidad; sin modelo, None.
        m = {"pluja": A.modelo_arxiu(), "temperatura": None}
        seco, mojado = (A.prob_pluja(m, hora("2026-10-05T18:00", mm=x)) for x in (0.0, 3.0))
        self.assertLess(seco, 0.05)
        self.assertGreater(mojado, 0.5)
        self.assertIsNone(A.prob_pluja({"pluja": None}, hora("2026-10-05T18:00")))
        self.assertEqual(A.temperatura(m, hora("2026-10-05T18:00", temp=21.5)), 21.5)

    def test_temperatura_del_archivo_con_y_sin_estacion(self):
        # El modelo da más calor que la estación de casa: la corrección baja la
        # temperatura; sin la estación al prever, también, con los otros pesos.
        m = {"temperatura": A.modelo_arxiu_temperatura()}
        con = A.temperatura(m, hora("2026-10-05T14:00", temp=22.0, antelacio=1, error_ara=2.0))
        sin = A.temperatura(m, hora("2026-10-05T14:00", temp=22.0, antelacio=1, error_ara=None))
        self.assertLess(con, sin)
        self.assertLess(sin, 22.0)

    def test_modelo_propio_sin_estacion_usa_el_archivo(self):
        propio = {"origen": "local", "rasgos": A.RASGOS_PROPIS, "w": [0.0] * len(A.RASGOS_PROPIS)}
        d = hora("2026-10-05T18:00", mm=3.0, antelacio=1)
        self.assertAlmostEqual(A.prob_pluja({"pluja": propio}, d), 0.5)
        sin = A.prob_pluja({"pluja": propio}, {**d, "deficit_rosada_ara": None})
        self.assertAlmostEqual(sin, A.prob_pluja({"pluja": A.modelo_arxiu()}, d))

    def test_lluvia_observada(self):
        # Lo que marca casa es lluvia; su cero solo vale si Meteocat tampoco recogió nada (ADR 0058).
        sec, moll = {"pluja_mm": "0.0"}, {"pluja_mm": "0.6"}
        self.assertEqual(A.pluja_observada({"pluja_mm": "1.2"}, [sec, sec]), 1.2)
        self.assertEqual(A.pluja_observada({"pluja_mm": "1.2"}), 1.2)
        self.assertEqual(A.pluja_observada({"pluja_mm": "0.0"}, [sec, sec]), 0.0)
        self.assertEqual(A.pluja_observada({"pluja_mm": "0.0"}, [sec, None]), 0.0)   # con una basta
        self.assertIsNone(A.pluja_observada({"pluja_mm": "0.0"}, [sec, moll]))     # llovía cerca: no se sabe
        self.assertIsNone(A.pluja_observada({"pluja_mm": "0.0"}, [None, None]))   # sin Meteocat, no se sabe
        self.assertIsNone(A.pluja_observada({"pluja_mm": "0.0"}))
        self.assertIsNone(A.pluja_observada(None, [sec, sec]))
        self.assertIsNone(A.pluja_observada({"pluja_mm": ""}, [sec, sec]))

    def test_montflorit_primer(self):
        # ADR 0070: les veïnes de Montflorit manen sobre Sabadell i Sant Cugat.
        z, p = {"pluja_mm": "0.0"}, {"pluja_mm": "0.6"}
        seca = {k: z for k in A.C.VEINES}
        # Casa i les veïnes a zero: seca, encara que plogui a Sabadell i a Sant Cugat.
        self.assertEqual(A.pluja_observada(z, [p, p], seca), 0.0)
        # Casa a zero però plou en dues veïnes que compten: plou (el pluviòmetre no ho va veure).
        dues = {**seca, "ICERDA18": p, "ICERDA28": {"pluja_mm": "1.0"}}
        self.assertGreaterEqual(A.pluja_observada(z, [z, z], dues), 0.6)
        # Una sola veïna amb pluja: no se sap.
        self.assertIsNone(A.pluja_observada(z, [z, z], {**seca, "ICERDA28": p}))
        # I llavors, els seus mm: potser va plovisquejar (l'historial ho diu).
        self.assertEqual(A.pluja_dubtosa({**seca, "ICERDA28": p}), 0.6)
        self.assertIsNone(A.pluja_dubtosa(seca))
        self.assertIsNone(A.pluja_dubtosa({**seca, "ICERDA48": p}))     # la que no compta
        # La que no compta per a la pluja no decideix.
        self.assertEqual(A.pluja_observada(z, [z, z], {**seca, "ICERDA48": p}), 0.0)
        # Sense cap veïna que confirmi, com abans: Meteocat.
        self.assertEqual(A.pluja_observada(z, [z, z], {}), 0.0)
        self.assertIsNone(A.pluja_observada(z, [z, p], {}))
        # Els registres per hores.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            vell = A.REGISTRE
            A.REGISTRE = d
            try:
                for nom in ("meteocat-XF", "meteocat-XV", "veina-ICERDA6", "veina-ICERDA28"):
                    with open(os.path.join(d, nom + ".csv"), "w") as f:
                        f.write("fins,pluja_mm\n2026-10-07T03:00," + ("0.6" if nom.startswith("meteocat") else "0.0") + "\n")
                self.assertEqual(len(A._meteocat()), 2)
                self.assertEqual(A.observada({"2026-10-07T03:00": z}, A._meteocat(), A._veines(), "2026-10-07T03:00"), 0.0)
            finally:
                A.REGISTRE = vell


class PlouAra(unittest.TestCase):
    """La veritat de la pluja d'ara amb les estacions (plou_ara_barri, ADR 0102)."""

    def veina(self, id_, mm):
        return {"estacio": id_, "pluja_15min": mm, "plou": bool(mm), "compta": bool(C.VEINES[id_]["plou"])}

    def test_casa_o_dues_veines(self):
        casa = {"plou": False}
        self.assertTrue(A.plou_ara_barri({"plou": True}, []))
        self.assertTrue(A.plou_ara_barri(casa, [self.veina("ICERDA6", 0.2), self.veina("ICERDA28", 0.1)]))
        self.assertIsNone(A.plou_ara_barri(casa, [self.veina("ICERDA6", 0.2), self.veina("ICERDA28", 0.0)]))
        self.assertFalse(A.plou_ara_barri(casa, [self.veina("ICERDA6", 0.0), self.veina("ICERDA18", 0.0)]))
        # ICERDA48 no compta ni confirma: amb ella sola, no se sap. Sense casa, tampoc.
        self.assertIsNone(A.plou_ara_barri(casa, [self.veina("ICERDA48", 0.0)]))
        self.assertIsNone(A.plou_ara_barri(casa, []))
        self.assertIsNone(A.plou_ara_barri(None, [self.veina("ICERDA6", 0.0), self.veina("ICERDA18", 0.0)]))
        # Plugim segons el radar: el zero és dubtós.
        self.assertIsNone(A.plou_ara_barri(casa, [self.veina("ICERDA6", 0.0), self.veina("ICERDA18", 0.0)], plugim=True))

    def test_llindar_de_la_regla(self):
        # Per a 5 minuts, 0,1 mm ja és pluja; per a l'hora, des de 0,2 (C.UMBRAL_MM).
        v = {"ICERDA6": {"pluja_mm": 0.1}, "ICERDA18": {"pluja_mm": 0.1}}
        self.assertEqual(A.pluja_observada({"pluja_mm": 0.0}, (), v, llindar=0.1), 0.1)
        self.assertEqual(A.pluja_observada({"pluja_mm": 0.0}, (), v), 0.0)


class Sortir(unittest.TestCase):
    """Les regles de «Si surts» de cada mitjà (ADR 0047 i 0068)."""

    def test_mismos_umbrales_que_la_pagina(self):
        web = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "sortir.js")
        js = open(web, encoding="utf-8").read()
        for nom, valor in (("MM_RISC", C.SORTIR_MM_RISC), ("MM_PLUJA", C.SORTIR_MM_PLUJA), ("CURT_H", C.SORTIR_CURT_H)):
            self.assertIn(f"const {nom} = {valor:g};", js)
        ll = C.SORTIR_LLINDARS_PLUJA
        self.assertIn("const LLINDARS_PLUJA_INICI = { curt: { pluja: %g, risc: %g }, llarg: { pluja: %g, risc: %g } };"
                      % (ll["curt"]["pluja"], ll["curt"]["risc"], ll["llarg"]["pluja"], ll["llarg"]["risc"]), js)
        for nom, clau in (("PLUJA_COTXE_30MIN", "30min"), ("PLUJA_COTXE_3H", "3h")):
            ll = C.SORTIR_PLUJA_COTXE[clau]
            self.assertIn(f"const {nom} = [{ll[0]:g}, {ll[1]:g}];", js)

    def test_el_cas_del_8_d_octubre(self):
        # A les 10 h, només l'avís; a les 17 h, ICON-EU 1,7 mm i un 25 %.
        deu, cinc = {"probabilitat": 0.0, "pluja_mm": 0.0, "avis": True}, {"probabilitat": 0.25, "pluja_mm": 1.7, "avis": True}
        self.assertEqual([A.nivell_pluja("moto", deu), A.nivell_pluja("moto", cinc)], ["compte", "compte"])
        self.assertEqual([A.nivell_moto_abans(deu), A.nivell_moto_abans({**cinc, "avis": False})], ["no", "no"])
        self.assertEqual(A.nivell_pluja("moto", {"probabilitat": 0.4, "pluja_mm": 0}), "no")
        self.assertEqual(A.nivell_pluja("moto", {"probabilitat": 0.05, "pluja_mm": 0.5}), "be")
        self.assertEqual(A.nivell_pluja("moto", {"probabilitat": None, "pluja_mm": 1.0}), "no")
        self.assertEqual(A.nivell_pluja("moto", {"probabilitat": 0.0, "pluja_mm": 0, "plou_ara": True}), "no")

    def test_cada_mitja_amb_les_seves_regles(self):
        h = {"probabilitat": 0.3, "pluja_mm": 0.5, "ratxa": 55, "temperatura": 2}
        self.assertEqual(A.nivells_sortir("peu", h), {"pluja": "compte", "vent": "be", "fred": "be"})
        self.assertEqual(A.nivells_sortir("bici", h), {"pluja": "compte", "vent": "no", "fred": "compte"})
        self.assertEqual(A.nivells_sortir("moto", h), {"pluja": "compte", "vent": "compte", "fred": "compte"})
        self.assertEqual(A.nivells_sortir("cotxe", h), {"pluja": "be", "vent": "be", "fred": "be"})
        self.assertEqual(A.nivell_sortir("bici", h), "no")
        # Cotxe, des de la 3.139.0: la pluja en 3 hores amb els llindars de Meteocat (60 i 90 mm, cal passar-los).
        self.assertEqual(A.nivell_pluja("cotxe", {"probabilitat": 0.1, "pluja_mm": 25}), "be")
        self.assertEqual(A.nivell_pluja("cotxe", {"probabilitat": 0.9, "pluja_mm": 45}), "compte")
        self.assertEqual(A.nivell_pluja("cotxe", {"probabilitat": 0.1, "pluja_mm": 0, "pluja_3h": 75}), "compte")
        self.assertEqual(A.nivell_pluja("cotxe", {"probabilitat": 0.1, "pluja_mm": 0, "pluja_3h": 95}), "no")
        self.assertEqual(A.nivell_pluja("cotxe", {"probabilitat": 0.1, "pluja_mm": 0, "pluja_3h": 60}), "be")

    def test_pluja_en_3_hores_com_la_pagina(self):
        hores = [{"pluja_mm": mm, "probabilitat": p} for mm, p in ((5, 0.5), (30, 0.9), (40, 0.9), (20, 0.1), (1, 0.3))]
        # La finestra de 3 hores que conté l'hora i més acumula; les hores per sota del 20 % no compten.
        self.assertEqual([A.pluja_3h(hores, i) for i in range(5)], [75, 75, 75, 70, 41])
        self.assertIsNone(A.pluja_3h(hores[:2], 0))
        self.assertIsNone(A.nivells_sortir("moto", {"probabilitat": 0})["vent"])     # sense ratxa, res


class Veines(unittest.TestCase):
    """La pluja de les veïnes de Montflorit al registre i al model (ADR 0070)."""

    def test_la_mediana_de_les_que_compten(self):
        self.assertIsNone(A.pluja_veines(None))
        self.assertIsNone(A.pluja_veines({"ICERDA48": 3.0}))                 # no compta per a «plou ara»
        self.assertEqual(A.pluja_veines({"ICERDA6": 0.0, "ICERDA18": 1.2, "ICERDA28": 0.4}), 0.4)
        self.assertEqual(A.pluja_veines({"ICERDA6": 0.2, "ICERDA18": None, "ICERDA28": 0.6}), 0.4)

    def test_el_rasgo_nomes_a_curt_termini(self):
        d = {"fins": "2026-10-10T12:00", "antelacio_h": 1.0, "pluja_meteofrance_arome_france_hd": 0,
             "pluja_meteofrance_arome_france": 0, "pluja_icon_eu": 0, "prob_ens": 0.1, "pluja_1h_emes": 0,
             "deficit_rosada_ara": 2, "pluja_1h_veines": 1.0}
        noms = A.RASGOS_PROPIS_VEINES
        x = A.rasgos(d, noms)
        self.assertAlmostEqual(x[noms.index("veines")], math.log1p(1.0))
        self.assertIsNone(A.rasgos({**d, "pluja_1h_veines": None}, noms))      # sense dada, no hi ha vector
        self.assertEqual(A.rasgos({**d, "antelacio_h": 12}, noms)[noms.index("veines")], 0.0)


class Diari(unittest.TestCase):
    """Registro sintético: el modelo da siempre dos grados más de lo que mide
    la estación de casa."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        A.REGISTRE = os.path.join(self.dir, "registre")
        A.DIR = os.path.join(self.dir, "aprenentatge")
        A.MODEL, A.PROPOSAT = os.path.join(A.DIR, "model.json"), os.path.join(A.DIR, "proposat.json")
        A.ATURA, A.HISTORIAL = os.path.join(A.DIR, "atura"), os.path.join(A.DIR, "historial.csv")
        A.HISTORIAL_HUMITAT = os.path.join(A.DIR, "historial-humitat.csv")
        A.AVIS_XV = os.path.join(A.DIR, "avis-sant-cugat")
        A.SORTIR, A.AVIS_SORTIR = os.path.join(A.REGISTRE, "sortir.csv"), os.path.join(A.DIR, "avis-sortir")
        A.MOTO_VELL = os.path.join(A.REGISTRE, "moto.csv")
        A.LLINDARS_SORTIR = os.path.join(A.DIR, "llindars-sortir.json")
        A.PROPOSTA_SORTIR = os.path.join(A.DIR, "llindars-sortir-proposta.json")
        os.makedirs(A.REGISTRE)

    def registra(self, dias, error=2.0, com_arxiu=False):
        """com_arxiu: la estación mide justo lo que da la corrección del
        archivo, que entonces no se puede mejorar."""
        rnd = random.Random(1)
        mont = ["fins,pluja_mm"]
        casa = ["fins,pluja_mm,temperatura,humitat,rosada,pressio,solar"]
        arxiu_t = {"temperatura": A.modelo_arxiu_temperatura()}
        inici = dt.datetime(2026, 9, 1)
        with open(os.path.join(A.REGISTRE, "casa-2026-09.jsonl"), "w") as f:
            for k in range(dias * 24):
                t = inici + dt.timedelta(hours=k)
                real = 15 + 8 * rnd.random()
                fins = (t + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
                h = hora(fins, temp=round(real + error, 1), antelacio=1, error_ara=error)
                if com_arxiu:
                    real = A.temperatura(arxiu_t, h)
                mont.append(f"{fins},0.0")
                casa.append(f"{fins},0.0,{real:.3f},80,15,1013,0")
                linea = {"emes": t.strftime("%Y-%m-%dT%H:%M") + "+02:00",
                         "ara_casa": {"pluja_1h": 0}, "hores": [h], "sant_cugat": {"pluja_1h": 0.0} if k % 2 else None}
                f.write(json.dumps(linea) + "\n")
        for nom, filas in (("meteocat-XV.csv", mont), ("estacio-casa.csv", casa)):
            with open(os.path.join(A.REGISTRE, nom), "w") as f:
                f.write("\n".join(filas) + "\n")

    def test_horas_de_lluvia_unicas_y_avance_temporal(self):
        # Auditoría del 08-10-2026: dos horas con lluvia previstas 24 veces contaban 48.
        # ADR 0106: cada día se evalúa con el modelo de los días anteriores (7 como mínimo).
        ms = []
        for dia in range(1, 11):
            d = dt.datetime(2026, 9, dia, 18)
            for k in range(24):
                for plou in (True, False):
                    fins = d + dt.timedelta(hours=0 if plou else 1)
                    ms.append({**hora(fins.isoformat(timespec="minutes"), mm=2 if plou else 0, antelacio=k + 1),
                               "emes": (fins - dt.timedelta(hours=k + 1)).isoformat(timespec="minutes") + "+02:00",
                               "obs_pluja": 2 if (plou and dia in (3, 8)) else 0, "obs_temp": None, "pluja_1h_emes": 0})
        v = A.valida_pluja(ms, A.modelo_arxiu())
        self.assertEqual(v["hores_pluja"], 2)
        self.assertEqual(v["mostres"], 480)
        # Se evalúan los días 8, 9 y 10 (los siete primeros solo entrenan); con lluvia, el 8.
        self.assertEqual((v["dies_avaluats"], v["avaluades"], v["hores_pluja_avaluades"]), (3, 144, 1))
        # Con menos de ocho días no se evalúa nada.
        self.assertIsNone(A.valida_pluja([m for m in ms if m["fins"] < "2026-09-08"], A.modelo_arxiu()))

    def test_sant_cugat_entra_en_las_muestras_y_se_valida_aparte(self):
        self.registra(20)
        ms = A.mostres()
        self.assertEqual({m["pluja_1h_xv"] for m in ms}, {0.0, None})
        vp = A.valida_pluja(ms, A.modelo_arxiu(), A.RASGOS_PROPIS_XV)
        self.assertEqual(vp["rasgos"], A.RASGOS_PROPIS_XV)
        self.assertEqual(vp["mostres"], len([m for m in ms if m["pluja_1h_xv"] is not None]))
        # El aviso de una vez: solo con bastante lluvia, y deja huella para no repetirse.
        self.assertIsNone(A.avis_sant_cugat({"error": 0.1, "error_abans": 0.12, "xv": {**vp, "hores_pluja": 5}}))
        text = A.avis_sant_cugat({"error": 0.1, "error_abans": 0.12, "xv": {**vp, "hores_pluja": 30, "error": 0.09, "error_base": 0.1}})
        self.assertIn("30 hores de pluja amb la dada de Sant Cugat", text)
        self.assertIn("Ajuda", text)
        self.assertTrue(os.path.exists(A.AVIS_XV))
        self.assertIsNone(A.avis_sant_cugat({"error": 0.1, "error_abans": 0.12, "xv": {**vp, "hores_pluja": 30, "error": 0.09, "error_base": 0.1}}))
        os.remove(A.AVIS_XV)
        self.assertIn("No ajuda", A.avis_sant_cugat({"error": 0.1, "error_abans": 0.12, "xv": {**vp, "hores_pluja": 30, "error": 0.11, "error_base": 0.1}}))

    def test_variant_i_base_amb_les_mateixes_mostres(self):
        # Auditoría del 09-10-2026: la variante de Sant Cugat se comparaba con
        # el base medido en todas las horas, aunque ella solo tuviera la mitad.
        ms = []
        for dia in range(20):
            for k in range(12):
                fins = dt.datetime(2026, 9, 1 + dia, 6) + dt.timedelta(hours=k)
                plou = k % 4 == 0
                ms.append({**hora(fins.isoformat(timespec="minutes"), mm=2.0 if plou else 0.0, antelacio=1),
                           "emes": (fins - dt.timedelta(hours=1)).isoformat(timespec="minutes") + "+02:00",
                           "obs_pluja": 1.0 if plou else 0.0, "pluja_1h_emes": 0.0,
                           "pluja_1h_xv": (1.0 if plou else 0.0) if dia % 2 else None})
        arxiu = A.modelo_arxiu()
        base, xv = A.valida_pluja(ms, arxiu), A.valida_variant(ms, arxiu, A.RASGOS_PROPIS_XV)
        self.assertEqual(base["mostres"], len(ms))
        self.assertEqual((xv["mostres"], xv["mostres_base"]), (len(ms) // 2, len(ms) // 2))
        self.assertIsNotNone(xv["error_base"])
        self.assertEqual(len(xv["_errors"]), xv["avaluades"])

    def test_el_competidor_es_el_que_publica_la_web(self):
        # Evaluación del 18-10-2026 (ADR 0104): el candidato se comparaba con los
        # coeficientes de tres modelos, y la web publica con ECMWF cuando la pasada lo tiene.
        ms = []
        for dia in range(12):
            for k in range(12):
                fins = dt.datetime(2026, 9, 1 + dia, 6) + dt.timedelta(hours=k)
                plou = k % 4 == 0
                m = {**hora(fins.isoformat(timespec="minutes"), mm=2.0 if plou else 0.0, antelacio=1),
                     "emes": (fins - dt.timedelta(hours=1)).isoformat(timespec="minutes") + "+02:00",
                     "obs_pluja": 1.0 if plou else 0.0, "pluja_1h_emes": 0.0}
                if k % 2:
                    m[f"pluja_{C.MODEL_ECMWF}"] = 1.5 if plou else 0.0
                ms.append(m)
        arxiu = A.modelo_arxiu()
        v = A.valida_pluja(ms, arxiu)
        # El competidor se mide en las mismas muestras evaluadas (los días 8 a 12).
        avaluades = [m for m in ms if m["fins"] >= "2026-09-08"]
        self.assertEqual(v["avaluades"], len(avaluades))
        y = np.array([m["obs_pluja"] >= C.UMBRAL_MM for m in avaluades], dtype=float)
        publicat = np.array([A.prob_pluja({"pluja": arxiu}, m) for m in avaluades])
        tres = np.array([A.predecir(np.array(arxiu["w"]), np.array(A.rasgos(m, arxiu["rasgos"]))) for m in avaluades])
        self.assertAlmostEqual(v["error_abans"], float(np.mean((publicat - y) ** 2)))
        self.assertNotAlmostEqual(v["error_abans"], float(np.mean((tres - y) ** 2)))
        self.assertIn("seguretat", v)
        self.assertEqual(len(v["_errors"]), len(avaluades))

    def test_la_variant_nomes_guanya_si_millora_el_base_a_les_seves_hores(self):
        from unittest.mock import patch
        arxiu = A.modelo_arxiu()
        base = {"mostres": 100, "hores_pluja": 40, "rasgos": A.RASGOS_PROPIS, "error": 0.10, "error_abans": 0.12,
                "seguretat": 0.99, "w": [0.0]}
        # Guanya l'arxiu, però no el base a les seves hores amb seguretat: no entra (ADR 0105).
        xv = {**base, "rasgos": A.RASGOS_PROPIS_XV, "mostres": 50, "error": 0.09, "error_base": 0.095,
              "mostres_base": 50, "seguretat_base": 0.8}
        ms = [{"emes": "2026-09-01T00:00+02:00"}]
        with patch.object(A, "valida_pluja", return_value=dict(base)), patch.object(A, "valida_temperatura", return_value=None), \
             patch.object(A, "valida_variant", side_effect=[xv, None, None]):
            model, vp, _ = A.candidat(ms, arxiu, None, "2026-10-09")
        self.assertEqual(model["pluja"]["rasgos"], A.RASGOS_PROPIS)
        # Si guanya el base en el 95 % dels remostrejos, sí.
        with patch.object(A, "valida_pluja", return_value=dict(base)), patch.object(A, "valida_temperatura", return_value=None), \
             patch.object(A, "valida_variant", side_effect=[{**xv, "seguretat_base": 0.96}, None, None]):
            model, vp, _ = A.candidat(ms, arxiu, None, "2026-10-09")
        self.assertEqual(model["pluja"]["rasgos"], A.RASGOS_PROPIS_XV)
        self.assertEqual(model["pluja"]["seguretat_base"], 0.96)
        self.assertEqual(model["pluja"]["error_base"], 0.095)
        # I el base sol, si no guanya l'arxiu amb seguretat, tampoc.
        with patch.object(A, "valida_pluja", return_value={**base, "seguretat": 0.9}), \
             patch.object(A, "valida_temperatura", return_value=None), \
             patch.object(A, "valida_variant", return_value=None):
            model, vp, _ = A.candidat(ms, arxiu, None, "2026-10-09")
        self.assertEqual(model["pluja"]["origen"], "arxiu")

    def test_verifica_tots_els_mitjans_un_cop_per_hora(self):
        # Cada hora, previsions d'1 a 9 hores abans; plou de 12 a 13 h i a les
        # 15 h bufa a 60 km/h; la temperatura és sempre de 18 °C.
        mont = ["fins,pluja_mm,temperatura,humitat,rosada,pressio,solar"]
        vent = ["fins,XV,XV_ratxa"]
        with open(os.path.join(A.REGISTRE, "casa-2026-10.jsonl"), "w") as f:
            for k in range(30):
                emes = dt.datetime(2026, 10, 8, 0) + dt.timedelta(hours=k)
                hores = []
                for ant in range(1, 10):
                    fins = (emes + dt.timedelta(hours=ant)).strftime("%Y-%m-%dT%H:%M")
                    hores.append({**hora(fins, antelacio=ant - 0.05), "avis_pluja": 1.0 if ant > 5 else 0.0,
                                  "mostrat": {"probabilitat": 0.15, "pluja_mm": 0.0, "temperatura": 18,
                                              "ratxa": 45 if fins.endswith("15:00") else 20}})
                f.write(json.dumps({"emes": emes.strftime("%Y-%m-%dT%H:%M") + "+02:00", "hores": hores}) + "\n")
                fins = (emes + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
                mont.append(f"{fins},{1.5 if fins.endswith('13:00') else 0.0},18,80,15,1013,0")
                mig = (emes + dt.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
                ratxa = 60 if fins.endswith("15:00") else 10
                vent += [f"{mig},5,{ratxa}", f"{fins},5,{ratxa}"]
        with open(os.path.join(A.REGISTRE, "estacio-casa.csv"), "w") as f:
            f.write("\n".join(mont) + "\n")
        with open(os.path.join(A.REGISTRE, "vent-mitges-hores.csv"), "w") as f:
            f.write("\n".join(vent) + "\n")
        # Les hores seques només compten si Meteocat tampoc no va recollir res (ADR 0058).
        with open(os.path.join(A.REGISTRE, "meteocat-XF.csv"), "w") as f:
            f.write("fins,pluja_mm\n" + "".join(f"{l.split(',')[0]},0.0\n" for l in mont[1:]))
        # El registre d'abans, només de la moto, se substitueix.
        open(A.MOTO_VELL, "w").close()
        ara = dt.datetime(2026, 10, 9, 0).astimezone()
        n = A.verifica_sortir(ara)
        self.assertEqual(n, 16 + 16)               # de 7 a 22 h, al sortir i la tornada
        self.assertFalse(os.path.exists(A.MOTO_VELL))
        self.assertEqual(A.verifica_sortir(ara), 0)  # no es repeteix
        r = A.resum_sortir()
        moto = r["mitjans"]["moto"]
        # Amb un 15 % i sense l'avís (al sortir), «compte»: 16 hores, va ploure en una.
        self.assertEqual(moto["pluja"]["sortida"]["compte"], [16, 1])
        self.assertEqual(moto["pluja"]["sortida"]["abans"]["be"], [16, 1])
        # La tornada porta l'avís: abans era «no» cada hora, ara «compte».
        self.assertEqual(moto["pluja"]["tornada"]["abans"]["no"], [16, 1])
        self.assertEqual(moto["pluja"]["tornada"]["no"], [0, 0])
        # El vent: la bici va avisar a les 15 h (45 km/h, «compte») i en va fer 60.
        self.assertEqual(r["mitjans"]["bici"]["vent"]["sortida"]["compte"], [1, 1])
        self.assertEqual(r["mitjans"]["moto"]["vent"]["sortida"]["be"], [16, 1])   # 45 < 50: no va avisar
        self.assertIn("vent", r["mitjans"]["cotxe"])               # 90 km/h: «compte»
        self.assertIn("fred", r["mitjans"]["moto"])
        self.assertNotIn("fred", r["mitjans"]["peu"])           # a peu no hi ha regla de fred
        # A peu, el paraigua des del 15 % per sortir aviat (ADR 0069): amb un 15 %, «compte».
        self.assertEqual(r["mitjans"]["peu"]["pluja"]["sortida"]["compte"], [16, 1])
        text = A.text_resum_sortir(r)
        self.assertIn("Bici o patinet, ratxes:", text)
        self.assertIn("Encara hi ha massa poca pluja", text)
        # El resum per Telegram, només amb prou dies i una sola vegada.
        self.assertIsNone(A.avis_sortir(avisa=False))
        A.DIES_RESUM_SORTIR = 1
        try:
            self.assertIn("Si surts, comprovació de tots els mitjans", A.avis_sortir(avisa=False))
            self.assertIsNone(A.avis_sortir(avisa=False))
        finally:
            A.DIES_RESUM_SORTIR = 28

    def test_els_llindars_de_pluja_s_aprenen(self):
        # ADR 0069: «millor no», que plogui almenys 2 de cada 3 vegades; «bé», com a molt 1 de cada 100.
        rnd = random.Random(3)
        mostres = []
        for _ in range(20000):
            p = rnd.choice([0.003] * 40 + [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9])
            mostres.append((p, rnd.random() < p))      # probabilitat ben calibrada
        ll = A.apren_llindars(mostres)
        # El llindar més baix amb què, per sobre, plou almenys 2 de cada 3 vegades
        # (aquí, les hores del 50, 70 i 90 %); amb el 30 % també a dins, no.
        self.assertEqual(ll["pluja"], 0.35)
        dins = [y for q, y in mostres if q >= ll["pluja"]]
        self.assertGreaterEqual(sum(dins) / len(dins), 2 / 3)
        self.assertLessEqual(ll["risc"], 0.15)           # per sota, l'1 %, i cap franja amb «bé» per sobre d'1 de cada 10
        self.assertIsNone(A.apren_llindars(mostres[:50]))  # sense prou pluja, res
        # Com a l'arxiu de casa: del 10 al 15 % plou el 14 %; tot i que per sota
        # del 15 % el conjunt queda per sota de l'1 %, aquesta franja no pot ser «bé».
        casa = ([(0.01, k < 40) for k in range(8000)] + [(0.07, k < 5) for k in range(100)]
                + [(0.12, k < 21) for k in range(150)] + [(0.5, k < 70) for k in range(100)])
        self.assertEqual(A.apren_llindars(casa)["risc"], 0.1)
        lo, hi = A.wilson(70, 100)
        self.assertTrue(lo < 0.7 < hi)
        # Al registre: es proposa, s'avisa i s'aplica l'endemà (si ningú no ho atura).
        os.makedirs(A.DIR, exist_ok=True)
        with open(A.SORTIR, "w") as f:
            f.write(",".join(A.CAMPS_SORTIR) + "\n")
            for p, y in mostres[:6000]:
                f.write(f"2026-10-09T12:00,sortida,x,2,{p},0,0,0,10,15,{1.0 if y else 0.0},10,15\n")
        self.assertEqual(A.llindars_sortir(), C.SORTIR_LLINDARS_PLUJA)
        text = A.aprén_sortir("2026-10-20", avisa=False)
        self.assertIn("canvi proposat", text)
        self.assertEqual(A.llindars_sortir(), C.SORTIR_LLINDARS_PLUJA)            # encara no
        A.aprén_sortir("2026-10-21", avisa=False)
        ara = A.llindars_sortir()
        self.assertNotEqual(ara["curt"], C.SORTIR_LLINDARS_PLUJA["curt"])
        self.assertEqual(ara["llarg"], C.SORTIR_LLINDARS_PLUJA["llarg"])          # sense dades de la tornada
        self.assertIsNone(A.aprén_sortir("2026-10-22", avisa=False))               # ja hi és: res a proposar

    def test_propone_avisa_y_aplica_al_dia_siguiente(self):
        self.registra(20)
        A.diari("2026-09-21", avisa=False)
        self.assertTrue(os.path.exists(A.PROPOSAT))
        self.assertEqual(A.carrega()["temperatura"]["origen"], "arxiu")      # aún no se aplica
        A.diari("2026-09-22", avisa=False)
        m = A.carrega()
        self.assertEqual(m["temperatura"]["origen"], "casa")
        self.assertAlmostEqual(A.temperatura(m, hora("2026-09-10T12:00", temp=22.0, antelacio=1, error_ara=2.0)),
                               20.0, delta=0.3)
        # La lluvia sigue con el archivo: no hay horas de lluvia propias.
        self.assertEqual(m["pluja"]["origen"], "arxiu")

    def test_atura(self):
        self.registra(20)
        A.diari("2026-09-21", avisa=False)
        os.makedirs(A.DIR, exist_ok=True)
        open(A.ATURA, "w").close()
        A.diari("2026-09-22", avisa=False)
        self.assertEqual(A.carrega()["temperatura"]["origen"], "arxiu")

    def test_pocos_dias_o_sin_mejora_no_cambia(self):
        self.registra(5)
        A.diari("2026-09-06", avisa=False)
        self.assertFalse(os.path.exists(A.PROPOSAT))
        self.registra(20, com_arxiu=True)
        A.diari("2026-09-21", avisa=False)
        self.assertFalse(os.path.exists(A.PROPOSAT))


if __name__ == "__main__":
    unittest.main()


class PrimersDies(unittest.TestCase):
    """Abans de poder avaluar res (calen 7 dies d'entrenament), es diuen els dies que ja hi ha (Juanjo,
    23-10-2026: «por qué la humedad no tiene ningún día?»; «Fiabilitat» deia «en porta 0» amb tres)."""

    def test_humitat_i_temperatura_amb_tres_dies(self):
        from unittest.mock import patch
        ms = [{"fins": f"2026-10-{d}T{h:02d}:00", "emes": f"2026-10-{d}T{h:02d}:00", "obs_rosada": 10.0, "obs_temp": 15.0,
               "temperature_2m": 15.0} for d in (21, 22, 23) for h in range(0, 24, 3)]
        with patch.object(A, "rasgos", side_effect=lambda m, noms: [1.0] * len(noms)), \
                patch.object(A, "rosada_model", return_value=10.5):
            vh = A.valida_humitat(ms, None)
            vt = A.valida_temperatura(ms, None)
        for v in (vh, vt):
            self.assertEqual((v["dies"], v["avaluades"], v["error"], v["seguretat"]), (3, 0, None, None))
            self.assertFalse(A.millora(v))
