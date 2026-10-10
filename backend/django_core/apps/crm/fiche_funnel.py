"""Écritures de funnel et d'étape de la fiche lead (SPL10, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from . import activity, stages
from .cadence_messages import _omettre_phrases_incompletes, langue_relance_du_lead
from .leads_premier_contact import marquer_premier_contact
from .models import Lead, LeadActivity
from .visites_rdv import resoudre_lien_rdv

logger = logging.getLogger(__name__)


# Mouvement automatique du funnel à partir des statuts DOCUMENT du devis
# (couche séparée et permanente — CLAUDE.md règles #2/#4) :
#   devis « envoye »  → étape QUOTE_SENT (Devis envoyé)
#   devis « accepte » → étape SIGNED (Signé)
# Clés scalaires uniquement — jamais de nouvelle liste d'étapes (STAGES.py).
_STATUT_VERS_STAGE = {
    'envoye': ('QUOTE_SENT', 'envoyé'),
    'accepte': ('SIGNED', 'accepté'),
}


def _rang_funnel(stage_key: str) -> int:
    """Rang d'avancement dans le funnel, depuis l'ordre canonique de STAGES.

    COLD est un état de PARKING, pas « plus avancé » : il est classé SOUS
    NEW (rang -1, donc sous toute étape active y compris NEW/CONTACTED) pour
    qu'un lead froid soit RÉACTIVÉ par les mouvements automatiques (devis
    envoyé/accepté, réactivation sur nouvelle touche YLEAD11) quelle que soit
    l'étape cible visée.
    """
    if stage_key == 'COLD':
        return -1
    return stages.STAGES.index(stage_key)


# ── QJ7 — Avance automatique NEW → CONTACTED au premier contact ──────────────
#
# Kinds d'activité qui comptent comme « premier contact » :
#   NOTE, APPEL, EMAIL — une CREATION ou MODIFICATION ne suffit pas.
_CONTACT_KINDS = frozenset([
    LeadActivity.Kind.NOTE,
    LeadActivity.Kind.APPEL,
    LeadActivity.Kind.EMAIL,
    # MRY10 — un WhatsApp envoyé fait AVANCER NEW → CONTACTED, exactement
    # comme un e-mail : c'est le canal principal de Meryem.
    LeadActivity.Kind.WHATSAPP,
])

# Clé canonique de l'étape « Contacté » (STAGES.py — jamais hardcodée ailleurs).
_STAGE_CONTACTED = 'CONTACTED'


def _emit_stage_changed(lead, old_stage, new_stage, user=None):
    """NTCRM12 — Émet ``core.events.lead_stage_changed`` pour TOUT point
    d'entrée qui fait bouger ``Lead.stage``. No-op si l'étape n'a pas changé.
    Best-effort : n'échoue jamais l'appelant."""
    if old_stage == new_stage:
        return
    try:
        from core.events import lead_stage_changed
        lead_stage_changed.send(
            sender=Lead, lead=lead, old_stage=old_stage, new_stage=new_stage,
            user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM12: émission lead_stage_changed échouée pour le lead #%s',
            getattr(lead, 'pk', '?'), exc_info=True)


def appliquer_stage_lead(lead, nouveau_stage, *, user=None):
    """CRX20 — Point de passage CANONIQUE de toute écriture de ``Lead.stage``.

    Écrit l'étape (``save(update_fields=['stage'])``) PUIS émet
    ``core.events.lead_stage_changed`` via :func:`_emit_stage_changed`, de
    sorte qu'aucun chemin ne puisse plus déplacer un lead « en muet » (les
    récepteurs playbook NTCRM12 et séquences compta XMKT1 s'abonnent à ce
    signal — un chemin muet les prive silencieusement de leur déclencheur).

    Ne journalise RIEN dans le chatter : chaque appelant garde sa propre
    écriture d'historique (note système, ``activity.log_bulk_change``…), qui
    diffère d'un point d'entrée à l'autre.

    ``nouveau_stage`` doit être une clé canonique de STAGES.py — jamais un
    littéral inventé. No-op si l'étape ne change pas.

    Renvoie ``True`` si l'étape a effectivement changé, ``False`` sinon.
    Point d'entrée PUBLIC : ``apps.ventes`` l'appelle pour l'expiration des
    devis (jamais un import des models crm depuis ventes).
    """
    ancien_stage = lead.stage
    if ancien_stage == nouveau_stage:
        return False
    lead.stage = nouveau_stage
    lead.save(update_fields=['stage'])
    _emit_stage_changed(lead, ancien_stage, nouveau_stage, user=user)
    return True


class SortieSigneBloquee(Exception):
    """Décision fondateur (08/10/2026) — le lead ne peut pas sortir de
    « Signé » : son devis accepté a déjà une suite RÉELLE (facture, bon de
    commande, chantier avancé…). ``message`` est la phrase française à
    montrer telle quelle (HTTP 409 à l'unité, motif de saut en masse)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def desaccepter_devis_du_lead(lead, user, *, motif=''):
    """Décision fondateur (08/10/2026) — un lead qui SORT de « Signé » par
    une action utilisateur dés-accepte ses devis acceptés (actifs) : chacun
    repasse « envoyé » par la porte de ``ventes``
    (``services.annuler_acceptation``), qui défait ce que l'acceptation avait
    créé automatiquement (événement ``devis_acceptation_annulee``).

    À appeler DANS la transaction de l'écriture d'étape, AVANT elle : si un
    devis est bloqué, ``SortieSigneBloquee`` est levée — l'appelant laisse la
    transaction s'annuler (aucun devis dés-accepté, étape inchangée). Les
    chemins AUTOMATIQUES (recyclage système) n'appellent jamais cette
    fonction. Rend le nombre de devis dés-acceptés (0 = comportement
    inchangé pour un lead « Signé » sans devis accepté)."""
    from apps.ventes.selectors import devis_acceptes_actifs
    from apps.ventes.services import (
        AnnulationAcceptationBloquee, annuler_acceptation,
    )
    libelle = stages.STAGE_LABELS[stages.SIGNED]
    nb = 0
    for devis in devis_acceptes_actifs(lead.company, lead_id=lead.pk):
        try:
            annuler_acceptation(
                devis=devis, user=user,
                motif=motif or f'lead sorti de « {libelle} »')
        except AnnulationAcceptationBloquee as exc:
            raise SortieSigneBloquee(
                f'Impossible de sortir ce lead de « {libelle} » : '
                f'{exc.message}') from exc
        nb += 1
    return nb


def _playbook_correspond_au_lead(playbook, lead):
    """NTCRM26 — ``playbook.condition`` matche-t-il ce lead ? ``None``/vide =
    playbook universel (comportement historique) — toujours ``True``.
    Réutilise ``core.rules.evaluate_condition_group`` (FG367), jamais un
    nouveau moteur. Tolérant : jamais d'exception, ``False`` en cas de doute."""
    if not playbook.condition:
        return True
    from core.rules import evaluate_condition_group
    criteres = {
        'type_installation': getattr(lead, 'type_installation', None),
        'canal': getattr(lead, 'canal', None),
        # AGR525 — le playbook FDA vise le REMPLACEMENT DU BUTANE (Guide FDA
        # 2024, D-AGR-6) : l'énergie de la pompe actuelle est un critère.
        'pompe_alim_actuelle': getattr(lead, 'pompe_alim_actuelle', None),
        # CIQ517 (D-CIQ-6) — le playbook « raccordement et autorisations du
        # site » vise un site MT, une régularisation 82-21 ou un client qui
        # veut revendre : ces trois critères sont lus.
        'tension_raccordement': getattr(lead, 'tension_raccordement', None),
        'regularisation_8221': getattr(lead, 'regularisation_8221', None),
        'objectif_projet': getattr(lead, 'objectif_projet', None),
    }
    try:
        return evaluate_condition_group(playbook.condition, criteres)
    except Exception:  # noqa: BLE001 — tolérant, jamais bloquant
        return False


def playbooks_recommandes(lead, stage):
    """NTCRM26 — Playbooks ACTIFS de la société de ``lead`` portant une étape
    sur ``stage`` dont ``condition`` matche le profil du lead (universels
    inclus). Lecture pure, sert à l'aperçu et à ``generer_playbook_progress``."""
    from .models import Playbook

    playbooks = Playbook.objects.filter(
        company=lead.company, actif=True, etapes__stage=stage,
    ).distinct()
    return [p for p in playbooks if _playbook_correspond_au_lead(p, lead)]


def generer_playbook_progress(lead, new_stage):
    """NTCRM12/NTCRM26 — Quand ``lead`` entre dans ``new_stage``, crée la
    progression (``LeadPlaybookProgress``, une par tâche) pour chaque playbook
    ACTIF de la société portant une étape sur ``new_stage`` ET dont
    ``condition`` matche le profil du lead (auto-sélection par similarité —
    un playbook sans condition reste universel, comportement historique
    inchangé). Idempotent (``unique_together(lead, tache)``, ``get_or_create``)
    : rejouer l'événement (ex. réactivation YLEAD11 qui repasse par la même
    étape) ne duplique jamais les tâches. Ne bloque JAMAIS le changement
    d'étape (avertissement seulement — cohérent avec « never auto-move ») :
    appelé en best-effort par le récepteur."""
    from .models import LeadPlaybookProgress, PlaybookEtape

    playbooks_ok = {p.pk for p in playbooks_recommandes(lead, new_stage)}
    etapes = PlaybookEtape.objects.filter(
        playbook__company=lead.company, playbook__actif=True,
        stage=new_stage, playbook_id__in=playbooks_ok,
    ).prefetch_related('taches')
    created = []
    for etape in etapes:
        for tache in etape.taches.all():
            _progress, was_created = LeadPlaybookProgress.objects.get_or_create(
                lead=lead, tache=tache)
            if was_created:
                created.append(_progress)
    return created


def avancer_stage_new_vers_contacted(lead, user) -> bool:
    """Avance le stage du lead NEW → CONTACTED lors du premier contact.

    « Premier contact » = première activité de type NOTE, APPEL ou EMAIL.
    Idempotent : si le lead n'est plus à NEW (ou est perdu), ne fait rien et
    renvoie False. Ne recule jamais une étape déjà plus avancée.
    Renvoie True si l'avance a effectivement eu lieu, False sinon.
    """
    # Relire l'état courant en base : l'instance passée par le signal peut être
    # périmée (ex. un autre effet du même flux a déjà avancé le lead vers
    # QUOTE_SENT) — sans cela, on écraserait une étape plus avancée par CONTACTED.
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu', 'first_contacted_at'])
    if lead.perdu:
        return False
    if lead.stage != stages.NEW:
        return False
    lead.stage = _STAGE_CONTACTED
    lead.save(update_fields=['stage'])
    # FG28/MRY19 — le premier contact passe par LA source unique
    # (``marquer_premier_contact``) : plus de pose artisanale ici.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.NEW],
        new_value=stages.STAGE_LABELS[_STAGE_CONTACTED],
        body='auto — premier contact',
    )
    marquer_premier_contact(lead)
    _emit_stage_changed(lead, stages.NEW, _STAGE_CONTACTED, user)
    return True


