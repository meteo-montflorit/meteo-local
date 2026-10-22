# SPDX-License-Identifier: AGPL-3.0-or-later
"""Més proves dels trens (trens.py, ADR 0029, 0078 i 0079): la passada
sencera, la prova diària de l'API de Rodalies i els casos límit, sense xarxa."""
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ARREL)
import config as C  # noqa: E402
import trens as T  # noqa: E402

ARA = dt.datetime(2026, 10, 7, 7, 50).astimezone()
R7 = C.TRENS_ESTACIONS["R7"]
S2 = C.TRENS_ESTACIONS["S2"]


def xarxa(respostes):
    """Un T.get fals: cada URL que comença per una clau torna el seu valor
    (si és una excepció, la llança)."""
    def get(url, binari=False):
        for prefix, valor in respostes.items():
            if url.startswith(prefix):
                if isinstance(valor, Exception):
                    raise valor
                return valor
        raise OSError(f"sense xarxa: {url}")
    return get


def posicions_renfe(ara, trens):
    return {"header": {"timestamp": str(int(ara.timestamp()))},
            "entity": [{"vehicle": {"vehicle": {"id": i, "label": f"{linia}-123"},
                                    "position": {"latitude": lat, "longitude": lon},
                                    "currentStatus": "IN_TRANSIT_TO"}} for i, linia, lat, lon in trens]}


class Protobuf(unittest.TestCase):
    def test_camps_de_64_i_32_bits(self):
        # Tipus 1 (8 bytes) i tipus 5 (4 bytes) es llegeixen sencers i se salten bé.
        b = bytes([1 << 3 | 1]) + b"ABCDEFGH" + bytes([2 << 3 | 5]) + b"WXYZ" + bytes([3 << 3 | 0, 7])
        self.assertEqual(T.camps(b), [(1, b"ABCDEFGH"), (2, b"WXYZ"), (3, 7)])

    def test_tipus_desconegut_falla(self):
        # Un tipus de camp que no existeix (3, grups obsolets) no es pot llegir: error, no dades.
        with self.assertRaises(ValueError):
            T.camps(bytes([1 << 3 | 3]))

    def test_iso_amb_valors_dolents(self):
        self.assertIsNone(T.iso(None))
        self.assertIsNone(T.iso("no"))
        self.assertEqual(T.iso(int(ARA.timestamp())), ARA.isoformat(timespec="minutes"))


