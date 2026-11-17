"""Déléguer ses dossiers (fondateur, 17/11/2026) — « mes leads deviennent ceux
de Meryem », en un geste.

Une touche de relance n'a PAS de responsable propre : l'écran la montre au
responsable de son lead. Changer le responsable des leads déplace donc leurs
touches ouvertes. Le geste passe par ``reattribuer_lead`` (jamais un
``update()``) : le nouveau responsable est notifié de ce qu'il hérite, la
touche de passation « prévenir le client » est posée sur un dossier déjà
contacté, la file est recalée.

PÉRIMÈTRE — « tout ce qui peut encore produire une tâche » : les leads de
``de`` ni perdus, ni archivés, ni opposés (``ne_plus_contacter``), ni
supprimés (le gestionnaire ``objects`` les exclut), et dont l'étape n'est pas
SIGNÉ. Les leads Froid suivent donc, qu'ils aient une touche ouverte ou non :
un réveil futur leur en créera une.
"""
from django.db import transaction
from django.db.models import Count, Q

from . import activity, stages
from .cadence_plan import sync_relance_activity
from .cadence_reponses import reattribuer_lead


class DelegationRefusee(Exception):
    """Refus NOMMÉ : ``champ`` dit sous quel champ l'écran l'affiche,
    ``statut`` le code HTTP : 400 valeur mal formée, 403 hors portée, 404 collègue
    introuvable, 409 état (compte désactivé, même personne) — ENF11."""

    def __init__(self, champ, message, statut=400):
        super().__init__(message)
        self.champ = champ
        self.message = message
        self.statut = statut


def _utilisateur_de_la_societe(company, valeur, champ):
    from authentication.models import CustomUser

    if isinstance(valeur, bool) or not isinstance(valeur, (int, str)):
        raise DelegationRefusee(champ, 'Collègue invalide.')
    try:
        pk = int(valeur)
    except (TypeError, ValueError):
        raise DelegationRefusee(champ, 'Collègue invalide.') from None
    cible = CustomUser.objects.filter(pk=pk, company=company).first()
    if cible is None:
        raise DelegationRefusee(
            champ, 'Collègue introuvable dans cette société.', statut=404)
    return cible


def resoudre_delegation(user, corps, *, exiger_vers=True):
    """``(de, vers)`` validés : société, portée, cible active, ``de`` ≠ ``vers``.

    ``de`` absent = l'appelant. ``de`` ≠ appelant exige que ``de`` soit dans la
    portée de visibilité de l'appelant (``visible_user_ids`` — la règle du CRM,
    ``None`` = tout)."""
    from core.scoping import visible_user_ids

    company = user.company
    brut_vers = corps.get('vers')
    # Aperçu sans cible (GET nu) : les chiffres de ce qui partirait.
    vers = (None if not exiger_vers and brut_vers in (None, '', 'null')
            else _utilisateur_de_la_societe(company, brut_vers, 'vers'))
    brut_de = corps.get('de')
    de = (user if brut_de in (None, '', 'null')
          else _utilisateur_de_la_societe(company, brut_de, 'de'))
    # ENF11 — un ÉTAT (compte désactivé, même personne) est un 409, jamais un 400.
    if vers is not None and not vers.is_active:
        raise DelegationRefusee(
            'vers', 'Ce collègue est désactivé : choisissez un compte actif.',
            statut=409)
    if vers is not None and de.pk == vers.pk:
        raise DelegationRefusee(
            'vers', 'Ces dossiers appartiennent déjà à cette personne : '
                    'choisissez un autre collègue.', statut=409)
    if de.pk != user.pk:
        visibles = visible_user_ids(user)
        if visibles is not None and de.pk not in visibles:
            raise DelegationRefusee(
                'de', "Vous ne pouvez déléguer que les dossiers de votre "
                      "périmètre.", statut=403)
    return de, vers


def leads_a_deleguer(user, de):
    """Les leads de ``de`` (société de ``user``, portée de ``user``) qui
    peuvent encore produire une tâche. UNE définition : l'aperçu et l'écriture
    la lisent toutes les deux."""
    from .portee_selectors import leads_visibles

    return leads_visibles(user, user.company).filter(
        owner=de, perdu=False, is_archived=False, ne_plus_contacter=False,
    ).exclude(stage=stages.SIGNED)


def apercu_delegation(user, de):
    """Les trois chiffres de la boîte de dialogue : dossiers, touches ouvertes
    (``a_faire``), dont en retard (le seuil unique du contrôle du suivi)."""
    from core.dates import aujourd_hui_local

    from .controle_suivi import seuil_retard
    from .models import RelanceEtape

    leads = leads_a_deleguer(user, de)
    seuil = seuil_retard(user.company, aujourd_hui_local())
    chiffres = RelanceEtape.objects.filter(
        company=user.company, statut=RelanceEtape.Statut.A_FAIRE,
        lead_id__in=leads.values('id'),
    ).aggregate(ouvertes=Count('id'),
                en_retard=Count('id', filter=Q(due_date__lt=seuil)))
    return {
        'dossiers': leads.count(),
        'etapes_ouvertes': chiffres['ouvertes'],
        'etapes_en_retard': chiffres['en_retard'],
    }


def deleguer_dossiers(user, de, vers, *, prevenir_clients=True):
    """Confie à ``vers`` les leads de ``de`` : une transaction, ``reattribuer_lead``
    par dossier, la ligne d'Historique « en masse » de la réattribution en lot.

    Renvoie l'aperçu pris AVANT l'écriture (ce que l'écran a annoncé) plus le
    nombre de dossiers confiés et de touches de passation posées."""
    chiffres = apercu_delegation(user, de)
    confies = passations = 0
    with transaction.atomic():
        for lead in leads_a_deleguer(user, de).select_related('owner'):
            ancien = lead.owner
            etape = reattribuer_lead(
                lead, user, vers, prevenir_client=prevenir_clients)
            activity.log_bulk_change(lead, user, 'owner', ancien, vers)
            sync_relance_activity(lead, user)
            confies += 1
            passations += 1 if etape is not None else 0
    return {**chiffres, 'confies': confies, 'passations_posees': passations}
