"""Encaissements — paiements, avances, retenues, mandats, liens de paiement.

L'argent qui ENTRE : enregistrement d'un paiement (simple, groupé, avec
retenue à la source), avances et leur ventilation, consolidation de
factures, mandats de prélèvement, liens de paiement publics et leur QR.

QJR69 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal

from apps.stock.services import qr_svg_for


def enregistrer_paiement(*, facture, montant, mode, date_paiement, user,
                         reference='', note=''):
    """Enregistre un ``Paiement`` MANUEL sur une facture EXISTANTE.

    Thin service exposé pour apps.pos (encaissement comptoir XPOS1/XPOS6) —
    même modèle/table que le paiement enregistré depuis l'écran facture,
    aucune duplication de logique."""
    from apps.ventes.models import Paiement
    paiement = Paiement.objects.create(
        company=facture.company,
        facture=facture,
        montant=montant,
        date_paiement=date_paiement,
        mode=mode,
        reference=reference or '',
        note=note or '',
        created_by=user,
    )
    # YLEDG1 — événement documentaire générique (pose du seam pour
    # compta.ecriture_pour_paiement, jamais d'import de son service ici).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


def facture_montant_du(facture):
    """Solde restant dû d'une facture (lecture, thin service pour apps.pos)."""
    return facture.montant_du


def affecter_encaissement_groupe(
        *, company, client, montant, mode, date_paiement, user, factures,
        reference='', repartition=None):
    """ZFAC6 — un seul règlement client réparti sur PLUSIEURS factures.

    Crée un ``Paiement`` par facture réglée : par défaut FIFO (la facture à
    l'échéance la plus ancienne d'abord, jusqu'à épuisement du montant) ; ou
    une répartition EXPLICITE si ``repartition`` (dict facture_id -> montant)
    est fournie. Toutes les factures doivent appartenir à ``company`` ET
    ``client`` (sinon ValueError — le viewset traduit en 400). Atomique :
    échec partiel = rollback total. Bascule le statut « Payée » sur toute
    facture intégralement soldée par ce geste (comportement identique à un
    encaissement facture-par-facture)."""
    from decimal import Decimal

    from django.db import transaction

    from apps.ventes.models import Facture

    montant = Decimal(str(montant))
    if montant <= 0:
        raise ValueError("Le montant doit être positif.")
    if not factures:
        raise ValueError("Aucune facture fournie.")

    for f in factures:
        if f.company_id != company.id or f.client_id != client.id:
            raise ValueError(
                f"La facture {f.reference} n'appartient pas à ce client.")

    paiements = []
    with transaction.atomic():
        locked = list(
            Facture.objects.select_for_update()
            .filter(id__in=[f.id for f in factures])
        )
        by_id = {f.id: f for f in locked}

        if isinstance(repartition, dict) and repartition:
            # Répartition explicite fournie par l'appelant.
            for fid, part in repartition.items():
                facture = by_id.get(int(fid))
                if facture is None:
                    raise ValueError(f"Facture {fid} inconnue dans ce lot.")
                part = Decimal(str(part))
                if part <= 0:
                    continue
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
        else:
            # FIFO : échéance la plus ancienne d'abord (None en dernier).
            ordonnees = sorted(
                locked,
                key=lambda f: (f.date_echeance is None, f.date_echeance))
            restant = montant
            for facture in ordonnees:
                if restant <= 0:
                    break
                reste_facture = facture.montant_du
                if reste_facture <= 0:
                    continue
                part = min(restant, reste_facture)
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
                restant -= part

        for facture in locked:
            facture.refresh_from_db()
            if facture.montant_du <= Decimal('0') and \
                    facture.statut not in (
                        Facture.Statut.ANNULEE, Facture.Statut.PAYEE):
                facture.statut = Facture.Statut.PAYEE
                facture.save(update_fields=['statut'])

    return paiements


def _creer_paiement_groupe(facture, montant, mode, date_paiement, user,
                           reference):
    from apps.ventes.models import Paiement

    paiement = Paiement.objects.create(
        company=facture.company, facture=facture, montant=montant,
        date_paiement=date_paiement, mode=mode,
        reference=reference or '', created_by=user,
    )
    # YLEDG1 — événement documentaire générique (même seam que
    # enregistrer_paiement / le geste facture-par-facture).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


