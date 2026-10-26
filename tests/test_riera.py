# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del aviso de la riera de Sant Cugat (sin red ni Telegram)."""
import csv
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C  # noqa: E402
import montflorit as M  # noqa: E402
import riera as RI  # noqa: E402

UTC = dt.timezone.utc
# Lluvia de Sant Cugat (Meteocat XV) el 04-10-2026, por medias horas que
# empiezan a la hora UTC indicada: la del desbordamiento de la 1-2 en Montflorit.
EPISODI = [(19, 30, 8.0), (20, 0, 4.6), (20, 30, 4.9), (21, 0, 8.7), (21, 30, 9.1),
           (22, 0, 8.9), (22, 30, 4.5), (23, 0, 10.0), (23, 30, 19.6)]


def files_xv(fins_utc):
    """Las medias horas del episodio publicadas hasta fins_utc (03-10 y 04-10 UTC)."""
    res = []
    for h, m, mm in EPISODI:
        t = dt.datetime(2026, 10, 3, h, m, tzinfo=UTC)
        if t + RI.MITJA_HORA <= fins_utc:
            res.append((t, mm))
    return res


def nowcast(hora, mm_h):
    """Radar con la misma lluvia sobre la cuenca durante 2 horas."""
    return {"hora": hora.isoformat(timespec="minutes"),
            "llocs": {"conca": [{"min": m, "mm_h": mm_h, "prob": 1.0 if mm_h else 0.0}
                                for m in range(0, 121, 5)]}}


