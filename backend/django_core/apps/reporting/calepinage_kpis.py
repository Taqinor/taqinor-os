"""CAL218 — LES indicateurs calepinage, pour le reporting qui existe déjà.

AUCUN TABLEAU DE BORD NEUF, AUCUNE ROUTE NEUVE
-----------------------------------------------
Le hub Rapports a déjà ses fabriques (``reports.py``, ``rapport_builder.py``)
et son endpoint KPI fédéré (``reports.kpi_federes``, ARC40) : le module
calepinage n'a pas besoin d'un écran de pilotage à lui, seulement d'une SOURCE
DE CHIFFRES. Ce fichier est cette source — une fonction d'agrégat
(``indicateurs_calepinage``) et son adaptateur en tuiles normalisées
(``kpi_calepinage``) que le KPI fédéré consomme comme n'importe quel autre
provider déclaré.

FRONTIÈRE INTER-APPS
--------------------
Toutes les lectures passent par ``apps.calepinage.selectors`` — jamais
``apps.calepinage.models``, jamais une vue. Le statut du devis lié est lu par
le REGISTRE (``apps.get_model('ventes', 'Devis').Statut``), donc sans import
statique et surtout sans littéral ``'accepte'`` recopié à la main.

ZÉRO CHIFFRE INVENTÉ (règle fondateur)
---------------------------------------
Tout ici est un COMPTEUR ou une DURÉE mesurée sur des dates réelles. Aucune
cible, aucun seuil, aucun lissage, aucune extrapolation, aucune projection.
Et la distinction est tenue dans les deux sens :

* un COMPTEUR sans donnée vaut ``0`` — c'est une information exacte
  (« aucun calepinage sur la période ») ;
* une MOYENNE, une MÉDIANE ou un TAUX sans échantillon vaut ``None`` — ce
  n'est PAS ``0`` : un délai moyen de zéro jour ou un taux de 0 % se lirait
  comme une mesure alors que rien n'a été mesuré. C'est exactement l'erreur
  que ce fichier refuse de commettre.
"""
from __future__ import annotations

from statistics import fmean, median

#: La clé de module du calepinage (``apps/calepinage/platform.py``) : sert à
#: n'exposer ces tuiles qu'aux sociétés chez qui le module est ACTIF.
MODULE_CALEPINAGE = 'calepinage'


def indicateurs_calepinage(company, *, debut=None, fin=None):
    """Les indicateurs calepinage de ``company``, bornés à une période.

    Args:
        company: la société — TOUJOURS celle passée. ``None`` rend un agrégat
            entièrement vide (le selector renvoie déjà un queryset vide : un
            filtre absent ne se mue jamais en absence de filtre).
        debut / fin: bornes sur la date de CRÉATION du calepinage
            (``fin`` exclusive). Absentes ⇒ tout l'historique.

    Returns:
        dict — voir la docstring du module pour la règle compteur/mesure.
    """
    from apps.calepinage.selectors import liste_calepinages

    lignes = liste_calepinages(company, depuis=debut)
    if fin is not None:
        lignes = lignes.filter(created_at__lt=fin)
    rangs = list(lignes.select_related('devis'))

    statut_accepte = _statut_devis_accepte()
    par_statut = _compteurs_par_statut(lignes, rangs)

    kwc_mesures = [v for v in (_kwc(ligne) for ligne in rangs) if v is not None]
    delais = [j for j in (_delai_jours(ligne) for ligne in rangs)
              if j is not None]
    avec_devis = sum(1 for ligne in rangs if ligne.devis_id)
    signes = sum(1 for ligne in rangs
                 if getattr(ligne.devis, 'statut', None) == statut_accepte)

    return {
        'periode': {'debut': debut, 'fin': fin},
        'total': len(rangs),
        'par_statut': par_statut,
        # Somme des kWc RÉELLEMENT calculés par le moteur ; `mesures` dit sur
        # combien de calepinages elle porte — sans quoi un total bas serait
        # illisible (peu de projets ? ou beaucoup de projets non calculés ?).
        'kwc_concus': round(sum(kwc_mesures), 2),
        'kwc_mesures': len(kwc_mesures),
        'delai_conception_devis_jours': {
            'echantillon': len(delais),
            'moyenne': round(fmean(delais), 1) if delais else None,
            'mediane': round(median(delais), 1) if delais else None,
        },
        'conversion_devis': {
            'avec_devis': avec_devis,
            'devis_signes': signes,
            # Taux SUR LES CALEPINAGES de la période. Sans aucun calepinage,
            # le taux n'existe pas (`None`) — il ne vaut pas 0 %.
            'taux_signature_pct': (round(100.0 * signes / len(rangs), 1)
                                   if rangs else None),
        },
    }


