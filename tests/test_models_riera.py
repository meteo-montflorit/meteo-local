# SPDX-License-Identifier: AGPL-3.0-or-later
"""Més proves de la riera de Sant Cugat (riera.py, ADR 0027 i 0107): les
estacions particulars, el registre del NAS, l'avís i la previsió quan alguna
cosa falla, i les ordres. Sense xarxa ni Telegram."""
import contextlib
import csv
import datetime as dt
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import prevision as P  # noqa: E402
import riera as RI  # noqa: E402
import wunderground as W  # noqa: E402

UTC = dt.timezone.utc
ARA = dt.datetime(2026, 10, 18, 14, 0).astimezone()


def obs(t, acumulada):
    return {"obsTimeUtc": t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "metric": {"precipTotal": acumulada}}


class AmbCarpetes(unittest.TestCase):
    """Totes les rutes del NAS dins d'una carpeta temporal."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        d = self.dir.name
        reg = os.path.join(d, "registre")
        rutes = {"DIR": reg, "ESTAT_DIR": d, "ESTADO": os.path.join(d, "riera.json"),
                 "REGISTRO": os.path.join(reg, "riera.csv"), "COMPTADOR_WU": os.path.join(d, "riera-wu.json"),
                 "CACHE_WU": os.path.join(d, "riera-wu-ahir"), "REGISTRE_WU": os.path.join(reg, "riera-veines.csv"),
                 "ESTAT_PREVISIO": os.path.join(d, "riera-previsio.json"),
                 "REGISTRE_PREVISIO": os.path.join(reg, "riera-previsio.csv"),
                 "PREGUNTES": os.path.join(reg, "p.csv"), "CONFIRMACIONS": os.path.join(reg, "c.csv")}
        for nom, valor in rutes.items():
            p = mock.patch.object(RI, nom, valor)
            p.start()
            self.addCleanup(p.stop)


class Consulta(AmbCarpetes):
    def test_compta_encara_que_no_pugui_desar_el_comptador(self):
        crides = []
        with mock.patch.object(RI, "COMPTADOR_WU", os.path.join(self.dir.name, "no-hi-es", "c.json")):
            c = RI.Consulta(ARA, lambda ruta, params: crides.append(ruta) or [])
            self.assertEqual(c("observations/all/1day", {}), [])
            self.assertEqual(c("observations/all/1day", {}), [])
        self.assertEqual((c.n, len(crides)), (2, 2))

    def test_el_comptador_d_un_altre_dia_no_compta(self):
        with open(RI.COMPTADOR_WU, "w", encoding="utf-8") as f:
            json.dump({"dia": "2026-10-17", "n": 499}, f)
        self.assertEqual(RI.Consulta(ARA, lambda r, p: []).n, 0)
        with open(RI.COMPTADOR_WU, "w", encoding="utf-8") as f:
            json.dump({"dia": ARA.date().isoformat(), "n": 7}, f)
        self.assertEqual(RI.Consulta(ARA, lambda r, p: []).n, 7)


class SerieVeina(AmbCarpetes):
    """Poc després de mitjanit, les 6 hores necessiten el dia d'ahir, que es
    baixa un cop i es guarda."""

    def setUp(self):
        super().setUp()
        self.ara = dt.datetime(2026, 10, 18, 2, 0).astimezone()
        mitjanit = self.ara.replace(hour=0)
        self.avui = [obs(mitjanit, 0.0), obs(mitjanit + dt.timedelta(hours=1), 2.0), obs(self.ara, 5.0)]
        ahir = self.ara - dt.timedelta(hours=3)
        self.ahir = [obs(ahir, 10.0), obs(ahir + dt.timedelta(minutes=30), 14.0)]
        self.crides = []

    def consulta(self, ruta, params):
        self.crides.append((ruta, params))
        return self.ahir if ruta == "history/all" else self.avui

    def test_baixa_ahir_un_cop_i_el_guarda(self):
        os.makedirs(RI.CACHE_WU)
        vell = os.path.join(RI.CACHE_WU, "ISANTC157-20261001.json")
        with open(vell, "w", encoding="utf-8") as f:
            f.write("[]")
        c = RI.Consulta(self.ara, self.consulta)
        s = RI.serie_veina("ISANTC157", self.ara, c)
        self.assertEqual([r for r, _ in self.crides], ["observations/all/1day", "history/all"])
        self.assertEqual(self.crides[1][1], {"stationId": "ISANTC157", "date": "20261017"})
        # La primera d'ahir compta sencera; la segona, l'increment; avui torna a zero.
        self.assertEqual([mm for _, mm in s], [10.0, 4.0, 0.0, 2.0, 3.0])
        self.assertFalse(os.path.exists(vell))         # els dies vells s'esborren
        self.assertTrue(os.path.exists(os.path.join(RI.CACHE_WU, "ISANTC157-20261017.json")))
        # La passada següent fa servir el que s'ha guardat.
        self.crides.clear()
        self.assertEqual(RI.serie_veina("ISANTC157", self.ara, c), s)
        self.assertEqual([r for r, _ in self.crides], ["observations/all/1day"])

    def test_sense_poder_guardar_ahir_continua(self):
        with open(RI.CACHE_WU, "w", encoding="utf-8") as f:
            f.write("és un fitxer, no una carpeta")
        s = RI.serie_veina("ISANTC157", self.ara, RI.Consulta(self.ara, self.consulta))
        self.assertEqual(len(s), 5)

    def test_amb_prou_dades_d_avui_no_baixa_ahir(self):
        tard = self.ara.replace(hour=9)
        RI.serie_veina("ISANTC157", tard, RI.Consulta(tard, self.consulta))
        self.assertEqual([r for r, _ in self.crides], ["observations/all/1day"])


class QuanCalMirarLesEstacions(AmbCarpetes):
    def test_episodi_obert(self):
        sec = {"mm_3h": 0.0}
        self.assertFalse(RI.cal_veines(sec, None, ARA, pluja_barri=0.2))
        self.assertTrue(RI.cal_veines(sec, None, ARA, pluja_barri=C.RIERA_VEINES_BARRI_MM))
        # El radar veu pluja sobre la conca en l'hora que ve (2 mm/h: 2 mm): sí.
        nc = {"hora": ARA.isoformat(timespec="minutes"),
              "llocs": {"conca": [{"min": m, "mm_h": 2.0, "prob": 1.0} for m in range(0, 121, 5)]}}
        self.assertTrue(RI.cal_veines(sec, nc, ARA))
        self.assertFalse(RI.cal_veines(sec, {**nc, "llocs": {"conca": [{"min": 0, "mm_h": 0.0, "prob": 0.0}]}}, ARA))
        RI.desa_estat({"episodi": {"inici": "x"}})
        self.assertEqual(RI.llegeix_estat(), {"episodi": {"inici": "x"}})
        self.assertTrue(RI.cal_veines(sec, None, ARA))
        self.assertTrue(RI.cal_veines(None, None, ARA))
        self.assertTrue(RI.cal_veines({"mm_3h": 1.0}, None, ARA))

    def test_estat_illegible(self):
        with open(RI.ESTADO, "w", encoding="utf-8") as f:
            f.write("{trencat")
        self.assertEqual(RI.llegeix_estat(), {"episodi": None})


class CalculaAmbFallades(AmbCarpetes):
    def xv(self, mm=4.0):
        fins = ARA - dt.timedelta(minutes=30)
        return [(fins - dt.timedelta(minutes=30 * (k + 1)), mm) for k in reversed(range(6))]

    def test_si_les_estacions_fallen_queda_meteocat(self):
        filas = self.xv()
        with mock.patch.object(P, "taula_meteocat",
                               lambda codi, dia=None, lector=None: [x for x in filas if x[0].date() == dia]
                               if codi == C.RIERA_ESTACIO else []), \
                mock.patch.object(RI, "calcula_veines", side_effect=RuntimeError("WU caigut")):
            r = RI.calcula(ARA, None, consulta=lambda ruta, params: [])
        self.assertEqual((r["font"], r["veines"], r["mm_3h"]), ("meteocat", None, 24.0))   # 6 mitges hores de 4 mm

    def test_si_res_respon_no_hi_ha_riera(self):
        with mock.patch.object(P, "taula_meteocat", lambda codi, dia=None, lector=None: []), \
                mock.patch.object(RI, "calcula_veines", return_value=None):
            self.assertIsNone(RI.calcula(ARA, None, consulta=lambda ruta, params: []))

    def test_sense_clau_de_wu_no_es_consulta(self):
        filas = self.xv()
        with mock.patch.object(P, "taula_meteocat",
                               lambda codi, dia=None, lector=None: [x for x in filas if x[0].date() == dia]
                               if codi == C.RIERA_ESTACIO else []), \
                mock.patch.object(W, "lectura_disponible", return_value=False), \
                mock.patch.object(RI, "calcula_veines") as cv:
            r = RI.calcula(ARA, None)
        cv.assert_not_called()
        self.assertIsNone(r["veines"])

    def test_la_capcalera_que_falla_no_tomba_la_riera(self):
        filas = self.xv()

        def taula(codi, dia=None, lector=None):
            if codi != C.RIERA_ESTACIO:
                raise OSError("Fabra caigut")
            return [x for x in filas if x[0].date() == dia]
        with mock.patch.object(P, "taula_meteocat", taula):
            r = RI.calcula_meteocat(ARA, None)
        self.assertIsNone(r["capcalera"])
        self.assertEqual(r["mm_3h"], 24.0)


class ApuntaVeines(AmbCarpetes):
    def files(self):
        with open(RI.REGISTRE_WU, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_les_dues_fonts_al_registre(self):
        veines = {"n": 5, "mm_3h": 30.0, "mm_6h": 35.0, "index": 41.0, "nivell": "atencio"}
        RI.apunta_veines({"mm_3h": 12.0, "index": 15.0, "nivell": None, "font": "meteocat", "veines": veines}, ARA)
        RI.apunta_veines({"mm_3h": 30.0, "sense_meteocat": True, "font": "veines", "nivell": "atencio",
                          "index": 41.0, "veines": dict(veines, nivell=None)}, ARA)
        RI.apunta_veines({"mm_3h": 1.0, "veines": None}, ARA)          # sense estacions, res
        RI.apunta_veines(None, ARA)
        f1, f2 = self.files()
        self.assertEqual((f1["xv_3h"], f1["xv_index"], f1["xv_nivell"], f1["veines_nivell"]),
                         ("12.0", "15.0", "", "atencio"))
        # Sense Meteocat, la columna de Meteocat queda buida.
        self.assertEqual((f2["xv_3h"], f2["xv_index"], f2["veines_nivell"], f2["font"]), ("", "", "", "veines"))

    def test_sense_poder_escriure_no_falla(self):
        with mock.patch.object(RI, "DIR", os.path.join(RI.ESTADO, "no")), \
                mock.patch.object(RI, "REGISTRE_WU", os.path.join(RI.ESTADO, "no", "x.csv")):
            with open(RI.ESTADO, "w", encoding="utf-8") as f:
                f.write("{}")
            RI.apunta_veines({"veines": {"n": 3, "mm_3h": 1, "mm_6h": 1, "index": 1, "nivell": None}}, ARA)


class Avisa(AmbCarpetes):
    def sortida(self, riera, generat=ARA):
        ruta = os.path.join(self.dir.name, "casa.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"generat": generat.isoformat(timespec="minutes"), "riera": riera}, f)
        return ruta

    def riera(self, index):
        return {"index": index, "index_6h": index, "mm_3h": index, "mm_6h": index, "nivell": RI.nivell(index, index),
                "fins": ARA.isoformat(timespec="minutes"), "estacio": "Sant Cugat", "incomplet": False,
                "radar_1h": None, "capcalera": None, "font": "meteocat"}

    def test_dades_velles_no_avisen_ni_toquen_l_estat(self):
        ruta = self.sortida(self.riera(40.0), ARA - dt.timedelta(minutes=C.INTERVALO_CASA_MIN + 1))
        with mock.patch.object(RI, "respostes", return_value=0):
            self.assertIsNone(RI.avisa(ruta, ARA))
        self.assertFalse(os.path.exists(RI.ESTADO))

    def test_obre_avisa_i_tanca_l_episodi(self):
        err = io.StringIO()
        with mock.patch.object(RI, "respostes", side_effect=OSError("Telegram caigut")), \
                mock.patch.object(RI, "pregunta_desbordament", side_effect=OSError("sense bot")) as preg, \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(err):
            text = RI.avisa(self.sortida(self.riera(40.0)), ARA)
            self.assertIn("Riera", text)
            self.assertEqual(set(RI.llegeix_estat()["episodi"]["avisos"]), {"atencio"})
            # Tres hores després sense pluja: es tanca, s'apunta i es diu que ha passat.
            despres = ARA + dt.timedelta(hours=C.RIERA_FI_H, minutes=5)
            text = RI.avisa(self.sortida(self.riera(0.0), despres), despres)
        self.assertIn("ja no hi ha risc de desbordament", text)
        self.assertIsNone(RI.llegeix_estat()["episodi"])
        self.assertEqual(preg.call_count, 1)
        self.assertIn("Respostes del desbordament: Telegram caigut", err.getvalue())
        self.assertIn("Pregunta del desbordament: sense bot", err.getvalue())
        self.assertIn("ja no hi ha risc", out.getvalue())
        with open(RI.REGISTRO, encoding="utf-8") as f:
            (fila,) = list(csv.DictReader(f))
        self.assertEqual((fila["index_max"], fila["avis_perill"]), ("40.0", ""))
        self.assertIn("atenció " + ARA.isoformat(timespec="minutes"), RI.resum())

    def test_resum_buit(self):
        self.assertEqual(RI.resum(), "Encara no hi ha cap episodi apuntat.")


class Telegram(unittest.TestCase):
    def test_fa_servir_el_bot_dels_agents(self):
        import confirmacio as CF
        with mock.patch.object(CF, "telegram", return_value=("ok", {})) as tg:
            self.assertEqual(RI.telegram("sendMessage", text="hola"), ("ok", {}))
        tg.assert_called_once_with("sendMessage", CF.CONFIG_BOT, text="hola")
        self.assertEqual(RI._config_bot(), CF.CONFIG_BOT)


class PrevisioAmbFallades(AmbCarpetes):
    ARA = dt.datetime(2026, 10, 19, 7, 40, tzinfo=dt.timezone(dt.timedelta(hours=2)))

    def resposta(self, pic=25.0, buida=False):
        hores = [(self.ARA.replace(minute=0, tzinfo=None) + dt.timedelta(hours=k)).isoformat(timespec="minutes")
                 for k in range(-7, 41)]
        serie = [None if buida else 0.0] * len(hores)
        if not buida:
            serie[17] = pic
        return json.dumps({"hourly": {"time": hores, "precipitation_icon_eu": serie}})

    def test_sense_cap_model_amb_dades(self):
        self.assertIsNone(RI.previsio(self.ARA, get=lambda url: self.resposta(buida=True)))
        self.assertFalse(os.path.exists(RI.REGISTRE_PREVISIO))

    def test_sant_cugat_caigut_no_tomba_la_previsio(self):
        with mock.patch.object(RI, "files", side_effect=OSError("Meteocat caigut")):
            p = RI.previsio(self.ARA, get=lambda url: self.resposta())
        self.assertEqual((p["nivell"], p["xv_24h"], p["xv_fins"]), ("possible", None, None))

    def test_amb_la_pluja_de_sant_cugat(self):
        fins = self.ARA.replace(minute=0)
        filas = [(fins - dt.timedelta(minutes=30 * (k + 1)), 1.5) for k in reversed(range(4))]
        with mock.patch.object(RI, "files", return_value=filas):
            p = RI.previsio(self.ARA, get=lambda url: self.resposta())
        self.assertEqual(p["xv_24h"], 6.0)
        self.assertEqual(p["xv_fins"], fins.isoformat(timespec="minutes"))

    def test_quan_baixa_s_oblida_l_inici(self):
        with mock.patch.object(RI, "files", return_value=[]):
            RI.previsio(self.ARA, get=lambda url: self.resposta())
            with open(RI.ESTAT_PREVISIO, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["inici"], self.ARA.isoformat(timespec="minutes"))
            p = RI.previsio(self.ARA + dt.timedelta(minutes=15), get=lambda url: self.resposta(pic=3.0))
        self.assertIsNone(p["nivell"])
        self.assertNotIn("inici", p)
        with open(RI.ESTAT_PREVISIO, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {})

    def test_sense_poder_desar_continua(self):
        # La carpeta d'estat és un fitxer: ni l'estat ni el registre es poden escriure, però hi ha previsió.
        fitxer = os.path.join(self.dir.name, "fitxer")
        with open(fitxer, "w", encoding="utf-8") as f:
            f.write("x")
        with mock.patch.object(RI, "ESTAT_DIR", fitxer), \
                mock.patch.object(RI, "ESTAT_PREVISIO", os.path.join(fitxer, "e.json")), \
                mock.patch.object(RI, "DIR", fitxer), \
                mock.patch.object(RI, "REGISTRE_PREVISIO", os.path.join(fitxer, "r.csv")), \
                mock.patch.object(RI, "files", return_value=[]):
            p = RI.previsio(self.ARA, get=lambda url: self.resposta())
        self.assertEqual(p["nivell"], "possible")

    def test_resum_amb_el_que_va_caure(self):
        self.assertEqual(RI.resum_previsio(), "Encara no hi ha cap previsió apuntada.")
        with mock.patch.object(RI, "files", return_value=[]):
            RI.previsio(self.ARA, get=lambda url: self.resposta())
        xv = os.path.join(self.dir.name, "xv.csv")
        with open(xv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["fins", "pluja_mm"])
            w.writeheader()
            for h, mm in (("16", "5.0"), ("17", "10.5"), ("18", "7.0"), ("19", "1.0"), ("20", "malament")):
                w.writerow({"fins": f"2026-10-19T{h}:00+02:00", "pluja_mm": mm})
        text = RI.resum_previsio(registre_xv=xv)
        # El màxim de 3 hores seguides que va caure: 5 + 10,5 + 7.
        self.assertIn("2026-10-19       25.0     22.5", text)
        self.assertIn("Dies amb 20 mm o més previstos: 1 de 1.", text)


class Ordres(unittest.TestCase):
    """python3 riera.py <ordre>, amb el registre en una carpeta temporal."""

    def executa(self, *args):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"REGISTRE_DIR": os.path.join(d, "registre")}), \
                mock.patch.object(sys, "argv", ["riera.py", *args]), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                runpy.run_path(os.path.join(ARREL, "riera.py"), run_name="__main__")
                codi = 0
            except SystemExit as ex:
                codi = ex.code
        return codi, out.getvalue()

    def test_estat_resum_i_ajuda(self):
        codi, text = self.executa("estat")
        self.assertEqual((codi, json.loads(text)), (0, {"episodi": None}))
        self.assertEqual(self.executa("resum"), (0, "Encara no hi ha cap episodi apuntat.\n"))
        self.assertEqual(self.executa("previsio-resum"), (0, "Encara no hi ha cap previsió apuntada.\n"))
        self.assertEqual(self.executa("respostes"), (0, "0\n"))
        codi, text = self.executa()
        self.assertEqual(codi, 1)
        self.assertIn("Uso:", text)


if __name__ == "__main__":
    unittest.main()