# ── FG53 — Liens de paiement « Payer en ligne » ──────────────────────────────

def create_payment_link(*, facture, provider=None):
    """FG53 — crée (ou réutilise) un lien de paiement pour une facture.

    Réutilise un lien encore valide (en attente, non expiré) pour la même
    facture plutôt que d'en empiler. Le montant est figé au reste à payer à
    l'instant T. Le fournisseur par défaut est NoOp (page interne, aucun coût).
    Société forcée depuis la facture, jamais lue d'un corps de requête.
    """
    from decimal import Decimal
    from django.utils import timezone
    from ..models import PaymentLink

    existing = (PaymentLink.objects
                .filter(facture=facture,
                        statut=PaymentLink.Statut.EN_ATTENTE,
                        expires_at__gt=timezone.now())
                .order_by('-created_at').first())
    if existing is not None:
        return existing

    montant = facture.montant_du
    if montant is None or montant <= Decimal('0'):
        montant = facture.total_ttc
    return PaymentLink.objects.create(
        company=facture.company,
        facture=facture,
        provider=(provider or 'noop'),
        montant=montant,
    )


def _public_url(path):
    """Construit une URL publique absolue à partir d'un chemin ``/api/...``.

    Réutilise ``settings.PUBLIC_BASE_URL`` (même pattern que
    ``bcf_share_url``) ; sans réglage, renvoie le chemin relatif tel quel (le
    QR reste valide une fois servi depuis le même domaine)."""
    from django.conf import settings
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    if base:
        return base.rstrip('/') + path
    return path


