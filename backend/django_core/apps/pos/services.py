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

    # (c bis) XPOS9 — capture n° de série → garantie SAV automatique. Gated
    # sur `produit.suivi_serie` (défaut off, rien ne change) ET la présence
    # de n° de série saisis sur la ligne ; best-effort par série (une série en
    # doublon ne bloque jamais la vente déjà validée).
    if vente.client_id is not None:
        from apps.sav.services import (
            SerieDejaEnregistreeError, creer_equipement_depuis_vente_pos,
        )
        for ligne in lignes:
            produit = ligne.produit
            if not getattr(produit, 'suivi_serie', False):
                continue
            for serie in (ligne.numeros_serie or []):
                serie = (serie or '').strip()
                if not serie:
                    continue
                try:
                    creer_equipement_depuis_vente_pos(
                        company=vente.company, produit=produit,
                        client=vente.client, numero_serie=serie,
                        date_vente=today, created_by=user)
                except SerieDejaEnregistreeError:
                    # Ne bloque jamais la vente déjà encaissée : la série en
                    # doublon est simplement ignorée (déjà tracée ailleurs).
                    pass

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


# ── NTRET2 — Rapport X (lecture) / Rapport Z (clôture définitive) formels ───

def rapport_x(session):
    """Rapport X (NTRET2) : lecture à tout moment, AUCUN effet de bord,
    relisible autant de fois que nécessaire (session ouverte ou déjà
    clôturée). Alias explicite de l'agrégat pur ``rapport_z`` sous un nom
    distinct — jamais confondu avec le rapport Z OFFICIEL (numéroté, généré
    une seule fois, voir ``generer_rapport_z``)."""
    return rapport_z(session)


class RapportZError(Exception):
    """Erreur métier sur la génération du rapport Z officiel."""


class RapportZDejaGenereError(RapportZError):
    """Le rapport Z de cette session a déjà été généré (2e appel → 409)."""


@transaction.atomic
def generer_rapport_z(session, *, user=None):
    """Rapport Z OFFICIEL (NTRET2) : clôture définitive de la session.

    Exige une session déjà CLÔTURÉE (``cloturer_session``) et ne peut être
    généré qu'UNE SEULE FOIS — la numérotation séquentielle anti-collision
    (``core.numbering.next_reference``, jamais count()+1) est posée à la
    première génération réussie et n'est plus jamais réattribuée. Un 2e appel
    sur la même session lève ``RapportZDejaGenereError`` (traduit en 409 côté
    vue) — exigence des contrôles fiscaux marocains : un Z unique par
    clôture. Renvoie l'agrégat + le numéro attribué.
    """
    if session.statut != SessionCaisse.Statut.CLOTUREE:
        raise RapportZError(
            'La session doit être clôturée avant de générer le rapport Z.')
    if session.numero_rapport_z:
        raise RapportZDejaGenereError(
            'Le rapport Z de cette session a déjà été généré '
            f'(n° {session.numero_rapport_z}).')

    from core.numbering import next_reference
    numero = next_reference(
        SessionCaisse, 'Z', session.company, field='numero_rapport_z')
    session.numero_rapport_z = numero
    session.save(update_fields=['numero_rapport_z'])

    from apps.audit import recorder
    recorder.record(
        'update', instance=session, company=session.company,
        user=user or session.caissier,
        detail=f'Rapport Z généré — n° {numero}.')

    data = rapport_z(session)
    data['numero_rapport_z'] = numero
    return data


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


# ── NTRET3 — Multi-caissiers avec PIN de session ────────────────────────────

class PinCaissierError(Exception):
    """Erreur métier sur le PIN de verrouillage rapide caissier."""


def definir_pin(*, company, user, raw_pin):
    """Définit (ou change) le PIN de verrouillage rapide d'un caissier
    (NTRET3). 4 à 6 chiffres — jamais stocké en clair (hashers Django)."""
    from .models import CodePinCaissier

    pin = str(raw_pin or '').strip()
    if not pin.isdigit() or not (4 <= len(pin) <= 6):
        raise PinCaissierError('Le PIN doit comporter entre 4 et 6 chiffres.')
    code, _ = CodePinCaissier.objects.get_or_create(
        company=company, user=user)
    code.set_pin(pin)
    code.save(update_fields=['pin_hash', 'date_modification'])
    return code


def verifier_pin(*, company, user_id, raw_pin, caissier_precedent=None,
                 acting_user=None):
    """Vérifie le PIN d'un caissier (NTRET3) : déverrouille l'écran caisse
    sans re-login JWT complet, sans perdre le panier en cours. Refuse un PIN
    inconnu/erroné — le throttle applicatif (5 tentatives/5 min) vit côté vue
    (``PinCaissierThrottle``). Journalise un CHANGEMENT DE CAISSIER (via
    ``apps.audit``) quand l'utilisateur qui se déverrouille diffère du
    caissier précédemment actif sur ce poste (transmis par le client)."""
    from .models import CodePinCaissier

    code = CodePinCaissier.objects.filter(
        company=company, user_id=user_id).select_related('user').first()
    if code is None or not code.check_pin(raw_pin):
        raise PinCaissierError('PIN incorrect.')

    user = code.user
    caissier_precedent = str(caissier_precedent) if caissier_precedent else None
    if caissier_precedent and caissier_precedent != str(user.id):
        from apps.audit import recorder
        recorder.record(
            'update', instance=code, company=company,
            user=acting_user or user,
            detail=(
                f'Changement de caissier au poste (PIN) : '
                f'{caissier_precedent} → {user.username} (#{user.id}).'),
        )
    return user


