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


def empreinte_des_surfaces(layout, cles):
    """ACAL968 — l'empreinte imprimée de LA copie que chiffrerait la sélection
    ``cles`` (même :func:`_layout_des_surfaces` que la création) ; ``''``
    quand la sélection ne s'applique plus (surface retirée du document)."""
    from apps.ventes.services import layout_hash

    try:
        return layout_hash(_layout_des_surfaces(layout, cles)) or ''
    except DevisRefuse:
        return ''


def _selection_du_devis(devis, porteur):
    """ACAL968 — la sélection écrite au devis (``roof_layout``), ou ``None`` ;
    ACAL1249 : lue contre le document de ``porteur`` (pan existant ignoré)."""
    from apps.ventes.selectors_calepinage import selection_lue_du_devis

    return selection_lue_du_devis(devis, porteur)


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


def lit_les_devis(user):
    """Lot 8 (D-ACAL-106) — LA garde de lecture d'un devis (``apps.ventes.selectors_assistant.
    lit_les_devis``), passée par ce module déjà importateur de ventes (cliquet
    ``test_imports_croises_ventes``)."""
    from apps.ventes.selectors_assistant import lit_les_devis as garde

    return garde(user)


def avertissements_sans_montant(avertissements):
    """Revue du 26/11 (D-ACAL-106/165) — les avertissements d'une resynchronisation sans montant de vente
    (``apps.ventes.services.avertissements_sans_montant``), passés par ce module déjà importateur de
    ventes (cliquet ``test_imports_croises_ventes``)."""
    from apps.ventes.services import avertissements_sans_montant as sans_montant

    return sans_montant(avertissements)


def _apercu_de_ventes(devis, layout, user, designations):
    """ACAL1320 — la resynchronisation jouée puis annulée par ventes (``apercu_de_resynchronisation``) et
    son refus de statut (``SyncLayoutError``), passés par ce module (même cliquet)."""
    from apps.ventes.services import SyncLayoutError, apercu_de_resynchronisation

    try:
        return apercu_de_resynchronisation(devis, layout, user, designations=designations), None
    except SyncLayoutError as refus:
        return None, refus


def devis_suit_les_designations(devis):
    """Relecture D-ACAL-148 round 4 — le devis est-il né sous la règle des désignations
    (``apps.ventes.selectors_calepinage.devis_suit_les_designations``) ? Même cliquet."""
    from apps.ventes.selectors_calepinage import devis_suit_les_designations as suit

    return suit(devis)


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


def _empreinte_generee(calepinage, layout):
    """ACAL968 — l'empreinte du document que « Générer » chiffre (celle du calepinage quand il
    chiffre tout, sinon celle de la copie des surfaces cochées)."""
    from apps.ventes.services import layout_hash

    return (calepinage.layout_hash if layout is calepinage.roof_layout else None) or layout_hash(layout)


def _brouillon_rendu(calepinage, company, lead, empreinte, *, lie=None):
    """Lane E9b — le brouillon que « Générer le devis » RENDRAIT au lieu d'en composer un : le
    devis lié actif encore brouillon à la même empreinte (ACAL33), sinon le brouillon
    réutilisable du lead (ACAL89) ; ``None`` sinon. Lecture seule ; ``lie`` : le lien déjà lu."""
    lie = lie if lie is not None else _devis_lie_actif(calepinage)
    if lie is not None:
        return lie if lie.statut == 'brouillon' and (lie.layout_hash or '') == (empreinte or '') else None
    return _brouillon_reutilisable(company, lead, empreinte, calepinage) if lead is not None else None


#: Lot 8 (B1) — les issues de « Générer le devis », dans l'ordre où ``_generer_sous_verrou`` les tranche.
ISSUE_RENDU, ISSUE_DEJA_RATTACHE, ISSUE_BROUILLON_LIBRE, ISSUE_COMPOSER = (
    'rendu', 'deja_rattache', 'brouillon_libre', 'composer')


def _ordre_de_generation(lie, rendu, libres_lus):
    """Lot 8 (B1) — ``(issue, objet)`` : L'ORDRE des décisions de « Générer », partagé par la
    génération et l'aperçu. Lié actif d'abord (rendu s'il est ce brouillon, sinon 409 « déjà
    rattaché ») ; puis le brouillon rendu ; puis les brouillons libres du lead (question R2-22,
    ``libres_lus()`` lu seulement à ce rang) ; sinon composer. Pur : n'écrit ni ne lit rien."""
    if lie is not None:
        return (ISSUE_RENDU, lie) if rendu is not None else (ISSUE_DEJA_RATTACHE, lie)
    if rendu is not None:
        return ISSUE_RENDU, rendu
    libres = libres_lus()
    return (ISSUE_BROUILLON_LIBRE, libres) if libres else (ISSUE_COMPOSER, None)


def _onduleur_designe(calepinage):
    """D-ACAL-148 — ``{'produit_id', 'nombre'}`` de l'onduleur désigné à l'étape Électrique
    (``electrique.entree_stockee``), ``None`` sans désignation. Lu par la génération ET l'aperçu :
    ``ventes`` décide seul s'il est chiffré (catalogue, prix, forme du devis)."""
    from .electrique import entree_stockee
    from .variantes import onduleur_designe_a_la_main

    entree = entree_stockee(calepinage)
    # Lot 8 — un onduleur « repris de l'original » (copie, ACAL1253) n'est pas une désignation du vendeur.
    if entree.get('onduleur_produit') in (None, '') or not onduleur_designe_a_la_main(calepinage):
        return None
    brut = entree.get('nombre_onduleurs')
    if brut in (None, ''):  # aucun nombre accepté : celui que le SCHÉMA dessine
        return {'produit_id': entree['onduleur_produit'], 'nombre': _nombre_du_schema(calepinage),
                'nombre_illisible': False}
    entier = (int(brut) if isinstance(brut, (int, float)) and not isinstance(brut, bool)
              and float(brut).is_integer() and brut >= 1 else None)
    return {'produit_id': entree['onduleur_produit'], 'nombre': entier, 'nombre_illisible': entier is None}