def qr_svg_for_facture_pdf(facture):
    """XFAC19 — QR de paiement/vérification pour le PDF facture LEGACY (jamais
    le moteur devis premium — voir RULE #4).

    Si un ``PaymentLink`` actif (en attente, non expiré) existe déjà pour la
    facture, le QR pointe vers sa page « Payer en ligne » publique. Sinon, il
    pointe vers le ``ShareLink`` public (lecture seule) du document. Ajout
    SILENCIEUX : renvoie ``None`` si aucun lien ne peut être établi (comportement
    actuel inchangé — pas de QR, pas d'erreur). Le rendu SVG délègue au
    générateur QR pur de N20 via ``apps.stock.services.qr_svg_for`` (jamais
    d'import direct de ``apps.stock.labels``)."""
    from django.utils import timezone
    from ..models import PaymentLink, ShareLink

    active_link = (
        PaymentLink.objects.filter(
            facture=facture, statut=PaymentLink.Statut.EN_ATTENTE,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at').first())
    if active_link is not None:
        url = _public_url(f'/api/django/public/pay/{active_link.token}/')
    else:
        share = ShareLink.for_facture(facture)
        url = _public_url(f'/api/django/public/document/{share.token}/')

    if not url:
        return None
    return qr_svg_for(url)


def record_payment_from_link(*, link, payload=None):
    """FG53 — enregistre un Paiement quand un lien est confirmé payé (webhook).

    Idempotent : un lien déjà payé renvoie le paiement existant sans en créer un
    second. Le fournisseur valide d'abord la notification (verify_webhook) ; tant
    qu'il ne confirme pas, rien n'est écrit. Le montant et le statut de la
    facture sont mis à jour exactement comme un encaissement manuel.

    Retourne (paiement, message_erreur). En succès message_erreur=None.
    """
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from ..models import Facture, Paiement, PaymentLink
    from ..payments.providers import get_provider

    if link.statut == PaymentLink.Statut.PAYE and link.paiement_id:
        # Déjà encaissé — idempotent.
        return link.paiement, None
    if not link.is_valid:
        return None, 'Lien de paiement expiré ou invalide.'

    provider = get_provider(link.provider)
    result = provider.verify_webhook(link, payload or {})
    if not result.get('paid'):
        return None, 'Paiement non confirmé par le fournisseur.'

    montant = result.get('montant')
    if montant is None:
        montant = link.montant
    montant = Decimal(str(montant))

    with transaction.atomic():
        locked_link = (PaymentLink.objects.select_for_update()
                       .get(pk=link.pk))
        if locked_link.statut == PaymentLink.Statut.PAYE \
                and locked_link.paiement_id:
            return locked_link.paiement, None
        facture = (Facture.objects.select_for_update()
                   .get(pk=locked_link.facture_id))
        if facture.statut == Facture.Statut.ANNULEE:
            return None, 'Facture annulée.'
        # Borne le montant au reste à payer (jamais de sur-paiement).
        reste = facture.montant_du
        if montant > reste:
            montant = reste
        if montant <= Decimal('0'):
            return None, 'Aucun reste à payer sur cette facture.'
        paiement = Paiement.objects.create(
            company=facture.company,
            facture=facture,
            montant=montant,
            date_paiement=timezone.localdate(),
            mode=Paiement.Mode.CARTE,
            reference=(result.get('provider_ref') or '')[:120],
            note='Paiement en ligne (lien « Payer en ligne »).',
        )
        # YLEDG1 — événement documentaire générique (pose du seam pour
        # compta.ecriture_pour_paiement).
        from core.events import paiement_enregistre
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=facture.company)
        locked_link.statut = PaymentLink.Statut.PAYE
        locked_link.paiement = paiement
        locked_link.provider_ref = (result.get('provider_ref') or '')[:200]
        locked_link.paid_at = timezone.now()
        locked_link.save(update_fields=[
            'statut', 'paiement', 'provider_ref', 'paid_at'])
        facture.refresh_from_db()
        if facture.montant_du <= Decimal('0') \
                and facture.statut != Facture.Statut.ANNULEE:
            facture.statut = Facture.Statut.PAYEE
            facture.save(update_fields=['statut'])
            # YDOCF4 — facture_paid, exactement une fois au passage
            # résiduel→0 via le webhook de lien de paiement.
            from core.events import facture_paid, facture_payee
            facture_paid.send(
                sender=Facture, facture=facture, montant=montant,
                company=facture.company)
            # YEVNT6 — événement documentaire générique (même transition).
            facture_payee.send(
                sender=Facture, instance=facture, company=facture.company)
    return paiement, None


# ── XFAC1 — Avances client (paiement sans facture) + affectation multi- ────
# ────────────────────────── factures ───────────────────────────────────────

def enregistrer_avance(*, company, client, montant, date_paiement, mode,
                       reference='', note='', created_by=None):
    """Enregistre un règlement reçu SANS facture (avance, acompte à la
    commande, trop-perçu). Le paiement reste ``statut_affectation=non_affecte``
    tant qu'il n'a pas été ventilé sur une ou plusieurs factures ouvertes du
    même client (voir ``ventiler_avance``)."""
    from decimal import Decimal, InvalidOperation
    from rest_framework.exceptions import ValidationError
    from ..models import Paiement

    if montant is None:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        montant = Decimal(str(montant))
    except InvalidOperation:
        raise ValidationError({'montant': 'Montant invalide.'})
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    if client is None:
        raise ValidationError({'client': 'Client requis pour une avance.'})
    return Paiement.objects.create(
        company=company, client=client, facture=None,
        statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
        montant=montant, date_paiement=date_paiement, mode=mode,
        reference=reference, note=note, created_by=created_by,
    )


def ventiler_avance(*, paiement, facture, montant, user=None):
    """Ventile UN paiement non affecté (avance) sur UNE facture ouverte du
    même client, pour ``montant``. Peut être appelée plusieurs fois pour
    répartir un même paiement sur plusieurs factures.

    Garde-fous (jamais de sur-affectation) :
      - la facture cible doit appartenir à la même société ET au même client
        que le paiement ;
      - le montant ventilé ne peut jamais dépasser le solde disponible du
        paiement (``montant_disponible``) ;
      - le montant ventilé ne peut jamais dépasser le reste à payer de la
        facture cible (``montant_du``).

    Met à jour ``statut_affectation`` du paiement (affecte / partiellement
    affecte) et le statut de la facture si elle devient intégralement réglée
    (réutilise le même seuil que ``enregistrer_paiement``)."""
    from decimal import Decimal
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from ..models import AffectationPaiement, Facture, Paiement

    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError(
            {'montant': "Le montant ventilé doit être positif."})

    with transaction.atomic():
        locked_paiement = Paiement.objects.select_for_update().get(
            pk=paiement.pk)
        if locked_paiement.facture_id is not None:
            raise ValidationError(
                {'paiement': "Ce paiement est déjà rattaché à une facture."})
        locked_facture = Facture.objects.select_for_update().get(
            pk=facture.pk)
        if locked_facture.company_id != locked_paiement.company_id:
            raise ValidationError(
                {'facture': "Facture d'une autre société."})
        if locked_facture.client_id != locked_paiement.client_id:
            raise ValidationError(
                {'facture': "La facture doit appartenir au même client "
                            "que l'avance."})
        if locked_facture.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'facture': "Impossible de ventiler sur une facture annulée."})

        disponible = locked_paiement.montant_disponible
        if montant - disponible > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le solde disponible de "
                    f"l'avance ({disponible:.2f} MAD)."),
            })
        reste_facture = locked_facture.montant_du
        if montant - reste_facture > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le reste à payer de la "
                    f"facture ({reste_facture:.2f} MAD)."),
            })

        affectation = AffectationPaiement.objects.create(
            company=locked_paiement.company, paiement=locked_paiement,
            facture=locked_facture, montant=montant, created_by=user,
        )

        locked_paiement.refresh_from_db()
        if locked_paiement.montant_disponible <= 0:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.AFFECTE)
        else:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.PARTIELLEMENT_AFFECTE)
        locked_paiement.save(update_fields=['statut_affectation'])

        locked_facture.refresh_from_db()
        if locked_facture.montant_du <= 0 and \
                locked_facture.statut != Facture.Statut.ANNULEE:
            locked_facture.statut = Facture.Statut.PAYEE
            locked_facture.save(update_fields=['statut'])
            reset_relance_escalation(locked_facture)

        from .. import activity
        activity.log_facture_avance_affectee(
            locked_facture, user, locked_paiement, montant)

    return affectation