class ProvaRodalies(unittest.TestCase):
    def test_resposta_bona(self):
        bona = {"included": [{"date": "2026-10-07", "lines": [], "title": {"ca": "x"}}]}
        self.assertIsNone(T.prova(lambda url: bona))

    def test_sense_llista(self):
        self.assertIn("included", T.prova(lambda url: {"data": []}))

    def test_avisos_sense_camps(self):
        self.assertIn("no porten", T.prova(lambda url: {"included": [{"date": "2026-10-07", "title": {"ca": "x"}}]}))
        self.assertIn("no porten", T.prova(lambda url: {"included": [{"date": "2026-10-07", "lines": []}]}))

    def test_no_respon(self):
        def falla(url):
            raise OSError("temps esgotat")
        self.assertEqual(T.prova(falla), "no respon: temps esgotat")

    def test_comprova_avisa_un_cop_quan_falla_i_un_cop_quan_torna(self):
        def falla(url):
            raise OSError("caiguda")
        bona = lambda url: {"included": []}  # noqa: E731
        with tempfile.TemporaryDirectory() as d, mock.patch("subprocess.run") as run, \
                contextlib.redirect_stdout(io.StringIO()) as sortida:
            marca = os.path.join(d, "rodalies-falla")
            self.assertEqual(T.comprova(marca, get_json=falla), "no respon: caiguda")
            self.assertTrue(os.path.exists(marca))
            self.assertEqual(run.call_count, 1)
            self.assertIn("ha deixat de funcionar (no respon: caiguda)", run.call_args[0][0][-1])
            # Mentre continua caiguda, no es torna a dir.
            T.comprova(marca, get_json=falla)
            self.assertEqual(run.call_count, 1)
            # Quan torna, un sol avís i es treu la marca.
            self.assertIsNone(T.comprova(marca, get_json=bona))
            self.assertFalse(os.path.exists(marca))
            self.assertEqual(run.call_count, 2)
            self.assertIn("torna a funcionar", run.call_args[0][0][-1])
            # Tot bé i sense marca: silenci.
            self.assertIsNone(T.comprova(marca, get_json=bona))
            self.assertEqual(run.call_count, 2)
        self.assertIn("ha deixat de funcionar", sortida.getvalue())

    def test_comprova_sense_avisar(self):
        def falla(url):
            raise OSError("caiguda")
        with tempfile.TemporaryDirectory() as d, mock.patch("subprocess.run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            marca = os.path.join(d, "rodalies-falla")
            T.comprova(marca, avisa=False, get_json=falla)
            self.assertTrue(os.path.exists(marca))
        run.assert_not_called()


def pb(num, valor):
    """Un camp protobuf de longitud variable (valors curts)."""
    valor = valor.encode() if isinstance(valor, str) else valor
    return bytes([num << 3 | 2, len(valor)]) + valor


def alerta_fgc(ruta, textos):
    traduccions = b"".join(pb(1, pb(1, t) + pb(2, idioma)) for idioma, t in textos)
    return pb(2, pb(5, pb(5, pb(2, ruta)) + pb(11, traduccions)))


class AvisosFgc(unittest.TestCase):
    def llegeix(self, feed):
        index = {"results": [{"file": {"url": "https://fgc/alertes.pb"}}]}
        with mock.patch.object(T, "get", xarxa({T.FGC: index, "https://fgc/alertes.pb": feed})):
            return T.avisos_fgc()

    def test_catala_i_castella(self):
        (a,) = self.llegeix(alerta_fgc("S2", [("ca", "Retards per una incidència a la línia."),
                                              ("es", "Retrasos por una incidencia en la línea.")]))
        self.assertEqual(a["linies"], {"S2"})
        self.assertEqual(a["text"], {"ca": "Retards per una incidència a la línia.",
                                     "es": "Retrasos por una incidencia en la línea."})

    def test_un_altre_idioma_tal_qual(self):
        # Sense català ni castellà, el text que hi hagi, sense traduir, a totes dues versions.
        (a,) = self.llegeix(alerta_fgc("S1", [("en", "Delays on the line.")]))
        self.assertEqual(a["text"], {"ca": "Delays on the line.", "es": "Delays on the line."})

    def test_sense_ruta_no_compta(self):
        feed = pb(2, pb(5, pb(11, pb(1, pb(1, "Avís general.") + pb(2, "ca")))))
        self.assertEqual(self.llegeix(feed), [])


class CasosLimit(unittest.TestCase):
    def test_rodalies_caiguda_passa_a_renfe(self):
        renfe = {"entity": [{"alert": {"informedEntity": [{"routeId": "51T0037R7"}],
                                       "descriptionText": {"translation": [{"text": "Servicio por carretera."}]}}}]}
        errors = []
        with mock.patch.object(T, "get", xarxa({T.RODALIES: OSError("503"), T.RENFE: renfe})):
            avisos = T.avisos_rodalies_o_renfe(errors)
        self.assertEqual(errors, ["avisos de Rodalies: 503"])
        self.assertEqual([a["linies"] for a in avisos], [{"R7"}])

    def test_tren_d_una_linia_desconeguda_no_compta(self):
        trens = [{"id": "x", "linia": "R2", "lat": R7[0], "lon": R7[1], "aturat": False}]
        self.assertEqual(T.es_mouen(trens, None, ARA), [])

    def test_posicions_anteriors_massa_velles(self):
        # Fa més de POSICIONS_MAX_MIN: no es compara; un tren aturat no compta encara que s'hagi mogut.
        abans = {"hora": (ARA - dt.timedelta(minutes=T.POSICIONS_MAX_MIN + 5)).isoformat(),
                 "posicions": {"a": (R7[0] - 0.05, R7[1])}}
        aturat = {"id": "a", "linia": "R7", "lat": R7[0], "lon": R7[1], "aturat": True}
        self.assertEqual(T.es_mouen([aturat], abans, ARA), [])

    def test_carretera_sense_parades_conegudes(self):
        # L'S2 no té llista de parades: un servei per carretera no es pot descartar.
        self.assertTrue(T.carretera_passa("S2", "Servei per carretera entre Sant Cugat i Sabadell."))
        self.assertFalse(T.carretera_passa("S2", "Retards de 10 minuts."))

    def test_carretera_si_l_estacio_no_es_a_la_llista(self):
        with mock.patch.object(C, "TRENS_PARADES", {"R7": ["Terrassa", "Manresa"]}):
            self.assertTrue(T.carretera_passa("R7", "Servei per carretera entre Terrassa i Manresa."))


class Calcula(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.estat = os.path.join(self.dir.name, "trens-posicions.json")
        patch = mock.patch.object(T, "ESTAT", self.estat)
        patch.start()
        self.addCleanup(patch.stop)

    def xarxa_bona(self, trens_s2_en_hora=(False, False)):
        fgc = [{"id": f"s{i}", "lin": "S2", "geo_point_2d": {"lat": S2[0], "lon": S2[1]},
                "estacionat_a": "", "en_hora": str(v)} for i, v in enumerate(trens_s2_en_hora)]
        fgc.append({"id": "sense-posicio", "lin": "S2"})
        return xarxa({
            T.RODALIES: {"included": []},
            T.RENFE + "vehicle_positions.json": posicions_renfe(dt.datetime.now().astimezone(), [("1", "R7", R7[0], R7[1])]),
            T.FGC + "alerts-gtfs_realtime": {"results": [{"file": {"url": "https://fgc/alertes.pb"}}]},
            "https://fgc/alertes.pb": b"",
            T.FGC + "posicionament-dels-trens": {"results": fgc},
        })

    def test_passada_sencera(self):
        with mock.patch.object(T, "get", self.xarxa_bona()):
            res = T.calcula(ARA)
        estats = {f["linia"]: f for f in res["linies"]}
        self.assertEqual(res["errors"], [])
        self.assertEqual(estats["R7"]["estat"], "circula")
        self.assertEqual(estats["R7"]["trens"], 1)
        # L'R8 comparteix estació amb l'R7, però no hi ha cap tren seu.
        self.assertEqual(estats["R8"]["estat"], "sense_trens")
        self.assertEqual(estats["R4"]["estat"], "sense_trens")
        # Dos trens de l'S2 que van tard i cap de puntual: «amb retard» (ADR 0079).
        self.assertEqual(estats["S2"]["estat"], "retard")
        self.assertEqual(estats["S2"]["trens_tard"], 2)
        self.assertNotIn("vist", estats["R7"])
        with open(self.estat, encoding="utf-8") as f:
            desat = json.load(f)
        self.assertEqual(set(desat["posicions"]), {"renfe-1", "fgc-s0", "fgc-s1"})
        self.assertEqual(desat["vist"]["R7"], ARA.isoformat(timespec="minutes"))
        self.assertEqual(set(desat["puntualitat"]["S2"]), {"fgc-s0", "fgc-s1"})
        self.assertFalse(os.path.exists(self.estat + ".tmp"))

    def test_s2_puntual_circula(self):
        with mock.patch.object(T, "get", self.xarxa_bona((True, True))):
            res = T.calcula(ARA)
        s2 = next(f for f in res["linies"] if f["linia"] == "S2")
        self.assertEqual(s2["estat"], "circula")
        self.assertNotIn("trens_tard", s2)

    def test_la_passada_seguent_recorda_quan_s_ha_vist(self):
        with mock.patch.object(T, "get", self.xarxa_bona()):
            T.calcula(ARA)
        # Vint minuts després no es veu cap tren de l'R7, però se n'ha vist un fa poc: circula.
        despres = ARA + dt.timedelta(minutes=20)
        sense_r7 = self.xarxa_bona()
        with mock.patch.object(T, "get", lambda url, binari=False: (
                posicions_renfe(dt.datetime.now().astimezone(), []) if url.startswith(T.RENFE) else sense_r7(url, binari))):
            res = T.calcula(despres)
        r7 = next(f for f in res["linies"] if f["linia"] == "R7")
        self.assertEqual((r7["estat"], r7["trens"]), ("circula", 0))

    def test_fonts_caigudes_no_son_sense_trens(self):
        # Si no hi ha avisos ni posicions, és «sense dades», no «sense trens» ni «circula».
        with open(self.estat, "w", encoding="utf-8") as f:
            f.write("no és json")
        with mock.patch.object(T, "get", xarxa({})):
            res = T.calcula(ARA)
        self.assertEqual({f["estat"] for f in res["linies"]}, {"sense_dades"})
        self.assertEqual(len(res["errors"]), 3)
        self.assertTrue(res["errors"][0].startswith("avisos de Rodalies:"))
        self.assertTrue(res["errors"][1].startswith("rodalies:"))
        self.assertTrue(res["errors"][2].startswith("fgc:"))
        # Sense posicions noves, l'estat anterior no es toca.
        with open(self.estat, encoding="utf-8") as f:
            self.assertEqual(f.read(), "no és json")

    def test_sense_carpeta_d_estat_no_desa(self):
        with mock.patch.object(T, "ESTAT", os.path.join(self.dir.name, "no-hi-es", "p.json")), \
                mock.patch.object(T, "get", self.xarxa_bona()):
            res = T.calcula(ARA)
        self.assertEqual(len(res["linies"]), len(C.TRENS))
        self.assertFalse(os.path.exists(os.path.join(self.dir.name, "no-hi-es")))


if __name__ == "__main__":
    unittest.main()
