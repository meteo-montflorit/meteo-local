# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proves del canvi d'hora (sense xarxa), amb els dos canvis de debò: el
25-10-2026 (a les 3 d'estiu tornen a ser les 2) i el 28-03-2027 (a les 2
d'hivern passen a ser les 3). Per dins tot és en UTC i la web, el bot i les
dades publicades veuen l'hora de Madrid amb el desfasament (ADR 0128)."""
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import casa  # noqa: E402
import config as C  # noqa: E402
import hora as H  # noqa: E402
import prevision as P  # noqa: E402
import registre as R  # noqa: E402
import riscos as RS  # noqa: E402
import avisos_bot as AB  # noqa: E402
import smp as SMP  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot"))
import bot as B  # noqa: E402

UTC = dt.timezone.utc


def resposta(desfase_h, inici, n):
    """Com respon Open-Meteo: totes les hores amb el mateix desfasament, el del
    moment de la consulta."""
    t0 = dt.datetime.fromisoformat(inici)
    return {"utc_offset_seconds": desfase_h * 3600,
            "hourly": {"time": [(t0 + dt.timedelta(hours=x)).strftime("%Y-%m-%dT%H:%M") for x in range(n)]}}


def locals_(claus):
    """Com les veu la gent: l'hora de Madrid amb el desfasament."""
    return [H.iso_local(c) for c in claus]


class Hora(unittest.TestCase):
    def test_clau_en_utc_i_publicada_en_hora_de_madrid(self):
        estiu = dt.datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
        claus = [P.clau_hora(estiu + dt.timedelta(hours=x)) for x in range(3)]
        self.assertEqual(claus, ["2026-10-25T00:00Z", "2026-10-25T01:00Z", "2026-10-25T02:00Z"])
        # Les dues hores de 2 a 3 són dues claus, i com a text s'ordenen bé.
        self.assertEqual(H.publica(claus), ["2026-10-25T02:00+02:00", "2026-10-25T02:00+01:00", "2026-10-25T03:00+01:00"])
        self.assertEqual(sorted(claus), claus)

    def test_es_llegeixen_les_formes_d_abans(self):
        # Sense zona, l'hora de Madrid (els registres d'abans de la 3.201.0).
        self.assertEqual(H.clau("2026-10-13T19:00"), "2026-10-13T17:00Z")
        # L'hora repetida d'octubre ja portava el desfasament.
        self.assertEqual(H.clau("2026-10-25T02:00+02:00"), "2026-10-25T00:00Z")
        self.assertEqual(H.clau("2026-10-25T02:00+01:00"), "2026-10-25T01:00Z")
        self.assertEqual(H.clau("2026-10-25T01:00Z"), "2026-10-25T01:00Z")

    def test_restar_hores_de_madrid_no_s_equivoca(self):
        # Python resta dues hores amb la mateixa ZoneInfo com a hores de
        # rellotge: per això llegeix torna UTC i els càlculs es fan en UTC.
        a, b = H.llegeix("2026-10-25T01:30"), H.llegeix("2026-10-25T03:30")
        self.assertEqual(b - a, dt.timedelta(hours=3))

    def test_hores_de_rellotge_del_dia_del_canvi(self):
        self.assertEqual(H.clau(H.de_rellotge("2026-10-25", 24)), "2026-10-25T23:00Z")    # el dia té 25 hores
        self.assertEqual(H.clau(H.de_rellotge("2027-03-28", 24)), "2027-03-28T22:00Z")    # i aquest, 23
        self.assertEqual(H.mitjanit(dt.date(2026, 10, 25)), dt.datetime(2026, 10, 24, 22, tzinfo=UTC))


class HoresOpenMeteo(unittest.TestCase):
    def test_octubre_l_hora_que_es_repeteix(self):
        # Consultat el 24, en hora d'estiu, Open-Meteo ho dona tot a GMT+2.
        r = P.horas_locales(resposta(2, "2026-10-25T00:00", 6))
        self.assertEqual(locals_(r["hourly"]["time"]),
                         ["2026-10-25T00:00+02:00", "2026-10-25T01:00+02:00", "2026-10-25T02:00+02:00",
                          "2026-10-25T02:00+01:00", "2026-10-25T03:00+01:00", "2026-10-25T04:00+01:00"])

    def test_març_l_hora_que_no_hi_es(self):
        r = P.horas_locales(resposta(1, "2027-03-28T00:00", 5))
        self.assertEqual(locals_(r["hourly"]["time"]),
                         ["2027-03-28T00:00+01:00", "2027-03-28T01:00+01:00", "2027-03-28T03:00+02:00",
                          "2027-03-28T04:00+02:00", "2027-03-28T05:00+02:00"])

    def test_desfasament_de_la_consulta_i_no_de_l_hora(self):
        # El 13-10-2026 Open-Meteo donava el 26-10 a GMT+2: les seves 22 h són les 21 h d'hivern.
        r = P.horas_locales(resposta(2, "2026-10-26T22:00", 1))
        self.assertEqual(locals_(r["hourly"]["time"]), ["2026-10-26T21:00+01:00"])
        r = P.horas_locales(resposta(1, "2027-04-02T10:00", 1))
        self.assertEqual(locals_(r["hourly"]["time"]), ["2027-04-02T11:00+02:00"])

    def test_sol_i_dates(self):
        r = P.horas_locales({"utc_offset_seconds": 7200,
                             "daily": {"time": ["2026-10-26"], "sunrise": ["2026-10-26T08:05"],
                                       "sunset": ["2026-10-26T19:02"]}})
        self.assertEqual(r["daily"], {"time": ["2026-10-26"], "sunrise": ["2026-10-26T06:05Z"],
                                      "sunset": ["2026-10-26T17:02Z"]})
        self.assertEqual(H.publica(r["daily"])["sunrise"], ["2026-10-26T07:05+01:00"])


class TaulaAmbCanvi(unittest.TestCase):
    def previsio(self, desfase_h, inici, desde):
        r = P.horas_locales(resposta(desfase_h, inici, 72))
        h = r["hourly"]
        h["temperature_2m_meteofrance_seamless"] = [15.0] * 72
        for m in C.MODELOS_FINOS:
            h[f"precipitation_{m}"] = [0.0] * 72
        return casa.previsio(desde, h, {}, [])

    def test_octubre_dues_franges_de_2_a_3(self):
        files = self.previsio(2, "2026-10-24T00:00", dt.datetime(2026, 10, 24, 22, 30, tzinfo=UTC))
        self.assertEqual(locals_(f["hora"] for f in files[:5]),
                         ["2026-10-25T00:00+02:00", "2026-10-25T01:00+02:00", "2026-10-25T02:00+02:00",
                          "2026-10-25T02:00+01:00", "2026-10-25T03:00+01:00"])
        # Cada fila acaba on comença la següent, i totes duren una hora.
        for a, b in zip(files, files[1:]):
            self.assertEqual(a["fins"], b["hora"])
            self.assertEqual(H.utc(a["fins"]) - H.utc(a["hora"]), dt.timedelta(hours=1))
        self.assertEqual(H.iso_local(files[-1]["fins"]), "2026-10-26T21:00+01:00")

    def test_a_les_2_30_d_estiu_l_hora_en_curs_hi_es(self):
        # Fins a la 3.200.0, a les 2:30 d'estiu la taula començava una hora tard.
        files = self.previsio(2, "2026-10-24T00:00", dt.datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
        self.assertEqual(H.iso_local(files[0]["hora"]), "2026-10-25T02:00+02:00")

    def test_març_sense_franja_de_2_a_3(self):
        files = self.previsio(1, "2027-03-27T00:00", dt.datetime(2027, 3, 27, 23, 30, tzinfo=UTC))
        self.assertEqual([H.local(f["hora"]).strftime("%H") for f in files[:4]], ["00", "01", "03", "04"])
        self.assertEqual(H.iso_local(files[-1]["fins"]), "2027-03-29T21:00+02:00")

    def test_la_pluja_del_radar_a_l_hora_repetida_no_fa_caure_res(self):
        # Fins a la 3.200.0, casa.ajusta_hores barrejava hores amb zona i sense
        # i la pluja a sobre la nit del canvi aturava tota la publicació.
        files = self.previsio(2, "2026-10-24T00:00", dt.datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
        ara = dt.datetime(2026, 10, 25, 1, 10, tzinfo=UTC)                   # les 2:10 d'hivern
        casa.ajusta_hores(files, {"estat": "radar_sobre"}, ara)
        self.assertEqual(files[1]["probabilitat"], 0.5)                       # la segona franja de 2 a 3

    def test_el_vent_fort_de_la_nit_del_canvi_no_fa_caure_res(self):
        # riscos.de_la_previsio, el mateix: el vent fort de la vigília, amb les
        # dues hores de 2 a 3 dins les 24 hores.
        files = self.previsio(2, "2026-10-24T00:00", dt.datetime(2026, 10, 24, 22, 30, tzinfo=UTC))
        for f in files[:6]:
            f["ratxa"], f["ratxes_models"] = 80.0, {m: 80.0 for m in C.MODELOS_FINOS}
        riscos = RS.de_la_previsio(files, dt.datetime(2026, 10, 24, 22, 30, tzinfo=UTC))
        self.assertTrue(any(r["tipus"] == "ratxa" for r in riscos))

    def test_el_bot_compara_i_ordena_les_hores(self):
        files = self.previsio(2, "2026-10-24T00:00", dt.datetime(2026, 10, 24, 22, 30, tzinfo=UTC))
        # El bot llegeix les dades publicades.
        dades = H.publica({"hores": files})
        hores = [B.hora_local(f["hora"]) for f in dades["hores"]]
        self.assertEqual(hores, sorted(hores))
        # A les 2.30 d'hivern, la segona franja de 2 a 3.
        moment = dt.datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
        self.assertEqual(B.hora_ara(dades, moment)["hora"], "2026-10-25T02:00+01:00")


class AvisosAmbCanvi(unittest.TestCase):
    def test_les_franges_de_meteocat_cobreixen_les_dues_hores_de_2_a_3(self):
        a = {"dies": {"2026-10-25": [(2, 3)]}}
        self.assertEqual(sorted(SMP.hores_avis(a)), ["2026-10-25T00:00Z", "2026-10-25T01:00Z"])
        # I la de març no hi és.
        self.assertEqual(SMP.hores_avis({"dies": {"2027-03-28": [(2, 3)]}}), set())

    def test_les_franges_d_un_avis_que_travessa_el_canvi(self):
        # De les 0 a les 6 del 25-10: 7 hores, les 2 dues vegades.
        self.assertEqual(SMP.hores("2026-10-24T22:00Z", "2026-10-25T05:00Z"), {"2026-10-25": [(0, 6)]})


class LlegirElPublicat(unittest.TestCase):
    def test_llegeix_sempre_torna_utc(self):
        a = H.llegeix(dt.datetime(2026, 10, 25, 1, 30, tzinfo=H.ZONA))
        b = H.llegeix(dt.datetime(2026, 10, 25, 3, 30, tzinfo=H.ZONA))
        self.assertEqual(b - a, dt.timedelta(hours=3))
        self.assertEqual(H.llegeix("2026-10-25T02:00+01:00").utcoffset(), dt.timedelta(0))

    def test_interna_es_el_contrari_de_publica(self):
        dades = {"hora": "2026-10-25T01:00Z", "fi": "2026-10-25T05:59:59Z", "dia": "2026-10-25", "text": "a les 02:00",
                 "per_hora": {"2026-10-25T00:00Z": 1}}
        self.assertEqual(H.interna(H.publica(dades)), dades)
        self.assertEqual(H.interna("2026-10-25T02:00"), "2026-10-25T00:00Z")      # sense zona: Madrid

    def test_la_fitxa_publicada_i_la_interna_son_la_mateixa(self):
        # Fins a la 3.201.0 inclosa, «Perill» la duplicava: el publicat, amb
        # l'hora de Madrid, i l'intern, en UTC, no coincidien com a text.
        intern = [{"clau": "propi", "inici": "2026-10-25T11:09Z", "nivell": "alt"}]
        publicat = H.publica([{"clau": "propi", "inici": "2026-10-25T11:09Z", "nivell": "mig", "fi": "2026-10-25T12:00Z"}])
        r = AB.fusiona(intern, publicat)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["fi"], "2026-10-25T13:00+01:00")

    def test_l_historial_s_ordena_pel_moment(self):
        hist = [{"clau": "b", "inici": "2026-10-24T17:30Z"}, {"clau": "a", "inici": "2026-10-24T18:00+02:00"}]
        self.assertEqual([e["clau"] for e in AB.fusiona(hist, [])], ["a", "b"])        # 16:00Z abans que 17:30Z


class FrangesAmbCanvi(unittest.TestCase):
    def test_un_avis_de_tot_el_dia_es_una_franja(self):
        for dia in ("2026-10-25", "2027-03-28"):
            a = {"meteor": "Intensitat de pluja", "perill": 3, "dies": {dia: [(0, 24)]}}
            self.assertEqual(SMP.per_fenomen([a])[0]["dies"], {dia: [[0, 24]]}, dia)

    def test_la_pluja_del_bot_no_es_parteix(self):
        for t0, esperat in ((dt.datetime(2026, 10, 24, 23, tzinfo=UTC), [("01", "04")]),
                            (dt.datetime(2027, 3, 27, 23, tzinfo=UTC), [("00", "05")])):
            files = [{"hora": H.iso_local(t0 + dt.timedelta(hours=x)), "fins": H.iso_local(t0 + dt.timedelta(hours=x + 1)),
                      "probabilitat": 0.6} for x in range(4)]
            self.assertEqual([(a.strftime("%H"), b.strftime("%H")) for a, b, _ in B.franges(files)], esperat)

    def test_l_hora_en_curs_del_bot_la_primera_de_2_a_3(self):
        files = [{"hora": "2026-10-25T02:00+02:00", "fins": "2026-10-25T02:00+01:00"},
                 {"hora": "2026-10-25T02:00+01:00", "fins": "2026-10-25T03:00+01:00"}]
        moment = dt.datetime(2026, 10, 25, 0, 30, tzinfo=UTC)                 # les 2:30 d'estiu
        self.assertEqual(B.hora_ara({"hores": files}, moment)["hora"], "2026-10-25T02:00+02:00")


class Registre(unittest.TestCase):
    def test_les_dues_hores_de_2_a_3_no_es_trepitgen(self):
        dir_abans = R.DIR
        with tempfile.TemporaryDirectory() as d:
            R.DIR = d
            try:
                utc = dt.datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
                R.apunta_meteocat("XF", {utc + dt.timedelta(hours=x): float(x) for x in range(3)})
                with open(os.path.join(d, "meteocat-XF.csv"), encoding="utf-8") as f:
                    files = f.read().split()
            finally:
                R.DIR = dir_abans
        self.assertEqual(files[1:], ["2026-10-25T00:00Z,0.0", "2026-10-25T01:00Z,1.0", "2026-10-25T02:00Z,2.0"])

    def test_un_registre_d_abans_es_migra_en_desar_i_no_es_duplica(self):
        dir_abans = R.DIR
        with tempfile.TemporaryDirectory() as d:
            R.DIR = d
            try:
                ruta = os.path.join(d, "meteocat-XV.csv")
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write("fins,pluja_mm\n2026-10-25T01:00,0.1\n2026-10-25T02:00+02:00,0.2\n"
                            "2026-10-25T02:00+01:00,0.3\n2026-10-25T03:00,0.4\n")
                # La mateixa hora, ara amb clau en UTC: substitueix la d'abans.
                R.apunta_meteocat("XV", {dt.datetime(2026, 10, 25, 2, 0, tzinfo=UTC): 0.5})
                with open(ruta, encoding="utf-8") as f:
                    files = f.read().split()
            finally:
                R.DIR = dir_abans
        self.assertEqual(files[1:], ["2026-10-24T23:00Z,0.1", "2026-10-25T00:00Z,0.2", "2026-10-25T01:00Z,0.3",
                                     "2026-10-25T02:00Z,0.5"])


if __name__ == "__main__":
    unittest.main()