# ── XFAC4 — Retenue à la source SUBIE (RAS TVA/RAS IS) sur factures ────────
# ────────────────────────── clients ────────────────────────────────────────

def enregistrer_paiement_avec_retenue(
        *, facture, montant, date_paiement, mode, type_retenue, taux,
        reference='', note='', created_by=None):
    """Enregistre un paiement PARTIEL accompagné d'une retenue à la source
    (RAS TVA / RAS IS) qui, ENSEMBLE, soldent la facture : payé + retenue +
    avoirs = TTC. Sans cette écriture, la facture resterait « partiellement
    payée » à tort — la retenue n'est pas un montant perdu, c'est une créance
    d'attestation à recevoir de la DGT/du client.

    ``taux`` est informatif (tracé sur la retenue) ; le MONTANT de la retenue
    est déduit du reste à payer : ``retenue = reste_avant − montant`` (le
    paiement partiel + la retenue soldent ensemble EXACTEMENT le reste à
    payer). Rejette un montant qui dépasserait seul le reste à payer, ou une
    retenue résultante négative (le paiement seul suffirait déjà). Le
    paiement + la retenue sont créés dans la MÊME transaction ; la facture
    bascule automatiquement « Payée » si le solde tombe à zéro (même seuil que
    ``enregistrer_paiement``).
    """
    from decimal import Decimal
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from ..models import Facture, Paiement, RetenueSubie

    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        taux = Decimal(taux)
    except (TypeError, ValueError):
        raise ValidationError({'taux': 'Taux de RAS invalide.'})
    if taux < 0 or taux > 100:
        raise ValidationError(
            {'taux': 'Le taux de RAS doit être compris entre 0 et 100 %.'})

    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'detail': "Impossible d'encaisser sur une facture annulée."})
        reste = locked.montant_du
        if montant - reste > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f'Le paiement dépasse le reste à payer '
                    f'({reste:.2f} MAD).'),
            })
        # Base de la retenue = ce qui reste dû après le règlement partiel ;
        # le paiement + la retenue soldent ensemble exactement le reste à
        # payer (jamais de fraction perdue, jamais de sur-solde).
        base = reste - montant
        retenue_montant = base.quantize(Decimal('0.01'))
        if retenue_montant < 0:
            retenue_montant = Decimal('0')

        paiement = Paiement.objects.create(
            company=locked.company, facture=locked, montant=montant,
            date_paiement=date_paiement, mode=mode, reference=reference,
            note=note, created_by=created_by,
        )
        retenue = RetenueSubie.objects.create(
            company=locked.company, facture=locked, paiement=paiement,
            type_retenue=type_retenue, taux=taux, base=base,
            montant=retenue_montant, note=note,
            created_by=created_by,
        )

        from .. import activity
        activity.log_facture_paiement(locked, created_by, paiement)
        activity.log_facture_retenue_subie(locked, created_by, retenue)

        locked.refresh_from_db()
        if locked.montant_paye_avec_retenues >= locked.total_ttc - \
                locked.avoirs_total - Decimal('0.01') and \
                locked.statut != Facture.Statut.ANNULEE:
            locked.statut = Facture.Statut.PAYEE
            locked.save(update_fields=['statut'])
            reset_relance_escalation(locked)

    return paiement, retenue


