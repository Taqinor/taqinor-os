"""Bordereau / BOQ — appariement catalogue et chiffrage d'un appel d'offres.

QJR68 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py`` : les corps
sont recopiés à l'identique, aucune ligne de logique n'a été touchée.
``services.py`` en garde un ré-export tant qu'un appelant l'y lit (le pin
``apps/ventes/tests/test_services_surface.py`` rend tout oubli visible).

DEUX RÈGLES D'IMPORT DE ``domain/`` (elles rendent le sous-paquet insensible à
l'ordre de chargement, dans les DEUX sens) :

* ``services.py`` importe les modules de ``domain/`` À LA TOUTE FIN du fichier
  — donc après que TOUTES ses définitions restantes existent ;
* un module de ``domain/`` qui a encore besoin d'un nom hébergé par
  ``services.py`` l'importe EN BAS DE FICHIER, après ses propres définitions
  (``# noqa: E402``). Que l'un ou l'autre soit importé le premier, chaque
  attribut lu à l'import existe déjà.

IMPORTS RELATIFS RE-ANCRÉS D'UN NIVEAU. Un corps qui descend d'un cran dans
l'arborescence (`apps/ventes/` → `apps/ventes/domain/`) voit son point de
départ relatif descendre avec lui : `from .models import …` désignerait
désormais `apps.ventes.domain.models`, qui n'existe pas. Toutes les lignes
concernées passent donc de `from .` à `from ..` — la MÊME cible qu'avant
(`apps.ventes.…`), au caractère près. C'est la seule retouche que subit un
corps déplacé, et elle est purement mécanique.

NOM DU LOGGER FIGÉ. ``logging.getLogger('apps.ventes.services')`` — et non
``__name__`` — parce que des tests capturent ce nom précis
(``assertLogs('apps.ventes.services')`` dans ``test_calepinage_bascule.py`` et
``test_pv42_boucle_electrique.py``). Un déplacement pur ne change pas non plus
le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal
import logging
import re

logger = logging.getLogger("apps.ventes.services")


# ═════════════════════════════════════════════════════════════════════════════
# PV47 — Le BORDEREAU électrique en LIGNES DE DEVIS (opt-in, jamais silencieux)
# ═════════════════════════════════════════════════════════════════════════════
# La conception électrique (PV41) produit un bordereau TECHNIQUE : câbles,
# fusibles, parafoudres, sectionneurs, disjoncteurs, différentiels, coffrets.
# Le devis, lui, porte des lignes CHIFFRÉES. Le pont entre les deux est
# DÉLIBÉRÉMENT un geste explicite de l'utilisateur (une action, un clic) et
# jamais un effet de bord d'un recalcul d'étude : sans cela, chaque
# re-conception ferait bouger le prix d'un devis sous les yeux du client.
#
# Deux issues par ligne de bordereau, aucune troisième :
#   * un produit du catalogue correspond → ligne PRODUIT à SON prix. Les SKU
#     PVG3 (câbles/protections) ont un prix VIDE tant que le fondateur ne les a
#     pas renseignés : la ligne part donc à 0 et son intitulé le DIT
#     (« — à chiffrer »). On n'invente jamais un prix ;
#   * aucun produit ne correspond → ligne de NOTE « à chiffrer », sans produit
#     ni prix, ET la ligne est reportée dans les MANQUES du catalogue (c'est la
#     donnée qui dit au fondateur ce qu'il lui reste à référencer).
#
# Les lignes de bordereau NON électriques (structure : rails, pinces, crochets)
# sont IGNORÉES : elles relèvent des postes « Structures & fixation » que le
# devis compose déjà, et les recopier en notes ne ferait que du bruit.

#: Catégories catalogue où l'on cherche une correspondance (taxonomie de
#: ``stock.seed_catalogue.TAXONOMIE``).
BOQ_CATEGORIES = ('Câbles', 'Protection & accessoires')

#: Familles d'organes reconnues, du motif le plus SPÉCIFIQUE au plus général —
#: le PREMIER motif satisfait gagne. L'ordre est porteur de sens :
#: « porte-fusible » avant « fusible » (sinon tout porte-fusible serait classé
#: fusible), « sectionneur-fusible » avant « fusible » de même, et les CÂBLES
#: sont éclatés par usage : un câble solaire DC et un câble AC U-1000 R2V ont
#: la même section possible mais ne sont PAS interchangeables.
#: Chaque motif est un tuple de fragments dont TOUS doivent être présents.
#: Une désignation sans famille connue est ignorée (lignes de structure).
_BOQ_FAMILLES = (
    ('porte_fusible', (('porte-fusible',), ('porte fusible',))),
    ('sectionneur', (('sectionneur',),)),
    ('fusible', (('fusible',),)),
    ('cable_solaire', (('cable', 'solaire'), ('cable', 'h1z2z2'))),
    ('cable_terre', (('cable', 'terre'),)),
    ('cable_batterie', (('cable', 'batterie'),)),
    ('cable_ac', (('cable', 'u-1000'), ('cable', 'r2v'))),
    ('cable', (('cable',),)),
    ('parafoudre', (('parafoudre',),)),
    ('differentiel', (('differentiel',), ('ddr',))),
    ('disjoncteur', (('disjoncteur',),)),
    ('coffret', (('coffret',),)),
)

#: Familles pour lesquelles la SECTION (mm²) est la grandeur dimensionnante.
_BOQ_FAMILLES_CABLE = frozenset({
    'cable_solaire', 'cable_terre', 'cable_batterie', 'cable_ac', 'cable'})

#: Familles pour lesquelles le CALIBRE (A) est la grandeur dimensionnante — et
#: donc une CONDITION d'appariement. Un parafoudre ou un coffret, eux, ne se
#: choisissent pas au calibre : exiger une égalité d'ampères sur eux
#: fabriquerait de faux manques (le coffret AC porte le calibre du disjoncteur
#: qu'il abrite, pas le sien).
_BOQ_FAMILLES_CALIBREES = frozenset({
    'fusible', 'porte_fusible', 'sectionneur', 'disjoncteur', 'differentiel'})

#: Suffixe apposé à toute ligne que le catalogue ne sait pas encore chiffrer.
BOQ_SUFFIXE_A_CHIFFRER = ' — à chiffrer'

_BOQ_NOMBRE_RE = re.compile(r'\d+(?:[.,]\d+)?')


def _boq_normaliser(texte):
    """Minuscules sans accents — la comparaison ne dépend pas d'un « é »."""
    texte = (texte or '').lower()
    for source, cible in (('é', 'e'), ('è', 'e'), ('ê', 'e'), ('â', 'a'),
                          ('à', 'a'), ('î', 'i'), ('ï', 'i'), ('ô', 'o'),
                          ('û', 'u'), ('ù', 'u'), ('ç', 'c'), ('²', '2')):
        texte = texte.replace(source, cible)
    return texte


