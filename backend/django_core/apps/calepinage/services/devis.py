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

import logging

logger = logging.getLogger(__name__)


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


def _layout_des_surfaces(layout, cles):
    """ACAL968 (D-ACAL-37) — la COPIE du document limitée aux surfaces
    COCHÉES (``cles`` de ``surfaces_chiffrables``) ; ``None`` ou tout coché ⇒
    le document lui-même. Vide, non-liste ou clé inconnue ⇒ 400 nommant
    ``surfaces_chiffrees``. Une zone retirée retire aussi le ``result``
    racine ; la sélection est écrite dans ``choixConception.surfacesChiffrees``."""
    import copy

    from ..serializers import surfaces_chiffrables

    if cles is None:
        return layout
    surfaces = surfaces_chiffrables(layout)
    connues = [s['cle'] for s in surfaces]
    if (not isinstance(cles, list) or not cles
            or any(not isinstance(c, str) or c not in connues for c in cles)):
        message = ("Cochez au moins une surface du calepinage parmi : %s."
                   % (', '.join(s['libelle'] for s in surfaces) or 'aucune surface posée'))
        raise DevisRefuse(message, champ='surfaces_chiffrees',
                          donnees={'surfaces_chiffrees': [message]})
    if set(cles) == set(connues):
        return layout
    copie = copy.deepcopy(layout)
    cle_zones = next((k for k in ('zones', 'areas', 'pans') if copie.get(k)), None)
    for cle_liste, prefixe in ((cle_zones, 'zone'), ('poseSurfaces', 'surface')):
        if not cle_liste or not isinstance(copie.get(cle_liste), list):
            continue
        gardees = []
        for index, element in enumerate(copie[cle_liste]):
            cle = (str(element.get('id') or '%s-%d' % (prefixe, index + 1))
                   if isinstance(element, dict) else None)
            if cle in connues and cle not in cles:
                if prefixe == 'zone':
                    copie.pop('result', None)
                continue
            if isinstance(element, dict) and not element.get('id'):
                element['id'] = cle  # la clé reste stable après retrait
            gardees.append(element)
        copie[cle_liste] = gardees
    choix = copie.get('choixConception')
    copie['choixConception'] = {**(choix if isinstance(choix, dict) else {}),
                                'surfacesChiffrees': list(cles)}
    return copie


def _selection_du_devis(devis):
    """ACAL968 — la sélection écrite au devis (``roof_layout``), ou ``None``."""
    document = getattr(devis, 'roof_layout', None)
    choix = document.get('choixConception') if isinstance(document, dict) else None
    return choix.get('surfacesChiffrees') if isinstance(choix, dict) else None


def _lead_et_client(calepinage):
    """Le lead ET le client du calepinage, résolus CÔTÉ SERVEUR.

    Jamais lus d'un corps de requête : ce sont ceux que le calepinage porte.
    Les lectures crm passent par ``apps.crm.selectors``.
    """
    from apps.crm.selectors import get_company_client, get_company_lead

    company = getattr(calepinage, 'company', None)
    lead = get_company_lead(company, getattr(calepinage, 'lead_id', None),
                            avec_corbeille=True)
    if lead is not None and getattr(lead, 'is_deleted', False):
        # ACAL178 — un lead à la corbeille n'est PAS « jamais rattaché » :
        # refus nommé, aucun devis créé.
        nom = ' '.join(p for p in [getattr(lead, 'nom', ''),
                                   getattr(lead, 'prenom', '') or '']
                       if p).strip() or f'Lead #{lead.pk}'
        raise DevisRefuse(
            f"Le lead #{lead.pk} « {nom} » est à la corbeille : restaurez-le "
            "avant de générer le devis.", champ='lead')
    client = get_company_client(company, getattr(calepinage, 'client_id',
                                                 None))
    if lead is None and client is None:
        raise DevisRefuse(
            "Ce calepinage n'est rattaché ni à un lead ni à un client : "
            "impossible de savoir pour qui chiffrer.", champ='client')
    return lead, client


