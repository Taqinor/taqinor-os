"""Services ÉCRITURE du vertical BTP/EPC (Groupe NTCON).

Toute mutation d'état (transition de statut, capture de signature,
génération de facture / impact budget, verrouillage DGD…) passe par ce
module — jamais une écriture directe depuis la vue. Les écritures cross-app
(facture ``ventes``, notification) passent par les ``services.py``/
``notify()`` de l'app CIBLE via import FONCTION-LOCAL, jamais un import de
modèle d'une autre app.
"""
from __future__ import annotations

import logging
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    LOTS_TYPES_DEFAUT, ReserveChantier, ReserveChantierHistorique,
)

logger = logging.getLogger(__name__)


class TransitionInvalide(ValueError):
    """Transition de statut illégale (état → état non autorisé)."""


def _notifier_btp(user, event_type_name, titre, corps, *, company=None, link=None):
    """Notification best-effort via ``apps.notifications`` (jamais d'exception).

    ``event_type_name`` est le nom d'un membre EXISTANT de ``EventType``
    (registre fermé — ``apps/notifications`` est hors périmètre d'édition de
    ce lot). On réutilise l'événement le plus proche sémantiquement, comme
    ``qhse.services._notifier_capa`` réutilise ``MAINTENANCE_DUE`` pour les
    relances CAPA — précédent déjà établi dans ce dépôt.
    """
    if user is None:
        return None
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        event_type = getattr(EventType, event_type_name, None)
        if event_type is None:
            return None
        return notify(
            user, event_type, titre, body=corps, link=link,
            company=company or getattr(user, 'company', None))
    except Exception:  # pragma: no cover - défensif, best-effort
        return None


def _emettre(signal_nom, **kwargs):
    """NTCON31 — émet un événement du bus ``core.events`` (best-effort).

    Le bus est le SEUL canal vers les abonnés externes (webhooks
    ``apps.publicapi``) : ``btp_chantier`` n'importe JAMAIS ``publicapi``, il
    émet et ignore qui écoute. Une exception d'un abonné ne doit jamais
    remonter dans la transaction métier qui vient de réussir.
    """
    try:
        from core import events
        signal = getattr(events, signal_nom, None)
        if signal is None:
            return
        signal.send(sender=None, **kwargs)
    except Exception:  # noqa: BLE001 - best-effort, jamais bloquant
        logger.warning('btp_chantier: emission %s echouee', signal_nom,
                       exc_info=True)


@transaction.atomic
def _transitionner_reserve(reserve, nouveau_statut, *, auteur, motif=''):
    """Change le statut d'une réserve et journalise la transition (NTCON2)."""
    ancien = reserve.statut
    reserve.statut = nouveau_statut
    reserve.save(update_fields=['statut', 'updated_at'])
    ReserveChantierHistorique.objects.create(
        company=reserve.company, reserve=reserve,
        ancien_statut=ancien, nouveau_statut=nouveau_statut,
        motif=motif, auteur=auteur)
    return reserve


def enregistrer_creation_reserve(reserve, *, created_by):
    """NTCON1 — journalise la création + notifie le responsable si la
    gravité est bloquante (appelé depuis ``ReserveChantierViewSet.perform_
    create`` juste après ``serializer.save()``)."""
    ReserveChantierHistorique.objects.create(
        company=reserve.company, reserve=reserve, ancien_statut='',
        nouveau_statut=reserve.statut, auteur=created_by)
    if (reserve.gravite == ReserveChantier.Gravite.BLOQUANTE
            and reserve.responsable_leve_id):
        _notifier_btp(
            reserve.responsable_leve, 'APPROVAL_REQUESTED',
            'Réserve bloquante à lever',
            f'Réserve #{reserve.id} ({reserve.lot or "chantier"}) requiert '
            'une action.', company=reserve.company,
            link=f'/btp/reserves/{reserve.id}')
    return reserve


def lever_reserve(reserve, *, user, signature_nom, ip_adresse='', user_agent=''):
    """NTCON2 — lève une réserve : capture la signature typée du constatant,
    horodate/attribue serveur, journalise, notifie le créateur.

    Lève ``TransitionInvalide`` si la réserve n'est pas dans un état levable
    (``ouverte``/``en_cours``/``contestee``). L'APPEL doit avoir DÉJÀ vérifié
    qu'une photo « après » existe (garde côté vue — 400 sans photo).
    """
    from .models import SignatureBtp

    if reserve.statut not in (
            ReserveChantier.Statut.OUVERTE, ReserveChantier.Statut.EN_COURS,
            ReserveChantier.Statut.CONTESTEE):
        raise TransitionInvalide(
            f'Réserve {reserve.pk} : impossible de lever depuis « '
            f'{reserve.statut} ».')

    with transaction.atomic():
        from django.contrib.contenttypes.models import ContentType
        signature = SignatureBtp.objects.create(
            company=reserve.company,
            content_type=ContentType.objects.get_for_model(ReserveChantier),
            object_id=reserve.pk,
            contexte='levee_reserve',
            signataire_nom=signature_nom,
            signataire=user,
            ip_adresse=ip_adresse,
            user_agent=user_agent,
        )
        reserve.date_levee = timezone.now()
        reserve.leve_par = user
        reserve.save(update_fields=['date_levee', 'leve_par', 'updated_at'])
        _transitionner_reserve(
            reserve, ReserveChantier.Statut.LEVEE, auteur=user)

    if reserve.created_by_id and reserve.created_by_id != getattr(user, 'id', None):
        _notifier_btp(
            reserve.created_by, 'APPROVAL_DECIDED', 'Réserve levée',
            f'Réserve #{reserve.id} a été levée par {user}.',
            company=reserve.company, link=f'/btp/reserves/{reserve.id}')
    # NTCON31 — `reserve.levee` sur le bus (abonné : webhook publicapi).
    _emettre('btp_reserve_levee', reserve=reserve, company=reserve.company,
             user=user)
    return signature


def contester_reserve(reserve, *, user, motif):
    """NTCON2 — réouvre une réserve « levée » (contestée + motif). Lève
    ``TransitionInvalide`` si la réserve n'est pas levée."""
    if reserve.statut != ReserveChantier.Statut.LEVEE:
        raise TransitionInvalide(
            f'Réserve {reserve.pk} : seule une réserve levée peut être '
            'contestée.')
    reserve.motif_contestation = motif
    reserve.save(update_fields=['motif_contestation', 'updated_at'])
    _transitionner_reserve(
        reserve, ReserveChantier.Statut.CONTESTEE, auteur=user, motif=motif)
    return reserve


# ── NTCON3 — RFI ─────────────────────────────────────────────────────────────

def _prochain_numero_rfi(chantier):
    """Numéro de RFI SUIVANT pour ce chantier (jamais ``count()+1``).

    Verrouille la ligne ``chantier`` (``select_for_update``) le temps du
    calcul pour sérialiser des créations concurrentes sur le MÊME chantier,
    puis prend le plus haut ``numero`` déjà UTILISÉ + 1 — pattern
    ``gestion_projet.services.prochain_numero_situation``. Doit être appelé
    dans une transaction atomique par l'appelant.
    """
    from django.db.models import Max

    from .models import RFI

    chantier.__class__.objects.select_for_update().get(pk=chantier.pk)
    plus_haut = RFI.objects.filter(
        chantier=chantier).aggregate(Max('numero'))['numero__max'] or 0
    return plus_haut + 1


