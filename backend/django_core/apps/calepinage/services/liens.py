"""CAL12 — rattacher APRÈS COUP un calepinage à un devis.

Un calepinage né sans devis (porte autonome) doit pouvoir être rattaché plus
tard.

LES DEUX REFUS QUI COMPTENT
---------------------------
* **Le double rattachement.** Si le devis est DÉJÀ lié à un AUTRE calepinage,
  on refuse — et le message NOMME le calepinage déjà lié : sans son nom,
  l'utilisateur ne peut rien faire du refus.
* **L'autre société.** Un devis d'une autre société est INTROUVABLE : on ne
  confirme jamais l'existence de la donnée d'autrui.

SOLMVP15 — ``lier_appel_offre`` vivait ici. C'était un PONT, et seulement un
pont : rattacher un calepinage à une affaire d'appel d'offres, en validant
l'existence de cette affaire chez l'autre app. Cette app sort du produit : il
n'y a plus d'affaire à rattacher, donc plus de pont. Le rattachement au DEVIS
— la voie du produit — est intact, au champ près.

CE QUE CE MODULE NE FAIT JAMAIS
-------------------------------
Il n'écrit AUCUN statut de devis (règle #4 : le moteur de devis ne fait que
RENDRE), et il n'importe aucun modèle de ``ventes`` — le devis passe par
``apps.ventes.selectors``. Rattacher au MÊME devis est une opération NEUTRE
(idempotente) : ré-envoyer la demande ne doit pas produire une erreur.
"""
from __future__ import annotations

from .journal import journaliser_lien_devis


