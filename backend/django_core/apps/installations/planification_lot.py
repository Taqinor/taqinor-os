"""XFSM2/APRF41 — calcul des propositions de créneau + technicien.

`selectors.suggerer_creneau` (un chantier) et `suggerer_creneaux_lot` (N
chantiers, replanification en masse XFSM3) partagent le même noyau :
`contexte_planification` charge UNE fois les ressources de la fenêtre de
recherche (occupation ACHT39, indisponibilités FG302), puis
`propositions_chantier` classe les candidats d'un chantier en mémoire, sans
aucune requête. Les deux chemins donnent donc les mêmes propositions, et le lot
coûte le même nombre de requêtes quel que soit le nombre d'interventions.
Lecture seule, scopée société.
"""
import datetime

from .selectors import (
    _haversine_km, _techniciens_eligibles, interventions_actives, membres_intervention,
)


def duree_valide(duree_jours):
    """Durée du créneau en jours ouvrés (>= 1 ; valeur illisible → 1)."""
    try:
        return max(int(duree_jours or 1), 1)
    except (TypeError, ValueError):
        return 1


def contexte_planification(company, techniciens, date_cible, duree_jours):
    """Ressources de la fenêtre de recherche, chargées UNE fois : occupation
    (ACHT39 : `interventions_actives`, équipe canonique résolue) `par_jour` /
    `occupe`, et indisponibilités FG302 par technicien (`indispos`) — mêmes
    lignes que `ressource_indisponible` (technicien, société, chevauchement)."""
    from .models import IndisponibiliteRessource

    fin_fenetre = date_cible + datetime.timedelta(days=14 + duree_jours * 2 + 4)
    par_jour, occupe, indispos = {}, {}, {}
    for iv in interventions_actives(
            company, date_cible, fin_fenetre).select_related('installation'):
        par_jour.setdefault(iv.date_prevue, []).append(iv)
        for membre_id in membres_intervention(iv):
            occupe.setdefault(membre_id, []).append(iv.date_prevue)
    lignes = IndisponibiliteRessource.objects.filter(
        company=company, technicien_id__in=[t.id for t in techniciens],
        date_debut__lte=fin_fenetre, date_fin__gte=date_cible,
    ).values_list('technicien_id', 'date_debut', 'date_fin')
    for tech_id, debut, fin in lignes:
        indispos.setdefault(tech_id, []).append((debut, fin))
    return {'techniciens': techniciens, 'par_jour': par_jour,
            'occupe': occupe, 'indispos': indispos}


def _bloc(depart, duree_jours):
    """ACHT39 — un créneau de `duree_jours` s'étale sur autant de jours OUVRÉS
    (le jour de départ ouvre le bloc ; 1 jour = ce seul jour)."""
    jours, courant = [depart], depart
    while len(jours) < duree_jours:
        courant += datetime.timedelta(days=1)
        if courant.weekday() < 5:
            jours.append(courant)
    return jours


def _distance_au_site(chantier, interventions_du_jour):
    """Distance au site la plus courte parmi les interventions déjà planifiées
    CE JOUR (toute ressource) — None sans GPS (jamais d'exception)."""
    site_lat = getattr(chantier, 'gps_lat', None)
    site_lng = getattr(chantier, 'gps_lng', None)
    if site_lat is None or site_lng is None:
        return None
    distance = None
    for iv in interventions_du_jour:
        autre_lat = getattr(iv.installation, 'gps_lat', None)
        autre_lng = getattr(iv.installation, 'gps_lng', None)
        if autre_lat is None or autre_lng is None:
            continue
        d = _haversine_km(site_lat, site_lng, autre_lat, autre_lng)
        if distance is None or d < distance:
            distance = d
    return distance


def propositions_chantier(chantier, ctx, date_cible, duree_jours, n):
    """Les `n` meilleures propositions pour UN chantier, en mémoire sur `ctx`,
    classées par charge (FG299), distance, date puis nom ; un technicien
    indisponible (FG302) ou déjà occupé (FG300) sur un jour du bloc n'est
    jamais proposé. Fenêtre : 14 jours calendaires à partir de `date_cible`."""
    occupe, indispos = ctx['occupe'], ctx['indispos']
    candidats = []
    for decalage in range(14):
        jour = date_cible + datetime.timedelta(days=decalage)
        bloc = _bloc(jour, duree_jours)
        distance = _distance_au_site(chantier, ctx['par_jour'].get(jour, []))
        for tech in ctx['techniciens']:
            if any(d <= j <= f for j in bloc for d, f in indispos.get(tech.id, ())):
                continue
            if set(occupe.get(tech.id, ())) & set(bloc):
                continue
            charge = sum(1 for j in occupe.get(tech.id, ())
                         if jour <= j < jour + datetime.timedelta(days=14))
            candidats.append({
                'technicien_id': tech.id,
                'nom': (getattr(tech, 'get_full_name', lambda: '')() or tech.username),
                'date': jour.isoformat(),
                'charge': charge,
                'distance_km': round(distance, 1) if distance is not None else None,
            })
    candidats.sort(key=lambda c: (
        c['charge'],
        c['distance_km'] if c['distance_km'] is not None else float('inf'),
        c['date'], c['nom'].lower()))
    return candidats[:max(int(n or 3), 1)]


def suggerer_creneaux_lot(company, chantier_ids, *, duree_jours=1, date_cible=None, n=10):
    """APRF41 — `suggerer_creneau` pour PLUSIEURS chantiers d'un coup : les
    techniciens éligibles, les indisponibilités, la charge et les interventions
    de la fenêtre sont chargés UNE fois pour tout le lot, puis le calcul se fait
    en mémoire par chantier. Mêmes propositions que l'appel unitaire.
    Renvoie `{chantier_id: {'chantier_id', 'propositions'}}` (un chantier
    inconnu de la société a `propositions: []`)."""
    from .models import Installation

    ids = list(dict.fromkeys(chantier_ids))
    resultat = {cid: {'chantier_id': cid, 'propositions': []} for cid in ids}
    techniciens = _techniciens_eligibles(company) if ids else []
    if not techniciens:
        return resultat
    date_cible = date_cible or datetime.date.today()
    duree_jours = duree_valide(duree_jours)
    ctx = contexte_planification(company, techniciens, date_cible, duree_jours)
    for chantier in Installation.objects.filter(company=company, id__in=ids).select_related('client'):
        resultat[chantier.id]['propositions'] = propositions_chantier(
            chantier, ctx, date_cible, duree_jours, n)
    return resultat