class Index(unittest.TestCase):
    def test_acumulat_nomes_mitges_hores_senceres(self):
        fins = dt.datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
        filas = files_xv(fins)
        self.assertEqual(RI.acumulat(filas, fins, 3), 60.8)   # 21:00-24:00 UTC
        self.assertEqual(RI.acumulat(filas, fins, 1), 29.6)

    def test_index_sense_radar_es_el_mesurat(self):
        fins = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        ara = fins + dt.timedelta(minutes=30)
        r = self.calcula(ara, fins, None)
        self.assertEqual(r["mm_3h"], 40.7)
        self.assertEqual(r["mm_1h"], 13.4)       # 22:00-23:00 UTC, per al registre (ADR 0042)
        self.assertEqual(r["index"], 40.7)
        self.assertEqual(r["index_6h"], 48.7)
        self.assertEqual(r["nivell"], "atencio")
        self.assertIsNone(r["radar_1h"])

    def test_el_radar_avanca_el_perill(self):
        # Con 40,7 mm medidos y el radar viendo 20 mm/h en la cuenca, la
        # lluvia de 3 horas pasará de 50 en la hora siguiente.
        fins = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        ara = fins + dt.timedelta(minutes=30)
        r = self.calcula(ara, fins, nowcast(ara - dt.timedelta(minutes=15), 20))
        self.assertEqual(r["nivell"], "perill")
        self.assertGreaterEqual(r["index"], C.RIERA_PERILL_MM)
        self.assertGreaterEqual(r["index_6h"], C.RIERA_PERILL_6H_MM)
        self.assertEqual(r["index_d_aqui_a_min"], 60)

    def test_perill_nomes_amb_3_i_6_hores_del_mateix_moment(self):
        # Auditoria del 09-10-2026: el màxim de 3 hores (ara: 50 mm sobre sòl sec)
        # i el de 6 (d'aquí a una hora: 60) eren de moments diferents i donaven
        # perill, i en cap moment es complien les dues condicions.
        from unittest.mock import patch
        ara = dt.datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
        files = lambda pluja: [(ara - RI.MITJA_HORA * (12 - i), mm) for i, mm in enumerate(pluja)]
        with patch.object(RI, "files", return_value=files([0] * 6 + [20, 0, 0, 0, 15, 15])):
            r = RI.calcula(ara, nowcast(ara, 10))
        self.assertEqual((r["nivell"], r["index"], r["index_6h"], r["index_d_aqui_a_min"]), ("atencio", 50.0, 50.0, 0))
        # Amb 10 mm més abans del xàfec, les dues condicions es donen alhora: perill.
        with patch.object(RI, "files", return_value=files([0, 0, 0, 0, 10, 0, 20, 0, 0, 0, 15, 15])):
            r = RI.calcula(ara, nowcast(ara, 10))
        self.assertEqual((r["nivell"], r["index"], r["index_6h"]), ("perill", 50.0, 60.0))

    def test_l_hora_seguent_es_compta_des_d_ara(self):
        # Auditoria del 08-10-2026: amb l'estació mitja hora endarrerida, un xàfec
        # de 37,5 mm entre d'aquí a 35 i 60 minuts quedava fora de l'«hora següent».
        from unittest.mock import patch
        ara = dt.datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
        fins = ara - dt.timedelta(minutes=30)
        filas = [(fins - RI.MITJA_HORA * (12 - i), 0.0) for i in range(12)]
        nc = {"hora": (ara - dt.timedelta(minutes=15)).isoformat(timespec="minutes"),
              "llocs": {"conca": [{"min": k, "mm_h": 90 if 50 <= k < 75 else 0, "prob": 1 if 50 <= k < 75 else 0}
                                  for k in range(0, 125, 5)]}}
        with patch.object(RI, "files", return_value=filas):
            r = RI.calcula(ara, nc)
        self.assertEqual(r["index"], 37.5)
        self.assertEqual(r["nivell"], "atencio")
        self.assertEqual(r["index_d_aqui_a_min"], 60)
        self.assertEqual(r["radar_1h"], 37.5)
        self.assertEqual(RI.horitzo(fins, ara), 90)
        self.assertIn("des de llavors fins d'aquí a una hora", RI.missatge(r, "atencio"))

    def test_forat_entre_estacio_i_radar(self):
        # Imagen 15 minutos más nueva que la estación, 12 mm/h: el hueco
        # cuenta 3 mm y la media hora siguiente, 3 más.
        desde = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        nc = nowcast(desde + dt.timedelta(minutes=15), 12)
        self.assertEqual(RI.previst(nc, desde, 15), 3.0)
        self.assertEqual(RI.previst(nc, desde, 30), 6.0)
        self.assertEqual(RI.previst(None, desde, 30), 0.0)

    def test_estacio_endarrerida(self):
        fins = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        self.assertIsNone(self.calcula(fins + dt.timedelta(hours=3), fins, None))

    def test_forats_a_l_estacio(self):
        # Auditoría del 07-10-2026: las medias horas que faltan contaban como
        # cero. Con todas, completo; sin una de las 6 de 3 h, aún; sin dos, no.
        fins = dt.datetime(2026, 10, 4, 0, 0, tzinfo=UTC)
        # La tabla de Meteocat trae todas las medias horas, con 0,0 si no llueve.
        filas = [(dt.datetime(2026, 10, 3, 18, m, tzinfo=UTC), 0.0) for m in (0, 30)] \
            + [(dt.datetime(2026, 10, 3, 19, 0, tzinfo=UTC), 0.0)] + files_xv(fins)
        self.assertEqual(RI.cobertura(filas, fins, 3), 6)
        self.assertEqual(RI.cobertura(filas, fins, 6), 12)
        self.assertFalse(RI.incomplet(filas, fins))
        sense_una = [f for f in filas if f[0].hour != 22 or f[0].minute != 0]
        self.assertFalse(RI.incomplet(sense_una, fins))
        sense_dues = [f for f in sense_una if f[0].hour != 21 or f[0].minute != 30]
        self.assertTrue(RI.incomplet(sense_dues, fins))
        # En 6 horas se admiten dos huecos; tres, no.
        sense_dues_de_6h = [f for f in filas if (f[0].hour, f[0].minute) not in ((18, 30), (19, 30))]
        self.assertFalse(RI.incomplet(sense_dues_de_6h, fins))
        sense_tres_de_6h = [f for f in sense_dues_de_6h if (f[0].hour, f[0].minute) != (20, 30)]
        self.assertTrue(RI.incomplet(sense_tres_de_6h, fins))

    def test_calcula_marca_incomplet_i_el_missatge_ho_diu(self):
        fins = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        ara = fins + dt.timedelta(minutes=30)
        import prevision as P
        original = P.taula_meteocat
        # Faltan las medias horas de las 21:30 y las 22:00: 2 huecos en 3 h.
        P.taula_meteocat = lambda codi, dia=None, lector=None: [
            f for f in files_xv(fins) if f[0].date() == dia and (f[0].hour, f[0].minute) not in ((21, 30), (22, 0))
        ] if codi == C.RIERA_ESTACIO else []
        try:
            r = RI.calcula(ara, None)
        finally:
            P.taula_meteocat = original
        self.assertTrue(r["incomplet"])
        self.assertEqual(r["mm_3h"], 22.7)      # 40,7 menos las dos medias horas que faltan (9,1 y 8,9)
        self.assertIn("li falten mesures", RI.missatge(r, "registre"))

    def test_darrera_meteocat_diu_des_de_quan_falta(self):
        # Meteocat calla des de les 23:00 UTC; tres hores després la riera no es calcula
        # i la pàgina ha de poder dir des de quan (21-10-2026).
        fins = dt.datetime(2026, 10, 3, 23, 0, tzinfo=UTC)
        ara = fins + dt.timedelta(hours=3)
        import prevision as P
        original = P.taula_meteocat
        P.taula_meteocat = lambda codi, dia=None, lector=None: [
            f for f in files_xv(fins) if f[0].date() == dia] if codi == C.RIERA_ESTACIO else []
        try:
            self.assertIsNone(RI.calcula_meteocat(ara, None))
            self.assertEqual(dt.datetime.fromisoformat(RI.darrera_meteocat(ara)), fins)
            self.assertIsNone(RI.darrera_meteocat(ara + dt.timedelta(days=2)))
        finally:
            P.taula_meteocat = original

    def test_canvi_de_dia_utc_sense_forats(self):
        # Ventana de 3 h que cruza la medianoche UTC (filas de dos días): completa.
        fins = dt.datetime(2026, 10, 4, 1, 0, tzinfo=UTC)
        filas = files_xv(dt.datetime(2026, 10, 4, 0, 0, tzinfo=UTC)) + [
            (dt.datetime(2026, 10, 4, 0, 0, tzinfo=UTC), 3.0), (dt.datetime(2026, 10, 4, 0, 30, tzinfo=UTC), 1.0)]
        self.assertEqual(RI.cobertura(filas, fins, 3), 6)
        self.assertFalse(RI.incomplet(filas, fins))
        self.assertEqual(RI.acumulat(filas, fins, 3), 47.0)   # 22:00-01:00 UTC

    def calcula(self, ara, fins, nc):
        import prevision as P
        original = P.taula_meteocat
        P.taula_meteocat = lambda codi, dia=None, lector=None: [
            f for f in files_xv(fins) if f[0].date() == dia] if codi == C.RIERA_ESTACIO else []
        try:
            return RI.calcula(ara, nc)
        finally:
            P.taula_meteocat = original