def _refuser_lead_agricole(lead):
    """ACAL89 — 422 ``{type_installation}`` pour un lead agricole ; ACON90 :
    le message est LA constante du constructeur partagé (ventes)."""
    if lead is not None and getattr(lead, 'type_installation', '') == 'agricole':
        from apps.ventes.services import MESSAGE_LEAD_AGRICOLE

        raise DevisRefuse(MESSAGE_LEAD_AGRICOLE, champ='type_installation',
                          statut=422)


def _refuser_autre_marche(devis, lead):
    """ACON90 (D-ACON-1) — 409 ``{devis}`` : la dédup ne rend jamais un
    brouillon d'un autre marché que celui du lead."""
    from apps.ventes.selectors_calepinage import refus_marche_du_brouillon

    motif = refus_marche_du_brouillon(devis, lead)
    if motif:
        raise DevisRefuse(motif, champ='devis', statut=409)


def _refus_deja_rattache(lie):
    """ACAL89 — 409 NOMMÉ ``{detail, devis, reference, revision_possible}``.

    Le calepinage est déjà lié à un devis qu'on ne peut pas réutiliser
    (brouillon d'une autre empreinte, ou devis non brouillon) : aucun devis
    n'est créé et ``calepinage.devis`` ne bouge pas. ``revision_possible`` est
    LU sur ventes (``devis_modifiabilite``), jamais recalculé ici.
    """
    from apps.ventes.selectors import devis_modifiabilite

    reference = lie.reference or f'#{lie.pk}'
    try:
        libelle_statut = lie.get_statut_display()
    except Exception:  # un libellé manquant n'empêche pas le refus
        logger.warning("refus deja rattache : échec ignoré, comportement dégradé", exc_info=True)
        libelle_statut = lie.statut
    message = (f"Ce calepinage est déjà rattaché au devis {reference} "
               f"({libelle_statut}) : utilisez « Resynchroniser le devis ».")
    try:
        revision_possible = bool(
            devis_modifiabilite(lie).get('revision_possible'))
    except Exception:  # verdict illisible : jamais un 500
        logger.warning("refus deja rattache : échec ignoré, comportement dégradé", exc_info=True)
        revision_possible = False
    return DevisRefuse(message, champ='devis', statut=409, donnees={
        'detail': message, 'devis': lie.pk, 'reference': lie.reference,
        'revision_possible': revision_possible,
    })


def _brouillon_reutilisable(company, lead, empreinte, calepinage):
    """ACAL89 — le brouillon de même empreinte, SEULEMENT s'il n'est lié à
    aucun AUTRE calepinage (la copie d'un calepinage ne vole jamais le devis
    de l'original — c'était le 500 de la porte PUB-10)."""
    from apps.ventes.selectors import devis_brouillon_pour_layout

    from ..selectors import calepinage_du_devis

    deja = devis_brouillon_pour_layout(company, lead.pk, empreinte)
    if deja is None:
        return None
    proprietaire = calepinage_du_devis(deja.pk, company)
    if proprietaire is not None and proprietaire.pk != calepinage.pk:
        return None
    return deja


