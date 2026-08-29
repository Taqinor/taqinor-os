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
from decimal import Decimal, ROUND_HALF_UP
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
                LigneDevis.objects.create(
                    devis=devis, produit=None, designation=intitule,
                    quantite=None, prix_unitaire=None, remise=Decimal('0'),
                    taux_tva=None, type_ligne=LigneDevis.TypeLigne.NOTE,
                    ordre=ordre)
                creees.append({'designation': intitule, 'produit': None,
                               'quantite': None, 'type_ligne': 'note',
                               'a_chiffrer': True})
            else:
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=intitule,
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


# ═══════════════════════════════════════════════════════════════════════════
# UN SEUL chemin de chiffrage : bordereau d'appel d'offres → devis ventes
# ═══════════════════════════════════════════════════════════════════════════
#
# POURQUOI ICI. ``apps.ao`` porte le bordereau des prix (BOQ : sections,
# lignes, TVA par ligne, remise globale, clause de réserve) mais n'a AUCUN lien
# avec le moteur de devis : un chiffrage d'AO se re-saisissait donc à la main
# pour sortir un devis client. Ce service est le POINT DE CONTACT UNIQUE de la
# traversée, symétrique exact de ``apps.ao.services.creer_appel_offre_depuis_
# avis`` : le domaine AO appelle CETTE fonction (jamais ``apps.ventes.models``)
# et le devis produit repart ensuite dans le pipeline devis NORMAL — PDF
# ``/proposal`` compris (règle #4 : aucun autre chemin de PDF client, et rien
# n'est touché dans ``quote_engine``).
#
# ``bordereau`` est reçu PAR RÉFÉRENCE et lu en CANARD : ``ventes`` n'importe
# jamais ``apps.ao.models`` (contrat import-linter). On ne lit que des
# attributs publics déjà documentés du BOQ.

#: Le devis porte une quantité au CENTIÈME, le bordereau au MILLIÈME. L'écart
#: est ANNONCÉ (jamais silencieux) : une quantité arrondie change un total.
_QUANTUM_QUANTITE = Decimal('0.01')
#: ``LigneDevis.prix_unitaire`` = 10 chiffres significatifs ; le BOQ en accepte
#: 14. Un P.U. hors gabarit ferait échouer l'écriture en base — on saute la
#: ligne et on le DIT, plutôt que de perdre tout le devis sur une seule ligne.
_PU_DEVIS_MAX = Decimal('99999999.99')
#: MÊME gabarit pour la QUANTITÉ (``LigneDevis.quantite`` : max_digits=10,
#: decimal_places=2) — alors que ``LigneBordereau.quantite`` accepte
#: max_digits=12/decimal_places=3, soit jusqu'à 999 999 999,999. Une ligne
#: « Terrassement » à 150 000 000 m³ faisait donc lever un ``numeric field
#: overflow`` DANS la transaction de ``create_with_reference`` → 500 muet (le
#: ``except`` de la vue n'attrape que ``DjangoValidationError``), au lieu de
#: l'avertissement français que le module promet pour « tout ce que le serveur
#: n'a PAS pu reprendre à l'identique ». Le P.U. était gardé, pas la quantité.
_QUANTITE_DEVIS_MAX = Decimal('99999999.99')


def _designation_ligne_bordereau(ligne):
    """Désignation du devis pour une ligne de BOQ, unité comprise.

    ``LigneDevis`` ne porte pas de colonne « unité » : la laisser tomber
    rendrait « 300 » ambigu (300 mètres linéaires ou 300 unités ?) sur un
    marché à prix unitaires, où c'est précisément l'unité qui engage. On la
    reporte donc dans la désignation, sauf pour l'unité par défaut ``U`` qui
    n'apprend rien.
    """
    designation = (ligne.designation or '').strip()
    unite = (ligne.unite or '').strip()
    if unite and unite.upper() != 'U':
        designation = f'{designation} ({unite})'
    return designation[:255]