def _batterie_designee(calepinage):
    """D-ACAL-164 — ``{'produit_id', 'packs', 'packs_illisible'}`` de la batterie désignée à l'étape
    Électrique (``entree_stockee(...)['batterie']['produit']``, saisie D-ACAL-157), ``None`` sans
    désignation. Le nombre de packs saisi (entier ≥ 1) ; autre chose ⇒ ``packs_illisible``, jamais
    tronqué ; absent ⇒ ``None`` (``ventes`` le dit). Lu par la génération, l'aperçu et la resynchro."""
    from .electrique import entree_stockee

    batterie = entree_stockee(calepinage).get('batterie')
    if not isinstance(batterie, dict) or batterie.get('produit') in (None, ''):
        return None
    brut = batterie.get('packs')
    entier = (int(brut) if isinstance(brut, (int, float)) and not isinstance(brut, bool)
              and float(brut).is_integer() and brut >= 1 else None)
    return {'produit_id': batterie['produit'], 'packs': entier,
            'packs_illisible': brut not in (None, '') and entier is None}


def _nombre_du_schema(calepinage):
    """D-ACAL-148 (relecture, point 1) — le nombre d'onduleurs que le schéma du calepinage
    dessine (``chaines.evaluer_onduleurs`` sur ``electrique.conception_du_calepinage``, la source
    de la table d'affectation), ``None`` quand il n'est pas établi (fiche incomplète…)."""
    from .chaines import evaluer_onduleurs
    from .electrique import conception_du_calepinage

    try:
        evaluation = evaluer_onduleurs(conception_du_calepinage(calepinage)[0])
    except Exception:  # noqa: BLE001 — conception illisible : nombre non établi, repli annoncé (D-ENF22-BLE001)
        logger.warning('onduleur désigné : nombre du schéma illisible', exc_info=True)
        return None
    nombre = getattr(evaluation, 'nombre', None)
    return int(nombre) if isinstance(nombre, int) and nombre >= 1 else None


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
                  derogation_electrique=None, surfaces_chiffrees=None,
                  confirmer_taille=False, rattacher_devis=None,
                  creer_autre_devis=False):
    """CAL24 — crée (ou RETROUVE) le devis de ce calepinage.

    ACAL968 — ``surfaces_chiffrees`` : les clés des surfaces COCHÉES
    (``None`` = toutes) ; le devis compose la copie sans les décochées.
    ACAL922 — sans ``confirmer_taille``, une CRÉATION que rien ne dimensionne
    (``taille_non_dimensionnee``), ou dont la pose dépasse 2 × la cible des
    factures (recette R2-17), est annulée : 409 ``confirmation_taille``.
    Recette R2-22 (D-ACAL-1) — le lead a un brouillon libre né AVANT ce
    calepinage : 409 ``devis_existant`` ; ``rattacher_devis`` (son id) y
    rattache ce calepinage, ``creer_autre_devis`` en crée un autre.
    Recette R2-10 — une génération RÉUSSIE annonce ``layout_finalise`` une
    fois, après la transaction (jamais sur une dédup ni sur un refus).

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
    choix = _choix_de_generation(confirmer_taille, rattacher_devis,
                                 creer_autre_devis)
    devis, cree = _generer(calepinage, layout, company, lead, client,
                           montants, user=user, journal=journal, choix=choix)
    if cree or choix.get('rattache'):
        _annoncer_conception(devis, user)
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


def _cible_du_calepinage(calepinage):
    """ACAL2012 (règle 5 de la consolidation C4) — LE point de bascule de la cible :
    la conception COURANTE du lead (ou du calepinage sans lead), jamais un second
    dimensionnement ni le devis lié (``devis_retenu.cible_de_la_conception``).
    Lecture seule."""
    from .devis_retenu import cible_de_la_conception

    return cible_de_la_conception(calepinage)


def taille_non_dimensionnee(calepinage, *, cible=None):
    """ACAL861/ACAL922 — LA condition « rien ne dimensionne ce devis », écrite
    UNE fois (le contrôle « prêt à envoyer ? » la lit ; la porte 409 d'ACAL922
    la lira) : sans lead, ou lead dont la conception refuse faute de facture
    (``motif_code`` = ``MOTIF_FACTURE_ABSENTE``), ou n'est pas encore rangée
    alors que le lead n'a ni facture ni taille (ACAL2012). Rend ``{'refus': texte}`` ou ``None`` (dimensionné, ou refusé
    pour une AUTRE raison : agricole, kWh incohérent ne posent pas cette
    question). Lecture seule. ``cible`` : la cible déjà lue
    (``_cible_du_calepinage``), pour ne pas la relire."""
    from apps.ventes.services import MOTIF_FACTURE_ABSENTE

    from .devis_retenu import CODE_CONCEPTION_ABSENTE, CODE_CONCEPTION_EN_COURS

    if cible is None:
        cible = _cible_du_calepinage(calepinage)
    if not getattr(calepinage, 'lead_id', None):
        # Relecture E5 m1 — la conception du calepinage lui-même donne la taille : rien à demander.
        if (cible or {}).get('panneaux'):
            return None
        return {'refus': "Calepinage sans lead : aucune facture ne "
                         "dimensionne le système."}
    motif = (cible or {}).get('motif_code')
    if motif == MOTIF_FACTURE_ABSENTE or (motif in (CODE_CONCEPTION_ABSENTE, CODE_CONCEPTION_EN_COURS)
                                          and lead_sans_facture_ni_taille(calepinage)):
        return {'refus': cible.get('refus') or ''}
    return None


#: ACAL1342 — les champs du lead d'où le moteur tire une consommation (facture d'hiver,
#: d'été, kWh mensuel déclaré) et la taille souhaitée qui le court-circuite.
_CHAMPS_DIMENSIONNANTS = ('facture_hiver', 'facture_ete', 'conso_mensuelle_kwh',
                          'taille_souhaitee_kwc')


def lead_sans_facture_ni_taille(calepinage):
    """ACAL1342 — vrai quand le lead RÉSIDENTIEL ne porte AUCUN des champs dimensionnants :
    le moteur refuserait « facture absente » (``taille_non_dimensionnee``) sans qu'il soit
    utile de le lancer. Une seule lecture du lead ; un champ inconnu ⇒ faux (le moteur
    tranche alors, comme avant)."""
    from apps.crm.selectors import get_company_lead

    if not getattr(calepinage, 'lead_id', None):
        return False
    lead = get_company_lead(getattr(calepinage, 'company', None), calepinage.lead_id,
                            avec_corbeille=True)
    absent = object()
    valeurs = [getattr(lead, champ, absent) for champ in _CHAMPS_DIMENSIONNANTS]
    if lead is None or absent in valeurs:
        return False
    if (getattr(lead, 'type_installation', '') or '').lower() not in ('', 'residentiel'):
        return False
    return not any(_positif_ou_none(v) for v in valeurs)


def _positif_ou_none(valeur):
    try:
        return float(valeur) > 0 if valeur not in (None, '') else False
    except (TypeError, ValueError):
        return False


#: Recette R2-17 (Q2, décision de l'orchestrateur du 22/11/2026, réversible) —
#: au-delà de 2 × la cible tirée des FACTURES, la taille se confirme. Le facteur
#: 2 est celui de la règle du fondateur du 30/09/2026 (« kWh déclaré contredisant
#: les factures de plus de 2× », docs/claude-memory/kwh-declare-vs-factures.md).
FACTEUR_POSE_SUR_CIBLE = 2


def _panneaux_du_devis(devis):
    """Les panneaux que le devis composé vend (option par défaut, lignes
    produit dont la désignation dit « panneau », comme ``builder.py``)."""
    from apps.ventes.selectors_calepinage import lignes_produits_calepinage

    return int(sum(ligne['quantite'] or 0 for ligne in lignes_produits_calepinage(devis)
                   if 'panneau' in (ligne['designation'] or '').lower()))


def _question_pose_sur_cible(devis, cible):
    """R2-17 — ``{'refus', 'poses', 'cible'}`` quand les panneaux vendus
    dépassent ``FACTEUR_POSE_SUR_CIBLE`` × la cible tirée des factures ;
    ``None`` sans cible des factures (taille souhaitée, C&I, agricole, refus :
    ACAL922 ou rien)."""
    from core.electrique.types import fr

    if not cible or cible.get('source') != 'factures' or not cible.get('panneaux'):
        return None
    attendus = int(cible['panneaux'])
    poses = _panneaux_du_devis(devis)
    if poses <= FACTEUR_POSE_SUR_CIBLE * attendus:
        return None
    kwc = f" ({fr(float(cible['kwc']), 2)} kWc)" if cible.get('kwc') else ''
    return {'poses': poses, 'cible': attendus,
            'refus': (f'Cible tirée des factures du lead (dimensionnement du devis '
                      f'automatique) : {attendus} panneaux{kwc}.')}


def _ttc_lisible(devis):
    """``(Decimal, '168 800,00 MAD TTC')`` du devis (total servi par ventes)."""
    from decimal import Decimal

    ttc = Decimal(str(devis.total_ttc or 0)).quantize(Decimal('0.01'))
    return ttc, f'{ttc:,.2f}'.replace(',', ' ').replace('.', ',') + ' MAD TTC'


def _kwc_compose_du_devis(devis):
    """ACAL1417 — le kWc que la composition vend : ``etude_params['puissance_kwc']``
    et, quand ce chemin de composition ne l'a pas posé, LA règle unique de
    ``ventes`` (``puissance_kwc_du_devis``, lue des lignes panneau) — jamais
    ``None`` faute de clé, ce qui faisait taire la garde du module substitué et
    vider le kWc de la question de taille. ``None`` seulement si rien n'est lisible."""
    from apps.ventes.services import puissance_kwc_du_devis

    kwc = (getattr(devis, 'etude_params', None) or {}).get('puissance_kwc')
    return kwc if kwc is not None else puissance_kwc_du_devis(devis)


