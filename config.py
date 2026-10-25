# SPDX-License-Identifier: AGPL-3.0-or-later
"""Datos fijos de «Temps a Montflorit»: lugares, horario, fuentes y umbrales.
Se cambian aquí, no en los programas."""

VERSION = "3.204.2"

# Coordenadas con tres decimales (unos 100 m), no las exactas: para el tiempo
# da igual una calle u otra, y el repositorio es público.
CASA = (41.482, 2.135)      # Cerdanyola del Vallès (Montflorit)

# La estación de casa (Ecowitt, API oficial; ADR 0017), en Montflorit: la
# única del barrio desde la 3.44.0 (ADR 0058). Temperatura, humedad, punto de
# rocío, presión y radiación son fiables; el viento no se usa. El pluviómetro
# registró toda la lluvia hasta PLUVIOMETRE_CASA_FIABLE_FINS; desde entonces
# a veces no marca la lluvia débil, así que solo cuenta cuando marca lluvia.
ESTACIO_CASA = "Casa"
PLUVIOMETRE_CASA_FIABLE_FINS = "2026-08-31"
# La estación da la presión medida a su altura (la «relativa» de Ecowitt no
# está calibrada: el 07-10-2026 marcaba 1002 hPa con 1011 de QNH en Sabadell).
# Se reduce al nivel del mar con esta altitud (modelo digital del terreno de
# Open-Meteo para las coordenadas redondeadas), que es lo que publican las
# demás estaciones y los mapas (ADR 0037).
ALTITUD_CASA_M = 70

# El viento de ahora: el anemómetro de la estación de casa no funciona bien,
# así que se muestra el de la estación de Meteocat más cercana, por medias
# horas (ADR 0037).
VENT_ESTACIO = "XV"
# El viento estimado con las estaciones vecinas (vent_veines.py, ADR 0064)
# se calcula y se aprende cada día, pero la página sigue con el de Sant Cugat
# hasta que Juanjo lo decida con las cifras de la comprobación.
VENT_VEINES_ACTIU = False

# Estaciones automáticas de Meteocat más próximas (código: nombre). Su lluvia
# por horas se registra: cuando el pluviómetro de casa marca cero, la hora
# solo cuenta como seca si ellas tampoco recogieron nada (ADR 0058).
ESTACIONES = {
    "XF": "Sabadell (Parc Agrari)",
    "XV": "Sant Cugat (CAR)",
}

# Estaciones vecinas de la red de estaciones personales de Weather Underground
# (ADR 0060), leídas con la clave de lectura que da la red a quien aporta una
# estación (ADR 0059). De cada una: dónde está (sin dirección exacta), si su
# lluvia cuenta para «plou ara» y para dar lluvia al aprender (con dos, ADR
# 0070) y si su cero confirma las horas secas (examen del 05 al 10-10-2026,
# ADR 0060; repetido con 75 días el 10-10-2026, ADR 0070: ICERDA18 e ICERDA28
# también confirman).
# «alta»: en la parte alta del barrio, más cálida que la de la riera, donde
# están la estación de casa e ICERDA6 (Juanjo, 13-10-2026; ADR 0087).
VEINES = {
    "ICERDA6": {"nom": "a 1 km a l'est, vora la riera", "plou": True, "sec": True, "alta": False},
    "ICERDA18": {"nom": "al Puig de la Guàrdia", "plou": True, "sec": True, "alta": True},
    "ICERDA28": {"nom": "a 300 m al nord-oest", "plou": True, "sec": True, "alta": True},
    "ICERDA48": {"nom": "a 600 m al nord-est", "plou": False, "sec": False, "alta": True},
}
# Lluvia en Montflorit para aprender (aprenentatge.pluja_observada, ADR 0070):
# si casa no la marca, llueve si la marcan al menos estas vecinas de las que
# cuentan («plou»).
VEINES_PLUJA_MIN = 2
# La clave de lectura caduca a los seis meses (generada el 10-10-2026): antes
# de esta fecha hay que regenerarla en wunderground.com (Member Settings > API
# Keys, en la versión antigua del sitio) y cambiarla en el NAS (RESTAURAR.md).
WU_CLAU_CADUCA = "2027-04-10"
WU_AVIS_CADUCITAT_DIES = 21

