"""Lignes du devis — les lire, et l'ÉCRIVAIN UNIQUE qui les remplace.

Deux moitiés qui vivaient séparées et se rejoignent ici.

LA LECTURE (déplacée de `services.py`) : les lignes produit d'un devis,
leur classe, les lignes d'une variante, l'option réellement servable et
`cible_depuis_lignes` — la dérivation compte × wattage d'une variante,
CORRIGÉE en QJR33 et déplacée ici TELLE QUELLE (rien n'a été re-corrigé).

L'ÉCRITURE (déplacée de `views/devis.py`) : `remplacer_lignes`, l'ancien
`DevisViewSet._replace_lines_atomic`. Les tests le décrivaient déjà comme
« le SEUL chemin d'écriture » des lignes alors qu'il vivait dans le
ViewSet — donc hors d'atteinte de tout autre appelant — pendant que
`services.py` créait des `LigneDevis` en direct sur 14 sites. Il vit
désormais où l'on peut l'appeler. LES 14 SITES SONT INCHANGÉS ICI : leur
convergence est QJR84.

QJR73 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal


# ── PV16 — la CIBLE de calepinage se lit dans les LIGNES du devis ───────────
#
# L'écran de conception 3D doit repartir de ce que le devis DIT AUJOURD'HUI
# (combien de panneaux, quelle puissance unitaire, quel scénario), pas d'un
# blob de layout qui peut être absent, périmé ou d'une version antérieure de
# l'outil. Les lignes du devis, elles, sont la source vivante — c'est ce qui a
# été chiffré et, pour un devis envoyé, ce que le client a sous les yeux.
#
# Fonction PURE de lecture : elle ne touche NI le statut, NI les lignes, NI
# l'étude. Elle expose ses doutes plutôt que de les cacher — d'où la liste
# ``avertissements`` en français, affichable telle quelle.

#: Wattage retenu quand plus rien n'est lisible (panneau catalogue courant).
CIBLE_WATT_DEFAUT = 550


def _lignes_produit(devis):
    """Lignes PRODUIT d'un devis — les sections/notes n'en sont pas.

    Une ligne de SECTION/NOTE (XSAL14) ne porte ni produit, ni prix, ni
    quantité : elle ne peut donc ni compter dans une cible ni recevoir un
    écart de calepinage.
    """
    if devis is None:
        return []
    return [ligne for ligne in devis.lignes.all()
            if getattr(ligne, 'type_ligne', 'produit') == 'produit']


def _classe_ligne(ligne, predicat):
    """Classe une ligne sur sa DÉSIGNATION, à défaut sur le nom du produit.

    La désignation est ce que lit ``quote_engine/builder.py`` (contrat
    d'alignement des mots-clés, CLAUDE.md règle #4) ; le nom du produit n'est
    consulté qu'en second, pour rattraper une désignation réécrite à la main
    (« Modules PV posés » sur un produit « Panneau Jinko 550W »).
    """
    return (predicat(ligne.designation or '')
            or predicat(getattr(ligne.produit, 'nom', '') or ''))


def _pmax_wc_du_produit(produit):
    """Pmax (Wc) de la fiche technique d'un produit, ou ``None``.

    Passe par ``apps.stock.selectors.specs_for_produit`` — le point d'entrée
    cross-app SANCTIONNÉ pour lire une ``FicheTechnique`` (jamais un import de
    ``apps.stock.models`` ici). Ce sélecteur peut ne pas encore exister dans
    l'arbre : son absence est un NON-ÉVÉNEMENT (on retombe simplement sur la
    lecture du wattage dans le libellé), jamais une exception.
    """
    if produit is None:
        return None
    try:
        from apps.stock import selectors as _stock_selectors
    except Exception:  # noqa: BLE001 — app absente / import cassé : on ignore
        return None
    lire = getattr(_stock_selectors, 'specs_for_produit', None)
    if lire is None:
        return None
    try:
        specs = lire(produit)
    except TypeError:
        # Le sélecteur peut attendre un id plutôt que l'objet.
        try:
            specs = lire(getattr(produit, 'id', None))
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001
        return None
    if specs is None:
        return None
    pmax = (specs.get('pmax_wc') if isinstance(specs, dict)
            else getattr(specs, 'pmax_wc', None))
    try:
        pmax = int(round(float(pmax)))
    except (TypeError, ValueError):
        return None
    return pmax if pmax > 0 else None


def lignes_de_variante(lignes, variante):
    """Les lignes qui composent l'option ``variante`` d'un devis.

    C'est-à-dire les lignes COMMUNES (``variante=''`` — donc TOUTES celles d'un
    devis non varianté) plus celles qui sont propres à cette option. Une ligne
    de l'AUTRE option décrit une AUTRE installation : la faire entrer dans ce
    panier donnerait un ensemble qu'aucun client n'achète.

    ``variante`` vaut ``'sans'`` (défaut) ou ``'avec'``.
    """
    propre = VARIANTE_AVEC if variante == VARIANTE_AVEC else VARIANTE_SANS
    return [li for li in lignes
            if (getattr(li, 'variante', '') or '')
            in (VARIANTE_COMMUNE, propre)]


def option_avec_servable(devis):
    """Ce devis peut-il RÉELLEMENT livrer l'option « Avec batterie » ?

    MÊME critère que partout ailleurs dans le domaine — le moteur PDF
    (``quote_engine/builder.py`` : ``avec_ok = has_hybride and has_batterie``,
    d'où descendent ``variantes_servables`` et ``dimensionnement_options``) et
    le scénario stocké à la création (``_a_batterie and _a_hybride``) : l'option
    « avec » exige un onduleur HYBRIDE ET une BATTERIE. Lu sur le sous-ensemble
    de lignes qui compose CETTE option, jamais sur le panier mélangé.

    LECTURE PURE : n'écrit rien, ne lève pas sur un devis sans lignes.
    """
    lignes = lignes_de_variante(_lignes_produit(devis), VARIANTE_AVEC)
    return (any(_classe_ligne(li, _is_hybrid_inverter) for li in lignes)
            and any(_classe_ligne(li, _is_battery) for li in lignes))


def cible_depuis_lignes(devis, variante='sans'):
    """PV16 — cible de calepinage LUE DANS LES LIGNES du devis.

    Rend toujours le même dict, quelles que soient les données :

        {panneaux, kwc, panel_watt, scenario, batterie, avertissements}

    * ``panneaux`` — somme des quantités des lignes classées « panneau » par le
      classifieur partagé ``_is_panel`` (aligné sur ``quote_engine/builder.py``).
      Les lignes de SECTION/NOTE (sans prix ni quantité) sont ignorées.
    * ``panel_watt`` — wattage unitaire de la ligne dominante DE CETTE OPTION
      (QJR33), dans cet ordre : la fiche technique du produit dominant
      (``pmax_wc``), sinon le wattage lu dans le libellé (désignation puis nom
      du produit), sinon déduit du kWc de l'étude, sinon ``CIBLE_WATT_DEFAUT``
      — et là SEULEMENT un avertissement est levé.
    * ``kwc`` — puissance recalculée DEPUIS LES LIGNES (``panneaux × watt``),
      pas recopiée de l'étude : c'est le devis qui fait foi ici, pas un
      paramètre d'étude qui a pu se désynchroniser.
    * ``scenario`` — ``avec_batterie`` dès qu'une batterie est présente, sinon
      ``hybride`` si un onduleur hybride l'est, sinon ``reseau`` (défaut
      résidentiel, même arbitrage que ``build_devis_from_layout``).
    * ``avertissements`` — messages FRANÇAIS affichables tels quels.

    L-2OPT — LA CIBLE SE LIT PAR VARIANTE. Un devis « Les deux » dont les deux
    optimums divergent porte DEUX comptes de panneaux : les lignes
    ``variante=''`` + ``'sans'`` font l'option SANS, les lignes ``''`` +
    ``'avec'`` font l'option AVEC. ``panneaux`` / ``kwc`` sont ceux de l'option
    SANS — l'option 1 du document, celle que l'écran de calepinage dessine.
    Additionner les deux vues (ce que faisait la somme brute des lignes)
    donnerait un nombre qui ne décrit AUCUNE installation.

    CTX3D (25/08/2026) — ``scenario`` ET ``batterie`` DÉCRIVENT LA MÊME OPTION
    QUE ``panneaux``. Ils se lisaient sur TOUTES les lignes du devis pendant que
    le compte, lui, était filtré : un devis « Les deux » rendait donc
    ``panneaux`` = l'option SANS accompagné de ``scenario='avec_batterie'`` —
    une cible que rien ne décrit, envoyée telle quelle à l'écran 3D (PV17). Les
    quatre grandeurs viennent désormais du MÊME sous-ensemble de lignes.

    QJR33 (29/08/2026) — ``panel_watt`` REJOINT ENFIN CE SOUS-ENSEMBLE. La ligne
    DOMINANTE (celle qui porte le wattage) se cherchait encore dans TOUTES les
    lignes panneau du devis : sur un devis « Les deux » à DEUX modèles de
    panneau, le ``kwc`` rendu mariait le COMPTE d'une option au WATTAGE de
    l'autre (5,68 kWc observés au lieu de 4,40), et ce kWc partait tel quel dans
    le contrat 3D. Les CINQ grandeurs viennent maintenant de la même variante.

    ``variante`` choisit ce sous-ensemble : ``'sans'`` (défaut — l'option 1,
    celle que l'écran dessine, comportement historique) ou ``'avec'``. Sur un
    devis NON varianté les deux vues sont identiques : les lignes y sont toutes
    communes.

    LA FORME DU DICT NE BOUGE PAS : ces six clés sont un contrat gelé (le
    contexte de conception PV17 le repique tel quel). Un devis NON varianté —
    tous ceux d'hier — rend donc exactement les mêmes valeurs qu'avant.

    LECTURE PURE : aucun statut, aucune ligne, aucune étude n'est écrite.
    """
    lignes = _lignes_produit(devis)
    # Le panier de CETTE option — la seule base légitime de tous les scalaires
    # ci-dessous (cf. CTX3D dans le docstring).
    lignes_option = lignes_de_variante(lignes, variante)

    def _nom(ligne):
        return ligne.designation or getattr(ligne.produit, 'nom', '') or ''

    lignes_panneau = [li for li in lignes if _classe_ligne(li, _is_panel)]

    def _quantite(ligne):
        try:
            # ArithmeticError couvre decimal.InvalidOperation.
            return int(Decimal(str(ligne.quantite or 0)))
        except (ArithmeticError, TypeError, ValueError):
            return 0

    # L-2OPT — LE COMPTE EST CELUI DE L'OPTION DEMANDÉE : les lignes COMMUNES
    # (``variante=''``, c'est-à-dire toutes celles d'un devis d'hier) plus
    # celles qui lui sont propres. Une ligne de l'autre option décrit une AUTRE
    # installation — la compter ici donnerait la somme des deux paniers, un
    # nombre de panneaux qu'aucune installation ne porte.
    lignes_panneau_option = [li for li in lignes_option
                             if _classe_ligne(li, _is_panel)]
    panneaux = sum(_quantite(li) for li in lignes_panneau_option)

    # CTX3D — MÊME sous-ensemble que le compte : sur un devis « Les deux », la
    # batterie et l'onduleur hybride appartiennent à l'option « avec ». Les
    # chercher dans tout le devis faisait décrire l'option 1 par le scénario de
    # l'option 2.
    batterie = any(_classe_ligne(li, _is_battery) for li in lignes_option)
    hybride = any(_classe_ligne(li, _is_hybrid_inverter)
                  for li in lignes_option)
    if batterie:
        scenario = 'avec_batterie'
    elif hybride:
        scenario = 'hybride'
    else:
        scenario = 'reseau'

    avertissements = []
    if not lignes_panneau:
        avertissements.append(
            'Aucune ligne de panneau dans ce devis : la cible de calepinage '
            'est vide. Ajoutez les panneaux au devis avant de concevoir la '
            'toiture.')

    # Ligne dominante = la plus GROSSE quantité : c'est elle qui porte le
    # wattage de référence, et c'est elle que PV18 ajustera en cas d'écart.
    #
    # QJR33 (29/08/2026) — ELLE SE LIT DANS LE PANIER DE CETTE OPTION, comme le
    # COMPTE juste au-dessus. Elle était cherchée dans TOUTES les lignes
    # panneau du devis : sur un devis « Les deux » à DEUX modèles de panneau
    # (8 × 710 Wc en « sans », 10 × 440 Wc en « avec »), le ``kwc`` rendu
    # mariait le compte d'une option au wattage de l'AUTRE — 5,68 kWc au lieu
    # de 4,40 — et ce kWc partait tel quel dans le contexte 3D (PV17).
    dominante = None
    if lignes_panneau_option:
        dominante = max(
            lignes_panneau_option,
            key=lambda li: Decimal(str(li.quantite or 0)))

    # Deux modèles de panneau différents dans un même devis : le calepinage ne
    # sait pas répartir l'écart — on le DIT au lieu de choisir en silence.
    #
    # L-2OPT — L'IDENTITÉ NE COMPTE PAS LA VARIANTE, EXPRÈS : deux lignes
    # variantées du MÊME modèle (8 panneaux « sans » / 10 panneaux « avec »)
    # sont UN SEUL modèle, et cet avertissement ne doit surtout pas se
    # déclencher pour elles — sinon tout devis à deux optimiseurs crierait au
    # « devis à deux modèles » alors qu'il n'en porte qu'un.
    identites = {
        (li.produit_id, (li.designation or '').strip().lower())
        for li in lignes_panneau
    }
    # QJR33 — ``dominante`` est désormais celle de CETTE option : elle peut être
    # absente (option sans aucune ligne panneau) alors que le devis, lui, porte
    # plusieurs modèles. On ne nomme alors aucune ligne plutôt que d'en inventer
    # une (et surtout plutôt que de planter sur ``None``).
    if len(identites) > 1 and dominante is not None:
        avertissements.append(
            'Ce devis porte %d modèles de panneau différents : l\'écart de '
            'calepinage sera appliqué à la ligne la plus grosse (« %s »).'
            % (len(identites), _nom(dominante)))

    panel_watt = None
    if dominante is not None:
        panel_watt = _pmax_wc_du_produit(dominante.produit)
        if not panel_watt:
            panel_watt = (_parse_watt(dominante.designation or '')
                          or _parse_watt(
                              getattr(dominante.produit, 'nom', '') or ''))

    if not panel_watt and panneaux > 0:
        # Dernier repli chiffré : la puissance de l'étude, divisée par le
        # nombre de panneaux réellement en ligne.
        etude = getattr(devis, 'etude_params', None) or {}
        try:
            kwc_etude = float(etude.get('puissance_kwc') or 0)
        except (TypeError, ValueError):
            kwc_etude = 0.0
        if kwc_etude > 0:
            panel_watt = int(round(kwc_etude * 1000 / panneaux / 10) * 10)

    if not panel_watt:
        panel_watt = CIBLE_WATT_DEFAUT
        if lignes_panneau:
            avertissements.append(
                'Puissance unitaire du panneau illisible (ni fiche technique '
                'ni wattage dans le libellé) : %d Wc retenus par défaut.'
                % CIBLE_WATT_DEFAUT)

    kwc = round(panneaux * panel_watt / 1000.0, 3) if panneaux else 0.0

    return {
        'panneaux': panneaux,
        'kwc': kwc,
        'panel_watt': int(panel_watt),
        'scenario': scenario,
        'batterie': bool(batterie),
        'avertissements': avertissements,
    }


def remplacer_lignes(devis, lignes_in, company):
    """QX21be — supprime puis recrée les lignes du devis (appelé SOUS une
    transaction par l'appelant). Produits bornés à la société de
    l'utilisateur OU au catalogue global (PV15, même portée que
    ``services._pick_product``) ; jamais de ``prix_achat`` accepté du corps.

    XSAL5 — ``optionnelle`` (add-on hors total) est persistée.
    XSAL14 — ``type_ligne`` (produit [défaut] / section / note) + ``ordre`` :
    une ligne section/note ne porte NI produit NI prix (jamais comptée dans
    les totaux). ``ordre`` par défaut = position dans la liste envoyée.

    L-2OPT — ``variante`` ('' commune | 'sans' | 'avec') est persistée.
    SANS ELLE, LA FONCTIONNALITÉ « DEUX OPTIMISEURS » NE SURVIVAIT PAS À
    L'ENREGISTREMENT : le générateur fusionne bien les deux kits
    (``fusionnerVariantes``, solar.js) et envoie le tag sur chaque ligne,
    mais CE chemin — le SEUL chemin d'écriture de l'écran, pour la création
    (``atomic``) comme pour l'édition (``replace-lines``) — recréait chaque
    ligne sans le kwarg, donc au défaut ``''``. Toutes les lignes
    redevenaient « communes » : plus de badge d'option à l'écran, et tout
    l'aval (``devis_variante`` dans ``services``, le comparatif du PDF, les
    cartes par option de la page publique) lisait un devis mono-option.
    Valeur inconnue ⇒ ``''`` (la ligne reste commune) : jamais une erreur
    d'enregistrement pour un tag mal formé."""
    from decimal import Decimal, InvalidOperation
    from django.db.models import Q
    from ..models import LigneDevis
    from apps.stock.models import Produit
    _VALID_TYPES = {c.value for c in LigneDevis.TypeLigne}
    _VALID_VARIANTES = {c.value for c in LigneDevis.Variante}
    devis.lignes.all().delete()
    for idx, li in enumerate(lignes_in):
        if not isinstance(li, dict):
            continue
        type_ligne = str(li.get('type_ligne') or 'produit')
        if type_ligne not in _VALID_TYPES:
            type_ligne = 'produit'
        try:
            ordre = int(li.get('ordre', idx))
        except (TypeError, ValueError):
            ordre = idx
        # XSAL14 — ligne de SECTION/NOTE : intertitre/texte sans prix.
        if type_ligne in ('section', 'note'):
            designation = (li.get('designation') or '').strip()
            if not designation:
                raise ValueError(
                    'Une ligne de section/note doit porter un intitulé.')
            LigneDevis.objects.create(
                devis=devis, produit=None,
                designation=designation[:255],
                quantite=None, prix_unitaire=None, remise=Decimal('0'),
                taux_tva=None, type_ligne=type_ligne, ordre=ordre)
            continue
        # Ligne PRODUIT (chemin historique + XSAL5 optionnelle + ordre).
        try:
            produit_id = int(li.get('produit'))
        except (TypeError, ValueError):
            raise ValueError('Ligne sans produit valide.')
        # PV15 — le catalogue GLOBAL (``company IS NULL``) est quotable :
        # c'est exactement la portée que ``services._pick_product`` retient
        # pour composer un devis. Le filtre société-stricte d'origine
        # REFUSAIT ici des produits que l'auto-composition venait de poser
        # sur le même devis (« Produit N inconnu » sur un simple
        # ré-enregistrement). La portée reste bornée : société de
        # l'utilisateur OU catalogue global — jamais celui d'un autre
        # tenant.
        produit = Produit.objects.filter(
            Q(company=company) | Q(company__isnull=True),
            id=produit_id).first()
        if produit is None:
            raise ValueError(f'Produit {produit_id} inconnu.')
        try:
            qte = Decimal(str(li.get('quantite', 1)))
            pu = Decimal(str(li.get('prix_unitaire', produit.prix_vente)))
            remise = Decimal(str(li.get('remise', 0)))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError('Quantité/prix/remise invalide.')
        taux = li.get('taux_tva')
        # L-2OPT — tag d'option porté par la ligne. Absent (tous les
        # appelants d'hier) ou inconnu ⇒ '' : ligne commune, comportement
        # historique strictement inchangé.
        variante = str(li.get('variante') or '')
        if variante not in _VALID_VARIANTES:
            variante = ''
        LigneDevis.objects.create(
            devis=devis, produit=produit,
            designation=(li.get('designation') or produit.nom)[:255],
            quantite=qte, prix_unitaire=pu, remise=remise,
            taux_tva=Decimal(str(taux)) if taux is not None else None,
            optionnelle=bool(li.get('optionnelle', False)),
            type_ligne='produit', ordre=ordre, variante=variante,
            # QJR59 / D12 — les marqueurs de saisie MANUELLE font l'aller
            # retour. Sans eux ici, ce chemin (le SEUL chemin d'écriture de
            # l'écran, création comme édition) les remettrait à False à
            # chaque enregistrement : le prix et la quantité tapés par le
            # commercial redeviendraient réécrivables au premier
            # rafraîchissement — exactement le trou que D12 referme.
            # Absents (tous les appelants d'hier) ⇒ False, comportement
            # historique strictement inchangé.
            quantite_manuelle=bool(li.get('quantite_manuelle', False)),
            prix_manuel=bool(li.get('prix_manuel', False)))


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (voir la docstring) : ils s'exécutent après toutes
# les définitions de ce module, donc l'ordre de chargement ne peut jamais faire
# lire un module à moitié construit.
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_battery,
    _is_hybrid_inverter,
    _is_panel,
    _parse_watt,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    VARIANTE_AVEC,
    VARIANTE_COMMUNE,
    VARIANTE_SANS,
)