def _garde_taille(devis, calepinage, confirmer_taille):
    """ACAL922 — un devis que rien ne dimensionne demande une CONFIRMATION :
    409 ``confirmation_taille`` avec le kWc et le TTC du devis composé, sous
    la transaction de la création (devis annulé) ; jamais un blocage.
    R2-17 — même question quand la pose dépasse 2 × la cible des factures."""
    from core.electrique.types import fr

    if confirmer_taille:
        return
    cible = _cible_du_calepinage(calepinage)
    question = taille_non_dimensionnee(calepinage, cible=cible)
    au_dela = None if question is not None else _question_pose_sur_cible(devis, cible)
    if question is None and au_dela is None:
        return
    kwc = _kwc_compose_du_devis(devis)
    ttc, ttc_texte = _ttc_lisible(devis)
    chiffres = ([f'{fr(float(kwc), 2)} kWc'] if kwc is not None else []) + [ttc_texte]
    if au_dela is not None:
        question = au_dela
        detail = (f"La pose compte {au_dela['poses']} panneaux ({', '.join(chiffres)}), "
                  f"plus de {FACTEUR_POSE_SUR_CIBLE} fois les {au_dela['cible']} panneaux "
                  'de la cible tirée des factures du lead. Confirmez, ou réduisez la '
                  'pose dans l’atelier.')
    else:
        detail = ('Aucune facture ni taille souhaitée sur le lead : le devis '
                  f'remplit le toit ({", ".join(chiffres)}). Confirmez, ou '
                  'renseignez la facture du lead.')
    raise DevisRefuse(detail, champ='confirmer_taille', statut=409, donnees={
        'detail': detail, 'code': 'confirmation_taille',
        'champ': 'confirmer_taille', 'total_ttc': str(ttc),
        'kwc': float(kwc) if kwc is not None else None,
        'refus': question['refus']})