# Horario de actualización con datos en directo (hora local): previsión a 24
# horas, actualizada cada cuarto de hora todo el día. La web lo muestra tal
# cual. Los datos van a IONOS en cada pasada y la web a GitHub cada media hora
# como mucho (ADR 0020).
HORARIO_CASA = ("00:00", "23:45")
HORARIO_CASA_AVISO = ("00:00", "23:54")
INTERVALO_CASA_MIN = 15

# Modo aviso: con aviso de AEMET vigente, plan de Protección Civil en alerta o
# emergencia, lluvia en casa o lluvia en el radar a menos de
# RADAR_AVISO_KM de casa (o que llegará a casa en la próxima hora), la página
# se actualiza cada 6 minutos: el ritmo del radar de Meteocat, que saca una
# imagen a :00, :06, :12… y la publica unos 13-14 minutos después. Con el
# desfase de 3 minutos, cada pasada coge la imagen nueva (la de las 10:06,
# publicada a las 10:19:43, a las 10:21).
MODO_AVISO_INTERVALO_MIN = 6
MODO_AVISO_DESFASE_MIN = 3
RADAR_AVISO_KM = 15
# Plugim segons el radar (ADR 0019; Juanjo, 18-10-2026, amb plugim a casa i la
# web dient «el radar no veu pluja»): els ecos per sota de la pluja que compta
# (nowcast.PLOU_MMH) només diuen plugim si són estesos a sobre del barri i els
# veuen els dos radars, PLUGIM_PX píxels o més a PLUGIM_KM o menys de casa en
# cadascun. Un píxel solt de la franja més baixa és soroll (10-10-2026).
PLUGIM_KM = 3
PLUGIM_PX = 15

# A qué hora el reloj del NAS (nas/reloj.sh) rellena las horas que falten de
# la estación de casa (registre.py estacio) y la página aprende de sus
# aciertos (aprenentatge.py diari).
HORA_VERIFICACION = "16:00"

# Zonas de aviso de AEMET. La primera es la del barrio; un aviso solo en la
# segunda, la costa, se tiene en cuenta pero no decide.
ZONA_AVISOS = "Prelitoral de Barcelona"
ZONA_CERCANA = "Litoral de Barcelona"

# Planes de Protección Civil de la Generalitat que dependen del tiempo, con el
# nombre que ve el lector. Un plan en alerta o emergencia cuenta como riesgo
# alto; en prealerta solo se muestra en la web (ADR 0051).
PLANES_PC = {"INUNCAT": "d'inundacions", "VENTCAT": "de vent", "NEUCAT": "de neu"}
# El PROCICAT agrupa riesgos distintos: el de cada registro lo dice su icono
# (ico_PROCICAT_<RIESGO>.png). Solo los que afectan a toda una zona; ni la
# pandemia ni el ferrocarril (los trenes ya están en «Si surts»).
PROCICAT_PC = {"ONADA_CALOR": "per onada de calor", "ONADA_FRED": "per onada de fred",
               "CONTAMINACIÓ": "per contaminació", "VENT": "per vent"}
# Los avisos de peligro de Meteocat (SMP) de la comarca, junto a los planes
# (smp.py, ADR 0067): el número del Vallès Occidental en los datos de
# Meteocat (IDComarca del mapa de comarcas de meteo.cat, comarquesAmbMar.json).
SMP_COMARCA = 40
SMP_COMARCA_NOM = "Vallès Occidental"
# Minutos sin ver un fenómeno de Meteocat para darlo por acabado (ADR 0092):
# entre dos emisiones del mismo aviso, el relevo no avisa dos veces.
SMP_FI_MIN = 30

# El revisor de coherencia (revisor.py, ADR 0101): el modelo, fijado por su
# nombre y de la generación 5.5 como mínimo (Juanjo, 05-10-2026); las horas
# en que revisa, con el resumen del bot, antes de los de la mañana (6, 7 y 8)
# y del de mañana (21); y los minutos que espera entre dos revisiones por un
# cambio de lo que concluye la web (un aviso enviado no espera).
REVISOR_MODEL = "claude-sonnet-5-5"
# El agente que arregla un commit que no pasa las comprobaciones de GitHub
# (reparador.py, ADR 0113): el modelo más capaz, porque trabaja solo.
REPARADOR_MODEL = "claude-opus-5-5"
REVISOR_HORES = ("05:50", "20:50")
REVISOR_MIN_MIN = 30
# Si la descripción del plan nombra solo otras zonas, no afecta al barrio.
ZONAS_PROPIAS_PC = ["Vallès", "Barcelona", "Catalunya"]
ZONAS_AJENAS_PC = ["Ebre", "Pirineu", "Aran", "Lleida", "Girona", "Tarragona", "Empordà"]

