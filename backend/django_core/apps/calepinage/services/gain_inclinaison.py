"""ACAL706 — ``production.gain_inclinaison`` : de l'horizontale au plan.

Le diagramme de PVsyst part de l'irradiation HORIZONTALE (GlobHor) puis
publie le gain d'inclinaison. Ce n'est pas une étape de ``ORDRE_ETAPES`` :
c'est un bloc de la production. L'horizontale vient d'UNE requête PVGIS à
0° (même base, même fenêtre ; même appel que la série horizontale du
bifacial, ACAL465, donc servi par le cache du client quand il existe),
ramenée à l'année moyenne de la fenêtre. Le plan est la somme des douze
``production.irradiation_mensuelle`` (ACAL451, déjà à l'année moyenne) —
JAMAIS ``cascade.irradiation_incidente_kwh_m2`` (fenêtre ENTIÈRE).

Aucune irradiation supposée : un fichier déposé, une requête refusée ou un
mois du plan inconnu ⇒ valeurs à ``null`` et ``motif_omission`` nommé ; la
simulation continue.
"""
from __future__ import annotations

MOTIF_FICHIER = ("Météo d'un fichier déposé : aucune série horizontale PVGIS "
                 "n'est demandée, le gain d'inclinaison n'est pas publié.")
MOTIF_REFUS = ("La série horizontale PVGIS (inclinaison 0°) n'a pas pu être "
               'obtenue : {motif}')
MOTIF_SANS_POINT = "La série horizontale PVGIS reçue ne porte aucun point."
MOTIF_PLAN_INCOMPLET = ("L'irradiation du plan n'est pas connue pour les "
                        'douze mois : aucune somme partielle n\'est publiée.')

__all__ = ['bloc_vide', 'depuis_serie', 'demander']


def bloc_vide(motif):
    return {'ghi_mensuel': [], 'ghi_annuel_kwh_m2': None,
            'plan_annuel_kwh_m2': None, 'gain_pct': None,
            'motif_omission': motif}


def _nombre(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def depuis_serie(reponse, irradiation_mensuelle):
    """Le bloc, d'après la réponse horizontale et l'irradiation du plan."""
    points = [p for p in (reponse or {}).get('points') or ()
              if isinstance(p, dict)]
    pas = _nombre(((reponse or {}).get('serie_horaire') or {}).get(
        'pas_minutes')) or 60.0
    annees = {p.get('annee') for p in points if p.get('annee') is not None}
    if not points or not annees:
        return bloc_vide(MOTIF_SANS_POINT)
    sommes = dict.fromkeys(range(1, 13), 0.0)
    for point in points:
        valeur = _nombre(point.get('gi_w_m2'))
        if point.get('mois') in sommes and valeur is not None:
            sommes[point['mois']] += valeur * pas / 60.0 / 1000.0
    ghi = [{'mois': mois, 'ghi_kwh_m2': round(sommes[mois] / len(annees), 3)}
           for mois in range(1, 13)]
    ghi_annuel = round(sum(sommes.values()) / len(annees), 3)
    plan = [_nombre(ligne.get('irradiation_plan_kwh_m2'))
            for ligne in irradiation_mensuelle or ()]
    bloc = {'ghi_mensuel': ghi, 'ghi_annuel_kwh_m2': ghi_annuel,
            'plan_annuel_kwh_m2': None, 'gain_pct': None,
            'motif_omission': ''}
    if len(plan) != 12 or None in plan:
        bloc['motif_omission'] = MOTIF_PLAN_INCOMPLET
        return bloc
    bloc['plan_annuel_kwh_m2'] = round(sum(plan), 3)
    if ghi_annuel:
        bloc['gain_pct'] = round((sum(plan) / ghi_annuel - 1.0) * 100.0, 2)
    return bloc


def demander(client, plan, decision, fichier, compteur, production):
    """La requête PVGIS à 0° (comptée), puis le bloc ; jamais une exception."""
    from .pvgis_serie import BASE_PAR_DEFAUT, EntreeInvalide, PvgisIndisponible

    if fichier is not None:
        return bloc_vide(MOTIF_FICHIER)
    debut, fin = (decision.get('fenetre_annees') or (None, None))
    try:
        reponse = client.serie_irradiance(
            lat=plan.get('lat'), lon=plan.get('lon'), inclinaison_deg=0.0,
            aspect_deg=0.0, annee_debut=debut, annee_fin=fin,
            base=BASE_PAR_DEFAUT, composantes=True,
            masque_dans_la_geometrie=True)
    except (EntreeInvalide, PvgisIndisponible) as refus:
        return bloc_vide(MOTIF_REFUS.format(motif=refus))
    if not (reponse or {}).get('depuis_cache'):
        compteur['appels'] = compteur.get('appels', 0) + 1
    return depuis_serie(reponse, (production or {}).get(
        'irradiation_mensuelle'))
