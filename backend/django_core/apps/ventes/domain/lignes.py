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

#: QJR608 — LE wattage de REPLI d'un layout (ou d'une composition) qui ne dit
#: aucun wattage. Propriétaire unique : ``geometrie``, ``creation`` et
#: ``composition`` l'importent d'ici. À NE PAS confondre avec
#: ``taille._AUTO_PANEL_WATT`` (710, le panneau catalogue par défaut du devis
#: automatique) : entrées différentes, valeurs volontairement distinctes.
LAYOUT_WATT_REPLI = 550
#: Nom historique (surface ``services``, tests PV16) du même repli.
CIBLE_WATT_DEFAUT = LAYOUT_WATT_REPLI


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
    (``quote_engine/builder.py`` : ``avec_ok = (has_hybride or has_offgrid)
    and has_batterie``, d'où descendent ``variantes_servables`` et
    ``dimensionnement_options``) et le scénario stocké à la création
    (``_a_batterie and _a_hybride``) : l'option « avec » exige un onduleur
    HYBRIDE **ou** AUTONOME (QJR-OFFGRID — un système de site isolé ne sert
    jamais que cette option-là) ET une BATTERIE. Lu sur le sous-ensemble de
    lignes qui compose CETTE option, jamais sur le panier mélangé.

    LECTURE PURE : n'écrit rien, ne lève pas sur un devis sans lignes.
    """
    # QJR607 — DÉLÈGUE au prédicat du noyau (``familles_servables``, BAT-DIFF
    # compris), lu sur le panier de CETTE option.
    from apps.ventes.utils.options import (
        familles_des_lignes, familles_servables)
    lignes = lignes_de_variante(_lignes_produit(devis), VARIANTE_AVEC)
    return familles_servables(**familles_des_lignes(lignes))[1]


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


# ── QJR84 — L'UNIQUE CONSTRUCTEUR DE `LigneDevis` DE `apps/ventes` ──────────
#
# Constat QB84 (audit L3 du 29/08/2026) : ``services.py`` créait des
# ``LigneDevis`` en direct sur QUATORZE sites, avec des jeux de champs
# légèrement différents, pendant que les tests décrivaient
# ``_replace_lines_atomic`` comme « le SEUL chemin d'écriture » des lignes.
# Le coût de cette divergence est mesurable et documenté ailleurs dans ce
# dépôt : un site qui oublie ``variante`` écrit une ligne COMMUNE là où elle
# devait servir UNE option (QJR81) ; un site qui oublie ``ordre`` laisse le
# tri retomber sur ``id`` et perd l'ordre voulu par la société (PVORD) ; un
# site qui oublie ``prix_manuel``/``quantite_manuelle`` rouvre à la réécriture
# une valeur que le commercial avait tapée (D12).
#
# LA PARADE N'EST PAS UNE CONVENTION, C'EST UN GOULOT : un seul appel
# ``LigneDevis.objects.create`` dans toute l'app, ici, avec le jeu de champs
# COMPLET nommé UNE fois (``CHAMPS_LIGNE``). Un champ ajouté au modèle se
# déclare à un seul endroit, et un champ mal orthographié est REFUSÉ en
# français au lieu d'être silencieusement perdu. Un test statique
# (``tests/test_qjr_ecrivain_lignes.py``) vérifie qu'aucun second constructeur
# ne réapparaît.

# ── QJR84 / R4-B1 — RECENSEMENT DES CHEMINS DE CRÉATION SECONDAIRES ─────────
#
# L'audit L3 a demandé qu'aucun chemin de création « secondaire » ne reste sans
# verdict écrit : soit il devient un ADAPTATEUR de plus du pipeline (il compose,
# donc il doit composer comme les autres), soit il est déclaré HORS PIPELINE
# avec sa raison. Tous passent, aujourd'hui, par ``creer_ligne`` — le goulot
# ci-dessous — mais aucun n'est un adaptateur.
#
# 1. ``domain/creation.create_draft_devis_from_ocr`` — HORS PIPELINE.
#    Il ne crée AUCUNE ligne : un document OCR brut ne fournit pas de
#    ``Produit`` du catalogue, et le brouillon est laissé à compléter dans
#    l'éditeur. Rien à composer, donc rien à converger.
#
# 2. ``domain/creation.dupliquer_devis`` (NTUX13) — HORS PIPELINE.
#    Une DUPLICATION recopie un devis existant ligne à ligne ; elle ne
#    consulte ni catalogue, ni dimensionnement, ni scénario. La faire
#    recomposer changerait en silence le devis que le commercial a
#    délibérément dupliqué. Ce qu'elle DOIT faire — et ce que QJR84 lui donne —
#    c'est recopier le jeu de champs COMPLET (``variante``, ``optionnelle``,
#    ``quantite_manuelle``, ``prix_manuel``), sans quoi « cloné à l'identique »
#    était faux.
#
# 3. ``domain/gammes.create_devis_from_reserve`` (XFSM18) — HORS PIPELINE.
#    Même raison que (1) : aucune ligne n'est créée (la réserve d'intervention
#    décrit un défaut, pas un kit).
#
# 4. ``domain/gammes.creer_variante_gamme`` — HORS PIPELINE **AUJOURD'HUI**,
#    CANDIDAT DÉCLARÉ au sixième adaptateur. C'est le seul des six dont le
#    verdict n'est pas définitif : une GAMME change les marques épinglées
#    (PVMRQ, ``carte_marques_composition(company, gamme_nom_devis)``), donc une
#    vraie variante de gamme devrait RECOMPOSER via
#    ``pipeline.composer(..., gamme_nom_devis=...)`` au lieu de recopier les
#    produits de la gamme d'origine. Le faire ici serait un changement de
#    comportement (la sœur cesserait d'être une copie), donc hors de QJR84 :
#    la tâche le NOMME et s'arrête là. En attendant, la copie passe par
#    ``creer_ligne`` avec le jeu de champs complet.
#
# 5. ``domain/cycle_vie.renouveler_devis`` (NTCPQ13) — HORS PIPELINE.
#    Un renouvellement REPREND le kit que le client a accepté et le RE-TARIFE
#    au catalogue courant ; recomposer lui ferait vendre autre chose que ce qui
#    a été accepté. QJR84 lui fait recopier le jeu complet ET honorer D12 : une
#    ligne ``prix_manuel`` n'est pas re-tarifée (sans cette garde, le marqueur
#    recopié aurait protégé une valeur qui venait d'être réécrite).
#
# ── QJR243 (g) — LE RECENSEMENT N'ÉTAIT PAS EXHAUSTIF : QUATRE CHEMINS DE PLUS,
#    ET UN CONTOURNEMENT DE LA GARDE (QJR608 : le second, « cpq », n'existe
#    pas). Chacun reçoit ici son verdict ÉCRIT ;
#    AUCUN n'est recâblé par cette tâche (« constater, pas corriger »).
#
# 7. ``domain/composition._completer_kit_residentiel`` — ADAPTATEUR DE FAIT,
#    et c'est LE chemin secondaire qui COMPOSE un kit. Il n'a pas besoin de
#    converger : il passe DÉJÀ par ``pipeline.composer`` (QJR81) — carte des
#    marques, ordre de lignes, phase électrique et, depuis QJR221, la gamme du
#    devis. Il écrit ensuite par ``creer_ligne``. Verdict : CONFORME, aucun
#    travail.
#
# 8. ``domain/resynchronisation.reconcilier`` (trois créations : panneau,
#    batterie, onduleur manquant) — HORS PIPELINE **par conception**. C'est le
#    mode ``MODE_RECONCILIER`` : il ajuste CHIRURGICALEMENT un devis existant
#    (prix négociés, ordre, groupes préservés) là où l'écrivain de lignes
#    SUPPRIME et RECRÉE. Le faire converger vers ``ecrire_lignes`` détruirait
#    exactement ce qu'il protège (cf. la note QJR220 dans ``pipeline``).
#
# 9. (QJR546) l'ancien ``apply_preset_to_devis`` (QJ16) est SUPPRIMÉ : un
#    modèle s'applique À L'ÉCRAN (lignes remplacées, produits non tarifés
#    sautés ET nommés) puis passe par ``replace-lines`` → ``ecrire_lignes``.
#
# 10. ``public_views`` (devis automatique depuis le tunnel public) — HORS
#    PIPELINE pour la CRÉATION DE LIGNES : la composition lui est fournie
#    toute faite ; il ne fait qu'écrire, par ``creer_ligne``, avec l'ordre
#    explicite (PVORD).
#
# 11. ``management/commands/reparer_devis_deux_options`` — HORS PIPELINE.
#    Commande de RÉPARATION d'historique, exécutée à la main par le fondateur :
#    elle recrée la ligne manquante d'un devis déjà vendu, elle ne compose pas.
#
# ── LE CONTOURNEMENT DE LA GARDE AST, NOMMÉ ──────────────────────────────────
#
# ``LigneDevisViewSet`` → ``LigneDevisSerializer`` (``ModelSerializer``,
# ``fields = '__all__'``). Le sérialiseur DRF appelle ``Model.objects
# .create(**validated_data)`` DANS DRF, pas dans ce dépôt : la garde AST de
# ``test_qjr_ecrivain_lignes`` ne peut structurellement pas le voir.
# VERDICT : ADAPTATEUR LÉGITIME, et il est SÛR — précisément parce que
# ``fields = '__all__'`` : il porte le jeu de champs du MODÈLE, donc il ne
# peut pas en oublier un (c'est le risque que ``CHAMPS_LIGNE`` couvre pour
# les appelants Python). Le faire passer par ``creer_ligne`` reviendrait à
# réécrire un ``ModelSerializer`` à la main pour un gain nul.
#
# QJR608 — l'ancienne entrée « B. apps/cpq/services.py » a été retirée :
# ``apps/cpq`` n'a pas de ``services.py`` et ne crée aucune ``LigneDevis``
# (vérifié le 01/10/2026). Un futur écrivain cross-app passera par une
# fonction de ``ventes/services.py``, jamais par ``LigneDevis.objects.create``.

#: QJR84 — le jeu de champs COMPLET d'une ligne de devis. ``produit`` et
#: ``produit_id`` sont les DEUX façons de rattacher le catalogue (la seconde
#: recopie la string-FK sans charger un ``Produit`` par ligne, cf.
#: ``domain/bordereau``) ; elles s'excluent.
CHAMPS_LIGNE = (
    'produit', 'produit_id', 'designation', 'quantite', 'prix_unitaire',
    'remise', 'taux_tva', 'type_ligne', 'ordre', 'variante',
    # AGR217 — la base légale d'une ligne exonérée (0 %) : une copie
    # (révision, duplication, variante, gamme, renouvellement) la reprend.
    'tva_base_legale',
    # STKCAT23 — le RÔLE de la ligne. Un appelant peut le poser explicitement ;
    # sinon ``creer_ligne`` le RÉSOUT (voir ``_role_a_la_creation``). Il figure
    # dans le jeu complet comme tout le reste : un chemin de COPIE
    # (``cloner_lignes``) doit le reprendre tel quel, sans le re-deviner.
    'role_devis',
    'groupe_index', 'groupe_label', 'optionnelle',
    'quantite_manuelle', 'prix_manuel',
    # ERR-QJR570 (D-QJR5-4) — la PROVENANCE (True composée / False ajoutée à
    # la main / None inconnue) : une copie la reprend (CHAMPS_CLONES :
    # révision, duplication, gamme, renouvellement, modèles), et
    # ``remplacer_lignes`` la fait suivre depuis l'écran.
    'ligne_composee',
    # NTCPQ18 — rattachement à un LOT (site/bâtiment). QJR667 : l'écran
    # « Lots / multi-sites » le pose (POST lots/) et ``remplacer_lignes`` le
    # fait suivre (borné aux lots du devis) ; un test le vérifie contre le
    # modèle, pour qu'aucun champ ne devienne inatteignable.
    'lot', 'lot_id',
)


def creer_ligne(devis, **champs):
    """QJR84 — crée UNE ``LigneDevis``. LE GOULOT PYTHON de ``apps/ventes``.

    QJR243 (g) — CETTE PHRASE DISAIT « le seul endroit où une ligne de devis
    naît », ET C'ÉTAIT FAUX : le sérialiseur DRF de ``LigneDevisViewSet`` crée
    ses lignes DANS DRF (sûr — il porte le jeu de champs du MODÈLE), recensé
    avec son verdict juste au-dessus (§ « LE CONTOURNEMENT »). Le goulot reste
    vrai pour tout ce qui s'écrit EN PYTHON dans cette app — ce qui est déjà
    la garantie qui compte, et ce que la garde AST vérifie.

    Les champs NON fournis gardent le défaut du MODÈLE : un appelant qui
    n'écrivait pas ``variante`` hier obtient exactement la ligne d'hier. Ce
    n'est donc pas une couche de valeurs par défaut — c'est un GOULOT, et il
    ne change aucun comportement à lui seul.

    Lève ``ValueError`` (en français) sur un champ hors ``CHAMPS_LIGNE`` : un
    nom mal orthographié n'a plus le droit de disparaître dans un ``**spec``.
    """
    from ..models import LigneDevis

    inconnus = sorted(set(champs) - set(CHAMPS_LIGNE))
    if inconnus:
        raise ValueError(
            'Champ de ligne de devis inconnu : %s. Le jeu de champs complet '
            'est déclaré dans CHAMPS_LIGNE (apps/ventes/domain/lignes.py) — '
            'ajoutez-l\'y plutôt que de contourner l\'écrivain unique.'
            % ', '.join(inconnus))
    for objet, cle in (('produit', 'produit_id'), ('lot', 'lot_id')):
        if objet in champs and cle in champs:
            raise ValueError(
                'Une ligne se rattache à son %s par « %s » OU par « %s », '
                'jamais par les deux.' % (objet, objet, cle))
    if 'role_devis' not in champs:
        champs['role_devis'] = _role_a_la_creation(champs)
    return LigneDevis.objects.create(devis=devis, **champs)


def _role_a_la_creation(champs):
    """STKCAT23 — le RÔLE à figer sur une ligne qu'on crée, ou ``None``.

    DEUX RANGS, ET PAS TROIS. Le rôle DÉCLARÉ du produit passe devant (c'est
    une donnée, posée par le fondateur sur la fiche) ; sinon les MOTS-CLÉS de
    la désignation, via le classifieur historique — le REPLI PERMANENT.

    LE RANG « CATÉGORIE » EST DÉLIBÉRÉMENT ABSENT ICI, et c'est une décision de
    COÛT, pas un oubli : lire ``produit.categorie.type_equipement`` coûterait
    UNE REQUÊTE PAR LIGNE à chaque enregistrement de devis (le vivier de
    composition ne précharge que ``fiche_technique``), et un rôle qui
    dépendrait de la présence d'un cache ne serait même pas déterministe. Le
    rail catégorie sert là où la requête est déjà payée : le sérialiseur
    produit (``role_devis_effectif``, STKCAT21). Une ligne dont le produit ne
    tient son rôle que de sa catégorie retombe donc ici sur les mots-clés —
    c'est-à-dire sur le comportement d'hier, jamais moins bien.

    NE LÈVE JAMAIS : une ligne doit naître même si la classification échoue.
    Un rôle absent vaut NULL, et NULL veut dire « les mots-clés décideront à la
    lecture », le comportement historique exact.
    """
    from core.product_roles import role_declare

    produit = champs.get('produit')
    declare = role_declare(getattr(produit, 'role_devis', None))
    if declare:
        return declare
    # ``designation`` peut manquer (une section/note n'en porte pas toujours) :
    # le classifieur rend alors None, et la ligne naît sans rôle.
    from .catalogue import classer_produit
    return role_declare(classer_produit(champs.get('designation') or ''))


# ── QJR116 — UN SEUL CLONEUR DE LIGNES POUR LES TROIS CHEMINS DE COPIE ──────
#
# Constat CS1/CS2/CS3 (audit du 30/08/2026), vérifié en code : les trois
# chemins qui recopient un devis — ``dupliquer_devis``, ``creer_variante_
# gamme``, ``renouveler_devis`` — nommaient chacun SA liste de champs, à la
# main. Elles avaient déjà divergé : ``renouveler_devis`` clonait
# ``optionnelle`` que les deux autres avaient reçue au même moment (QJR84),
# et AUCUNE des trois ne clonait ``lot``. Le coût d'un champ oublié n'est pas
# cosmétique : sans ``variante``, ``_repartir_options`` (``quote_engine/
# builder.py``) retombe sur son filtre par mots-clés et range panneaux,
# structures et pose dans les DEUX paniers d'options ; sans ``optionnelle``,
# un add-on hors totaux (``LigneDevis.compte_dans_totaux``) redevient une
# ligne facturée.
#
# LA PARADE EST LA MÊME QUE POUR L'ÉCRITURE : un seul endroit. Le jeu cloné
# est DÉRIVÉ de ``CHAMPS_LIGNE`` (jamais retapé), donc un champ ajouté demain
# au modèle entre dans les trois copies par le seul ajout que le test statique
# ``test_qjr_ecrivain_lignes`` exige déjà.

#: QJR116 — ce qu'une COPIE de devis reprend : le jeu COMPLET moins les deux
#: formes « par identifiant », qui s'excluent avec leur objet (``creer_ligne``
#: refuse le couple).
CHAMPS_CLONES = tuple(champ for champ in CHAMPS_LIGNE
                      if champ not in ('produit_id', 'lot_id'))


def cloner_lignes(source, cible, *, prix_unitaire=None, remplacements=None):
    """QJR116 — recopie TOUTES les lignes de ``source`` sur ``cible``.

    Le SEUL cloneur de lignes de l'app : les CINQ chemins de copie
    (``dupliquer_devis``, ``creer_variante_gamme``, ``renouveler_devis``, et
    depuis QJR224 les deux chemins de VUE ``/variante`` et ``/reviser``)
    passent par lui, donc un champ ne peut plus tomber sur un chemin et pas
    sur les autres.

    ``remplacements`` — QJR224, appelable optionnel ``(ligne) -> dict`` de
    champs à SUBSTITUER sur la copie. Il existe parce que ``/variante`` MET À
    L'ÉCHELLE les quantités : sa règle d'échelle lui est propre (0,8 / 1,2 avec
    son arrondi et son plancher), le JEU DE CHAMPS ne l'est pas. Les clés sont
    validées contre :data:`CHAMPS_CLONES` — un champ mal orthographié lève,
    il ne disparaît pas en silence. ``None`` (tous les appelants d'hier) ⇒
    aucune substitution, copie byte-identique.

    ``prix_unitaire`` — appelable optionnel ``(ligne) -> prix``. Absent (les
    deux copies « à l'identique »), le prix de la ligne source est repris tel
    quel. Fourni (le RENOUVELLEMENT, qui re-tarife au catalogue courant), sa
    valeur remplace le prix cloné et RIEN d'autre : les marqueurs D12
    (``prix_manuel``/``quantite_manuelle``) restent ceux de la source, et
    c'est à l'appelable de les honorer.

    LES LOTS SUIVENT LEUR DEVIS. ``LigneDevis.lot`` pointe un ``LotDevis`` qui
    appartient à UN devis (contrainte d'unicité ``devis``+``nom_lot``) :
    recopier la clé telle quelle rattacherait les lignes de la copie aux lots
    de la SOURCE. Les lots sont donc recréés sur ``cible`` et les lignes
    re-pointées vers leur jumeau. Un devis sans lot — tous ceux d'hier, aucun
    chemin de création n'en pose — ne crée rien et voit ``lot=None`` partout :
    comportement strictement inchangé.

    Rend la liste des lignes créées, dans l'ordre de lecture de la source
    (``LigneDevis.Meta.ordering`` = ``ordre``, ``id``).
    """
    from ..models import LotDevis

    jumeaux = {}
    for lot in source.lots.all():
        jumeaux[lot.pk] = LotDevis.objects.create(
            company=cible.company, devis=cible, nom_lot=lot.nom_lot,
            adresse_site=lot.adresse_site, ordre=lot.ordre)

    creees = []
    for ligne in source.lignes.all().select_related('produit'):
        champs = {champ: getattr(ligne, champ) for champ in CHAMPS_CLONES
                  # ``lot`` est re-résolu ci-dessous : le lire ici coûterait
                  # une requête par ligne pour une valeur aussitôt remplacée.
                  if champ != 'lot'}
        champs['lot'] = jumeaux.get(ligne.lot_id)
        if prix_unitaire is not None:
            champs['prix_unitaire'] = prix_unitaire(ligne)
        if remplacements is not None:
            substitutions = remplacements(ligne) or {}
            inconnus = sorted(set(substitutions) - set(CHAMPS_CLONES))
            if inconnus:
                raise ValueError(
                    'Champ de clonage inconnu : %s. Le jeu cloné est déclaré '
                    'dans CHAMPS_CLONES (apps/ventes/domain/lignes.py).'
                    % ', '.join(inconnus))
            champs.update(substitutions)
        creees.append(creer_ligne(cible, **champs))
    return creees


# ── L-FORFAIT / QJR83 — LES FORFAITS AU PANNEAU SUIVENT LE COMPTE ───────────
#
# Constat QB83 (audit L3 du 29/08/2026), vérifié en code : AUCUN chemin ne
# re-tarifait les lignes de forfait par panneau après un changement de compte.
# Un devis passé de 9 à 20 panneaux gardait une pose facturée POUR 9 — alors
# que la docstring de ``prix_forfait_ht`` affirme précisément le contraire
# (« changer le nombre de panneaux requote mécaniquement les forfaits »). Elle
# ne disait vrai que pour une COMPOSITION neuve : dès que le devis existait,
# plus rien ne repassait sur ses lignes.
#
# La re-tarification vit donc chez L'ÉCRIVAIN UNIQUE (QJR73) : tout chemin qui
# finit par écrire les lignes d'un devis l'obtient, et aucun n'a sa propre
# copie de la règle. Le barème, lui, reste au STOCK
# (``prix_fixe_ht``/``prix_par_panneau_ht``) — aucun montant n'est écrit ici.
#
# D12 (décision fondateur du 29/08/2026) — UNE LIGNE ``prix_manuel`` N'EST
# JAMAIS RÉÉCRITE. Le prix négocié que le commercial a tapé est souverain ; ce
# qui change, c'est qu'on le DIT au lieu de laisser croire que le barème a
# joué.


def prix_negocie(ligne, *, prix_reference):
    """QJR555 — LA définition unique du « prix négocié » d'une ligne.

    Une ligne est négociée (donc jamais recalée ni supprimée en silence) si :

    * ``prix_manuel`` est posé (D12 — le prix tapé est souverain, même quand
      il coïncide avec le prix catalogue) ;
    * OU elle porte une remise de ligne non nulle ;
    * OU il n'y a pas de prix de référence (pas de produit, pas de prix) —
      on ne peut rien prouver, le doute profite à la ligne ;
    * OU son prix unitaire diffère du prix de référence.

    ``prix_reference`` est le prix catalogue contre lequel on juge : le prix
    catalogue COURANT pour la composition, l'ANCIEN prix pour le recalage
    catalogue (``catalogue_events``). Fonction pure : n'écrit rien.
    """
    if getattr(ligne, 'prix_manuel', False):
        return True
    if prix_reference is None:
        return True
    try:
        if Decimal(str(getattr(ligne, 'remise', None) or 0)) != Decimal('0'):
            return True
        actuel = getattr(ligne, 'prix_unitaire', None)
        if actuel is None:
            return True
        return Decimal(str(actuel)) != Decimal(str(prix_reference))
    except (TypeError, ValueError, ArithmeticError):
        return True


def avertissement_forfait_verrouille(designation, nb_panneaux, attendu):
    """Le message FR d'un forfait au barème que ``prix_manuel`` protège."""
    return ('« %s » : prix saisi à la main — il n\'a PAS été re-tarifé sur '
            'les %d panneaux du devis (barème du stock : %s MAD HT). Effacez '
            'la saisie manuelle sur cette ligne pour qu\'elle suive de nouveau '
            'le barème.' % (designation, nb_panneaux, attendu))


def avertissement_forfait_commun_divergent(designation):
    """Le message FR d'un forfait COMMUN à deux options qui ne portent pas le
    même champ de panneaux : le tarifer sur l'une fausserait l'autre."""
    return ('« %s » : ce forfait est COMMUN aux deux options, dont les champs '
            'de panneaux diffèrent — il n\'a PAS été re-tarifé, car le tarifer '
            'sur une option fausserait l\'autre. Dupliquez-le par option pour '
            'qu\'il suive chaque compte.' % designation)


def _comptes_panneaux(lignes):
    """Le compte de panneaux de CHAQUE vue, lu sur les lignes du devis.

    Rend ``{variante: nb}`` pour les trois valeurs de ``variante``. Sur un
    devis NON varianté — tous ceux d'hier — les trois valent le même total.
    Sur un devis varianté, la vue « sans » et la vue « avec » comptent chacune
    les lignes COMMUNES plus les leurs (même règle que
    ``lignes_de_variante``), et la clé COMMUNE vaut ``None`` quand les deux
    divergent : il n'existe alors AUCUN compte qui décrive les deux options.
    """
    def _quantite(ligne):
        try:
            # ArithmeticError couvre decimal.InvalidOperation.
            return int(Decimal(str(ligne.quantite or 0)))
        except (ArithmeticError, TypeError, ValueError):
            return 0

    panneaux = [li for li in lignes if _classe_ligne(li, _is_panel)]
    if not any((getattr(li, 'variante', '') or '') for li in panneaux):
        total = sum(_quantite(li) for li in panneaux)
        return {VARIANTE_COMMUNE: total,
                VARIANTE_SANS: total, VARIANTE_AVEC: total}
    comptes = {}
    for variante in (VARIANTE_SANS, VARIANTE_AVEC):
        comptes[variante] = sum(
            _quantite(li) for li in lignes_de_variante(panneaux, variante))
    comptes[VARIANTE_COMMUNE] = (
        comptes[VARIANTE_SANS]
        if comptes[VARIANTE_SANS] == comptes[VARIANTE_AVEC] else None)
    return comptes


def retarifer_forfaits_par_panneau(devis, *, avertissements=None):
    """QJR83 — remet au barème les lignes de forfait TARIFÉES AU PANNEAU.

    Ne touche QUE les lignes dont le produit porte un barème
    (``porte_bareme_par_panneau``) : tout le reste du catalogue garde son prix,
    négocié ou non. Rend la liste des avertissements FRANÇAIS (et enrichit
    ``avertissements`` sur place quand l'appelant en fournit un).

    TROIS ABSTENTIONS, toutes DITES :

    * ``prix_manuel`` posé (D12) — le prix tapé par le commercial est souverain ;
    * forfait COMMUN d'un devis à deux options DIVERGENTES — aucun compte ne
      décrit les deux, et inventer une moyenne serait un chiffre inventé ;
    * barème illisible (``prix_forfait_ht`` rend ``None``) — silencieux, c'est
      simplement un produit sans barème.

    Aucune écriture quand le prix est DÉJÀ celui du barème : une ligne
    inchangée ne doit pas voir sa date de modification bouger.

    QJR220 (31/08/2026) — TROIS APPELANTS, PLUS UN. Cette fonction était
    correcte et n'avait qu'UN appelant dans tout le dépôt
    (:func:`remplacer_lignes`, plus bas) alors que DEUX autres chemins changent
    le compte de panneaux d'un devis EXISTANT et ne passaient pas par lui :

    * ``MODE_RECONCILIER`` (``domain/resynchronisation.reconcilier``, les trois
      sites qui écrivent ``dominante.quantite``) — une sync-layout 9 → 20
      panneaux laissait la pose au barème de 9, l'incident que le fichier de
      test de QJR83 nomme lui-même ;
    * ``LigneDevisViewSet`` (ajout / modification / suppression d'UNE ligne).

    Les deux l'appellent désormais, APRÈS toutes leurs écritures de lignes.
    """
    messages = avertissements if isinstance(avertissements, list) else []
    lignes = _lignes_produit(devis)
    comptes = _comptes_panneaux(lignes)
    for ligne in lignes:
        produit = getattr(ligne, 'produit', None)
        if not porte_bareme_par_panneau(produit):
            continue
        variante = getattr(ligne, 'variante', '') or VARIANTE_COMMUNE
        nb_panneaux = comptes.get(variante, comptes.get(VARIANTE_COMMUNE))
        if nb_panneaux is None:
            messages.append(
                avertissement_forfait_commun_divergent(ligne.designation))
            continue
        attendu = prix_forfait_ht(produit, nb_panneaux)
        if attendu is None:
            continue
        try:
            actuel = Decimal(str(ligne.prix_unitaire or 0))
        except (ArithmeticError, TypeError, ValueError):
            actuel = None
        if actuel == attendu:
            continue
        if getattr(ligne, 'prix_manuel', False):
            messages.append(avertissement_forfait_verrouille(
                ligne.designation, nb_panneaux, attendu))
            continue
        ligne.prix_unitaire = attendu
        ligne.save(update_fields=['prix_unitaire'])
    return messages


#: QJR204 — LE REFUS, EN FRANÇAIS, D'UN REMPLACEMENT PAR LE VIDE.
MSG_REMPLACEMENT_VIDE = (
    "Au moins une ligne est requise : un remplacement par une liste VIDE "
    "effacerait tout le devis. Pour retirer une ligne, renvoyez les lignes "
    "restantes ; pour abandonner le devis, supprimez-le ou révisez-le."
)


#: QJR517 — ``LigneDevis.groupe_label.max_length`` (models.py).
_GROUPE_LABEL_MAX = 80

#: QJR517 — champs de ``CHAMPS_LIGNE`` que ``remplacer_lignes`` n'accepte
#: PAS du corps, chacun avec sa raison : ``produit_id`` (la ligne produit
#: passe par ``produit``, borné société/catalogue global), ``lot_id`` (le lot
#: passe par ``lot``, borné aux lots de CE devis).
#: QJR667 — ``lot`` fait désormais l'aller-retour : l'écran « Lots /
#: multi-sites » de l'Édition complète rattache des lignes à un lot, et sans
#: lui le prochain enregistrement (qui recrée les lignes) les détachait.
EXCLUSIONS_REMPLACEMENT = ('produit_id', 'lot_id')


def _groupe_index_emis(valeur):
    """QJR517 — un ``groupe_index`` entier ≥ 0, sinon ``None``."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _ligne_composee_emise(valeur):
    """ERR-QJR570 — ``True`` / ``False`` / ``None`` (absente ou inconnue).

    Les chaînes 'true'/'false' (formulaires) sont lues comme telles : un
    ``bool('false')`` ferait d'un ajout manuel une ligne composée."""
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, bool):
        return valeur
    texte = str(valeur).strip().lower()
    if texte in ('true', '1', 'oui', 'yes'):
        return True
    if texte in ('false', '0', 'non', 'no'):
        return False
    return None


#: AGR217 — longueur maximale de ``LigneDevis.tva_base_legale``.
TVA_BASE_LEGALE_MAX = 160


def _taux_nul(taux):
    """Le taux ÉMIS est-il 0 % ? ``None``/illisible ⇒ non (le taux du
    produit ou du devis s'applique, aucun contrôle ici)."""
    from decimal import Decimal, InvalidOperation
    if taux is None or taux == '':
        return False
    try:
        return Decimal(str(taux)) == 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def exiger_base_legale_tva(lignes_in):
    """AGR217 (contrat AGR200, ``exemple_400_tva_base_legale``) — une ligne
    PRODUIT émise à 0 % sans base légale est REFUSÉE : 400
    ``{detail, champ: 'lignes[i].tva_base_legale'}``, AVANT toute écriture.

    Seul un 0 % EXPLICITEMENT émis est contrôlé : une ligne sans
    ``taux_tva`` (composition du moteur, appelants d'hier) n'est jamais
    refusée. AUCUN taux n'est changé ni proposé (AGRM8)."""
    from rest_framework.exceptions import ValidationError

    for index, li in enumerate(lignes_in or ()):
        if not isinstance(li, dict):
            continue
        if str(li.get('type_ligne') or 'produit') in ('section', 'note'):
            continue
        if not _taux_nul(li.get('taux_tva')):
            continue
        if str(li.get('tva_base_legale') or '').strip():
            continue
        raise ValidationError({
            'detail': ('Ligne %d : une base légale est obligatoire pour un '
                       'taux de TVA de 0 %%.' % (index + 1)),
            'champ': 'lignes[%d].tva_base_legale' % index,
        })


def remplacer_lignes(devis, lignes_in, company, *, avertissements=None,
                     autoriser_vidage=False):
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
    d'enregistrement pour un tag mal formé.

    QJR83 — LES FORFAITS AU PANNEAU SONT REMIS AU BARÈME une fois les lignes
    écrites (``retarifer_forfaits_par_panneau``), en respectant ``prix_manuel``
    (D12). ``avertissements`` (optionnel) reçoit les messages FRANÇAIS des
    lignes qui ont REFUSÉ de suivre ; la fonction les rend aussi — elle ne
    rendait rien jusqu'ici, aucun appelant ne régresse.

    QJR204 (31/08/2026) — UNE LISTE VIDE EST REFUSÉE, PAS EXÉCUTÉE. Cet
    écrivain SUPPRIME puis recrée : appelé avec ``[]`` il effaçait toutes les
    lignes d'un devis brouillon/envoyé et rendait 200, là où ``/atomic``
    refusait déjà l'ensemble vide par un 400. Le balayage du dépôt (front
    compris : ``ventesApi.replaceLignesDevis`` est l'unique appelant de
    production et ``DevisGenerator`` n'a AUCUN geste « tout vider ») n'a trouvé
    aucun flux légitime de vidage — il est donc refusé ici pour TOUS les
    chemins d'écriture, ``ecrire_lignes(composition=None)`` compris. Un futur
    flux de vidage devra le DÉCLARER (``autoriser_vidage=True``), jamais
    l'obtenir par une liste vide."""
    from decimal import Decimal, InvalidOperation
    from django.db.models import Q
    from ..models import LigneDevis
    from apps.stock.models import Produit
    if not lignes_in and not autoriser_vidage:
        raise ValueError(MSG_REMPLACEMENT_VIDE)
    # AGR217 — un 0 % sans base légale est refusé AVANT la suppression.
    exiger_base_legale_tva(lignes_in)
    _VALID_TYPES = {c.value for c in LigneDevis.TypeLigne}
    _VALID_VARIANTES = {c.value for c in LigneDevis.Variante}
    # QJR667 — un ``lot`` n'est accepté que s'il appartient à CE devis (donc
    # à sa société) ; tout autre id (ou un id illisible) ⇒ ligne hors lot.
    lots_du_devis = {lot.pk: lot for lot in devis.lots.all()}

    def _lot_emis(valeur):
        try:
            return lots_du_devis.get(int(valeur))
        except (TypeError, ValueError):
            return None
    # STKCAT23 (bis) — vocabulaire des rôles : un rôle hors liste n'est
    # jamais écrit tel quel, creer_ligne le résout lui-même.
    from core.product_roles import ROLES_DEVIS
    _VALID_ROLES = set(ROLES_DEVIS)
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
            creer_ligne(
                devis, produit=None,
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
        role_emis = str(li.get('role_devis') or '')
        extra_role = ({'role_devis': role_emis}
                      if role_emis in _VALID_ROLES else {})
        # QJR517 — le mode « villas » (QJ29/QJ31) survit à l'écrivain unique :
        # groupe_index entier ≥ 0 (sinon None, ligne mono-système), label
        # tronqué au max_length du modèle. ``lot`` reste une exclusion
        # NOMMÉE (aucun écrivain UI : il se pose après coup, à l'écran).
        groupe_index = _groupe_index_emis(li.get('groupe_index'))
        groupe_label = str(li.get('groupe_label') or '')[:_GROUPE_LABEL_MAX]
        creer_ligne(
            devis, produit=produit,
            designation=(li.get('designation') or produit.nom)[:255],
            quantite=qte, prix_unitaire=pu, remise=remise,
            taux_tva=Decimal(str(taux)) if taux is not None else None,
            # AGR217 — la base légale fait l'aller-retour (absente ⇒ '').
            tva_base_legale=str(li.get('tva_base_legale') or '').strip()[
                :TVA_BASE_LEGALE_MAX],
            optionnelle=bool(li.get('optionnelle', False)),
            type_ligne='produit', ordre=ordre, variante=variante,
            groupe_index=groupe_index, groupe_label=groupe_label,
            lot=_lot_emis(li.get('lot')),
            **extra_role,
            # QJR59 / D12 — les marqueurs de saisie MANUELLE font l'aller
            # retour. Sans eux ici, ce chemin (le SEUL chemin d'écriture de
            # l'écran, création comme édition) les remettrait à False à
            # chaque enregistrement : le prix et la quantité tapés par le
            # commercial redeviendraient réécrivables au premier
            # rafraîchissement — exactement le trou que D12 referme.
            # Absents (tous les appelants d'hier) ⇒ False, comportement
            # historique strictement inchangé.
            quantite_manuelle=bool(li.get('quantite_manuelle', False)),
            prix_manuel=bool(li.get('prix_manuel', False)),
            # ERR-QJR570 (D-QJR5-4) — la provenance fait l'aller-retour :
            # sans elle, un produit ajouté à la main, enregistré puis rouvert,
            # était pris pour une ligne composée et REMPLACÉ au recalcul.
            # Absente / null ⇒ None (inconnue), comportement d'hier.
            ligne_composee=_ligne_composee_emise(li.get('ligne_composee')))
    # QJR83 — les forfaits AU PANNEAU suivent le compte réellement écrit
    # ci-dessus (jamais celui que l'appelant croyait envoyer).
    return retarifer_forfaits_par_panneau(devis,
                                          avertissements=avertissements)


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (voir la docstring) : ils s'exécutent après toutes
# les définitions de ce module, donc l'ordre de chargement ne peut jamais faire
# lire un module à moitié construit.
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_battery,
    _is_hybrid_inverter,
    _is_offgrid_inverter,
    _is_panel,
    _parse_watt,
    porte_bareme_par_panneau,
    prix_forfait_ht,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    VARIANTE_AVEC,
    VARIANTE_COMMUNE,
    VARIANTE_SANS,
)