# Modelos deterministas «finos» de Open-Meteo: los que usa la previsión.
MODELOS_FINOS = [
    "meteofrance_arome_france_hd",  # 1,5 km, el más fino que cubre Cataluña
    "meteofrance_arome_france",     # 2,5 km
    "icon_eu",                      # 7 km
]
# ECMWF IFS a 9 km: entra en la probabilidad de lluvia como un modelo más
# (ADR 0086), no en los milímetros de la tabla.
MODEL_ECMWF = "ecmwf_ifs"
# Ensemble horario usado como probabilidad.
ENSEMBLE = "icon_eu_eps"

# Si Open-Meteo falla, la página de casa usa la última previsión buena, si no
# tiene más de estas horas (ADR 0016).
CASA_PREVISION_ANTERIOR_MAX_H = 6

# Situaciones de peligro en casa (riscos.py, ADR 0018): desde el 16-10-2026,
# los umbrales bajo y alto de los avisos de situación meteorológica de peligro
# de Meteocat para Cerdanyola y el Vallès Occidental (meteo.cat, «Situació
# Meteorològica de Perill» y «Llindars_municipi_2026.pdf»; los de temperatura
# son del municipio). Hasta entonces, los de AEMET para el Prelitoral; por
# fenómeno manda Meteocat (ADR 0092). Se superan con «más que» (en el frío,
# «menos que»), como dice Meteocat. Se comparan con lo que miden las estaciones
# y con la previsión de la página de casa, no con los avisos oficiales. El frío,
# con la temperatura de la riera, la zona más fría (Juanjo: «el frío con la
# riera»). Lluvia en mm, racha en km/h, temperatura en °C y nieve en cm (por
# debajo de 300 m, cualquier cantidad).
RISC_LLINDARS = {
    "pluja_30min": (20, 40),
    "pluja_3h": (60, 90),
    "pluja_24h": (100, 200),
    "ratxa": (72, 108),
    "calor": (36.8, 38.8),
    "fred": (-1.6, -3.6),
    "neu_24h": (0, 5),
}
# Horas sin ver un riesgo para darlo por acabado: así el vaivén de los modelos
# entre una pasada y otra no repite el aviso por Telegram.
RISC_FI_H = 3

# Aviso de antes de llover (pluja_arriba.py, ADR 0022; el público, avisos_bot.py,
# ADR 0034 y 0048; desde el 08-10-2026 no hay uno aparte para Juanjo): sale
# cuando el radar llevado hacia delante dice que faltan AVIS_PLUJA_MIN minutos
# más una pasada del modo aviso (entre 15 y 21 minutos antes): lo que importa
# es que llegue con margen, no el minuto exacto. Un episodio de
# lluvia acaba tras AVIS_PLUJA_REPOS_MIN minutos sin lluvia medida ni
# anunciada, y hay un aviso por episodio. El aviso cuenta como acierto si
# empieza a llover en AVIS_PLUJA_VERIFICA_MIN minutos.
AVIS_PLUJA_MIN = 15
AVIS_PLUJA_REPOS_MIN = 60
AVIS_PLUJA_VERIFICA_MIN = 45

