"""CAL11 — les trois portes de création d'un calepinage.

TROIS PORTES, UN SEUL OBJET
---------------------------
* ``obtenir_ou_creer_pour_devis`` — la PARITÉ CRM. Le geste « Concevoir la
  toiture (3D) » d'un devis doit retomber sur LE MÊME calepinage à chaque
  appel : le service est IDEMPOTENT et reprend la conception déjà portée par
  le devis (``roof_layout`` / ``layout_hash``).
* ``creer_pour_lead`` et ``creer_pour_client`` — les portes du module
  AUTONOME : on choisit un lead ou un client, et on conçoit sa toiture, même
  s'il n'existe aucun devis. Un calepinage sans devis est un objet de
  première classe.

CE QUE CE MODULE NE FAIT JAMAIS
-------------------------------
* il n'importe AUCUN modèle de ``crm`` ni de ``ventes`` : le lead et le
  client sont résolus par ``apps.crm.selectors`` (``get_company_lead`` /
  ``get_company_client``), le devis par ``apps.ventes.selectors``
  (``get_devis_by_pk``, dont l'appelant vérifie la société — c'est fait ici) ;
* il n'écrit JAMAIS un statut de devis (règle #4 : le moteur de devis ne fait
  que RENDRE) ;
* il ne lit JAMAIS la société d'un corps de requête : ``company`` et l'auteur
  sont posés par l'appelant côté serveur.
"""
from __future__ import annotations


class CreationRefusee(ValueError):
    """Refus métier de création, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _exiger_societe(company):
    if company is None:
        raise CreationRefusee(
            "Un calepinage est toujours rattaché à une société : aucune "
            "société n'a été fournie.", champ='company')


def obtenir_ou_creer_pour_devis(devis_id, company, *, user=None, titre=''):
    """Le calepinage de ce devis — le même à chaque appel (IDEMPOTENT).

    Returns:
        ``(calepinage, cree)`` — ``cree`` vaut ``True`` seulement au premier
        appel.

    Raises:
        CreationRefusee: devis absent, ou appartenant à une AUTRE société
            (rien n'est créé, et l'appelant n'apprend rien de son existence).
    """
    from django.db import transaction

    from apps.ventes.selectors import get_devis_by_pk

    from ..models import Calepinage
    from ..selectors import calepinage_du_devis

    _exiger_societe(company)
    if not devis_id:
        raise CreationRefusee(
            "Aucun devis n'a été indiqué : impossible de retrouver ou de "
            "créer son calepinage.", champ='devis')

    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        raise CreationRefusee(
            f"Devis introuvable (#{devis_id}).", champ='devis')

    existant = calepinage_du_devis(devis_id, company)
    if existant is not None:
        return existant, False

    with transaction.atomic():
        # Re-lecture DANS la transaction : deux clics simultanés sur
        # « Concevoir la toiture » ne doivent pas produire deux calepinages.
        existant = calepinage_du_devis(devis_id, company)
        if existant is not None:
            return existant, False
        calepinage = Calepinage.objects.create(
            company=company,
            devis=devis,
            client_id=getattr(devis, 'client_id', None),
            lead_id=getattr(devis, 'lead_id', None),
            titre=titre or _titre_du_devis(devis),
            roof_layout=getattr(devis, 'roof_layout', None),
            layout_hash=getattr(devis, 'layout_hash', None) or '',
            roof_image=getattr(devis, 'roof_image', None) or '',
            cree_par=user,
        )
    return calepinage, True


def _titre_du_devis(devis):
    """Un titre lisible, dérivé du devis — jamais un prénom codé en dur."""
    reference = (getattr(devis, 'reference', '') or '').strip()
    return f'Calepinage {reference}'.strip() if reference else ''


def creer_pour_lead(lead_id, company, *, user=None, titre=''):
    """Crée un calepinage sur un LEAD (porte autonome du module).

    Raises:
        CreationRefusee: lead absent ou d'une autre société — rien n'est créé.
    """
    from apps.crm.selectors import get_company_lead

    from ..models import Calepinage

    _exiger_societe(company)
    if not lead_id:
        raise CreationRefusee(
            "Aucun lead n'a été indiqué : choisissez le lead dont vous "
            "concevez la toiture.", champ='lead')

    lead = get_company_lead(company, lead_id)
    if lead is None:
        raise CreationRefusee(
            f"Lead introuvable (#{lead_id}).", champ='lead')

    return Calepinage.objects.create(
        company=company,
        lead_id=lead.pk,
        client_id=getattr(lead, 'client_id', None),
        titre=titre or _titre_depuis(getattr(lead, 'nom', '')),
        cree_par=user,
    )


def creer_pour_client(client_id, company, *, user=None, titre=''):
    """Crée un calepinage sur un CLIENT (porte autonome du module).

    Raises:
        CreationRefusee: client absent ou d'une autre société — rien n'est
            créé.
    """
    from apps.crm.selectors import get_company_client

    from ..models import Calepinage

    _exiger_societe(company)
    if not client_id:
        raise CreationRefusee(
            "Aucun client n'a été indiqué : choisissez le client dont vous "
            "concevez la toiture.", champ='client')

    client = get_company_client(company, client_id)
    if client is None:
        raise CreationRefusee(
            f"Client introuvable (#{client_id}).", champ='client')

    return Calepinage.objects.create(
        company=company,
        client_id=client.pk,
        titre=titre or _titre_depuis(getattr(client, 'nom', '')),
        cree_par=user,
    )


def _titre_depuis(nom):
    """« Calepinage <nom> » — dérivé de la donnée, jamais d'un nom figé."""
    nom = (nom or '').strip()
    return f'Calepinage {nom}'.strip() if nom else ''