def avancer_stage_sur_reponse_devis(lead, user) -> bool:
    """QJ-FUNNEL (fondateur 09/09/2026 — « le lead reste en Contacté et ne
    bouge ni vers Devis envoyé ni vers Relance sur les réponses aux
    touches ») — avance QUOTE_SENT → FOLLOW_UP quand le client RÉPOND après
    l'envoi de sa proposition.

    Symétrique EXACT de ``avancer_stage_new_vers_contacted`` juste au-dessus,
    un cran plus loin dans le funnel, sous la MÊME doctrine 07/09/2026 : le
    funnel ne bouge que sur une réponse CONFIRMÉE (« joint »/« intéressé »)
    journalisée par un humain — jamais sur un comportement observé (YLEAD10
    débranché) ni sur une touche sautée. Le déclencheur est le même récepteur
    d'activité (receivers ``_avancer_stage_on_contact_activity``), donc il
    couvre d'un seul mécanisme la clôture de touche de cadence
    (``marquer_etape_relance``) ET l'appel journalisé à la main
    (``log_interaction``).

    Garde d'étape EXACTE (QUOTE_SENT seul) : un lead encore à CONTACTED dont
    l'appel aboutit reste à CONTACTED (aucun devis envoyé — « Relance » vient
    APRÈS « Devis envoyé » dans l'ordre canonique STAGES.py) ; un lead déjà à
    FOLLOW_UP ou plus avancé ne bouge pas. Idempotent, jamais en arrière,
    leads perdus ignorés."""
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu'])
    if lead.perdu:
        return False
    if lead.stage != stages.QUOTE_SENT:
        return False
    lead.stage = stages.FOLLOW_UP
    lead.save(update_fields=['stage'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
        new_value=stages.STAGE_LABELS[stages.FOLLOW_UP],
        body='auto — réponse du client après devis',
    )
    _emit_stage_changed(lead, stages.QUOTE_SENT, stages.FOLLOW_UP, user)
    return True


def avancer_stage_devis_envoye_sur_touche(lead, user) -> bool:
    """QJ-FUNNEL (fondateur 09/09/2026 — « when I do Fait for quote sent, it
    should be at quote sent ») — place le lead à QUOTE_SENT quand la touche
    « Préparer et envoyer le devis » est cochée FAIT sans issue (le même
    geste que RELANCE-SUITE lit déjà comme « devis parti » pour démarrer le
    plan après-devis — appelé par ``marquer_etape_relance`` sur LA MÊME
    détection, jamais une seconde règle de libellé).

    Avance-seulement par RANG (``_rang_funnel``) : un lead COLD est RÉACTIVÉ
    (rang -1 — même doctrine que les mouvements devis envoyé/accepté), un
    lead déjà à QUOTE_SENT ou plus avancé ne bouge pas, un lead perdu est
    ignoré. C'est un mouvement de la couche FUNNEL seule (règle #2) : le
    STATUT document du devis, lui, ne bascule que par ``mark_devis_sent``
    (envoi réel — email, WhatsApp, lien copié)."""
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu'])
    if lead.perdu:
        return False
    if _rang_funnel(lead.stage) >= _rang_funnel(stages.QUOTE_SENT):
        return False
    ancien = lead.stage
    lead.stage = stages.QUOTE_SENT
    lead.save(update_fields=['stage'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien],
        new_value=stages.STAGE_LABELS[stages.QUOTE_SENT],
        body='auto — touche « envoyer le devis » faite',
    )
    _emit_stage_changed(lead, ancien, stages.QUOTE_SENT, user)
    return True


def avancer_stage_pour_devis(devis, ancien_statut, nouveau_statut, user):
    """Avance l'étape du lead quand le STATUT d'un devis change.

    Ne recule jamais, ignore les leads perdus (drapeau `perdu`), n'agit que sur
    les transitions envoye/accepte. Écrit UNE entrée d'historique marquée
    automatique (« auto — devis … »).
    """
    if nouveau_statut == ancien_statut:
        return
    cible = _STATUT_VERS_STAGE.get(nouveau_statut)
    if cible is None:
        return
    # `getattr` défensif : un vrai Devis résout son FK `lead` à l'identique
    # (chargement paresseux), mais ce récepteur est câblé au signal partagé
    # `devis_accepted` — un émetteur d'un autre domaine (ex. la séquence
    # d'inscription XMKT1) peut envoyer un objet devis minimal ne portant que
    # `lead_id` : on l'ignore alors proprement plutôt que de lever AttributeError.
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return
    if lead.perdu:
        return  # lead perdu (drapeau) — le funnel ne bouge plus automatiquement.

    stage_cible, suffixe = cible
    if _rang_funnel(lead.stage) >= _rang_funnel(stage_cible):
        return  # jamais en arrière (ni sur-place).

    ancien_stage = lead.stage
    lead.stage = stage_cible
    lead.save(update_fields=['stage'])
    _emit_stage_changed(lead, ancien_stage, stage_cible, user)

    if stage_cible == 'SIGNED':
        # QJ9 — CAPI SignedQuote : le hook réside dans ventes.services.accept_devis
        # (_fire_capi_signed_quote, gated sur META_CAPI_ACCESS_TOKEN). L'avancée
        # manuelle en masse vers SIGNED (set_stage bulk) ne reporte pas de devis
        # accepté et ne dispose pas de l'attribution UTM — pas de CAPI ici.
        pass

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[stage_cible],
        body=f"auto — devis {devis.reference} {suffixe}",
    )