#: Repli SANS puissance unitaire des deux côtés : le kWc dessiné est arrondi à deux décimales par l'outil de
#: toit et le kWc composé l'est aussi (``quote_engine.lignes_classement.kwc_lu_des_panneaux`` : ``round(…, 2)``,
#: arrondi de Python sur un flottant), les deux sur une règle d'arrondi qui peut différer : deux demi-unités,
#: soit 0,01 kWc — lu du code, jamais un seuil métier.
TOLERANCE_KWC_AFFICHE = 0.01

#: Un watt lu d'une fiche ou d'une désignation est entier (``_fiche_watt``, ``_parse_watt``) : un module de
#: 577,5 W dessiné se lit 577 ou 578 au catalogue.
TOLERANCE_WATT_LU = 0.5


def _module_est_substitue(dessine_kwc, compose_kwc, dessine=None, compose=None):
    """Le module que le devis composerait n'est-il PAS celui du dessin ?

    Fonction PURE. ``dessine`` / ``compose`` = ``[(quantité, watt unitaire)]`` des deux côtés (le dessin :
    ses pans vendus ; la composition : ses lignes panneau, lues par ``ventes``). Quand les deux sont
    connus, la comparaison ne dépend d'AUCUN arrondi de kWc : le compte total doit être le même et
    chaque puissance unitaire du dessin doit être celle d'une ligne composée (à l'entier du watt lu
    près). Sinon, repli sur les kWc avec ``TOLERANCE_KWC_AFFICHE``."""
    if dessine and compose and all(w for _n, w in dessine) and all(w for _n, w in compose):
        if sum(n for n, _w in dessine) != sum(n for n, _w in compose):
            return True
        watts_d = sorted({float(w) for _n, w in dessine})
        watts_c = sorted({float(w) for _n, w in compose})
        if len(watts_d) != len(watts_c):
            return True
        return any(abs(d - c) > TOLERANCE_WATT_LU + 1e-9 for d, c in zip(watts_d, watts_c))
    return abs(float(compose_kwc) - dessine_kwc) > TOLERANCE_KWC_AFFICHE + 1e-9


def _chiffres_distincts(dessine, compose):
    """Les deux kWc affichés, avec UNE décimale de plus dès que deux décimales les
    montreraient identiques : un refus n'imprime jamais deux chiffres égaux."""
    from core.electrique.types import fr

    for decimales in (2, 3, 4):
        a, b = fr(dessine, decimales), fr(compose, decimales)
        if a != b:
            break
    return a, b


def _kwc_exact(wc):
    """Un total en Wc EXACT écrit en kWc sans arrondi (deux décimales au moins) : 25 025 -> « 25,025 »."""
    from decimal import Decimal

    texte = format((Decimal(str(wc)) / 1000).normalize(), 'f')
    entier, _, decimales = texte.partition('.')
    return '%s,%s' % (entier, decimales.ljust(2, '0'))


def _phrase_module(paires):
    """« 35 panneaux de 715 W, soit 25,025 kWc » (le total seul si les modules sont mêlés)."""
    from decimal import Decimal

    nombre = sum(n for n, _w in paires)
    total = sum((n * Decimal(str(w)) for n, w in paires), Decimal(0))
    watts = {Decimal(str(w)) for _n, w in paires}
    unitaire = ' de %s W' % format(next(iter(watts)).normalize(), 'f') if len(watts) == 1 else ''
    return '%d panneaux%s, soit %s kWc' % (nombre, unitaire, _kwc_exact(total))


def _paires_composees(devis):
    """``[(quantité, watt)]`` des lignes panneau du devis composé, ou ``[]`` : la lecture de ``ventes``."""
    if getattr(devis, 'lignes', None) is None:
        return []
    from apps.ventes.services import panneaux_composes_du_devis

    return panneaux_composes_du_devis(devis)


def _paires_dessinees(pans):
    """``[(compte, watt unitaire)]`` des pans VENDUS, ou ``None`` dès qu'un pan vendu n'a pas l'un des deux
    (jamais de puissance supposée) ; le watt est le ``pmaxWc`` du modèle posé, EXACT (``Decimal``)."""
    from decimal import Decimal

    vendus = [p for p in pans if p['modules'] > 0 and not p.get('existant')]
    if not vendus or any(not p.get('module_wc') for p in vendus):
        return None
    return [(p['modules'], Decimal(str(p['module_wc']))) for p in vendus]


