# SPDX-License-Identifier: AGPL-3.0-or-later
"""La web diu i compta en hora de Madrid sigui quina sigui la zona del
dispositiu (ADR 0128): els mateixos textos amb el dispositiu a Madrid, Nova
York, UTC (Firefox amb «resistFingerprinting»), Canàries i Tòquio, també les
dues nits del canvi d'hora. Necessita Node."""
import datetime as dt
import json
import os
import shutil
import subprocess
import unittest
from zoneinfo import ZoneInfo

from test_web import ARNES, ARNES_SW, WEB

MADRID = ZoneInfo("Europe/Madrid")
ZONES = ["Europe/Madrid", "America/New_York", "UTC", "Atlantic/Canary", "Asia/Tokyo"]


def hores(inici_utc, n):
    """Les hores com les publica la 3.201.0: hora de Madrid amb el desfasament."""
    t0 = dt.datetime.fromisoformat(inici_utc)
    res = []
    for i in range(n):
        a, b = t0 + dt.timedelta(hours=i), t0 + dt.timedelta(hours=i + 1)
        res.append({"hora": a.astimezone(MADRID).isoformat(timespec="minutes"),
                    "fins": b.astimezone(MADRID).isoformat(timespec="minutes"),
                    "temperatura": 12.0, "nuvols": 50, "codi": 3, "probabilitat": 0, "pluja_mm": 0})
    return res


def avalua(zona, ara, expr, pagina="casa.js", arnes=ARNES):
    r = subprocess.run(["node", "-e", arnes, WEB, ara, expr, pagina], capture_output=True, text=True,
                       check=True, env={**os.environ, "TZ": zona})
    return json.loads(r.stdout)


@unittest.skipUnless(shutil.which("node"), "cal Node")
class ZonaDelDispositiu(unittest.TestCase):
    def igual_a_tot_arreu(self, ara, expr, pagina="casa.js", arnes=ARNES):
        madrid = avalua("Europe/Madrid", ara, expr, pagina, arnes)
        for zona in ZONES[1:]:
            with self.subTest(zona=zona):
                self.assertEqual(avalua(zona, ara, expr, pagina, arnes), madrid)
        return madrid

    def test_nit_d_octubre(self):
        # Dissabte 24 a les 22 h de Madrid fins diumenge 25: les 3 d'estiu tornen a ser les 2.
        h = hores("2026-10-24T20:00:00+00:00", 30)
        expr = (f"h = {json.dumps(h)};"
                "[h.map((f) => horaLocal(f.hora)), resumTrams(h, new Date(), null).map((t) => [t.clau, t.nom, t.hores]),"
                " h.map((f) => desfasDe(f.hora)), horaCurta(new Date()), nomDiaCurt(h[29].hora, new Date())]")
        hores_, trams, desfasos, ara, dia = self.igual_a_tot_arreu("2026-10-25T02:30:00+02:00", expr)
        self.assertEqual(hores_[:8], [22, 23, 0, 1, 2, 2, 3, 4])            # dues files de 2 a 3
        self.assertEqual(trams[0], ["2026-10-24|Nit", "Nit", "fins a les 7 h"])
        self.assertEqual(desfasos[0], 120)
        self.assertEqual(desfasos[-1], 60)
        self.assertEqual(ara, "02:30")                                      # la primera 2:30, la d'estiu
        self.assertEqual(dia, "demà")                                       # l'última, el 26 a les 2

    def test_nit_de_marc(self):
        # Diumenge 28-03-2027: a les 2 d'hivern passen a ser les 3.
        h = hores("2027-03-27T22:00:00+00:00", 8)
        madrid = self.igual_a_tot_arreu("2027-03-28T00:30:00+01:00",
                                        f"[{json.dumps(h)}.map((f) => horaLocal(f.hora)), horaCurta(new Date())]")
        self.assertEqual(madrid, [[23, 0, 1, 3, 4, 5, 6, 7], "00:30"])     # cap fila de 2 a 3

    def test_dies_i_hores_dels_textos(self):
        expr = ("[quanFase('2026-10-26T05:12+01:00'), diaPassat('2026-10-24T23:30+02:00', new Date()),"
                " textFranja(new Date('2026-10-25T21:00+01:00'), new Date('2026-10-26T00:00+01:00'), new Date()),"
                " quanLlum('2026-10-26T00:15+01:00'), sumaDies(new Date(), 1), diesEntre(new Date(), '2026-10-26T00:10+01:00')]")
        self.assertEqual(self.igual_a_tot_arreu("2026-10-25T23:40:00+01:00", expr),
                         ["demà, 5:12", "ahir", "avui fins a mitjanit", "el 26/10 a les 00:15", "2026-10-26", 1])

    def test_les_dades_d_abans_sense_zona_son_hora_de_madrid(self):
        expr = ("d = ambDesfas({ hores: [{ hora: '2026-10-04T00:00' }], dia: '2026-10-04', '2026-10-04T09:00': 1 });"
                "[d, llegeixHora('2026-10-25T02:30').toISOString(), llegeixHora('2027-03-28T02:30').toISOString(),"
                " llegeixHora('2026-10-04').toISOString()]")
        self.assertEqual(self.igual_a_tot_arreu("2026-10-25T12:00:00+01:00", expr), [
            {"hores": [{"hora": "2026-10-04T00:00+02:00"}], "dia": "2026-10-04", "2026-10-04T09:00+02:00": 1},
            "2026-10-25T00:30:00.000Z",          # la repetida, la primera (d'estiu)
            "2027-03-28T01:30:00.000Z",          # la que no existeix, una hora després
            "2026-10-03T22:00:00.000Z"])

    def test_el_dia_de_l_avis_tocat_a_mitjanit(self):
        # Passada la mitjanit de Madrid, «Demà» ja és «Avui», també a Nova York.
        dema = "https://m.test/consultes.html#dema"
        self.assertEqual(self.igual_a_tot_arreu("2026-10-11T00:20:00+02:00",
                                                f"destiAvis({json.dumps(dema)}, '2026-10-11')", arnes=ARNES_SW),
                         "https://m.test/consultes.html#avui")


if __name__ == "__main__":
    unittest.main()