# ── U11 — Cohérence funnel : « Signé sans devis actif » (DÉCISION fondateur) ──
#
# Le funnel n'avance jamais en arrière (avancer_stage_pour_devis), donc un lead
# peut rester à SIGNED alors que son SEUL devis accepté a depuis été refusé : un
# « signé fantôme ». La règle #2 (le funnel est une couche PERMANENTE, séparée
# des statuts DOCUMENT — les deux ne se mélangent jamais) interdit de reculer
# l'étape à l'aveugle. Option conservatrice retenue : on NE recule PAS l'étape,
# on SIGNALE l'incohérence (drapeau dérivé + note de chatter) pour que l'UI
# puisse la badger et que le commercial décide.

# Statut DOCUMENT « accepté » d'un devis (couche séparée — STATUT, pas étape).
_DEVIS_STATUT_ACCEPTE = 'accepte'


def lead_signe_sans_devis_actif(lead) -> bool:
    """Drapeau DÉRIVÉ (lecture seule) : le lead est à SIGNED mais n'a plus aucun
    devis accepté actif.

    « Actif » = un devis au statut DOCUMENT « accepté » qui n'est pas archivé.
    Ne modifie RIEN (aucune écriture, aucune migration) : c'est un calcul que
    l'UI peut badger pour repérer un « signé fantôme ». Renvoie ``False`` dès que
    le lead n'est pas à SIGNED (rien à signaler hors de l'étape Signé).
    """
    if getattr(lead, 'stage', None) != 'SIGNED':
        return False
    qs = lead.devis.filter(statut=_DEVIS_STATUT_ACCEPTE)
    # Certains devis peuvent être archivés (champ optionnel selon le schéma) —
    # on les exclut s'il existe, sinon on compte tous les devis acceptés.
    try:
        Devis = lead.devis.model
        if any(f.name == 'is_archived' for f in Devis._meta.get_fields()):
            qs = qs.filter(is_archived=False)
    except Exception:
        pass
    return not qs.exists()


