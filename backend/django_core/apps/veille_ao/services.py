"""Services (écritures / orchestration) du module « Veille appels d'offres ».

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin d'écrire
dans ce module ou d'orchestrer une action passe par une fonction de CE fichier
(jamais en important ``apps.veille_ao.models``/``.views`` directement).

VAO10 — les règles d'exclusion. Le principe qui gouverne tout ce fichier :
**aucun filtrage muet**. Quand une règle écarte un avis, l'avis GARDE la trace
de la règle qui l'a écarté, et la règle compte ses applications. Un utilisateur
doit toujours pouvoir répondre à « pourquoi je ne vois pas cet avis ? » et
faire marche arrière en un geste (désactiver la règle).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .hashing import empreinte_avis
from .models import AvisMarche, PorteeExclusion, RegleExclusion, StatutAvis
from .scoring import normaliser

logger = logging.getLogger(__name__)


def _valeur_de_l_avis(avis, portee):
    """Le champ de l'avis que cette portée compare."""
    if portee == PorteeExclusion.ACHETEUR:
        return avis.acheteur or ''
    if portee == PorteeExclusion.LIBELLE:
        return avis.objet or ''
    if portee == PorteeExclusion.CATEGORIE:
        return avis.categorie or ''
    if portee == PorteeExclusion.REGION:
        return avis.region or ''
    return ''


def regle_mord(regle, avis):
    """Cette règle écarte-t-elle cet avis ?

    La catégorie est comparée à l'IDENTIQUE (c'est une valeur fermée) ; les
    trois autres portées sont des recherches de sous-chaîne normalisées
    (casse, accents et espaces neutralisés).
    """
    cible = normaliser(_valeur_de_l_avis(avis, regle.portee))
    aiguille = normaliser(regle.valeur)
    if not aiguille or not cible:
        return False
    if regle.portee == PorteeExclusion.CATEGORIE:
        return cible == aiguille
    return aiguille in cible


def regles_actives(company):
    """Les règles actives d'UNE société (jamais tous les tenants)."""
    return list(RegleExclusion.objects.filter(company=company).actives())


def regle_correspondante(avis, regles=None):
    """La PREMIÈRE règle active qui écarte cet avis, ou ``None``.

    Lecture pure : ne modifie ni l'avis ni la règle.
    """
    if regles is None:
        regles = regles_actives(avis.company)
    for regle in regles:
        if regle_mord(regle, avis):
            return regle
    return None


def appliquer_regles_exclusion(avis, regles=None, enregistrer=True):
    """Marque l'avis ``ignore`` s'il est capté par une règle active.

    Renvoie la règle appliquée, ou ``None`` si aucune ne mord.

    Deux garanties non négociables :
      * l'avis ENREGISTRE quelle règle l'a filtré (jamais un filtrage muet) ;
      * la règle incrémente son compteur d'application de façon atomique
        (``F()``), jamais par lecture-modification-écriture.
    """
    regle = regle_correspondante(avis, regles)
    if regle is None:
        return None

    avis.statut = StatutAvis.IGNORE
    avis.regle_exclusion = regle
    if enregistrer:
        avis.save(update_fields=['statut', 'regle_exclusion', 'updated_at'])
        RegleExclusion.objects.filter(pk=regle.pk).update(
            compteur_application=F('compteur_application') + 1)
        regle.refresh_from_db(fields=['compteur_application'])
    return regle


def proposer_regle_pour_avis(avis, portee=PorteeExclusion.ACHETEUR):
    """Propose une règle à partir d'un avis — **sans jamais la créer**.

    « Ignorer » doit APPRENDRE, mais l'apprentissage ne se fait pas en
    douce : l'écran propose, l'utilisateur décide. Cette fonction rend un
    brouillon (portée, valeur, motif suggéré) et n'écrit rien en base.

    ``existe_deja`` dit si une règle identique est déjà enregistrée, pour que
    l'écran propose de la RÉACTIVER plutôt que d'en créer une jumelle.
    """
    valeur = (_valeur_de_l_avis(avis, portee) or '').strip()
    libelle_portee = PorteeExclusion(portee).label
    existante = RegleExclusion.objects.filter(
        company=avis.company, portee=portee, valeur=valeur).first()
    return {
        'portee': portee,
        'portee_libelle': libelle_portee,
        'valeur': valeur,
        'motif_suggere': (
            f'Ignoré depuis un avis — {libelle_portee.lower()} « {valeur} »'
            if valeur else ''),
        'existe_deja': existante is not None,
        'regle_existante_id': existante.pk if existante else None,
        'regle_existante_active': (
            existante.actif if existante is not None else None),
    }