@transaction.atomic
def creer_rfi(*, company, chantier, pose_par, delai_jours=5, **kwargs):
    """NTCON3 — crée un RFI, numéro race-safe par chantier + échéance en
    jours OUVRÉS (férié-aware, ``notifications.calendar_utils``). Notifie le
    destinataire (best-effort)."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from .models import RFI

    numero = _prochain_numero_rfi(chantier)
    date_limite = ajouter_jours_ouvres(
        timezone.localdate(), delai_jours, company)
    rfi = RFI.objects.create(
        company=company, chantier=chantier, numero=numero,
        pose_par=pose_par, delai_jours=delai_jours,
        date_limite_reponse=date_limite, **kwargs)
    if rfi.destinataire_user_id:
        _notifier_btp(
            rfi.destinataire_user, 'APPROVAL_REQUESTED',
            f'RFI #{rfi.numero} en attente de réponse', rfi.question[:200],
            company=company, link=f'/btp/rfi/{rfi.id}')
    return rfi


def repondre_rfi(rfi, *, auteur, texte):
    """NTCON3 — ajoute une réponse et clôt le cycle (statut → repondu)."""
    from .models import RFI, RFIReponse

    if rfi.statut == RFI.Statut.CLOS:
        raise TransitionInvalide(f'RFI {rfi.pk} : déjà clos.')
    with transaction.atomic():
        reponse = RFIReponse.objects.create(
            company=rfi.company, rfi=rfi, texte=texte, auteur=auteur)
        rfi.statut = RFI.Statut.REPONDU
        rfi.save(update_fields=['statut'])
    if rfi.pose_par_id and rfi.pose_par_id != getattr(auteur, 'id', None):
        _notifier_btp(
            rfi.pose_par, 'APPROVAL_DECIDED', f'RFI #{rfi.numero} répondu',
            texte[:200], company=rfi.company, link=f'/btp/rfi/{rfi.id}')
    # NTCON31 — `rfi.repondu` sur le bus (abonné : webhook publicapi).
    _emettre('btp_rfi_repondu', rfi=rfi, company=rfi.company,
             reponse=reponse, user=auteur)
    return reponse


def clore_rfi(rfi, *, user):
    """NTCON3 — clôt un RFI répondu (ou directement ouvert, sans réponse)."""
    from .models import RFI

    if rfi.statut == RFI.Statut.CLOS:
        raise TransitionInvalide(f'RFI {rfi.pk} : déjà clos.')
    rfi.statut = RFI.Statut.CLOS
    rfi.save(update_fields=['statut'])
    return rfi


# ── NTCON5 — Visas de documents techniques ──────────────────────────────────

def _date_limite_visa(company, delai_jours):
    from apps.notifications.calendar_utils import ajouter_jours_ouvres
    return ajouter_jours_ouvres(timezone.localdate(), delai_jours, company)


def soumettre_visa(
        *, company, chantier, document_ged_id, soumis_par,
        type_visa, delai_revue_jours=10):
    """NTCON5 — soumet un nouveau visa (référence race-safe ``core.
    numbering``, préfixe ``VIS``)."""
    from core.numbering import create_with_reference

    from .models import VisaDocument

    def _create(reference):
        return VisaDocument.objects.create(
            company=company, chantier=chantier,
            document_ged_id=document_ged_id, reference=reference,
            type_visa=type_visa, soumis_par=soumis_par,
            date_soumission=timezone.now(),
            delai_revue_jours=delai_revue_jours,
            date_limite=_date_limite_visa(company, delai_revue_jours))

    return create_with_reference(VisaDocument, 'VIS', company, _create)


def soumettre_observations_visa(visa, *, user, observations):
    """NTCON5 — passe le visa en revue avec observations (sans décider)."""
    from .models import VisaDocument

    if visa.statut in VisaDocument.STATUTS_DECIDES:
        raise TransitionInvalide(
            f'Visa {visa.reference} : déjà décidé ({visa.statut}).')
    visa.statut = VisaDocument.Statut.EN_REVUE
    visa.observations = observations
    visa.revu_par = user
    visa.date_revue = timezone.now()
    visa.save(update_fields=[
        'statut', 'observations', 'revu_par', 'date_revue'])
    if visa.soumis_par_id:
        _notifier_btp(
            visa.soumis_par, 'APPROVAL_REMINDER',
            f'Observations sur le visa {visa.reference}', observations[:200],
            company=visa.company, link=f'/btp/visas/{visa.id}')
    return visa


def _decider_visa(visa, *, user, nouveau_statut, observations=''):
    from .models import VisaDocument

    if visa.statut in VisaDocument.STATUTS_DECIDES:
        raise TransitionInvalide(
            f'Visa {visa.reference} : déjà décidé ({visa.statut}).')
    visa.statut = nouveau_statut
    if observations:
        visa.observations = observations
    visa.revu_par = user
    visa.date_revue = timezone.now()
    visa.save(update_fields=[
        'statut', 'observations', 'revu_par', 'date_revue'])
    if visa.soumis_par_id:
        _notifier_btp(
            visa.soumis_par, 'APPROVAL_DECIDED',
            f'Visa {visa.reference} : {visa.get_statut_display()}',
            observations[:200], company=visa.company,
            link=f'/btp/visas/{visa.id}')
    return visa


def approuver_visa(visa, *, user, avec_observations=False, observations=''):
    """NTCON5 — approuve (sans réserve ou avec observations)."""
    from .models import VisaDocument

    statut = (
        VisaDocument.Statut.APPROUVE_AVEC_OBSERVATIONS if avec_observations
        else VisaDocument.Statut.APPROUVE_SANS_RESERVE)
    decide = _decider_visa(
        visa, user=user, nouveau_statut=statut, observations=observations)
    # NTCON31 — `visa.approuve` sur le bus (abonné : webhook publicapi).
    # JAMAIS émis sur un refus : l'événement s'appelle « approuvé ».
    _emettre('btp_visa_approuve', visa=decide, company=decide.company,
             user=user)
    return decide


def refuser_visa(visa, *, user, observations=''):
    """NTCON5 — refuse le visa."""
    from .models import VisaDocument
    return _decider_visa(
        visa, user=user, nouveau_statut=VisaDocument.Statut.REFUSE,
        observations=observations)


def resoumettre_visas_pour_document(document_ged_id, *, company=None):
    """NTCON5 — ré-ouvre (statut → soumis) tous les visas d'un document GED
    quand une nouvelle ``ged.DocumentVersion`` y est déposée.

    Appelé depuis ``receivers.py`` (signal ``post_save`` sur ``ged.
    DocumentVersion``, connexion paresseuse via ``apps.get_model``). Ré-ouvre
    TOUT visa portant sur ce document (quel que soit son statut courant — une
    nouvelle version invalide aussi une revue en cours), incrémente
    ``nb_resoumissions`` (ré-ouverture tracée) et recalcule l'échéance.
    """
    from django.db.models import F

    from .models import VisaDocument

    qs = VisaDocument.objects.filter(document_ged_id=document_ged_id)
    if company is not None:
        qs = qs.filter(company=company)
    resoumis = []
    for visa in qs:
        visa.statut = VisaDocument.Statut.SOUMIS
        # Compteur partagé : incrément ATOMIQUE via F() (jamais un
        # read-modify-write non verrouillé — une seconde version déposée en
        # concurrence ne doit pas perdre une incrémentation).
        visa.nb_resoumissions = F('nb_resoumissions') + 1
        visa.date_soumission = timezone.now()
        visa.observations = ''
        visa.revu_par = None
        visa.date_revue = None
        visa.date_limite = _date_limite_visa(
            visa.company, visa.delai_revue_jours)
        visa.save(update_fields=[
            'statut', 'nb_resoumissions', 'date_soumission', 'observations',
            'revu_par', 'date_revue', 'date_limite'])
        # ``nb_resoumissions`` porte l'expression F() en mémoire après save :
        # recharger la valeur entière résolue pour l'objet renvoyé.
        visa.refresh_from_db(fields=['nb_resoumissions'])
        resoumis.append(visa)
    return resoumis


# ── NTCON7/NTCON8 — Avenant de chantier (chiffrage + approbation client) ───

def creer_avenant_chantier(
        *, company, chantier, cree_par, description, montant_ht,
        impact_delai_jours=None, impact_budget=False,
        avenant_contrat_id=None, lignes=None):
    """NTCON7 — crée un avenant de chantier (référence race-safe ``core.
    numbering``, préfixe ``AVC``)."""
    from core.numbering import create_with_reference

    from .models import AvenantChantier

    def _create(reference):
        return AvenantChantier.objects.create(
            company=company, chantier=chantier, reference=reference,
            avenant_contrat_id=avenant_contrat_id, description=description,
            montant_ht=montant_ht, impact_delai_jours=impact_delai_jours,
            impact_budget=impact_budget, lignes=lignes or [],
            cree_par=cree_par)

    return create_with_reference(AvenantChantier, 'AVC', company, _create)


def soumettre_client_avenant(avenant, *, user, validite_jours=30):
    """NTCON8 — passe l'avenant en « soumis au client » et (RE)génère son
    jeton public (invalide tout lien précédemment émis), avec expiration."""
    from datetime import timedelta

    from .models import AvenantChantier, _default_btp_token

    if avenant.statut != AvenantChantier.Statut.BROUILLON:
        raise TransitionInvalide(
            f'Avenant {avenant.reference} : seul un avenant brouillon peut '
            'être soumis au client.')
    avenant.statut = AvenantChantier.Statut.SOUMIS_CLIENT
    avenant.token = _default_btp_token()
    avenant.token_expires_at = timezone.now() + timedelta(days=validite_jours)
    avenant.save(update_fields=[
        'statut', 'token', 'token_expires_at', 'updated_at'])
    return avenant


def _resoudre_budget_projet_id(chantier):
    """NTCON7 — best-effort, LECTURE SEULE : résout l'ID du ``BudgetProjet``
    actif du projet auquel ce ``chantier`` est rattaché.

    Traverse ``gestion_projet.ProjetChantier`` (référence lâche ``chantier_
    id``) puis ``apps.gestion_projet.selectors.budget_effectif`` (lecture
    sanctionnée cross-app). Aucune fonction de SERVICE n'existe côté
    ``gestion_projet`` pour MUTER un budget depuis une autre app — l'impact
    se traduit donc par cette référence lâche, jamais une écriture directe
    (frontière cross-app, CLAUDE.md). Ne lève JAMAIS (best-effort) : renvoie
    ``None`` si rien n'est trouvé, n'empêche jamais l'approbation.
    """
    from django.apps import apps as django_apps

    try:
        ProjetChantier = django_apps.get_model('gestion_projet', 'ProjetChantier')
        pc = ProjetChantier.objects.filter(
            chantier_id=chantier.pk).select_related('projet').first()
        if pc is None:
            return None
        from apps.gestion_projet.selectors import budget_effectif
        budget = budget_effectif(pc.projet)
        return budget.id if budget else None
    except Exception:  # pragma: no cover - défensif, best-effort
        return None


@transaction.atomic
def approuver_avenant(avenant, *, user=None):
    """NTCON7 — approuve l'avenant : IMPACTE le budget projet (référence
    lâche best-effort, ``impact_budget=True``) OU génère une ``ventes.
    Facture`` d'acompte (``impact_budget=False``, fonction cross-app
    sanctionnée ``apps.ventes.services.creer_facture_acompte_situation``).

    ``user=None`` couvre le signataire CLIENT externe (NTCON8, sans compte
    ERP). Idempotent : lève ``TransitionInvalide`` si déjà décidé (approuvé
    ou refusé) — un second appel n'impacte jamais deux fois.
    """
    from .models import AvenantChantier

    if avenant.statut in (
            AvenantChantier.Statut.APPROUVE, AvenantChantier.Statut.REFUSE):
        raise TransitionInvalide(
            f'Avenant {avenant.reference} : déjà décidé ({avenant.statut}).')

    if avenant.impact_budget:
        avenant.budget_projet_id = _resoudre_budget_projet_id(avenant.chantier)
    else:
        if not avenant.chantier.client_id:
            raise TransitionInvalide(
                f"Avenant {avenant.reference} : le chantier n'a pas de "
                "client rattaché — impossible de générer la facture "
                "d'acompte.")
        from apps.ventes.services import creer_facture_acompte_situation
        facture = creer_facture_acompte_situation(
            company=avenant.company, client=avenant.chantier.client,
            user=user, libelle=f'Avenant {avenant.reference}',
            montant_periode_ht=avenant.montant_ht)
        avenant.facture_id = facture.id

    avenant.statut = AvenantChantier.Statut.APPROUVE
    avenant.approuve_par = user
    avenant.date_approbation = timezone.now()
    avenant.save(update_fields=[
        'statut', 'approuve_par', 'date_approbation', 'budget_projet_id',
        'facture_id', 'updated_at'])
    return avenant


def refuser_avenant(avenant, *, user, motif=''):
    """NTCON7 — refuse l'avenant : n'impacte JAMAIS ni budget ni facture."""
    from .models import AvenantChantier

    if avenant.statut in (
            AvenantChantier.Statut.APPROUVE, AvenantChantier.Statut.REFUSE):
        raise TransitionInvalide(
            f'Avenant {avenant.reference} : déjà décidé ({avenant.statut}).')
    avenant.statut = AvenantChantier.Statut.REFUSE
    avenant.motif_refus = motif
    avenant.save(update_fields=['statut', 'motif_refus', 'updated_at'])
    return avenant


def approuver_avenant_public(avenant, *, signataire_nom, ip_adresse='', user_agent=''):
    """NTCON8 — approbation CLIENT via lien public tokenisé : capture la
    signature typée (loi 53-05, IP/user-agent serveur) PUIS déclenche
    ``approuver_avenant`` (``user=None``, signataire externe). Idempotent :
    refuse (``TransitionInvalide``) un second appel sur un avenant déjà
    décidé — l'impact NTCON7 ne se déclenche jamais deux fois.
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import AvenantChantier, SignatureBtp

    if avenant.statut != AvenantChantier.Statut.SOUMIS_CLIENT:
        raise TransitionInvalide(
            f'Avenant {avenant.reference} : pas en attente d\'approbation '
            'client.')
    with transaction.atomic():
        signature = SignatureBtp.objects.create(
            company=avenant.company,
            content_type=ContentType.objects.get_for_model(AvenantChantier),
            object_id=avenant.pk, contexte='approbation_avenant',
            signataire_nom=signataire_nom, signataire=None,
            ip_adresse=ip_adresse, user_agent=user_agent)
        approuver_avenant(avenant, user=None)
    return signature