def _signature_lignes_devis(devis):
    """Empreinte COMPARABLE des lignes d'un devis, dans l'ordre d'affichage.

    Même forme que les specs de ``creer_devis_depuis_bordereau`` : ce qui
    permet de dire, sans heuristique, si le brouillon dit encore la même chose
    que le bordereau. Les montants sont normalisés au centième (une même valeur
    écrite ``12`` ou ``12.00`` ne doit pas passer pour une divergence)."""
    def _q(valeur):
        if valeur is None:
            return None
        try:
            return Decimal(str(valeur)).quantize(Decimal('0.01'),
                                                 rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, ArithmeticError):
            return None

    return [
        (ligne.type_ligne, (ligne.designation or ''), ligne.produit_id,
         _q(ligne.quantite), _q(ligne.prix_unitaire), _q(ligne.remise),
         _q(ligne.taux_tva))
        for ligne in devis.lignes.all().order_by('ordre', 'id')
    ]


def _signature_specs_bordereau(a_ecrire):
    """La MÊME empreinte, côté bordereau (specs pas encore écrites)."""
    def _q(valeur):
        if valeur is None:
            return None
        try:
            return Decimal(str(valeur)).quantize(Decimal('0.01'),
                                                 rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, ArithmeticError):
            return None

    return [
        (spec['type_ligne'], spec['designation'], spec['produit_id'],
         _q(spec['quantite']), _q(spec['prix_unitaire']), _q(spec['remise']),
         _q(spec['taux_tva']))
        for spec in sorted(a_ecrire, key=lambda s: s['ordre'])
    ]


def _reouvrir_devis_depuis_bordereau(devis, *, bordereau, a_ecrire, origine,
                                     avertissements):
    """Rouvre le brouillon déjà issu de ce bordereau — RAFRAÎCHI s'il diverge.

    Un brouillon n'engage personne : quand le bordereau a bougé (lignes, P.U.,
    quantités, TVA, remise globale, clause de réserve), ses lignes sont
    réécrites depuis le bordereau et l'écran le DIT. Identique ⇒ ZÉRO écriture,
    donc un double-clic reste un no-op complet. Le statut n'est ni lu comme
    modifiable ni écrit (règle #4) : le queryset appelant a déjà borné à
    ``brouillon``."""
    from django.db import transaction

    from apps.ventes.models import LigneDevis

    memes_lignes = (_signature_lignes_devis(devis)
                    == _signature_specs_bordereau(a_ecrire))
    memes_entetes = (
        Decimal(devis.taux_tva or 0)
        == Decimal(bordereau.taux_tva_defaut or 20)
        and Decimal(devis.remise_globale or 0)
        == Decimal(bordereau.remise_globale_pct or 0))

    if memes_lignes and memes_entetes:
        return (devis, {
            'cree': False,
            'lignes': devis.lignes.count(),
            'avertissements': avertissements + [
                'Un devis brouillon issu de ce bordereau existait déjà : il '
                "est réouvert, aucun doublon n'a été créé."],
        })

    with transaction.atomic():
        devis.lignes.all().delete()
        for spec in a_ecrire:
            LigneDevis.objects.create(devis=devis, **spec)
        devis.taux_tva = Decimal(bordereau.taux_tva_defaut or 20)
        devis.remise_globale = Decimal(bordereau.remise_globale_pct or 0)
        etude = dict(devis.etude_params or {})
        etude['origine'] = origine
        devis.etude_params = etude
        # ``update_fields`` EXCLUT ``statut`` (règle #4).
        devis.save(update_fields=['taux_tva', 'remise_globale',
                                  'etude_params'])
    refresh_marge_snapshot(devis)
    logger.info(
        'Devis %s RAFRAÎCHI depuis le bordereau %s (%d ligne(s))',
        devis.reference, bordereau.pk, len(a_ecrire))
    return (devis, {
        'cree': False,
        'lignes': len(a_ecrire),
        'avertissements': avertissements + [
            'Un devis brouillon issu de ce bordereau existait déjà et le '
            'bordereau a changé depuis : ce devis existant a été MIS À JOUR '
            "depuis le bordereau (aucun doublon n'a été créé)."],
    })