def generer_devis(calepinage, *, user=None, taux_tva=None,
                  remise_globale=None, journal=None,
                  derogation_electrique=None, surfaces_chiffrees=None):
    """CAL24 — crée (ou RETROUVE) le devis de ce calepinage.

    ACAL968 — ``surfaces_chiffrees`` : les clés des surfaces COCHÉES
    (``None`` = toutes) ; le devis compose la copie sans les décochées.

    Args:
        journal: ACAL89 — dict facultatif rempli SUR PLACE avec ce que la
            composition n'a pas pu faire (``avertissements``,
            ``marques_manquantes``, canal U3 de ``build_devis_from_layout``) ;
            vide (listes vides) quand un brouillon existant est rendu.
            ACAL170 — y reçoit aussi ``electrique`` (verdict, manquantes,
            dérogation consignée).
        derogation_electrique: ACAL170 — ``{motif}`` qui lève un verdict
            électrique BLOQUANT (droit vérifié par la vue) ; consignée au
            fil ``journal_derogations`` et au chatter une fois le devis rendu.

    Returns:
        ``(devis, cree)`` — ``cree`` est ``False`` quand la dédup a rendu le
        brouillon EXISTANT : un second clic ne fabrique pas un doublon.

    Raises:
        DevisRefuse: conception absente, rattachement manquant, lead agricole
            (422 ``type_installation``), calepinage déjà rattaché à un devis
            non réutilisable (409 nommé), ou pré-vol de composition en échec
            (statut 422, messages du serveur ventes propagés MOT POUR MOT) ;
            ACAL170 — verdict électrique bloquant sans dérogation (422
            ``electrique``), dérogation sans motif (400).
    """
    from decimal import Decimal

    if journal is not None:
        journal.setdefault('avertissements', [])
        journal.setdefault('marques_manquantes', [])
    # ACAL116 (D-ACAL-24) — feu vert / approbation à jour AVANT toute
    # écriture ; no-op quand la société n'exige rien.
    from .feu_vert import GESTE_DEVIS, verifier_avant_publication

    verifier_avant_publication(calepinage, geste=GESTE_DEVIS)
    layout = _layout_des_surfaces(_exiger_layout(calepinage), surfaces_chiffrees)
    company = calepinage.company
    lead, client = _lead_et_client(calepinage)
    _refuser_lead_agricole(lead)
    # ACAL277 — les montants sont VALIDÉS avant toute écriture (y compris le
    # rattachement d'un brouillon existant) : un refus n'écrit rien.
    montants = _montants(taux_tva, remise_globale, Decimal)
    # ACAL170 (D-ACAL-9) — le verdict électrique BLOQUANT refuse AVANT toute
    # écriture (422 nommant les bloquants) ; l'indéterminé passe.
    garde = _garde_electrique(calepinage, derogation_electrique, user,
                              geste='généré')
    devis, cree = _generer(calepinage, layout, company, lead, client,
                           montants, user=user, journal=journal)
    servi = _consigner_et_servir(calepinage, garde, user=user)
    if journal is not None:
        journal['electrique'] = servi
        # ACON28 — une conception REFUSÉE à l'approbation se DIT au devis.
        from .approbation import avertissement_refus

        refus = avertissement_refus(calepinage)
        if refus:
            journal['avertissements'] = [*journal.get('avertissements', ()),
                                         refus]
        # ACAL426 — pentes / faces jamais confirmées : dites, jamais bloquées.
        from .hypotheses_toit import avertissements_hypotheses

        journal['avertissements'] = [
            *journal.get('avertissements', ()),
            *avertissements_hypotheses(layout)]
    return devis, cree


def _garde_kwh_declare(devis):
    """ADVS26 — même refus qu'``/atomic`` : un kWh déclaré que les factures
    contredisent annule la création (409 ``{detail, code}``, sous sa
    transaction)."""
    from apps.ventes.selectors_calepinage import refus_kwh_declare_du_devis

    refus = refus_kwh_declare_du_devis(devis)
    if refus is not None:
        raise DevisRefuse(refus['detail'], champ='conso_mensuelle_kwh',
                          statut=409, donnees=refus)


