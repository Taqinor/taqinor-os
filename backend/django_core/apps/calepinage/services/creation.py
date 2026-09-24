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

from .journal import journaliser_creation


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


def obtenir_ou_creer_pour_devis(devis_id, company, *, user=None, titre='',
                                preset_id=None):
    """Le calepinage de ce devis — le même à chaque appel (IDEMPOTENT).

    CALX351 — ``preset_id`` (optionnel) désigne un jeu de réglages société
    (``services/presets.py``) appliqué aux pans du document de DÉPART, à la
    création seulement : un calepinage déjà existant n'est jamais retouché.
    Absent ⇒ comportement d'aujourd'hui, strictement identique.

    Returns:
        ``(calepinage, cree)`` — ``cree`` vaut ``True`` seulement au premier
        appel.

    Raises:
        CreationRefusee: devis absent, ou appartenant à une AUTRE société
            (rien n'est créé, et l'appelant n'apprend rien de son existence) ;
            jeu de réglages inconnu (``preset_id``).
    """
    from django.db import transaction

    from apps.ventes.selectors import get_devis_by_pk

    from ..models import Calepinage
    from ..selectors import calepinage_du_devis

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
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

    roof_layout = getattr(devis, 'roof_layout', None)
    empreinte = getattr(devis, 'layout_hash', None) or ''
    regles = 0
    if jeu is not None:
        roof_layout, regles = _layout_regle(roof_layout, jeu)
        if regles:
            from apps.ventes.services import layout_hash

            empreinte = layout_hash(roof_layout) or ''

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
            roof_layout=roof_layout,
            layout_hash=empreinte,
            roof_image=getattr(devis, 'roof_image', None) or '',
            cree_par=user,
        )
    # CAL26 — la première ligne du chatter, par la primitive `records`.
    journaliser_creation(calepinage, user=user)
    _noter_jeu(calepinage, jeu, regles, user=user)
    return calepinage, True


def _titre_du_devis(devis):
    """Un titre lisible, dérivé du devis — jamais un prénom codé en dur."""
    reference = (getattr(devis, 'reference', '') or '').strip()
    return f'Calepinage {reference}'.strip() if reference else ''


def creer_pour_lead(lead_id, company, *, user=None, titre='',
                    preset_id=None):
    """Crée un calepinage sur un LEAD (porte autonome du module).

    CALX351 — ``preset_id`` : voir ``obtenir_ou_creer_pour_devis``. Un
    calepinage neuf n'a encore aucun pan : le jeu est VALIDÉ et son choix
    noté au chatter, rien n'est inventé dans un document vide.

    Raises:
        CreationRefusee: lead absent ou d'une autre société — rien n'est
            créé ; jeu de réglages inconnu (``preset_id``).
    """
    from apps.crm.selectors import get_company_lead

    from ..models import Calepinage

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    if not lead_id:
        raise CreationRefusee(
            "Aucun lead n'a été indiqué : choisissez le lead dont vous "
            "concevez la toiture.", champ='lead')

    lead = get_company_lead(company, lead_id)
    if lead is None:
        raise CreationRefusee(
            f"Lead introuvable (#{lead_id}).", champ='lead')

    calepinage = Calepinage.objects.create(
        company=company,
        lead_id=lead.pk,
        client_id=getattr(lead, 'client_id', None),
        titre=titre or _titre_depuis(getattr(lead, 'nom', '')),
        cree_par=user,
    )
    journaliser_creation(calepinage, user=user)  # CAL26
    _noter_jeu(calepinage, jeu, 0, user=user)
    return calepinage


def creer_pour_client(client_id, company, *, user=None, titre='',
                      preset_id=None):
    """Crée un calepinage sur un CLIENT (porte autonome du module).

    CALX351 — ``preset_id`` : voir ``creer_pour_lead``.

    Raises:
        CreationRefusee: client absent ou d'une autre société — rien n'est
            créé ; jeu de réglages inconnu (``preset_id``).
    """
    from apps.crm.selectors import get_company_client

    from ..models import Calepinage

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    if not client_id:
        raise CreationRefusee(
            "Aucun client n'a été indiqué : choisissez le client dont vous "
            "concevez la toiture.", champ='client')

    client = get_company_client(company, client_id)
    if client is None:
        raise CreationRefusee(
            f"Client introuvable (#{client_id}).", champ='client')

    calepinage = Calepinage.objects.create(
        company=company,
        client_id=client.pk,
        titre=titre or _titre_depuis(getattr(client, 'nom', '')),
        cree_par=user,
    )
    journaliser_creation(calepinage, user=user)  # CAL26
    _noter_jeu(calepinage, jeu, 0, user=user)
    return calepinage


def _titre_depuis(nom):
    """« Calepinage <nom> » — dérivé de la donnée, jamais d'un nom figé."""
    nom = (nom or '').strip()
    return f'Calepinage {nom}'.strip() if nom else ''