def _garde_module_substitue(devis, layout):
    """ACAL914 — 409 ``module_substitue`` quand la composition chiffre un
    autre module que le dessin (kWc composé ≠ kWc dessiné), sous la
    transaction de la création (devis annulé)."""
    from core.electrique.types import fr

    from apps.ventes.selectors_calepinage import lignes_produits_calepinage
    from apps.ventes.services import pans_du_document

    from .valeurs import nombre

    pans = pans_du_document(layout)
    # Un pan existant (ACAL573) n'est pas vendu : la composition l'ignore aussi.
    dessine = sum(p['kwc'] for p in pans if p.get('kwc') and not p.get('existant'))
    paires = _paires_dessinees(pans)
    if dessine and not any(p['kind'] == 'toit' and p['source'] != 'aucune' for p in pans):
        paires = None
        # Toit sans pan mesuré : il est résumé par le ``result`` racine, que la
        # composition compte aussi (``ventes.lire_layout``) — sinon un toit
        # résumé + un champ au sol se lisait « champ seul » (faux 409).
        dessine += nombre(((layout if isinstance(layout, dict) else {})
                           .get('result') or {}).get('kwc')) or 0.0
    if any(p['kind'] == 'toit' and p['modules'] > 0 and not p.get('kwc')
           and not p.get('existant') for p in pans):
        # Critique 22/11 (soupçon 2) — un pan pavé sans kWc lisible : la
        # composition lit alors le toit à son résumé ; la somme partielle des
        # pans ferait un faux 409. Le dessin est lu par LA même lecture.
        from apps.ventes.selectors_calepinage import kwc_lu_du_layout

        dessine = kwc_lu_du_layout(layout)
        paires = None
    compose = _kwc_compose_du_devis(devis)
    if not dessine or compose is None:
        return
    composees = _paires_composees(devis)
    if not _module_est_substitue(dessine, compose, paires, composees):
        return
    # Le refus imprime les chiffres COMPARÉS : quand la comparaison s'est faite en compte × puissance
    # unitaire des deux côtés, les deux totaux EXACTS et leurs puissances ; sinon les deux kWc (le
    # champ ``kwc`` stocké d'un pan peut être périmé et égal au composé : jamais deux chiffres égaux).
    en_watts = bool(paires and composees and all(w for _n, w in composees))
    if en_watts:
        affiche_dessine = _phrase_module(paires)
        affiche_compose = _phrase_module(composees)
    else:
        affiche_dessine, affiche_compose = (
            '%s kWc' % a_ for a_ in _chiffres_distincts(dessine, float(compose)))
    panneau = next((ligne['designation'] for ligne in
                    lignes_produits_calepinage(devis)
                    if 'panneau' in (ligne['designation'] or '').lower()), '')
    vendus = [p for p in pans if p['modules'] > 0 and not p.get('existant')]
    if vendus and all(p['kind'] != 'toit' for p in vendus):
        # ACAL1440 — une surface de pose (champ au sol…) n'a aucun choix de module : elle reprend
        # celui du pan actif à l'enregistrement (ACAL918). Le texte dit donc quoi changer et où.
        watts = sorted({fr(p['module_wc'], 0) for p in vendus if p.get('module_wc')})
        detail = ("%s : son module (« %s ») n'est pas celui que le catalogue compose (« %s »). "
                  "Changez le module du pan, puis ré-enregistrez le contour."
                  % (', '.join(p['libelle'] for p in vendus),
                     ' / '.join('%s W' % w for w in watts) or '?',
                     panneau or '%s kWc' % fr(float(compose), 2)))
    else:
        detail = ("Le dessin porte %s ; le catalogue compose %s%s. "
                  "Choisissez le module du catalogue dans l'atelier puis "
                  "relancez." % (affiche_dessine, affiche_compose,
                                 ' (%s)' % panneau if panneau else ''))
    raise DevisRefuse(detail, champ='zones.0.geometry.moduleId', statut=409,
                      donnees={'detail': detail, 'code': 'module_substitue',
                               'champ': 'zones.0.geometry.moduleId',
                               'kwc_dessine': round(dessine, 3),
                               'kwc_compose': round(float(compose), 3)})