def taille_non_dimensionnee(calepinage):
    """ACAL861/ACAL922 — LA condition « rien ne dimensionne ce devis », écrite
    UNE fois (le contrôle « prêt à envoyer ? » la lit ; la porte 409 d'ACAL922
    la lira) : sans lead, ou lead résidentiel sans ``taille_souhaitee_kwc``
    dont ``cible_depuis_lead`` refuse faute de facture (``motif_code`` =
    ``MOTIF_FACTURE_ABSENTE``). Rend ``{'refus': texte}`` ou ``None``
    (dimensionné, ou refusé pour une AUTRE raison : C&I, agricole, kWh
    incohérent ne posent pas cette question). Lecture seule."""
    from apps.crm.selectors import get_company_lead
    from apps.ventes.selectors import cible_depuis_lead
    from apps.ventes.services import MOTIF_FACTURE_ABSENTE

    company = getattr(calepinage, 'company', None)
    if not getattr(calepinage, 'lead_id', None):
        return {'refus': "Calepinage sans lead : aucune facture ne "
                         "dimensionne le système."}
    lead = get_company_lead(company, calepinage.lead_id, avec_corbeille=True)
    cible = cible_depuis_lead(lead, company) if lead is not None else None
    if cible and cible.get('motif_code') == MOTIF_FACTURE_ABSENTE:
        return {'refus': cible.get('refus') or ''}
    return None


#: ACAL914 — l'écart d'ÉGALITÉ entre kWc dessiné et kWc composé : l'arrondi
#: d'écriture de ``etude_params['puissance_kwc']`` (trois décimales), pas un
#: seuil métier.
EPSILON_KWC_COMPOSE = 0.001


def _garde_module_substitue(devis, layout):
    """ACAL914 — 409 ``module_substitue`` quand la composition chiffre un
    autre module que le dessin (kWc composé ≠ kWc dessiné), sous la
    transaction de la création (devis annulé)."""
    from core.electrique.types import fr

    from apps.ventes.selectors_calepinage import lignes_produits_calepinage
    from apps.ventes.services import pans_du_document

    dessine = sum(p['kwc'] for p in pans_du_document(layout) if p.get('kwc'))
    compose = (getattr(devis, 'etude_params', None) or {}).get('puissance_kwc')
    if not dessine or compose is None:
        return
    if abs(float(compose) - dessine) <= EPSILON_KWC_COMPOSE + 1e-9:
        return
    panneau = next((ligne['designation'] for ligne in
                    lignes_produits_calepinage(devis)
                    if 'panneau' in (ligne['designation'] or '').lower()), '')
    detail = ("Le dessin porte %s kWc ; le catalogue compose %s kWc%s. "
              "Choisissez le module du catalogue dans l'atelier puis "
              "relancez." % (fr(dessine, 2), fr(float(compose), 2),
                             ' (%s)' % panneau if panneau else ''))
    raise DevisRefuse(detail, champ='zones.0.geometry.moduleId', statut=409,
                      donnees={'detail': detail, 'code': 'module_substitue',
                               'champ': 'zones.0.geometry.moduleId',
                               'kwc_dessine': round(dessine, 3),
                               'kwc_compose': round(float(compose), 3)})


def _generer(calepinage, layout, company, lead, client, montants, *, user,
             journal):
    """CAL24 — la création (ou la dédup) APRÈS toutes les gardes."""
    from django.db import transaction

    from apps.ventes.services import (
        AutoDevisError, layout_hash, validate_composition_for_layout,
    )

    # Pré-vol de composition : le catalogue peut-il servir ce toit ? Le refus
    # est celui du serveur ventes, mot pour mot (422).
    # ACAL32 — le pré-vol compose avec la phase et le site isolé du LEAD,
    # comme la création ; un site isolé non servable est un 422 NOMMÉ.
    try:
        erreurs = validate_composition_for_layout(layout, company, lead=lead)
    except AutoDevisError as refus:
        raise DevisRefuse(refus.message, champ=refus.field or 'composition',
                          statut=422) from None
    if erreurs:
        raise DevisRefuse(erreurs[0], champ='composition', statut=422,
                          donnees={'detail': erreurs[0], 'errors': erreurs})

    # ACAL968 — une copie limitée aux surfaces cochées se dédoublonne sur SA empreinte.
    empreinte = (calepinage.layout_hash if layout is calepinage.roof_layout
                 else None) or layout_hash(layout)
    # ACON46 — UNE transaction sous verrou de ligne du calepinage : deux
    # générations concurrentes se sérialisent ; la seconde relit le lien posé
    # par la première (dédup) au lieu de créer un second devis.
    with transaction.atomic():
        from ..models import Calepinage

        Calepinage.objects.select_for_update().filter(pk=calepinage.pk).exists()
        calepinage.refresh_from_db(fields=['devis'])
        return _generer_sous_verrou(calepinage, layout, company, lead, client,
                                    montants, empreinte, user=user,
                                    journal=journal)