# ── NTRET5 — Arrhes / acompte sur commande comptoir ─────────────────────────

class ArrhesError(Exception):
    """Erreur métier sur un encaissement d'arrhes/solde (NTRET5)."""


@transaction.atomic
def encaisser_arrhes(*, vente, montant_arrhes, paiement, user):
    """Encaisse des arrhes sur une vente comptoir (NTRET5) : article manquant
    en stock ou sur-mesure. Crée la facture légale + le paiement PARTIEL sur
    les mêmes rails que ``valider_vente`` (numérotation, timbre fiscal,
    mouvement de caisse), mais passe la vente en ``EN_ATTENTE_SOLDE`` — la
    marchandise reste bloquée (``marchandise_remise=False``) tant que le
    solde n'est pas réglé. Le stock N'EST PAS décrémenté ici (la marchandise
    ne bouge pas encore) — voir ``encaisser_solde_arrhes``. Le règlement
    fourni doit correspondre EXACTEMENT au montant des arrhes (pas
    d'ambiguïté sur un trop/pas assez perçu)."""
    if vente.statut != VenteComptoir.Statut.BROUILLON:
        raise ArrhesError(
            'Cette vente a déjà été validée, mise en arrhes ou annulée.')
    lignes = list(vente.lignes.all())
    if not lignes:
        raise ArrhesError('Aucune ligne dans cette vente.')
    if vente.client_id is None:
        raise ArrhesError('Un client est requis pour émettre la facture légale.')

    total_ttc = _q2(vente.total_ttc)
    montant_arrhes = _q2(montant_arrhes)
    if montant_arrhes <= 0:
        raise ArrhesError('Le montant des arrhes doit être positif.')
    if montant_arrhes >= total_ttc:
        raise ArrhesError(
            'Le montant des arrhes doit être strictement inférieur au total '
            'de la vente (sinon utilisez un encaissement complet).')
    montant_paiement = _q2((paiement or {}).get('montant'))
    if montant_paiement != montant_arrhes:
        raise ArrhesError(
            'Le règlement doit correspondre exactement au montant des '
            f'arrhes ({montant_arrhes}).')

    from apps.ventes import services as ventes_services

    taux_tva = vente.taux_tva or Decimal('20')
    total_ht = _q2(vente.total_ht)
    montant_tva = _q2(total_ttc - total_ht)
    facture = ventes_services.creer_facture_classique(
        company=vente.company, client=vente.client, user=user,
        taux_tva=taux_tva, montant_ht=total_ht, montant_tva=montant_tva,
        montant_ttc=total_ttc,
        libelle=f'Vente comptoir {vente.reference} (arrhes)',
    )

    mode = (paiement.get('mode') or '').strip().lower() or MODE_ESPECES
    today = timezone.localdate()
    ventes_services.enregistrer_paiement(
        facture=facture, montant=montant_paiement, mode=mode,
        date_paiement=paiement.get('date_paiement') or today, user=user,
        reference=paiement.get('reference') or '',
        note=f'Arrhes sur {vente.reference}',
    )
    _poster_encaissement_especes(
        vente=vente, mode=mode, montant=montant_paiement,
        facture=facture, motif=f'Arrhes {vente.reference}', user=user)

    vente.facture = facture
    vente.statut = VenteComptoir.Statut.EN_ATTENTE_SOLDE
    vente.montant_arrhes = montant_arrhes
    vente.caissier = vente.caissier or user
    vente.save(update_fields=[
        'facture', 'statut', 'montant_arrhes', 'caissier'])
    return vente


def solde_restant_arrhes(vente):
    """Solde restant à régler avant remise de marchandise (NTRET5). 0 pour
    une vente qui n'est pas (ou plus) en attente de solde."""
    if vente.montant_arrhes is None:
        return Decimal('0')
    return _q2(vente.total_ttc) - _q2(vente.montant_arrhes)


