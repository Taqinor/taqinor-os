"""PARAM-CADENCE — la chaîne après l'appel et autour de la visite, lue dans
Paramètres (décision fondateur du 25/09/2026 : « cette cadence doit être dans
Paramètres, pour qu'une autre société ou nous puissions tout y changer »).

Le moteur (``services.py``, ``suite_touche.py``) posait et RECONNAISSAIT ces
étapes par leur LIBELLÉ codé en dur. Ce module est le seul pont entre lui et
les deux gabarits de Paramètres (``parametres.CadenceRelanceEtape``, cadences
``apres_contact`` et ``visite``) :

* ``etape_configuree`` — ce que la société a réglé pour une CLÉ (libellé,
  délai, canal, heure, gabarit de message), avec repli sur le défaut du gabarit ;
* ``est_etape`` / ``cle_de`` / ``q_etape`` — LE prédicat qui remplace toute
  comparaison de libellé : une étape posée depuis la clé porte ``cle`` ; une
  étape posée AVANT la clé (``cle`` vide) est reconnue par son libellé par
  DÉFAUT — jamais par un libellé renommé ;
* ``cles_actives`` — la même lecture, sans rien écrire (pour les promesses
  d'écran, qui ne doivent jamais seeder).

Petit et sans effet de bord, sauf le seed à la volée d'une cadence vide
(``CadenceRelanceEtape.barreau_par_cle``, même règle que ``cadence_pour``).
"""
from django.db.models import Q

from apps.parametres.models_relance import (
    CADENCES_DEFAUT, CLE_APPEL_APRES_REPONSE, CLE_CONFIRMATION, CLE_DEBRIEF,
    CLE_DECIDER_SUITE, CLE_DERNIER_APPEL, CLE_DEVIS, CLE_DEVIS_MODIFIE,
    CLE_MESSAGE_CRENEAU, CLE_PLANIFIER, CLE_RAPPEL_CONVENU, CLES_PALIERS,
    Cadence, CadenceRelanceEtape, barreau_par_defaut,
)

__all__ = [
    'CADENCE_DE_LA_CLE', 'CLES_APRES_CONTACT', 'CLES_VISITE', 'CLES_PALIERS',
    'CLE_APPEL_APRES_REPONSE', 'CLE_CONFIRMATION', 'CLE_DEBRIEF',
    'CLE_DECIDER_SUITE', 'CLE_DERNIER_APPEL', 'CLE_DEVIS',
    'CLE_DEVIS_MODIFIE', 'CLE_MESSAGE_CRENEAU', 'CLE_PLANIFIER',
    'CLE_RAPPEL_CONVENU', 'LIBELLE_DEVIS_ANCIEN', 'cle_de', 'cles_actives',
    'config_cle', 'est_etape', 'etape_configuree', 'libelles_par_defaut',
    'palier_actif', 'q_etape',
]

#: Les clés de chaque gabarit du moteur, dans l'ordre du gabarit.
CLES_APRES_CONTACT = tuple(
    e['cle'] for e in CADENCES_DEFAUT[Cadence.APRES_CONTACT])
CLES_VISITE = tuple(e['cle'] for e in CADENCES_DEFAUT[Cadence.VISITE])

#: Chaque clé n'existe que dans UNE cadence de gabarit.
CADENCE_DE_LA_CLE = {
    **{cle: Cadence.APRES_CONTACT for cle in CLES_APRES_CONTACT},
    **{cle: Cadence.VISITE for cle in CLES_VISITE},
}

#: RELANCE-SUITE (08/09/2026) — l'ancien libellé de l'étape devis, encore
#: porté par des étapes posées avant le 08/09 : coché, il vaut « devis
#: parti » exactement comme le nouveau. Reconnu comme un libellé par défaut
#: de la clé ``devis``, jamais posé.
LIBELLE_DEVIS_ANCIEN = 'Prochaine étape — envoyer le devis ou fixer un rappel'
_LIBELLES_ANCIENS = {CLE_DEVIS: (LIBELLE_DEVIS_ANCIEN,)}


def libelles_par_defaut(*cles):
    """Les libellés PAR DÉFAUT (gabarit livré) de ces clés, anciens libellés
    compris — ceux que portent les étapes posées avant la clé."""
    libelles = set()
    for cle in cles:
        defaut = barreau_par_defaut(CADENCE_DE_LA_CLE.get(cle), cle)
        if defaut is not None:
            libelles.add(defaut['libelle'])
        libelles.update(_LIBELLES_ANCIENS.get(cle, ()))
    return frozenset(libelles)


#: Libellé par défaut → clé (pour les étapes posées avant la clé).
_CLE_PAR_LIBELLE_DEFAUT = {
    libelle: cle
    for cle in CLES_APRES_CONTACT + CLES_VISITE
    for libelle in libelles_par_defaut(cle)
}