def _generer(calepinage, layout, company, lead, client, montants, *, user,
             journal, choix):
    """CAL24 — la création (ou la dédup) APRÈS toutes les gardes."""
    from django.db import transaction

    from apps.ventes.services import (
        AutoDevisError, validate_composition_for_layout,
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
    empreinte = _empreinte_generee(calepinage, layout)
    # ACON46 — UNE transaction sous verrou de ligne du calepinage : deux
    # générations concurrentes se sérialisent ; la seconde relit le lien posé
    # par la première (dédup) au lieu de créer un second devis.
    with transaction.atomic():
        from ..models import Calepinage

        Calepinage.objects.select_for_update().filter(pk=calepinage.pk).exists()
        calepinage.refresh_from_db(fields=['devis'])
        return _generer_sous_verrou(calepinage, layout, company, lead, client,
                                    montants, empreinte, user=user,
                                    journal=journal, choix=choix)


def _generer_sous_verrou(calepinage, layout, company, lead, client, montants,
                         empreinte, *, user, journal, choix):
    """ACON46 — dédup, création et liaison, sous le verrou de ``_generer``."""
    from django.db import transaction

    from apps.ventes.services import (
        AutoDevisError, build_devis_from_layout, poser_layout_hash,
        rafraichir_etudes_du_devis,
    )

    # ACAL89 — le lien EXISTANT est lu AVANT toute création.
    lie = _devis_lie_actif(calepinage)
    # Lane E9b — LA décision « le brouillon rendu au lieu d'un devis neuf », lue aussi par l'aperçu.
    rendu = _brouillon_rendu(calepinage, company, lead, empreinte, lie=lie)
    # Lot 8 (B1) — L'ORDRE des issues, partagé avec l'aperçu (``_ordre_de_generation``) ; la
    # question R2-22 reste posée plus bas, selon le choix de l'utilisateur.
    issue, retenu = _ordre_de_generation(lie, rendu, list)
    # ACAL33 — un calepinage lié à un devis ACTIF n'est jamais re-pointé :
    # le même brouillon à la même empreinte est rendu (dédup, double clic,
    # client seul compris), tout autre cas est un 409 NOMMÉ avant toute
    # création (jamais un devis orphelin ni un 500).
    if issue == ISSUE_DEJA_RATTACHE:
        raise _refus_deja_rattache(retenu)
    if issue == ISSUE_RENDU and lie is not None:
        _refuser_autre_marche(lie, lead)  # ACON90
        _refuser_montants_differents(lie, montants)  # ACON49
        return lie, False
    if lead is not None:
        deja = retenu if issue == ISSUE_RENDU else None
        if deja is not None:
            _refuser_autre_marche(deja, lead)  # ACON90
            _refuser_montants_differents(deja, montants)  # ACON49
            _lier(calepinage, deja, user=user)
            # ACON85 — les études relues APRÈS le lien (ombrage servi).
            rafraichir_etudes_du_devis(deja)
            _poser_affiche(calepinage, deja)
            return deja, False
        # R2-22 (D-ACAL-1) — un brouillon libre né avant ce calepinage : la
        # question nommée, ou le rattachement choisi ; jamais un second devis
        # en silence.
        if not choix['creer_autre_devis']:
            libre = _brouillon_libre_choisi(calepinage, company, lead, choix)
            if libre is not None:
                choix['rattache'] = True
                return _rattacher_au_brouillon(
                    calepinage, layout, libre, lead, montants, empreinte,
                    user=user, journal=journal,
                    confirmer_taille=choix['confirmer_taille']), False

    journal_composition = {}
    try:
        with transaction.atomic():
            devis = build_devis_from_layout(
                layout=layout, user=user, company=company, lead=lead,
                client=client, journal=journal_composition,
                onduleur_designe=_onduleur_designe(calepinage),  # D-ACAL-148
                batterie_designee=_batterie_designee(calepinage),  # D-ACAL-164
                marquer_designations=True, **montants)  # né sous la règle (relecture, point 1)
            _garde_kwh_declare(devis)
            _garde_module_substitue(devis, layout)  # ACAL914
            _garde_taille(devis, calepinage, choix['confirmer_taille'])  # ACAL922
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


def reponses_du_corps(corps):
    """Les réponses aux questions de ``generer-devis`` lues du corps (la vue) :
    ``confirmer_taille`` (ACAL922) et ``creer_autre_devis`` comptent seulement
    à ``true`` ; ``rattacher_devis`` est validé par ``generer_devis``."""
    return {'confirmer_taille': corps.get('confirmer_taille') is True,
            'rattacher_devis': corps.get('rattacher_devis'),
            'creer_autre_devis': corps.get('creer_autre_devis') is True}


def _choix_de_generation(confirmer_taille, rattacher_devis, creer_autre_devis):
    """Les réponses de l'utilisateur aux questions de « Générer le devis » ;
    ``rattacher_devis`` : un identifiant entier, jamais avec ``creer_autre_devis``
    (400 nommant le champ)."""
    if rattacher_devis is not None and (isinstance(rattacher_devis, bool)
                                        or not isinstance(rattacher_devis, int)):
        raise DevisRefuse("Indiquez le numéro du devis à rattacher.",
                          champ='rattacher_devis')
    if rattacher_devis is not None and creer_autre_devis:
        raise DevisRefuse("Choisissez : rattacher ce calepinage au devis existant, "
                          "ou créer un autre devis — pas les deux.",
                          champ='rattacher_devis')
    return {'confirmer_taille': bool(confirmer_taille),
            'rattacher_devis': rattacher_devis,
            'creer_autre_devis': bool(creer_autre_devis), 'rattache': False}


def _brouillons_libres_anterieurs(calepinage, company, lead):
    """R2-22 — les brouillons ACTIFS du lead qu'aucun calepinage ne porte, nés
    AVANT ce calepinage (« Dessiner le toit » sur un lead qui avait déjà un
    devis), du plus récent au plus ancien. Lecture seule."""
    from apps.ventes.selectors import devis_par_mode_pour_lead, get_devis_by_pk

    from ..selectors import calepinage_du_devis

    ne_le = getattr(calepinage, 'created_at', None)
    libres = []
    for ligne in reversed(devis_par_mode_pour_lead(lead.pk, company)):
        if ligne.get('statut') != 'brouillon':
            continue
        devis = get_devis_by_pk(ligne['id'])
        if (devis is None or not getattr(devis, 'is_active', True)
                or (ne_le is not None and devis.date_creation >= ne_le)
                or calepinage_du_devis(devis.pk, company) is not None):
            continue
        libres.append(devis)
    return libres


def _brouillon_libre_choisi(calepinage, company, lead, choix):
    """R2-22 — le brouillon à RATTACHER (``choix['rattacher_devis']``, revérifié :
    brouillon actif, libre, du lead), ``None`` quand le lead n'en a aucun ; sans
    choix, 409 ``devis_existant`` nommant le plus récent. Un devis envoyé ou
    accepté n'est jamais rattaché par cette voie (400 nommant le champ)."""
    libres = _brouillons_libres_anterieurs(calepinage, company, lead)
    voulu = choix['rattacher_devis']
    if voulu is not None:
        devis = next((d for d in libres if d.pk == voulu), None)
        if devis is None:
            raise DevisRefuse(
                f"Le devis #{voulu} n'est pas un brouillon libre de ce lead : il ne "
                "peut pas recevoir ce calepinage (un devis envoyé ou accepté n'est "
                "jamais rattaché ici).", champ='rattacher_devis', statut=409)
        return devis
    if not libres:
        return None
    devis = libres[0]
    reference = devis.reference or f'#{devis.pk}'
    autres = len(libres) - 1
    ttc, ttc_texte = _ttc_lisible(devis)
    detail = (f"Ce lead a déjà le devis {reference} (brouillon, {ttc_texte}), créé "
              "avant ce calepinage"
              + (f" (et {autres} autre{'s' if autres > 1 else ''} brouillon"
                 f"{'s' if autres > 1 else ''})" if autres else '')
              + " : rattachez-lui ce calepinage, ou créez un autre devis.")
    raise DevisRefuse(detail, champ='rattacher_devis', statut=409, donnees={
        'detail': detail, 'code': 'devis_existant', 'champ': 'rattacher_devis',
        'devis': devis.pk, 'reference': devis.reference, 'total_ttc': str(ttc)})


def _rattacher_au_brouillon(calepinage, layout, devis, lead, montants,
                            empreinte, *, user, journal, confirmer_taille):
    """R2-22 (D-ACAL-1) — ce calepinage devient LA conception du brouillon :
    lien, puis la resynchronisation de ventes (prix négociés, remises et notes
    préservés) ; mêmes gardes que la dédup et que la création (marché,
    montants, taille), sous la transaction de ``_generer``."""
    from apps.ventes.services import (
        SyncLayoutError, poser_layout_hash, rafraichir_etudes_du_devis,
        resynchroniser_conception,
    )

    _refuser_autre_marche(devis, lead)  # ACON90
    _refuser_montants_differents(devis, montants)  # ACON49
    _lier(calepinage, devis, user=user)
    try:
        # L'annonce ``layout_finalise`` part une fois, après la transaction.
        resultat = resynchroniser_conception(devis, layout, user, emettre=False)
    except SyncLayoutError as refus:
        raise DevisRefuse(refus.detail, champ='devis', statut=409, donnees={
            'detail': refus.detail,
            'revision_possible': refus.revision_possible}) from refus
    if (resultat or {}).get('inchange'):
        rafraichir_etudes_du_devis(devis)  # ACON85 — l'ombrage lié est servi
    _garde_taille(devis, calepinage, confirmer_taille)  # R2-17
    poser_layout_hash(devis, empreinte)
    _poser_affiche(calepinage, devis)
    if journal is not None:
        journal['avertissements'] = list((resultat or {}).get('avertissements') or ())
    return devis


def _annoncer_conception(devis, user):
    """R2-10 — ``layout_finalise`` (bus ``core.events``) APRÈS la transaction :
    l'abonné crm note « Conception 3D finalisée » au lead (auteur et société
    lus du serveur), l'abonné calepinage relit un lien déjà posé. Jamais
    bloquant ; une génération annulée (aperçu de l'assistant) n'annonce rien."""
    from django.db import transaction

    from core.events import layout_finalise

    def envoyer():
        try:
            layout_finalise.send(sender='calepinage.services.devis', devis=devis,
                                 user=user)
        except Exception:  # noqa: BLE001 — un abonné cassé ne casse pas le devis (D-ENF22-BLE001)
            logger.warning('R2-10 : abonné en échec sur layout_finalise (devis %s)',
                           getattr(devis, 'pk', None), exc_info=True)

    transaction.on_commit(envoyer)


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


def _onduleur_juge(calepinage, devis, refus=None):
    """Lane E6e (T4-X5-010) — un refus de resynchro juge l'onduleur du DEVIS ; quand
    l'étape Électrique en désigne un AUTRE, la phrase le dit et nomme les deux. T4-X7-007 —
    elle ne propose plus de désigner l'onduleur du devis (geste qui ne lève pas un refus
    jugé sur ce même onduleur) : elle nomme les gestes qui le lèvent (un autre module à
    l'étape Électrique, ou un autre onduleur dans le devis). ``''`` sinon (refus inchangé)."""
    from apps.stock.selectors import get_produit_scoped
    from apps.ventes.selectors_calepinage import lignes_produits_calepinage
    from apps.ventes.services import classer_produit

    from .electrique import entree_stockee

    try:
        designe = int((entree_stockee(calepinage) or {}).get('onduleur_produit'))
    except (TypeError, ValueError):
        return ''
    onduleurs = [li['produit'] for li in lignes_produits_calepinage(devis)
                 if (classer_produit(li['produit'].nom or li['designation']) or '').startswith('onduleur')]
    produit = get_produit_scoped(calepinage.company, designe)
    if not onduleurs or produit is None or designe in {o.pk for o in onduleurs}:
        return ''
    du_devis = onduleurs[0].nom
    from .variantes import onduleur_designe_a_la_main  # revue du 26/11 : un onduleur repris n'est pas « désigné »
    mot = 'désigné' if onduleur_designe_a_la_main(calepinage) else 'repris de l’original'
    phrase = (f" L'étape Électrique juge l'onduleur {mot} « {produit.nom} » ; ce devis porte "
              f"« {du_devis} », c'est lui que ce refus juge : désigner un onduleur à l'étape "
              f"Électrique ne le change pas.")
    if getattr(refus, 'code', '') == 'couple_incompatible':  # ventes.domain.resynchronisation.COUPLE_INCOMPATIBLE
        phrase += (f" Pour lever ce refus, choisissez un autre module à l'étape Électrique "
                   f"(Matériel électrique), ou remplacez « {du_devis} » dans le devis, puis "
                   f"resynchronisez.")
    return phrase


def _avant_resynchro(calepinage, devis_id):
    """``(variante, layout)`` — les décisions d'ENTRÉE de « Resynchroniser le devis », partagées avec
    son aperçu (ACAL1320) : feu vert, document (celui de la VARIANTE qui porte ``devis_id``),
    refus de lecture seule (409). N'écrit rien."""
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
    return variante, layout


def _devis_a_resynchroniser(calepinage, variante, layout, surfaces_chiffrees):
    """``(devis, layout)`` — le devis lié (société bornée) et le document aux surfaces chiffrées
    (ACAL968 : absentes ⇒ la sélection écrite au devis), partagés avec l'aperçu (ACAL1320)."""
    from apps.ventes.selectors import get_devis_by_pk

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
                                  is not None else _selection_du_devis(devis, variante or calepinage))
    return devis, layout


