"""PACT118 — cibles RÉELLES d'édition en masse déclarées par l'app CPQ.

CONSTAT À L'ORIGINE DE CE FICHIER : le moteur générique du socle
(``core.bulk_edit``) existait, était testé… et **aucune app ne l'avait jamais
branché** — ``register_bulk_target`` n'était appelé que depuis les tests du
socle. Le registre était donc vide en production : l'endpoint
``GET core/bulk-edit/targets/`` renvoyait une liste vide et aucun écran ne
pouvait s'en servir.

Ce module DÉCLARE trois cibles réelles côté CPQ (l'app qui connaît ses
modèles) ; le socle ne connaît toujours aucune app métier — le sens de la
dépendance reste ``cpq → core``, jamais l'inverse (contrat import-linter
``core-foundation-is-a-base-layer``).

Chaque cible fournit un ``queryset_provider(company, user)`` DÉJÀ scopé
société : la sécurité multi-tenant reste chez l'app propriétaire, exactement
comme ``apps/sav/bi_datasets.py`` le fait pour l'explorateur de données.

Listes blanches VOLONTAIREMENT étroites : seuls des champs de PARAMÉTRAGE
(statut d'activation, type de contrainte, message affiché). Aucun champ de
PRIX n'est modifiable en masse — une erreur de saisie groupée sur un prix se
propagerait silencieusement à des devis.
"""


def offres_groupees_queryset(company, user):
    """``cpq.OffreGroupee`` scopées société (import local : évite de charger
    les modèles à l'import du module, appelé depuis ``apps.py``)."""
    from .models import OffreGroupee
    return OffreGroupee.objects.filter(company=company)


def questions_configurateur_queryset(company, user):
    """``cpq.QuestionConfigurateur`` scopées société."""
    from .models import QuestionConfigurateur
    return QuestionConfigurateur.objects.filter(company=company)


def contraintes_compatibilite_queryset(company, user):
    """``cpq.ContrainteCompatibilite`` scopées société."""
    from .models import ContrainteCompatibilite
    return ContrainteCompatibilite.objects.filter(company=company)


# {nom logique: (libellé, champs modifiables, fournisseur de queryset)}
CIBLES = {
    'cpq.offre-groupee': (
        'Offres groupées', ['actif'], offres_groupees_queryset),
    'cpq.question-configurateur': (
        'Questions du configurateur', ['actif', 'ordre'],
        questions_configurateur_queryset),
    'cpq.contrainte-compatibilite': (
        'Contraintes de compatibilité', ['type', 'message_utilisateur'],
        contraintes_compatibilite_queryset),
}


def register_bulk_targets():
    """Enregistre les cibles CPQ dans ``core.bulk_edit``.

    Idempotent : ``register_bulk_target`` remplace l'entrée existante sans
    erreur — appelable plusieurs fois (``ready()``, tests) sans effet de bord.
    """
    from core import bulk_edit
    for nom, (libelle, champs, provider) in CIBLES.items():
        bulk_edit.register_bulk_target(nom, libelle, champs, provider)
