# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de los autobuses del barrio (busos.py, ADR 0120), sin red: el
horario oficial, la corrección con el tiempo real y los avisos del AMB."""
import datetime as dt
import io
import os
import sys
import unittest
from zoneinfo import ZoneInfo
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import busos as BU  # noqa: E402


def varint(n):
    res = b""
    while True:
        b, n = n & 0x7F, n >> 7
        res += bytes([b | (0x80 if n else 0)])
        if not n:
            return res


def camp(num, valor):
    """Un camp protobuf: enter (tipus 0) o bytes (tipus 2)."""
    if isinstance(valor, int):
        return varint(num << 3) + varint(valor)
    if isinstance(valor, str):
        valor = valor.encode()
    return varint(num << 3 | 2) + varint(len(valor)) + valor


def gtfs(fitxers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nom, text in fitxers.items():
            z.writestr(nom, text)
    return buf.getvalue()


DIA = dt.date(2026, 10, 22)  # dijous
MITJANIT = dt.datetime.combine(DIA, dt.time()).timestamp()

ZIP = gtfs({
    "routes.txt": "route_id,route_short_name,route_long_name,map_url,timetable_url\n"
                  "508,CV1,Canaletes-Flor de Maig,https://m/cv1.pdf,https://h/cv1.pdf\n"
                  "999,X,Una altra,,\n",
    "trips.txt": "route_id,service_id,trip_id,trip_headsign\n"
                 "508,S1,508.1,Flor de Maig\n508,S2,508.2,Flor de Maig\n508,S1,508.3,Canaletes\n999,S1,999.1,Lluny\n",
    "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                    "S1,1,1,1,1,1,0,0,20261001,20261231\nS2,0,0,0,0,0,1,1,20261001,20261231\n",
    "calendar_dates.txt": "service_id,date,exception_type\nS2,20261022,1\n",
    "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                      "508.1,09:00:00,09:00:00,201243,1\n508.1,09:01:00,09:01:00,201464,2\n508.1,09:03:00,09:03:00,201463,3\n"
                      "508.2,10:00:00,10:00:00,201243,1\n"
                      "508.3,14:00:00,14:00:00,200075,1\n",
})


class Horari(unittest.TestCase):
    def test_nomes_les_linies_i_els_dies_que_circulen(self):
        hor = BU.horari(ZIP, [DIA])
        self.assertEqual(set(hor["rutes"]), {"508"})
        self.assertEqual(hor["rutes"]["508"]["nom"], "Canaletes – Flor de Maig")
        # S2 és de cap de setmana, però aquest dijous hi ha una excepció que l'afegeix.
        self.assertEqual(sorted(v["v"] for v in hor["viatges"]), ["508.1", "508.2", "508.3"])
        v = next(v for v in hor["viatges"] if v["v"] == "508.1")
        self.assertEqual(v["p"]["201464"], MITJANIT + 9 * 3600 + 60)

    def test_el_dia_del_canvi_d_hora(self):
        # 25-10-2026: el GTFS compta des de les 12 menys 12 hores; un bus de les
        # 10:00 passa a les 10:00 de l'hora d'hivern, no a les 9:00.
        hor = BU.horari(ZIP, [dt.date(2026, 10, 25)])
        v = next(v for v in hor["viatges"] if v["v"] == "508.2")
        self.assertEqual(dt.datetime.fromtimestamp(v["p"]["201243"], ZoneInfo("Europe/Madrid")).strftime("%H:%M"), "10:00")

    def test_un_dissabte_sense_excepcio_no_hi_ha_el_servei_de_feiner(self):
        hor = BU.horari(ZIP, [dt.date(2026, 10, 24)])
        self.assertEqual([v["v"] for v in hor["viatges"]], ["508.2"])


class Linies(unittest.TestCase):
    def setUp(self):
        self.hor = BU.horari(ZIP, [DIA])

    def parada(self, linies, sentit, nom):
        cv1 = next(l for l in linies if l["linia"] == "CV1")
        s = next(s for s in cv1["sentits"] if s["cap_a"] == sentit)
        return next(p for p in s["parades"] if p["parada"] == nom)["hores"]

    def test_sense_temps_real_hores_de_l_horari(self):
        linies = BU.linies(self.hor, {}, MITJANIT + 8 * 3600)
        # Les claus, en UTC (ADR 0128): les 9 i les 10 de Madrid.
        self.assertEqual(self.parada(linies, "Flor de Maig", BU.BANDERES), ["2026-10-22T07:00Z", "2026-10-22T08:00Z"])
        self.assertEqual(self.parada(linies, "Canaletes", "Canaletes - Av. Flor de Maig"), ["2026-10-22T12:00Z"])

    def test_el_temps_real_mana_i_el_retard_passa_a_les_parades_que_no_porta(self):
        real = {"508.1": {"201243": MITJANIT + 9 * 3600 + 300}}  # 5 minuts tard a la primera
        linies = BU.linies(self.hor, real, MITJANIT + 8 * 3600)
        self.assertEqual(self.parada(linies, "Flor de Maig", BU.BANDERES)[0], "2026-10-22T07:05Z")
        self.assertEqual(self.parada(linies, "Flor de Maig", "Av. Flor de Maig - Pl. Olivé"), ["2026-10-22T07:08Z"])

    def test_els_busos_que_ja_han_passat_no_surten(self):
        linies = BU.linies(self.hor, {}, MITJANIT + 9 * 3600 + 30 * 60)
        self.assertEqual(self.parada(linies, "Flor de Maig", BU.BANDERES), ["2026-10-22T08:00Z"])


class TempsReal(unittest.TestCase):
    def test_llegeix_les_hores_de_les_linies_del_barri(self):
        def viatge(id_, parada, hora):
            stu = camp(4, parada) + camp(2, camp(2, hora))
            return camp(2, camp(1, "e") + camp(3, camp(1, camp(1, id_)) + camp(2, stu)))
        feed = camp(1, camp(3, 1234)) + viatge("508.1", "201243", 5000) + viatge("999.1", "1", 6000)
        self.assertEqual(BU.temps_real(feed), (1234, {"508.1": {"201243": 5000}}))


class Incidencies(unittest.TestCase):
    def avis(self, ruta, inici, fi):
        text = lambda t, idioma: camp(1, camp(1, t) + camp(2, idioma))  # noqa: E731
        alerta = (camp(1, camp(1, inici) + camp(2, fi)) + camp(5, camp(2, ruta))
                  + camp(10, text("Desviament", "ca")) + camp(10, text("Desvío", "es"))
                  + camp(8, text("https://amb/avis", "ca")))
        return camp(2, camp(1, "a") + camp(5, alerta))

    def test_les_del_barri_vigents_amb_l_hora_local_escrita_com_utc(self):
        rutes = BU.horari(ZIP, [DIA])["rutes"]
        # Fins al divendres 23 a les 23:59, «en UTC».
        fi = int(dt.datetime(2026, 10, 23, 23, 59, tzinfo=dt.timezone.utc).timestamp())
        inici = int(dt.datetime(2026, 10, 20, 8, 0, tzinfo=dt.timezone.utc).timestamp())
        feed = self.avis("508", inici, fi) + self.avis("999", inici, fi)
        incs = BU.incidencies(feed, rutes, MITJANIT + 12 * 3600)
        self.assertEqual(incs, [{"linies": ["CV1"], "titol": {"ca": "Desviament", "es": "Desvío"},
                                 "url": {"ca": "https://amb/avis"}, "inici": "2026-10-20T06:00Z", "fi": "2026-10-23T21:59Z"}])

    def test_les_acabades_no_surten(self):
        rutes = BU.horari(ZIP, [DIA])["rutes"]
        fi = int(dt.datetime(2026, 10, 21, 20, 0, tzinfo=dt.timezone.utc).timestamp())
        self.assertEqual(BU.incidencies(self.avis("508", fi - 3600, fi), rutes, MITJANIT + 12 * 3600), [])


class HorariDesat(unittest.TestCase):
    def test_si_no_es_pot_baixar_serveix_el_desat_de_fa_pocs_dies(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cau = os.path.join(d, "busos-horari.json")
            with open(cau, "w", encoding="utf-8") as f:
                json.dump({"dia": "2026-10-20", "rutes": {}, "viatges": []}, f)
            antic, baixa = BU.CAU, BU.baixa
            BU.CAU = cau
            BU.baixa = lambda *a, **k: (_ for _ in ()).throw(OSError("sense xarxa"))
            try:
                self.assertEqual(BU.horari_desat(DIA)["dia"], "2026-10-20")
                with self.assertRaises(OSError):
                    BU.horari_desat(dt.date(2026, 10, 30))
            finally:
                BU.CAU, BU.baixa = antic, baixa


if __name__ == "__main__":
    unittest.main()