# ── XFAC11 — Facture consolidée multi-devis/BC d'un même client ────────────

def consolider_factures(*, company, devis_ids, user, created_by=None):
    """Crée UNE Facture unique regroupant PLUSIEURS devis acceptés du MÊME
    client (ex. projet multi-sites : ferme à N forages, tranches). Chaque
    document source garde ses lignes (recopiées, groupées par ``source_devis``
    pour le sous-titre « Devis DV-… » sur le PDF) et une ``FactureSource``
    trace le sous-total HT de son document d'origine.

    Contrôles :
      - au moins 2 devis, tous acceptés, tous de la MÊME société ET du MÊME
        client (clients différents → rejeté) ;
      - un devis déjà facturé (une Facture non annulée référence ce devis,
        directement ou via une FactureSource antérieure) est refusé.

    La chaîne Sous-total → Remise → HT → TVA → TTC reste calculée par les
    propriétés existantes de ``Facture`` (aucune formule dupliquée) : les
    lignes recopiées portent leur ``taux_tva`` d'origine, donc la ventilation
    TVA par taux (10 %/20 %) reste correcte pour le mélange.
    """
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from ..models import Devis, Facture, FactureSource, LigneFacture
    from ..utils.company_settings import create_numbered

    if not devis_ids or len(devis_ids) < 2:
        raise ValidationError(
            {'devis_ids': 'Au moins 2 devis sont requis pour consolider.'})

    devis_qs = list(Devis.objects.select_related('client').filter(
        id__in=devis_ids, company=company).prefetch_related('lignes'))
    if len(devis_qs) != len(set(devis_ids)):
        raise ValidationError({'devis_ids': 'Un ou plusieurs devis introuvables.'})

    client_ids = {d.client_id for d in devis_qs}
    if len(client_ids) > 1:
        raise ValidationError(
            {'devis_ids': 'Tous les devis doivent appartenir au même client.'})

    for d in devis_qs:
        if d.statut != Devis.Statut.ACCEPTE:
            raise ValidationError({
                'devis_ids': (
                    f'Le devis {d.reference} doit être accepté pour être '
                    f'consolidé.'),
            })
        deja_facture = Facture.objects.filter(
            devis=d).exclude(statut=Facture.Statut.ANNULEE).exists() or \
            FactureSource.objects.filter(devis=d).exists()
        if deja_facture:
            raise ValidationError({
                'devis_ids': f'Le devis {d.reference} est déjà facturé.',
            })

    client = devis_qs[0].client

    with transaction.atomic():
        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=company, client=client,
                statut=Facture.Statut.EMISE, created_by=created_by,
            )

        facture = create_numbered(Facture, company, 'facture', _create)

        for d in devis_qs:
            sous_total = Decimal('0')
            for ligne in d.lignes.all():
                LigneFacture.objects.create(
                    facture=facture, produit=ligne.produit,
                    designation=f'{d.reference} — {ligne.designation}',
                    quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
                    remise=ligne.remise, taux_tva=ligne.taux_tva,
                    source_devis=d,
                )
                sous_total += ligne.total_ht
            FactureSource.objects.create(
                company=company, facture=facture, devis=d,
                sous_total_ht=sous_total,
            )

    return facture


# ── XCTR22 — Encaissement récurrent automatique (tokenisation / mandat) ────

def mandat_actif_pour_client(client):
    """Renvoie le ``MandatPaiement`` ACTIF du client, ou None.

    Lecture pure ; jamais d'effet de bord. Sert de garde d'entrée pour
    ``debiter_mandat_pour_facture`` — un client sans mandat actif (le cas
    par défaut) fait strictement l'encaissement manuel actuel."""
    from apps.ventes.models import MandatPaiement
    return (
        MandatPaiement.objects
        .filter(client=client, statut=MandatPaiement.Statut.ACTIF)
        .exclude(token='')
        .order_by('-created_at')
        .first()
    )