# ── NTCON9/NTCON10 — DGD (Décompte Général et Définitif) ───────────────────

def creer_decompte_general(
        *, company, chantier, cree_par, montant_marche_initial_ht,
        situations_incluses=None, retenue_garantie_id=None):
    """NTCON9 — crée un DGD (référence race-safe ``core.numbering``, préfixe
    ``DGD``) puis recalcule immédiatement ses totaux."""
    from core.numbering import create_with_reference

    from . import selectors
    from .models import DecompteGeneral

    def _create(reference):
        return DecompteGeneral.objects.create(
            company=company, chantier=chantier, reference=reference,
            montant_marche_initial_ht=montant_marche_initial_ht,
            situations_incluses=situations_incluses or [],
            retenue_garantie_id=retenue_garantie_id, cree_par=cree_par)

    dgd = create_with_reference(DecompteGeneral, 'DGD', company, _create)
    return selectors.recalculer_et_enregistrer_dgd(dgd)


def notifier_dgd(dgd, *, user):
    """NTCON9 — notifie le DGD (statut → notifie), après recalcul des
    totaux. Le PDF est rendu par la vue (``pdf.render_dgd_pdf``)."""
    from . import selectors
    from .models import DecompteGeneral

    if dgd.statut == DecompteGeneral.Statut.DEFINITIF:
        raise TransitionInvalide(f'DGD {dgd.reference} : déjà définitif.')
    dgd = selectors.recalculer_et_enregistrer_dgd(dgd)
    dgd.statut = DecompteGeneral.Statut.NOTIFIE
    dgd.date_notification = timezone.now()
    dgd.save(update_fields=['statut', 'date_notification', 'updated_at'])
    return dgd


def contester_dgd(dgd, *, user, motif, montant_conteste=None):
    """NTCON10 — trace une contestation (motif + montant contesté)."""
    from .models import DecompteGeneral

    if dgd.statut == DecompteGeneral.Statut.DEFINITIF:
        raise TransitionInvalide(f'DGD {dgd.reference} : verrouillé (définitif).')
    dgd.statut = DecompteGeneral.Statut.CONTESTE
    dgd.motif_contestation = motif
    dgd.montant_conteste = montant_conteste
    dgd.save(update_fields=[
        'statut', 'motif_contestation', 'montant_conteste', 'updated_at'])
    return dgd


def finaliser_dgd(dgd, *, user):
    """NTCON10 — finalise le DGD (statut → definitif) : VERROUILLE le
    décompte en lecture seule (pattern ``compta.PeriodeComptable.
    verrouillee``). Toute écriture ultérieure est refusée en 403 par la vue
    (``DecompteGeneralViewSet.perform_update``), sauf déverrouillage admin
    journalisé (``deverrouiller_dgd``)."""
    from .models import DecompteGeneral

    if dgd.statut == DecompteGeneral.Statut.DEFINITIF:
        raise TransitionInvalide(f'DGD {dgd.reference} : déjà définitif.')
    dgd.statut = DecompteGeneral.Statut.DEFINITIF
    dgd.date_finalisation = timezone.now()
    dgd.finalise_par = user
    dgd.save(update_fields=[
        'statut', 'date_finalisation', 'finalise_par', 'updated_at'])
    # NTCON31 — `dgd.finalise` sur le bus (abonné : webhook publicapi).
    _emettre('btp_dgd_finalise', dgd=dgd, company=dgd.company, user=user)
    return dgd


def deverrouiller_dgd(dgd, *, user, motif):
    """NTCON10 — déverrouillage ADMIN d'un DGD définitif (statut → accepte),
    JOURNALISÉ dans ``historique_deverrouillage`` (jamais silencieux)."""
    from .models import DecompteGeneral

    if dgd.statut != DecompteGeneral.Statut.DEFINITIF:
        raise TransitionInvalide(f'DGD {dgd.reference} : pas verrouillé.')
    dgd.statut = DecompteGeneral.Statut.ACCEPTE
    dgd.historique_deverrouillage = list(dgd.historique_deverrouillage or []) + [{
        'date': timezone.now().isoformat(),
        'user_id': getattr(user, 'id', None),
        'motif': motif,
    }]
    dgd.save(update_fields=[
        'statut', 'historique_deverrouillage', 'updated_at'])
    return dgd


# ── NTCON12 — Diffusion contrôlée de plans ──────────────────────────────────

def diffuser_plan(diffusion, *, user):
    """NTCON12 — diffuse un plan : crée un ``ged.PartageGed`` externe
    (fonction cross-app sanctionnée ``apps.ged.services.create_partage``,
    jamais un 2e mécanisme de partage) si des destinataires externes sont
    renseignés, notifie les destinataires internes (in-app, best-effort) et
    envoie un email aux externes (``django.core.mail.send_mail`` — no-op
    silencieux en dev/sans backend SMTP configuré, jamais bloquant).
    """
    diffusion.date_diffusion = timezone.now()

    if diffusion.destinataires_externes:
        try:
            from django.apps import apps as django_apps
            GedDocument = django_apps.get_model('ged', 'Document')
            document = GedDocument.objects.get(
                pk=diffusion.document_ged_id, company=diffusion.company)
            from apps.ged.services import create_partage
            partage = create_partage(
                document=document, company=diffusion.company,
                created_by=user)
            diffusion.partage_ged_id = partage.id
        except Exception:  # pragma: no cover - défensif, best-effort
            logger.warning(
                'btp_chantier: création du partage GED externe échouée pour '
                'la diffusion %s', diffusion.pk, exc_info=True)

    diffusion.save(update_fields=['date_diffusion', 'partage_ged_id'])

    for interne in diffusion.destinataires_internes.all():
        _notifier_btp(
            interne, 'APPROVAL_REQUESTED', 'Nouveau plan diffusé',
            f'Une nouvelle version (v{diffusion.version_diffusee}) du plan '
            'a été diffusée.', company=diffusion.company,
            link=f'/btp/diffusions/{diffusion.id}')

    if diffusion.destinataires_externes:
        try:
            from django.core.mail import send_mail

            from django.conf import settings as dj_settings

            lien = f'/btp/diffusions-plan/public/{diffusion.token}/'
            send_mail(
                'Nouveau plan diffusé',
                f'Une nouvelle version du plan a été diffusée : {lien}',
                getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local'),
                list(diffusion.destinataires_externes),
                fail_silently=True,
            )
        except Exception:  # pragma: no cover - défensif, best-effort
            logger.warning(
                'btp_chantier: envoi email diffusion %s échoué',
                diffusion.pk, exc_info=True)

    return diffusion


def marquer_diffusion_lue(diffusion, *, cle_destinataire):
    """NTCON12 — marque ``cle_destinataire`` (email ou identifiant utilisateur)
    comme ayant OUVERT le lien d'accusé de réception de cette diffusion
    (utilisé par NTCON13 pour détecter un plan périmé consulté)."""
    accuse = dict(diffusion.accuse_reception or {})
    accuse[str(cle_destinataire)] = {
        'lu': True, 'horodatage': timezone.now().isoformat(),
    }
    diffusion.accuse_reception = accuse
    diffusion.save(update_fields=['accuse_reception'])
    return diffusion


