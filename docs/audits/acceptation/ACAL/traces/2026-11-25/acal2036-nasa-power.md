# Trace — ACAL2036, comparaison NASA POWER en service joignable (25/11/2026, vers 07 h 05 UTC)

Joué par l'orchestrateur sur la pile privée de revue (copie anonymisée, jamais la production), qui servait le commit
`22e6aa81a` (lot 3). Aujourd'hui cette pile sort sur Internet (le 23/11, NASA POWER y était injoignable : URLError).

## 1. Ce que l'ERP sert
Calepinage SYNTHÉTIQUE d'un relecteur (lead d'essai à Casablanca, aucune donnée d'un client de la copie), simulé avec
PVGIS réel, fenêtre 2014 à 2023. `GET /api/django/calepinage/calepinages/<id>/resultat/` (200), bloc `meteo` :

    "comparaison_nasa_power": {"meteo": null,
      "motif": "NASA POWER a refusé la demande (HTTP 422) : la comparaison météo est omise.",
      "annees": [], "ecart_pct": null, "source_comparee": "nasa_power", "source_du_chiffre": "pvgis",
      "irradiation_horizontale_kwh_m2": {"pvgis": 1977.035, "nasa_power": null}}
    "annees": [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]

La simulation a réussi, PVGIS reste la source, le motif est dit en français : le service en refus se comporte comme un
service muet (valeurs `null`, motif, aucune erreur). Mais la comparaison n'est PAS obtenue.

## 2. La cause, prouvée par deux appels directs au service public
Mêmes paramètres que le client (`apps/calepinage/services/nasa_power.py::ClientNasaPower.serie_horizontale`), point de
la ville de Casablanca (33,57 ; −7,59) :

| Demande | Réponse |
|---|---|
| une année, `start=20220101&end=20221231` | HTTP 200, 804 609 octets, série horaire complète |
| dix années, `start=20140101&end=20231231` | HTTP 422 — « The please shorten your requested time extent for a JSON formatted data request. » |

Le client demande toute la fenêtre pluriannuelle en UN appel horaire : le service refuse. Avec la fenêtre par défaut
(dix ans), la comparaison ne peut donc jamais apparaître, même service joignable.

## 3. Service muet
Non rejoué sur ce commit. Relevé le 23/11/2026 par le relecteur T3-VAGUED (`docs/audits/l5-calepinage/T3/T3-VAGUED.md`) :
« injoignable (URLError) », comparaison omise avec motif, simulation réussie — même chemin de code que le refus ci-dessus.

## 4. Verdict et suite
- ACAL2036 (le rejeu) : FAIT — réponse relevée en service joignable ; écart nommé.
- ACAL746 : clause « deux irradiations et un écart en pourcent » NON tenue en service joignable → reste « code livré »,
  écart porté par la tâche ACAL2043 (demander au service une étendue qu'il accepte). La moitié écran d'ACAL746 (bandeau
  de provenance de la production) reste absente, comme déjà noté dans la ligne d'ACAL2036.