# Umbrales de la lluvia (mm en una hora; fracción de miembros del ensemble o
# del círculo del radar): lo que ya moja, y desde qué probabilidad se avisa
# de lluvia posible.
UMBRAL_MM = 0.2
# La boira de l'hora en curs (ADR 0100): l'observa l'aeroport de Sabadell
# (METAR) i l'estació de casa és saturada. Sola, la humitat no n'hi ha prou:
# del 13 al 17-10-2026, 26 hores amb el 98 % o més i boira només en 4.
HUMITAT_BOIRA = 97
PROB_ATENCION = 0.2
# Llueve ahora si una de las dos estaciones ha recogido lluvia en estos
# minutos. Ni la intensidad que dan (tarda en volver a cero) ni la media hora:
# el 08-10-2026 las dos pararon a las 19:50 y la página aún decía «Pluja a
# sobre» a las 20:15. Con 15, una llovizna de 0,8 mm/h (una marca de 0,2 mm
# cada 15 minutos) sigue contando como lluvia.
PLOU_ARA_MIN = 15
# El radar en directo, centrado en Montflorit si se puede: el que da el aviso
# de lluvia lo enlaza (avisos_bot.py, ADR 0048). Los mismos en web/casa.js y
# bot/bot.py, que las pruebas comparan.
RADAR_EN_DIRECTE = {"rainviewer": "https://www.rainviewer.com/map.html?loc=41.482,2.135,9&layer=radar",
                    "meteocat": "https://www.meteo.cat/observacions/radar"}

# «Si surts», lluvia (web/sortir.js, ADR 0047 y 0069): solo la probabilidad,
# con los umbrales aprendidos (SORTIR_LLINDARS_PLUJA, más abajo); sin
# probabilidad, la lluvia de los modelos: 0,2 mm «compte» y 1 mm «millor no».
# Un aviso de AEMET solo, «compte». Las pruebas miran que coincidan con la página.
SORTIR_MM_RISC = 0.2
SORTIR_MM_PLUJA = 1.0
# Els llindars de pluja de «Si surts», per a tots els mitjans, apresos
# (aprenentatge.aprén_sortir, ADR 0069): amb «millor no» ha de ploure almenys
# 2 de cada 3 vegades i amb «bé», com a molt 1 de cada 100, també amb el marge
# de la mostra (cota de Wilson amb z = 1,28, un 90 % d'un sol costat). Dos
# jocs: «curt», per a d'aquí a SORTIR_CURT_H hores o menys, i «llarg», per a
# més tard. Els de partida surten de l'arxiu amb la pluja de l'estació de casa
# (del 08-10-2025 al 04-10-2026, ADR 0069). «pluja»: «millor no» en bici i
# moto, «compte» en cotxe; «risc»: «compte» en bici i moto i el paraigua a peu.
SORTIR_CURT_H = 3
SORTIR_OBJECTIU_NO = 2 / 3
SORTIR_OBJECTIU_BE = 0.01
SORTIR_OBJECTIU_FRANJA = 0.1   # i cap franja de 5 punts amb «bé» per sobre d'1 de cada 10
SORTIR_Z = 1.28
SORTIR_MIN_PLUJA = 30          # hores amb pluja per banda abans d'aprendre
SORTIR_MIN_HORES = 30          # hores per sobre (o per sota) d'un llindar per jutjar-lo
# Curt: 40 % (hi plou el 71 %, 233 hores) i 10 % (per sota, el 0,6 %; del 10
# al 15 % plou el 14 %, massa per a «bé»); llarg, amb la previsió d'un dia
# abans: 60 % (el 79 %, 56 hores) i 10 % (del 10 al 15 %, el 12 %).
SORTIR_LLINDARS_PLUJA = {"curt": {"pluja": 0.4, "risc": 0.1}, "llarg": {"pluja": 0.6, "risc": 0.1}}
# La resta de regles meteorològiques de «Si surts» (web/sortir.js), per a la
# comprovació diària de tots els mitjans (aprenentatge.verifica_sortir, ADR
# 0068); les proves les comparen amb la pàgina. En cotxe, des de la 3.139.0, els
# llindars de pluja de Meteocat dels perills (RISC_LLINDARS): la mesurada a la
# darrera mitja hora, si se surt ara, i la prevista en 3 hores (abans, 20 i 40
# mm previstos en una hora, d'AEMET, ADR 0039). Ratxes (km/h) i fred (°C):
# (compte, millor no).
SORTIR_PLUJA_COTXE = {"30min": RISC_LLINDARS["pluja_30min"], "3h": RISC_LLINDARS["pluja_3h"]}
# El viento sale en «Ara» solo cuando molesta (Juanjo, 25-10-2026): media de
# 20 km/h o más (fuerza 4 de Beaufort, levanta polvo y papeles) o racha de 40
# km/h o más (la de «compte» en bici). Del 2 al 25-10-2026, en Sant Cugat, la
# media llegó a 14 km/h y la racha a 33: ninguna media hora lo pasó.
VENT_MOLEST = {"mitja": 20, "ratxa": 40}
SORTIR_LLINDARS = {
    "peu": {"ratxa": (None, 70), "fred": (None, None)},
    "bici": {"ratxa": (40, 50), "fred": (3, 1)},
    "moto": {"ratxa": (50, 70), "fred": (3, 1)},
    "cotxe": {"ratxa": (90, None), "fred": (1, None)},
}