@transaction.atomic
def encaisser_solde_arrhes(*, vente, paiement, user):
    """Encaisse le SOLDE restant d'une vente ``EN_ATTENTE_SOLDE`` (NTRET5) —
    décrémente ENFIN le stock (jamais fait à l'encaissement des arrhes),
    passe la vente à ``VALIDEE`` et débloque la remise de marchandise. Le
    règlement doit correspondre exactement au solde restant."""
    if vente.statut != VenteComptoir.Statut.EN_ATTENTE_SOLDE:
        raise ArrhesError("Cette vente n'est pas en attente de solde.")
    solde = solde_restant_arrhes(vente)
    montant_paiement = _q2((paiement or {}).get('montant'))
    if montant_paiement != solde:
        raise ArrhesError(
            f'Le règlement ({montant_paiement}) doit correspondre exactement '
            f'au solde restant ({solde}).')

    from apps.ventes import services as ventes_services

    mode = (paiement.get('mode') or '').strip().lower() or MODE_ESPECES
    today = timezone.localdate()
    ventes_services.enregistrer_paiement(
        facture=vente.facture, montant=montant_paiement, mode=mode,
        date_paiement=paiement.get('date_paiement') or today, user=user,
        reference=paiement.get('reference') or '',
        note=f'Solde sur {vente.reference}',
    )
    _poster_encaissement_especes(
        vente=vente, mode=mode, montant=montant_paiement,
        facture=vente.facture, motif=f'Solde {vente.reference}', user=user)

    from apps.stock import services as stock_services
    for ligne in vente.lignes.all():
        produit = ligne.produit
        produit.refresh_from_db()
        avant = produit.quantite_stock
        apres = avant - int(ligne.quantite)
        stock_services.record_stock_movement(
            company=vente.company, produit=produit,
            type_mouvement=stock_services.mouvement_type_sortie(),
            quantite=ligne.quantite, quantite_avant=avant, quantite_apres=apres,
            reference=vente.reference,
            note=f'Vente comptoir {vente.reference} (solde arrhes)',
            created_by=user,
        )

    vente.statut = VenteComptoir.Statut.VALIDEE
    vente.date_validation = timezone.now()
    vente.marchandise_remise = True
    vente.save(update_fields=[
        'statut', 'date_validation', 'marchandise_remise'])
    return vente


@transaction.atomic
def remettre_marchandise_override(*, vente, user, motif):
    """Override ADMIN (NTRET5) : débloque la remise de marchandise AVANT que
    le solde soit réglé — cas exceptionnel (client de confiance, urgence
    chantier…). Motif OBLIGATOIRE, journalisé via ``apps.audit``. Ne change
    PAS le statut de la vente (reste ``EN_ATTENTE_SOLDE`` — le solde reste
    dû) : seule la remise physique est débloquée."""
    if vente.statut != VenteComptoir.Statut.EN_ATTENTE_SOLDE:
        raise ArrhesError("Cette vente n'est pas en attente de solde.")
    if vente.marchandise_remise:
        raise ArrhesError('La marchandise a déjà été remise.')
    if not (motif or '').strip():
        raise ArrhesError('Un motif est requis pour cet override.')

    vente.marchandise_remise = True
    vente.save(update_fields=['marchandise_remise'])

    from apps.audit import recorder
    recorder.record(
        'update', instance=vente, company=vente.company, user=user,
        detail=(
            'Override admin — marchandise remise AVANT solde réglé '
            f'(solde restant {solde_restant_arrhes(vente)}). '
            f'Motif : {motif}'),
    )
    return vente


def _poster_encaissement_especes(*, vente, mode, montant, facture, motif, user):
    """Mouvement de caisse + timbre fiscal sur un règlement espèces
    (factorisé entre ``encaisser_arrhes``/``encaisser_solde_arrhes`` et le
    même bloc dans ``valider_vente``)."""
    if mode != MODE_ESPECES or montant <= 0:
        return
    today = timezone.localdate()
    if vente.session_caisse_id:
        from apps.compta.models import MouvementCaisse
        from apps.compta.services import enregistrer_mouvement_caisse
        enregistrer_mouvement_caisse(
            vente.session_caisse.caisse_comptable,
            sens=MouvementCaisse.Sens.ENTREE, montant=montant,
            date_mouvement=today, motif=motif, user=user)
    from apps.compta.services import enregistrer_timbre_fiscal
    enregistrer_timbre_fiscal(
        vente.company, date_encaissement=today, base=montant,
        mode_reglement=MODE_ESPECES, facture_ref=facture.reference,
        tiers_type='client', tiers_id=vente.client_id,
        tiers_nom=str(vente.client) if vente.client_id else '',
        libelle=motif, user=user)


# ── NTRET12 — Moteur de promotions panier (apps.promotions) ────────────────

def promotions_applicables(vente, *, maintenant=None):
    """NTRET12 — promotions actives applicables au panier de ``vente``.

    Import FONCTION-LOCAL vers ``apps.promotions.services`` — jamais
    l'inverse (règle de modularité cross-app, CLAUDE.md). Best-effort : une
    erreur du moteur promo (ex. app absente, règle mal configurée) ne
    bloque JAMAIS une vente — renvoie ``[]`` plutôt que de lever. Consommé
    par l'écran caisse (aperçu avant encaissement) et par
    ``apps/promotions`` pour les tests d'intégration."""
    try:
        from apps.promotions.services import evaluer_panier
        return evaluer_panier(
            vente.company, vente.lignes.all(), maintenant=maintenant)
    except Exception:
        return []


def total_remises_promotions(vente, *, maintenant=None):
    """Somme des remises promo retenues (MAD) pour le panier de ``vente``."""
    return sum(
        (r.montant for r in promotions_applicables(vente, maintenant=maintenant)),
        Decimal('0'))