def _boq_famille(texte):
    """Famille d'organe d'une désignation, ou ``None`` si non électrique."""
    normalise = _boq_normaliser(texte)
    for famille, motifs in _BOQ_FAMILLES:
        for motif in motifs:
            if all(fragment in normalise for fragment in motif):
                return famille
    return None


def _boq_polarite(texte):
    """``'mono'`` / ``'tri'`` / ``None`` — nombre de pôles d'un organe AC.

    Le moteur écrit « bipolaire »/« tétrapolaire » (NF C 15-100), le catalogue
    « monophasé »/« tétrapolaire », et la tension réseau tranche aussi
    (230 V ↔ 400 V). Poser un tétrapolaire sur du monophasé n'est pas une
    approximation de prix : c'est un organe qui ne se câble pas.
    """
    normalise = _boq_normaliser(texte)
    if any(motif in normalise for motif in
           ('triphas', 'tetrapolaire', '400 v', ' 4p')):
        return 'tri'
    if any(motif in normalise for motif in
           ('monophas', 'bipolaire', '230 v', ' 1p')):
        return 'mono'
    return None


def _boq_nombres(texte):
    """Les nombres d'un texte, normalisés (« 6,0 mm² » et « 6 mm² » → 6)."""
    valeurs = set()
    for brut in _BOQ_NOMBRE_RE.findall(_boq_normaliser(texte)):
        try:
            valeurs.add(float(brut.replace(',', '.')))
        except ValueError:
            continue
    return valeurs


def _boq_courant(texte):
    """Le CALIBRE en ampères d'un texte (« 32 A »), ou ``None``."""
    trouve = re.search(r'(\d+(?:[.,]\d+)?)\s*a\b', _boq_normaliser(texte))
    if not trouve:
        return None
    try:
        return float(trouve.group(1).replace(',', '.'))
    except ValueError:
        return None


def _boq_section(texte):
    """La SECTION en mm² d'un texte (« 6,0 mm² »), ou ``None``."""
    trouve = re.search(r'(\d+(?:[.,]\d+)?)\s*mm2', _boq_normaliser(texte))
    if not trouve:
        return None
    try:
        return float(trouve.group(1).replace(',', '.'))
    except ValueError:
        return None


def _boq_courant_alternatif(texte):
    """``True`` (AC) / ``False`` (DC) / ``None`` — discriminant d'un organe.

    Un parafoudre DC posé à la place d'un parafoudre AC n'est pas une
    approximation, c'est une erreur de dossier : le discriminant est donc une
    CONDITION de correspondance, jamais un simple critère de tri.
    """
    normalise = _boq_normaliser(texte)
    a_dc = bool(re.search(r'\bdc\b|\bvdc\b', normalise))
    a_ac = bool(re.search(r'\bac\b', normalise))
    if a_dc and not a_ac:
        return False
    if a_ac and not a_dc:
        return True
    return None