def cle_de(etape):
    """La clé moteur de ``etape`` : sa ``cle`` si elle en porte une, sinon
    celle que désigne son libellé PAR DÉFAUT (étape posée avant la clé),
    sinon ``''`` (barreau du protocole, étape hors gabarit)."""
    if etape is None:
        return ''
    cle = (getattr(etape, 'cle', '') or '').strip()
    if cle:
        return cle
    return _CLE_PAR_LIBELLE_DEFAUT.get((etape.libelle or '').strip(), '')


def est_etape(etape, *cles):
    """LE prédicat de reconnaissance du moteur : ``etape`` est-elle l'une de
    ces étapes ? Par sa clé ; à défaut de clé, par son libellé par DÉFAUT —
    jamais par un libellé qu'une société aurait renommé."""
    cle = cle_de(etape)
    return bool(cle) and cle in cles


def q_etape(*cles):
    """Le même prédicat, en requête : ``Q(cle__in=…) | Q(cle='',
    libelle__in=<libellés par défaut>)``."""
    return (Q(cle__in=cles)
            | Q(cle='', libelle__in=tuple(libelles_par_defaut(*cles))))


def _depuis_barreau(barreau):
    return {
        'libelle': barreau.libelle,
        'delai_jours': barreau.delai_jours or 0,
        'delai_minutes': barreau.delai_minutes or 0,
        'heure_cible': barreau.heure_cible,
        'canal': barreau.canal,
        'template_cle': barreau.template_cle or '',
        # D1 — ces deux drapeaux étaient LUS sur le barreau (l'écran les
        # enregistre bien) mais jamais RENDUS ici : une société qui cochait
        # « Samedi » sur un barreau moteur (message_creneau…) le voyait
        # ignoré, exactement comme le protocole le fait pour les siens
        # (`calculer_echeances_cadence`).
        'dimanche_ok': bool(barreau.dimanche_ok),
        'samedi_ok': bool(barreau.samedi_ok),
    }


def etape_configuree(company, cadence, cle):
    """Ce que ``company`` a réglé pour l'étape ``cle`` de ``cadence``.

    ``dict(cle, libelle, delai_jours, delai_minutes, heure_cible, canal,
    template_cle, dimanche_ok, samedi_ok, actif)``, lu dans son barreau
    (``barreau_par_cle``, seedé à la volée si la cadence est vide). Barreau
    SUPPRIMÉ ou DÉSACTIVÉ : le défaut livré de ``CADENCES_DEFAUT`` — avec
    ``actif=True`` pour un PILIER (la chaîne ne tient pas sans lui) et
    ``actif=False`` pour un PALIER optionnel (l'appelant le SAUTE)."""
    barreau = CadenceRelanceEtape.barreau_par_cle(
        company, cadence, cle, inactif_ok=True)
    if barreau is not None and barreau.actif:
        config = _depuis_barreau(barreau)
        config['actif'] = True
    else:
        defaut = barreau_par_defaut(cadence, cle) or {}
        config = {
            'libelle': defaut.get('libelle', ''),
            'delai_jours': defaut.get('delai_jours', 0),
            'delai_minutes': defaut.get('delai_minutes', 0),
            'heure_cible': defaut.get('heure_cible'),
            'canal': defaut.get('canal', 'appel'),
            'template_cle': defaut.get('template_cle', ''),
            'dimanche_ok': defaut.get('dimanche_ok', False),
            'samedi_ok': defaut.get('samedi_ok', False),
            'actif': cle not in CLES_PALIERS,
        }
    config['cle'] = cle
    return config


def config_cle(company, cle):
    """``etape_configuree`` pour une clé du moteur, sa cadence déduite."""
    return etape_configuree(company, CADENCE_DE_LA_CLE[cle], cle)


def cles_actives(company_id, cadence):
    """LECTURE PURE — les clés des barreaux ACTIFS de ``cadence`` pour la
    société, SANS RIEN ÉCRIRE : une cadence encore vide est lue comme son
    gabarit par défaut (tout actif), exactement ce que le seed à la volée
    poserait. UNE requête."""
    lignes = list(CadenceRelanceEtape.objects.filter(
        company_id=company_id, cadence=cadence,
    ).values_list('cle', 'actif'))
    if not lignes:
        return frozenset(e['cle'] for e in CADENCES_DEFAUT.get(cadence, []))
    return frozenset(cle for cle, actif in lignes if actif and cle)


def palier_actif(cle, actives):
    """Un palier optionnel est-il à poser ? (Un pilier l'est toujours.)"""
    return cle not in CLES_PALIERS or cle in actives
