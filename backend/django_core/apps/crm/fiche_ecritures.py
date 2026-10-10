"""Écritures de champs de la fiche lead (SPL20, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from django.utils import timezone

from core.dates import aujourd_hui_local

from .cadence_plan import sync_relance_activity
from .leads_socle import MOTIF_BULK_CADENCE_ACTIVE, leads_avec_cadence_active
from .models import Lead, LeadActivity, PointContact


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

    LeadActivity.objects.create(
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
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
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
    except Exception:  # noqa: BLE001
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
        LeadActivity.objects.create(
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
    setattr(lead, champ, propre)
    lead.save(update_fields=[champ])
    LeadActivity.objects.create(
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
