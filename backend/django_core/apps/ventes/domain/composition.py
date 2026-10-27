"""Composition — le cœur qui transforme une cible en kit de lignes.

`composition_residentielle` (733 lignes) et tout ce qui l'entoure : le
porteur de ligne (`LigneKit`), le résultat (`CompositionLignes`), l'ordre
des rôles, les constructeurs d'avertissements (vivier batterie vide,
rupture de stock, plafond de banc, épingle sans correspondance, aucun
onduleur triphasé), la fusion de deux kits, la composition à deux
optimiseurs, et les constantes PVHEAL du kit complétable
(`CLASSES_KIT_COMPLETABLES`, `AVERTISSEMENTS_KIT_ABSENT`,
`_classe_kit_de_ligne`, `_est_au_prix_catalogue`,
`_completer_kit_residentiel`, le refus du couple panneau/onduleur
impossible).

QJR74 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
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
from collections import namedtuple
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── PVKIT — la composition RÉSIDENTIELLE COMPLÈTE (port de solar.js) ─────────
#
# Un devis issu du calepinage ne composait jusqu'ici qu'un SQUELETTE : le
# panneau, l'onduleur, et la batterie quand le scénario en veut une. Ce n'est
# pas ce qui est vendu. Le kit réel — celui de l'ancien simulateur, porté à
# l'écran par ``autoFillLines`` (frontend/src/features/ventes/solar.js) — porte
# aussi les structures de fixation, les socles, les accessoires (câblage DC/AC,
# connecteurs), le tableau de protection AC/DC, l'installation, le transport et,
# DERRIÈRE UN ONDULEUR HUAWEI SEULEMENT, le Smart Meter et la clé Wifi.
#
# Ce bloc est le port Python FIDÈLE de ``autoFillLines`` : mêmes classes de
# mots-clés (alignées sur ``quote_engine/builder.py`` — règle du dépôt, le
# découpage des options du PDF en dépend), mêmes règles de quantités, mêmes
# paliers de prix par blocs de 5 kWc, même choix de structure. Trois écarts,
# assumés et seulement trois :
#
#   1. **Les lignes à quantité nulle ne sont pas enregistrées.** L'écran les
#      affiche pour qu'on puisse les saisir ; ``autoFillLines`` le dit mot pour
#      mot dans son propre en-tête (« lignes à quantité nulle comprises — elles
#      s'affichent mais ne sont pas enregistrées »). Un devis, lui, n'écrit que
#      ce qu'il vend.
#   2. **Le scénario tranche entre les deux onduleurs.** L'écran propose les
#      deux options côte à côte (option 1 sans batterie / option 2 avec) et les
#      totaux les séparent au moment de l'affichage ; un devis construit depuis
#      un calepinage a DÉJÀ choisi. On ne quote donc qu'un onduleur, et les
#      batteries ne suivent que le scénario batterie.
#   3. **Un produit SANS PRIX n'entre JAMAIS dans le kit** (garde ``_has_price``,
#      règle du dépôt) ; l'écran, lui, affiche une ligne à 0 à compléter.
#
# Un composant absent du catalogue est SAUTÉ, jamais fatal : le kit se dégrade
# proprement (c'est exactement ce que fait l'écran avec un produit introuvable).
# Le panneau, lui, reste gardé EN AMONT par ``validate_composition_for_layout``
# — un devis sans panneau est une erreur 422 explicite, pas un kit silencieux.

#: Une ligne composée, prête à devenir une ``LigneDevis``. ``prix_unitaire``
#: est TOUJOURS un montant **HT** (le modèle stocke du HT ; le simulateur
#: raisonne en TTC, la conversion se fait dans la composition).
#:
#: L-2OPT — ``variante`` dit à QUELLE option la ligne appartient ('' = commune
#: aux deux, 'sans' / 'avec' = propre à cette option-là). Le champ porte un
#: DÉFAUT VIDE : tout appelant historique construit sa ``LigneKit`` sans le
#: mentionner et obtient exactement la ligne d'hier.
LigneKit = namedtuple('LigneKit',
                      'produit designation quantite prix_unitaire variante',
                      defaults=('',))

#: L-2OPT — les trois valeurs de ``LigneDevis.variante`` / ``LigneKit.variante``.
#: Répétées ici (chaînes nues) plutôt qu'importées de ``models`` : ce module
#: n'importe les modèles qu'en local, dans les fonctions.
VARIANTE_COMMUNE = ''
VARIANTE_SANS = 'sans'
VARIANTE_AVEC = 'avec'


class CompositionLignes(list):
    """U3 — le résultat de ``composition_residentielle``.

    C'est une LISTE de ``LigneKit`` (tout appelant historique la parcourt sans
    rien changer) qui porte EN PLUS les métadonnées de la composition. Une
    liste nue ne peut pas porter d'attribut : c'est la seule raison de cette
    sous-classe, et c'est ce qui permet au dry-run de rendre à l'écran ce que
    le serveur a réellement décidé (wattage retenu, kWc réel, marques
    introuvables) au lieu de le laisser le recalculer de son côté.
    """

    roles = ()
    nb_panneaux = 0
    panel_watt_reel = 0
    kwc_reel = 0.0
    blocs = 1
    marques_manquantes = ()
    # ── L-2OPT — métadonnées de la composition FUSIONNÉE (deux optimiseurs) ──
    # ``variantes`` reste False sur toute composition d'hier : une composition
    # mono-optimum n'a que des lignes communes. Les deux clés ``_avec`` ne
    # valent quelque chose que quand l'optimum AVEC batterie a choisi un AUTRE
    # champ PV que l'optimum SANS.
    variantes = False
    nb_panneaux_avec = 0
    kwc_reel_avec = 0.0
    #: RSIZ4 — les avertissements FRANÇAIS de la composition (phrases prêtes à
    #: afficher), dédoublonnés, dans l'ordre où ils ont été prononcés. Rendus
    #: même quand l'appelant n'a fourni aucun canal ``avertissements`` : c'est
    #: la clé STABLE que l'étude du devis recopie (``etude_params``).
    avertissements_composition = ()


#: STKCAT7 — la valeur de ``stock.Categorie.TypeEquipement.STRUCTURE``.
#: Répétée ici en chaîne nue (comme ``ROLES_AUTO_COMPOSITION`` répète les clés
#: de ``solar.js``) : ce module est PUR — il n'importe aucun modèle, et surtout
#: pas ceux d'``apps.stock``, qui se lisent par ``apps.stock.selectors``.
TYPE_EQUIPEMENT_STRUCTURE = 'structure'


def _type_equipement(produit):
    """Le TYPE D'ÉQUIPEMENT déclaré par la CATÉGORIE d'un produit, ou ``None``.

    STKCAT7 — LECTURE SANS REQUÊTE : la catégorie est préchargée par
    ``catalogue_de_la_societe`` (``select_related('categorie')``), et un produit
    SANS catégorie n'en déclenche aucune (on regarde ``categorie_id`` d'abord).
    C'est ce qui permet à la composition de rester une fonction PURE : aucune
    requête par candidat, quel que soit le nombre de produits au catalogue.
    """
    if getattr(produit, 'categorie_id', None) is None:
        return None
    return getattr(getattr(produit, 'categorie', None),
                   'type_equipement', None) or None


def role_structure_du_produit(produit, voulu='acier'):
    """STKCAT1/STKCAT7 — LE RÔLE émis pour la ligne structure RETENUE.

    RÈGLE D'ÉMISSION DU CONTRAT (``contract_samples/devis_composition.json``) :
    le rôle suit le NOM DU PRODUIT RETENU, jamais le toggle demandé.

      · le nom porte encore « acier » ⇒ ``structure_acier`` ;
      · le nom porte encore « alu » / « aluminium » ⇒ ``structure_alu`` ;
      · le nom ne porte NI l'un NI l'autre (une pergola, un bac lesté…) ⇒ le
        rôle GÉNÉRIQUE ``structure`` (STKCAT2 l'a inscrit dans les quatre
        miroirs de vocabulaire, juste AVANT ses deux alias dépréciés).

    ``voulu`` (``'acier'`` / ``'alu'``) départage un nom qui porterait LES DEUX
    mots-clés, et c'est aussi le rôle rendu quand AUCUN produit n'a été retenu
    (``produit`` vaut ``None``) : la ligne n'est alors pas écrite du tout
    (``ajouter`` saute un produit absent), mais le rôle reste celui d'hier —
    comportement historique strictement inchangé.
    """
    prefere = 'alu' if str(voulu or '').startswith('alu') else 'acier'
    autre = 'acier' if prefere == 'alu' else 'alu'
    role = {'alu': 'structure_alu', 'acier': 'structure_acier'}
    nom = _sans_accents(getattr(produit, 'nom', '') or '')
    if not nom:
        return role[prefere]
    if prefere in nom:
        return role[prefere]
    if autre in nom:
        return role[autre]
    return 'structure'


def ordonner_par_role(taguees, ordre_lignes):
    """PVORD — trie des couples ``(rôle, objet)`` selon une séquence de rôles.

    Miroir EXACT de ``solar.js::orderLinesByRolePreference`` : un rôle PRÉSENT
    dans ``ordre_lignes`` est classé à sa position ; un rôle ABSENT garde son
    rang canonique mais TOUJOURS après tout rôle explicitement préféré. Tri
    STABLE — les deux lignes « batterie » (5 / 10 kWh) gardent leur ordre
    relatif. Séquence absente ou vide : la liste est rendue TELLE QUELLE
    (ordre canonique du simulateur, comportement historique).
    """
    couples = list(taguees or [])
    if not isinstance(ordre_lignes, (list, tuple)) or not ordre_lignes:
        return couples
    rangs = {}
    for position, role in enumerate(ordre_lignes):
        rangs.setdefault(role, position)
    grand = len(couples) + len(ordre_lignes) + 1
    return sorted(
        couples,
        key=lambda couple: rangs.get(couple[0], grand))


def avertissement_vivier_batterie_vide(plage):
    """Le message FRANÇAIS d'un vivier batterie VIDE sous un onduleur à plage.

    Une seule formulation, partagée par tous les chemins qui savent avertir
    (composition, resynchronisation de calepinage, pré-vol de composition) :
    le commercial doit lire la MÊME phrase quel que soit le bouton utilisé."""
    if plage and plage[1] > 0:
        return ('Aucune batterie compatible tarifée pour cet onduleur '
                '(plage %s-%s V) : le devis a été composé SANS batterie. '
                'Ajoutez une batterie compatible au catalogue, ou changez '
                'd\'onduleur.' % (_v_txt(plage[0]), _v_txt(plage[1])))
    return ('Aucune batterie tarifée au catalogue : le devis a été composé '
            'SANS batterie. Ajoutez une batterie tarifée.')


def avertissement_batterie_rupture_stock():
    """BATHOMO/F5 (fondateur 26/08/2026) — message DISTINCT de
    ``avertissement_vivier_batterie_vide`` : ici, une (ou plusieurs)
    batterie(s) COMPATIBLE(S) existent (le couple électrique est bon) mais
    leur STOCK est à 0. Conflater ce cas avec « aucune batterie compatible »
    enverrait le commercial vers le mauvais correctif (« changez d'onduleur »
    quand le vrai geste est de réapprovisionner, ou de choisir un autre
    module déjà en stock)."""
    return ('Batterie(s) compatibles en rupture de stock : le devis a été '
            'composé SANS batterie. Réapprovisionnez, ou choisissez un '
            'autre module batterie.')


def avertissement_batterie_plafond_banc():
    """BATHOMO/F3 (fondateur 26/08/2026) — message DISTINCT des deux
    précédents : des batteries compatibles ET en stock existent, mais
    ``bat_max_modules_par_banc`` (le plafond fondateur de modules par
    banque) a rejeté TOUTES les candidates homogènes pour cette cible —
    jamais une banque tronquée, jamais un « avec batterie » qui part sans
    aucune batterie sans le dire."""
    return ('Aucune banque batterie ne respecte le plafond de modules par '
            'banc pour cette cible : le devis a été composé SANS batterie. '
            'Augmentez le plafond, ou choisissez un autre module.')


def avertissement_batterie_pin_sans_correspondance(calibre_impose):
    """A1 (revue adversariale Fable, 26/08/2026) — message DISTINCT des trois
    précédents : le devis vend DÉJÀ un calibre précis (``batterie_module_
    kwh``, lu par ``dimensionnement.module_batterie_du_devis``), mais AUCUNE
    batterie de ce calibre n'existe dans le vivier COMPATIBLE — ni stock, ni
    plafond en cause, le calibre lui-même n'est pas composable sous cet
    onduleur (ex. un système haute tension jamais compatible avec un
    hybride basse tension). « Honest absence beats a wrong pairing » :
    repeindre la banque dans un AUTRE calibre que celui déjà vendu serait
    exactement la violation que ce chantier ferme — la composition part
    donc SANS batterie plutôt que dans un calibre que ce devis ne vend pas."""
    return ('Le module batterie déjà vendu sur ce devis (%s kWh) ne '
            'correspond à aucune batterie du vivier compatible : le devis a '
            'été composé SANS batterie plutôt que dans un autre calibre. '
            'Vérifiez le catalogue, ou la compatibilité électrique de ce '
            'module avec l\'onduleur retenu.' % _v_txt(calibre_impose))


def _v_txt(volts):
    """« 160.0 » → « 160 » (une tension entière ne s'écrit pas avec un ,0)."""
    try:
        f = float(volts)
    except (TypeError, ValueError):
        return str(volts)
    return str(int(f)) if f == int(f) else ('%g' % f)


def avertissement_aucun_onduleur_triphase():
    """L-TRI — le message FRANÇAIS d'un client TRIPHASÉ sans onduleur triphasé.

    Une seule formulation, comme ``avertissement_vivier_batterie_vide`` : le
    commercial doit lire la MÊME phrase quel que soit le bouton utilisé. Elle
    dit la seule chose vraie — la composition a été REFUSÉE, il manque une
    référence au catalogue — et surtout PAS « composition en monophasé à
    valider » : un onduleur monophasé n'est pas une solution dégradée pour un
    client triphasé, c'est une erreur de devis (ordre fondateur 24/08/2026).
    """
    return ('Raccordement TRIPHASÉ déclaré — aucun onduleur TRIPHASÉ '
            'disponible au catalogue : la composition a été REFUSÉE plutôt '
            'que de coter un onduleur monophasé. Ajoutez un onduleur '
            'triphasé (tarifé, fiche technique complète) au catalogue.')


def _vivier_onduleurs_par_phase(candidats, phase):
    """PVCOMPAT — restreint un vivier d'onduleurs au RACCORDEMENT du client.

    Le client déclare son raccordement sur sa fiche lead (``raccordement``), et
    jusqu'ici la composition l'ignorait complètement : un client MONOPHASÉ
    pouvait se voir composer un onduleur triphasé — impossible à raccorder chez
    lui, donc un devis à refaire.

    Deux traitements DIFFÉRENTS, et c'est voulu :

    * ``monophase`` — les triphasés sont ÉCARTÉS du vivier (on ne raccorde pas
      du triphasé sur un abonnement monophasé). Si cela vide le vivier, on rend
      le vivier D'ORIGINE et on le DIT : mieux vaut un devis à valider qu'aucun
      onduleur du tout (même principe que ``_filtrer_onduleurs_complets`` : un
      verrou qui vide la table est une panne).
    * ``triphase`` — L-TRI (incident fondateur 24/08/2026 : « pourquoi j'ai du
      mono alors que le client est tri ») — les monophasés sont ÉCARTÉS, sans
      AUCUN repli. La préférence tri d'hier n'était qu'un départage À PUISSANCE
      ÉGALE (``choisir_onduleur``) : dès que le premier palier triphasé du
      catalogue (10 kW) était plus GROS que le plus petit modèle ≥ 80 % du kWc,
      le monophasé gagnait — un client triphasé se voyait coter un « Onduleur
      réseau Huawei 5kW Monophasé ». Le vivier est donc TRIPHASÉ EXCLUSIVEMENT :
      un petit kWc prend le plus petit triphasé du catalogue, même très
      surdimensionné (la règle des 80 % est un PLANCHER, jamais une raison de
      retomber en monophasé), et un catalogue sans triphasé ne compose AUCUN
      onduleur — le refus est annoncé par ``choisir_onduleur``.

    Rend ``(vivier, a_replie)``. ``a_replie`` reste le drapeau du SEUL repli qui
    subsiste, celui du monophasé. ``phase`` vide/inconnue ⇒ vivier inchangé,
    donc comportement d'avant à l'octet près.
    """
    from apps.ventes.compatibilites import (
        PHASE_MONO, PHASE_TRI, est_triphase_produit)
    source = list(candidats or [])
    if phase == PHASE_TRI:
        # Jamais de repli : un vivier vide vaut mieux qu'une ligne monophasée.
        return [p for p in source if est_triphase_produit(p)], False
    if phase != PHASE_MONO:
        return source, False
    monophases = [p for p in source if not est_triphase_produit(p)]
    if monophases:
        return monophases, False
    return source, True


# ── QJR403 — LES QUANTITÉS QUI SUIVENT LE COMPTE DE PANNEAUX ────────────────
#
# Elles n'étaient écrites qu'ICI, au fil de la composition (``ajouter(role_
# structure, structure, nb)`` / ``ajouter('socle', ..., nb * 2)``). Or le chemin
# MODE_ECRIRE réécrit la quantité de la ligne panneau DOMINANTE
# (``pipeline._appliquer_preseance_quantite``, depuis ``taille.nb_panneaux``)
# SANS toucher à ses sœurs : le devis sortait avec N' panneaux montés sur N
# structures et N×2 socles — une nomenclature fausse ET un prix faux.
#
# La règle est donc DÉCLARÉE ICI, une seule fois, et le pipeline l'IMPORTE : il
# re-dérive, il ne recalcule pas selon une seconde formule.


def quantites_derivees_du_compte(nb_panneaux) -> dict:
    """``{'structure': N, 'socle': N × 2}`` pour ``N`` panneaux.

    LA définition de ces rapports — la composition la consomme comme le
    pipeline. Les clés sont celles de ``catalogue.classer_produit`` (le
    classifieur unique), pour qu'un appelant puisse apparier une ligne à sa
    quantité dérivée sans réécrire, lui non plus, une seconde classification.
    """
    try:
        nb = int(nb_panneaux or 0)
    except (TypeError, ValueError):
        return {'structure': 0, 'socle': 0}
    nb = max(0, nb)
    return {'structure': nb, 'socle': nb * 2}


# RSIZ (27/10/2026) — ``composition_residentielle`` (et ses deux privés
# exclusifs) vit dans ``composition_residentielle.py`` — DÉPLACEMENT PUR.
# Ré-export À LA PLACE D'ORIGINE : le nom est lié au même moment du
# chargement qu'avant, donc tout importeur (services, creation, pipeline,
# tests) reste identique, même au milieu d'un cycle d'import.
from apps.ventes.domain.composition_residentielle import (  # noqa: E402,F401 — ré-export du symbole déplacé (RSIZ)
    composition_residentielle,
)


# ── L-2OPT — DEUX OPTIMISEURS : le champ PV de l'option « avec » peut DIFFÉRER
# de celui de l'option « sans » ────────────────────────────────────────────────
#
# LE TROU QUE CECI BOUCHE. Le moteur calibré (``apps.ventes.dimensionnement``)
# calcule DEPUIS DIM2 deux gagnants distincts : ``recommandation`` (meilleur
# payback SANS stockage) et ``recommandation_avec`` (balayage CONJOINT
# champ × stockage, meilleur payback AVEC). Le second n'alimentait AUCUN chemin
# de génération de lignes : il ne servait qu'à l'affichage. Le devis « Les deux »
# composait donc UN SEUL champ PV et se contentait de le REGARDER de deux
# façons — le découpage sans/avec du PDF est un filtrage par MOTS-CLÉS
# (batterie → « avec », onduleur réseau → « sans »), si bien que les panneaux,
# la structure, les socles et la pose tombaient dans les DEUX options avec la
# MÊME quantité. Une option « avec batterie » qui, économiquement, veut deux
# panneaux de plus ne pouvait tout simplement pas être proposée.
#
# LA FUSION. On compose DEUX kits complets (chacun par la source de vérité
# ``composition_residentielle``, en forme MONO-option — donc aucune règle
# dupliquée) puis on les fusionne ligne à ligne :
#   · même produit, même désignation, même quantité, même prix unitaire dans
#     les deux kits → UNE ligne COMMUNE (``variante=''``) ;
#   · présente dans les deux mais avec une quantité (ou un prix) différente →
#     DEUX lignes, ``variante='sans'`` et ``variante='avec'`` ;
#   · présente dans un seul kit → une ligne portant la variante de ce kit
#     (batteries → « avec », onduleur réseau → « sans », hybride → « avec »).
#
# RSIZ3 (27/10/2026) — PLUS DE FORME COMMUNE. L'ancien « repli de sécurité »
# rendait, à dimensionnements ÉGAUX, la composition « deux options »
# HISTORIQUE : onduleur réseau Huawei ET N hybrides Deye dans la MÊME offre,
# toutes lignes communes, sans variante (mesuré sur les devis auto 25 000 /
# 80 000 / 100 000 MAD). La fusion est désormais TOUJOURS jouée, au besoin
# avec ``nb_avec = nb_sans`` ; et quand l'option « avec » ne peut porter
# AUCUNE batterie, seule l'option « sans » est rendue, et c'est DIT.


def _memes_lignes_kit(a, b):
    """Deux ``LigneKit`` sont-elles LA MÊME ligne (donc fusionnables) ?

    Compare ce qui fait le contenu d'une ligne de devis : le produit, la
    désignation, la quantité et le prix unitaire HT. La remise et la TVA n'en
    sont pas : une ligne composée automatiquement naît toujours sans remise et
    au taux du devis — les deux kits partagent donc forcément les mêmes.
    """
    if a is None or b is None:
        return False
    if _cle_produit(a.produit) != _cle_produit(b.produit):
        return False
    if (a.designation or '') != (b.designation or ''):
        return False
    try:
        if Decimal(str(a.quantite or 0)) != Decimal(str(b.quantite or 0)):
            return False
        return (Decimal(str(a.prix_unitaire or 0))
                == Decimal(str(b.prix_unitaire or 0)))
    except (TypeError, ValueError, ArithmeticError):
        return False


def _cle_produit(produit):
    """Identité STABLE d'un produit catalogue (pk quand il en a un)."""
    if produit is None:
        return None
    pk = getattr(produit, 'pk', None)
    if pk is None:
        pk = getattr(produit, 'id', None)
    return pk if pk is not None else ('nom', getattr(produit, 'nom', ''))


def fusionner_kits(taguees_sans, taguees_avec):
    """L-2OPT — fusionne deux kits ``(rôle, LigneKit)`` en UNE séquence variantée.

    Les deux kits sortent de la MÊME fonction de composition, donc leurs
    séquences de rôles sont deux sous-suites d'un même ordre canonique (celui
    des appels ``ajouter`` de ``composition_residentielle``, éventuellement
    reclassé par le MÊME ``ordre_lignes``). Un entrelacement stable les remet
    donc dans un ordre lisible sans qu'aucun ordre canonique n'ait à être
    recopié ici — une copie divergerait au premier rôle ajouté.

    Rend une liste de couples ``(rôle, LigneKit)`` dont chaque ligne porte sa
    ``variante``. Fonction PURE.
    """
    sans = list(taguees_sans or [])
    avec = list(taguees_avec or [])
    roles_avec = [role for role, _ in avec]
    fusion = []
    i = j = 0
    while i < len(sans) or j < len(avec):
        if i < len(sans) and j < len(avec):
            role_s, ligne_s = sans[i]
            role_a, ligne_a = avec[j]
            if role_s == role_a:
                if _memes_lignes_kit(ligne_s, ligne_a):
                    fusion.append(
                        (role_s, ligne_s._replace(variante=VARIANTE_COMMUNE)))
                else:
                    # Les deux options ne veulent pas la même chose de ce rôle
                    # (typiquement : le nombre de panneaux, donc aussi les
                    # structures, les socles et le forfait de pose). Les deux
                    # lignes restent CÔTE À CÔTE : le devis se lit.
                    fusion.append(
                        (role_s, ligne_s._replace(variante=VARIANTE_SANS)))
                    fusion.append(
                        (role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
                i += 1
                j += 1
                continue
            if role_s in roles_avec[j:]:
                # Le rôle courant du kit « sans » réapparaît plus loin dans le
                # kit « avec » : ce qui est propre à « avec » (batteries,
                # onduleur hybride) passe d'abord, à sa place canonique.
                fusion.append(
                    (role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
                j += 1
            else:
                fusion.append(
                    (role_s, ligne_s._replace(variante=VARIANTE_SANS)))
                i += 1
            continue
        if i < len(sans):
            role_s, ligne_s = sans[i]
            fusion.append((role_s, ligne_s._replace(variante=VARIANTE_SANS)))
            i += 1
        else:
            role_a, ligne_a = avec[j]
            fusion.append((role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
            j += 1
    return fusion


def composition_deux_optimiseurs(produits, *, panel_watt,
                                 kwc_sans, nb_panneaux_sans,
                                 kwc_avec=None, nb_panneaux_avec=0,
                                 batterie_cible_kwh=None,
                                 structure_type='acier',
                                 structure_produit_id=None,
                                 taux_tva=Decimal('20'), avertissements=None,
                                 marques=None, ordre_lignes=None,
                                 mppt_paires=1, phase=None, modeles=None,
                                 batterie_module_kwh=None,
                                 paires_mppt_derivees=False):
    """L-2OPT — LE devis « Les deux » quand les deux optimums DIVERGENT.

    Compose DEUX kits complets par ``composition_residentielle`` (la source de
    vérité — aucune règle de composition n'est réécrite ici) :

      · kit SANS  — ``nb_panneaux_sans`` panneaux, onduleur RÉSEAU, ZÉRO
        batterie (``avec_batterie=False``) ;
      · kit AVEC  — ``nb_panneaux_avec`` panneaux, onduleur HYBRIDE dimensionné
        pour CE champ-là, et les batteries du palier retenu
        (``batterie_cible_kwh`` ; absent ⇒ la règle historique kWc/5 décide,
        aucun chiffre inventé).

    puis les FUSIONNE (cf. :func:`fusionner_kits`).

    RSIZ3 — deux dimensionnements ÉGAUX fusionnent AUSSI (l'onduleur réseau
    part dans « sans », l'hybride et les batteries dans « avec », le reste
    commun) : la forme commune réseau + hybride n'est plus jamais rendue.
    ``modeles`` (ACAL63) n'est transmis aux deux kits qu'à champs ÉGAUX (le
    seul cas où le calepinage dessine les deux options) ;
    ``batterie_module_kwh`` (BATHOMO) va au kit « avec ». Kit « avec » SANS
    aucune batterie ⇒ le kit « sans » seul, avec
    :func:`avertissement_option_avec_retiree`.

    Fonction PURE (elle ne requête ni n'écrit rien) ; ``produits`` est déjà
    cantonné à la société appelante par l'appelant.
    """
    nb_sans = int(nb_panneaux_sans or 0)
    nb_avec = int(nb_panneaux_avec or 0) or nb_sans
    cible_stockage = (float(batterie_cible_kwh)
                      if batterie_cible_kwh not in (None, '')
                      and float(batterie_cible_kwh) > 0 else None)
    kwc_s = float(kwc_sans or 0)
    # Un champ « avec » de 10 panneaux évalué à la puissance du champ « sans »
    # se verrait dimensionner l'onduleur (et la batterie) de l'autre option :
    # à défaut de kWc fourni, on le DÉRIVE de son propre compte de panneaux,
    # jamais on ne recopie celui d'en face.
    kwc_a = (float(kwc_avec or 0)
             or (nb_avec * float(panel_watt or 0) / 1000.0)
             or kwc_s)
    # Le catalogue est parcouru DEUX fois (un kit chacun) : on le matérialise
    # une bonne fois, sans quoi un itérable à usage unique livrerait un second
    # kit VIDE.
    catalogue = list(produits or ())

    commun = dict(
        panel_watt=panel_watt, structure_type=structure_type,
        # STKCAT7 — LES DEUX kits fusionnés portent LA MÊME structure : sans
        # ce passage, l'option « avec batterie » serait chiffrée en acier
        # pendant que l'option « sans » porterait la pergola choisie.
        structure_produit_id=structure_produit_id,
        taux_tva=taux_tva, avertissements=avertissements, marques=marques,
        ordre_lignes=ordre_lignes, mppt_paires=mppt_paires, phase=phase,
        # RSIZ5 — les deux kits dérivent (ou non) leurs paires MPPT ensemble.
        paires_mppt_derivees=paires_mppt_derivees)

    modeles_kits = modeles if nb_avec == nb_sans else None
    kit_sans = composition_residentielle(
        catalogue, kwc=kwc_s, nb_panneaux=nb_sans, avec_batterie=False,
        deux_options=False, modeles=modeles_kits, **commun)
    kit_avec = composition_residentielle(
        catalogue, kwc=kwc_a, nb_panneaux=nb_avec, avec_batterie=True,
        deux_options=False, batterie_cible_kwh=cible_stockage,
        batterie_module_kwh=batterie_module_kwh, modeles=modeles_kits,
        **commun)
    if kit_sans and 'batterie' not in (getattr(kit_avec, 'roles', ()) or ()):
        return _sans_option_avec(kit_sans, kit_avec, avertissements)

    def _taguees(kit):
        roles = list(getattr(kit, 'roles', ()) or ())
        return [(roles[index] if index < len(roles) else None, ligne)
                for index, ligne in enumerate(kit)]

    fusion = fusionner_kits(_taguees(kit_sans), _taguees(kit_avec))

    lignes = CompositionLignes(ligne for _role, ligne in fusion)
    lignes.roles = [role for role, _ligne in fusion]
    lignes.variantes = any(ligne.variante for ligne in lignes)
    # Les métadonnées « nominales » restent celles de l'option SANS — c'est
    # l'option 1 du document (celle que la liste et le repli d'affichage
    # montrent) et c'est ce que les appelants historiques lisent. L'option AVEC
    # a ses propres clés, à côté, jamais à la place.
    lignes.nb_panneaux = getattr(kit_sans, 'nb_panneaux', nb_sans)
    lignes.panel_watt_reel = getattr(kit_sans, 'panel_watt_reel', panel_watt)
    lignes.kwc_reel = getattr(kit_sans, 'kwc_reel', 0.0)
    lignes.blocs = getattr(kit_sans, 'blocs', 1)
    lignes.nb_panneaux_avec = getattr(kit_avec, 'nb_panneaux', nb_avec)
    lignes.kwc_reel_avec = getattr(kit_avec, 'kwc_reel', 0.0)
    lignes.capacites_batterie_vivier = list(
        getattr(kit_avec, 'capacites_batterie_vivier', ()) or ())
    # Marques épinglées introuvables : l'UNION des deux kits, dédoublonnée —
    # un rôle manquant ne doit pas être annoncé deux fois parce qu'on a composé
    # deux fois.
    vues = set()
    manquantes = []
    for kit in (kit_sans, kit_avec):
        for manque in (getattr(kit, 'marques_manquantes', ()) or ()):
            cle = (manque.get('role'), manque.get('marque'))
            if cle in vues:
                continue
            vues.add(cle)
            manquantes.append(manque)
    lignes.marques_manquantes = manquantes
    lignes.avertissements_composition = avertissements_des_kits(
        kit_sans, kit_avec)
    return lignes


def avertissement_option_avec_retiree():
    """RSIZ3 — le message FRANÇAIS d'un devis « Les deux » dont l'option
    « avec batterie » n'a pu porter AUCUNE batterie."""
    return ('Option « avec batterie » non proposée : aucune batterie '
            "compatible en stock n'a pu être composée avec l'onduleur "
            "hybride — le devis ne présente que l'option sans batterie. "
            'Ajoutez une batterie compatible tarifée en stock pour proposer '
            'les deux options.')


def _sans_option_avec(kit_sans, kit_avec, avertissements):
    """RSIZ3 — le kit « sans » SEUL, porteur de tous les avertissements des
    deux kits et de :func:`avertissement_option_avec_retiree` (dit aussi dans
    le canal de l'appelant quand il en fournit un)."""
    message = avertissement_option_avec_retiree()
    if avertissements is not None and message not in avertissements:
        avertissements.append(message)
    kit_sans.avertissements_composition = avertissements_des_kits(
        kit_sans, kit_avec) + [message]
    return kit_sans


def avertissements_des_kits(*kits):
    """RSIZ4 — l'UNION ordonnée et dédoublonnée des avertissements de
    composition de plusieurs kits (``.avertissements_composition``)."""
    union = []
    for kit in kits:
        for message in (getattr(kit, 'avertissements_composition', ()) or ()):
            if message not in union:
                union.append(message)
    return union


# ── PVHEAL — la resynchronisation GUÉRIT les devis SQUELETTES ────────────────
#
# `build_devis_from_layout` compose le KIT COMPLET (PVKIT) depuis PVKIT. Mais
# les devis créés AVANT lui sont restés des squelettes — panneau + onduleur
# (± batterie), parfois une pose et des accessoires — sans structures, sans
# socles, sans tableau de protection AC/DC, alors que le catalogue de la
# société les porte, actifs et tarifés. Ce que le client reçoit est alors un
# devis qui ne décrit pas ce qu'on lui installe.
#
# La resynchronisation les COMPLÈTE donc, sous trois règles DURES :
#
#   1. **Elle n'AJOUTE que.** Aucune ligne existante n'est modifiée, supprimée
#      ni re-tarifée : les prix négociés sont sacrés — c'est toute la promesse
#      « chirurgicale » de PV18, et compléter ne la desserre pas.
#   2. **Une classe déjà présente ne revient jamais.** La présence se lit avec
#      le MÊME classifieur par mots-clés que la composition et que le moteur PDF
#      (`classer_produit`) : la désignation d'abord, le nom du produit ensuite —
#      une ligne « Pose et mise en service » posée sur un produit
#      « Installation » compte donc bien comme l'installation.
#   3. **Un composant introuvable (ou sans prix) n'est jamais inventé** : il est
#      sauté ET DIT, en français, dans `avertissements`. Le silence d'hier est
#      exactement ce qui a laissé partir des devis amputés.
#
# Le duo Smart Meter + clé Wifi suit une quatrième règle, héritée du
# simulateur : il ne se vend que derrière un onduleur HUAWEI. Et c'est
# l'onduleur RÉELLEMENT posé sur le devis qui tranche — pas celui que la
# composition aurait choisi, puisqu'on ne remplace jamais l'onduleur en place.

#: Les classes du kit que la resynchronisation peut compléter : tout le kit
#: résidentiel SAUF les trois que la logique chirurgicale gère déjà (panneau,
#: batterie, onduleurs), dans l'ordre d'affichage du simulateur.
CLASSES_KIT_COMPLETABLES = (
    'smart_meter', 'wifi_dongle', 'structure', 'socle', 'accessoires',
    'tableau', 'installation', 'transport',
)

#: ACAL90 (D-ACAL-22) — le message FRANÇAIS d'une classe NON RECRÉÉE parce
#: qu'elle a été retirée à la main (marqueur ``etude_params.kit_retire``).
AVERTISSEMENTS_KIT_RETIRE = {
    'smart_meter': 'Smart Meter non recréé : retiré à la main — remettez-le '
                   'depuis le générateur.',
    'wifi_dongle': 'Clé Wifi non recréée : retirée à la main — remettez-la '
                   'depuis le générateur.',
    'structure': 'Structure non recréée : retirée à la main — remettez-la '
                 'depuis le générateur.',
    'socle': 'Socles non recréés : retirés à la main — remettez-les depuis '
             'le générateur.',
    'accessoires': 'Accessoires non recréés : retirés à la main — '
                   'remettez-les depuis le générateur.',
    'tableau': 'Tableau de protection AC/DC non recréé : retiré à la main — '
               'remettez-le depuis le générateur.',
    'installation': 'Installation non recréée : retirée à la main — '
                    'remettez-la depuis le générateur.',
    'transport': 'Transport non recréé : retiré à la main — remettez-le '
                 'depuis le générateur.',
}

#: Le message FRANÇAIS d'une classe manquante, écrit EN ENTIER par classe pour
#: que l'accord soit juste (« Structure … absente », « Socles … absents »).
AVERTISSEMENTS_KIT_ABSENT = {
    'smart_meter': 'Smart Meter absent du catalogue ou sans prix — ligne non '
                   'ajoutée.',
    'wifi_dongle': 'Clé Wifi absente du catalogue ou sans prix — ligne non '
                   'ajoutée.',
    'structure': 'Structure de fixation absente du catalogue ou sans prix — '
                 'ligne non ajoutée.',
    'socle': 'Socles de lestage absents du catalogue ou sans prix — ligne non '
             'ajoutée.',
    'accessoires': 'Accessoires (câblage DC/AC, connecteurs) absents du '
                   'catalogue ou sans prix — ligne non ajoutée.',
    'tableau': 'Tableau de protection AC/DC absent du catalogue ou sans prix '
               '— ligne non ajoutée.',
    'installation': 'Installation (pose et mise en service) absente du '
                    'catalogue ou sans prix — ligne non ajoutée.',
    'transport': 'Transport absent du catalogue ou sans prix — ligne non '
                 'ajoutée.',
}


def _classe_kit_de_ligne(ligne):
    """Classe CATALOGUE d'une ligne de devis, ou ``None``.

    Même lecture que ``_classe_ligne`` (désignation d'abord, nom du produit
    ensuite) mais rendue par le classifieur PARTAGÉ ``classer_produit`` — celui
    de la composition et du moteur PDF. Une classe inventée ici ferait diverger
    « ce qu'on croit avoir » de « ce que le PDF montre ».

    STKCAT8 — DERNIER RECOURS, et le MÊME que celui de la composition
    (STKCAT7) : quand NI la désignation NI le nom du produit ne disent rien,
    la CATÉGORIE TYPÉE tranche. Sans lui, un devis qui vend une PERGOLA
    s'entendrait dire que sa structure « manque au catalogue » et se verrait
    ajouter une SECONDE ligne de structure, en acier — la réparation de kit
    casserait exactement le devis qu'elle prétend compléter. L'ordre est
    inchangé : le nom garde la main, la catégorie ne parle qu'en dernier.
    """
    return (classer_produit(ligne.designation or '')
            or classer_produit(getattr(ligne.produit, 'nom', '') or '')
            or ('structure'
                if _type_equipement(getattr(ligne, 'produit', None))
                == TYPE_EQUIPEMENT_STRUCTURE else None))


def structure_produit_id_du_devis(devis):
    """STKCAT8 — L'ID DU PRODUIT DE STRUCTURE que ce devis VEND, ou ``None``.

    LECTURE, JAMAIS UNE RECOMPOSITION — exactement le principe de
    ``module_batterie_du_devis`` (BATHOMO, « the battery-related features in
    the quote web page should ALWAYS use the quote items ») appliqué à la
    structure : les cartes de taille, les balayages et la réparation de kit
    doivent servir la structure des LIGNES RÉELLES, pas celle qu'un toggle par
    défaut re-choisirait. C'est ce qui empêche un devis ALUMINIUM de recevoir
    une carte Éco/Max chiffrée en ACIER.

    La ligne est reconnue par :func:`_classe_kit_de_ligne` — donc par le
    classifieur PARTAGÉ d'abord, la catégorie typée en dernier recours. La
    PREMIÈRE ligne structure rencontrée fait foi (un devis n'en vend qu'une).
    Ne lève jamais : un devis non sauvegardé, détaché ou sans ligne rend
    ``None``, et l'appelant retombe alors sur son comportement d'hier.
    """
    try:
        lignes = _lignes_produit(devis)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran (D-ENF22-BLE001)
        logger.warning("composition.structure_produit_id_du_devis : erreur ignorée (mode dégradé)", exc_info=True)
        return None
    for ligne in lignes:
        produit = getattr(ligne, 'produit', None)
        if produit is None:
            continue
        if _classe_kit_de_ligne(ligne) == 'structure':
            return getattr(produit, 'pk', None)
    return None


def _est_au_prix_catalogue(ligne):
    """La ligne est-elle restée au prix CATALOGUE, sans remise ?

    Un « non » vaut prix NÉGOCIÉ : une telle ligne n'est jamais supprimée en
    silence (le chemin appelant avertit à la place). Sans produit rattaché on
    ne peut RIEN prouver — donc on répond non, le doute profitant à la ligne.

    QJR555 — enveloppe mince de ``lignes.prix_negocie`` (la définition
    unique) : ``prix_manuel`` compte désormais, même au prix catalogue.
    """
    produit = getattr(ligne, 'produit', None)
    if produit is None or not _has_price(produit):
        return False
    return not prix_negocie(ligne, prix_reference=produit.prix_vente)


def _options_a_reparer(devis, lignes, *, kwc, watt, nb_panneaux,
                       avec_batterie):
    """QJR81 — LES vues d'option que la réparation doit traiter, une par une.

    Constat QB81 : sur un devis « Les deux » dont les DEUX optimums divergent
    (8 panneaux sans stockage, 12 avec), la réparation composait UN kit
    dimensionné sur le compte SANS et écrivait ses lignes en COMMUN
    (``variante=''``). La resynchronisation PVSTR refuse ensuite — par design,
    et à raison — de porter une ferrure commune au compte d'une seule option :
    l'option AVEC restait donc durablement sous-structurée, et son forfait de
    pose par panneau sous-facturé.

    Rend une liste de vues ``{variante, kwc, watt, nb_panneaux, scenario,
    lignes}`` :

    * devis NON varianté (tous ceux d'hier, et tout devis mono-option) ⇒ UNE
      seule vue COMMUNE, avec exactement les paramètres reçus : comportement
      strictement inchangé ;
    * devis varianté dont les deux options portent le MÊME champ PV ⇒ une
      seule vue commune elle aussi (rien ne les distingue, une ligne commune
      est correcte pour les deux) ;
    * devis varianté DIVERGENT ⇒ DEUX vues, chacune sur SON propre compte de
      panneaux (lu par ``cible_depuis_lignes``, la lecture par variante déjà
      en service) et sur SON propre scénario.
    """
    commune = [{
        'variante': VARIANTE_COMMUNE,
        'kwc': kwc,
        'watt': watt,
        'nb_panneaux': nb_panneaux,
        'scenario': (COMPOSITION_AVEC if avec_batterie
                     else COMPOSITION_SANS),
        'lignes': lignes,
    }]
    if not any((getattr(ligne, 'variante', '') or '') for ligne in lignes):
        return commune

    cibles = {variante: cible_depuis_lignes(devis, variante)
              for variante in (VARIANTE_SANS, VARIANTE_AVEC)}
    comptes = {variante: int(cible.get('panneaux') or 0)
               for variante, cible in cibles.items()}
    if comptes[VARIANTE_SANS] == comptes[VARIANTE_AVEC]:
        # Les deux options décrivent le MÊME champ PV : une ligne commune les
        # sert toutes les deux, et c'est ce que ce dépôt écrivait déjà.
        return commune

    vues = []
    for variante, scenario in ((VARIANTE_SANS, COMPOSITION_SANS),
                               (VARIANTE_AVEC, COMPOSITION_AVEC)):
        cible = cibles[variante]
        if comptes[variante] <= 0 or float(cible.get('kwc') or 0) <= 0:
            # Une option sans aucune ligne panneau n'est pas dimensionnable :
            # on ne devine pas son champ (règle « zéro chiffre inventé »).
            continue
        vues.append({
            'variante': variante,
            'kwc': cible['kwc'],
            'watt': cible['panel_watt'],
            'nb_panneaux': comptes[variante],
            'scenario': scenario,
            'lignes': lignes_de_variante(lignes, variante),
        })
    return vues or commune


def _completer_kit_residentiel(devis, *, kwc, watt, nb_panneaux,
                               avec_batterie, avertissements):
    """Ajoute les lignes du kit résidentiel ABSENTES du devis. N'écrit RIEN
    d'autre : aucune ligne existante n'est touchée (voir le bloc PVHEAL).

    ``avertissements`` est enrichi sur place pour chaque classe manquante que
    le catalogue ne sait pas servir. Rend le nombre de lignes AJOUTÉES.

    QJR81 — LA RÉPARATION HÉRITE DES RÈGLES DE LA CRÉATION. Le « kit attendu »
    se composait ici par un appel DIRECT à ``composition_residentielle``, sans
    la carte des marques épinglées (PVMRQ), sans l'ordre de lignes de la
    société (PVORD) et sans la phase électrique déclarée du client
    (PVCOMPAT) : ce chemin pouvait donc coter une marque et une phase
    d'onduleur que le chemin de création s'interdit. Il passe désormais par
    ``pipeline.composer`` — LE composeur, celui de l'aperçu et de la création —
    et il ESTAMPILLE la variante de l'option qu'il répare.

    QJR221 — ET IL HÉRITE AUSSI DU **GAMME DU DEVIS**. L'intention partait sans
    ``gamme_nom_devis``, donc ``carte_marques_composition(company, None)``
    résolvait la carte de marques PAR DÉFAUT de la société pendant que la
    moitié CHIRURGICALE de la même resynchro (``_pick_product(..., gamme=
    gamme_nom(devis))``) utilisait la vraie gamme : un devis Premium d'une
    société à ``deux_gammes=True`` se faisait compléter avec les marques de
    l'autre gamme. Une société mono-gamme est byte-identique (``gamme_nom``
    rend alors la même chose que le défaut).
    """
    if float(kwc or 0) <= 0:
        # Sans puissance, le kit n'est pas dimensionnable : on ne devine pas.
        return 0

    lignes = _lignes_produit(devis)

    # PVCOMPAT (QJR81) — le RACCORDEMENT déclaré du client descend jusqu'à la
    # réparation, comme il descend jusqu'à la création : un client monophasé ne
    # doit pas se voir compléter un kit autour d'un onduleur triphasé.
    # « inconnu »/absent ⇒ ``None`` ⇒ aucun filtre, composition inchangée.
    from apps.ventes.compatibilites import normaliser_phase
    from apps.crm.selectors import lead_du_devis  # QJR585 — résolveur unique
    phase = normaliser_phase(
        getattr(lead_du_devis(devis), 'raccordement', None))

    catalogue = catalogue_de_la_societe(devis.company)
    taux_tva = (devis.taux_tva if devis.taux_tva is not None
                else Decimal('20'))
    # QJR221 — LA GAMME DU DEVIS, lue par LA fonction qui la lit partout
    # ailleurs dans la resynchro (``domain.gammes.gamme_nom``) : une seule
    # définition, jamais une seconde lecture d'``etude_params['gamme']``.
    from apps.ventes.domain.gammes import gamme_nom
    gamme_devis = gamme_nom(devis)
    # STKCAT8 — ET IL HÉRITE AUSSI DE LA STRUCTURE DU DEVIS. Sans elle,
    # l'intention partait sur le défaut ``structure_type='acier'`` : un devis
    # aluminium (ou à pergola) dont une SEULE option manquait sa ligne
    # structure se la voyait compléter EN ACIER, c'est-à-dire avec un matériau
    # que ce devis ne vend pas. ``None`` (aucune ligne structure encore
    # vendue) ⇒ comportement d'hier, strictement inchangé.
    structure_devis = structure_produit_id_du_devis(devis)

    # Les lignes ajoutées se rangent APRÈS l'existant — sections et notes
    # COMPRISES : l'ordre d'affichage du commercial n'est jamais réécrit, et
    # une note de bas de devis ne doit pas se retrouver au milieu du kit.
    ordre = max([int(ligne.ordre or 0)
                 for ligne in devis.lignes.all()] or [0])
    ajoutees = 0
    # Une classe que le catalogue ne sait pas servir se dit UNE fois, même
    # quand deux options la réclament : deux fois le même message ferait
    # croire à deux manques distincts.
    deja_dit = set()
    # ACAL90 (D-ACAL-22) — les classes RETIRÉES À LA MAIN ne sont jamais
    # recréées ; la réponse le DIT (une fois par classe).
    from apps.ventes.domain.lignes import classes_kit_retirees
    from apps.ventes.domain.regles_calcul import (
        REGLES_CORRIGEES_2710, regles_au_moins)
    retirees = set(classes_kit_retirees(devis))

    for vue in _options_a_reparer(devis, lignes, kwc=kwc, watt=watt,
                                  nb_panneaux=nb_panneaux,
                                  avec_batterie=avec_batterie):
        lignes_vue = vue['lignes']
        presentes = set()
        onduleurs = []
        for ligne in lignes_vue:
            classe = _classe_kit_de_ligne(ligne)
            if classe:
                presentes.add(classe)
            if classe in ('onduleur_reseau', 'onduleur_hybride'):
                onduleurs.append(ligne)

        huawei = any(
            'huawei' in _sans_accents('%s %s %s' % (
                ligne.designation or '',
                getattr(ligne.produit, 'nom', '') or '',
                getattr(ligne.produit, 'marque', '') or ''))
            for ligne in onduleurs)

        attendu = composer(IntentionComposition(
            company=devis.company,
            kwc=vue['kwc'],
            nb_panneaux=vue['nb_panneaux'],
            panel_watt=vue['watt'],
            scenario=vue['scenario'],
            taux_tva=taux_tva,
            phase=phase,
            # QJR221 — la GAMME du devis (PVMRQ) : sans elle, la carte des
            # marques était celle par défaut de la société.
            gamme_nom_devis=gamme_devis,
            # STKCAT8 — la structure RÉELLEMENT vendue par ce devis.
            structure_produit_id=structure_devis,
            # PVOND — ce chemin SAIT avertir : un vivier batterie vide remonte
            # à l'écran plutôt que de disparaître dans un kit silencieusement
            # amputé.
            avertissements=avertissements,
            variante=vue['variante'],
            # RSIZ5 — un devis aux règles d'origine (< 3) garde ses paires.
            paires_mppt_derivees=regles_au_moins(
                devis, REGLES_CORRIGEES_2710),
        ))
        roles_attendu = list(getattr(attendu, 'roles', ()) or ())
        par_classe = {}
        for index, spec in enumerate(attendu):
            classe = classer_produit(spec.designation)
            # STKCAT8 — un produit que le NOM ne classe pas (une pergola) est
            # quand même une structure : c'est le RÔLE ÉMIS par la composition
            # qui le dit. Sans ce repli, la structure composée serait invisible
            # ici et le kit se plaindrait d'une structure « absente du
            # catalogue » alors qu'elle vient d'être choisie.
            if classe is None and index < len(roles_attendu):
                if str(roles_attendu[index]).startswith('structure'):
                    classe = 'structure'
            if classe and classe not in par_classe:
                par_classe[classe] = spec

        # Le duo Smart Meter + clé Wifi ne sort de la composition que si
        # l'onduleur QU'ELLE a choisi est un Huawei — or ici c'est celui du
        # DEVIS qui décide. On le retrouve donc directement au catalogue (même
        # choix que la composition : le premier produit tarifé de la classe, à
        # l'unité). Sans ce rattrapage, un devis Huawei face à un catalogue
        # dont l'hybride est un Deye s'entendrait dire, à tort, que son Smart
        # Meter manque au catalogue.
        if huawei:
            for classe in ('smart_meter', 'wifi_dongle'):
                if classe in par_classe or classe in presentes:
                    continue
                produit = next(
                    (p for p in catalogue
                     if classer_produit(getattr(p, 'nom', '')) == classe
                     and _has_price(p)), None)
                if produit is not None:
                    par_classe[classe] = LigneKit(
                        produit=produit, designation=produit.nom, quantite=1,
                        prix_unitaire=Decimal(produit.prix_vente),
                        variante=vue['variante'])

        for classe in CLASSES_KIT_COMPLETABLES:
            if classe in presentes:
                continue
            if classe in ('smart_meter', 'wifi_dongle') and not huawei:
                continue
            if classe in retirees:
                cle_dite = ('retire', classe)
                if cle_dite not in deja_dit:
                    deja_dit.add(cle_dite)
                    avertissements.append(AVERTISSEMENTS_KIT_RETIRE[classe])
                continue
            spec = par_classe.get(classe)
            if spec is None:
                if classe not in deja_dit:
                    deja_dit.add(classe)
                    avertissements.append(AVERTISSEMENTS_KIT_ABSENT[classe])
                continue
            ordre += 1
            # STKCAT23 (bis) — le rôle ÉMIS voyage avec la ligne : la classe
            # complétée EST le rôle, sauf « structure » où le nom du produit
            # tranche (acier/alu → alias, sinon générique), même règle que
            # role_structure_du_produit.
            role_emis = (role_structure_du_produit(spec.produit)
                         if classe == 'structure' else classe)
            creer_ligne(
                devis, produit=spec.produit,
                designation=spec.designation,
                quantite=Decimal(str(spec.quantite)),
                prix_unitaire=Decimal(spec.prix_unitaire),
                remise=Decimal('0'), ordre=ordre,
                role_devis=role_emis,
                # QJR81 — l'option que cette ligne SERT. Vide (le cas de tout
                # devis non varianté) ⇒ ligne COMMUNE, comme avant.
                variante=getattr(spec, 'variante', '') or '')
            ajoutees += 1
    return ajoutees


def _refuser_couple_panneau_onduleur_impossible(devis, lignes, lignes_panneau,
                                                cible_panneaux, watt, gamme,
                                                modeles=None):
    """DEV-202608-0016 — la resynchro 3D n'ÉCRIT PAS une composition impossible.

    L'outil 3D a posé 25 panneaux Canadian Solar 710 Wc (Isc 18,59 A par
    chaîne) sur un devis dont l'onduleur vendu est un Deye 5 kW monophasé dont
    chaque entrée MPPT admet 17 A en court-circuit. La resynchro prenait
    ``layout.result.panels`` pour vérité et écrivait la ligne sans jamais
    regarder l'onduleur du devis : le couple est physiquement impossible — UNE
    chaîne seule sort déjà de la borne — et rien ne le disait.

    LE VERDICT N'EST PAS RÉÉCRIT ICI : on appelle ``verdict_panneau_onduleur``,
    la logique compose-time qui existait déjà et qui n'avait simplement jamais
    été branchée sur ce chemin. Elle ne conclut ``incompatible`` que si AUCUNE
    configuration de chaînes n'évite un BLOQUANT — c'est-à-dire quand le couple
    lui-même est en cause, jamais parce que le compte du calepinage tombe mal.
    Les chiffres cités viennent des deux FICHES TECHNIQUES (règle fondateur du
    21/08/2026 : aucun seuil, aucune marge, aucun ratio inventé).

    Lève ``SyncLayoutError`` AVANT toute écriture — la transaction reste
    intacte. Un couple ``compatible``/``sous réserve``/``inconnu`` passe : une
    fiche muette ne fait pas un refus (c'est le domaine de PVFCH).
    """
    from apps.ventes.compatibilites import (STATUT_INCOMPATIBLE,
                                            verdict_panneau_onduleur)

    if cible_panneaux <= 0:
        return

    # ACAL63 — modèles DÉSIGNÉS : CHAQUE modèle est jugé, à son compte.
    juges = []
    if modeles:
        from apps.ventes.domain.geometrie import _produit_designe
        for modele in modeles:
            produit_m = (_produit_designe(devis.company,
                                          modele.get('produit_id'))
                         if modele.get('produit_id') else None)
            if produit_m is not None:
                juges.append((produit_m, int(modele.get('count') or 0)))
    if not juges:
        # Le panneau CONCERNÉ : celui que la resynchro va ajuster (la ligne
        # dominante, même politique que l'écriture plus bas), ou celui
        # qu'elle créerait s'il n'y a encore aucune ligne panneau.
        candidats = [li for li in lignes_panneau
                     if getattr(li, 'produit', None) is not None]
        if candidats:
            panneau = max(candidats,
                          key=lambda li: Decimal(str(li.quantite or 0))).produit
        else:
            panneau = _pick_product(devis.company, _is_panel, watt=watt,
                                    role='panneau', gamme=gamme)
        if panneau is None:
            return
        juges = [(panneau, cible_panneaux)]

    onduleurs = [li.produit for li in lignes
                 if getattr(li, 'produit', None) is not None
                 and (_classe_ligne(li, _is_hybrid_inverter)
                      or _classe_ligne(li, _is_reseau_inverter))]
    for panneau, compte_juge in juges:
        for onduleur in onduleurs:
            verdict = verdict_panneau_onduleur(panneau, onduleur)
            if verdict.get('statut') != STATUT_INCOMPATIBLE:
                continue
            raisons = verdict.get('raisons') or []
            raise SyncLayoutError(
                '%d panneaux « %s » sont incompatibles avec « %s » : %s. '
                'Corrigez le nombre de panneaux ou changez d\'onduleur — le '
                'devis n\'a pas été modifié.'
                % (compte_juge, getattr(panneau, 'nom', '') or 'panneau',
                   getattr(onduleur, 'nom', '') or 'onduleur',
                   raisons[0] if raisons else
                   'le couple sort des bornes de la fiche constructeur'),
                revision_possible=False)


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER : ils s'exécutent après toutes les définitions de
# ce module, et ils visent le module qui PORTE le corps — jamais la façade
# `services.py`, dont les ré-exports s'exécutent dans l'ordre des tâches et
# ne portent donc pas encore les noms des tâches suivantes.
from apps.ventes.domain.catalogue import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _has_price,
    _is_hybrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    _pick_product,
    _sans_accents,
    catalogue_de_la_societe,
    classer_produit,
)
from apps.ventes.domain.lignes import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _classe_ligne,
    _lignes_produit,
    cible_depuis_lignes,
    creer_ligne,
    lignes_de_variante,
    prix_negocie,
)
from apps.ventes.domain.etape_composer import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    COMPOSITION_AVEC,
    COMPOSITION_SANS,
    IntentionComposition,
    composer,
)
from apps.ventes.domain.resynchronisation import SyncLayoutError  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