def _designations_de(porteur, *, apercu_confirme=False):
    """D-ACAL-148 / 159 / 164 — les désignations de l'étape Électrique que la resynchro (et son
    aperçu) transmet à ``ventes``, qui les juge. Revue du 26/11 (D-ACAL-73) — ``apercu_confirme`` :
    la resynchro a été confirmée sur la carte d'aperçu ; sans lui, un devis ENVOYÉ ne les reçoit pas."""
    return {'onduleur': _onduleur_designe(porteur), 'batterie': _batterie_designee(porteur),
            'apercu_confirme': bool(apercu_confirme)}


#: Revue du 26/11 — l'aperçu confirmé ne décrit plus ce que la resynchronisation écrirait (contrat
#: ``calepinage_apercu_resync.json``, ``reponse_409_apercu_perime``).
MESSAGE_APERCU_PERIME = "L'aperçu a changé depuis son affichage : relancez-le avant de confirmer."
CODE_APERCU_PERIME = 'apercu_perime'


def _exiger_apercu_a_jour(devis, layout, designations, apercu_confirme, jeton_apercu):
    """La confirmation est LIÉE à l'aperçu : ``apercu_confirme`` sans jeton ⇒ 400 nommant
    ``jeton_apercu`` ; un jeton qui ne décrit plus les entrées d'aujourd'hui ⇒ 409 ``apercu_perime``.
    Sans confirmation : rien à vérifier (les autres appelants n'appliquent rien de plus à un envoyé)."""
    if not apercu_confirme:
        return
    if not isinstance(jeton_apercu, str) or not jeton_apercu:
        raise DevisRefuse("La confirmation de l'aperçu doit renvoyer son jeton : relancez l'aperçu.",
                          champ='jeton_apercu')
    from apps.ventes.services import jeton_de_resynchronisation

    if jeton_de_resynchronisation(devis, layout, designations) != jeton_apercu:
        raise DevisRefuse(MESSAGE_APERCU_PERIME, champ='jeton_apercu', statut=409,
                          donnees={'detail': MESSAGE_APERCU_PERIME, 'code': CODE_APERCU_PERIME})