def _boq_candidats(company):
    """Produits catalogue quotables des catégories du bordereau.

    Portée identique à ``_pick_product`` (PV15) : société de l'utilisateur OU
    catalogue global — jamais celui d'un autre tenant.
    """
    from django.db.models import Q
    from apps.stock.models import Produit

    filtre = Q(company=company) | Q(company__isnull=True)
    qs = Produit.objects.filter(
        filtre, categorie__nom__in=BOQ_CATEGORIES, is_archived=False)
    return list(qs.select_related('categorie').order_by('nom'))


def _boq_apparier(designation, spec, candidats):
    """Produit catalogue correspondant à une ligne de bordereau, ou ``None``.

    Quatre conditions CUMULATIVES :

    1. même FAMILLE d'organe (câble solaire, câble AC, fusible, parafoudre…) ;
    2. même nature de courant quand les deux la portent (un parafoudre DC ne
       remplace pas un parafoudre AC) ;
    3. même POLARITÉ quand les deux la portent (un tétrapolaire ne se câble
       pas sur du monophasé) ;
    4. même grandeur DIMENSIONNANTE quand la ligne en porte une — la section
       pour un câble, le calibre en ampères pour un organe de coupure. Une
       ligne calibrée sans calibre correspondant au catalogue N'EST PAS
       appariée : proposer un 15 A à la place d'un 16 A calculé serait une
       erreur d'étude déguisée en commodité.
    """
    famille = _boq_famille(designation)
    if famille is None:
        return None
    texte = '%s %s' % (designation or '', spec or '')
    alternatif = _boq_courant_alternatif(texte)
    polarite = _boq_polarite(texte)
    section = (_boq_section(designation)
               if famille in _BOQ_FAMILLES_CABLE else None)
    calibre = (_boq_courant(spec) or _boq_courant(designation)
               if famille in _BOQ_FAMILLES_CALIBREES else None)

    meilleur = None
    meilleur_score = None
    for produit in candidats:
        nom = produit.nom or ''
        if _boq_famille(nom) != famille:
            continue
        nature = _boq_courant_alternatif(nom)
        if alternatif is not None and nature is not None \
                and nature != alternatif:
            continue
        pole = _boq_polarite(nom)
        if polarite is not None and pole is not None and pole != polarite:
            continue
        if section is not None:
            if _boq_section(nom) != section:
                continue
        elif calibre is not None:
            if _boq_courant(nom) != calibre:
                continue
        # À conditions égales, le nom au recouvrement de nombres le plus
        # large gagne, puis le plus court (le moins spécifié inutilement).
        score = (len(_boq_nombres(nom) & _boq_nombres(texte)), -len(nom))
        if meilleur_score is None or score > meilleur_score:
            meilleur_score = score
            meilleur = produit
    return meilleur


def _boq_prix(produit):
    try:
        return Decimal(str(getattr(produit, 'prix_vente', 0) or 0))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal('0')