class LiaisonRefusee(ValueError):
    """Refus métier de rattachement, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _etiquette(calepinage):
    """Comment NOMMER un calepinage déjà lié, dans un message de refus."""
    titre = (getattr(calepinage, 'titre', '') or '').strip()
    return f'« {titre} » (#{calepinage.pk})' if titre else f'#{calepinage.pk}'


def lier_devis(calepinage, devis_id, *, user=None):
    """Rattache ``calepinage`` au devis ``devis_id``.

    Returns:
        Le calepinage rattaché (inchangé si le lien existait déjà).

    Raises:
        LiaisonRefusee: devis introuvable/d'une autre société, ou déjà lié à
            un AUTRE calepinage (le message le nomme).
    """
    from django.db import transaction

    from apps.ventes.selectors import get_devis_by_pk

    from ..selectors import calepinage_du_devis

    company = _exiger_calepinage(calepinage)
    if not devis_id:
        raise LiaisonRefusee(
            "Aucun devis n'a été indiqué : choisissez le devis auquel "
            "rattacher ce calepinage.", champ='devis')

    ancien_devis = calepinage.devis_id
    if ancien_devis and int(ancien_devis) == int(devis_id):
        return calepinage  # neutre : le lien demandé existe déjà.

    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        raise LiaisonRefusee(
            f"Devis introuvable (#{devis_id}).", champ='devis')

    with transaction.atomic():
        deja = calepinage_du_devis(devis_id, company)
        if deja is not None and deja.pk != calepinage.pk:
            raise LiaisonRefusee(
                f"Le devis {devis.reference or f'#{devis_id}'} est déjà "
                f"rattaché au calepinage {_etiquette(deja)} : détachez-le "
                "d'abord, ou rattachez ce devis à un autre calepinage.",
                champ='devis')
        calepinage.devis_id = devis.pk
        champs = ['devis']
        if not calepinage.client_id and getattr(devis, 'client_id', None):
            calepinage.client_id = devis.client_id
            champs.append('client')
        if not calepinage.lead_id and getattr(devis, 'lead_id', None):
            calepinage.lead_id = devis.lead_id
            champs.append('lead_id')
        calepinage.save(update_fields=champs + ['updated_at'])
    # CAL26 — ancien → nouveau, par la primitive `records`.
    journaliser_lien_devis(calepinage, ancien=ancien_devis,
                           nouveau=devis.pk, user=user)
    return calepinage


def transferer_lead(company, *, de_lead_id, vers_lead_id, user=None):
    """ACAL176 — les calepinages d'un lead ABSORBÉ suivent le survivant.

    Appelé par la fusion de leads (``apps.crm.services.merge_leads``,
    ACAL177) dans SA transaction : même patron direct que
    ``update_installation_lead`` — pas d'événement, tout ou rien.

    Pour TOUS les calepinages de ``de_lead_id`` dans ``company`` (archivés en
    corbeille compris — l'archive est logique, la ligne reste) :
      * ``lead_id`` devient ``vers_lead_id`` ;
      * ``client_id`` prend le client du survivant quand le calepinage n'en
        avait pas ou portait celui du lead absorbé (un client posé à la main,
        différent, n'est jamais écrasé ; un survivant sans client n'efface
        rien) ;
      * ``roof_layout``, ``layout_hash`` et ``statut`` ne sont PAS touchés
        (``update`` ciblé, aucun ``save()``) ;
      * UNE ligne de chatter par calepinage (``journal.noter``). Si le
        survivant avait déjà un calepinage OUVERT, les deux restent ouverts —
        jamais de fusion de dessins — et la ligne le dit.

    Un lead d'une AUTRE société (absorbé ou survivant) ne déplace rien : la
    lecture est bornée à ``company`` des deux côtés.

    Returns:
        La liste des identifiants de calepinages déplacés (vide si rien).
    """
    from django.db import transaction
    from django.db.models import Q

    from apps.crm.selectors import get_company_lead

    from ..models import Calepinage
    from ..selectors import liste_calepinages
    from .journal import noter

    if company is None or not de_lead_id or not vers_lead_id:
        return []
    if int(de_lead_id) == int(vers_lead_id):
        return []
    survivant = get_company_lead(company, vers_lead_id)
    if survivant is None:
        return []
    absorbe = get_company_lead(company, de_lead_id)
    client_survivant = getattr(survivant, 'client_id', None)
    client_absorbe = getattr(absorbe, 'client_id', None)

    with transaction.atomic():
        a_deplacer = Calepinage.objects.filter(
            company=company, lead_id=de_lead_id).order_by('pk')
        ids = list(a_deplacer.values_list('pk', flat=True))
        if not ids:
            return []
        deja_ouvert = (liste_calepinages(company, lead_id=vers_lead_id)
                       .exclude(pk__in=ids).order_by('-updated_at', '-pk')
                       .first())
        if client_survivant:
            cible = Q(client_id__isnull=True)
            if client_absorbe:
                cible |= Q(client_id=client_absorbe)
            Calepinage.objects.filter(company=company, pk__in=ids).filter(
                cible).update(client_id=client_survivant)
        Calepinage.objects.filter(company=company, pk__in=ids).update(
            lead_id=vers_lead_id)

        ligne = (f'Rattaché au lead #{vers_lead_id} '
                 f'(fusion avec #{de_lead_id}).')
        if deja_ouvert is not None:
            ligne = (f'{ligne} Le lead #{vers_lead_id} avait déjà un '
                     f'calepinage ouvert ({_etiquette(deja_ouvert)}) : les '
                     'deux restent ouverts, aucun dessin n\'est fusionné.')
        for calepinage in Calepinage.objects.filter(pk__in=ids):
            noter(calepinage, ligne, user=user)
    return ids


def _exiger_calepinage(calepinage):
    """Le calepinage existe et porte une société — sinon, refus explicite."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise LiaisonRefusee(
            "Le calepinage à rattacher n'est pas encore enregistré.",
            champ='calepinage')
    company = getattr(calepinage, 'company', None)
    if company is None:
        raise LiaisonRefusee(
            "Ce calepinage n'a pas de société : impossible de vérifier le "
            "rattachement.", champ='company')
    return company