def _refus_de_resynchro(calepinage, devis, refus):
    """Le ``SyncLayoutError`` de ventes traduit en 409 du pont (``revision_possible`` compris),
    l'onduleur jugé nommé (E6e) — le même pour la resynchro et son aperçu."""
    detail = refus.detail + _onduleur_juge(calepinage, devis, refus)
    return DevisRefuse(detail, champ='devis', statut=409,
                       donnees={'detail': detail, 'revision_possible': refus.revision_possible})


def resynchroniser_devis(calepinage, *, user=None,
                         derogation_electrique=None, devis_id=None,
                         surfaces_chiffrees=None, apercu_confirme=False, jeton_apercu=None):
    """CAL25 — resynchronise le devis lié sur la conception COURANTE.

    Revue du 26/11 (D-ACAL-73) — ``apercu_confirme`` : vrai SEULEMENT quand le vendeur confirme la
    carte d'aperçu (vue ``sync-devis``) ; faux (tous les autres appelants), un devis ENVOYÉ ne reçoit
    pas l'onduleur / la batterie désignés et une phrase le dit. ``jeton_apercu`` (obligatoire avec
    ``apercu_confirme``) : le ``jeton`` de l'aperçu ; s'il ne décrit plus les entrées d'aujourd'hui,
    409 ``apercu_perime`` et rien n'est écrit.

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
    from apps.ventes.services import (
        SyncLayoutError, resynchroniser_conception)

    variante, layout = _avant_resynchro(calepinage, devis_id)
    # ACAL170 — même cliquet électrique que la génération, AVANT toute
    # écriture (un devis ENVOYÉ suit le même refus).
    garde = _garde_electrique(calepinage, derogation_electrique, user,
                              geste='resynchronisé')
    devis, layout = _devis_a_resynchroniser(calepinage, variante, layout, surfaces_chiffrees)
    designations = _designations_de(variante or calepinage, apercu_confirme=apercu_confirme)
    _exiger_apercu_a_jour(devis, layout, designations, apercu_confirme, jeton_apercu)

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
                getattr(calepinage, 'roof_image', None) or None),
            # D-ACAL-148 / 159 — la MÊME décision que « Générer le devis » (ventes la juge).
            designations=designations)
    except SyncLayoutError as refus:
        raise _refus_de_resynchro(calepinage, devis, refus) from refus
    resultat = dict(resultat or {})
    resultat['electrique'] = _consigner_et_servir(calepinage, garde,
                                                  user=user)
    return resultat