def ajouter_lignes_boq_electrique(devis, user=None):
    """PV47 — ajoute au devis les lignes issues du bordereau électrique (PV41).

    Rend TOUJOURS le même dict ``{creees, lignes, manques, deja_presentes}`` :

    * ``creees`` — nombre de lignes ajoutées ;
    * ``lignes`` — une entrée par ligne créée (``designation``, ``produit``,
      ``quantite``, ``type_ligne``, ``a_chiffrer``) ;
    * ``manques`` — les lignes de bordereau qu'AUCUN produit du catalogue ne
      couvre. C'est la liste de courses du référencement, pas une erreur ;
    * ``deja_presentes`` — lignes ignorées parce que le devis les portait déjà
      (garde anti-double-clic : ré-appeler l'action ne duplique rien).

    N'écrit QUE des lignes : ni statut, ni prix inventé (règle #4). Un produit
    sans prix part à 0 avec « à chiffrer » dans son intitulé — visible à
    l'écran comme sur le PDF.
    """
    from django.db import transaction
    from ..models import LigneDevis

    design = getattr(devis, 'electrical_design', None)
    bom = (design or {}).get('bom') if isinstance(design, dict) else None
    if not isinstance(bom, list) or not bom:
        return {'creees': 0, 'lignes': [], 'manques': [], 'deja_presentes': []}

    candidats = _boq_candidats(devis.company)
    lignes_existantes = list(devis.lignes.all())
    existantes = {(li.designation or '').strip() for li in lignes_existantes}
    ordre = max([int(li.ordre or 0) for li in lignes_existantes] or [0]) + 1

    creees = []
    manques = []
    deja = []
    with transaction.atomic():
        for item in bom:
            if not isinstance(item, dict):
                continue
            designation = (item.get('designation') or '').strip()
            if not designation or _boq_famille(designation) is None:
                continue
            spec = item.get('spec') or ''
            produit = _boq_apparier(designation, spec, candidats)
            a_chiffrer = produit is None or _boq_prix(produit) <= 0
            intitule = (designation + (BOQ_SUFFIXE_A_CHIFFRER
                                       if a_chiffrer else ''))[:255]
            if intitule in existantes:
                deja.append(designation)
                continue
            try:
                quantite = (Decimal(str(item.get('quantite')))
                            if item.get('quantite') not in (None, '')
                            else Decimal('1'))
            except (ArithmeticError, TypeError, ValueError):
                quantite = Decimal('1')

            if produit is None:
                manques.append({'designation': designation,
                                'quantite': float(quantite), 'spec': spec})
                creer_ligne(
                    devis, produit=None, designation=intitule,
                    quantite=None, prix_unitaire=None, remise=Decimal('0'),
                    taux_tva=None, type_ligne=LigneDevis.TypeLigne.NOTE,
                    ordre=ordre)
                creees.append({'designation': intitule, 'produit': None,
                               'quantite': None, 'type_ligne': 'note',
                               'a_chiffrer': True})
            else:
                creer_ligne(
                    devis, produit=produit, designation=intitule,
                    quantite=quantite, prix_unitaire=_boq_prix(produit),
                    remise=Decimal('0'), taux_tva=None,
                    type_ligne=LigneDevis.TypeLigne.PRODUIT, ordre=ordre)
                creees.append({'designation': intitule, 'produit': produit.pk,
                               'quantite': float(quantite),
                               'type_ligne': 'produit',
                               'a_chiffrer': a_chiffrer})
            existantes.add(intitule)
            ordre += 1

    if creees:
        logger.info('PV47 — %d ligne(s) de bordereau électrique ajoutées au '
                    'devis %s par %s', len(creees), devis.pk, user)
    return {'creees': len(creees), 'lignes': creees, 'manques': manques,
            'deja_presentes': deja}


# ── QJR76 : la CONCEPTION électrique rejoint le bordereau qu'elle produit ────
# `concevoir_electrique_du_devis` (PV41) écrit `devis.electrical_design`, dont
# le bloc `bom` est exactement ce que lit `ajouter_lignes_boq_electrique`
# (PV47, plus haut). Les deux moitiés de la même chaîne vivent désormais dans
# le même module.
def concevoir_electrique_du_devis(devis, *, origine=''):
    """PV42 — enchaîne la conception ÉLECTRIQUE derrière le calepinage, SANS
    jamais pouvoir casser le devis.

    Le calepinage vient d'être rangé dans ``roof_layout`` : ses pans
    (``_pans_geometry``) sont exactement ce que ``electrical_service`` attend
    pour composer UN GROUPE DE CHAÎNES PAR PAN — deux orientations ne partagent
    jamais une entrée MPPT (le moteur PV34 le refuse structurellement).

    **Meilleur effort, et c'est structurel** : une panne d'étude électrique est
    une pièce technique manquante, jamais une création (ou une resynchro) de
    devis perdue. Toute exception est journalisée et avalée, et la fonction rend
    ``None``. Elle n'écrit que ``electrical_design``/``electrical_design_hash``
    (règle #4 : aucun statut, aucune ligne, aucun prix).
    """
    try:
        from apps.ventes import electrical_service
        return electrical_service.build_electrical_design(devis)
    except Exception:
        logger.warning(
            'PV42: conception électrique indisponible pour le devis %s (%s) — '
            'le devis est intact, la pièce technique sera recalculée à la '
            'demande', getattr(devis, 'reference', '?'), origine or 'layout',
            exc_info=True)
        return None


# ── PONT M3 : nom hébergé ailleurs ───────────────────────────────────────────
# Import EN BAS DE FICHIER (voir la docstring) : il s'exécute après toutes les
# définitions de ce module, donc ``services.py`` peut le ré-exporter sans jamais
# lire un module à moitié construit. Il vise le module qui PORTE le corps
# (QJR75 a sorti ``refresh_marge_snapshot`` vers ``domain/etudes.py``) et non la
# façade : les ré-exports de ``services.py`` s'exécutent dans l'ordre des
# tâches, donc le bloc QJR68 ne porte pas encore les noms de QJR75.
from apps.ventes.domain.etudes import refresh_marge_snapshot  # noqa: E402,F401
# QJR84 — l'écrivain unique des lignes (le seul constructeur de LigneDevis).
from apps.ventes.domain.lignes import creer_ligne  # noqa: E402,F401