# Riera de Sant Cugat (riera.py, ADR 0027): nace en Collserola y pasa por
# Montflorit. Se desbordó con 53 mm en 3 horas en Sant Cugat (29-04-2024, el
# agua llegó a la puerta de las casas) y con 67 (29-09-2026 y 04-10-2026,
# entró en ellas), justo al acabar las 3 horas más lluviosas. Cuenta la
# lluvia de las últimas 3 horas en la estación de Meteocat de Sant Cugat más
# la que el radar lleva hacia delante sobre la cuenca en la hora siguiente.
# Desde RIERA_REGISTRE_MM se apunta el episodio; desde ATENCIO, aviso por
# Telegram; con PERILL en 3 horas y PERILL_6H en 6, otro: el 13-09-2025
# cayeron 52 mm en 3 horas sin lluvia antes (52 en 6) y no se desbordó, y los
# tres desbordamientos tenían 67 o más en 6 horas. Son una hipótesis con
# cuatro casos: se ajustan con el registro.
RIERA_ESTACIO = "XV"                # Sant Cugat (CAR), en medio de la cuenca
RIERA_CAPCALERA = ("D5", "Observatori Fabra")   # cresta de Collserola, junto a Les Planes
CONCA_RIERA = (41.46, 2.10)         # centro aproximado de la cuenca, para el radar
RIERA_HORES = 3
RIERA_REGISTRE_MM = 20
RIERA_ATENCIO_MM = 35
RIERA_PERILL_MM = 50
RIERA_PERILL_6H_MM = 60
RIERA_FI_H = 3                      # horas por debajo del registro para cerrar el episodio
# La previsió de crescuda (riera.previsio, ADR 0107): si algun model preveu
# RIERA_PREVISIO_MM o més en 3 hores a la conca en les properes
# RIERA_PREVISIO_HORES, la pàgina «Riera» diu «risc de crescuda possible».
# No avisa: amb l'arxiu 2024-2026, 27 dies amb 20 mm previstos, 4 reals.
RIERA_PREVISIO_MM = 20
RIERA_PREVISIO_HORES = 24
# Las estaciones particulares de Sant Cugat en Weather Underground (ADR 0027,
# 18-10-2026; Juanjo: «se podría buscar una estación cercana a la riera…
# así no solo la de Meteocat, que es cada media hora»): dato cada 5 minutos,
# casi sin retraso. Las seis que midieron con coherencia los cuatro episodios
# conocidos (29-04-2024, 13-09-2025, 29-09-2026 y 04-10-2026); otras cuatro
# cercanas fallaban (siempre a cero o un día sí y otro no). Del centro y de la
# parte alta de la cuenca (Valldoreix y el oeste). Se usa su mediana, con
# RIERA_VEINES_MIN como mínimo con dato de los últimos RIERA_VEINES_FRESCA_MIN
# minutos, y el aviso toma el nivel más alto de las dos fuentes: con lo
# medido, adelantaba los avisos 40-55 minutos, y el 13-09-2025 habría dado un
# peligro de más (Juanjo: «habrá que arriesgarse»). Solo se consultan cuando
# llueve en Sant Cugat o de forma moderada en el barrio o el radar ve lluvia
# sobre la cuenca, con un tope diario para no quitar cuota a la web (1.500
# consultas al día; la web gasta unas 400).
RIERA_VEINES = ("ISANTC157", "ISANTC147", "ISANTC65", "ISANTC37", "ISANTC40", "ISANTC89")
RIERA_VEINES_MIN = 3
RIERA_VEINES_FRESCA_MIN = 20
RIERA_VEINES_MAX_DIA = 500
# También se consultan si llueve de forma moderada o más en el barrio: 1 mm o
# más en media hora (2 mm/h, el primer escalón de la escala de intensidad de la
# web) en la red del barrio (Juanjo, 18-10-2026), por si el radar aún no la ve.
RIERA_VEINES_BARRI_MM = 1.0

