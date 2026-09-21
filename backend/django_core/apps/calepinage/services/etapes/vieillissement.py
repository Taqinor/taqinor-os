"""CALX178 — LE VIEILLISSEMENT : une production ANNÉE PAR ANNÉE.

CE MODULE N'EST PAS UNE ÉTAPE HORAIRE — ET C'EST VOULU
--------------------------------------------------------
``vieillissement`` ne figure PAS dans ``chaine_pertes.ORDRE_ETAPES`` : il est
déclaré dans ``POSTES_HORS_CHAINE``, avec sa raison — « la chaîne est celle
de l'ANNÉE 1, et il ne se soustrait pas deux fois ». Ce module n'expose donc
AUCUNE fonction ``appliquer(serie, contexte)`` : le registre des étapes ne
l'appellera jamais, et la cascade horaire ne le verra jamais passer. Il vit
ici parce que c'est le dossier des postes de pertes, et il produit le bloc
``production.annees`` du résultat (contrat CALX4) À PARTIR du résultat de
l'année 1 que la chaîne vient de calculer.

LE CONSTAT
----------
``vieillissement`` était un poste PLAT du catalogue : un pourcentage unique
pour vingt-cinq ans. La fiche porte pourtant ``degradation_annuelle_pct``,
``degradation_annee1_pct``, ``garantie_pct_a_10_ans`` et
``garantie_pct_a_25_ans``, déjà publiés par ``specs_for_produit`` ; et la
seule courbe de dégradation du dépôt vit dans le moteur de devis avec des
littéraux non sourcés qu'``apps.calepinage`` n'importe pas.

LES DEUX MODÈLES, ET AUCUN N'EST SUPPOSÉ
------------------------------------------
PV*SOL décrit deux modèles de dégradation, linéaire et exponentiel
(https://help.valentin-software.com/pvsol/en/pages/pv-modules/
module-degradation/) ; PVsyst en fait un outil de vieillissement dédié avec
une courbe de PR par année
(https://www.pvsyst.com/help/project-design/simulation/ageing-tool.html).
Le modèle se CHOISIT dans le réglage société ``simulation.modele_degradation``
— il n'est jamais deviné.

* ``lineaire``    : ``f(N) = 1 − d1/100 − (N−1) × d/100``
* ``exponentiel`` : ``f(N) = (1 − d1/100) × (1 − d/100)^(N−1)``

``f`` est le facteur de performance du module rapporté à sa puissance de
plaque ; la production publiée est ``p50_annee1 × f(N) / f(1)``, si bien que
l'année 1 vaut EXACTEMENT le résultat de la chaîne : le vieillissement ne se
soustrait pas deux fois.

L'HORIZON — SAISI, OU DÉRIVÉ-TRAÇABLE
---------------------------------------
``simulation.annees_exploitation`` d'abord. À défaut, l'horizon peut être
DÉDUIT de la plus longue garantie de production des modules du système
(``Produit.garantie_production_mois``) : il est alors publié avec
``source: 'derivee_fiche'`` et le NOM du produit qui l'a fixé — une valeur
dérivée-traçable au sens de D-CALX 7. OpenSolar automatise la même déduction
(« Automatically Set Years to Simulate : Toggle ON to automatically simulate
based on the maximum module product warranty among all system options in a
project », et note que la saisie manuelle est « typically 20 years »,
https://support.opensolar.com/hc/en-us/articles/
13155219591183-How-to-adjust-your-simulation-settings) — mais chez nous
« typically 20 » n'est PAS une valeur : ni garantie ni saisie ⇒ le tableau
pluriannuel reste OMIS, et jamais 20 ou 25 ans supposés.

NOTE DE LECTURE : ``garantie_production_mois`` vit sur ``Produit`` et n'est
pas encore publié par ``apps.stock.selectors.specs_for_produit`` ; il est lu
ici DÉFENSIVEMENT, si bien que la déduction reste inerte — et l'horizon
simplement omis — tant que le sélecteur ne le publie pas.

L'ANNÉE EST UN RANG, PAS UN MILLÉSIME : aucune date de mise en service n'est
saisie, et en inventer une ferait écrire un millésime faux sur chaque ligne.

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes

#: Les clés de réglage société lues ici (registre CALX145).
CLE_HORIZON = 'annees_exploitation'
CLE_MODELE = 'modele_degradation'

#: Les deux modèles admis. Un modèle hors de cette table est refusé en le
#: citant : c'est une faute de saisie, pas une absence de saisie.
MODELE_LINEAIRE = 'lineaire'
MODELE_EXPONENTIEL = 'exponentiel'
MODELES = (MODELE_LINEAIRE, MODELE_EXPONENTIEL)

#: Les champs de fiche produit lus — sous les noms que ``specs_for_produit``
#: publie déjà (CAL113).
CHAMP_DEGRADATION = 'degradation_annuelle_pct'
CHAMP_ANNEE1 = 'degradation_annee1_pct'

#: Le champ de garantie qui peut DÉRIVER l'horizon, et son nom de produit.
CHAMP_GARANTIE_MOIS = 'garantie_production_mois'
CHAMPS_NOM_PRODUIT = ('designation', 'nom', 'produit', 'modele')

SOURCE_REGLAGE = 'reglage'
SOURCE_DERIVEE = 'derivee_fiche'
SOURCE_CHAINE = 'chaine'

REFERENCE = (
    'PV*SOL — Module degradation : deux modèles, linéaire et exponentiel '
    '(https://help.valentin-software.com/pvsol/en/pages/pv-modules/'
    'module-degradation/) ; PVsyst — Ageing tool : une courbe de PR par '
    'année (https://www.pvsyst.com/help/project-design/simulation/'
    'ageing-tool.html) ; OpenSolar — Simulation settings : horizon déduit de '
    'la garantie produit maximale des modules '
    '(https://support.opensolar.com/hc/en-us/articles/'
    '13155219591183-How-to-adjust-your-simulation-settings).')

__all__ = ['CLE_HORIZON', 'CLE_MODELE', 'MODELE_LINEAIRE',
           'MODELE_EXPONENTIEL', 'MODELES', 'CHAMP_DEGRADATION',
           'CHAMP_ANNEE1', 'CHAMP_GARANTIE_MOIS', 'SOURCE_REGLAGE',
           'SOURCE_DERIVEE', 'SOURCE_CHAINE', 'REFERENCE',
           'tableau_pluriannuel']


def tableau_pluriannuel(p50_annee1_kwh, contexte):
    """Le bloc ``production.annees`` (CALX4) — ou la seule année 1.

    Args:
        p50_annee1_kwh: le P50 de l'ANNÉE 1, tel que la chaîne de pertes
            vient de le calculer. ``None`` ⇒ rien n'est publié du tout : une
            production inconnue ne se projette pas sur vingt ans.
        contexte: le dict des étapes — ``reglages_simulation``,
            ``fiche_module`` (et, s'il existe, ``fiches_modules``).

    Returns:
        ``{annees, modele, horizon_annees, source_horizon, produit_horizon,
        reference, motif_omission}``. ``annees`` porte toujours au moins
        l'année 1 quand le P50 est connu ; ``motif_omission`` est vide
        seulement quand le tableau PLURIANNUEL a pu être construit.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    p50 = _nombre(p50_annee1_kwh)
    if p50 is None:
        return _bloc([], motif=(
            "La production P50 de l'année 1 n'est pas connue : aucune "
            'projection pluriannuelle n\'est publiée. Une production '
            'inconnue ne se projette pas.'))

    annee1 = [{'annee': 1, 'facteur': None, 'p50_kwh': round(p50, 3),
               'source': SOURCE_CHAINE}]

    fiche = contexte.get('fiche_module')
    fiche = fiche if isinstance(fiche, dict) else {}
    degradation = _pourcentage(fiche.get(CHAMP_DEGRADATION))
    premiere = _pourcentage(fiche.get(CHAMP_ANNEE1))
    manquants = [nom for nom, valeur in ((CHAMP_DEGRADATION, degradation),
                                         (CHAMP_ANNEE1, premiere))
                 if valeur is None]
    if manquants:
        return _bloc(annee1, motif=(
            'La fiche du module ne porte pas sa dégradation : le tableau '
            'pluriannuel est OMIS et seule l\'année 1 est publiée. '
            f'Non renseigné(s) : {_liste("FicheTechnique", manquants)}.'))

    modele, motif = _modele(contexte)
    if modele is None:
        return _bloc(annee1, motif=motif)

    horizon, source_horizon, produit, motif = _horizon(contexte)
    if horizon is None:
        return _bloc(annee1, motif=motif)

    facteurs = _facteurs(modele, degradation, premiere, horizon)
    reference_facteur = facteurs[0]
    annees = []
    for rang, facteur in enumerate(facteurs, start=1):
        ligne = {
            'annee': rang,
            'facteur': round(facteur, 6),
            'p50_kwh': round(p50 * facteur / reference_facteur, 3),
            'source': (SOURCE_CHAINE if rang == 1
                       else f'{modele} — fiche produit'),
        }
        if facteur <= 0.0:
            ligne['plancher'] = True
        annees.append(ligne)
    return _bloc(annees, modele=modele, horizon=horizon,
                 source_horizon=source_horizon, produit=produit)


# ── le modèle, CHOISI ──────────────────────────────────────────────────

def _modele(contexte):
    """``(modele, '')`` ou ``(None, motif)`` — jamais un modèle supposé."""
    saisie = _reglage(contexte, CLE_MODELE)
    if not saisie:
        return None, (
            'Aucun modèle de dégradation choisi : PV*SOL en décrit deux, '
            'linéaire et exponentiel, qui ne donnent pas la même courbe. Le '
            'tableau pluriannuel est OMIS et seule l\'année 1 est publiée. '
            f'Non renseigné : « simulation.{CLE_MODELE} ».')
    lu = str(saisie.get('valeur') or '').strip().lower()
    if lu not in MODELES:
        return None, (
            f'Le modèle de dégradation « {lu} » n\'est pas reconnu : les deux '
            f'modèles admis sont {", ".join(MODELES)}. Le tableau '
            'pluriannuel est OMIS.')
    return lu, ''


# ── l'horizon, saisi ou dérivé-traçable ────────────────────────────────

def _horizon(contexte):
    """``(annees, source, produit, motif)`` — jamais 20 ni 25 supposés."""
    saisie = _reglage(contexte, CLE_HORIZON)
    if saisie:
        annees = _entier(saisie.get('valeur'))
        if annees is not None and annees > 0:
            return annees, SOURCE_REGLAGE, '', ''

    annees, produit = _horizon_de_la_garantie(contexte)
    if annees is not None:
        return annees, SOURCE_DERIVEE, produit, ''

    return None, None, '', (
        "Aucune durée d'exploitation saisie, et aucun module du système ne "
        'porte sa garantie de production : le tableau pluriannuel est OMIS '
        "et seule l'année 1 est publiée. Ni 20 ni 25 ans ne sont supposés. "
        f'Non renseigné : « simulation.{CLE_HORIZON} » ou '
        f'« Produit.{CHAMP_GARANTIE_MOIS} ».')


def _horizon_de_la_garantie(contexte):
    """La plus LONGUE garantie de production des modules, et son produit."""
    meilleur, produit = None, ''
    for fiche in _fiches(contexte):
        mois = _entier(fiche.get(CHAMP_GARANTIE_MOIS))
        if mois is None or mois < 12:
            continue
        annees = mois // 12
        if meilleur is None or annees > meilleur:
            meilleur, produit = annees, _nom_du_produit(fiche)
    return meilleur, produit


def _fiches(contexte):
    """Les fiches des modules du système — la liste, ou la seule connue."""
    plusieurs = contexte.get('fiches_modules')
    if isinstance(plusieurs, (list, tuple)):
        return [fiche for fiche in plusieurs if isinstance(fiche, dict)]
    fiche = contexte.get('fiche_module')
    return [fiche] if isinstance(fiche, dict) else []


def _nom_du_produit(fiche):
    for champ in CHAMPS_NOM_PRODUIT:
        valeur = fiche.get(champ)
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()
    return ''


# ── les facteurs ───────────────────────────────────────────────────────

def _facteurs(modele, degradation, premiere, horizon):
    """La suite des facteurs de performance, année 1 comprise."""
    depart = 1.0 - premiere / 100.0
    facteurs = []
    for rang in range(horizon):
        if modele == MODELE_LINEAIRE:
            facteur = depart - rang * degradation / 100.0
        else:
            facteur = depart * (1.0 - degradation / 100.0) ** rang
        facteurs.append(max(facteur, 0.0))
    return facteurs


# ── lectures ───────────────────────────────────────────────────────────

def _reglage(contexte, cle):
    return _etapes.reglage(contexte, cle)


def _bloc(annees, *, modele=None, horizon=None, source_horizon=None,
          produit='', motif=''):
    return {
        'annees': annees,
        'modele': modele,
        'horizon_annees': horizon,
        'source_horizon': source_horizon,
        'produit_horizon': produit,
        'reference': REFERENCE,
        'motif_omission': motif,
    }


def _liste(prefixe, champs):
    return ', '.join(f'« {prefixe}.{nom} »' for nom in champs)


def _pourcentage(valeur):
    nombre = _nombre(valeur)
    if nombre is None or nombre < 0 or nombre >= 100:
        return None
    return nombre


def _entier(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre
