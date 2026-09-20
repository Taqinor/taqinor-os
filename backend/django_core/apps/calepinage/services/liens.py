"""CAL12 — rattacher APRÈS COUP un calepinage à un devis ou à une affaire.

Un calepinage né sans devis (porte autonome) doit pouvoir être rattaché plus
tard, et une affaire d'appel d'offres doit pouvoir pointer SON calepinage.

LES DEUX REFUS QUI COMPTENT
---------------------------
* **Le double rattachement.** Si le devis (ou l'affaire) est DÉJÀ lié à un
  AUTRE calepinage, on refuse — et le message NOMME le calepinage déjà lié :
  sans son nom, l'utilisateur ne peut rien faire du refus.
* **L'autre société.** Un devis ou une affaire d'une autre société est
  INTROUVABLE : on ne confirme jamais l'existence de la donnée d'autrui.

CE QUE CE MODULE NE FAIT JAMAIS
-------------------------------
Il n'écrit AUCUN statut de devis (règle #4 : le moteur de devis ne fait que
RENDRE), et il n'importe aucun modèle de ``ventes`` ni de ``ao`` — le devis
passe par ``apps.ventes.selectors``, l'affaire par ``apps.ao.selectors``.
Rattacher au MÊME devis est une opération NEUTRE (idempotente) : ré-envoyer
la demande ne doit pas produire une erreur.
"""
from __future__ import annotations


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

    if calepinage.devis_id and int(calepinage.devis_id) == int(devis_id):
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
    return calepinage


def lier_appel_offre(calepinage, appel_offre_id, *, user=None):
    """Rattache ``calepinage`` à l'affaire d'appel d'offres ``appel_offre_id``.

    Raises:
        LiaisonRefusee: affaire introuvable/d'une autre société, ou déjà liée
            à un AUTRE calepinage (le message le nomme).
    """
    from django.db import transaction

    from apps.ao.selectors import issues_par_ids

    from ..selectors import calepinage_de_l_affaire

    company = _exiger_calepinage(calepinage)
    if not appel_offre_id:
        raise LiaisonRefusee(
            "Aucune affaire n'a été indiquée : choisissez l'appel d'offres "
            "auquel rattacher ce calepinage.", champ='appel_offre')

    try:
        cle = int(appel_offre_id)
    except (TypeError, ValueError):
        raise LiaisonRefusee(
            f"Appel d'offres introuvable (#{appel_offre_id}).",
            champ='appel_offre')

    if calepinage.appel_offre_id and int(calepinage.appel_offre_id) == cle:
        return calepinage  # neutre : le lien demandé existe déjà.

    # Lecture cross-app par le SEUL sélecteur AO : une affaire d'une autre
    # société est simplement ABSENTE du résultat (on n'apprend rien d'elle).
    if cle not in issues_par_ids(company, [cle]):
        raise LiaisonRefusee(
            f"Appel d'offres introuvable (#{cle}).", champ='appel_offre')

    with transaction.atomic():
        deja = calepinage_de_l_affaire(cle, company)
        if deja is not None and deja.pk != calepinage.pk:
            raise LiaisonRefusee(
                f"L'appel d'offres #{cle} est déjà rattaché au calepinage "
                f"{_etiquette(deja)} : détachez-le d'abord, ou rattachez "
                "cette affaire à un autre calepinage.",
                champ='appel_offre')
        calepinage.appel_offre_id = cle
        calepinage.save(update_fields=['appel_offre_id', 'updated_at'])
    return calepinage


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