# ── Réglages BTP par société (consommés par les soft-guards) ───────────────

#: Défauts du module quand la société n'a encore aucun réglage enregistré.
#: NTCON25 pose le modèle ``ParametresBtpChantier`` (singleton par société) ;
#: ``config_btp`` le consomme dès qu'il existe — ces valeurs restent le repli.
CONFIG_BTP_DEFAUTS = {
    'delai_reponse_rfi_defaut_jours': 5,
    'delai_revue_visa_defaut_jours': 10,
    'guard_ppsps_bloquant': True,
    'guard_checklist_lot_bloquant': True,
    'lots_types_defaut': list(LOTS_TYPES_DEFAUT),
    'taux_penalite_retard_defaut_pmil': None,
    # NTCON27 — ancienneté d'archivage des réserves levées (mois).
    'delai_archivage_reserves_levees_mois': 24,
}


def config_btp(company):
    """Réglages BTP EFFECTIFS de ``company`` (dict), repli sur
    ``CONFIG_BTP_DEFAUTS``.

    Point d'accès UNIQUE des soft-guards du module (PPSPS NTCON16, checklist
    de lot NTCON19) : changer un réglage change le comportement du guard
    immédiatement, sans redéploiement (aucun cache — la lecture est faite à
    chaque appel). Tant qu'aucune ligne ``ParametresBtpChantier`` n'existe
    pour la société, les défauts du module s'appliquent.

    ``False`` est une valeur SIGNIFICATIVE (désactiver un guard) : seuls
    ``None`` et la chaîne vide sont ignorés.
    """
    from .models import ParametresBtpChantier

    valeurs = dict(CONFIG_BTP_DEFAUTS)
    if company is None:
        return valeurs
    reglages = ParametresBtpChantier.objects.filter(company=company).first()
    if reglages is None:
        return valeurs
    for cle in valeurs:
        valeur = getattr(reglages, cle, None)
        if valeur is None or valeur == '':
            continue
        valeurs[cle] = valeur
    return valeurs


# ── NTCON16 — PPSPS : validation, signature sous-traitant, soft-guard ──────

def valider_ppsps(ppsps, *, user):
    """NTCON16 — rend le PPSPS opposable (pose ``date_validation``/
    ``valide_par`` côté SERVEUR). Idempotent : revalider est refusé."""
    if ppsps.date_validation:
        raise TransitionInvalide(
            f'PPSPS #{ppsps.pk} : déjà validé le {ppsps.date_validation}.')
    ppsps.date_validation = timezone.localdate()
    ppsps.valide_par = user
    ppsps.save(update_fields=['date_validation', 'valide_par', 'updated_at'])
    return ppsps


def signer_ppsps(ppsps, *, sous_traitant, signataire_nom, ip_adresse='',
                 user_agent=''):
    """NTCON16 — enregistre la signature d'un sous-traitant sur le PPSPS
    (e-sign typée loi 53-05 : nom dactylographié + IP/user-agent SERVEUR).

    Refuse (``TransitionInvalide``) une seconde signature du même
    sous-traitant sur le même PPSPS, et un sous-traitant d'une autre société.
    """
    from .models import PPSPSSignature

    if getattr(sous_traitant, 'company_id', None) not in (
            None, ppsps.company_id):
        raise TransitionInvalide(
            'sous_traitant : sous-traitant inconnu pour cette société.')
    if PPSPSSignature.objects.filter(
            ppsps=ppsps, sous_traitant=sous_traitant).exists():
        raise TransitionInvalide(
            f'PPSPS #{ppsps.pk} : ce sous-traitant a déjà signé.')
    return PPSPSSignature.objects.create(
        company=ppsps.company, ppsps=ppsps, sous_traitant=sous_traitant,
        signataire_nom=signataire_nom, ip_adresse=ip_adresse,
        user_agent=user_agent)


def sous_traitant_a_signe_ppsps(chantier_id, sous_traitant_id):
    """NTCON16 — le sous-traitant a-t-il signé un PPSPS VALIDÉ de ce chantier ?

    Un PPSPS non encore validé (``date_validation`` vide) n'est pas opposable :
    seule une signature sur un PPSPS validé compte.
    """
    from .models import PPSPSSignature

    return PPSPSSignature.objects.filter(
        ppsps__chantier_id=chantier_id,
        ppsps__date_validation__isnull=False,
        sous_traitant_id=sous_traitant_id,
    ).exists()


def chantier_a_un_ppsps(chantier_id):
    """NTCON16 — ce chantier gère-t-il un PPSPS (au moins un VALIDÉ) ?

    Le soft-guard ne s'applique QUE dans ce cas : un chantier sans PPSPS
    validé n'a rien à faire signer — bloquer y rendrait l'ERP inutilisable
    pour les chantiers hors périmètre PPSPS.
    """
    from .models import PPSPSChantier

    return PPSPSChantier.objects.filter(
        chantier_id=chantier_id, date_validation__isnull=False).exists()


def verifier_ppsps_avant_demarrage(*, company, chantier_id, sous_traitant_id,
                                   libelle_ordre=''):
    """NTCON16 — soft-guard « PPSPS signé » avant le démarrage d'un ordre de
    sous-traitance (FG305, ``installations.OrdreSousTraitance`` → ``en_cours``).

    Motif (pattern ``qhse.services.exiger_document_unique``, QHSE22) :
      * chantier sans PPSPS validé → rien à exiger, on laisse passer ;
      * sous-traitant ayant signé → on laisse passer ;
      * sinon, selon ``config_btp(company)['guard_ppsps_bloquant']`` :
        ``True`` → ``PermissionDenied`` (403 côté API, message français),
        ``False`` → simple AVERTISSEMENT journalisé (jamais bloquant).

    Renvoie ``True`` si le démarrage est autorisé, ``False`` s'il n'est
    qu'averti. Ne lève jamais pour une raison technique (chantier absent…).
    """
    from django.core.exceptions import PermissionDenied

    if not chantier_id or not sous_traitant_id:
        return True
    if not chantier_a_un_ppsps(chantier_id):
        return True
    if sous_traitant_a_signe_ppsps(chantier_id, sous_traitant_id):
        return True

    message = (
        f'PPSPS non signé : le sous-traitant de {libelle_ordre or "cet ordre"} '
        "n'a pas signé le PPSPS validé du chantier — signature requise avant "
        'le démarrage des travaux.')
    if config_btp(company).get('guard_ppsps_bloquant', True):
        raise PermissionDenied(message)
    logger.warning('btp_chantier: %s (guard en mode avertissement)', message)
    return False


# ── NTCON24 — Clôture guidée d'un chantier BTP ─────────────────────────────

def prerequis_cloture_btp(chantier):
    """NTCON24 — pré-requis de clôture d'un chantier BTP (lecture seule).

    Trois contrôles, chacun renvoyant un message EXPLICITE en français (jamais
    un « non conforme » générique — règle fondateur « l'erreur nomme ce qui
    bloque ») :

    1. aucune réserve BLOQUANTE encore ouverte (NTCON1/2) ;
    2. aucun visa encore en attente de décision NI refusé (NTCON5) ;
    3. si le chantier gère un PPSPS validé (NTCON16), tous les sous-traitants
       ACTIFS (ordres FG305 ``emis``/``en_cours``) l'ont signé.

    Renvoie ``{'pret': bool, 'blocages': [str, …]}``.
    """
    from . import selectors
    from .models import VisaDocument

    blocages = []

    bloquantes = selectors.reserves_actives_bloquantes(
        chantier.company, chantier=chantier).count()
    if bloquantes:
        blocages.append(
            f'{bloquantes} réserve(s) bloquante(s) encore ouverte(s) — '
            'à lever avant la clôture.')

    en_attente = VisaDocument.objects.filter(
        chantier=chantier, company=chantier.company,
        statut__in=[VisaDocument.Statut.SOUMIS, VisaDocument.Statut.EN_REVUE],
    ).values_list('reference', flat=True)
    if en_attente:
        blocages.append(
            'Visa(s) encore en attente de décision : '
            f'{", ".join(en_attente)}.')
    refuses = VisaDocument.objects.filter(
        chantier=chantier, company=chantier.company,
        statut=VisaDocument.Statut.REFUSE).values_list('reference', flat=True)
    if refuses:
        blocages.append(
            f'Visa(s) refusé(s) à reprendre : {", ".join(refuses)}.')

    if chantier_a_un_ppsps(chantier.pk):
        manquants = []
        ordres = (
            chantier.installations_ordres_sous_traitance
            .filter(statut__in=['emis', 'en_cours'])
            .select_related('sous_traitant'))
        for ordre in ordres:
            if not ordre.sous_traitant_id:
                continue
            if not sous_traitant_a_signe_ppsps(
                    chantier.pk, ordre.sous_traitant_id):
                manquants.append(ordre.sous_traitant.nom)
        if manquants:
            blocages.append(
                'PPSPS non signé par : ' + ', '.join(sorted(set(manquants)))
                + '.')

    return {'pret': not blocages, 'blocages': blocages}


