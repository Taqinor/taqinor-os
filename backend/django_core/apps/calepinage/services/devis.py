"""CAL24/CAL25 — le pont calepinage → devis, SANS doubler le chemin canonique.

Ce module n'écrit AUCUNE ligne de devis et ne produit AUCUN PDF (règle #4 : le
moteur de devis ne fait que rendre). Il appelle les services VENTES qui font
déjà ce travail, et il rattache le devis au calepinage :

* ``apps.ventes.services.build_devis_from_layout`` — la création (composition,
  études, référence anti-collision) ;
* ``apps.ventes.services.sync_devis_from_layout`` — la resynchronisation
  CHIRURGICALE (prix négociés, remises, sections et notes PRÉSERVÉS) ;
* ``apps.ventes.selectors.devis_brouillon_pour_layout`` — la dédup QJ17
  (``lead`` + ``layout_hash``) ;
* ``services.liens.lier_devis`` — le rattachement, côté calepinage.

LES REFUS DU SERVEUR VENTES SE PROPAGENT TELS QUELS. Un pré-vol de composition
qui rend 422 garde SES messages, et un devis émis qui rend 409 garde son
``revision_possible`` — ni traduits, ni adoucis, ni renumérotés. Deux façons de
dire le même refus, c'est un utilisateur qui apprend deux règles différentes
pour un seul comportement.
"""
from __future__ import annotations


class DevisRefuse(ValueError):
    """Refus métier, avec le statut HTTP que la vue doit rendre TEL QUEL."""

    def __init__(self, message, *, champ='', statut=400, donnees=None):
        super().__init__(message)
        self.champ = champ
        self.statut = statut
        #: La charge utile du serveur ventes, à propager MOT POUR MOT.
        self.donnees = donnees or {}


def _exiger_layout(calepinage):
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise DevisRefuse("Ce calepinage n'est pas enregistré.",
                          champ='calepinage')
    layout = getattr(calepinage, 'roof_layout', None)
    if not isinstance(layout, dict) or not layout:
        raise DevisRefuse(
            "Dessinez d'abord la toiture : sans conception, il n'y a rien à "
            "chiffrer.", champ='roof_layout')
    return layout


def _lead_et_client(calepinage):
    """Le lead ET le client du calepinage, résolus CÔTÉ SERVEUR.

    Jamais lus d'un corps de requête : ce sont ceux que le calepinage porte.
    Les lectures crm passent par ``apps.crm.selectors``.
    """
    from apps.crm.selectors import get_company_client, get_company_lead

    company = getattr(calepinage, 'company', None)
    lead = get_company_lead(company, getattr(calepinage, 'lead_id', None))
    client = get_company_client(company, getattr(calepinage, 'client_id',
                                                 None))
    if lead is None and client is None:
        raise DevisRefuse(
            "Ce calepinage n'est rattaché ni à un lead ni à un client : "
            "impossible de savoir pour qui chiffrer.", champ='client')
    return lead, client


def generer_devis(calepinage, *, user=None, taux_tva=None,
                  remise_globale=None):
    """CAL24 — crée (ou RETROUVE) le devis de ce calepinage.

    Returns:
        ``(devis, cree)`` — ``cree`` est ``False`` quand la dédup a rendu le
        brouillon EXISTANT : un second clic ne fabrique pas un doublon.

    Raises:
        DevisRefuse: conception absente, rattachement manquant, ou pré-vol de
            composition en échec (statut 422, messages du serveur ventes
            propagés MOT POUR MOT).
    """
    from decimal import Decimal

    from apps.ventes.selectors import devis_brouillon_pour_layout
    from apps.ventes.services import (
        build_devis_from_layout, layout_hash, poser_layout_hash,
        validate_composition_for_layout,
    )

    from .liens import lier_devis

    layout = _exiger_layout(calepinage)
    company = calepinage.company
    lead, client = _lead_et_client(calepinage)

    # Pré-vol de composition : le catalogue peut-il servir ce toit ? Le refus
    # est celui du serveur ventes, mot pour mot (422).
    erreurs = validate_composition_for_layout(layout, company)
    if erreurs:
        raise DevisRefuse(erreurs[0], champ='composition', statut=422,
                          donnees={'detail': erreurs[0], 'errors': erreurs})

    empreinte = calepinage.layout_hash or layout_hash(layout)
    if lead is not None:
        deja = devis_brouillon_pour_layout(company, lead.pk, empreinte)
        if deja is not None:
            lier_devis(calepinage, deja.pk, user=user)
            return deja, False

    devis = build_devis_from_layout(
        layout=layout, user=user, company=company, lead=lead, client=client,
        **_montants(taux_tva, remise_globale, Decimal))
    # Le devis porte la MÊME empreinte que le calepinage : c'est ce qui rend
    # la dédup possible au clic suivant, et le badge « à jour » honnête.
    poser_layout_hash(devis, empreinte)
    lier_devis(calepinage, devis.pk, user=user)
    return devis, True


def _montants(taux_tva, remise_globale, Decimal):
    """Les deux montants optionnels — absents, on laisse les DÉFAUTS ventes.

    On ne réinvente pas un taux de TVA ni une remise « par défaut » ici : ce
    que l'appelant ne dit pas, le service ventes le décide comme il le décide
    pour tous ses autres appelants.
    """
    montants = {}
    for cle, brut in (('taux_tva', taux_tva),
                      ('remise_globale', remise_globale)):
        if brut in (None, ''):
            continue
        try:
            montants[cle] = Decimal(str(brut))
        except Exception as erreur:  # noqa: BLE001 — refus NOMMÉ, jamais un 500
            raise DevisRefuse(f"Valeur invalide pour « {cle} » : {brut!r}.",
                              champ=cle) from erreur
    return montants


def resynchroniser_devis(calepinage, *, user=None):
    """CAL25 — resynchronise le devis lié sur la conception COURANTE.

    Le service ventes fait le travail chirurgical (quantités, batterie,
    onduleur accordé au scénario) et PRÉSERVE prix négociés, remises, sections
    et notes. Son 409 sur un devis émis — avec ``revision_possible`` — remonte
    TEL QUEL : le bon geste est « Réviser », et l'écran doit lire exactement ce
    que dit la porte d'écriture.

    Returns:
        Le dictionnaire du service ventes (``inchange``, ``lignes_ajoutees``,
        ``avertissements``…), inchangé.

    Raises:
        DevisRefuse: aucun devis lié (400, le message NOMME le geste
            « Générer le devis »), ou refus 409 du serveur ventes propagé.
    """
    from apps.ventes.selectors import get_devis_by_pk
    from apps.ventes.services import SyncLayoutError, sync_devis_from_layout

    layout = _exiger_layout(calepinage)
    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id:
        raise DevisRefuse(
            "Aucun devis n'est rattaché à ce calepinage : utilisez d'abord "
            "« Générer le devis ».", champ='devis')
    devis = get_devis_by_pk(devis_id)
    company = getattr(calepinage, 'company', None)
    if devis is None or (company is not None
                         and devis.company_id != company.pk):
        raise DevisRefuse(f"Devis introuvable (#{devis_id}).", champ='devis')

    try:
        return sync_devis_from_layout(devis, layout, user)
    except SyncLayoutError as refus:
        raise DevisRefuse(
            refus.detail, champ='devis', statut=409,
            donnees={'detail': refus.detail,
                     'revision_possible': refus.revision_possible}) from refus