def _generer_sous_verrou(calepinage, layout, company, lead, client, montants,
                         empreinte, *, user, journal):
    """ACON46 — dédup, création et liaison, sous le verrou de ``_generer``."""
    from django.db import transaction

    from apps.ventes.services import (
        AutoDevisError, build_devis_from_layout, poser_layout_hash,
        rafraichir_etudes_du_devis,
    )

    # ACAL89 — le lien EXISTANT est lu AVANT toute création.
    lie = _devis_lie_actif(calepinage)
    if lie is not None:
        # ACAL33 — un calepinage lié à un devis ACTIF n'est jamais re-pointé :
        # le même brouillon à la même empreinte est rendu (dédup, double clic,
        # client seul compris), tout autre cas est un 409 NOMMÉ avant toute
        # création (jamais un devis orphelin ni un 500).
        if (lie.statut == 'brouillon'
                and (lie.layout_hash or '') == (empreinte or '')):
            _refuser_autre_marche(lie, lead)  # ACON90
            _refuser_montants_differents(lie, montants)  # ACON49
            return lie, False
        raise _refus_deja_rattache(lie)
    if lead is not None:
        deja = _brouillon_reutilisable(company, lead, empreinte, calepinage)
        if deja is not None:
            _refuser_autre_marche(deja, lead)  # ACON90
            _refuser_montants_differents(deja, montants)  # ACON49
            _lier(calepinage, deja, user=user)
            # ACON85 — les études relues APRÈS le lien (ombrage servi).
            rafraichir_etudes_du_devis(deja)
            _poser_affiche(calepinage, deja)
            return deja, False

    journal_composition = {}
    try:
        with transaction.atomic():
            devis = build_devis_from_layout(
                layout=layout, user=user, company=company, lead=lead,
                client=client, journal=journal_composition, **montants)
            _garde_kwh_declare(devis)
            _garde_module_substitue(devis, layout)  # ACAL914
    except AutoDevisError as refus:
        # ACAL32 — phase / site isolé du lead déduits par la création ; son
        # refus NOMMÉ (``hors_reseau``) remonte en 422, jamais un 500.
        raise DevisRefuse(refus.message, champ=refus.field or 'composition',
                          statut=422) from None
    # Le devis porte la MÊME empreinte que le calepinage : c'est ce qui rend
    # la dédup possible au clic suivant, et le badge « à jour » honnête.
    poser_layout_hash(devis, empreinte)
    _lier(calepinage, devis, user=user)
    # ACON85 — ``build_devis_from_layout`` a rafraîchi AVANT le lien
    # (``calepinage_du_devis`` ne trouvait rien) : l'ombrage du calepinage
    # n'entre dans le bloc horaire qu'ici.
    rafraichir_etudes_du_devis(devis)
    _poser_affiche(calepinage, devis)
    if journal is not None:
        # ACAL89 — ce que la composition a REFUSÉ de faire, tel quel.
        journal['avertissements'] = list(
            journal_composition.get('avertissements') or ())
        journal['marques_manquantes'] = list(
            journal_composition.get('marques_manquantes') or ())
    return devis, True


