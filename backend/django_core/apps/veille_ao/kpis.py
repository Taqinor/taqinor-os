"""VAO31 — ATTRIBUTION : d'où vient réellement le chiffre d'affaires.

Le constat central de l'étude, et la raison d'être de ce module
----------------------------------------------------------------
L'appel d'offres qui a réellement occupé le fondateur n'aurait été capté par
AUCUN dispositif automatique. Il faut donc **MESURER**, sur douze mois, quel
canal rapporte — au lieu de le supposer. C'est la seule façon d'arbitrer
honnêtement entre « payer un agrégateur », « améliorer le collecteur » et
« aller démarcher » (VAO29).

Le tableau est CALCULÉ, jamais saisi
-------------------------------------
Chaque colonne se dérive de données déjà écrites : les avis viennent du sas,
les affaires du lien opaque ``appel_offre_id``, et l'ISSUE (gagné / perdu)
d'``apps.ao`` **par son ``selectors.py``** — jamais par un import de ses
modèles. Un chiffre saisi à la main serait un chiffre qu'on flatte.

Deux axes, pas un
------------------
* par **SOURCE** (portail officiel, tuyau partenaire, import…) — d'où
  l'information est ENTRÉE ;
* par **INFORMATEUR** (partenaire, client, employé, presse) — QUI l'a
  signalée.

Le second est tout l'intérêt de la mesure : c'est lui qui rend visible ce que
la veille automatique ne voit pas, et il apparaît à égalité avec le portail —
jamais en note de bas de page.
"""
from __future__ import annotations

from .models import AvisMarche, Informateur, StatutAvis, TypeSource

#: Les statuts d'avis qui comptent comme « retenus par un humain ».
STATUTS_RETENUS = (StatutAvis.RETENU, StatutAvis.CONVERTI)


def _ligne_vide(cle, libelle):
    return {
        'cle': cle,
        'libelle': libelle,
        'avis': 0,
        'retenus': 0,
        'affaires': 0,
        'gagnes': 0,
        'perdus': 0,
        'en_cours': 0,
    }


def _issues(company, appel_offre_ids):
    """L'issue de chaque affaire — lue par le ``selectors.py`` d'``apps.ao``.

    Import fonction-local ET par le selector : c'est la frontière inter-apps
    du dépôt. Si le module AO venait à disparaître, la mesure DÉGRADE (toutes
    les affaires comptent « en cours ») au lieu de faire tomber l'écran.
    """
    try:
        from apps.ao.selectors import (
            issues_par_ids, statuts_gagnes, statuts_perdus,
        )
    except Exception:  # pragma: no cover - module AO indisponible
        return {}, (), ()
    return (issues_par_ids(company, appel_offre_ids),
            tuple(statuts_gagnes()), tuple(statuts_perdus()))


def _compter(company, avis, cle_de):
    """Agrège les avis selon ``cle_de(avis)`` et croise avec l'issue AO."""
    identifiants = [a.appel_offre_id for a in avis if a.appel_offre_id]
    issues, gagnes, perdus = _issues(company, identifiants)

    lignes = {}
    for un_avis in avis:
        cle, libelle = cle_de(un_avis)
        ligne = lignes.setdefault(cle, _ligne_vide(cle, libelle))
        ligne['avis'] += 1
        if un_avis.statut in STATUTS_RETENUS:
            ligne['retenus'] += 1
        if not un_avis.appel_offre_id:
            continue
        ligne['affaires'] += 1
        statut = issues.get(un_avis.appel_offre_id)
        if statut in gagnes:
            ligne['gagnes'] += 1
        elif statut in perdus:
            ligne['perdus'] += 1
        else:
            ligne['en_cours'] += 1
    return lignes


def _cle_source(un_avis):
    type_source = getattr(un_avis.source, 'type_source', '') or 'inconnue'
    try:
        libelle = TypeSource(type_source).label
    except ValueError:  # pragma: no cover - type retiré de l'énumération
        libelle = type_source
    return type_source, libelle


def _cle_informateur(un_avis):
    if not un_avis.informateur:
        # Un avis COLLECTÉ n'a pas d'informateur : personne ne l'a signalé,
        # une machine l'a lu. Le dire explicitement vaut mieux qu'un blanc.
        return 'collecte_automatique', 'Collecte automatique (personne)'
    try:
        return un_avis.informateur, Informateur(un_avis.informateur).label
    except ValueError:  # pragma: no cover
        return un_avis.informateur, un_avis.informateur


def _toutes_les_cles_source():
    """Les canaux TOUJOURS affichés, même à zéro.

    Un canal absent du tableau se lit « pas mesuré » ; un canal à zéro se lit
    « mesuré, il ne rapporte rien ». La différence est exactement ce que cette
    mesure existe pour établir.
    """
    return [(c, TypeSource(c).label) for c, _ in TypeSource.choices]


def _toutes_les_cles_informateur():
    lignes = [('collecte_automatique', 'Collecte automatique (personne)')]
    lignes += [(c, Informateur(c).label) for c, _ in Informateur.choices]
    return lignes


def _fusionner(lignes, toutes_les_cles):
    """Complète les canaux absents à zéro et rend une liste TRIÉE et stable."""
    for cle, libelle in toutes_les_cles:
        lignes.setdefault(cle, _ligne_vide(cle, libelle))
    return sorted(lignes.values(),
                  key=lambda ligne: (-ligne['gagnes'], -ligne['avis'],
                                     ligne['libelle']))


def attribution(company, depuis=None):
    """« canal → avis → affaires → gagnés », CALCULÉ (jamais saisi).

    ``depuis`` borne la mesure (par défaut : tout l'historique). Rend les deux
    axes plus un total, dans une seule structure — l'écran n'a rien à
    recalculer, et deux écrans ne peuvent donc pas afficher deux chiffres
    différents.
    """
    avis = AvisMarche.objects.filter(company=company).select_related('source')
    if depuis is not None:
        avis = avis.filter(created_at__gte=depuis)
    avis = list(avis)

    par_source = _fusionner(_compter(company, avis, _cle_source),
                            _toutes_les_cles_source())
    par_informateur = _fusionner(_compter(company, avis, _cle_informateur),
                                 _toutes_les_cles_informateur())

    total = _ligne_vide('total', 'Total')
    for ligne in par_source:
        for champ in ('avis', 'retenus', 'affaires', 'gagnes', 'perdus',
                      'en_cours'):
            total[champ] += ligne[champ]

    return {
        'depuis': depuis,
        'par_source': par_source,
        'par_informateur': par_informateur,
        'total': total,
    }
