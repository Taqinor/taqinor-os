"""Écritures de champs de la fiche lead (SPL20, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from django.utils import timezone

from core.dates import aujourd_hui_local

from .cadence_plan import sync_relance_activity
from .leads_socle import MOTIF_BULK_CADENCE_ACTIVE, leads_avec_cadence_active
from .models import Lead, LeadActivity, PointContact
import logging
from .activity import creer_activite, journal_systeme

logger = logging.getLogger(__name__)


def appliquer_plan_activite(*, lead, plan, user):
    """ZSAL2 — applique un :class:`~apps.crm.models.PlanActivite` à un lead.

    Crée une ``records.Activity`` par étape du plan, échéance = aujourd'hui +
    ``etape.delai_jours``, assignée à ``etape.assigne_par_defaut`` si posé
    sinon au owner du lead sinon à l'acteur. IDEMPOTENT par (lead, plan) : les
    activités déjà créées par une précédente application de CE plan sur CE
    lead sont retrouvées via ``summary`` + une marque dédiée dans ``note``
    (``[plan:<id>:<etape_id>]``) — une seconde application ne duplique rien et
    renvoie la liste déjà existante. Un plan archivé (``actif=False``) n'est
    jamais applicable (ValueError, traduit en 400 par la vue).

    Retourne la liste des ``records.Activity`` (créées ou déjà existantes,
    dans l'ordre des étapes).
    """
    if not plan.actif:
        raise ValueError("Ce plan d'activité est archivé et n'est plus applicable.")
    if plan.company_id != lead.company_id:
        raise ValueError("Plan hors de votre société.")

    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Activity

    ct = ContentType.objects.get_for_model(Lead)
    today = aujourd_hui_local()
    resultats = []
    for etape in plan.etapes.select_related(
            'activity_type', 'assigne_par_defaut').order_by('ordre', 'delai_jours'):
        marque = f'[plan:{plan.id}:{etape.id}]'
        existante = Activity.objects.filter(
            company=lead.company, content_type=ct, object_id=lead.id,
            note__contains=marque,
        ).first()
        if existante is not None:
            resultats.append(existante)
            continue
        assigne = etape.assigne_par_defaut or lead.owner or user
        from datetime import timedelta
        due = today + timedelta(days=etape.delai_jours)
        act = Activity.objects.create(
            company=lead.company, content_type=ct, object_id=lead.id,
            activity_type=etape.activity_type,
            summary=(etape.resume_defaut or etape.activity_type.nom)[:255],
            due_date=due,
            assigned_to=assigne,
            note=marque,
            created_by=user,
        )
        resultats.append(act)

    creer_activite(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Plan d'activité « {plan.nom} » appliqué "
             f"({len(plan.etapes.all())} étape(s)).")
    return resultats


def noter_touche_marketing(lead, message, *, ordre=0, cout=None):
    """XMKT16 — Consigne un événement marketing significatif (envoi/ouverture/
    clic de campagne, étape de séquence exécutée, réponse WhatsApp entrante)
    dans le chatter du lead (``LeadActivity``) + le journal d'attribution
    multi-touch FG204 (``PointContact``). Appelé par le module marketing de
    compta — jamais d'import du modèle CRM depuis compta, ce point d'entrée
    reste dans ``apps.crm.services`` comme toutes les écritures cross-app.

    Le canal réutilise ``Lead.Canal.AUTRE`` (aucun nouveau vocabulaire de
    canal n'est inventé) ; ``message`` porte le libellé lisible de
    l'événement (ex. « Campagne X envoyée »), stocké aussi dans
    ``PointContact.detail`` pour l'attribution.
    """
    journal_systeme(
        company=lead.company, lead=lead,
        kind=LeadActivity.Kind.NOTE, body=message)
    return PointContact.objects.create(
        company=lead.company, lead=lead, canal=Lead.Canal.AUTRE,
        source='marketing', date_contact=timezone.now(),
        ordre=ordre, detail=message, cout=cout)


#: APAR51 — les issues de ``appliquer_champ_automatique``.
CHAMP_AUTO_APPLIQUE = 'applique'
CHAMP_AUTO_INCHANGE = 'inchange'
CHAMP_AUTO_INVALIDE = 'invalide'
CHAMP_AUTO_CADENCE = 'cadence_active'


def appliquer_champ_automatique(lead, champ, valeur, user=None):
    """APAR51 (C-APAR-032) — LA porte d'écriture d'un champ de lead par une
    AUTOMATISATION (règle SET_FIELD, action serveur, assignation) : la même
    discipline que le geste manuel.

    * la valeur est VALIDÉE par le champ du modèle (choix, longueur, type) —
      hors choix ⇒ ``(CHAMP_AUTO_INVALIDE, motif)``, rien n'est écrit ;
    * ``relance_date`` sur un lead à CADENCE ACTIVE ⇒ refus CAD49
      (``(CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE)``) : la date vient
      de la prochaine touche du plan ;
    * une valeur égale ⇒ ``(CHAMP_AUTO_INCHANGE, '')`` ;
    * sinon le champ est écrit et UNE ligne MODIFICATION (ancien → nouveau)
      entre au chatter, l'acteur étant ``user`` (la règle).

    ``champ='owner'`` accepte un utilisateur (ou son identifiant) de la
    société du lead. Rend ``(issue, motif)``."""
    from django.core.exceptions import ValidationError

    from . import activity as _activity

    try:
        champ_modele = Lead._meta.get_field(champ)
    except Exception:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning('%s : échec ignoré (dégradé)', 'appliquer_champ_automatique', exc_info=True)
        return CHAMP_AUTO_INVALIDE, f'Champ « {champ} » inconnu.'
    if champ == 'owner':
        from django.contrib.auth import get_user_model
        pk = getattr(valeur, 'pk', valeur)
        cible = get_user_model().objects.filter(
            pk=pk, company=lead.company).first() if pk else None
        if cible is None:
            return CHAMP_AUTO_INVALIDE, 'Utilisateur cible inconnu.'
        ancien = lead.owner
        if ancien is not None and ancien.pk == cible.pk:
            return CHAMP_AUTO_INCHANGE, ''
        lead.owner = cible
        lead.save(update_fields=['owner'])
        creer_activite(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.MODIFICATION, field='owner',
            field_label=_activity.TRACKED_FIELDS.get('owner', 'owner'),
            old_value=_activity._display(lead, 'owner', ancien),
            new_value=_activity._display(lead, 'owner', cible))
        return CHAMP_AUTO_APPLIQUE, ''
    try:
        propre = champ_modele.clean(valeur, lead)
    except ValidationError as exc:
        hors_choix = bool(getattr(champ_modele, 'choices', None))
        detail = '; '.join(exc.messages)
        return CHAMP_AUTO_INVALIDE, (
            f'Valeur hors choix pour « {champ} » : {valeur!r}.' if hors_choix
            else f'Valeur invalide pour « {champ} » : {detail}')
    if champ == 'relance_date' and leads_avec_cadence_active(
            lead.company, [lead.pk]):
        return CHAMP_AUTO_CADENCE, MOTIF_BULK_CADENCE_ACTIVE
    ancien = getattr(lead, champ, None)
    if ancien == propre:
        return CHAMP_AUTO_INCHANGE, ''
    # ACVI32 — comme le PATCH : marqueur respecté (refus au chatter), dérivée persistée.
    from apps.records.provenance import MESSAGE_REFUS, ecrire_si_libre

    if not ecrire_si_libre(lead, champ, propre, user=user):
        return CHAMP_AUTO_INCHANGE, MESSAGE_REFUS
    # Par introspection (jamais `views` : contrat import-linter ventes -/-> audit).
    derivees = [c.name for c in Lead._meta.concrete_fields if c.name.endswith('_normalise')]
    lead.save(update_fields=[champ, *derivees])
    creer_activite(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION, field=champ,
        field_label=_activity.TRACKED_FIELDS.get(champ, champ),
        old_value=_activity._display(lead, champ, ancien),
        new_value=_activity._display(lead, champ, propre))
    if champ == 'relance_date':
        sync_relance_activity(lead, user)
    return CHAMP_AUTO_APPLIQUE, ''


# ── CAD-A ── RÉPONSES DE TOUCHE : ce que le client DIT décide de la suite ─────
#
# Audit L3 du 21/09/2026. Les réponses offertes sur une touche se limitaient
# aux issues de ``LeadActivity.OUTCOMES`` (joint / non joint / à rappeler /
# refus / intéressé / visite acceptée) : « arrêtez de m'appeler », « plus
# tard », « c'est une question de prix », « refaites-moi le devis », « on
# décide en famille » n'avaient AUCUN bouton, et la commerciale choisissait
# l'issue la moins fausse — dont la suite automatique était, elle, fausse.
#
# LA RÈGLE. Une RÉPONSE est une clé connue du SERVEUR, jamais une nouvelle
# valeur d'énumération : elle se traduit en une issue EXISTANTE (aucune
# migration), une note typée (la phrase du client, telle qu'elle est comptée
# dans le chatter) et UN effet — celui que le client a demandé. L'écran
# n'envoie que la clé ; l'issue est dérivée ICI, et nulle part ailleurs.


# ── CAD-A ── CAD7 — « Question de prix — veut négocier » ────────────────────


# ── CAD158 — « votre facture, c'est pour un mois ou pour deux ? » ───────────
#
# Le moteur (`apps/ventes/etude_horaire.py`, inversion au barème) lit
# `facture_hiver` comme un montant MENSUEL : un client qui donne le montant de
# sa facture BIMESTRIELLE faussait tout l'aval (niveau de facture, économie).
# Décision fondateur du 21/09/2026 (Q24) : le montant est ramené au mois AU
# MOMENT DE LA SAISIE, et aucun champ « périodicité » n'est stocké.

def refus_periodicite_facture(periodicite):
    """CAD158 — le message (FR, qui NOMME le champ) si ``periodicite`` n'est
    pas une période connue, sinon ``None``."""
    if periodicite in Lead.PERIODICITES_FACTURE:
        return None
    choix = ' ou '.join(f'« {cle} »' for cle in Lead.PERIODICITES_FACTURE)
    return (f'« Période de la facture » : {choix} attendu '
            f'(reçu « {periodicite} »).')


def facture_au_mois(montant, periodicite):
    """CAD158 — le montant MENSUEL d'une facture déclarée sur ``periodicite``
    (``mensuelle`` : inchangé ; ``bimestrielle`` : divisé par deux), arrondi
    au centime selon la convention monétaire (moitié vers le haut).

    ``None`` reste ``None`` : aucun montant n'est jamais inventé."""
    from decimal import Decimal

    from core.money import quantize_mad

    if montant is None or montant == '':
        return None
    mois = Lead.PERIODICITES_FACTURE[periodicite]
    return quantize_mad(Decimal(str(montant)) / Decimal(mois))


def appliquer_bascules_fiche(old, new_lead, user):
    """ACVI31 — les effets d'un PATCH de la fiche sur ses bascules (extrait de
    ``LeadViewSet.perform_update``) : perdu, opposition, réouverture,
    responsable. Le PATCH ``owner`` a les effets de ``reattribuer_lead``."""
    # MRY9 (c)(d) — deux bascules ARRÊTENT les relances. Le passage
    # d'étape est déjà couvert par le receiver `lead_stage_changed`.
    # SUIVI E21 (30/09/2026) — et le rendez-vous de visite EN ATTENTE
    # s'annule avec elles (best-effort, note au chatter quand un
    # rendez-vous est réellement annulé) : le technicien ne se déplace
    # pas chez un client perdu ou qui ne veut plus être contacté.
    from .cadence_visite import (
        CAUSE_RDV_NE_PLUS_CONTACTER,
        annuler_rendez_vous_sur_arret,
        cause_rdv_perdu,
    )
    from .cadence_plan import arreter_cadence
    try:
        if not old.perdu and new_lead.perdu:
            arreter_cadence(
                new_lead, user=user,
                motif=(new_lead.motif_perte or 'lead perdu'))
            annuler_rendez_vous_sur_arret(
                new_lead, user,
                cause=cause_rdv_perdu(new_lead.motif_perte))
        if not old.ne_plus_contacter and new_lead.ne_plus_contacter:
            arreter_cadence(new_lead, user=user,
                            motif='ne plus contacter')
            annuler_rendez_vous_sur_arret(
                new_lead, user,
                cause=CAUSE_RDV_NE_PLUS_CONTACTER)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning(
            'MRY9: arrêt de cadence échoué sur le lead #%s',
            new_lead.pk, exc_info=True)
    # CAD91 — l'opposition cochée sur la fiche est inscrite au REGISTRE
    # (``ConsentRecord`` granted=False, daté), indépendamment de l'arrêt
    # de cadence ci-dessus : sans elle, rien ne prouverait qu'elle a été
    # honorée. Aucun motif exigé (loi 09-08 art. 9 al. 2).
    if not old.ne_plus_contacter and new_lead.ne_plus_contacter:
        from .cadence_reponses import (
            CONSENT_SOURCE_OPPOSITION_FICHE,
            tracer_opposition_registre,
        )
        tracer_opposition_registre(
            new_lead, source=CONSENT_SOURCE_OPPOSITION_FICHE)
    # ACRM59 — la DÉCOCHE est tracée elle aussi : une ligne accordée par
    # finalité de contact, dont la source nomme l'utilisateur.
    if old.ne_plus_contacter and not new_lead.ne_plus_contacter:
        from .leads_consentement import tracer_levee_opposition_registre
        tracer_levee_opposition_registre(new_lead, user)
    # CAD107 — la bascule INVERSE n'était traitée nulle part : décocher
    # « Perdu » ne déclenchait rien, alors qu'un client perdu qui revient
    # est le meilleur signal d'achat qui existe. Les trois chemins de
    # réouverture (ce PATCH, le lot `unset_perdu`, la nouvelle touche
    # entrante) posent désormais la MÊME cadence de reprise.
    from .cadence_touche import reprendre_cadence_apres_reouverture
    try:
        if old.perdu and not new_lead.perdu:
            reprendre_cadence_apres_reouverture(
                new_lead, user, origine='fiche rouverte')
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning(
            'CAD107: reprise non posée sur le lead #%s',
            new_lead.pk, exc_info=True)
    # ACVI52 — lever l'opposition pose la même reprise que rouvrir un perdu.
    if old.ne_plus_contacter and not new_lead.ne_plus_contacter:
        try:
            reprendre_cadence_apres_reouverture(
                new_lead, user, origine='opposition levée')
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
            logger.warning('ACVI52: reprise non posée sur le lead #%s',
                           new_lead.pk, exc_info=True)
    if new_lead.owner_id and old.owner_id != new_lead.owner_id:
        from .cadence_reponses import effets_reattribution
        try:
            effets_reattribution(new_lead, user, old.owner)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
            logger.warning('ACVI31: passation non posée sur le lead #%s',
                           new_lead.pk, exc_info=True)


def refus_restauration_lead(lead):
    """ASUP9 — motif du refus de restaurer (absorbé par une fusion, doublon vivant), sinon ``None``."""
    import re

    from .leads_doublons import find_duplicates_by_contact
    from .leads_fusion import NOTE_FUSION
    if absorbant := re.findall(re.escape(NOTE_FUSION) + r'(\d+)', lead.note or ''):
        return f'Restauration refusée : absorbé par le lead #{absorbant[-1]} (fusion).'
    if vivants := [d for d in find_duplicates_by_contact(lead.company, phone=lead.telephone, email=lead.email,
                                                         whatsapp=lead.whatsapp, exclude_pk=lead.pk)
                   if not d.is_archived]:
        return f'Restauration refusée : doublon vivant : lead #{vivants[0].pk}.'
    return None


def restaurer_lead(lead, user, *, note=None, sur_refus=None):
    """ACVI36 — LA restauration d'un lead archivé (fiche et lot) : écriture et
    chatter dans la même transaction (ALEA30), puis la prochaine étape.
    ``note`` : le texte du lot, sinon la ligne de restauration de la fiche.
    ASUP9 — refus 409 nommé (rien écrit) pour un absorbé ou un doublon ; le lot
    passe ``sur_refus(motif)`` et reçoit ``None`` au lieu du 409."""
    from django.db import transaction

    from core.conflit_etat import ConflitEtat
    if refus := refus_restauration_lead(lead):
        if sur_refus is None:
            raise ConflitEtat(refus)
        return sur_refus(refus)

    from . import activity
    from .cadence_filet import assurer_prochaine_etape_apres_succes

    lead.is_archived = False
    lead.archived_by = None
    lead.archived_at = None
    with transaction.atomic():
        lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
        if note:
            activity.log_bulk_note(lead, user, note)
        else:
            activity.log_restore(lead, user)
    assurer_prochaine_etape_apres_succes(lead, user)
    return lead


def restaurer_lead_corbeille(element):
    """ASUP11 — restaurateur ``crm.lead`` de la corbeille commune : la garde d'ASUP9 (409 nommé), puis ``restore()``
    (ligne « restauré » et prochaine étape suivent, ASOC86) ; l'archivage n'est jamais touché."""
    from core.conflit_etat import ConflitEtat
    lead = Lead.all_objects.filter(pk=element.object_id, company_id=element.company_id).first()
    if lead is not None and (refus := refus_restauration_lead(lead)):
        raise ConflitEtat(refus)
    return lead.restore() if lead is not None else None
