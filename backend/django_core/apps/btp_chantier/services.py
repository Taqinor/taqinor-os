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

from django.db import transaction
from django.utils import timezone

from .models import ReserveChantier, ReserveChantierHistorique

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
    return _decider_visa(
        visa, user=user, nouveau_statut=statut, observations=observations)


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