def creer_devis_depuis_bordereau(bordereau, *, user=None, company=None,
                                 client=None):
    """Construit un DEVIS ventes standard à partir d'un bordereau des prix AO.

    Le devis reprend la structure du BOQ à l'identique : une ligne de SECTION
    (intertitre XSAL14) par section du bordereau, puis ses lignes chiffrées
    dans leur ordre de numérotation, avec la TVA de la ligne
    (``taux_tva_effectif``), sa remise de ligne, sa quantité et son P.U. La
    remise GLOBALE et le taux de TVA par défaut du bordereau deviennent ceux du
    devis : la chaîne « sous-total HT → remise → TVA → TTC » est donc la MÊME
    des deux côtés, par construction et non par recopie.

    Le client est résolu CÔTÉ SERVEUR : ``client`` fourni, sinon le lead
    rattaché à l'affaire (``crm.selectors`` puis ``crm.services``, sans jamais
    créer de doublon). Sans l'un ni l'autre, une ``ValidationError`` FRANÇAISE
    nomme le geste qui débloque (rattacher un lead à l'affaire) — inventer un
    client serait pire qu'un refus.

    IDEMPOTENT : un brouillon déjà issu de CE bordereau est réouvert au lieu
    d'être dupliqué (un double clic ne crée pas deux devis) — mais RAFRAÎCHI
    quand le bordereau a bougé depuis (fondateur 2026-08-18). Le renvoyer tel
    quel « en affirmant qu'il en est issu » laissait l'utilisateur repartir avec
    un devis client périmé : il corrigeait un prix au bordereau, recliquait
    « Créer le devis », lisait « aucun doublon créé » — et le devis gardait
    l'ANCIEN total pour toujours, l'écran n'offrant aucun autre geste. Un
    BROUILLON n'engage personne : ses lignes sont donc réécrites depuis le
    bordereau, et l'écran le DIT.

    La numérotation passe TOUJOURS par ``create_with_reference``
    (``core.numbering``) — JAMAIS ``count()+1``. Le devis reste ``brouillon`` :
    ce service CRÉE, il ne change aucun statut aval (règle #4).

    Rend ``(devis, rapport)`` où ``rapport`` vaut
    ``{'cree': bool, 'lignes': int, 'avertissements': [str, …]}``.
    """
    from django.core.exceptions import ValidationError

    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.references import create_with_reference

    if bordereau is None:
        raise ValidationError({'bordereau': 'Bordereau introuvable.'})

    affaire = bordereau.appel_offre
    company = company or bordereau.company

    # ── Le client : jamais inventé, jamais dupliqué ──
    lead = None
    if client is None:
        from apps.crm.selectors import get_company_lead
        from apps.crm.services import resolve_client_for_lead

        lead = get_company_lead(company, getattr(affaire, 'lead_id', None))
        if lead is None:
            raise ValidationError({'client': (
                "Cette affaire n'est rattachée à aucun lead : un devis a "
                'toujours un client. Rattachez un lead à l\'affaire (action '
                '« rattacher-lead ») ou indiquez le client, puis relancez.'
            )})
        client = resolve_client_for_lead(lead)

    # ── Les lignes, dans l'ORDRE du bordereau ──
    sections = list(bordereau.sections.all())
    lignes_bordereau = list(bordereau.lignes.all())
    par_section = {}
    for ligne in lignes_bordereau:
        # Le bordereau est DÉJÀ chargé : on garnit le cache de la FK pour que
        # ``taux_tva_effectif`` (repli sur le taux du bordereau) reste la SEULE
        # source de vérité du taux, sans une requête par ligne.
        ligne.bordereau = bordereau
        par_section.setdefault(ligne.section_id, []).append(ligne)
    for groupe in par_section.values():
        groupe.sort(key=lambda li: (li.numero or 0, li.pk))

    avertissements = []
    a_ecrire = []
    ordre = 0

    def _ajouter_ligne(ligne):
        nonlocal ordre
        prix = Decimal(ligne.prix_unitaire or 0)
        if abs(prix) > _PU_DEVIS_MAX:
            avertissements.append(
                'Ligne %s « %s » : prix unitaire hors gabarit du devis — la '
                'ligne a été écartée.' % (ligne.numero, ligne.designation))
            return
        brute = Decimal(ligne.quantite or 0)
        if abs(brute) > _QUANTITE_DEVIS_MAX:
            avertissements.append(
                'Ligne %s « %s » : quantité hors gabarit du devis (%s) — la '
                'ligne a été écartée.'
                % (ligne.numero, ligne.designation, brute))
            return
        quantite = brute.quantize(_QUANTUM_QUANTITE, rounding=ROUND_HALF_UP)
        if quantite != brute:
            avertissements.append(
                'Ligne %s « %s » : quantité %s arrondie à %s (le devis compte '
                'au centième, le bordereau au millième).'
                % (ligne.numero, ligne.designation, brute, quantite))
        a_ecrire.append({
            # ``produit_id`` et non ``produit`` : la string-FK catalogue est
            # recopiée telle quelle, sans charger un Produit par ligne.
            'produit_id': ligne.produit_id,
            'designation': _designation_ligne_bordereau(ligne),
            'quantite': quantite,
            'prix_unitaire': prix,
            'remise': Decimal(ligne.remise_pct or 0),
            'taux_tva': Decimal(ligne.taux_tva_effectif),
            'type_ligne': LigneDevis.TypeLigne.PRODUIT,
            'ordre': ordre,
        })
        ordre += 1

    for section in sections:
        groupe = par_section.get(section.pk) or []
        if not groupe:
            continue
        intitule = ' — '.join(
            part for part in [(section.numero or '').strip(),
                              (section.libelle or '').strip()] if part)
        a_ecrire.append({
            'produit_id': None,
            'designation': (intitule or 'Section')[:255],
            'quantite': None,
            'prix_unitaire': None,
            'remise': Decimal('0'),
            'taux_tva': None,
            'type_ligne': LigneDevis.TypeLigne.SECTION,
            'ordre': ordre,
        })
        ordre += 1
        for ligne in groupe:
            _ajouter_ligne(ligne)

    # Les lignes SANS section ferment le devis — jamais perdues en silence.
    for ligne in par_section.get(None) or []:
        _ajouter_ligne(ligne)

    if not any(spec['type_ligne'] == LigneDevis.TypeLigne.PRODUIT
               for spec in a_ecrire):
        raise ValidationError({'bordereau': (
            "Ce bordereau ne porte aucune ligne chiffrable : il n'y a rien à "
            'reprendre dans un devis.'
        )})

    # ── CLAUSE DE RÉSERVE — elle traverse, sinon le devis ment ──
    #
    # ``BordereauPrix.raisons_de_non_conformite()`` REFUSE de rendre remettable
    # un bordereau « marché à prix unitaires » sans clause de réserve, avec ce
    # motif : « sans elle, les quantités du bordereau sont lues comme un
    # engagement ferme ». Le devis reprenait les quantités… et laissait la
    # clause derrière lui : le document remis au CLIENT contredisait celui remis
    # à l'ACHETEUR sur la nature même de l'engagement. Elle voyage désormais
    # deux fois — en ligne NOTE visible (XSAL14, hors totaux) et dans
    # ``etude_params.origine`` pour tout consommateur machine.
    clause = (getattr(bordereau, 'clause_reserve', '') or '').strip()
    if clause:
        a_ecrire.append({
            'produit_id': None,
            'designation': clause[:255],
            'quantite': None,
            'prix_unitaire': None,
            'remise': Decimal('0'),
            'taux_tva': None,
            'type_ligne': LigneDevis.TypeLigne.NOTE,
            'ordre': ordre,
        })
        ordre += 1

    origine = {
        'type': 'bordereau_ao',
        'bordereau': bordereau.pk,
        'appel_offre': getattr(affaire, 'pk', None),
        'reference_ao': getattr(affaire, 'reference', '') or '',
        'intitule': bordereau.intitule or '',
        'indice_revision': bordereau.indice_revision or '',
        'marche_prix_unitaires': bool(
            getattr(bordereau, 'marche_prix_unitaires', False)),
        'clause_reserve': clause,
    }

    # ── Idempotence : le MÊME bordereau ne produit qu'UN brouillon ──
    # Placée APRÈS la construction des lignes : c'est elle qui permet de
    # COMPARER l'existant au bordereau d'aujourd'hui plutôt que de le renvoyer
    # les yeux fermés.
    existant = Devis.objects.filter(
        company=company, statut=Devis.Statut.BROUILLON,
        etude_params__origine__bordereau=bordereau.pk).order_by('pk').first()
    if existant is not None:
        return _reouvrir_devis_depuis_bordereau(
            existant, bordereau=bordereau, a_ecrire=a_ecrire, origine=origine,
            avertissements=avertissements)

    def _creer(reference):
        devis = Devis.objects.create(
            company=company,
            reference=reference,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal(bordereau.taux_tva_defaut or 20),
            remise_globale=Decimal(bordereau.remise_globale_pct or 0),
            created_by=user,
            etude_params={'origine': origine},
        )
        for spec in a_ecrire:
            LigneDevis.objects.create(devis=devis, **spec)
        return devis

    devis = create_with_reference(Devis, 'DEV', company, _creer)
    # QX23be — fige la marge interne dès la création, comme tout autre chemin
    # de création de devis (best-effort, jamais bloquant, manager-only).
    refresh_marge_snapshot(devis)
    logger.info(
        'Devis %s créé depuis le bordereau %s (affaire %s, %d ligne(s)) par %s',
        devis.reference, bordereau.pk, origine['reference_ao'],
        len(a_ecrire), user)
    return (devis, {'cree': True, 'lignes': len(a_ecrire),
                    'avertissements': avertissements})