@transaction.atomic
def cloturer_chantier_btp(chantier, *, user, montant_marche_initial_ht=0,
                          situations_incluses=None, retenue_garantie_id=None):
    """NTCON24 — enchaîne la clôture d'un chantier BTP en UNE action.

    Séquence : vérification des pré-requis (``prerequis_cloture_btp`` — refus
    ``TransitionInvalide`` listant PRÉCISÉMENT ce qui manque) → génération du
    DGD (NTCON9, ``creer_decompte_general`` : référence race-safe + totaux
    recalculés) → notification (NTCON9 ``notifier_dgd``, statut ``notifie``).

    L'export du dossier consolidé (NTCON20) se télécharge ensuite sur
    ``chantiers/<id>/export-dossier-btp/`` — l'assistant enchaîne les deux
    sans étape manuelle côté utilisateur.

    NOTE DE PÉRIMÈTRE — NTCON24 évoquait un « lien client NTCON8-style » : le
    jeton public de NTCON8 appartient à ``AvenantChantier`` ; ``DecompteGeneral``
    n'en porte pas et lui en ajouter un serait un NOUVEAU canal public
    non demandé. La notification passe donc par le chemin DGD EXISTANT
    (statut ``notifie`` + PDF ``export-pdf``), sans inventer de surface
    publique supplémentaire.
    """
    prerequis = prerequis_cloture_btp(chantier)
    if not prerequis['pret']:
        raise TransitionInvalide(
            'Clôture impossible — ' + ' '.join(prerequis['blocages']))

    dgd = creer_decompte_general(
        company=chantier.company, chantier=chantier, cree_par=user,
        montant_marche_initial_ht=montant_marche_initial_ht or 0,
        situations_incluses=situations_incluses,
        retenue_garantie_id=retenue_garantie_id)
    notifier_dgd(dgd, user=user)
    dgd.refresh_from_db()
    return {'dgd': dgd, 'prerequis': prerequis}


# ── NTCON20 — Export « dossier chantier » consolidé ────────────────────────

def export_dossier_btp(chantier):
    """NTCON20 — ZIP consolidant le dossier d'un chantier (archivage légal
    loi 09-08 / litige). Réutilise le PATTERN d'export ZIP de XKB17
    (``kb.services.export_articles_zip``) : ``zipfile`` + ``records.storage.
    fetch_attachment`` (import fonction-local, ``records`` est une app de
    FONDATION).

    Contenu, STRICTEMENT scopé au chantier ET à sa société — jamais une pièce
    d'un autre chantier ni d'une autre société :

    * ``manifeste.txt`` — inventaire daté du dossier ;
    * ``journal-chantier.pdf`` — journal complet (NTCON6) ;
    * ``reserves/reserves-levees.csv`` + ``reserves/<id>/<fichier>`` — réserves
      LEVÉES (NTCON1/2) avec leurs preuves photo ;
    * ``visas/visas-approuves.csv`` — visas approuvés (NTCON5) ;
    * ``dgd/<reference>.pdf`` — décomptes généraux (NTCON9) ;
    * ``ppsps/ppsps-<id>.txt`` — PPSPS validés + signataires (NTCON16).

    Renvoie les octets du ZIP.
    """
    import csv
    import io
    import zipfile

    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.records.storage import fetch_attachment

    from .models import (
        DecompteGeneral, JournalChantier, PPSPSChantier, ReserveChantier,
        VisaDocument,
    )
    from .pdf import render_dgd_pdf, render_journal_chantier_pdf

    company = chantier.company
    buffer = io.BytesIO()

    def _csv(entetes, lignes):
        sortie = io.StringIO()
        writer = csv.writer(sortie, delimiter=';')
        writer.writerow(entetes)
        writer.writerows(lignes)
        return sortie.getvalue()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # ── Journal de chantier (NTCON6) ────────────────────────────────
        entrees = JournalChantier.objects.filter(
            chantier=chantier, company=company).order_by('date')
        try:
            zf.writestr(
                'journal-chantier.pdf',
                render_journal_chantier_pdf(chantier, entrees))
        except Exception:  # pragma: no cover - défensif (WeasyPrint absent)
            logger.warning(
                'btp_chantier: journal PDF absent du dossier %s',
                chantier.pk, exc_info=True)

        # ── Réserves LEVÉES + preuves (NTCON1/2) ────────────────────────
        reserves = ReserveChantier.objects.filter(
            chantier=chantier, company=company,
            statut=ReserveChantier.Statut.LEVEE).order_by('id')
        zf.writestr('reserves/reserves-levees.csv', _csv(
            ['id', 'lot', 'gravite', 'description', 'date_levee'],
            [[r.id, r.lot, r.gravite, r.description, r.date_levee or '']
             for r in reserves]))
        ct_reserve = ContentType.objects.get_for_model(ReserveChantier)
        for reserve in reserves:
            preuves = Attachment.objects.filter(
                content_type=ct_reserve, object_id=reserve.id,
                company=company)
            for preuve in preuves:
                data, erreur = fetch_attachment(preuve.file_key)
                if erreur or data is None:
                    continue
                zf.writestr(
                    f'reserves/{reserve.id}/{preuve.filename}', data)

        # ── Visas approuvés (NTCON5) ────────────────────────────────────
        visas = VisaDocument.objects.filter(
            chantier=chantier, company=company,
            statut__in=[
                VisaDocument.Statut.APPROUVE_SANS_RESERVE,
                VisaDocument.Statut.APPROUVE_AVEC_OBSERVATIONS,
            ]).order_by('id')
        zf.writestr('visas/visas-approuves.csv', _csv(
            ['reference', 'type', 'document_ged_id', 'statut', 'date_revue'],
            [[v.reference, v.type_visa, v.document_ged_id, v.statut,
              v.date_revue or ''] for v in visas]))

        # ── DGD (NTCON9) ────────────────────────────────────────────────
        decomptes = DecompteGeneral.objects.filter(
            chantier=chantier, company=company).order_by('id')
        for dgd in decomptes:
            try:
                zf.writestr(f'dgd/{dgd.reference}.pdf', render_dgd_pdf(dgd))
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'btp_chantier: DGD PDF %s absent du dossier',
                    dgd.reference, exc_info=True)

        # ── PPSPS validés + signataires (NTCON16) ───────────────────────
        for ppsps in PPSPSChantier.objects.filter(
                chantier=chantier, company=company,
                date_validation__isnull=False).order_by('id'):
            lignes = [
                f'PPSPS #{ppsps.pk} — {ppsps.titre or "sans titre"}',
                f'Validé le : {ppsps.date_validation}',
                f'Document GED : {ppsps.document_ged_id or "—"}',
                'Signataires :',
            ]
            for signature in ppsps.signatures.select_related('sous_traitant'):
                lignes.append(
                    f'  - {signature.sous_traitant.nom} — '
                    f'{signature.signataire_nom} '
                    f'({signature.date_signature:%Y-%m-%d})')
            zf.writestr(
                f'ppsps/ppsps-{ppsps.pk}.txt', '\n'.join(lignes) + '\n')

        # ── Manifeste ───────────────────────────────────────────────────
        zf.writestr('manifeste.txt', '\n'.join([
            f'Dossier de chantier — {chantier}',
            f'Chantier : #{chantier.pk}',
            f'Export du : {timezone.localdate()}',
            f'Entrées de journal : {entrees.count()}',
            f'Réserves levées : {reserves.count()}',
            f'Visas approuvés : {visas.count()}',
            f'Décomptes généraux : {decomptes.count()}',
        ]) + '\n')

    return buffer.getvalue()


# ── NTCON19 — Checklist de réception de lot ────────────────────────────────

#: Étapes de réception proposées par défaut quand aucune n'est fournie —
#: modèle de départ ÉDITABLE, jamais imposé (chaque lot garde les siennes).
CHECKLIST_RECEPTION_DEFAUT = [
    ('conformite_execution', "Conformité d'exécution vérifiée"),
    ('reserves_levees', 'Réserves du lot levées'),
    ('essais_realises', 'Essais / mise en service réalisés'),
    ('doe_remis', "Dossier des ouvrages exécutés (DOE) remis"),
    ('nettoyage', 'Nettoyage et repli de chantier'),
]


@transaction.atomic
def definir_checklist_lot(lot, etapes=None):
    """NTCON19 — (RE)définit les étapes de réception d'un ``Lot``.

    ``etapes`` : liste de dicts ``{cle, libelle, ordre?, obligatoire?}``.
    ``None``/vide applique ``CHECKLIST_RECEPTION_DEFAUT``. Les étapes DÉJÀ
    cochées conservent leur état (on ne « décoche » jamais un contrôle
    réalisé) ; les étapes absentes de la nouvelle liste sont retirées.
    """
    from .models import LotChecklistItem

    if not etapes:
        etapes = [
            {'cle': cle, 'libelle': libelle, 'ordre': rang}
            for rang, (cle, libelle) in enumerate(
                CHECKLIST_RECEPTION_DEFAUT, start=1)
        ]

    cles = []
    for rang, etape in enumerate(etapes, start=1):
        if not isinstance(etape, dict):
            raise TransitionInvalide(
                'etapes : chaque étape doit être un objet '
                '{cle, libelle, ordre?, obligatoire?}.')
        cle = (etape.get('cle') or '').strip()
        libelle = (etape.get('libelle') or '').strip()
        if not cle or not libelle:
            raise TransitionInvalide(
                'etapes : « cle » et « libelle » sont obligatoires pour '
                'chaque étape.')
        if cle in cles:
            raise TransitionInvalide(
                f'etapes : clé en double « {cle} ».')
        cles.append(cle)
        LotChecklistItem.objects.update_or_create(
            lot=lot, cle=cle,
            defaults={
                'company': lot.company,
                'libelle': libelle,
                'ordre': etape.get('ordre') or rang,
                'obligatoire': bool(etape.get('obligatoire', True)),
            })
    LotChecklistItem.objects.filter(lot=lot).exclude(cle__in=cles).delete()
    return list(LotChecklistItem.objects.filter(lot=lot))