class Avisos(unittest.TestCase):
    T0 = dt.datetime(2026, 10, 3, 22, 0).astimezone()

    def riera(self, index, index_6h=None):
        index_6h = index + 20 if index_6h is None else index_6h
        return {"fins": self.T0.isoformat(timespec="minutes"), "mm_3h": index, "mm_6h": index_6h,
                "radar_1h": 4.0, "index": index, "index_6h": index_6h, "capcalera": {"mm_3h": 30.0}}

    def passades(self, indexs, cada=30, index_6h=None):
        estat, textos, files = {"episodi": None}, [], []
        for i, index in enumerate(indexs):
            ara = self.T0 + dt.timedelta(minutes=cada * i)
            text, fila = RI.compara(estat, self.riera(index, index_6h) if index is not None else None, ara)
            textos.append(text)
            if fila:
                files.append(fila)
        return textos, files, estat

    def test_un_avis_per_nivell(self):
        textos, _, _ = self.passades([10, 22, 36, 40, 52, 60, 45, 55])
        self.assertEqual([bool(t) for t in textos], [False, False, True, False, True, False, False, False])
        self.assertIn("atenció", textos[2])
        self.assertIn("perill de desbordament", textos[4])
        self.assertIn("En 3 hores, al Fabra (Collserola), 30 mm.", textos[2])
        self.assertIn("el radar en preveu uns 4,0 més", textos[2])

    def test_xafec_sobre_sol_sec_nomes_atencio(self):
        # 13-09-2025: 52 mm en 3 horas y nada antes (52 en 6); no se desbordó.
        textos, _, estat = self.passades([40, 52, 52], index_6h=52)
        self.assertEqual(sum(bool(t) for t in textos), 1)
        self.assertIn("atenció", textos[0])
        self.assertIn("S'ha desbordat amb 50 mm o més en 3 hores i 60 en 6", textos[0])
        self.assertNotIn("perill", estat["episodi"]["avisos"])

    def test_nivells(self):
        self.assertEqual(RI.nivell(53, 75), "perill")      # 29-04-2024
        self.assertEqual(RI.nivell(67, 67), "perill")      # 29-09-2026
        self.assertEqual(RI.nivell(52, 52), "atencio")     # 13-09-2025
        self.assertEqual(RI.nivell(25, 90), "registre")
        self.assertIsNone(RI.nivell(10, 70))

    def test_perill_de_cop_no_envia_tambe_atencio(self):
        textos, _, estat = self.passades([55, 60])
        self.assertEqual(sum(bool(t) for t in textos), 1)
        self.assertIn("perill", textos[0])
        self.assertEqual(set(estat["episodi"]["avisos"]), {"atencio", "perill"})

    def test_episodi_es_tanca_i_s_apunta(self):
        # 3 horas por debajo de 20 mm cierran el episodio con sus máximos.
        textos, files, estat = self.passades([25, 38, 30, 15, 10, 5, 5, 5, 5, 5])
        self.assertEqual(len(files), 1)
        f = files[0]
        self.assertEqual(f["index_max"], 38)
        self.assertTrue(f["avis_atencio"])
        self.assertEqual(f["avis_perill"], "")
        self.assertEqual(f["desbordament"], "")
        self.assertIsNone(estat["episodi"])
        # En tancar-se, un sol missatge de final (Juanjo, 08-10-2026), del nivell que es va avisar.
        self.assertEqual([t for t in textos if t][-1], "Riera de Sant Cugat: ja no hi ha risc de desbordament. A Sant Cugat fa 3 hores "
                                     "que no plou amb força (5,0 mm en les últimes 3 hores) i el radar no hi veu pluja forta. "
                                     "Si torna a ploure fort, tornarà l'avís.")
        self.assertEqual(sum(bool(t) for t in textos), 2)

    def test_el_final_diu_perill_si_n_hi_va_haver_i_res_sense_avis(self):
        textos, files, _ = self.passades([55, 60, 10, 5, 5, 5, 5, 5, 5], index_6h=70)
        self.assertTrue([t for t in textos if t][-1].startswith("Riera de Sant Cugat: ha passat el perill de desbordament."))
        self.assertEqual(len(files), 1)
        # Un episodi només de registre (20-35 mm) s'apunta sense cap missatge.
        textos, files, _ = self.passades([25, 28, 10, 5, 5, 5, 5, 5, 5])
        self.assertEqual(len(files), 1)
        self.assertEqual([t for t in textos if t], [])

    def test_sense_dades_no_canvia_res(self):
        textos, files, estat = self.passades([38, None, None])
        self.assertEqual(sum(bool(t) for t in textos), 1)
        self.assertIsNotNone(estat["episodi"])
        self.assertEqual(files, [])

    def test_amb_forats_l_episodi_no_es_tanca(self):
        # Tras el aviso, 4 horas de índice bajo pero con huecos en la estación:
        # el episodio sigue abierto; con los datos completos, se cierra.
        estat, files = {"episodi": None}, []
        for i, (index, forats) in enumerate([(38, False), (5, True), (5, True), (5, True), (5, True), (5, True),
                                             (5, True), (5, True), (5, True), (5, False)]):
            riera = dict(self.riera(index), incomplet=forats)
            _, fila = RI.compara(estat, riera, self.T0 + dt.timedelta(minutes=30 * i))
            if fila:
                files.append(fila)
            if i == 8:
                self.assertIsNotNone(estat["episodi"])
        self.assertIsNone(estat["episodi"])
        self.assertEqual(len(files), 1)

    def test_pluja_feble_no_obre_episodi(self):
        _, files, estat = self.passades([5, 12, 19, 8])
        self.assertIsNone(estat["episodi"])
        self.assertEqual(files, [])