def avis_ignores_par(regle):
    """Les avis que CETTE règle a écartés (pour l'écran de la règle)."""
    return AvisMarche.objects.filter(
        company=regle.company, regle_exclusion=regle)


# ─────────────────────────────────────────────────────────────────────────
# VAO11 — dédoublonnage à DEUX niveaux : le cœur de fiabilité du groupe.
# ─────────────────────────────────────────────────────────────────────────

#: Les champs qu'une rectification a le droit de mettre à jour sur un avis
#: déjà connu. Le STATUT n'y est PAS : un avis que l'utilisateur a retenu ou
#: ignoré ne doit jamais être ramené à « nouveau » par une re-collecte.
CHAMPS_RECTIFIABLES = (
    'ref_consultation', 'org_acronyme', 'reference_avis', 'objet',
    'acheteur', 'lieu', 'region', 'procedure', 'categorie', 'lot',
    'date_publication', 'date_limite_remise', 'date_ouverture',
    'montant_estime', 'caution_provisoire', 'url_detail',
)


def calculer_empreinte(donnees):
    """L'empreinte de niveau 2 d'un dictionnaire d'avis."""
    reference = (donnees.get('reference_avis')
                 or donnees.get('ref_consultation') or '')
    return empreinte_avis(
        reference, donnees.get('acheteur') or '',
        donnees.get('date_limite_remise'))


def trouver_avis_existant(company, source, donnees):
    """Le SAS a-t-il déjà cet avis ? Renvoie ``(avis, niveau)``.

    ``niveau`` vaut 1 (identité de portail), 2 (empreinte) ou 0 (inconnu).
    """
    ref = (donnees.get('ref_consultation') or '').strip()
    if ref:
        existant = AvisMarche.objects.filter(
            company=company, source=source, ref_consultation=ref,
            org_acronyme=(donnees.get('org_acronyme') or '')).first()
        if existant is not None:
            return existant, 1

    empreinte = calculer_empreinte(donnees)
    if empreinte:
        # Le filet de niveau 2 traverse les SOURCES à dessein : c'est ainsi
        # qu'un avis saisi à la main fusionne avec le même avis collecté
        # ensuite, au lieu de doubler.
        existant = AvisMarche.objects.filter(
            company=company, empreinte=empreinte).first()
        if existant is not None:
            return existant, 2

    return None, 0


def _journaliser_rectification(avis, changements, niveau):
    """Trace la rectification DANS l'avis — une fusion silencieuse est un
    bug qu'on ne peut plus expliquer trois mois plus tard.
    """
    brutes = dict(avis.donnees_brutes or {})
    historique = list(brutes.get('rectifications') or [])
    historique.append({
        'date': timezone.now().isoformat(),
        'niveau_dedoublonnage': niveau,
        'changements': changements,
    })
    brutes['rectifications'] = historique
    avis.donnees_brutes = brutes
    logger.info(
        'veille_ao: avis %s rectifié (niveau %s) — champs modifiés : %s',
        avis.pk, niveau, ', '.join(sorted(changements)) or 'aucun')


@transaction.atomic
def enregistrer_avis(company, source, donnees):
    """Enregistre UN avis dans le sas, sans jamais créer de doublon.

    Renvoie ``(avis, cree, niveau)`` :
      * ``cree=True`` → un avis neuf a été inséré (``niveau=0``) ;
      * ``cree=False`` → un avis déjà connu a été MIS À JOUR, et ``niveau``
        dit lequel des deux filets l'a reconnu (1 = identité de portail,
        2 = empreinte).

    Une collision de niveau 2 sans collision de niveau 1 — l'avis rectifié
    qui ressort avec un NOUVEL identifiant — met à jour l'existant et
    journalise la rectification, elle ne duplique pas.
    """
    champs = {k: v for k, v in donnees.items()
              if k in CHAMPS_RECTIFIABLES}
    existant, niveau = trouver_avis_existant(company, source, donnees)

    if existant is None:
        avis = AvisMarche(company=company, source=source, **champs)
        avis.empreinte = calculer_empreinte(donnees)
        avis.save()
        return avis, True, 0

    changements = []
    for nom, valeur in champs.items():
        if getattr(existant, nom) != valeur:
            setattr(existant, nom, valeur)
            changements.append(nom)

    nouvelle_empreinte = calculer_empreinte(donnees)
    if nouvelle_empreinte and existant.empreinte != nouvelle_empreinte:
        existant.empreinte = nouvelle_empreinte
        changements.append('empreinte')

    if changements:
        _journaliser_rectification(existant, changements, niveau)
        existant.save()
    return existant, False, niveau
