"""NTMOB1 — handlers de rejeu enregistrés au démarrage (`apps.py: ready()`).

Chaque handler passe EXCLUSIVEMENT par le `selectors.py` (lecture) et le
`services.py` (écriture) de l'app visée : `apps.offlinesync` n'importe jamais
les `models`/`views` d'une autre app. Les imports sont fonction-locaux — le
registre se charge au `ready()`, avant que les autres apps aient forcément fini
de se peupler.

Le jeu de départ couvre le CRM (critère d'acceptation NTMOB1 : une note posée
hors-ligne sur un lead s'applique UNE SEULE FOIS à la reconnexion, même si le
flush est rejoué deux fois). Les autres modules s'ajoutent par un simple
``registry.register(...)`` — c'est le point d'extension, aucun code du moteur
n'est à toucher.

NOTE — la capture terrain (`installations`) garde son point de synchro
historique `/installations/sync/` (mêmes clés d'idempotence, même contrat de
réponse) : NTMOB1 généralise l'ENTRÉE serveur pour les autres modules, il ne
rebranche pas un flux terrain déjà éprouvé.
"""
from .registry import OfflineOpError, register


def _lead(company, payload):
    """Résout un lead BORNÉ SOCIÉTÉ via le selector du CRM (jamais ses models).
    Un id d'une autre société est donc indiscernable d'un id inconnu."""
    from apps.crm import selectors as crm_selectors

    lead = crm_selectors.get_company_lead(company, payload.get('lead'))
    if lead is None:
        raise OfflineOpError('Lead inconnu.')
    return lead


def h_lead_noter(company, user, payload):
    """`crm.lead.noter` — note manuelle (chatter) posée hors-ligne."""
    from apps.crm import services as crm_services

    body = (payload.get('body') or '').strip()
    if not body:
        raise OfflineOpError('Note vide.')
    lead = _lead(company, payload)
    activite = crm_services.ajouter_note_lead(
        company=company, lead_id=lead.id, user=user, body=body)
    return {'lead': lead.id, 'activite': activite.id}


def h_lead_tag(company, user, payload):
    """`crm.lead.tag` — pose un tag (idempotent, last-write-wins)."""
    from apps.crm import services as crm_services

    tag = (payload.get('tag') or '').strip()
    if not tag:
        raise OfflineOpError('Tag vide.')
    lead = _lead(company, payload)
    crm_services.poser_tag_lead(lead, user, tag)
    return {'lead': lead.id, 'tags': lead.tags}


register('crm.lead.noter', 'crm', h_lead_noter)
register('crm.lead.tag', 'crm', h_lead_tag)