def resume_devis_depuis_bordereau(devis):
    """Bloc ``devis`` du contrat ``ao_bordereau_devis`` — totaux SERVEUR.

    Les montants passent par la chaîne canonique unique
    (``selectors._canonical_totaux`` : HT brut → remise globale → TVA par taux
    → TTC), celle-là même que l'écran et le PDF consomment. Aucun total n'est
    recalculé ailleurs, donc aucun ne peut diverger.
    """
    from apps.ventes.selectors import _canonical_totaux

    totaux = _canonical_totaux(
        devis.lignes.all(), remise_globale_pct=devis.remise_globale,
        fallback_taux=devis.taux_tva)
    client = getattr(devis, 'client', None)
    return {
        'id': devis.pk,
        'reference': devis.reference,
        'statut': devis.statut,
        'client': devis.client_id,
        'client_nom': (getattr(client, 'nom', '') or '') if client else '',
        'lignes': devis.lignes.count(),
        'total_ht': str(totaux['ht_net']),
        'total_ttc': str(totaux['ttc']),
    }


# ── PONT M3 : noms encore hébergés par ``services.py`` ───────────────────────
# Import EN BAS DE FICHIER (voir la docstring) : il s'exécute après toutes les
# définitions de ce module, donc ``services.py`` peut le ré-exporter sans
# jamais lire un module à moitié construit. ``refresh_marge_snapshot`` partira
# vers ``domain/etudes.py`` en QJR75 ; ce pont continuera de le trouver via le
# ré-export de ``services.py``.
from apps.ventes.services import refresh_marge_snapshot  # noqa: E402,F401
