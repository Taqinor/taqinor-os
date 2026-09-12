"""Écritures/orchestration du module « Visites terrain » (``apps.visites``).

VT3 — LE FEU VERT DU BUREAU D'ÉTUDES
------------------------------------
Deux transitions, deux notifications au COMMERCIAL de la visite (primitive
``apps.notifications`` existante — jamais un second système de messages) :
« validée » (feu vert, il peut passer au calepinage) et « à refaire » (une
action lui est demandée, avec le motif). Ces deux transitions ne portent
AUCUN jugement automatisé : c'est un humain qui décide, le code se contente
d'enregistrer sa décision et de la faire savoir.

FRONTIÈRE M3 — tout ce qui ÉCRIT SUR LE LEAD (le chatter ``LeadActivity`` et
le retour du feu vert sur la fiche) reste du ressort du CRM et passe par
``apps.crm.services`` en import PARESSEUX ; cette app n'importe JAMAIS
``apps.crm.models``. VTA5 remplacera ces appels directs par l'émission de
l'événement ``visite_validee`` sur le bus ``core.events``, auquel le CRM
s'abonnera dans son propre ``receivers.py``.
"""


def _notifier_commercial_visite(visite, event_type, titre, corps):
    """Notifie le commercial de la visite. Best-effort, jamais bloquant."""
    destinataire = visite.commercial
    if destinataire is None:
        return None
    try:
        from apps.notifications.services import notify

        return notify(
            destinataire, event_type, titre, body=corps,
            link=f'/crm/visites/{visite.pk}', company=visite.company)
    except Exception:  # pragma: no cover - défensif
        return None


def valider_visite(visite, user):
    """Feu vert calepinage : la visite passe VALIDÉE et devient lecture seule."""
    from .models import VisiteTerrain

    visite.statut = VisiteTerrain.Statut.VALIDEE
    visite.save(update_fields=['statut'])
    # Frontière M3 : les DEUX écritures qui touchent le LEAD passent par le
    # ``services.py`` du CRM (imports paresseux). VTA5 les remplacera par
    # l'événement ``visite_validee`` du bus ``core.events``.
    from apps.crm import services as crm_services

    crm_services.ecrire_retour_lead_visite(visite)
    crm_services.journaliser_visite(visite, user, 'validee')
    _notifier_commercial_visite(
        visite, 'visite_terrain_validee',
        'Visite technique validée',
        f'La visite du lead « {visite.lead} » a reçu le feu vert du bureau '
        "d'études.")
    return visite


def renvoyer_visite(visite, user, *, photos=None, mesures=None, motif=''):
    """Renvoie la visite au commercial avec le détail EXACT de ce qu'il refaire.

    ``photos`` — ids de ``VisiteMedia`` à reprendre ; ``mesures`` — liste de
    ``{'categorie': ..., 'code': ...}`` à re-relever. Le ``motif`` est
    obligatoire (validé côté sérialiseur) et il est recopié sur CHAQUE élément
    marqué, pour que la tuile porte elle-même son explication.

    Renvoie un message d'erreur FR si un id de photo ne correspond à rien sur
    cette visite (l'erreur NOMME ce qui cloche), sinon ``''``.
    """
    from . import visite_checklist as checklist
    from .models import VisiteTerrain

    ids = [int(pk) for pk in (photos or [])]
    medias = list(visite.medias.filter(pk__in=ids)) if ids else []
    if len(medias) != len(set(ids)):
        connus = sorted(str(media.pk) for media in medias)
        return ('Une ou plusieurs photos demandées n’appartiennent pas à cette '
                'visite. Photos reconnues : '
                + (', '.join(connus) if connus else 'aucune') + '.')

    for media in medias:
        media.a_refaire = True
        media.motif_refaire = motif
        media.save(update_fields=['a_refaire', 'motif_refaire'])

    # Une mesure « à refaire » est une mesure à RE-RELEVER : on la vide, donc
    # la complétude serveur la redemande d'elle-même — aucun second registre
    # d'état à tenir synchrone.
    stockees = dict(visite.mesures if isinstance(visite.mesures, dict) else {})
    touchee = False
    for demande in (mesures or []):
        categorie = (demande or {}).get('categorie')
        code = (demande or {}).get('code')
        if checklist.mesure(categorie, code) is None:
            continue
        bloc = dict(stockees.get(categorie) or {})
        if code in bloc:
            bloc[code] = None
            stockees[categorie] = bloc
            touchee = True
    if touchee:
        visite.mesures = stockees

    visite.statut = VisiteTerrain.Statut.A_REFAIRE
    champs = ['statut', 'mesures'] if touchee else ['statut']
    visite.save(update_fields=champs)
    from apps.crm import services as crm_services

    crm_services.journaliser_visite(
        visite, user, 'a_refaire', detail=f'Motif : {motif}')
    _notifier_commercial_visite(
        visite, 'visite_terrain_a_refaire',
        'Visite technique à refaire',
        f'La visite du lead « {visite.lead} » revient à refaire. '
        f'Motif : {motif}')
    return ''
