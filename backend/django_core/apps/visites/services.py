"""Écritures/orchestration du module « Visites terrain » (``apps.visites``).

VT3 — LE FEU VERT DU BUREAU D'ÉTUDES
------------------------------------
Deux transitions, deux notifications au COMMERCIAL de la visite (primitive
``apps.notifications`` existante — jamais un second système de messages) :
« validée » (feu vert, il peut passer au calepinage) et « à refaire » (une
action lui est demandée, avec le motif). Ces deux transitions ne portent
AUCUN jugement automatisé : c'est un humain qui décide, le code se contente
d'enregistrer sa décision et de la faire savoir.

FRONTIÈRE M3 — cette app n'importe JAMAIS ``apps.crm.models`` et n'écrit
JAMAIS sur ``crm.Lead`` :

* le FEU VERT est publié comme ÉVÉNEMENT ``visite_validee`` (bus
  ``core.events``, M6) ; c'est ``apps.crm.receivers`` qui décide ce qu'il
  inscrit sur la fiche lead. Le ``lead_id`` voyage en entier, le récap est
  pré-calculé par le selector de cette app ;
* le chatter des AUTRES moments (création / terminée / à refaire) passe par
  ``journaliser_visite`` ci-dessous, qui délègue au ``services.py`` du CRM en
  import paresseux — le journal d'un lead appartient au lead.
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
            link=f'/visites/{visite.pk}', company=visite.company)
    except Exception:  # pragma: no cover - défensif
        return None


def notifier_assignation(visite, acteur=None):
    """VTA7 — previent l'ASSIGNE qu'une visite l'attend.

    Appele a la creation ET a la reassignation : sans ce message, un commercial
    terrain ne decouvrait sa visite qu'en ouvrant l'app -- alors que sa journee
    vient justement de changer. Le lien pointe l'ecran de la visite dans l'app
    autonome (``/visites/<id>``).

    Trois prudences :

    * on ne notifie PAS l'acteur de sa propre assignation (s'assigner une
      visite ne merite pas une cloche) ;
    * pas de destinataire (visite non assignee) => rien a envoyer ;
    * best-effort -- la visite est deja creee/reassignee quand on arrive ici,
      une notification en echec ne doit pas defaire ce geste.

    La cloche elle-meme est ouverte a TOUT role (``apps.notifications`` la sert
    sous ``IsAnyRole``), donc un « Commercial terrain » -- qui n'a aucun droit
    CRM -- la recoit normalement.
    """
    destinataire = visite.commercial
    if destinataire is None:
        return None
    if acteur is not None and getattr(acteur, 'id', None) == destinataire.id:
        return None
    quand = ('' if visite.date_prevue is None
             else f" du {visite.date_prevue.strftime('%d/%m/%Y')}")
    return _notifier_commercial_visite(
        visite, 'visite_terrain_assignee',
        'Visite technique assignee',
        f'La visite{quand} chez « {visite.lead} » vous est assignee.')


def journaliser_visite(visite, user, moment, detail=''):
    """Pose la note de chatter du ``moment`` sur le LEAD de la visite.

    Le chatter d'un lead (``crm.LeadActivity``) est le journal COMMUN de tout
    ce qui lui arrive : la visite y écrit ses moments plutôt que d'ouvrir un
    second historique (la dette des 13 chatters hand-rollés). L'écriture
    appartient donc au CRM et passe par SON ``services.py`` (frontière M3,
    import paresseux) ; cette app n'importe jamais ``apps.crm.models``.

    Best-effort côté CRM : un chatter indisponible ne fait jamais échouer la
    transition métier qui vient d'aboutir.
    """
    from apps.crm import services as crm_services

    return crm_services.journaliser_visite(visite, user, moment, detail=detail)


def valider_visite(visite, user):
    """Feu vert calepinage : la visite passe VALIDÉE et devient lecture seule.

    VTA5 — le retour vers le lead se fait par ÉVÉNEMENT (``visite_validee``,
    bus ``core.events``), plus par un appel direct : c'est ``apps.crm`` qui
    décide, dans SON ``receivers.py``, ce qu'il inscrit sur la fiche. Le récap
    est PRÉ-CALCULÉ ici (le selector de cette app en est la source de vérité)
    et le ``lead_id`` voyage en ENTIER — l'app visites ne fait plus aucun écrit
    sur ``crm.Lead``.
    """
    from core.events import visite_validee

    from . import selectors
    from .models import VisiteTerrain

    visite.statut = VisiteTerrain.Statut.VALIDEE
    visite.save(update_fields=['statut'])
    visite_validee.send(
        sender=VisiteTerrain, visite=visite, lead_id=visite.lead_id,
        user=user, recap=selectors.recap_visite_terrain(visite))
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
    journaliser_visite(visite, user, 'a_refaire', detail=f'Motif : {motif}')
    _notifier_commercial_visite(
        visite, 'visite_terrain_a_refaire',
        'Visite technique à refaire',
        f'La visite du lead « {visite.lead} » revient à refaire. '
        f'Motif : {motif}')
    return ''
