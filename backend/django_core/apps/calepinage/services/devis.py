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

    layout = _exiger_layout(calepinage)
    company = calepinage.company
    lead, client = _lead_et_client(calepinage)
    # ACAL277 — les montants sont VALIDÉS avant toute écriture (y compris le
    # rattachement d'un brouillon existant) : un refus n'écrit rien.
    montants = _montants(taux_tva, remise_globale, Decimal)

    # Pré-vol de composition : le catalogue peut-il servir ce toit ? Le refus
    # est celui du serveur ventes, mot pour mot (422).
    erreurs = validate_composition_for_layout(layout, company)
    if erreurs:
        raise DevisRefuse(erreurs[0], champ='composition', statut=422,
                          donnees={'detail': erreurs[0], 'errors': erreurs})

    empreinte = calepinage.layout_hash or layout_hash(layout)
    lie = _devis_lie_actif(calepinage)
    if lie is not None:
        # ACAL33 — un calepinage lié à un devis ACTIF n'est jamais re-pointé :
        # le même brouillon à la même empreinte est rendu (dédup), tout autre
        # cas est un 409 NOMMÉ avant toute création (jamais un devis orphelin
        # ni un 500). ACAL89 affine ce refus.
        if (lie.statut == 'brouillon'
                and (lie.layout_hash or '') == (empreinte or '')):
            return lie, False
        raise DevisRefuse(
            f"Ce calepinage est déjà lié au devis "
            f"{lie.reference or f'#{lie.pk}'} : utilisez « Resynchroniser "
            "le devis ».", champ='devis', statut=409)
    if lead is not None:
        deja = devis_brouillon_pour_layout(company, lead.pk, empreinte)
        if deja is not None:
            _lier(calepinage, deja, user=user)
            return deja, False

    devis = build_devis_from_layout(
        layout=layout, user=user, company=company, lead=lead, client=client,
        **montants)
    # Le devis porte la MÊME empreinte que le calepinage : c'est ce qui rend
    # la dédup possible au clic suivant, et le badge « à jour » honnête.
    poser_layout_hash(devis, empreinte)
    _lier(calepinage, devis, user=user)
    return devis, True


def _devis_lie_actif(calepinage):
    """ACAL33 — le devis lié s'il est ACTIF (même société), sinon ``None``."""
    from apps.ventes.selectors import get_devis_by_pk

    if not calepinage.devis_id:
        return None
    lie = get_devis_by_pk(calepinage.devis_id)
    if (lie is None or lie.company_id != calepinage.company_id
            or not getattr(lie, 'is_active', True)):
        return None
    return lie


def _lier(calepinage, devis, *, user=None):
    """``lier_devis`` dont le refus devient un 409 NOMMÉ (jamais un 500)."""
    from .liens import LiaisonRefusee, lier_devis

    try:
        lier_devis(calepinage, devis.pk, user=user)
    except LiaisonRefusee as refus:
        raise DevisRefuse(str(refus), champ='devis', statut=409) from None


def _montants(taux_tva, remise_globale, Decimal):
    """Les deux montants optionnels — absents, on laisse les DÉFAUTS ventes.

    On ne réinvente pas un taux de TVA ni une remise « par défaut » ici : ce
    que l'appelant ne dit pas, le service ventes le décide comme il le décide
    pour tous ses autres appelants.
    """
    from .valeurs import nombre_fini

    montants = {}
    for cle, libelle, brut in (('taux_tva', 'Taux de TVA', taux_tva),
                               ('remise_globale', 'Remise globale',
                                remise_globale)):
        if brut in (None, ''):
            continue
        # ACAL277 — un pourcentage FINI dans [0, 100], deux décimales au
        # plus : « NaN », « 123456 », « 150 » ou « -5 » sont refusés en
        # nommant le champ, jamais un 500 ni un devis aberrant.
        nombre_fini(brut, cle, libelle=libelle, mini=0, maxi=100,
                    decimales=2, erreur=DevisRefuse)
        montants[cle] = Decimal(str(brut))
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