def cocher_item_checklist_lot(lot, *, cle, user, fait=True):
    """NTCON19 — coche/décoche une étape de réception (auteur + horodatage
    posés CÔTÉ SERVEUR)."""
    from .models import LotChecklistItem

    item = LotChecklistItem.objects.filter(lot=lot, cle=cle).first()
    if item is None:
        raise TransitionInvalide(
            f'cle : étape « {cle} » inconnue sur ce lot.')
    item.fait = bool(fait)
    item.fait_par = user if fait else None
    item.fait_le = timezone.now() if fait else None
    item.save(update_fields=['fait', 'fait_par', 'fait_le', 'updated_at'])
    return item


def etat_checklist_lot(lot):
    """NTCON19 — état de la checklist de réception : ``{total, faits,
    obligatoires_restants, complete}`` (lecture seule).

    ``complete`` vaut True quand AUCUNE étape obligatoire ne reste à cocher —
    un lot sans checklist est donc « complet » (rien n'est exigé tant que rien
    n'a été défini).
    """
    from .models import LotChecklistItem

    items = list(LotChecklistItem.objects.filter(lot=lot))
    restants = [i.libelle for i in items if i.obligatoire and not i.fait]
    return {
        'total': len(items),
        'faits': sum(1 for i in items if i.fait),
        'obligatoires_restants': restants,
        'complete': not restants,
    }


def verifier_checklist_avant_reception(lot):
    """NTCON19 — soft-guard « checklist de réception 100 % cochée » avant le
    passage d'un ``Lot`` à ``termine``.

    Selon ``config_btp(company)['guard_checklist_lot_bloquant']`` :
    ``True`` → ``TransitionInvalide`` nommant les étapes restantes,
    ``False`` → simple AVERTISSEMENT journalisé. Renvoie ``True`` si la
    réception est autorisée sans réserve, ``False`` si elle n'est qu'avertie.
    """
    etat = etat_checklist_lot(lot)
    if etat['complete']:
        return True
    restants = ', '.join(etat['obligatoires_restants'])
    message = (
        f'Checklist de réception incomplète pour le lot « {lot.nom} » — '
        f'étape(s) restante(s) : {restants}.')
    if config_btp(lot.company).get('guard_checklist_lot_bloquant', True):
        raise TransitionInvalide(message)
    logger.warning('btp_chantier: %s (guard en mode avertissement)', message)
    return False


def terminer_lot(lot, *, user, date_fin_reelle=None):
    """NTCON19 — réceptionne un lot (statut → ``termine``) APRÈS le soft-guard
    de checklist. Pose ``date_fin_reelle`` (aujourd'hui par défaut) : c'est
    elle qui FIGE le retard pris en compte par NTCON15."""
    from .models import Lot

    if lot.statut == Lot.Statut.TERMINE:
        raise TransitionInvalide(
            f'Lot « {lot.nom} » : déjà terminé.')
    verifier_checklist_avant_reception(lot)
    lot.statut = Lot.Statut.TERMINE
    lot.date_fin_reelle = date_fin_reelle or timezone.localdate()
    lot.save(update_fields=['statut', 'date_fin_reelle', 'updated_at'])
    return lot


# ── NTCON18 — Photo-rapport hebdomadaire (opt-in par chantier) ─────────────

#: Plafond de photos embarquées dans un photo-rapport (PDF raisonnable).
MAX_PHOTOS_RAPPORT = 60


def email_sortant_configure():
    """NTCON18 — l'envoi d'email réel est-il configuré (clé API présente) ?

    Lecture de ``settings.ANYMAIL`` UNIQUEMENT (aucune dépendance cross-app) :
    sans clé, la commande est un NO-OP PROPRE (elle produit le PDF mais
    n'envoie rien et le dit) — jamais une erreur.
    """
    from django.conf import settings as dj_settings

    anymail = getattr(dj_settings, 'ANYMAIL', None) or {}
    return bool(
        anymail.get('SENDINBLUE_API_KEY') or anymail.get('SENDGRID_API_KEY'))


def collecter_photos_periode(chantier, du, au):
    """NTCON18 — photos ``records.Attachment`` du chantier sur ``[du, au]``.

    Trois sources, toutes rattachées au MÊME chantier : le chantier lui-même,
    ses réserves (NTCON1) et ses entrées de journal (NTCON6). ``records`` est
    une app de FONDATION : import direct autorisé (aucune frontière cross-app).
    Seules les images sont embarquées (``mime`` commençant par ``image/``) ;
    les octets sont lus via ``records.storage.fetch_attachment`` et encodés en
    ``data:`` URI. Renvoie une liste de dicts triés par date croissante.
    """
    import base64

    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    from .models import JournalChantier, ReserveChantier

    cibles = [
        ('Chantier', ContentType.objects.get_for_model(chantier.__class__),
         [chantier.pk]),
        ('Réserve', ContentType.objects.get_for_model(ReserveChantier),
         list(ReserveChantier.objects.filter(
             chantier=chantier).values_list('id', flat=True))),
        ('Journal', ContentType.objects.get_for_model(JournalChantier),
         list(JournalChantier.objects.filter(
             chantier=chantier).values_list('id', flat=True))),
    ]

    lignes = []
    for libelle, content_type, ids in cibles:
        if not ids:
            continue
        qs = Attachment.objects.filter(
            company=chantier.company, content_type=content_type,
            object_id__in=ids, created_at__date__gte=du,
            created_at__date__lte=au).order_by('created_at', 'id')
        for att in qs:
            lignes.append({
                'source': libelle,
                'date': att.created_at.date().isoformat(),
                'phase': att.phase or '',
                'filename': att.filename,
                'mime': att.mime or '',
                'file_key': att.file_key,
            })

    lignes.sort(key=lambda ligne: ligne['date'])
    lignes = lignes[:MAX_PHOTOS_RAPPORT]

    from apps.records.storage import fetch_attachment
    for ligne in lignes:
        ligne['data_uri'] = None
        if not (ligne['mime'] or '').startswith('image/'):
            continue
        data, erreur = fetch_attachment(ligne['file_key'])
        if erreur or not data:
            continue
        ligne['data_uri'] = (
            f'data:{ligne["mime"]};base64,'
            f'{base64.b64encode(data).decode("ascii")}')
    return lignes


