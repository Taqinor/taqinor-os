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


def _add_months(d, months):
    """NTPRO6 — ``d`` décalée de ``months`` mois (jour recadré fin de mois).

    Fonction pure stdlib (pas de dépendance ajoutée) : même calcul que
    ``apps.ventes.services._add_months`` mais gardée LOCALE (pas d'import
    cross-app pour une simple arithmétique de date, cf. frontière CLAUDE.md)."""
    import calendar
    from datetime import date

    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def generer_echeancier(bail):
    """NTPRO6 — Génère l'échéancier mensuel d'un ``Bail`` ``actif``.

    Crée une ``EcheanceLoyer`` par mois, de ``date_debut`` sur ``duree_mois``
    mois. IDEMPOTENT : une période déjà présente (``unique_together`` bail +
    periode_debut) est SAUTÉE, jamais dupliquée ni recréée — relancer la
    génération sur un bail déjà échéancé ne crée que les mois manquants.
    Ne fait rien (renvoie une liste vide) si le bail n'est pas ``actif``.
    """
    from datetime import timedelta

    from .models import Bail, EcheanceLoyer

    if bail.statut != Bail.Statut.ACTIF:
        return []

    existantes = set(
        EcheanceLoyer.objects
        .filter(bail=bail)
        .values_list('periode_debut', flat=True)
    )

    montant_loyer_ht = bail.loyer_mensuel_ht
    montant_charges = bail.charges_mensuelles_provisions or 0
    montant_total = montant_loyer_ht + montant_charges

    creees = []
    for i in range(bail.duree_mois):
        periode_debut = _add_months(bail.date_debut, i)
        if periode_debut in existantes:
            continue
        periode_fin = _add_months(periode_debut, 1) - timedelta(days=1)
        echeance = EcheanceLoyer.objects.create(
            company=bail.company, bail=bail,
            periode_debut=periode_debut, periode_fin=periode_fin,
            montant_loyer_ht=montant_loyer_ht,
            montant_charges=montant_charges,
            montant_total=montant_total,
        )
        creees.append(echeance)

    return creees


class ClientVentesIntrouvableError(Exception):
    """NTPRO7 — le locataire n'a aucun ``crm.Client`` résolu/résolvable."""


def emettre_quittance(echeance):
    """NTPRO7 — Émet la quittance d'une ``EcheanceLoyer`` : crée UNE facture
    ventes via ``apps.ventes.services`` (function-local, jamais un import de
    modèle ``Facture``) liée au Locataire résolu (NTPRO2), avec un libellé
    combinant loyer + charges de la période.

    IDEMPOTENT — jamais de doublon : si l'échéance porte déjà un
    ``facture_ventes_id`` (quittance déjà émise), ne recrée RIEN et renvoie
    l'id de facture existant tel quel. Résout le client ventes du locataire
    à la volée si nécessaire (best-effort, ``resolve_client_ventes_for_
    locataire``). Passe le statut de l'échéance à ``emise``."""
    from decimal import Decimal

    from django.utils import timezone

    from .models import EcheanceLoyer

    if echeance.facture_ventes_id:
        return echeance.facture_ventes_id

    locataire = echeance.bail.locataire
    client_id = locataire.client_ventes_id
    if not client_id:
        client_id = resolve_client_ventes_for_locataire(locataire)
    if not client_id:
        raise ClientVentesIntrouvableError(
            f'Aucun client ventes résolu pour le locataire {locataire}.')

    from apps.crm.selectors import get_company_client
    client = get_company_client(echeance.company, client_id)
    if client is None:
        raise ClientVentesIntrouvableError(
            f'Client ventes {client_id} introuvable pour cette société.')

    periode = f'{echeance.periode_debut:%m/%Y}'
    libelle = f'Loyer {periode} — {echeance.bail.local}'
    if echeance.montant_charges and echeance.montant_charges > 0:
        libelle += f' + Charges {periode}'

    from apps.ventes.services import creer_facture_classique

    montant_total = echeance.montant_total
    facture = creer_facture_classique(
        company=echeance.company, client=client, user=None,
        taux_tva=Decimal('0'), montant_ht=montant_total,
        montant_tva=Decimal('0'), montant_ttc=montant_total,
        libelle=libelle,
    )

    EcheanceLoyer.objects.filter(pk=echeance.pk).update(
        facture_ventes_id=facture.id, statut=EcheanceLoyer.Statut.EMISE,
        date_emission_quittance=timezone.now())
    echeance.facture_ventes_id = facture.id
    echeance.statut = EcheanceLoyer.Statut.EMISE
    echeance.date_emission_quittance = timezone.now()

    return facture.id


def relancer_echeance(echeance, *, canal=None, template_utilise=''):
    """NTPRO8 — Enregistre une relance d'impayé sur ``echeance`` et incrémente
    le niveau (1 → 2 → 3, plafonné à 3 : une relance déjà au niveau 3 reste au
    niveau 3, on n'en invente pas un 4ᵉ). Passe le statut de l'échéance à
    ``relancee``. Renvoie la ``RelanceLoyer`` créée."""
    from .models import EcheanceLoyer, RelanceLoyer

    canal = canal or RelanceLoyer.Canal.WHATSAPP
    derniere = (
        RelanceLoyer.objects
        .filter(echeance_loyer=echeance)
        .order_by('-niveau', '-id')
        .first()
    )
    niveau = min((derniere.niveau + 1) if derniere else 1, 3)

    relance = RelanceLoyer.objects.create(
        company=echeance.company, echeance_loyer=echeance, niveau=niveau,
        canal=canal, template_utilise=template_utilise,
    )

    EcheanceLoyer.objects.filter(pk=echeance.pk).update(
        statut=EcheanceLoyer.Statut.RELANCEE)
    echeance.statut = EcheanceLoyer.Statut.RELANCEE

    return relance
