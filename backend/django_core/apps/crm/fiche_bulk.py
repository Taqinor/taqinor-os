"""Actions en masse sur les leads (SPL3, extrait de crm/services.py : déplacement pur).

Module RACINE de la scission : il importe ``.services`` au niveau module ;
aucun module de type (a) ne l'importe et ``services`` ne le réexporte pas.
"""
import re

from django.db.models import Q
from django.utils import timezone

from . import activity, stages
from .models import Canal, Lead, LeadActivity
from .leads_fusion import raison_refus_suppression
from .cadence_touche import reprendre_cadence_apres_reouverture
from .cadence_filet import assurer_prochaine_etape_apres_succes
from .cadence_plan import arreter_cadence, sync_relance_activity
from .fiche_funnel import (
    ETAT_PAR_RAISON,
    ParcRefuse,
    SortieSigneBloquee,
    _bulk_stage_allowed,
    _corps_whatsapp_en_masse,
    _resolve_owner,
    appliquer_stage_lead,
    desaccepter_devis_du_lead,
    parquer_lead,
)
from .cadence_reponses import reattribuer_lead
from .leads_socle import MOTIF_BULK_CADENCE_ACTIVE, leads_avec_cadence_active
from .mesure_cadence import SEAUX_REACTIVATION, trace_reactivation


BULK_ACTIONS = {
    'reassign', 'add_tag', 'remove_tag', 'set_stage', 'set_canal',
    'set_priorite', 'set_relance', 'clear_relance', 'set_perdu',
    'unset_perdu', 'archive', 'unarchive', 'delete', 'plan_activity',
    'prepare_whatsapp',  # FG33 — file de click-through WhatsApp en masse
}

# Priorités valides (clés du modèle Lead.Priorite).
_PRIORITES = {'basse', 'normale', 'haute'}
# Actions réservées à l'admin (la suppression définitive l'est déjà partout).
BULK_ADMIN_ONLY = {'delete'}


class ReferenceInconnue(ValueError):
    """CI #997 (2) — une référence bien formée qui ne désigne rien (canal hors
    référentiel) : la vue la sert en 404, plus en 400 (la requête est conforme
    au schéma, c'est la ressource qui manque)."""


def _texte(valeur):
    """Texte rogné d'un paramètre ; tout autre type vaut « vide » (un nombre
    levait ``AttributeError`` sur ``.strip()`` — 500)."""
    return valeur.strip() if isinstance(valeur, str) else ''


def _motif_perte_exige(params):
    """Motif de la mise en perte en masse, exigé AVANT la boucle — même pour
    une sélection vide (CI #997 (2) : la vérification ne vivait que dans la
    boucle, un schéma qui le déclare obligatoire était donc « violé » en
    silence). MRY22 — même exigence qu'à l'unité : perdre 40 leads d'un coup
    SANS raison est pire, pas plus acceptable."""
    motif = _texte(params.get('motif'))
    if not motif:
        raise ValueError(
            'Motif de perte obligatoire pour une mise en perte en masse.')
    return motif


_DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}\Z')