# Trenes de cerca (trens.py, ADR 0029): línea, operador y dónde para en
# Cerdanyola. Una línea circula si se ha visto un tren suyo moviéndose a
# TRENS_RADI_KM o menos de su estación (TRENS_ESTACIONS) en los últimos
# TRENS_VIST_MIN minutos; fuera de su horario, sin trenes es lo normal. El
# horario es el de cada línea en Cerdanyola (TRENS_HORARI_LINIA: primer y
# último tren, del GTFS de Renfe y de FGC del 08-10-2026, con el primero del
# tipo de día que empieza más tarde), y hasta TRENS_MARGE_INICI_MIN minutos
# después del primer tren no se dice que no circula: el 08-10-2026 a las 05:39
# el bot avisó de que la R7 no circulaba, y su primer tren es a las 06:40
# (ADR 0038). Sin horario propio, TRENS_HORARI.
TRENS = [
    ("R4", "rodalies", "Cerdanyola del Vallès"),
    ("R7", "rodalies", "Cerdanyola Universitat"),
    ("R8", "rodalies", "Cerdanyola Universitat"),
    ("S2", "fgc", "Bellaterra i Universitat Autònoma"),
]
# Lo que pasa alrededor (entorn.py, ADR 0046): incendios forestales en curso
# de Bombers (cuáles, abajo); el Pla Alfa del municipio
# (ALFA_MUNICIPI, código de Agents Rurals), solo si la capa se ha editado en
# las últimas ALFA_ACTUAL_H horas (fuera de campaña se queda con el último
# valor); se muestra desde el nivel ALFA_NIVELL_MOSTRAR, el que restringe el
# acceso a los espacios forestales.
ENTORN_RADI_KM = 2
# Desde el 16-10-2026 (ADR 0071): los de Collserola a cualquier distancia y,
# fuera del parque, los de ENTORN_RADI_KM o menos, sea cual sea el municipio
# (Juanjo: «bájalo a 2 km esté donde esté y luego los del parque»). Del
# 11-10-2026 a esa fecha, los de Cerdanyola siempre y los de los demás
# municipios del parque a 3 km («5km es demasiado»); Ripollet o Sabadell, no. Se piden a
# Bombers los de la caja INCENDIS_CAIXA (lon. mín., lat. mín., lon. máx., lat.
# máx.), que abarca el parque y 6 km alrededor de casa; la posición de cada
# actuación es aproximada: cuenta como parque hasta COLLSEROLA_MARGE_KM fuera.
MUNICIPI = "Cerdanyola del Vallès"
MUNICIPIS_COLLSEROLA = ("Barcelona", "Cerdanyola del Vallès", "Esplugues de Llobregat", "Molins de Rei",
                        "Montcada i Reixac", "el Papiol", "Sant Cugat del Vallès", "Sant Feliu de Llobregat",
                        "Sant Just Desvern")
INCENDIS_CAIXA = (1.99, 41.375, 2.21, 41.54)
COLLSEROLA_MARGE_KM = 0.2
# Un incendio que Bombers deja abierto sin ningún vehículo ni cambio durante
# más de INCENDI_PARAT_H horas se da por apagado (25-10-2026, ADR 0071): los
# anteriores duraron entre 6 minutos y 1 hora.
INCENDI_PARAT_H = 3
ALFA_MUNICIPI = "082665"            # Cerdanyola del Vallès
ALFA_ACTUAL_H = 36
ALFA_NIVELL_MOSTRAR = 3

# Cortes de luz del barrio (llum.py, ADR 0072): las averías y los trabajos
# programados en curso de e-distribución dentro de los límites de Montflorit
# (montflorit-limits.geojson) o a LLUM_MARGE_KM o menos de ellos: el punto que
# da es aproximado. No se dice la calle.
LLUM_MARGE_KM = 0.15