def _garde_electrique(calepinage, derogation, user, *, geste):
    """ACAL170 — ``garde_publication`` traduite en refus du pont devis.

    Bloquant sans dérogation ⇒ 422 ``{detail, electrique{verdict,
    bloquants, derogation_possible}}`` (contrat
    ``calepinage_publication_electrique.json``) ; dérogation illisible ou
    sans motif ⇒ 400 nommant ``derogation_electrique``. N'écrit rien.
    """
    from .electrique import (
        CHAMP_DEROGATION_PUBLICATION, EntreeInvalide, PublicationBloquee,
        garde_publication,
    )

    try:
        return garde_publication(calepinage, derogation=derogation,
                                 user=user)
    except PublicationBloquee as refus:
        detail = ("Le verdict électrique est bloquant : le devis n'est pas "
                  f"{geste}.")
        raise DevisRefuse(detail, champ='electrique', statut=422, donnees={
            'detail': detail,
            'electrique': {'verdict': 'bloquant',
                           'bloquants': list(refus.bloquants),
                           'derogation_possible': True},
        }) from None
    except EntreeInvalide as refus:
        raise DevisRefuse(str(refus), champ=(
            refus.champ or CHAMP_DEROGATION_PUBLICATION)) from None


def _consigner_et_servir(calepinage, garde, *, user=None):
    """ACAL170 — consigne la dérogation (fil + chatter) et rend la clé
    ``electrique`` de la réponse ``{verdict, manquantes, derogation}``."""
    from .electrique import consigner_derogation_publication

    trace = garde.get('derogation')
    derogation = None
    if trace:
        consigner_derogation_publication(calepinage, trace, user=user)
        derogation = {
            'motif': trace['motif'],
            'auteur': {'id': trace.get('auteur_id'),
                       'nom_complet': trace['auteur']},
            'horodatage': trace['horodatage'],
        }
    return {'verdict': garde['verdict'],
            'manquantes': list(garde.get('manquantes') or ()),
            'etat': garde['etat'], 'points': garde['points'],
            'derogation': derogation}


def _poser_affiche(calepinage, devis):
    """ACAL98 (C-ACAL-107) — l'affiche 3D du calepinage COPIÉE sur le devis
    (``apps.ventes.services.poser_affiche_depuis``, clé du devis, jamais une
    clé partagée). Best-effort : un magasin injoignable ne fait pas échouer
    une génération déjà réussie (le PDF se rend alors sans affiche)."""
    cle = getattr(calepinage, 'roof_image', None)
    if not cle:
        return
    from apps.ventes.services import poser_affiche_depuis

    try:
        poser_affiche_depuis(devis, cle)
    except Exception:  # cf. docstring
        logger.warning('ACAL98 : affiche non copiée du calepinage %s',
                       getattr(calepinage, 'pk', None), exc_info=True)


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


def _refuser_montants_differents(brouillon, montants):
    """ACON49 — une génération DÉDUPLIQUÉE ne change jamais en silence les
    montants demandés : TVA ou remise différente du brouillon rendu ⇒ 409
    nommant le champ (le brouillon se modifie depuis le devis), rien écrit."""
    for cle, quoi, geste in (('taux_tva', 'à {} %', 'la TVA'),
                             ('remise_globale', 'avec une remise de {} %',
                              'la remise')):
        actuel = getattr(brouillon, cle, None)
        if cle in montants and actuel is not None and montants[cle] != actuel:
            message = (f"Le devis {brouillon.reference} existe déjà "
                       f"{quoi.format(_pourcentage_lisible(actuel))} : "
                       f"changez {geste} depuis le devis.")
            raise DevisRefuse(message, champ=cle, statut=409,
                              donnees={cle: message})


def _pourcentage_lisible(valeur):
    """ACON49 — ``Decimal('20.00')`` ⇒ ``'20'``, ``5.50`` ⇒ ``'5,5'``."""
    texte = f'{valeur:f}'
    if '.' in texte:
        texte = texte.rstrip('0').rstrip('.')
    return texte.replace('.', ',')


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


