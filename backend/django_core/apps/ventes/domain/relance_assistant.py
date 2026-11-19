"""Copilote vague 2 (VAD8) — préparer le WhatsApp de RELANCE d'une facture.

CLAUSE CALCULÉE (19/11/2026) : la route de l'écran ``POST
factures/<id>/whatsapp/`` (``facturation/views/facture_documents.py``)
refuse une facture contestée et un numéro invalide, mais NE CONTRÔLE PAS
l'opposition de la personne (« ne plus contacter », D-AMSG-2 étendu à toutes
les fiches) et lit ``modele`` dans le corps. L'assistant ne l'appelle donc pas :
cette préparation-ci force le modèle « relance », refuse tout ce que la relance
refuse (``facture_relancable`` : brouillon, payée, annulée, soldée, contestée),
refuse une personne opposée (``crm.selectors.peut_contacter`` sur le lead de
la facture et de son devis + ``porte_une_opposition`` sur l'adresse du
client) et un numéro
inexploitable.

Le TEXTE est le modèle « relance » VALIDÉ de la société (Paramètres →
Messages, ``utils/whatsapp.build_facture_whatsapp``) — jamais un texte écrit
par le modèle, aucune entrée libre. Rien n'est envoyé : un lien wa.me que la
personne ouvre et envoie elle-même ; la préparation est tracée au chatter de la
facture, comme à l'écran.
"""


class RelanceRefusee(Exception):
    """409 ``{detail, code}`` : la relance ne se prépare pas."""

    def __init__(self, detail, code):
        super().__init__(detail)
        self.corps = {'detail': detail, 'code': code}


def _porteurs_du_lead(facture):
    """La facture (lead snapshoté, U12), son devis et le devis de son BC :
    tout objet qui porte un ``lead`` lu par ``peut_contacter``."""
    bon_commande = getattr(facture, 'bon_commande', None)
    return [o for o in (facture, getattr(facture, 'devis', None),
                        getattr(bon_commande, 'devis', None)) if o is not None]


def motif_de_refus(facture):
    """Le premier refus qui s'applique, ou ``None``."""
    from apps.crm.selectors import (
        MOTIF_CONTACT_REFUSE, peut_contacter, porte_une_opposition)
    from apps.facturation.recouvrement import facture_relancable
    from apps.ventes.utils.phone import normalize_phone_e164

    relancable, motif = facture_relancable(facture)
    if not relancable:
        return RelanceRefusee(motif, 'non_relancable')
    client = facture.client if facture.client_id else None
    if not all(peut_contacter(o, 'whatsapp') for o in _porteurs_du_lead(facture)) or (
            client is not None and porte_une_opposition(
                facture.company_id, email=client.email or None,
                telephone=client.telephone or None)):
        return RelanceRefusee(MOTIF_CONTACT_REFUSE + '.', 'opposition')
    if client is None or not normalize_phone_e164(client.telephone or ''):
        return RelanceRefusee(
            'Numéro de téléphone du client invalide ou absent : corrigez la '
            'fiche client.', 'telephone_invalide')
    return None


def preparer_relance(request, facture, langue='fr'):
    """``(texte, wa_url)`` du modèle « relance » validé + trace au chatter.
    Lève :class:`RelanceRefusee` (rien n'est préparé ni tracé)."""
    from apps.ventes.activity import log_facture_whatsapp
    from apps.ventes.utils.whatsapp import build_facture_whatsapp, build_wa_url

    refus = motif_de_refus(facture)
    if refus is not None:
        raise refus
    texte, _lien = build_facture_whatsapp(request, facture, 'relance', langue)
    log_facture_whatsapp(facture, request.user, 'relance')
    return texte, build_wa_url(facture.client.telephone, texte)