# ── CALX351 — partir d'un MODÈLE et d'un JEU DE RÉGLAGES société ────────────
#
# Les trois portes ci-dessus acceptent un ``preset_id`` optionnel : un jeu
# MAISON de la section ``presets`` (``services/presets.py``, CAL197), appliqué
# aux pans du document de départ par ``services/gabarits.py::
# appliquer_gabarit`` — le SEUL applicateur de réglages de pose du module :
# il ne touche que les clés de pan déjà définies par le contrat v2 (type de
# toit, pente, azimut…) et JAMAIS la géométrie. ``preset_id`` absent ⇒ AUCUNE
# lecture de réglage, création strictement identique à aujourd'hui (D12).

def _jeu_de_reglages(company, preset_id):
    """Le jeu MAISON ``preset_id`` de la société, ``None`` s'il n'est pas
    demandé — refus nommant ``preset_id`` s'il est inconnu."""
    if preset_id in (None, ''):
        return None
    from .presets import jeux_de_societe

    demande = str(preset_id).strip()
    for jeu in jeux_de_societe(company):
        if isinstance(jeu, dict) and str(jeu.get('id') or '') == demande:
            return jeu
    raise CreationRefusee(
        f"Jeu de réglages inconnu : « {demande} » — choisissez l'un des jeux "
        "enregistrés dans les réglages de la société.", champ='preset_id')


def _layout_regle(roof_layout, jeu):
    """``(copie du document, nombre de pans réglés)`` — l'original intact."""
    import copy

    from .gabarits import appliquer_gabarit

    if not isinstance(roof_layout, dict):
        return roof_layout, 0
    document = copy.deepcopy(roof_layout)
    zones = document.get('zones')
    if not isinstance(zones, list):
        return document, 0
    regles = 0
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        reglee, _regles_moteur = appliquer_gabarit(jeu, zone)
        if reglee != zone:
            regles += 1
        zones[rang] = reglee
    return document, regles


def _noter_jeu(calepinage, jeu, regles, *, user=None):
    """Le choix du jeu au chatter — rien quand aucun jeu n'est demandé."""
    if jeu is None:
        return
    from .journal import noter

    nom = str(jeu.get('nom') or jeu.get('id') or '').strip()
    if regles:
        texte = (f"Jeu de réglages « {nom} » appliqué à {regles} pan(s) du "
                 "document de départ.")
    else:
        texte = (f"Jeu de réglages « {nom} » retenu à la création : aucun pan "
                 "du document de départ n'en a été modifié.")
    noter(calepinage, texte, user=user)


def demarrer_depuis_modele(modele, company, *, user=None, lead_id=None,
                           client_id=None, devis_id=None, titre='',
                           preset_id=None):
    """CALX351 — un calepinage NEUF depuis un MODÈLE, sur un lead, un client
    OU un devis, avec un jeu de réglages optionnel.

    La copie reste le service UNIQUE ``services.modeles.creer_depuis_modele``
    (qui appelle ``services.variantes.dupliquer``, CAL14) : aucun troisième
    chemin de copie. Un ``devis_id`` rattache la copie à ce devis (son lead et
    son client en sont repris) ; rien n'est écrit si le devis, le jeu ou le
    rattachement est refusé.

    Raises:
        CreationRefusee: jeu inconnu (``preset_id``), devis introuvable
            (``devis_id``).
        services.modeles.ModeleInvalide: modèle non marqué, rattachement
            absent ou étranger (champ nommé par le service).
    """
    from apps.ventes.selectors import get_devis_by_pk

    from .modeles import creer_depuis_modele

    _exiger_societe(company)
    jeu = _jeu_de_reglages(company, preset_id)
    devis = None
    if devis_id:
        devis = get_devis_by_pk(devis_id)
        if devis is None or devis.company_id != company.pk:
            raise CreationRefusee(f"Devis introuvable (#{devis_id}).",
                                  champ='devis_id')
        lead_id = getattr(devis, 'lead_id', None) or lead_id
        client_id = getattr(devis, 'client_id', None) or client_id

    copie = creer_depuis_modele(modele, user=user, lead_id=lead_id,
                                client_id=client_id, titre=titre)
    champs = []
    if devis is not None:
        copie.devis = devis
        champs.append('devis')
    regles = 0
    if jeu is not None:
        document, regles = _layout_regle(copie.roof_layout, jeu)
        if regles:
            from apps.ventes.services import layout_hash

            copie.roof_layout = document
            copie.layout_hash = layout_hash(document) or ''
            champs += ['roof_layout', 'layout_hash']
    if champs:
        copie.save(update_fields=champs + ['updated_at'])
    _noter_jeu(copie, jeu, regles, user=user)
    return copie