def kpi_calepinage(company):
    """Tuiles normalisées ``{id, label, valeur, unite?}`` pour ``kpi_federes``.

    Le format est celui, existant, du KPI fédéré (ARC40) : ce module ne crée
    donc NI écran NI route — il alimente le hub Rapports déjà en place.

    Gaté ``ModuleToggle`` : une société chez qui le module calepinage est
    désactivé ne reçoit AUCUNE tuile, exactement comme si le provider était
    déclaré dans le manifeste du calepinage lui-même.
    """
    if company is None or not _module_actif(company):
        return []
    chiffres = indicateurs_calepinage(company)
    tuiles = [
        {'id': 'calepinage_total', 'label': 'Calepinages',
         'valeur': chiffres['total']},
        {'id': 'calepinage_kwc_concus', 'label': 'kWc conçus',
         'valeur': chiffres['kwc_concus'], 'unite': 'kWc'},
        {'id': 'calepinage_devis_signes',
         'label': 'Calepinages devenus devis signés',
         'valeur': chiffres['conversion_devis']['devis_signes']},
    ]
    mediane = chiffres['delai_conception_devis_jours']['mediane']
    if mediane is not None:
        # Aucun échantillon ⇒ AUCUNE tuile : afficher « 0 jour » mentirait.
        tuiles.append({'id': 'calepinage_delai_devis_median',
                       'label': 'Délai médian conception → devis',
                       'valeur': mediane, 'unite': 'jours'})
    return tuiles


# ── Détail (privé) ───────────────────────────────────────────────────────────

def _module_actif(company):
    from core import platform as core_platform
    return MODULE_CALEPINAGE in core_platform.platform_manifests_for_company(
        company)


def _statut_devis_accepte():
    """Le code « accepté » du devis, LU du modèle (jamais un littéral).

    Par le registre : le reporting n'importe pas ``apps.ventes.models``, et
    un renommage du code serait suivi ici sans rien à corriger.
    """
    from django.apps import apps as django_apps
    try:
        return django_apps.get_model('ventes', 'Devis').Statut.ACCEPTE
    except (LookupError, AttributeError):  # pragma: no cover — ventes absent
        return None


def _compteurs_par_statut(queryset, rangs):
    """Un compteur par statut DÉCLARÉ, y compris à zéro.

    Les statuts viennent du champ lui-même (via le modèle du queryset rendu
    par le selector) : aucune liste recopiée qui pourrait diverger. Un statut
    sans aucun calepinage vaut ``0`` — c'est un compteur exact, pas un trou.
    """
    compteurs = {}
    try:
        choix = queryset.model._meta.get_field('statut').choices or []
        compteurs = {code: 0 for code, _libelle in choix}
    except Exception:  # noqa: BLE001 — jamais un 500 pour un champ déplacé
        compteurs = {}
    for ligne in rangs:
        statut = getattr(ligne, 'statut', '') or ''
        compteurs[statut] = compteurs.get(statut, 0) + 1
    return compteurs


def _kwc(calepinage):
    """Les kWc RÉELLEMENT calculés par le moteur, ou ``None``."""
    resultat = getattr(calepinage, 'resultat', None)
    if not isinstance(resultat, dict):
        return None
    valeur = resultat.get('kwc')
    if valeur is None or isinstance(valeur, bool):
        return None
    return float(valeur) if isinstance(valeur, (int, float)) else None


def _delai_jours(calepinage):
    """Jours entre la CRÉATION du calepinage et celle de son devis.

    ``None`` dès qu'une des deux dates manque — et ``None`` aussi si le devis
    précède le calepinage (cas réel : un calepinage créé APRÈS coup sur un
    devis existant). Un délai négatif n'est pas un délai de conception : le
    compter aplatirait la moyenne avec une durée qui n'a pas eu lieu.
    """
    devis = getattr(calepinage, 'devis', None)
    debut = getattr(calepinage, 'created_at', None)
    fin = getattr(devis, 'date_creation', None)
    if debut is None or fin is None:
        return None
    jours = (fin - debut).total_seconds() / 86400.0
    return jours if jours >= 0 else None