def _parse_date(value):
    """Date ``AAAA-MM-JJ`` STRICTE (comme le schéma ``format: date``) ; vide ou
    illisible -> ``None``. Un objet ``date`` passe tel quel (appelants internes)."""
    from datetime import date
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not _DATE_ISO.match(value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _resolve_activity_type(company, type_id, type_nom):
    """Type d'activité cible pour une planification en masse : par id (société
    courante) sinon par nom (créé à la volée s'il manque), repli sur « À faire ».
    """
    from apps.records.models import ActivityType
    if type_id not in (None, '', 'null'):
        atype = ActivityType.objects.filter(id=type_id, company=company).first()
        if atype is not None:
            return atype
    nom = (type_nom or 'À faire').strip() or 'À faire'
    atype = ActivityType.objects.filter(company=company, nom=nom).first()
    if atype is None:
        atype = ActivityType.objects.create(company=company, nom=nom, ordre=50)
    return atype


def coerce_id_list(raw):
    """Normalise une liste d'ids reçue du client en entiers uniques.

    Accepte ints et chaînes numériques ; déduplique en préservant l'ordre.
    Lève ValueError sur un élément non entier — la vue le traduit en 400 propre
    au lieu de laisser un 500 remonter du `id__in` (PostgreSQL refuse un id
    non numérique). Sert aux endpoints en masse + WhatsApp.
    """
    if not isinstance(raw, (list, tuple)):
        raise ValueError("Liste d'identifiants invalide.")
    out = []
    seen = set()
    for item in raw:
        if isinstance(item, (bool, float)):
            raise ValueError("Identifiant invalide.")
        try:
            value = int(item)
        except (TypeError, ValueError):
            raise ValueError("Identifiant invalide.")
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


#: CADV10 (conception v4 §5.2) — au plus 25 préparations WhatsApp en masse par
#: jour et par utilisateur ; le compte se lit sur la trace laissée au chatter.
PREPARER_WHATSAPP_PLAFOND_PAR_JOUR = 25
TRACE_WHATSAPP_PREPARE = 'WhatsApp préparé en lot'


def _minuit_local():
    import datetime

    from core.dates import aujourd_hui_local

    from . import horaires
    return datetime.datetime.combine(
        aujourd_hui_local(), datetime.time(0), tzinfo=horaires.CASABLANCA)


def _preparations_whatsapp_du_jour(company, user):
    """CADV10 — traces « WhatsApp préparé en lot » de ``user`` aujourd'hui
    (jour de Casablanca) : aucun modèle, aucune migration. CADV109 — une
    préparation de réactivation en est une, sous son propre marqueur."""
    return LeadActivity.objects.filter(
        Q(body__startswith=TRACE_WHATSAPP_PREPARE)
        | Q(body__in=[trace_reactivation(s) for s in SEAUX_REACTIVATION]),
        company=company, user=user, created_at__gte=_minuit_local()).count()


def _reactivation_demandee(company, params, leads):
    """CADV109 (D-CADV-11) — ``None`` hors réactivation, sinon le seau demandé :
    ``ferme`` (palier 2 sans son interrupteur), ``membres`` (lus sur
    ``seaux_reactivation``), ``deja`` (leads déjà tracés aujourd'hui, rejouer le
    même jour n'ajoute rien). Seau ou gabarit inconnus : refus (400)."""
    from django.conf import settings

    from apps.parametres.models_messages import CLES_REACTIVATION

    from .cadence_selectors import seaux_reactivation

    seau = _texte(params.get('seau'))
    if not seau:
        return None
    if seau not in SEAUX_REACTIVATION:
        raise ValueError("Seau de réactivation inconnu.")
    cle = _texte(params.get('template_cle'))
    if cle and cle not in CLES_REACTIVATION:
        raise ValueError("Gabarit de réactivation inconnu.")
    ferme = seau == 'k6_p2' and not getattr(settings, 'REACTIVATION_K6_PALIER2', False)
    return {
        'seau': seau, 'cle': cle, 'ferme': ferme,
        'membres': [] if ferme else seaux_reactivation(company)[seau.capitalize()],
        'deja': set(LeadActivity.objects.filter(
            company=company, lead__in=leads, body=trace_reactivation(seau),
            created_at__gte=_minuit_local()).values_list('lead_id', flat=True)),
    }


def _lien_reactivation(lead, user, cle, plateforme=''):
    """CADV109 — ``(wa_url, blancs)`` du gabarit ``cle`` : la machinerie des touches
    (``message_pour_etape``), sur une touche NON enregistrée, jamais un second rendu.
    ERR-CADV-REACTIVATION-BLANC — ``plateforme`` (tapée à la main) complète le blanc
    « [plateforme] » ; tout blanc restant est rendu en ``blancs`` (CAD69) : le lien
    n'est alors pas utilisable et l'appelant sort le lead avec le blanc nommé."""
    from apps.ventes.utils.whatsapp import build_wa_url
    from core.dates import aujourd_hui_local

    from .cadence_messages import _crochets_a_completer, message_pour_etape
    from .models import RelanceEtape

    touche = RelanceEtape(company=lead.company, lead=lead, due_date=aujourd_hui_local(),
                          canal=RelanceEtape.Canal.WHATSAPP)
    rendu = message_pour_etape(touche, user=user, cle=cle)
    if not plateforme:
        return rendu['wa_url'], _crochets_a_completer(rendu['message'])
    corps = rendu['message'].replace('[plateforme]', plateforme)
    return build_wa_url(rendu['phone'], corps), _crochets_a_completer(corps)


def _tracer_reactivation(lead, user, seau):
    """CADV109 — UNE ligne de chatter et UNE entrée de registre par préparation."""
    from .leads_consentement import (
        BASE_LEGALE_SOLLICITATION, CONSENT_SOURCE_REACTIVATION,
        enregistrer_base_legale_lead,
    )

    activity.log_bulk_note(lead, user, trace_reactivation(seau))
    enregistrer_base_legale_lead(
        lead, base_legale=BASE_LEGALE_SOLLICITATION,
        source=CONSENT_SOURCE_REACTIVATION.format(seau=SEAUX_REACTIVATION[seau]))


def _file_whatsapp_en_masse(company, user, leads, params, skip, skipped):
    """FG33 — la file de click-through WhatsApp, ordonnée : gardes ACRM15,
    plafond et trace CADV10. Sortie de ``apply_bulk_action`` (C20)."""
    from apps.ventes.utils.whatsapp import build_wa_url

    from .cadence_messages import _crochets_a_completer, numero_joignable, refus_rendu_whatsapp
    from .serializers import pii_masquee_pour
    template_id = params.get('template_id')
    body_tpl = params.get('body') or ''
    tpl = None
    if template_id:
        try:
            from .models import MessageTemplate
            tpl = MessageTemplate.objects.filter(
                company=company, id=template_id).first()
        except (ValueError, TypeError):  # id illisible : corps direct
            tpl = None
    queue = []
    deja = _preparations_whatsapp_du_jour(company, user)
    nouvelles = 0
    reactivation = _reactivation_demandee(company, params, leads)
    for lead in leads:
        # ACRM15 (C-ACRM-010), ACVI44 — LA garde des rendus de cadence : une
        # personne qui a demandé à ne plus être contactée, un lead perdu ou
        # archivé ne reçoit AUCUN message — sortis avec leur motif.
        refus = refus_rendu_whatsapp(lead)
        if refus:
            skip(lead, refus)
            continue
        if reactivation and reactivation['ferme']:
            skip(lead, 'palier2_ferme')
            continue
        if reactivation and lead.id not in reactivation['membres']:
            skip(lead, 'hors seau')
            continue
        phone = numero_joignable(lead)  # ACVI50
        if not phone:
            continue
        nouvelle = not (reactivation and lead.id in reactivation['deja'])
        if nouvelle and deja + nouvelles >= PREPARER_WHATSAPP_PLAFOND_PAR_JOUR:
            skip(lead, 'plafond journalier atteint '
                       f'({PREPARER_WHATSAPP_PLAFOND_PAR_JOUR})')
            continue
        if reactivation and reactivation['cle']:
            wa_url, trous = _lien_reactivation(
                lead, user, reactivation['cle'], _texte(params.get('plateforme')))
            if trous:
                skip(lead, 'à compléter : ' + ', '.join(trous))
                continue
        else:
            corps = _corps_whatsapp_en_masse(lead, tpl, body_tpl)
            # CAD69 — LA règle du message d'une touche (``message_pour_etape`` →
            # ``crochets``) : un blanc « [plateforme] » non complété n'est jamais
            # envoyé ; le lead sort de la file avec le blanc nommé.
            trous = _crochets_a_completer(corps)
            if trous:
                skip(lead, 'à compléter : ' + ', '.join(trous))
                continue
            wa_url = build_wa_url(phone, corps)
        masque = pii_masquee_pour(user)  # ACVI4
        queue.append({
            'lead_id': lead.id,
            'nom': str(lead),
            'phone': '' if masque else phone,
            'wa_url': None if masque else wa_url,
        })
        if not nouvelle:
            continue
        nouvelles += 1
        if reactivation:
            _tracer_reactivation(lead, user, reactivation['seau'])
        else:
            activity.log_bulk_note(lead, user, TRACE_WHATSAPP_PREPARE)
    return {
        'ok': True,
        'op': 'prepare_whatsapp',
        'queue': queue,
        'count': len(queue),
        'skipped': skipped,
    }


def apply_bulk_action(*, company, user, lead_ids, op, params, queryset=None):
    """Applique une action en masse à une sélection de leads de la société.

    Renvoie un récapitulatif : nombre mis à jour, nombre inchangés, et la liste
    des leads ignorés avec leur raison (en français). Chaque modification écrit
    une entrée Historique marquée « en masse ».

    ALEA27 — ``queryset`` (BORNÉ) : l'action HTTP ``leads/bulk/`` transmet la
    portée du viewset (société + équipe/sous-arbre) ; un id hors portée est
    IGNORÉ en silence, exactement comme un id absent (aucune fuite
    d'existence). ``None`` = la société entière (aucun appelant HTTP).
    """
    from django.db import transaction

    if op not in BULK_ACTIONS:
        raise ValueError("Action en masse inconnue.")

    lead_ids = coerce_id_list(lead_ids)
    base = queryset if queryset is not None else Lead.objects.all()
    leads = list(
        base.filter(company=company, id__in=lead_ids).order_by('id'))
    updated, unchanged, skipped = 0, 0, []

    def skip(lead, reason):
        skipped.append({'id': lead.id, 'nom': str(lead), 'reason': reason})

    # Pré-validation des paramètres dépendant de l'action.
    target_stage = None
    owner_obj = None
    tag = _texte(params.get('tag')) if op in ('add_tag', 'remove_tag') else None
    relance = None
    target_canal = None
    target_priorite = None
    activity_type = None
    activity_due = None
    activity_summary = None
    if op == 'set_stage':
        target_stage = params.get('stage')
        if target_stage not in stages.STAGES:
            raise ValueError("Étape cible invalide.")
        # CADV73 (D-CADV-4) — le Froid en lot exige sa raison ; une raison à
        # date (standby) ne s'applique pas à un lot sans date.
        parc_raison = params.get('parc_raison')
        if target_stage == stages.COLD and not (
                isinstance(parc_raison, str)
                and ETAT_PAR_RAISON.get(parc_raison) in ('nurture', 'archive')):
            raise ValueError("Raison de mise au Froid obligatoire.")
    elif op == 'set_canal':
        target_canal = _texte(params.get('canal'))
        if not target_canal:
            raise ValueError("Canal cible vide.")
        # Le canal doit appartenir au référentiel géré (s'il existe).
        if (Canal.objects.filter(company=company).exists()
                and not Canal.objects.filter(
                    company=company, cle=target_canal, archived=False).exists()):
            raise ReferenceInconnue("Canal inconnu.")
    elif op == 'set_priorite':
        target_priorite = params.get('priorite')
        if not isinstance(target_priorite, str) or target_priorite not in _PRIORITES:
            raise ValueError("Priorité invalide.")
    elif op == 'reassign':
        owner_obj = _resolve_owner(company, params.get('owner'))
        if params.get('owner') not in (None, '', 'null') and owner_obj is None:
            raise ValueError("Responsable introuvable dans cette société.")
    elif op in ('add_tag', 'remove_tag') and not tag:
        raise ValueError("Étiquette vide.")
    elif op == 'set_perdu':
        target_motif = _motif_perte_exige(params)
    elif op == 'set_relance':
        relance = _parse_date(params.get('relance_date'))
        if relance is None:
            raise ValueError("Date de relance invalide.")
    elif op == 'plan_activity':
        activity_due = _parse_date(params.get('due_date'))
        if activity_due is None:
            raise ValueError("Date d'échéance invalide.")
        activity_summary = _texte(params.get('summary'))
        if not activity_summary:
            raise ValueError("Intitulé de l'activité vide.")
        activity_type = _resolve_activity_type(
            company, params.get('activity_type_id'), params.get('type_nom'))

    # CAD49 — quels leads de la sélection ont une CADENCE ACTIVE ? Une seule
    # requête, avant la boucle : le bulk traite des centaines de dossiers.
    leads_a_cadence = (
        leads_avec_cadence_active(company, lead_ids)
        if op in ('set_relance', 'clear_relance') else frozenset())

    with transaction.atomic():
        for lead in leads:
            if op == 'reassign':
                if lead.owner_id == (owner_obj.id if owner_obj else None):
                    unchanged += 1
                    continue
                old = lead.owner
                # CAD54 — la réattribution a des EFFETS : le nouveau
                # responsable apprend ce qu'il hérite, et le client est
                # prévenu du changement de conseiller. `reattribuer_lead`
                # pose l'owner lui-même ; le journal « en masse » reste écrit
                # ici, comme pour les autres champs.
                reattribuer_lead(lead, user, owner_obj)
                if owner_obj is None:
                    lead.owner = None
                    lead.save(update_fields=['owner'])
                activity.log_bulk_change(lead, user, 'owner', old, owner_obj)
                sync_relance_activity(lead, user)
                updated += 1

            elif op in ('add_tag', 'remove_tag'):
                current = [t.strip() for t in (lead.tags or '').split(',') if t.strip()]
                has = tag in current
                if op == 'add_tag' and has:
                    unchanged += 1
                    continue
                if op == 'remove_tag' and not has:
                    unchanged += 1
                    continue
                old = lead.tags or ''
                if op == 'add_tag':
                    current.append(tag)
                else:
                    current = [t for t in current if t != tag]
                lead.tags = ', '.join(current)[:500]
                lead.save(update_fields=['tags'])
                activity.log_bulk_change(lead, user, 'tags', old, lead.tags)
                updated += 1

            elif op == 'set_stage':
                if lead.perdu:
                    skip(lead, "lead Perdu — étape non modifiée")
                    continue
                if not _bulk_stage_allowed(lead.stage, target_stage):
                    skip(lead, "étape déjà atteinte ou recul non autorisé")
                    continue
                old = lead.stage
                # Décision fondateur 08/10/2026 — sortir de « Signé » en
                # masse dés-accepte le devis, PAR LEAD, dans son propre point
                # de sauvegarde : un lead bloqué (facture émise, chantier
                # avancé…) est sauté avec la raison, les autres passent.
                try:
                    with transaction.atomic():
                        if old == stages.SIGNED:
                            desaccepter_devis_du_lead(lead, user)
                        # CRX20 — chemin canonique : le bulk émet enfin
                        # ``lead_stage_changed`` (playbooks NTCRM12 +
                        # séquences compta XMKT1 partaient pour un PATCH
                        # unitaire, jamais pour un bulk).
                        if target_stage == stages.COLD:
                            parquer_lead(lead, parc_raison, None, user)
                        else:
                            appliquer_stage_lead(lead, target_stage, user=user)
                            activity.log_bulk_change(
                                lead, user, 'stage', old, target_stage)
                except SortieSigneBloquee as exc:
                    lead.stage = old
                    skip(lead, exc.message)
                    continue
                except ParcRefuse as exc:
                    lead.refresh_from_db()
                    skip(lead, str(exc))
                    continue
                # QJ9 — entrée manuelle en masse dans SIGNED : pas de CAPI ici
                # (pas de devis accepté associé ni d'attribution UTM disponible).
                updated += 1

            elif op == 'set_canal':
                if lead.canal == target_canal:
                    unchanged += 1
                    continue
                old = lead.canal
                lead.canal = target_canal
                lead.save(update_fields=['canal'])
                activity.log_bulk_change(lead, user, 'canal', old, target_canal)
                updated += 1

            elif op == 'set_priorite':
                if (lead.priorite or 'normale') == target_priorite:
                    unchanged += 1
                    continue
                old = lead.priorite
                lead.priorite = target_priorite
                lead.save(update_fields=['priorite'])
                activity.log_bulk_change(lead, user, 'priorite', old, target_priorite)
                updated += 1

            elif op == 'set_relance':
                # CAD49 — REFUSÉ sur un lead à cadence active : la date serait
                # écrasée au premier geste du plan (voir le motif).
                if lead.id in leads_a_cadence:
                    skip(lead, MOTIF_BULK_CADENCE_ACTIVE)
                    continue
                if lead.relance_date == relance:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = relance
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, relance)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'clear_relance':
                # CAD49 — même refus : effacer la date ne retire pas la
                # touche, elle reviendrait au premier geste du plan.
                if lead.id in leads_a_cadence:
                    skip(lead, MOTIF_BULK_CADENCE_ACTIVE)
                    continue
                if not lead.relance_date:
                    unchanged += 1
                    continue
                old = lead.relance_date
                lead.relance_date = None
                lead.save(update_fields=['relance_date'])
                activity.log_bulk_change(lead, user, 'relance_date', old, None)
                sync_relance_activity(lead, user)
                updated += 1

            elif op == 'set_perdu':
                motif = target_motif
                if lead.perdu and lead.motif_perte == motif:
                    unchanged += 1
                    continue
                old_perdu, old_motif = lead.perdu, lead.motif_perte
                lead.perdu = True
                lead.motif_perte = motif
                lead.save(update_fields=['perdu', 'motif_perte'])
                if not old_perdu:
                    activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
                    # MRY9 (c) — un lead perdu EN MASSE arrête ses relances
                    # exactement comme un lead perdu à l'unité : sans cela,
                    # une purge de 40 leads laissait 40 cadences vivantes.
                    arreter_cadence(lead, user=user,
                                    motif=motif or 'lead perdu')
                if old_motif != motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, motif)
                updated += 1

            elif op == 'unset_perdu':
                if not lead.perdu:
                    unchanged += 1
                    continue
                lead.perdu = False
                old_motif = lead.motif_perte
                lead.motif_perte = None
                lead.save(update_fields=['perdu', 'motif_perte'])
                activity.log_bulk_change(lead, user, 'perdu', True, False)
                if old_motif:
                    activity.log_bulk_change(lead, user, 'motif_perte', old_motif, None)
                # CAD107 — un lead REPRIS (dé-perdu) redevient actif : ses
                # cadences avaient été arrêtées au marquage. Les TROIS
                # chemins de réouverture passent désormais par la MÊME
                # fonction (cadence de REPRISE, filet en repli) — avant, ce
                # lot appelait le filet, le PATCH ne faisait rien et la
                # nouvelle touche entrante ne créait aucune relance.
                reprendre_cadence_apres_reouverture(
                    lead, user, origine='reprise en masse')
                updated += 1

            elif op == 'archive':
                if lead.is_archived:
                    unchanged += 1
                    continue
                lead.is_archived = True
                lead.archived_by = user
                lead.archived_at = timezone.now()
                lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
                activity.log_bulk_note(
                    lead, user,
                    f"Lead archivé en masse par {getattr(user, 'username', '?')}")
                updated += 1

            elif op == 'unarchive':
                if not lead.is_archived:
                    unchanged += 1
                    continue
                # QJ-INVARIANT, ACVI36 — la restauration partagée pose le filet.
                from .fiche_ecritures import restaurer_lead
                restaurer_lead(
                    lead, user,
                    note=f"Lead restauré en masse par {getattr(user, 'username', '?')}")
                updated += 1

            elif op == 'plan_activity':
                # Crée UNE activité ouverte (records.Activity) par lead, échéance
                # + intitulé communs, assignée au responsable du lead (repli sur
                # l'acteur). Aucune dédup : planifier deux fois crée deux rappels.
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(lead.__class__)
                Activity.objects.create(
                    company=company, content_type=ct, object_id=lead.id,
                    activity_type=activity_type, summary=activity_summary[:255],
                    due_date=activity_due,
                    assigned_to=lead.owner or user, created_by=user)
                activity.log_bulk_note(
                    lead, user,
                    f"Activité « {activity_summary} » planifiée en masse "
                    f"pour le {activity_due.isoformat()}")
                updated += 1

            elif op == 'delete':
                # ACAL177 — la MÊME garde que la suppression unitaire.
                refus = raison_refus_suppression(lead)
                if refus is not None:
                    skip(lead, refus['detail'])
                    continue
                # VX96 — soft-delete réversible (corbeille 30 min), cohérent avec
                # la suppression unitaire : plus de destruction définitive ici.
                import logging
                logging.getLogger('crm.audit').warning(
                    'BULK SOFT DELETE lead id=%s "%s" par user=%s (company=%s)',
                    lead.id, lead, getattr(user, 'username', '?'), company.id)
                lead.soft_delete(user)
                updated += 1

            # FG33 — Préparer la file WhatsApp en masse (pas d'envoi auto)
            elif op == 'prepare_whatsapp':
                # Pas de décompte updated/unchanged — cette action retourne
                # directement en dehors de la boucle.
                pass

    # FG33 — Résultat spécial : file de click-through WhatsApp ordonné
    if op == 'prepare_whatsapp':
        return _file_whatsapp_en_masse(company, user, leads, params, skip, skipped)

    return {
        'ok': True,
        'updated': updated,
        'unchanged': unchanged,
        'skipped': skipped,
        'total': len(leads),
    }
