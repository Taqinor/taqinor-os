"""Helpers feuilles du moteur horaire (SPL254, déplacé de ``etude_horaire.py``).

Mois d'été des factures, saison PVGIS d'un mois, flottant tolérant ``_num`` —
les feuilles que les autres modules de ``horaire/`` lisent sans importer
``etude_horaire`` en retour (sens unique, pas de cycle). Déplacement pur :
corps octet-identiques, prouvé par ``tests/golden/split_eh_base.json``.
"""
from apps.parametres.pvgis_profils import MOIS_PAR_SAISON


#: Mois (index 0 = janvier) considérés « été » quand le lead déclare une
#: facture d'été DISTINCTE. Mai→octobre — MÊME découpage que
#: ``apps/ventes/public_views._monthly_consumption``, qui sert déjà la série
#: mensuelle de la page : deux découpages différents feraient diverger l'écran
#: et le moteur sur le même client.
MOIS_ETE_FACTURE = frozenset({4, 5, 6, 7, 8, 9})


#: Mois (1-12) → saison PVGIS, dérivé de ``MOIS_PAR_SAISON`` (source unique :
#: hiver = DJF, mi-saison = MAM+SON, été = JJA). Jamais un second découpage.
_SAISON_DU_MOIS = {
    mois: saison
    for saison, mois_tuple in MOIS_PAR_SAISON.items()
    for mois in mois_tuple
}


def _num(valeur, defaut=0.0):
    """Flottant tolérant — illisible/``None`` → ``defaut``, jamais d'exception."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def saison_du_mois(mois):
    """Saison PVGIS d'un mois 1-12 (``None`` hors bornes)."""
    return _SAISON_DU_MOIS.get(mois)


#: ACAL1169 — la supposition DITE (règle du 17/11) : forme horaire des jours types = profil PVGIS du site.
FORME_HORAIRE_BASE = 'profil PVGIS du site, orientation des pans non prise en compte'
AVERTISSEMENT_FORME_HORAIRE = 'production de la pose réelle ; forme horaire supposée : ' + FORME_HORAIRE_BASE


def serie_de_base_production(base_production, mensuel):
    """ACAL1169 (D-ACAL-36) — ``(mensuel, pertes_incluses)`` : base pertes incluses (12 valeurs) ⇒ elle
    REMPLACE la série de la ville, ni derate ni ombrage réappliqués ; pertes non incluses ⇒ lue comme
    ``productible_kwh_kwc`` (mise à l'échelle) ; sans base ⇒ inchangé."""
    base = base_production if isinstance(base_production, dict) else {}
    serie = base.get('kwh_kwc_mensuel')
    if base and base.get('pertes_incluses') and isinstance(serie, (list, tuple)) and len(serie) == 12:
        return ([_num(v) for v in serie], str(base.get('source') or 'base_production')), True
    if base and mensuel:
        from apps.ventes.horaire.productible_societe import mettre_a_l_echelle
        return mettre_a_l_echelle(mensuel, base.get('kwh_kwc_annuel')), False
    return mensuel, False


def bloc_base_production(base_production):
    """ACAL1169 — la base publiée dans le bloc : ses quatre clés + la forme horaire supposée."""
    cles = ('kwh_kwc_annuel', 'kwh_kwc_mensuel', 'pertes_incluses', 'source')
    return dict({c: base_production.get(c) for c in cles}, forme_horaire=FORME_HORAIRE_BASE)


def publier_base_production(resultat, base_production):
    """ACAL1169 — le bloc ``resultat`` de ``calculer_etude_horaire``, rendu tel quel ; avec une base, il
    porte ``base_production`` et son avertissement de forme horaire (ajouté à ``resultat['avertissements']``)."""
    if base_production:
        resultat['base_production'] = bloc_base_production(base_production)
        resultat['avertissements'].append(AVERTISSEMENT_FORME_HORAIRE)
    return resultat