def resynchroniser_devis(calepinage, *, user=None,
                         derogation_electrique=None, devis_id=None,
                         surfaces_chiffrees=None):
    """CAL25 — resynchronise le devis lié sur la conception COURANTE.

    ACAL968 — ``surfaces_chiffrees`` absent : la sélection ÉCRITE au devis
    (``choixConception.surfacesChiffrees``) est relue ; aucune ⇒ tout.

    ACON6 — ``devis_id`` : le devis à resynchroniser, lu par
    ``selectors.conception_du_devis`` (un devis porté par une VARIANTE suit
    le document de la variante, jamais celui du calepinage).

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
    from apps.ventes.services import (
        SyncLayoutError, resynchroniser_conception)

    from .feu_vert import GESTE_DEVIS, verifier_avant_publication

    verifier_avant_publication(calepinage, geste=GESTE_DEVIS)
    layout = _exiger_layout(calepinage)
    # ACON6/ACON80 — un devis porté par une variante de CE calepinage suit
    # le document de la variante ; tout autre ``devis_id`` est ignoré.
    from ..selectors import variante_portant_le_devis

    variante = variante_portant_le_devis(calepinage, devis_id)
    if variante is not None:
        layout = _exiger_layout(variante)
    # ACAL373 — agricole / multi-villa : la raison de l'écran, 409, rien n'est
    # écrit (le refus de STATUT reste celui de ventes, revision_possible compris).
    from apps.ventes.selectors_calepinage import raison_lecture_seule_conception

    from .verrou import est_verrouille
    lie = (variante.devis if variante is not None
           else getattr(calepinage, 'devis', None))
    if lie is not None and not est_verrouille(calepinage, devis=lie):
        raison = raison_lecture_seule_conception(lie)
        if raison:
            raise DevisRefuse(raison, champ='roof_layout', statut=409,
                              donnees={'roof_layout': [raison]})
    # ACAL170 — même cliquet électrique que la génération, AVANT toute
    # écriture (un devis ENVOYÉ suit le même refus).
    garde = _garde_electrique(calepinage, derogation_electrique, user,
                              geste='resynchronisé')
    devis_id = (variante.devis_id if variante is not None
                else getattr(calepinage, 'devis_id', None))
    if not devis_id:
        raise DevisRefuse(
            "Aucun devis n'est rattaché à ce calepinage : utilisez d'abord "
            "« Générer le devis ».", champ='devis')
    devis = get_devis_by_pk(devis_id)
    company = getattr(calepinage, 'company', None)
    if devis is None or (company is not None
                         and devis.company_id != company.pk):
        raise DevisRefuse(f"Devis introuvable (#{devis_id}).", champ='devis')
    layout = _layout_des_surfaces(layout, surfaces_chiffrees if surfaces_chiffrees
                                  is not None else _selection_du_devis(devis))

    try:
        # ACAL34 — l'enveloppe ventes UNIQUE : resynchro + quatre études
        # (étude horaire, profils… décrivent les lignes). L'annonce
        # layout_finalise depuis le module est branchée par D02-T14.
        # ACAL38 — la resynchro du MODULE annonce enfin ``layout_finalise``
        # (UNE fois) : le rattachement n'écrit plus rien sur un calepinage
        # existant (plus de miroir), et l'abonné crm note la conception.
        # ACAL98 — l'affiche du calepinage suit (copie sous la clé du devis).
        # ACON6/ACON80 — un devis porté par une VARIANTE ne reçoit JAMAIS
        # l'affiche du conteneur C1 (image client de /proposal et du PDF).
        resultat = resynchroniser_conception(
            devis, layout, user, emettre=True,
            roof_image=None if variante is not None else (
                getattr(calepinage, 'roof_image', None) or None))
    except SyncLayoutError as refus:
        raise DevisRefuse(
            refus.detail, champ='devis', statut=409,
            donnees={'detail': refus.detail,
                     'revision_possible': refus.revision_possible}) from refus
    resultat = dict(resultat or {})
    resultat['electrique'] = _consigner_et_servir(calepinage, garde,
                                                  user=user)
    return resultat
