"""Services (écriture/orchestration) du module Immobilier.

Toute lecture/écriture vers un autre domaine (``crm``/``ventes``) passe
exclusivement par ses ``selectors.py``/``services.py`` (imports FONCTION-LOCAL,
jamais ``apps.crm.models``/``apps.ventes.models`` importés en tête de module) —
frontière cross-app de CLAUDE.md.
"""


def resolve_client_ventes_for_locataire(locataire):
    """NTPRO2 — Relie ``locataire`` à un ``crm.Client`` EXISTANT sans jamais en
    créer un nouveau (pas de point d'entrée d'écriture sanctionné pour créer un
    client hors lead dans ce périmètre) : même esprit que
    ``crm.services.resolve_client_for_lead``, mais strictement LECTURE — un
    locataire sans client ventes correspondant reste simplement délié
    (``client_ventes_id`` = None), jamais de doublon créé.

    Recherche par email d'abord, puis par téléphone (repli), via
    ``apps.crm.selectors`` (jamais un import de ``apps.crm.models``). Idempotent
    : si ``locataire.client_ventes_id`` est déjà posé, ne fait rien et renvoie
    l'id existant.
    """
    if locataire.client_ventes_id:
        return locataire.client_ventes_id

    from apps.crm.selectors import find_client_by_email, find_client_by_phone

    client = None
    if locataire.email:
        client = find_client_by_email(locataire.email, company=locataire.company)
    if client is None and locataire.telephone:
        client = find_client_by_phone(locataire.company, locataire.telephone)

    if client is None:
        return None

    locataire.client_ventes_id = client.id
    locataire.save(update_fields=['client_ventes_id'])
    return client.id


class BailActifExistantError(Exception):
    """NTPRO3 — un Local a déjà un bail ``actif`` (contrainte applicative)."""


def creer_bail(*, company, local, locataire, **champs):
    """NTPRO3 — Crée un ``Bail`` et fait passer le ``Local`` en statut ``loue``
    si le bail est créé directement ``actif``.

    Refuse (``BailActifExistantError``) si ``local`` porte déjà un bail
    ``actif`` — un seul bail actif à la fois par local (contrainte
    applicative, pas de contrainte DB : un bail ``brouillon``/``resilie``/
    ``expire`` coexiste sans problème). Statut par défaut ``actif`` si non
    fourni (le cas d'usage courant : signer un bail le rend actif
    immédiatement)."""
    from .models import Bail, Local

    statut = champs.pop('statut', Bail.Statut.ACTIF)
    if statut == Bail.Statut.ACTIF:
        deja_actif = Bail.objects.filter(
            company=company, local=local, statut=Bail.Statut.ACTIF).exists()
        if deja_actif:
            raise BailActifExistantError(
                f'Le local {local} a déjà un bail actif.')

    bail = Bail.objects.create(
        company=company, local=local, locataire=locataire, statut=statut,
        bailleur_nom_snapshot=champs.pop('bailleur_nom_snapshot', ''),
        locataire_nom_snapshot=champs.pop(
            'locataire_nom_snapshot', locataire.nom),
        **champs,
    )

    if statut == Bail.Statut.ACTIF:
        Local.objects.filter(pk=local.pk).update(statut=Local.Statut.LOUE)
        local.statut = Local.Statut.LOUE

    return bail


def appliquer_revision(bail, nouveau_loyer, date_effet, *, indice=''):
    """NTPRO4 — Applique une révision de loyer INDEXÉE sur ``bail``.

    Journalise une ligne ``RevisionLoyer`` IMMUABLE (ancien loyer, nouveau
    loyer, taux de variation calculé) puis met à jour
    ``Bail.loyer_mensuel_ht`` au NOUVEAU loyer, à compter de ``date_effet``.

    JAMAIS rétroactif : les ``EcheanceLoyer`` déjà générées gardent leur
    ``montant_loyer_ht`` figé au moment de leur génération (NTPRO6) — seules
    les échéances générées APRÈS cette révision hériteront du nouveau loyer.
    Renvoie la ``RevisionLoyer`` créée."""
    from decimal import Decimal

    from .models import RevisionLoyer

    ancien_loyer = bail.loyer_mensuel_ht
    nouveau_loyer = Decimal(nouveau_loyer)
    taux_variation = None
    if ancien_loyer:
        taux_variation = (
            (nouveau_loyer - ancien_loyer) / ancien_loyer * 100
        ).quantize(Decimal('0.01'))

    revision = RevisionLoyer.objects.create(
        company=bail.company, bail=bail, date_effet=date_effet,
        ancien_loyer=ancien_loyer, nouveau_loyer=nouveau_loyer,
        indice=indice, taux_variation=taux_variation,
    )

    bail.loyer_mensuel_ht = nouveau_loyer
    bail.save(update_fields=['loyer_mensuel_ht'])

    return revision


class DepotGarantieError(Exception):
    """NTPRO5 — opération invalide sur le cycle de vie du dépôt de garantie."""


def encaisser_depot(bail, date_reception=None):
    """NTPRO5 — Marque le dépôt de garantie du bail comme reçu (horodaté)."""
    from django.utils import timezone

    bail.depot_garantie_recu = True
    bail.date_reception_depot = date_reception or timezone.localdate()
    bail.save(update_fields=['depot_garantie_recu', 'date_reception_depot'])
    return bail


def restituer_depot(bail, montant_retenu=0, motif_retenue='', date_restitution=None):
    """NTPRO5 — Restitue le dépôt de garantie (jamais plus que le dépôt initial).

    ``montant_restitue`` = ``depot_garantie - montant_retenu``, jamais négatif
    — une retenue supérieure au dépôt initial est refusée
    (``DepotGarantieError``) plutôt que silencieusement plafonnée."""
    from decimal import Decimal

    from django.utils import timezone

    montant_retenu = Decimal(montant_retenu or 0)
    if montant_retenu < 0:
        raise DepotGarantieError('Le montant retenu ne peut pas être négatif.')
    if montant_retenu > bail.depot_garantie:
        raise DepotGarantieError(
            'Le montant retenu ne peut pas excéder le dépôt de garantie.')

    bail.depot_garantie_restitue = True
    bail.date_restitution = date_restitution or timezone.localdate()
    bail.montant_retenu = montant_retenu
    bail.motif_retenue = motif_retenue or ''
    bail.save(update_fields=[
        'depot_garantie_restitue', 'date_restitution', 'montant_retenu',
        'motif_retenue',
    ])
    return bail


def montant_restitue_depot(bail):
    """NTPRO5 — Montant effectivement restitué (dépôt - retenue), jamais < 0."""
    from decimal import Decimal

    montant = bail.depot_garantie - (bail.montant_retenu or Decimal('0'))
    return max(montant, Decimal('0'))