def signaler_mismatch_signe_sur_refus(devis, user):
    """À l'événement « devis refusé » : si le refus laisse un lead SIGNED sans
    AUCUN devis accepté actif, consigne UNE note de chatter pour signaler le
    « signé sans devis actif » — SANS jamais reculer l'étape (règle #2).

    Best-effort, idempotent dans les faits : on n'écrit la note que lorsque
    l'incohérence est réellement présente après le refus. Ne crée pas de doublon
    pour un même refus car ``date_refus``/``motif_refus`` y figurent en clair.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return
    # Le refus a déjà été appliqué (statut DOCUMENT) avant l'émission du signal,
    # donc le devis refusé n'est plus compté comme « accepté actif » ici.
    if not lead_signe_sans_devis_actif(lead):
        return
    activity.log_note(
        lead, user,
        f"⚠ Étape Signé sans devis actif : le devis {devis.reference} "
        f"(qui avait fait passer ce lead à « Signé ») est désormais refusé et "
        f"plus aucun devis accepté n'est actif. L'étape n'a PAS été reculée "
        f"automatiquement (à vérifier).")


def avancer_stage_sur_ouverture_devis(lead) -> bool:
    """YLEAD10 — Avance le lead à FOLLOW_UP (STAGES.py) quand le client ouvre
    sa proposition, comme les autres avances de funnel automatiques
    (``avancer_stage_pour_devis``) : ne recule jamais, ignore les leads
    perdus et ceux déjà ≥ FOLLOW_UP (donc un lead déjà SIGNED/COLD-au-delà
    ne bouge pas). Idempotent : une seconde ouverture ne réécrit rien de
    plus (le rang est déjà atteint). Renvoie True si l'avance a eu lieu.

    CAD139 (21/09/2026) — CONSERVÉE SANS APPELANT DE PRODUCTION. La RÈGLE
    FONDATEUR du 07/09/2026 a débranché cette avance automatique
    (``noter_devis_ouvert`` ne l'appelle plus : « le funnel ne bouge que sur
    une réponse confirmée de Meryem ») ; seuls ``tests_crx20_stage_events.py``
    et ``tests_ylead10_fastlane_open.py`` l'invoquent aujourd'hui. Gardée
    plutôt que supprimée (version préférée de l'audit L3, round 2) : c'est
    l'implémentation TESTÉE et idempotente du fast-lane comportemental que la
    décision du 07/09 a désactivé sans l'invalider — si le fondateur revient
    sur ce choix, le comportement et ses tests existent déjà, au lieu d'être
    re-dérivés de zéro. Ni code mort silencieux, ni suppression d'un choix
    documenté.
    """
    if lead is None or lead.perdu:
        return False
    cible = stages.FOLLOW_UP
    if _rang_funnel(lead.stage) >= _rang_funnel(cible):
        return False  # déjà à FOLLOW_UP ou plus avancé (jamais en arrière).

    ancien_stage = lead.stage
    # CRX20 — chemin canonique : écrit ET émet ``lead_stage_changed`` (ce
    # point d'entrée était muet, les playbooks/séquences ne partaient pas).
    appliquer_stage_lead(lead, cible, user=None)
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS[ancien_stage],
        new_value=stages.STAGE_LABELS[cible],
        body='auto — devis ouvert par le client',
    )
    return True


COLD = 'COLD'  # état de PARKING (pas une régression) — cf. _rang_funnel.


def _bulk_stage_allowed(current, target):
    """Le funnel n'avance jamais EN ARRIÈRE en masse.

    - même étape → non (rien à faire) ;
    - Froid → n'importe quelle étape active → oui (réactivation) ;
    - vers Froid → oui (mise au parking, autorisée depuis n'importe où) ;
    - sinon → uniquement vers une étape PLUS avancée.

    INCHANGÉ par l'ordre fondateur 2026-08-01 (« les leads doivent pouvoir
    revenir en arrière d'étape, avec une confirmation avant ») : LE BULK RESTE
    EN AVANT SEULEMENT. Cette fonction reste la définition PURE de « ce qui
    avance », et elle demeure l'unique source du garde funnel — le
    ``LeadSerializer`` continue de l'appeler telle quelle pour un PATCH
    unitaire, puis décide seul d'accepter un recul quand l'utilisatrice l'a
    confirmé (champ write-only ``confirme_recul``). Une confirmation vise UN
    lead nommé, avec ses deux étapes affichées ; il n'existe aucune boîte de
    dialogue capable de faire assumer sincèrement le recul de 200 leads d'un
    coup — l'action de masse ne gagne donc pas d'échappatoire.
    """
    if current == target:
        return False
    if current == COLD or target == COLD:
        return True
    return _rang_funnel(target) > _rang_funnel(current)


def _resolve_owner(company, owner_id):
    """Responsable cible (société courante uniquement) ou None si vidé."""
    if owner_id in (None, '', 'null'):
        return None
    from authentication.models import CustomUser
    return CustomUser.objects.filter(id=owner_id, company=company).first()


def _corps_whatsapp_en_masse(lead, tpl, corps_direct=''):
    """ACRM15 — le texte d'un message de la file WhatsApp en masse, rendu
    avec la discipline de ``message_pour_etape`` (MRY13) :

    * la LANGUE préférée du lead (``langue_relance_du_lead``) : un gabarit de
      même nom dans cette langue est préféré au gabarit choisi ;
    * ``{lien_rdv}`` résolu seulement s'il est présent ;
    * une phrase dont un placeholder n'a PAS de valeur réelle (``{lien}`` —
      aucun devis ici —, ``{lien_rdv}`` non généré, ``{prenom}``/``{ville}``
      vides) est OMISE — jamais « Réservez votre visite : » suivi de rien."""
    from apps.ventes.utils.whatsapp import render_message_template

    from .models import MessageTemplate

    corps = corps_direct or ''
    if tpl is not None:
        langue = langue_relance_du_lead(lead)
        if tpl.langue != langue:
            traduit = (MessageTemplate.objects
                       .filter(company=lead.company, nom=tpl.nom,
                               langue=langue, archived=False)
                       .first())
            if traduit is not None:
                tpl = traduit
        corps = tpl.corps or ''
    contexte = {
        'prenom': (lead.prenom or lead.nom or '').strip(),
        'ville': (lead.ville or '').strip(),
        'lien': '',
    }
    if '{lien_rdv}' in corps:
        contexte['lien_rdv'] = (
            resoudre_lien_rdv('{lien_rdv}', lead) or '')
    manquants = [cle for cle, valeur in contexte.items()
                 if '{' + cle + '}' in corps and not str(valeur).strip()]
    return render_message_template(
        _omettre_phrases_incompletes(corps, manquants), contexte)


def avancer_stage_lead_vers(lead, user, stage_cible):
    """XMKT19 — avance ``lead`` vers ``stage_cible`` (clé canonique
    STAGES.py, jamais hardcodée par l'appelant). Refuse un recul (même règle
    que le bulk edit, ``_bulk_stage_allowed``). Renvoie True si appliqué.
    """
    if not _bulk_stage_allowed(lead.stage, stage_cible):
        return False
    ancien = lead.stage
    lead.stage = stage_cible
    lead.save(update_fields=['stage'])
    activity.log_bulk_change(lead, user, 'stage', ancien, stage_cible)
    _emit_stage_changed(lead, ancien, stage_cible, user)
    return True


def assigner_lead_a(lead, user, owner_id):
    """XMKT19 — assigne (ou vide) le propriétaire du lead."""
    nouveau = _resolve_owner(lead.company, owner_id)
    ancien = lead.owner
    lead.owner = nouveau
    lead.save(update_fields=['owner'])
    activity.log_bulk_change(
        lead, user,
        'owner',
        getattr(ancien, 'username', '') if ancien else '',
        getattr(nouveau, 'username', '') if nouveau else '')
    return lead


def poser_tag_lead(lead, user, tag):
    """XMKT19 — ajoute (idempotent) un tag au lead."""
    tag = (tag or '').strip()
    if not tag:
        return lead
    current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
    if tag in current:
        return lead
    old = lead.tags or ''
    current.append(tag)
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
    return lead


def retirer_tag_lead(lead, user, tag):
    """XMKT19 — retire (idempotent) un tag du lead."""
    tag = (tag or '').strip()
    if not tag:
        return lead
    current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
    if tag not in current:
        return lead
    old = lead.tags or ''
    current.remove(tag)
    lead.tags = ', '.join(current)[:500]
    lead.save(update_fields=['tags'])
    activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
    return lead


def ajuster_score_lead(lead, user, delta):
    """XMKT19 — ajuste le score du lead de ``delta`` (peut être négatif),
    borné à [0, 100]."""
    ancien = lead.score or 0
    nouveau = max(0, min(100, ancien + int(delta)))
    lead.score = nouveau
    lead.save(update_fields=['score'])
    activity.log_bulk_change(lead, user, 'score', ancien, nouveau)
    return lead


def creer_relance_lead(lead, user, *, relance_date, note=''):
    """XMKT19 — crée/pose une relance/tâche (FG31) sur le lead."""
    lead.relance_date = relance_date
    lead.save(update_fields=['relance_date'])
    body = f'Relance planifiée le {relance_date}'
    if note:
        body += f' — {note}'
    activity.log_note(lead, user, body)
    return lead


def rattraper_playbooks_pompe(lead):
    """AGR525 (3) — l'énergie de la pompe vient de passer à « butane » sur un
    lead agricole déjà à la prise de contact OU au-delà : les tâches des
    playbooks qui lisent ``pompe_alim_actuelle`` (le playbook FDA) sont
    générées pour les étapes déjà atteintes. Idempotent (``get_or_create`` sur
    (lead, tâche)) ; jamais au Froid ni à « Nouveau ». Renvoie les
    progressions créées."""
    if (getattr(lead, 'type_installation', None) or '') != 'agricole' \
            or getattr(lead, 'pompe_alim_actuelle', None) != 'butane':
        return []
    return _rattraper_playbooks_lisant(lead, ('pompe_alim_actuelle',))


#: CIQ517 — les champs du lead que lit le playbook « raccordement et
#: autorisations du site ».
CHAMPS_PLAYBOOK_8221 = ('tension_raccordement', 'regularisation_8221',
                        'objectif_projet')


def rattraper_playbooks_8221(lead):
    """CIQ517 — un lead commercial/industriel déjà à la prise de contact (ou
    au-delà) passe en MT, se déclare en régularisation 82-21 ou veut
    revendre : la tâche « raccordement et autorisations du site » est
    générée pour les étapes atteintes (idempotent, comme AGR525)."""
    if (getattr(lead, 'type_installation', None) or '') \
            not in ('commercial', 'industriel'):
        return []
    return _rattraper_playbooks_lisant(lead, CHAMPS_PLAYBOOK_8221)


def _rattraper_playbooks_lisant(lead, champs):
    """AGR525/CIQ517 — génère, pour les étapes DÉJÀ atteintes (prise de
    contact incluse, jamais Froid), les tâches des playbooks ACTIFS dont la
    condition lit l'un de ``champs`` ET matche le lead. Idempotent."""
    from . import stages as _stages
    from .models import LeadPlaybookProgress, Playbook

    ordre = [s for s in _stages.STAGES if s != _stages.COLD]
    if lead.stage not in ordre or ordre.index(lead.stage) < ordre.index(
            _stages.CONTACTED):
        return []
    atteintes = ordre[ordre.index(_stages.CONTACTED):ordre.index(lead.stage) + 1]
    import json as _json
    created = []
    for playbook in Playbook.objects.filter(company=lead.company, actif=True):
        condition = _json.dumps(playbook.condition or {})
        if not any(champ in condition for champ in champs):
            continue
        if not _playbook_correspond_au_lead(playbook, lead):
            continue
        for etape in playbook.etapes.filter(stage__in=atteintes) \
                .prefetch_related('taches'):
            for tache in etape.taches.all():
                progress, cree = LeadPlaybookProgress.objects.get_or_create(
                    lead=lead, tache=tache)
                if cree:
                    created.append(progress)
    return created