# Tráfico de cerca (transit.py, ADR 0052): las incidencias del Servei Català de
# Trànsit que empiezan a TRANSIT_RADI_KM o menos de casa, en línea recta (AP-7,
# B-30, C-58, C-17, C-33, BV-1414 y BV-1415); desde la 3.33.0, 5 km y no 6
# (Juanjo, 09-10-2026). Las
# retenciones, accidentes y averías salen siempre; las obras, solo si desvían
# o cortan la vía (nivel TRANSIT_NIVELL_OBRES o más, o «tallada» en el texto).
# En «Si surts», si se sale ahora, el coche y la moto pasan a «compte» con una
# incidencia de nivel TRANSIT_NIVELL_SORTIDA o más (3, retenciones; 4,
# congestión; 5, calzada cortada); la «circulació intensa» (2) solo se lista.
TRANSIT_RADI_KM = 5
TRANSIT_NIVELL_OBRES = 3
# Obras sin ubicación precisa: sin punto kilométrico o en un tramo de más de
# TRANSIT_OBRES_TRAM_MAX_KM no dicen dónde está el corte, y no salen (Juanjo,
# 09-10-2026, ante la BV-1414 del km 4 al 0: «si no hay ubicación precisa se
# elimina»).
TRANSIT_OBRES_TRAM_MAX_KM = 2
TRANSIT_NIVELL_SORTIDA = 3

TRENS_ESTACIONS = {"R4": (41.493, 2.148), "R7": (41.497, 2.115), "R8": (41.497, 2.115),
                   "S2": (41.502, 2.091)}
TRENS_RADI_KM = 6
# Las paradas de cada línea de Rodalies, en orden (API de la web de Rodalies,
# lines/<línea>, 18-10-2026). Un aviso de servicio por carretera que nombra un
# tramo solo cuenta si el tramo pasa por la estación de Cerdanyola de la línea
# (el 18-10-2026 la R4 salía «per carretera» por un autobús entre Terrassa
# Nord y Manresa).
TRENS_PARADES = {
    "R4": ["Sant Vicenç de Calders", "El Vendrell", "L'Arboç", "Els Monjos", "Vilafranca del Penedès",
           "La Granada", "Lavern-Subirats", "Sant Sadurní d'Anoia", "Gelida", "Martorell Central",
           "Castellbisbal", "El Papiol", "Molins de Rei", "Sant Feliu de Llobregat", "Sant Joan Despí",
           "Cornellà", "L'Hospitalet de Llobregat", "Barcelona-Sants", "Barcelona-Plaça de Catalunya",
           "Barcelona-Arc de Triomf", "Barcelona-La Sagrera-Meridiana", "Barcelona-Fabra i Puig",
           "Barcelona-Torre Baró", "Vallbona", "Montcada Bifurcació", "Montcada i Reixac-Manresa",
           "Montcada i Reixac-Santa Maria", "Cerdanyola del Vallès", "Barberà del Vallès", "Sabadell Sud",
           "Sabadell Centre", "Sabadell Nord", "Terrassa Est", "Terrassa Estació del Nord",
           "Sant Miquel de Gonteres-Viladecavalls", "Viladecavalls", "Vacarisses-Torreblanca", "Vacarisses",
           "Castellbell i el Vilar-Monistrol de Mont", "Sant Vicenç de Castellet", "Manresa"],
    "R7": ["Barcelona-Fabra i Puig", "Barcelona-Torre Baró", "Vallbona", "Montcada Bifurcació",
           "Montcada i Reixac-Manresa", "Montcada i Reixac-Santa Maria", "Cerdanyola del Vallès",
           "Cerdanyola-Universitat"],
    "R8": ["Martorell Central", "Castellbisbal", "Rubí Can Vallhonrat", "Sant Cugat Coll Favà",
           "Cerdanyola-Universitat", "Santa Perpètua de Mogoda Riera de Caldes", "Mollet-Sant Fost",
           "Montmeló", "Granollers Centre"],
}
TRENS_VIST_MIN = 60
TRENS_HORARI = ("05:30", "23:30")
TRENS_HORARI_LINIA = {"R4": ("05:20", "23:59"), "R7": ("06:35", "22:40"), "R8": ("06:49", "21:50"),
                      "S2": ("05:14", "23:59")}
TRENS_MARGE_INICI_MIN = 30