DUNNING_RETRY_DAYS = (1, 3, 7)


def debiter_mandat_pour_facture(*, facture, periode, retry_index=0):
    """XCTR22 — débite le mandat actif du client de ``facture`` pour la
    période donnée, via `payments.providers`.

    Appelé APRÈS la création d'une facture de cycle récurrent
    (`creer_facture_contrat`/`facturer_ligne_echeance` — contrats/sav restent
    les points d'entrée existants ; ceci est un branchement ADDITIF appelé
    depuis leurs services). Sans mandat actif → no-op silencieux (retourne
    None, comportement actuel intact). Avec mandat :
      - succès → crée un `Paiement` rapproché (comme un encaissement manuel)
        + une `TentativeDebitMandat` `reussi` ; jamais deux débits RÉUSSIS
        pour la même (mandat, periode) — idempotent.
      - échec → `TentativeDebitMandat` `echec` avec motif + programme la
        prochaine retentative (`DUNNING_RETRY_DAYS`, défaut J+1/J+3/J+7) et
        notifie le client (lien de mise à jour de carte — best-effort).

    Renvoie le `Paiement` créé en cas de succès, sinon None.
    """
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from apps.ventes.models import TentativeDebitMandat, Paiement
    from apps.ventes.payments.providers import get_provider

    mandat = mandat_actif_pour_client(facture.client)
    if mandat is None:
        return None

    # Jamais deux débits RÉUSSIS pour la même période — idempotence.
    deja_reussi = TentativeDebitMandat.objects.filter(
        mandat=mandat, periode=periode,
        statut=TentativeDebitMandat.Statut.REUSSI).exists()
    if deja_reussi:
        return None

    provider = get_provider(mandat.provider)
    result = provider.charge(token=mandat.token, montant=facture.montant_ttc)

    with transaction.atomic():
        if result.get('ok'):
            paiement = Paiement.objects.create(
                company=facture.company, facture=facture,
                montant=facture.montant_ttc,
                date_paiement=timezone.localdate(),
                mode=Paiement.Mode.CARTE,
                reference=(result.get('provider_ref') or '')[:120],
                note='Débit automatique (mandat de paiement récurrent).',
            )
            TentativeDebitMandat.objects.create(
                company=facture.company, mandat=mandat, periode=periode,
                statut=TentativeDebitMandat.Statut.REUSSI,
                paiement=paiement,
            )
            return paiement

        tentatives_precedentes = TentativeDebitMandat.objects.filter(
            mandat=mandat, periode=periode,
            statut=TentativeDebitMandat.Statut.ECHEC).count()
        idx = min(tentatives_precedentes, len(DUNNING_RETRY_DAYS) - 1)
        prochaine = (
            timezone.localdate() + timedelta(days=DUNNING_RETRY_DAYS[idx]))
        TentativeDebitMandat.objects.create(
            company=facture.company, mandat=mandat, periode=periode,
            statut=TentativeDebitMandat.Statut.ECHEC,
            motif_echec=(result.get('motif_echec') or '')[:255],
            prochaine_retentative=prochaine,
        )

    try:
        from apps.notifications.services import notify
        client = facture.client
        if client is not None and getattr(client, 'created_by', None):
            notify(
                client.created_by, 'mandat_debit_echec',
                f'Débit automatique échoué — {facture.reference}',
                body=(f'Le débit automatique de {facture.montant_ttc} MAD '
                      f'a échoué pour {client.nom}. Mettez à jour la carte.'),
                link='/ventes/factures',
                company=facture.company,
            )
    except Exception:  # noqa: BLE001 — best-effort
        pass

    return None


# ── PONT M3 : noms hébergés par un autre module ──────────────────────────────
# Import EN BAS DE FICHIER : il s'exécute après toutes les définitions de ce
# module, donc un import croisé ne peut jamais lire un module à moitié
# construit, quel que soit celui qui est chargé le premier.
from apps.ventes.domain.recouvrement import reset_relance_escalation  # noqa: E402,F401
