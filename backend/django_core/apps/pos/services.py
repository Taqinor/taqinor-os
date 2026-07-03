"""apps.pos.services — orchestration vente comptoir / caisse / retrait.

Règle de modularité (CLAUDE.md) : AUCUN import direct des modèles
``ventes``/``stock``/``compta`` — uniquement leurs ``services``/``selectors``
ou des FK chaîne. Tout le code métier POS reste dans cette app.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import CommandeRetrait, SessionCaisse, VenteComptoir

MODE_ESPECES = 'especes'


# ── XPOS1 — Validation d'une vente comptoir ─────────────────────────────────

class VenteComptoirError(Exception):
    """Erreur métier lors de la validation d'une vente comptoir."""


def _q2(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _discount_threshold_ok(company, remise, *, approuve, user):
    """T17 — remise ligne plafonnée par le seuil d'approbation existant.

    Réutilise ``parametres.CompanyProfile.discount_approval_threshold`` (même
    seuil que les devis). Seuil non renseigné = désactivé. Un admin peut
    toujours dépasser ; sinon la remise au-delà du seuil est refusée sans
    approbation explicite (``approuve=True``, posé par un admin/responsable
    côté vue).
    """
    from apps.parametres.models import CompanyProfile
    seuil = CompanyProfile.get(company).discount_approval_threshold
    if seuil is None:
        return True
    if (remise or 0) <= seuil:
        return True
    if approuve:
        return True
    return bool(getattr(user, 'is_admin_role', False))


@transaction.atomic
def valider_vente(*, vente, paiements, user):
    """Valide une ``VenteComptoir`` (XPOS1).

    ``paiements`` : liste de dicts ``{mode, montant, reference?}``. En une
    transaction :
      (a) crée la ``Facture`` légale via ``ventes.services`` (facture classique
          sans devis) ;
      (b) enregistre le/les ``Paiement`` ;
      (c) décrémente le stock immédiatement via ``stock.services`` (sortie) ;
      (d) applique le droit de timbre espèces (FG144) sur la part réglée cash.

    Refuse une remise de ligne au-delà du seuil d'approbation société sans
    approbation (T17). Refuse un règlement espèces sans session de caisse
    active (XPOS4). Renvoie la vente validée (avec ``facture`` posée).
    """
    if vente.statut != VenteComptoir.Statut.BROUILLON:
        raise VenteComptoirError('Cette vente a déjà été validée ou annulée.')
    lignes = list(vente.lignes.all())
    if not lignes:
        raise VenteComptoirError('Aucune ligne dans cette vente.')
    if not paiements:
        raise VenteComptoirError('Aucun règlement fourni.')

    for ligne in lignes:
        if not _discount_threshold_ok(
                vente.company, ligne.remise, approuve=False, user=user):
            raise VenteComptoirError(
                f'Remise de {ligne.remise} % sur « {ligne.designation} » '
                'dépasse le seuil autorisé sans approbation.')

    total_ttc = vente.total_ttc
    total_paiements = sum((_q2(p.get('montant')) for p in paiements), Decimal('0'))
    if total_paiements <= 0:
        raise VenteComptoirError('Le montant réglé doit être positif.')

    a_du_cash = any(
        (p.get('mode') or '').strip().lower() == MODE_ESPECES for p in paiements)
    if a_du_cash and vente.session_caisse_id is None:
        raise VenteComptoirError(
            'Aucune session de caisse ouverte : impossible d\'encaisser en '
            'espèces.')
    if a_du_cash and vente.session_caisse.statut != SessionCaisse.Statut.OUVERTE:
        raise VenteComptoirError('La session de caisse est clôturée.')

    # (a) Facture légale classique (sans devis) — via le thin service exposé
    # par ventes.services (numérotation collision-proof, jamais count()+1).
    from apps.ventes import services as ventes_services

    if vente.client_id is None:
        raise VenteComptoirError(
            'Un client est requis pour émettre la facture légale.')

    taux_tva = vente.taux_tva or Decimal('20')
    total_ht = _q2(vente.total_ht)
    montant_tva = _q2(total_ttc - total_ht)

    facture = ventes_services.creer_facture_classique(
        company=vente.company,
        client=vente.client,
        user=user,
        taux_tva=taux_tva,
        montant_ht=total_ht,
        montant_tva=montant_tva,
        montant_ttc=_q2(total_ttc),
        libelle=f'Vente comptoir {vente.reference}',
    )

    # (b) Paiement(s) — multi-modes, via le thin service ventes.services.
    today = timezone.localdate()
    total_especes = Decimal('0')
    for p in paiements:
        montant = _q2(p.get('montant'))
        mode = (p.get('mode') or '').strip().lower() or MODE_ESPECES
        ventes_services.enregistrer_paiement(
            facture=facture,
            montant=montant,
            mode=mode,
            date_paiement=p.get('date_paiement') or today,
            user=user,
            reference=p.get('reference') or '',
            note=p.get('note') or '',
        )
        if mode == MODE_ESPECES:
            total_especes += montant

    # (b bis) — les espèces encaissées entrent dans la caisse comptable de la
    # session (XPOS4) : sans ce mouvement, le solde théorique de la caisse à la
    # clôture ignore les ventes réglées en espèces et l'écart est faux.
    if total_especes > 0 and vente.session_caisse_id:
        from apps.compta.models import MouvementCaisse
        from apps.compta.services import enregistrer_mouvement_caisse
        enregistrer_mouvement_caisse(
            vente.session_caisse.caisse_comptable,
            sens=MouvementCaisse.Sens.ENTREE,
            montant=total_especes,
            date_mouvement=today,
            motif=f'Vente comptoir {vente.reference}',
            user=user,
        )

    # (c) Décrément stock immédiat (sortie) via stock.services.
    from apps.stock import services as stock_services
    for ligne in lignes:
        produit = ligne.produit
        produit.refresh_from_db()
        avant = produit.quantite_stock
        apres = avant - int(ligne.quantite)
        stock_services.record_stock_movement(
            company=vente.company,
            produit=produit,
            type_mouvement=stock_services.mouvement_type_sortie(),
            quantite=ligne.quantite,
            quantite_avant=avant,
            quantite_apres=apres,
            reference=vente.reference,
            note=f'Vente comptoir {vente.reference}',
            created_by=user,
        )

    # (d) Droit de timbre espèces (FG144) sur la part réglée cash.
    if total_especes > 0:
        from apps.compta.services import enregistrer_timbre_fiscal
        enregistrer_timbre_fiscal(
            vente.company,
            date_encaissement=today,
            base=total_especes,
            mode_reglement=MODE_ESPECES,
            facture_ref=facture.reference,
            tiers_type='client',
            tiers_id=vente.client_id,
            tiers_nom=str(vente.client) if vente.client_id else '',
            libelle=f'Vente comptoir {vente.reference}',
            user=user,
        )

    vente.facture = facture
    vente.statut = VenteComptoir.Statut.VALIDEE
    vente.date_validation = timezone.now()
    vente.caissier = vente.caissier or user
    vente.save(update_fields=[
        'facture', 'statut', 'date_validation', 'caissier'])
    return vente


# ── XPOS4 — Sessions de caisse comptoir ─────────────────────────────────────

class SessionCaisseError(Exception):
    """Erreur métier sur une session de caisse comptoir."""


@transaction.atomic
def ouvrir_session(*, company, caisse_comptable, caissier, fond_ouverture,
                   user=None):
    """Ouvre une session de caisse comptoir (XPOS4).

    Refuse d'ouvrir une deuxième session tant qu'une session est déjà ouverte
    pour la même caisse comptable. Journalise l'ouverture via ``apps.audit``.
    """
    if caisse_comptable.company_id != company.id:
        raise SessionCaisseError('Caisse comptable inconnue.')
    deja_ouverte = SessionCaisse.objects.filter(
        company=company, caisse_comptable=caisse_comptable,
        statut=SessionCaisse.Statut.OUVERTE).exists()
    if deja_ouverte:
        raise SessionCaisseError(
            'Une session est déjà ouverte pour cette caisse.')
    session = SessionCaisse(
        company=company,
        caisse_comptable=caisse_comptable,
        caissier=caissier,
        fond_ouverture=Decimal(fond_ouverture or 0),
        statut=SessionCaisse.Statut.OUVERTE,
    )
    session.full_clean()
    session.save()

    from apps.audit import recorder
    recorder.record(
        'create', instance=session, company=company, user=user or caissier,
        detail=f'Ouverture session caisse (fond {session.fond_ouverture}).')
    return session


def rapport_z(session):
    """Rapport Z de session : totaux par mode de paiement + nb ventes (XPOS4).

    Agrégat pur lecture, pas de nouveau modèle : parcourt les paiements des
    factures des ventes comptoir rattachées à la session (via le string-FK
    ``VenteComptoir.facture``), lus via ``ventes.selectors`` (jamais d'import
    direct du modèle ``Paiement``).
    """
    from apps.ventes.selectors import paiements_totaux_par_mode

    ventes_qs = session.ventes.filter(
        statut=VenteComptoir.Statut.VALIDEE, facture__isnull=False)
    facture_ids = list(ventes_qs.values_list('facture_id', flat=True))
    par_mode = {}
    for row in paiements_totaux_par_mode(facture_ids):
        par_mode[row['mode']] = {
            'total': row['total'] or Decimal('0'), 'nb': row['nb']}
    return {
        'nb_ventes': ventes_qs.count(),
        'par_mode': par_mode,
        'total': sum(
            (v['total'] for v in par_mode.values()), Decimal('0')),
    }


@transaction.atomic
def cloturer_session(*, session, montant_compte, montant_tpe_compte=None,
                     commentaire='', user=None):
    """Clôture une session de caisse (XPOS4 + XPOS18).

    Calcule attendu vs compté (espèces) et poste l'écart dans la caisse
    compta via ``compta.services.cloturer_caisse`` (FG124, pas de duplication
    du journal d'espèces). Si ``montant_tpe_compte`` est fourni, calcule aussi
    l'écart carte (XPOS18) — attendu = total des règlements « carte » de la
    session — et le journalise via ``apps.audit`` (symétrique du contrôle
    espèces existant). Renvoie la session clôturée.
    """
    if session.statut != SessionCaisse.Statut.OUVERTE:
        raise SessionCaisseError('Cette session est déjà clôturée.')

    from apps.compta.services import cloturer_caisse
    cloture = cloturer_caisse(
        session.caisse_comptable,
        date_cloture=timezone.localdate(),
        solde_compte=montant_compte,
        commentaire=commentaire,
        user=user,
    )

    session.statut = SessionCaisse.Statut.CLOTUREE
    session.date_cloture = timezone.now()
    session.montant_compte_cloture = _q2(montant_compte)
    session.cloture_caisse_comptable = cloture
    session.commentaire = commentaire or ''

    update_fields = [
        'statut', 'date_cloture', 'montant_compte_cloture',
        'cloture_caisse_comptable', 'commentaire',
    ]

    if montant_tpe_compte is not None:
        z = rapport_z(session)
        attendu_carte = z['par_mode'].get('carte', {}).get('total', Decimal('0'))
        compte_carte = _q2(montant_tpe_compte)
        ecart_carte = compte_carte - attendu_carte
        session.montant_tpe_compte = compte_carte
        session.ecart_tpe = ecart_carte
        update_fields += ['montant_tpe_compte', 'ecart_tpe']

    session.save(update_fields=update_fields)

    from apps.audit import recorder
    detail = f'Clôture session caisse — écart espèces {cloture.ecart}.'
    if session.ecart_tpe is not None:
        detail += f' Écart TPE {session.ecart_tpe}.'
    recorder.record(
        'update', instance=session, company=session.company,
        user=user or session.caissier, detail=detail)
    return session


# ── XPOS6 — Encaisser un devis/une facture existants au comptoir ───────────

class EncaissementCompteError(Exception):
    """Erreur métier lors d'un encaissement comptoir sur document existant."""


@transaction.atomic
def encaisser_facture_existante(*, facture, montant, mode, company, user,
                                reference='', note=''):
    """Encaisse un règlement (acompte/solde) sur une ``Facture`` EXISTANTE
    (XPOS6) — devis accepté ou facture émise, réutilise le modèle
    ``ventes.Paiement`` et l'échéancier acompte/solde EXISTANT (N33). Le POS
    n'ajoute que la saisie rapide du règlement + le reçu de la vente comptoir.
    Aucun changement de statut de devis hors du chemin existant.
    """
    from apps.ventes import services as ventes_services

    if facture.company_id != company.id:
        raise EncaissementCompteError('Facture inconnue.')
    montant = _q2(montant)
    if montant <= 0:
        raise EncaissementCompteError('Le montant réglé doit être positif.')
    solde_avant = ventes_services.facture_montant_du(facture)
    if montant > solde_avant:
        raise EncaissementCompteError(
            f'Le montant ({montant}) dépasse le solde restant dû '
            f'({solde_avant}).')

    paiement = ventes_services.enregistrer_paiement(
        facture=facture,
        montant=montant,
        mode=(mode or '').strip().lower() or MODE_ESPECES,
        date_paiement=timezone.localdate(),
        user=user,
        reference=reference,
        note=note or f'Encaissement comptoir sur {facture.reference}',
    )

    if paiement.mode == MODE_ESPECES:
        from apps.compta.services import enregistrer_timbre_fiscal
        enregistrer_timbre_fiscal(
            company,
            date_encaissement=paiement.date_paiement,
            base=montant,
            mode_reglement=MODE_ESPECES,
            facture_ref=facture.reference,
            tiers_type='client',
            tiers_id=facture.client_id,
            tiers_nom=str(facture.client) if facture.client_id else '',
            libelle=f'Reçu d\'acompte sur {facture.reference}',
            user=user,
        )

    return paiement


# ── XPOS15 — Click-and-collect (retrait en magasin) ─────────────────────────

class CommandeRetraitError(Exception):
    """Erreur métier sur une commande de retrait magasin."""


@transaction.atomic
def marquer_pret(*, commande, user):
    """Passe une commande retrait « à préparer » → « prêt » (XPOS15).

    Décrémente le stock à la PRÉPARATION (pas à la commande) via
    ``stock.services``. Envoie une notification client « prêt au retrait ».
    """
    if commande.statut != CommandeRetrait.Statut.A_PREPARER:
        raise CommandeRetraitError(
            'Seule une commande « à préparer » peut passer « prête ».')

    from apps.stock import services as stock_services
    for ligne in commande.lignes.all():
        produit = ligne.produit
        produit.refresh_from_db()
        avant = produit.quantite_stock
        apres = avant - int(ligne.quantite)
        stock_services.record_stock_movement(
            company=commande.company,
            produit=produit,
            type_mouvement=stock_services.mouvement_type_sortie(),
            quantite=ligne.quantite,
            quantite_avant=avant,
            quantite_apres=apres,
            reference=commande.reference,
            note=f'Préparation retrait {commande.reference}',
            created_by=user,
        )

    commande.statut = CommandeRetrait.Statut.PRET
    commande.date_pret = timezone.now()
    commande.save(update_fields=['statut', 'date_pret'])

    _notifier_commande_prete(commande)
    return commande


def _notifier_commande_prete(commande):
    """Notifie le client « prêt au retrait » (WhatsApp/email, best-effort).

    Même patron que les relances devis (``ventes.services``) : un lien
    wa.me pré-rempli si le client a un téléphone, un email direct sinon.
    N'élève jamais — une notification ratée ne bloque pas le workflow."""
    import logging
    logger = logging.getLogger(__name__)
    client = commande.client
    message = (
        f'Votre commande {commande.reference} est prête au retrait. '
        f'Code de retrait : {commande.code_retrait}')
    phone = getattr(client, 'telephone', '') if client else ''
    email = getattr(client, 'email', '') if client else ''
    try:
        if phone:
            import urllib.parse
            digits = ''.join(c for c in phone if c.isdigit())
            if digits:
                wa_url = f'https://wa.me/{digits}?text={urllib.parse.quote(message)}'
                logger.info(
                    'XPOS15: commande %s prête, lien WhatsApp %s',
                    commande.reference, wa_url)
                return
        if email:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                f'Commande {commande.reference} prête au retrait',
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                [email],
                fail_silently=True,
            )
    except Exception:
        logger.warning(
            'XPOS15: notification « prêt au retrait » échouée pour %s',
            commande.reference)


@transaction.atomic
def remettre_commande(*, commande, code_saisi, user):
    """Remet une commande « prête » au client après vérification du code
    de retrait (XPOS15). Passe la commande à « retiré »."""
    if commande.statut != CommandeRetrait.Statut.PRET:
        raise CommandeRetraitError(
            'Seule une commande « prête » peut être remise.')
    if (code_saisi or '').strip().upper() != (commande.code_retrait or '').upper():
        raise CommandeRetraitError('Code de retrait incorrect.')
    commande.statut = CommandeRetrait.Statut.RETIRE
    commande.date_retrait = timezone.now()
    commande.save(update_fields=['statut', 'date_retrait'])
    return commande