def envoyer_rapports_photo_hebdo(*, du=None, au=None, chantier_id=None,
                                 dry_run=False):
    """NTCON18 — balaie les chantiers ABONNÉS et envoie leur photo-rapport.

    Opt-in strict : seuls les ``AbonnementRapportPhoto`` ``actif=True`` sont
    traités. Période par défaut : les 7 derniers jours (``au`` = aujourd'hui).
    Sans clé email configurée (``email_sortant_configure``) ou en ``dry_run``,
    le PDF est bien produit mais RIEN n'est envoyé — no-op propre.

    Renvoie ``{'examines', 'envoyes', 'sans_photo', 'email_configure'}``.
    """
    from datetime import timedelta

    from .models import AbonnementRapportPhoto
    from .pdf import render_rapport_photo_pdf

    au = au or timezone.localdate()
    du = du or (au - timedelta(days=6))
    envoi_possible = email_sortant_configure() and not dry_run

    qs = AbonnementRapportPhoto.objects.filter(
        actif=True).select_related('chantier', 'company')
    if chantier_id:
        qs = qs.filter(chantier_id=chantier_id)

    examines = envoyes = sans_photo = 0
    for abonnement in qs:
        examines += 1
        photos = collecter_photos_periode(abonnement.chantier, du, au)
        if not photos:
            sans_photo += 1
            continue
        try:
            pdf_bytes = render_rapport_photo_pdf(
                abonnement.chantier, du, au, photos)
        except Exception:  # pragma: no cover - défensif, jamais bloquant
            logger.warning(
                'btp_chantier: rendu du photo-rapport échoué pour le chantier '
                '%s', abonnement.chantier_id, exc_info=True)
            continue
        destinataires = [
            adresse for adresse in (abonnement.destinataires or []) if adresse]
        if not (envoi_possible and destinataires):
            continue
        try:
            from django.conf import settings as dj_settings
            from django.core.mail import EmailMessage

            message = EmailMessage(
                subject=f'Avancement photo — {abonnement.chantier}',
                body=(
                    f'Bonjour,\n\nVeuillez trouver ci-joint le rapport '
                    f"d'avancement photo du {du} au {au}.\n"),
                from_email=getattr(
                    dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local'),
                to=destinataires,
            )
            message.attach(
                f'avancement-photo-{abonnement.chantier_id}-{au}.pdf',
                pdf_bytes, 'application/pdf')
            message.send(fail_silently=True)
        except Exception:  # pragma: no cover - défensif, best-effort
            logger.warning(
                'btp_chantier: envoi du photo-rapport échoué pour le chantier '
                '%s', abonnement.chantier_id, exc_info=True)
            continue
        abonnement.dernier_envoi = au
        abonnement.save(update_fields=['dernier_envoi', 'updated_at'])
        envoyes += 1

    return {
        'examines': examines,
        'envoyes': envoyes,
        'sans_photo': sans_photo,
        'email_configure': email_sortant_configure(),
    }


# ── NTCON14 — Rattachement des tâches existantes à un lot ──────────────────

def taches_hors_societe(tache_ids, company):
    """NTCON14 — parmi ``tache_ids`` (IDs ``gestion_projet.Tache``), renvoie
    ceux qui n'appartiennent PAS à ``company`` (inconnu ou autre société).

    LECTURE cross-app via ``django.apps.apps.get_model`` — jamais un import
    statique de ``gestion_projet.models``, jamais une écriture (même patron que
    ``selectors.situations_incluses_hors_societe``).
    """
    from django.apps import apps as django_apps

    tache_ids = list(tache_ids or [])
    if not tache_ids:
        return []
    try:
        Tache = django_apps.get_model('gestion_projet', 'Tache')
    except LookupError:  # pragma: no cover - gestion_projet non installé
        return list(tache_ids)
    connus = set(Tache.objects.filter(
        id__in=tache_ids, company=company).values_list('id', flat=True))
    return [tid for tid in tache_ids if tid not in connus]


@transaction.atomic
def definir_taches_du_lot(lot, tache_ids):
    """NTCON14 — (RE)définit l'ensemble des tâches rattachées à ``lot``.

    Refuse (``TransitionInvalide``, message français nommant le champ) toute
    tâche inconnue/cross-société, ou déjà rattachée à un AUTRE lot (une tâche
    appartient à au plus un lot — contrainte ``btp_lot_tache_unique_lot``).
    """
    from .models import LotTache

    tache_ids = [int(t) for t in (tache_ids or [])]
    inconnues = taches_hors_societe(tache_ids, lot.company)
    if inconnues:
        raise TransitionInvalide(
            f'taches : tâche(s) inconnue(s) ou appartenant à une autre '
            f'société : {inconnues}.')
    deja_ailleurs = list(
        LotTache.objects.filter(tache_id__in=tache_ids)
        .exclude(lot=lot).values_list('tache_id', flat=True))
    if deja_ailleurs:
        raise TransitionInvalide(
            f'taches : tâche(s) déjà rattachée(s) à un autre lot : '
            f'{deja_ailleurs}. Détachez-les d\'abord.')
    LotTache.objects.filter(lot=lot).exclude(
        tache_id__in=tache_ids).delete()
    existantes = set(
        LotTache.objects.filter(lot=lot).values_list('tache_id', flat=True))
    LotTache.objects.bulk_create([
        LotTache(company=lot.company, lot=lot, tache_id=tid)
        for tid in tache_ids if tid not in existantes
    ])
    return lot


def alerter_rfi_en_retard():
    """NTCON4 (AUD231) — balaie les ``RFI`` OUVERTS dont
    ``date_limite_reponse`` est dépassée et notifie leur ``destinataire_user``
    ET leur créateur (``pose_par``).

    Le corps de ce balayage vivait ENTIÈREMENT dans la commande de gestion
    ``alertes_rfi_retard`` — dont la docstring annonçait « Sweep quotidien …
    (Celery beat) » alors qu'aucune entrée de ``beat_schedule`` ni aucune tâche
    Celery n'existait : aucun RFI en retard n'a jamais été alerté. Le corps est
    donc remonté ICI, unique implémentation partagée par la commande (à la
    demande) et par ``btp_chantier.tasks`` (planifiée).

    Idempotente : UNE SEULE alerte par jour et par RFI, via
    ``RFI.derniere_alerte_retard`` comparée à la date du jour. Renvoie
    ``{'examines': n, 'alertes_envoyees': n}``.
    """
    from .selectors import rfi_en_retard

    today = timezone.localdate()
    examines = 0
    envoyees = 0
    for rfi in rfi_en_retard().select_related(
            'chantier', 'pose_par', 'destinataire_user'):
        examines += 1
        if rfi.derniere_alerte_retard == today:
            continue  # déjà alerté aujourd'hui — idempotent
        titre = f'RFI #{rfi.numero} en retard de réponse'
        corps = (
            f'RFI #{rfi.numero} ({rfi.chantier}) — échéance '
            f'{rfi.date_limite_reponse} dépassée sans réponse.')
        link = f'/btp/rfi/{rfi.id}'
        for user in {rfi.destinataire_user, rfi.pose_par} - {None}:
            _notifier_btp(
                user, 'APPROVAL_REMINDER', titre, corps,
                company=rfi.company, link=link)
        with transaction.atomic():
            rfi.derniere_alerte_retard = today
            rfi.save(update_fields=['derniere_alerte_retard'])
        envoyees += 1
    return {'examines': examines, 'alertes_envoyees': envoyees}


# ── NTCON27 — archivage des réserves levées anciennes ───────────────────────

def archiver_reserves_levees(*, company=None, maintenant=None):
    """NTCON27 — sort des listes actives les réserves LEVÉES trop anciennes.

    JAMAIS une suppression physique : une réserve levée porte une signature
    (``SignatureBtp``) et son historique de transitions — ce sont des PREUVES
    de réception, opposables des années plus tard. On pose ``archivee=True`` +
    ``archivee_le``, exactement dans l'esprit de la politique soft-delete du
    dépôt (``core.SoftDeleteQuerySet``).

    Le seuil est un RÉGLAGE PAR SOCIÉTÉ
    (``ParametresBtpChantier.delai_archivage_reserves_levees_mois``, défaut
    24 mois) : le balayage boucle donc par société plutôt que d'appliquer un
    seuil global qui serait faux pour l'une d'elles.

    IDEMPOTENT : le filtre exclut déjà ``archivee=True``, donc un second
    passage n'écrit rien et renvoie ``archivees: 0``.

    Renvoie ``{'examines': n, 'archivees': n}``.
    """
    from .models import ReserveChantier
    from .selectors import reserves_archivables

    examines = 0
    archivees = 0
    horodatage = maintenant or timezone.now()
    par_societe = reserves_archivables(company, maintenant=horodatage)
    for qs in par_societe.values():
        ids = list(qs.values_list('pk', flat=True))
        examines += len(ids)
        if not ids:
            continue
        with transaction.atomic():
            archivees += ReserveChantier.objects.filter(
                pk__in=ids, archivee=False).update(
                    archivee=True, archivee_le=horodatage)
    return {'examines': examines, 'archivees': archivees}


# ── NTCON28 — recalcul planifié des pénalités de retard par lot ─────────────

def _json_penalite(ligne):
    """Rend une ligne de ``penalites_retard_par_lot`` STOCKABLE en JSON.

    ``Decimal``/``date`` ne sont pas sérialisables par ``json.dumps`` : on les
    convertit en CHAÎNES (jamais en ``float`` — un montant en ``float`` perd
    des centimes, et cette valeur est une exposition financière)."""
    from datetime import date
    from decimal import Decimal

    sortie = {}
    for cle, valeur in ligne.items():
        if isinstance(valeur, Decimal):
            sortie[cle] = str(valeur)
        elif isinstance(valeur, date):
            sortie[cle] = valeur.isoformat()
        else:
            sortie[cle] = valeur
    return sortie


def recalculer_penalites_lots(*, company=None, chantier=None,
                              maintenant=None, tous=False):
    """NTCON28 — recalcule et MET EN CACHE l'exposition aux pénalités par lot.

    Périmètre par défaut : les chantiers portant AU MOINS un lot en retard
    ACTIF (``selectors.chantiers_avec_lot_en_retard``) — recalculer un
    chantier dont aucun lot n'a glissé coûterait une requête pour rien.
    ``tous=True`` force le balayage complet (recalcul manuel), ``chantier=``
    cible un seul chantier (action admin/cockpit).

    Le calcul lui-même reste celui de NTCON15 (``penalites_retard_par_lot``) —
    AUCUNE seconde formule : on ne fait que figer son résultat sur
    ``Lot.penalite_calculee_cache`` + ``penalite_calculee_le``.

    Renvoie ``{'chantiers': n, 'lots': n}``.
    """
    from .models import Lot
    from .selectors import (
        chantiers_avec_lot_en_retard, penalites_retard_par_lot,
    )

    horodatage = maintenant or timezone.now()

    if chantier is not None:
        chantiers = [chantier]
    else:
        lots_qs = Lot.objects.all()
        if company is not None:
            lots_qs = lots_qs.filter(company=company)
        if not tous:
            lots_qs = chantiers_avec_lot_en_retard(company)
        ids = list(
            lots_qs.values_list('chantier_id', flat=True).distinct())
        if not ids:
            return {'chantiers': 0, 'lots': 0}
        Chantier = Lot._meta.get_field('chantier').related_model
        chantiers = list(Chantier.objects.filter(pk__in=ids))

    nb_chantiers = 0
    nb_lots = 0
    for site in chantiers:
        calcul = penalites_retard_par_lot(site)
        date_reference = calcul['date_reference']
        nb_chantiers += 1
        with transaction.atomic():
            for ligne in calcul['lots']:
                charge = _json_penalite(ligne)
                charge['date_reference'] = date_reference.isoformat()
                nb_lots += Lot.objects.filter(pk=ligne['lot_id']).update(
                    penalite_calculee_cache=charge,
                    penalite_calculee_le=horodatage)
    return {'chantiers': nb_chantiers, 'lots': nb_lots}


# ── NTCON29 — import CSV/XLSX des lots et jalons contractuels ───────────────

#: En-têtes acceptés → champ ``Lot``. Plusieurs libellés par champ parce
#: qu'un fichier réel vient d'un planning Excel, pas d'un gabarit ERP.
COLONNES_LOT = {
    'nom': ('nom', 'lot', 'nom du lot', 'designation', 'désignation',
            'libelle', 'libellé'),
    'sous_traitant': ('entreprise', 'sous-traitant', 'sous_traitant',
                      'sous traitant', 'fournisseur', 'reference entreprise',
                      'référence entreprise'),
    'date_debut_prevue': ('date debut', 'date début', 'debut prevu',
                          'début prévu', 'date_debut_prevue', 'debut'),
    'date_fin_prevue': ('date fin', 'fin prevue', 'fin prévue',
                        'date_fin_prevue', 'fin'),
    'jalon_contractuel': ('jalon', 'jalon contractuel', 'jalon_contractuel',
                          'contractuel'),
    'montant_ht': ('montant', 'montant ht', 'montant_ht'),
    'taux_penalite_retard_pmil': (
        'taux penalite', 'taux pénalité', 'taux_penalite_retard_pmil',
        'penalite', 'pénalité', 'taux penalite retard'),
    'plafond_penalite_pct': ('plafond', 'plafond penalite', 'plafond pénalité',
                             'plafond_penalite_pct'),
    'ordre': ('ordre', 'rang', 'n°', 'numero', 'numéro'),
}

_ESPACES = re.compile(r'\s+')

_VRAI_IMPORT = {'1', 'oui', 'o', 'true', 'vrai', 'yes', 'y', 'x'}
_FAUX_IMPORT = {'', '0', 'non', 'n', 'false', 'faux', 'no'}


def _normaliser_entete(entete):
    """Minuscule, espaces normalises (un fichier Excel reel porte des
    espaces insecables et des doubles espaces dans ses en-tetes)."""
    texte = (entete or '').replace('\xa0', ' ')
    return _ESPACES.sub(' ', texte).strip().lower()


def _index_colonnes(headers):
    """En-tête brut du fichier → nom de champ ``Lot`` (dict)."""
    connus = {}
    for champ, alias in COLONNES_LOT.items():
        for libelle in alias:
            connus[libelle] = champ
    index = {}
    for entete in headers or []:
        champ = connus.get(_normaliser_entete(entete))
        if champ and champ not in index.values():
            index[entete] = champ
    return index


def _valeur_date(brut):
    """Date ISO ou jj/mm/aaaa → ``date``. Lève ``ValueError`` si illisible."""
    from datetime import date, datetime

    if brut in (None, ''):
        return None
    if isinstance(brut, datetime):
        return brut.date()
    if isinstance(brut, date):
        return brut
    texte = str(brut).strip()
    for motif in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(texte, motif).date()
        except ValueError:
            continue
    raise ValueError(f'date illisible : « {texte} » (attendu jj/mm/aaaa)')


def _valeur_decimale(brut, libelle):
    """Nombre décimal tolérant (virgule, espaces, séparateur de milliers)."""
    from decimal import Decimal, InvalidOperation

    if brut in (None, ''):
        return None
    texte = (str(brut).replace(' ', '').replace(' ', '')
             .replace(',', '.'))
    try:
        return Decimal(texte)
    except InvalidOperation:
        raise ValueError(f'{libelle} illisible : « {brut} »')


def _valeur_booleenne(brut):
    texte = str(brut if brut is not None else '').strip().lower()
    if texte in _VRAI_IMPORT:
        return True
    if texte in _FAUX_IMPORT:
        return False
    raise ValueError(f'jalon contractuel illisible : « {brut} » (oui/non)')


def _resoudre_sous_traitant(reference, company):
    """``stock.Fournisseur`` de la société par référence/nom — LECTURE
    cross-app par ``django.apps.get_model`` (jamais un import de ``stock.
    models``, jamais une écriture). ``None`` si la cellule est vide ;
    ``ValueError`` si la référence ne résout pas."""
    from django.apps import apps as django_apps

    texte = (str(reference) if reference is not None else '').strip()
    if not texte:
        return None
    Fournisseur = django_apps.get_model('stock', 'Fournisseur')
    qs = Fournisseur.objects.filter(company=company)
    trouve = qs.filter(nom__iexact=texte).first()
    if trouve is None and hasattr(Fournisseur, 'code'):
        trouve = qs.filter(code__iexact=texte).first()
    if trouve is None:
        trouve = qs.filter(nom__icontains=texte).first()
    if trouve is None:
        raise ValueError(
            f'sous-traitant introuvable : « {texte} » (créez-le au '
            'référentiel fournisseurs avant l\'import)')
    return trouve


def importer_lots(*, company, chantier, fichier_octets, nom_fichier,
                  user=None):
    """NTCON29 — importe en masse les lots d'un chantier depuis un CSV/XLSX.

    Réutilise TEL QUEL le mécanisme d'import du dépôt (``apps.dataimport`` :
    ``parsing.iter_rows`` pour la lecture, ``services.enregistrer_job`` pour le
    journal ``ImportJob``/``ImportJobRow``) — jamais un 2ᵉ mécanisme d'import.

    UNE LIGNE INVALIDE NE BLOQUE PAS LES AUTRES : chaque ligne est validée et
    écrite indépendamment ; l'échec d'une ligne produit une ``ImportJobRow``
    en erreur avec un motif PRÉCIS (sous-traitant introuvable, dates
    incohérentes, montant illisible) et le lot suivant est traité.

    Renvoie ``{'job_id', 'total_lignes', 'crees', 'erreurs', 'lignes': [...]}``
    — ``lignes`` ne contient QUE les lignes en erreur (rapport à l'écran).
    """
    from apps.dataimport.models import ImportJobRow
    from apps.dataimport.parsing import iter_rows
    from apps.dataimport.services import enregistrer_job

    from .models import Lot

    try:
        headers, lignes_brutes = iter_rows(fichier_octets, nom_fichier)
    except Exception as exc:  # noqa: BLE001 — fichier corrompu/illisible
        raise ValueError(
            f'Fichier illisible ({nom_fichier}) : {exc}') from exc

    index = _index_colonnes(headers)
    if 'nom' not in index.values():
        raise ValueError(
            "Colonne « nom du lot » introuvable. En-têtes acceptés : "
            + ', '.join(COLONNES_LOT['nom']))

    journal = []
    crees = 0
    for rang, brute in enumerate(lignes_brutes, start=2):  # 1 = l'en-tête
        donnees = {champ: brute.get(entete)
                   for entete, champ in index.items()}
        try:
            champs = _valider_ligne_lot(donnees, company)
        except ValueError as exc:
            journal.append({
                'ligne': rang, 'statut': ImportJobRow.Statut.ERREUR,
                'motif': str(exc)[:255], 'donnees': _jsonifiable(brute)})
            continue
        try:
            # SAVEPOINT par ligne : une violation d'unicité (lot déjà présent
            # sur ce chantier) salit la transaction si elle n'est pas isolée —
            # la ligne suivante échouerait alors sans raison propre.
            with transaction.atomic():
                lot = Lot.objects.create(
                    company=company, chantier=chantier, **champs)
        except IntegrityError:
            journal.append({
                'ligne': rang, 'statut': ImportJobRow.Statut.ERREUR,
                'motif': (f'lot « {champs["nom"]} » déjà présent sur ce '
                          'chantier')[:255],
                'donnees': _jsonifiable(brute)})
            continue
        crees += 1
        journal.append({
            'ligne': rang, 'statut': ImportJobRow.Statut.OK,
            'donnees': _jsonifiable(brute),
            'cible': 'btp_chantier.Lot', 'cible_id': lot.pk})

    job = enregistrer_job(
        company, 'btp_lots', nom_fichier, user=user, mode='creer',
        total_lignes=len(lignes_brutes), created=crees, lignes=journal)
    erreurs = [ligne for ligne in journal
               if ligne['statut'] == ImportJobRow.Statut.ERREUR]
    return {
        'job_id': job.pk,
        'total_lignes': len(lignes_brutes),
        'crees': crees,
        'erreurs': len(erreurs),
        'lignes': [{'ligne': e['ligne'], 'motif': e['motif']}
                   for e in erreurs],
    }


def _jsonifiable(brute):
    """Ligne brute stockable en JSON (openpyxl rend des ``datetime``)."""
    from datetime import date, datetime
    from decimal import Decimal

    sortie = {}
    for cle, valeur in (brute or {}).items():
        if isinstance(valeur, (datetime, date)):
            sortie[str(cle)] = valeur.isoformat()
        elif isinstance(valeur, Decimal):
            sortie[str(cle)] = str(valeur)
        else:
            sortie[str(cle)] = valeur
    return sortie


def _valider_ligne_lot(donnees, company):
    """Une ligne brute → kwargs de ``Lot``. ``ValueError`` NOMME le champ
    fautif (règle fondateur : jamais un « non enregistré » générique)."""
    nom = (str(donnees.get('nom') or '')).strip()
    if not nom:
        raise ValueError('nom du lot manquant')

    champs = {'nom': nom[:120]}

    sous_traitant = _resoudre_sous_traitant(
        donnees.get('sous_traitant'), company)
    if sous_traitant is not None:
        champs['sous_traitant'] = sous_traitant
        champs['interne'] = False

    debut = _valeur_date(donnees.get('date_debut_prevue'))
    fin = _valeur_date(donnees.get('date_fin_prevue'))
    if debut and fin and fin < debut:
        raise ValueError(
            f'dates incohérentes : fin prévue ({fin}) avant début prévu '
            f'({debut})')
    if debut:
        champs['date_debut_prevue'] = debut
    if fin:
        champs['date_fin_prevue'] = fin

    if donnees.get('jalon_contractuel') is not None:
        champs['jalon_contractuel'] = _valeur_booleenne(
            donnees['jalon_contractuel'])

    montant = _valeur_decimale(donnees.get('montant_ht'), 'montant HT')
    if montant is not None:
        if montant < 0:
            raise ValueError(f'montant HT négatif : {montant}')
        champs['montant_ht'] = montant

    taux = _valeur_decimale(
        donnees.get('taux_penalite_retard_pmil'), 'taux de pénalité')
    if taux is not None:
        if taux < 0:
            raise ValueError(f'taux de pénalité négatif : {taux}')
        champs['taux_penalite_retard_pmil'] = taux

    plafond = _valeur_decimale(
        donnees.get('plafond_penalite_pct'), 'plafond de pénalité')
    if plafond is not None:
        if not 0 <= plafond <= 100:
            raise ValueError(
                f'plafond de pénalité hors bornes : {plafond} % '
                '(attendu entre 0 et 100)')
        champs['plafond_penalite_pct'] = plafond

    ordre = _valeur_decimale(donnees.get('ordre'), 'ordre')
    if ordre is not None:
        if ordre < 0:
            raise ValueError(f'ordre négatif : {ordre}')
        champs['ordre'] = int(ordre)

    return champs