def obs_wu(fins, mm_h, hores=2, fresca=True):
    """Lectures de 5 minuts d'una estació de Weather Underground, plovent mm_h
    les darreres hores fins a fins (acumulada del dia, com la dona l'API)."""
    res, acum = [], 0.0
    t = fins.replace(hour=0, minute=0)
    while t <= fins:
        if t > fins - dt.timedelta(hours=hores):
            acum += mm_h / 12
        res.append({"obsTimeUtc": t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "metric": {"precipTotal": round(acum, 2)}})
        t += dt.timedelta(minutes=5)
    return res if fresca else [o for o in res if o["obsTimeUtc"] < (fins - dt.timedelta(hours=1)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")]


class Veines(unittest.TestCase):
    """Les estacions particulars de Sant Cugat (18-10-2026): la mediana fa el
    mateix índex i mana el nivell més alt de les dues fonts."""
    def setUp(self):
        import tempfile
        from unittest import mock
        self.dir = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(RI, "COMPTADOR_WU", os.path.join(self.dir.name, "c.json")),
                  mock.patch.object(RI, "CACHE_WU", os.path.join(self.dir.name, "cache")),
                  mock.patch.object(RI, "ESTADO", os.path.join(self.dir.name, "riera.json"))]
        for x in self.p:
            x.start()
        self.ara = dt.datetime(2026, 10, 18, 14, 0).astimezone()
        self.crides = 0

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.dir.cleanup()

    def consulta(self, mm_h, frescas=6):
        def f(ruta, params):
            self.crides += 1
            i = C.RIERA_VEINES.index(params["stationId"])
            return obs_wu(self.ara, mm_h, fresca=i < frescas)
        return f

    def calcula(self, mm_h_xv, mm_h_wu, frescas=6, pluja_barri=None):
        import prevision as P
        from unittest import mock
        fins = self.ara - dt.timedelta(minutes=30)
        xv = [(fins - dt.timedelta(minutes=30 * (k + 1)), mm_h_xv / 2) for k in range(4)]
        with mock.patch.object(P, "taula_meteocat",
                               lambda codi, dia=None, lector=None: [x for x in xv if x[0].date() == dia]
                               if codi == C.RIERA_ESTACIO else []):
            return RI.calcula(self.ara, None, consulta=self.consulta(mm_h_wu, frescas), pluja_barri=pluja_barri)

    def test_mana_la_mes_alta(self):
        # Meteocat, 20 mm en 2 h; les estacions, 30 mm/h: 60 mm en 3 i en 6 hores, perill.
        r = self.calcula(10, 30)
        self.assertEqual((r["font"], r["nivell"], r["veines"]["n"]), ("veines", "perill", 6))
        self.assertEqual(r["veines"]["mm_3h"], 60.0)
        import avisos_bot as AB
        self.assertIn("60 mm en 3 hores a Sant Cugat (segons 6 estacions particulars, a les 14:00)",
                      AB.text_riera(r, "perill")["ca"])
        self.assertIn("Mediana de 6 estacions particulars", RI.missatge(r, "perill"))
        # Si Meteocat en dona més, mana Meteocat.
        r = self.calcula(40, 5)
        self.assertEqual(r["font"], "meteocat")

    def test_calen_tres_estacions_amb_dada_recent(self):
        r = self.calcula(10, 30, frescas=2)
        self.assertIsNone(r["veines"])
        self.assertEqual(r["font"], "meteocat")

    def test_sense_pluja_no_es_consulta(self):
        self.calcula(0, 30)
        self.assertEqual(self.crides, 0)

    def test_sense_meteocat_les_consulta_encara_que_no_plogui(self):
        # Meteocat callat i temps sec (21-10-2026): les estacions el substitueixen.
        import prevision as P
        from unittest import mock
        with mock.patch.object(P, "taula_meteocat", lambda codi, dia=None, lector=None: []):
            r = RI.calcula(self.ara, None, consulta=self.consulta(0))
        self.assertGreater(self.crides, 0)
        self.assertEqual((r["font"], r["sense_meteocat"], r["nivell"]), ("veines", True, None))

    def test_pluja_moderada_al_barri_les_consulta(self):
        # Meteocat encara sense pluja i el radar sense res sobre la conca: amb plugim al barri,
        # no; des d'1 mm en mitja hora (2 mm/h), sí, i l'avís pot sortir de les estacions.
        self.calcula(0, 30, pluja_barri=0.5)
        self.assertEqual(self.crides, 0)
        r = self.calcula(0, 30, pluja_barri=1.0)
        self.assertGreater(self.crides, 0)
        self.assertEqual((r["font"], r["nivell"]), ("veines", "perill"))

    def test_el_tope_del_dia(self):
        from unittest import mock
        with mock.patch.object(C, "RIERA_VEINES_MAX_DIA", 4):
            r = self.calcula(10, 30)
        self.assertEqual(self.crides, 4)
        self.assertIsNotNone(r["veines"])        # 4 estacions llegides, prou
        with mock.patch.object(C, "RIERA_VEINES_MAX_DIA", 4):
            r = self.calcula(10, 30)
        self.assertIsNone(r["veines"])           # el dia ja ha gastat el tope
        self.assertEqual(self.crides, 4)


class Privacitat(unittest.TestCase):
    def test_la_web_publica_porta_la_riera(self):
        # Fins a la 3.149.0 era privada (només servia per a l'avís, ADR 0027); ara la
        # mostra la pàgina «Riera» (ADR 0107), amb la previsió.
        self.assertNotIn("riera", M.PRIVADES)
        publiques = M.dades_publiques({"versio": "1", "riera": {"nivell": None, "index": 0.0},
                                       "riera_previsio": {"nivell": "possible"}, "sortides": []})
        self.assertEqual(set(publiques), {"versio", "riera", "riera_previsio"})


if __name__ == "__main__":
    unittest.main()


class Desbordament(unittest.TestCase):
    """La pregunta a Juanjo en tancar-se un episodi amb avís, i la seva resposta
    a la columna «desbordament» del registre (auditoria del 18-10-2026)."""

    def setUp(self):
        import json
        import tempfile
        import confirmacio as CF
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for nom in ("PREGUNTES", "CONFIRMACIONS", "REGISTRO", "DIR"):
            self.addCleanup(setattr, RI, nom, getattr(RI, nom))
        RI.DIR = self.dir.name
        RI.PREGUNTES = os.path.join(self.dir.name, "p.csv")
        RI.CONFIRMACIONS = os.path.join(self.dir.name, "c.csv")
        RI.REGISTRO = os.path.join(self.dir.name, "riera.csv")
        self.addCleanup(setattr, CF, "CONFIG_BOT", CF.CONFIG_BOT)
        CF.CONFIG_BOT = os.path.join(self.dir.name, "bot.json")
        with open(CF.CONFIG_BOT, "w") as f:
            json.dump({"token": "x", "chat_id": 7}, f)
        self.crides = []
        self.resposta = "si"

        def telegram(metode, **p):
            self.crides.append((metode, p))
            if metode == "sendMessage":
                return {"message_id": 52}, {"chat_id": 7}
            if metode == "getUpdates":
                return [{"callback_query": {"id": "q", "data": f"riera:{self.resposta}", "from": {"id": 7},
                                            "message": {"message_id": 52}}}], {"chat_id": 7}
            return True, {"chat_id": 7}
        self.addCleanup(setattr, RI, "telegram", RI.telegram)
        RI.telegram = telegram
        self.ara = dt.datetime(2026, 10, 9, 1, 0).astimezone()

    def fila(self, atencio="2026-10-08T20:30+02:00", perill=""):
        return {"inici": "2026-10-08T19:24+02:00", "fi": "2026-10-09T00:51+02:00", "hora_max": "2026-10-08T21:33+02:00",
                "index_max": 38.2, "mm_3h_max": 30.1, "mm_6h_max": 40.0, "capcalera_3h_max": 12.0,
                "avis_atencio": atencio, "avis_perill": perill, "desbordament": ""}

    def test_pregunta_en_tancar_amb_avis_i_apunta_la_resposta(self):
        RI.apunta(self.fila())
        self.assertEqual(RI.pregunta_desbordament(self.fila(), self.ara), 52)
        text = self.crides[0][1]["text"]
        self.assertIn("¿se ha desbordado", text)
        self.assertIn("aviso de atención a las 20:30", text)
        self.assertIn("como mucho, 38 mm en 3 horas", text)
        self.assertEqual([b["callback_data"] for b in self.crides[0][1]["reply_markup"]["inline_keyboard"][0]],
                         ["riera:si", "riera:no", "riera:nose"])
        self.assertEqual(RI.respostes(self.ara + dt.timedelta(hours=2)), 1)
        self.assertEqual(RI.respostes(self.ara + dt.timedelta(hours=2)), 0)      # una sola vegada
        self.assertIn("desbordament si", RI.resum())
        # Amb perill, ho diu; i el «no lo sé» no omple la columna.
        self.crides.clear()
        RI.pregunta_desbordament(self.fila(perill="2026-10-08T21:10+02:00"), self.ara)
        self.assertIn("aviso de peligro a las 21:10", self.crides[0][1]["text"])

    def test_sense_avis_o_sense_bot_no_pregunta(self):
        import confirmacio as CF
        self.assertIsNone(RI.pregunta_desbordament(self.fila(atencio=""), self.ara))
        os.remove(CF.CONFIG_BOT)                                   # la reserva d'IONOS no té el bot
        self.assertIsNone(RI.pregunta_desbordament(self.fila(), self.ara))
        self.assertEqual(self.crides, [])
        self.assertEqual(RI.respostes(self.ara), 0)

    def test_no_lo_se_no_omple_la_columna(self):
        RI.apunta(self.fila())
        self.resposta = "nose"
        RI.pregunta_desbordament(self.fila(), self.ara)
        self.assertEqual(RI.respostes(self.ara), 1)
        self.assertIn("desbordament ?", RI.resum())


class Previsio(unittest.TestCase):
    """La previsió de crescuda (ADR 0107): el model que més en dona en 3 hores,
    la finestra, la mitjana i el nivell «possible»; només les properes hores."""

    def test_la_finestra_no_comenca_abans_d_ara(self):
        # El revisor, 26-10-2026: a les 19:24, sense pluja, «entre les 17 i les 20 h».
        ara = dt.datetime(2026, 10, 26, 19, 24, tzinfo=dt.timezone(dt.timedelta(hours=1)))
        hores = [(ara.replace(minute=0) + dt.timedelta(hours=k)).isoformat(timespec="minutes") for k in range(-2, 46)]
        zeros = [0.0] * len(hores)
        hm = lambda t: __import__("hora").local(t).strftime("%H:%M")  # noqa: E731
        p = RI.previsio_models(hores, {"icon_eu": zeros}, ara)
        self.assertEqual(p["mm_3h_max"], 0.0)
        self.assertEqual(hm(p["finestra_3h"]["ini"]), "19:00")
        self.assertEqual(hm(p["finestra_6h"]["ini"]), "19:00")
        # La pluja de l'hora en curs compta, la de dues hores enrere no.
        pluja = list(zeros)
        pluja[0], pluja[2] = 30.0, 4.0
        p = RI.previsio_models(hores, {"icon_eu": pluja}, ara)
        self.assertEqual((p["mm_3h_max"], hm(p["finestra_3h"]["ini"])), (4.0, "19:00"))

    def test_el_model_que_mes_en_dona_i_la_finestra(self):
        ara = dt.datetime(2026, 10, 19, 7, 40, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        hores = [(ara.replace(minute=0) + dt.timedelta(hours=k)).isoformat(timespec="minutes") for k in range(-2, 46)]
        zeros = [0.0] * len(hores)
        arome = list(zeros)
        arome[2 + 9], arome[2 + 10], arome[2 + 11] = 5.2, 7.0, 10.9      # de 16 a 19 h: 23,1
        icon = list(zeros)
        icon[2 + 30] = 40.0                                              # demà: fora de les 24 hores
        ecmwf = [None] * len(hores)                                      # sense dades
        p = RI.previsio_models(hores, {"meteofrance_arome_france_hd": arome, "icon_eu": icon, "ecmwf_ifs": ecmwf}, ara)
        self.assertEqual((p["model_max"], p["mm_3h_max"], p["nivell"]), ("meteofrance_arome_france_hd", 23.1, "possible"))
        hm = lambda t: __import__("hora").local(t).strftime("%H:%M")  # noqa: E731
        self.assertEqual((hm(p["finestra_3h"]["ini"]), hm(p["finestra_3h"]["fi"])), ("16:00", "19:00"))
        self.assertAlmostEqual(p["mm_3h_mitjana"], round(23.1 / 2, 1), places=1)     # dos models amb dades
        self.assertEqual(p["per_model"], {"meteofrance_arome_france_hd": 23.1, "icon_eu": 0.0})
        self.assertEqual(p["models"], ["meteofrance_arome_france_hd", "icon_eu"])
        self.assertEqual(len(p["hores"]), 25)        # l'hora en curs i les 24 següents
        # Per sota del llindar, cap nivell; i sense cap model amb dades, res.
        arome[2 + 11] = 1.0
        self.assertIsNone(RI.previsio_models(hores, {"a": arome}, ara)["nivell"])
        self.assertIsNone(RI.previsio_models(hores, {"a": ecmwf}, ara))

    def test_previsio_amb_xarxa_simulada_i_registre(self):
        ara = dt.datetime(2026, 10, 19, 7, 40, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        hores = [(ara.replace(minute=0, tzinfo=None) + dt.timedelta(hours=k)).isoformat(timespec="minutes") for k in range(-7, 41)]
        serie = [0.0] * len(hores)
        serie[7 + 10] = 25.0
        resposta = json.dumps({"hourly": {"time": hores, "precipitation_meteofrance_arome_france_hd": serie,
                                          "precipitation_meteofrance_arome_france": [0.0] * len(hores),
                                          "precipitation_icon_eu": [0.0] * len(hores),
                                          "precipitation_ecmwf_ifs": [0.0] * len(hores)}})
        with tempfile.TemporaryDirectory() as d:
            vell = (RI.DIR, RI.ESTAT_DIR, RI.ESTAT_PREVISIO, RI.REGISTRE_PREVISIO)
            RI.DIR, RI.ESTAT_DIR = os.path.join(d, "registre"), d
            RI.ESTAT_PREVISIO, RI.REGISTRE_PREVISIO = os.path.join(d, "riera-previsio.json"), os.path.join(RI.DIR, "riera-previsio.csv")
            try:
                p = RI.previsio(ara, get=lambda url: resposta, lector=lambda url: "")
                self.assertEqual((p["nivell"], p["mm_3h_max"], p["inici"]), ("possible", 25.0, __import__("hora").clau(ara)))
                # Una passada després, el «possible» continua des de la mateixa hora (per al punt de la pestanya).
                p2 = RI.previsio(ara + dt.timedelta(minutes=15), get=lambda url: resposta, lector=lambda url: "")
                self.assertEqual(p2["inici"], __import__("hora").clau(ara))
                with open(RI.REGISTRE_PREVISIO, encoding="utf-8") as f:
                    files_ = list(csv.DictReader(f))
                self.assertEqual([r["mm_3h_max"] for r in files_], ["25.0", "25.0"])
                self.assertIn("2026-10-19", RI.resum_previsio(registre_xv=os.path.join(d, "no-hi-es.csv")))
            finally:
                RI.DIR, RI.ESTAT_DIR, RI.ESTAT_PREVISIO, RI.REGISTRE_PREVISIO = vell

