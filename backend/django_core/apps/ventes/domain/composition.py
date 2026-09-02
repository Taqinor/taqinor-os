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
import math

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


def _statut_couple_panneau(panneau, onduleurs):
    """PVCOMPAT — le PIRE verdict d'un panneau face aux onduleurs VENDUS.

    En forme deux options les DEUX onduleurs partent au devis : un panneau qui
    coince avec l'un des deux coince pour le devis entier. L'ordre de sévérité
    est celui du noyau — ``incompatible`` (bloquant matériel) l'emporte sur
    ``reserve`` (production dégradée), qui l'emporte sur ``inconnu`` (fiche
    incomplète), qui l'emporte sur ``compatible``.
    """
    from apps.ventes.compatibilites import (
        STATUT_COMPATIBLE, STATUT_INCOMPATIBLE, STATUT_INCONNU,
        STATUT_RESERVE, verdict_panneau_onduleur)
    severite = {STATUT_INCOMPATIBLE: 3, STATUT_RESERVE: 2,
                STATUT_INCONNU: 1, STATUT_COMPATIBLE: 0}
    pire = (0, STATUT_COMPATIBLE, None)
    for onduleur in onduleurs:
        verdict = verdict_panneau_onduleur(panneau, onduleur)
        rang = severite.get(verdict['statut'], 0)
        if rang > pire[0]:
            pire = (rang, verdict['statut'], (onduleur, verdict))
    return pire[1], pire[2]


def composition_residentielle(produits, *, kwc, panel_watt, nb_panneaux=0,
                              avec_batterie=False, structure_type='acier',
                              taux_tva=Decimal('20'), avertissements=None,
                              deux_options=False, marques=None,
                              ordre_lignes=None, mppt_paires=1, phase=None,
                              batterie_cible_kwh=None,
                              batterie_module_kwh=None,
                              hors_reseau=False):
    """Le KIT résidentiel COMPLET composé depuis un catalogue.

    U3 (fondateur 20/08/2026) — CETTE FONCTION EST LA SOURCE DE VÉRITÉ de la
    composition résidentielle. Elle porte désormais TOUTES les règles qui
    n'existaient que dans ``solar.js::autoFillLines`` :

      · ``marques`` — PVMRQ, carte ``{rôle: marque}`` DÉJÀ résolue par
        l'appelant (via ``marque_preferee``, seule voie de lecture du réglage
        gammes ; cette fonction reste PURE et ne requête rien). Une marque
        épinglée restreint le vivier de son rôle À ELLE SEULE ; sans candidat,
        le vivier est VIDE — jamais un repli silencieux sur une autre marque —
        et le rôle est consigné dans ``.marques_manquantes``.
      · ``ordre_lignes`` — PVORD, séquence de rôles préférée ; absente, l'ordre
        canonique du simulateur est rendu tel quel.
      · ``mppt_paires`` — C4/PVCBL, nombre de paires de câble DC descendantes
        (60 m par paire) ; repli fondateur explicite à 1 paire.
      · ``phase`` — PVCOMPAT, le RACCORDEMENT déclaré par le client
        (``'monophase'`` / ``'triphase'``, cf.
        ``compatibilites.normaliser_phase``). Monophasé : les onduleurs
        triphasés sortent du vivier ; triphasé : le départage à puissance égale
        préfère DUREMENT le triphasé. ``None`` (défaut) ⇒ aucun filtre, donc
        comportement byte-identique à l'historique.

    PVCOMPAT (fondateur 20/08/2026) — LE COUPLE PANNEAU/ONDULEUR EST VÉRIFIÉ.
    Le panneau et l'onduleur étaient choisis INDÉPENDAMMENT (l'un au wattage
    demandé, l'autre à la puissance) et rien ne vérifiait qu'ils allaient
    ensemble : « il n'y a pas de PV parce que le courant maxi par MPPT de cet
    onduleur est sous le courant de nos panneaux » ne pouvait pas être dit. Le
    verdict du noyau électrique est désormais consulté APRÈS les deux choix :
    un couple INCOMPATIBLE fait chercher un autre panneau du vivier (marque
    épinglée respectée) ; à défaut, le choix d'origine est CONSERVÉ — jamais
    une composition morte — et le problème est ANNONCÉ par ``avertissements``.

    Le résultat est une ``CompositionLignes`` : une LISTE de ``LigneKit`` (tout
    appelant historique la lit sans rien changer) qui porte en plus les
    métadonnées de la composition (``nb_panneaux``, ``panel_watt_reel``,
    ``kwc_reel``, ``roles``, ``marques_manquantes``) — le dry-run les rend à
    l'écran.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS que la proposition résidentielle rend déjà : les DEUX onduleurs
    (réseau ET hybride) et les batteries dans UN seul devis. C'est le
    découpage que lisent ``optionTotalsTTC`` (écran) et le moteur PDF :
      · option « sans batterie » = tout SAUF batterie + onduleur hybride ;
      · option « avec batterie »  = tout SAUF onduleur réseau.
    Le client compare, puis choisit. Sans ce drapeau (défaut), la composition
    reste MONO-OPTION et byte-identique à l'historique : ``avec_batterie``
    décide seul quel onduleur est vendu — c'est ce que veut le calepinage 3D,
    où le scénario a DÉJÀ été arrêté à l'écran.

    Fonction PURE : elle ne requête rien, n'écrit rien, ne touche aucun statut.
    ``produits`` est un itérable de produits DÉJÀ cantonnés à la société
    appelante (voir ``catalogue_de_la_societe``) ; les produits sans prix de
    vente en sont écartés d'entrée de jeu.

    ``taux_tva`` — le taux du DEVIS. Il servait à reconvertir en HT les trois
    prix forfaitaires que le simulateur exprimait en TTC ; depuis L-FORFAIT
    (fondateur 24/08/2026) ces forfaits sont dictés EN HT et lus au catalogue
    (``stock.Produit.prix_fixe_ht`` / ``prix_par_panneau_ht``), donc plus rien
    ici ne convertit quoi que ce soit. Le paramètre est CONSERVÉ — tous les
    appelants le passent et la TVA reste celle du devis — mais il n'influence
    plus aucun montant composé.

    ``batterie_cible_kwh`` (DIM2, fondateur 24/08/2026) — capacité de stockage
    VISÉE, en kWh, servie par les modules du catalogue. ``None`` (LE DÉFAUT,
    épinglé par un test) ⇒ la règle historique du simulateur reste seule maître
    à bord : ``cible = max(5, arrondi(kwp / 5) × 5)``. **Le devis automatique ne
    passe JAMAIS ce paramètre** : sa batterie reste une conséquence des kWc,
    exactement comme avant. Seul le TABLEAU de dimensionnement
    (``apps.ventes.dimensionnement``) l'utilise, pour EXPLORER le stockage comme
    une deuxième dimension et montrer au fondateur ce qu'une banque plus grande
    changerait — explorer n'est pas décider.

    ``batterie_module_kwh`` (BATHOMO, fondateur 26/08/2026 — « if the quote has
    5 kWh batteries the web page should only show 5 kWh batteries ; and we can
    go up to 30 or 40 kWh using 5 kWh batteries, no problem ») — IMPOSE le
    calibre (``5`` ou ``10``) de la banque, plutôt que de laisser le choix « au
    plus proche de la cible » ci-dessous décider. Un appelant qui connaît déjà
    le module RÉELLEMENT engagé par un devis (lu sur ses LIGNES vendues, jamais
    redeviné ici) l'impose ainsi pour toute l'échelle qu'il explore : la banque
    grandit alors en N modules de CE calibre — jusqu'à 6-8 packs de 5 kWh pour
    atteindre 30-40 kWh — sans jamais glisser vers l'autre calibre au passage
    d'un multiple de 10 (où le choix « au plus proche » préfère normalement le
    plus gros module). ``None`` (LE DÉFAUT) ⇒ comportement inchangé : le
    calibre le plus proche de ``cible_kwh`` décide, égalité tranchée pour le
    plus gros. Calibre imposé absent du catalogue ⇒ repli silencieux sur ce
    même choix « au plus proche » — jamais une banque vide du seul fait d'un
    calibre non stocké.

    ``hors_reseau`` (QJR-OFFGRID, fondateur 01/09/2026) — le site est ISOLÉ :
    aucun raccordement ONEE, donc AUCUN onduleur réseau ni hybride ne peut
    être vendu. La composition passe alors sur la TROISIÈME famille
    d'onduleur — ``onduleur_offgrid``, même règle des 80 % que les deux
    autres — et le stockage devient OBLIGATOIRE (sans batterie, un site isolé
    n'a pas d'électricité la nuit). Forme MONO-OPTION de type « avec » : le
    drapeau ``deux_options`` est sans objet et il est ignoré. **Aucun repli sur
    un hybride** : sans onduleur autonome tarifé au catalogue, la ligne
    onduleur est ABSENTE et l'appelant refuse (``pipeline.verifier``) — jamais
    un composant substitué en silence (règle fondateur des chiffres vérifiés).
    ``False`` (LE DÉFAUT) ⇒ composition byte-identique à l'historique.

    ``avertissements`` (optionnel) est LE CANAL de cette fonction : une liste
    que l'appelant fournit et que la composition enrichit sur place quand elle
    a dû composer AUTREMENT que demandé — aujourd'hui le seul cas est un vivier
    batterie VIDE alors que ``avec_batterie`` était demandé. Sans ce canal, un
    devis « avec batterie » pouvait partir SANS aucune ligne batterie et sans
    que personne ne l'apprenne. Absent (``None``) ⇒ comportement inchangé.

    Rend la liste ORDONNÉE des ``LigneKit`` à créer, dans l'ordre canonique du
    simulateur, quantités nulles exclues. Liste vide si la puissance est nulle.
    """
    kwp = float(kwc or 0)
    if kwp <= 0:
        return []
    watt = float(panel_watt or 0) or 550.0

    # QJR-OFFGRID — un site ISOLÉ n'a qu'UNE composition possible : onduleur
    # autonome + stockage. La forme deux options (réseau / hybride) n'a alors
    # aucun sens et le drapeau batterie n'est plus une question.
    # QJR400 — LA RÈGLE VIENT DU NOYAU (``utils.options.deux_options_composables``),
    # elle n'est plus écrite ici : c'est le MÊME propriétaire que le prédicat
    # « devis à deux options » du document.
    from apps.ventes.utils.options import deux_options_composables
    hors_reseau = bool(hors_reseau)
    deux_options = deux_options_composables(deux_options, hors_reseau)
    if hors_reseau:
        avec_batterie = True

    # Catalogue indexé par catégorie. Le filtre de prix passe ICI, une fois
    # pour toutes : aucune branche ne peut ensuite coter un produit non tarifé.
    par_type = {}
    for produit in produits:
        if not _has_price(produit):
            continue
        categorie = classer_produit(getattr(produit, 'nom', ''))
        if categorie:
            par_type.setdefault(categorie, []).append(produit)

    # ── PVMRQ (U3) — restriction par marque épinglée ────────────────────────
    # Miroir EXACT de ``_filtrerParMarque`` (solar.js) : sans préférence, le
    # vivier passe TEL QUEL ; avec une préférence sans aucun candidat, le
    # vivier est VIDE et le rôle est consigné UNE fois (jamais un repli
    # silencieux sur une autre marque — ordre fondateur #5).
    carte_marques = marques if isinstance(marques, dict) else {}
    marques_manquantes = []
    _roles_signales = set()

    def par_marque(pool, role):
        source = list(pool or [])
        marque = str(carte_marques.get(role) or '').strip()
        if not marque:
            return source
        filtres = [p for p in source if _marque_correspond(p, marque)]
        if not filtres and role not in _roles_signales:
            _roles_signales.add(role)
            marques_manquantes.append({'role': role, 'marque': marque})
        return filtres

    def premier(categorie):
        pool = par_marque(par_type.get(categorie), categorie)
        return pool[0] if pool else None

    # ── Panneaux : compte explicite, sinon dérivé de la puissance ──
    # U1 — dérivation AU PLAFOND (``plafond_panneaux``) : 5 kWc en 710 Wc font
    # 8 panneaux, jamais 7. Un compte fourni explicitement est déjà un ENTIER
    # de panneaux ; il garde son arrondi au plus proche.
    nb = (_arrondi_js(nb_panneaux) if float(nb_panneaux or 0) > 0
          else max(1, plafond_panneaux(kwp * 1000 / watt)))

    # ── Onduleur : plus petit modèle ≥ 80 % de la puissance, sinon le plus
    # gros du catalogue ; à puissance égale, Triphasé au-delà de 10 kW ──
    seuil = kwp * 0.8

    # PVCOMPAT — le raccordement déclaré, normalisé une seule fois.
    from apps.ventes.compatibilites import (
        PHASE_MONO, PHASE_TRI, avertissement_raccordement, normaliser_phase)
    phase_client = normaliser_phase(phase)

    def _avertir(message):
        """Consigne un avertissement UNE fois (deux onduleurs, un message)."""
        if avertissements is None:
            logger.warning('PVCOMPAT: %s', message)
            return
        if message not in avertissements:
            avertissements.append(message)

    # PVCOMPAT — catégories dont le vivier a dû IGNORER le raccordement
    # déclaré. On ne prévient PAS ici : les deux catégories sont toujours
    # explorées (réseau ET hybride) alors qu'une seule part au devis en forme
    # mono-option — avertir depuis le vivier ferait crier l'onduleur invendu.
    # Le message est prononcé plus bas, pour les seules catégories VENDUES.
    replis_phase = {}
    # L-TRI — catégories dont le vivier TRIPHASÉ est VIDE alors que le client
    # est triphasé : la composition a REFUSÉ de coter un monophasé. Même
    # discipline que ``replis_phase`` — on ne prononce le message que pour les
    # catégories réellement VENDUES.
    refus_tri = {}

    def choisir_onduleur(categorie):
        candidats = []
        # PVOND — VERROU DE COMPLÉTUDE, miroir de solar.js::pickInverter : un
        # onduleur au contrat incomplet est écarté de l'auto-composition AVANT
        # le tri par puissance, exactement comme à l'écran.
        # PVCOMPAT/L-TRI — puis le RACCORDEMENT du client réduit le vivier :
        # monophasé (les triphasés sortent, repli toléré) comme triphasé (les
        # monophasés sortent, AUCUN repli).
        complets = _filtrer_onduleurs_complets(
            par_marque(par_type.get(categorie), categorie))
        vivier, replie = _vivier_onduleurs_par_phase(complets, phase_client)
        replis_phase[categorie] = replie
        refus_tri[categorie] = False
        for produit in vivier:
            kw = _parse_kw(getattr(produit, 'nom', ''))
            if kw and kw > 0:
                candidats.append((kw, getattr(produit, 'id', 0) or 0, produit))
        if not candidats:
            # L-TRI — distinguer « catalogue vide pour cette catégorie »
            # (silence historique) de « il y avait des onduleurs, mais AUCUN
            # triphasé » : ce second cas est un REFUS, et un refus se dit.
            refus_tri[categorie] = bool(
                phase_client == PHASE_TRI and complets)
            return None, None
        candidats.sort(key=lambda c: (c[0], c[1]))
        # Le plus petit modèle ≥ 80 % du kWc : sur un vivier déjà réduit au
        # raccordement du client, ce PLANCHER ne peut plus faire changer de
        # phase — un petit kWc prend simplement le plus petit triphasé.
        valides = [c for c in candidats if c[0] >= seuil] or [candidats[-1]]
        meilleure = valides[0][0]
        memes = [c for c in valides if c[0] == meilleure]
        # PVCOMPAT — un raccordement DÉCLARÉ passe devant l'heuristique
        # « ≥ 10 kW ⇒ triphasé » : le client sait de quel abonnement il dispose,
        # la puissance n'en est qu'un indice. Sans déclaration, l'heuristique
        # historique décide seule, à l'identique.
        if phase_client == PHASE_TRI:
            prefere_tri = True
        elif phase_client == PHASE_MONO:
            prefere_tri = False
        else:
            prefere_tri = meilleure >= 10
        assortis = [c for c in memes
                    if _est_triphase(getattr(c[2], 'nom', '')) == prefere_tri]
        retenu = (assortis or memes)[0]
        return retenu[2], retenu[0]

    def quantite_onduleur(kw):
        """Un onduleur suffit dès qu'il couvre le seuil ; sinon on en met assez
        pour absorber le champ (blocs entiers, jamais moins d'un)."""
        if not kw or kw >= seuil:
            return 1
        return max(1, int(math.ceil(kwp / kw)))

    if hors_reseau:
        # QJR-OFFGRID — les deux familles RACCORDÉES ne sont même pas
        # explorées : rien ne pourrait les vendre ici, et les explorer
        # ferait prononcer des avertissements de raccordement sur des
        # onduleurs qui ne partent pas au devis.
        onduleur_reseau = onduleur_hybride = None
        kw_reseau = kw_hybride = None
        onduleur, kw_onduleur = choisir_onduleur('onduleur_offgrid')
    else:
        onduleur_reseau, kw_reseau = choisir_onduleur('onduleur_reseau')
        onduleur_hybride, kw_hybride = choisir_onduleur('onduleur_hybride')
        onduleur = onduleur_hybride if avec_batterie else onduleur_reseau
        kw_onduleur = kw_hybride if avec_batterie else kw_reseau
    # L'onduleur qui PORTE le stockage : l'hybride sur un site raccordé,
    # l'autonome sur un site isolé. C'est lui qui dicte la plage batterie.
    onduleur_stockage = onduleur if hors_reseau else onduleur_hybride

    # PVCOMPAT — le raccordement n'a pas pu être tenu SUR UN ONDULEUR VENDU :
    # on le dit UNE fois. Un repli sur une catégorie qui ne part pas au devis
    # (l'hybride d'un devis « sans batterie », par exemple) ne concerne
    # personne et reste muet.
    _categories_vendues = (
        ('onduleur_offgrid',) if hors_reseau
        else (('onduleur_reseau', 'onduleur_hybride') if deux_options
              else (('onduleur_hybride',) if avec_batterie
                    else ('onduleur_reseau',))))
    _onduleurs_par_categorie = {
        'onduleur_reseau': onduleur_reseau,
        'onduleur_hybride': onduleur_hybride,
        'onduleur_offgrid': onduleur if hors_reseau else None,
    }
    if phase_client and any(
            replis_phase.get(categorie)
            and _onduleurs_par_categorie.get(categorie) is not None
            for categorie in _categories_vendues):
        _avertir(avertissement_raccordement(PHASE_MONO))
    # L-TRI — le raccordement TRIPHASÉ n'a AUCUN onduleur au catalogue sur une
    # catégorie VENDUE : la composition part sans onduleur (jamais un
    # monophasé), et elle le DIT — sinon le devis mentirait par omission.
    if phase_client == PHASE_TRI and any(
            refus_tri.get(categorie) for categorie in _categories_vendues):
        _avertir(avertissement_aucun_onduleur_triphase())
    # U2 — en forme DEUX OPTIONS, le stockage fait partie du devis : les
    # batteries sont composées même si ``avec_batterie`` est faux, puisque
    # c'est l'option « avec » qui les porte.
    veut_batterie = bool(avec_batterie or deux_options)

    # ── Panneau : wattage demandé d'abord, à défaut le plus proche ──
    # PVMRQ — la marque épinglée restreint le vivier AVANT le rapprochement de
    # wattage : la substitution « wattage le plus proche » ne joue plus que
    # DANS la marque retenue, jamais hors d'elle (miroir de l'écran).
    tries = []
    for produit in par_marque(par_type.get('panneau'), 'panneau'):
        w = _parse_watt(getattr(produit, 'nom', ''))
        if w is not None:
            tries.append((w, produit))
    exacts = [c for c in tries if c[0] == int(watt)]
    if exacts:
        # Même départage qu'à l'écran : un Canadien Solar passe devant.
        exacts.sort(key=lambda c: 0 if 'canadien' in _sans_accents(
            getattr(c[1], 'nom', '')) else 1)
        panneau = exacts[0][1]
    elif tries:
        panneau = min(tries, key=lambda c: abs(c[0] - watt))[1]
    else:
        panneau = None

    # ── PVCOMPAT — LE COUPLE PANNEAU / ONDULEUR EST VÉRIFIÉ ────────────────
    # Les deux choix ci-dessus sont INDÉPENDANTS : rien ne garantissait qu'ils
    # allaient ensemble. On demande au noyau électrique son verdict et on agit
    # SANS JAMAIS produire une composition morte :
    #   · incompatible → on cherche un autre panneau du vivier (le vivier DÉJÀ
    #     restreint par la marque épinglée : on ne contourne pas une consigne
    #     de gamme pour réparer une incompatibilité) ; si aucun ne va, on GARDE
    #     le choix d'origine et on DIT le problème ;
    #   · réserve      → on garde et on DIT (écrêtage : ça s'installe, ça
    #     produit moins — le client doit l'apprendre du devis, pas du toit) ;
    #   · inconnu      → on se tait : la fiche incomplète est déjà signalée
    #     ailleurs (verrou de complétude), le répéter ne dirait rien de neuf.
    onduleurs_vendus = [o for o in (
        (onduleur_reseau, onduleur_hybride) if deux_options else (onduleur,))
        if o is not None]
    if panneau is not None and onduleurs_vendus:
        from apps.ventes.compatibilites import (
            STATUT_INCOMPATIBLE, STATUT_RESERVE,
            avertissement_panneau_onduleur)
        statut, coince = _statut_couple_panneau(panneau, onduleurs_vendus)
        if statut == STATUT_INCOMPATIBLE:
            # Repli ORDONNÉ : d'abord les wattages exacts (l'ordre de départage
            # de l'écran), puis les plus proches — la même préférence que le
            # choix initial, appliquée aux candidats restants.
            replis = [c[1] for c in exacts] + [
                c[1] for c in sorted(tries, key=lambda c: abs(c[0] - watt))]
            vus = set()
            for candidat in replis:
                if id(candidat) in vus or candidat is panneau:
                    vus.add(id(candidat))
                    continue
                vus.add(id(candidat))
                statut_bis, coince_bis = _statut_couple_panneau(
                    candidat, onduleurs_vendus)
                if statut_bis != STATUT_INCOMPATIBLE:
                    _avertir(
                        'Panneau remplacé pour compatibilité électrique : '
                        '« %s » ne se raccorde pas à l\'onduleur retenu, '
                        '« %s » a été composé à la place.'
                        % (getattr(panneau, 'nom', '') or '?',
                           getattr(candidat, 'nom', '') or '?'))
                    panneau, statut, coince = candidat, statut_bis, coince_bis
                    break
        if statut in (STATUT_INCOMPATIBLE, STATUT_RESERVE) and coince:
            _avertir(avertissement_panneau_onduleur(
                panneau, coince[0], coince[1]))

    # ── Batteries : cible = kWc arrondi au multiple de 5 (5 kWh au minimum),
    # servie en modules HOMOGÈNES (un seul calibre par banque — voir la garde
    # plus bas, après le choix du vivier) ──
    # TOLÉRANCE DEUX ORTHOGRAPHES : la marque s'écrit « Dyness » (correction
    # fondateur 2026-08-18) ; un produit encore nommé « Deyness » (base non
    # migrée, saisie manuelle, fixture ancienne) doit rester reconnu, sans quoi
    # le vivier retomberait sur TOUTES les batteries du catalogue.
    # DIM2 — une cible EXPLICITE (balayage du stockage) prime sur la règle
    # kWc ; sans elle, la règle historique décide seule, à l'octet près.
    if batterie_cible_kwh is not None and float(batterie_cible_kwh) > 0:
        cible_kwh = max(5, _arrondi_js(float(batterie_cible_kwh) / 5) * 5)
    else:
        cible_kwh = max(5, _arrondi_js(kwp / 5) * 5)
    # PVOND — GARDE BATTERIE PILOTÉ PAR LA DONNÉE (remplace le mot-clé PVG4) :
    # une batterie n'entre au vivier que si sa TENSION NOMINALE tombe dans la
    # PLAGE BATTERIE de l'onduleur retenu ci-dessus. Le repli par mot-clé
    # « haute tension » ne joue QUE lorsque L'ONDULEUR ne déclare aucune plage
    # (catalogue non renseigné : comportement d'hier, byte-identique) ; dès
    # qu'une plage existe, une candidate sans tension mesurée est EXCLUE.
    # Sur un devis SANS batterie, ``onduleur`` vaut l'onduleur réseau : la
    # question ne se pose pas (le vivier n'est lu que si ``avec_batterie``).
    # U2 — la batterie pend TOUJOURS à l'onduleur HYBRIDE : en forme deux
    # options, c'est lui qui décide de la plage, jamais l'onduleur réseau de
    # l'option « sans ».
    # QJR-OFFGRID — sur un site isolé, c'est l'onduleur AUTONOME qui porte le
    # stockage (``onduleur_stockage``), jamais l'hybride (absent ici).
    _plage_bat = _plage_batterie_de_l_onduleur(
        onduleur_stockage if veut_batterie else onduleur)
    # PVMRQ — la compatibilité ÉLECTRIQUE se calcule sur le vivier COMPLET
    # (c'est elle qui alimente l'avertissement « vivier vide », un motif
    # DISTINCT de « marque introuvable ») ; la marque ne restreint qu'ENSUITE.
    # Même ordre que l'écran et que ``_pick_product`` : garde métier d'abord.
    # BATHOMO (26/08/2026, F1 recalé) — DEUX VIVIERS, PAS UN. La
    # COMPATIBILITÉ (tension) est un fait électrique qui s'applique TOUJOURS ;
    # le STOCK, lui, ne s'applique QU'AU CHOIX ÉCONOMIQUE (une composition
    # SANS pin — une NOUVELLE sélection). Un devis qui vend DÉJÀ un calibre
    # (``batterie_module_kwh``) l'a COMMIS : la loi fondateur est « la page
    # suit les articles du devis », donc le pin reste composable même si son
    # stock est tombé à 0 depuis — repeindre la banque en 10 kWh (un module
    # que ce devis ne vend PAS) serait exactement la violation que ce
    # correctif devait éliminer, et avec les DEUX calibres à 0 la page
    # mourrait sur un devis pourtant déjà signé. SCOPÉ AU RÔLE BATTERIE SEUL :
    # aucun autre rôle (panneaux/onduleurs) n'a cette garde de stock — un
    # filtre global casserait la composition pour un catalogue au stock non
    # suivi (cf. ``_batterie_en_stock``).
    batteries_compat = [(_parse_kwh(getattr(p, 'nom', '')), p)
                        for p in par_marque(
                            [p for p in par_type.get('batterie') or []
                             if _batterie_compatible(p, _plage_bat)],
                            'batterie')]
    dyness_compat = [b for b in batteries_compat
                     if any(marque in _sans_accents(getattr(b[1], 'nom', ''))
                            for marque in ('dyness', 'deyness'))]
    vivier_compat = dyness_compat or batteries_compat
    # Le vivier ÉCONOMIQUE (nouvelle sélection, sans pin) : compatible ET en
    # stock — sous-ensemble du vivier compatible, jamais un second filtrage
    # indépendant (une marque non stockée reste hors des deux).
    vivier_stock = [(cap, p) for cap, p in vivier_compat
                    if _batterie_en_stock(p)]
    # A1 — ``bat5_compat``/``bat10_compat`` (le vivier COMPATIBLE, 5/10 SEUL)
    # ont disparu : le pin résout désormais N'IMPORTE QUEL calibre du vivier
    # compatible (recherche directe dans ``vivier_compat``, voir plus bas) —
    # seul le repli ÉCONOMIQUE (sans pin) reste borné à 5/10, et lui reste
    # STOCK-gaté.
    bat5_stock = next((p for cap, p in vivier_stock if cap == 5), None)
    bat10_stock = next((p for cap, p in vivier_stock if cap == 10), None)
    # ── BANQUE HOMOGÈNE + ÉCONOMIE DE CALIBRE (fondateur 26/08/2026) ──
    # JAMAIS un mélange de calibres dans la même banque : c'est électriquement
    # interdit (des modules 5 kWh et 10 kWh en parallèle/série ne s'équilibrent
    # pas), et c'est ce mélange, composé côté serveur, qui a fait retirer le
    # Dyness 10 kWh du stock de production (cf. ``apps.stock.management.
    # commands.seed_catalogue``).
    #
    # Pour CHAQUE calibre disponible (en stock, compatible, et dont le
    # plafond ``bat_max_modules_par_banc`` n'est pas dépassé — cf.
    # ``_max_modules_par_banc``), UNE SEULE candidate homogène est générée :
    # le plus petit N de modules IDENTIQUES qui ATTEINT OU DÉPASSE
    # ``cible_kwh`` (plafond arrondi, jamais un manque — « extra batteries
    # might add extra panels with extra cost, that is still fine »). Parmi
    # les candidates retenues, celle au prix TTC TOTAL LE PLUS BAS gagne,
    # égalité tranchée par le MOINS de modules (fondateur 26/08/2026 :
    # l'économie décide, pas une préférence de calibre — 2×5 kWh à 28 000
    # TTC bat 1×10 kWh à 30 000 pour une cible de 10 kWh dès que les modules
    # 5 kWh sont moins chers au kWh). C'est ce qui fait grandir la banque en
    # 5 kWh, sans jamais glisser vers le 10 kWh, tant que ce dernier reste
    # plus cher au kWh — et REDEVENIR compétitif tout seul si son prix ou
    # son stock changent. Aucun mélange n'est jamais formé : au plus UN des
    # deux compteurs ci-dessous est non nul.
    #
    # ``batterie_module_kwh`` COURT-CIRCUITE ce choix économique quand
    # l'appelant impose un calibre précis (module déjà engagé par un devis) :
    # la banque grandit alors en N modules de CE seul calibre, jamais l'autre
    # — c'est ce qui garantit que l'échelle explorée pour UN devis ne bascule
    # jamais vers un autre calibre que celui qu'il vend déjà. LE PIN LIT LE
    # VIVIER COMPATIBLE (F1) — jamais le vivier stock : le module déjà engagé
    # reste composable même hors stock, SEULE la sélection ÉCONOMIQUE (sans
    # pin) est stock-gatée.

    def _candidat(calibre, produit):
        """Une candidate homogène ``(prix_ttc, n, calibre, produit)`` pour ce
        calibre, ou ``None`` si son plafond fondateur de modules est dépassé."""
        n = max(1, int(math.ceil(cible_kwh / calibre - 1e-9)))
        plafond = _max_modules_par_banc(produit)
        if plafond is not None and n > plafond:
            return None
        prix_ttc = _prix_ttc_batterie(produit, n, taux_tva)
        return (round(prix_ttc, 2), n, calibre, produit)

    calibre_impose = None
    if batterie_module_kwh is not None:
        try:
            calibre_impose = float(batterie_module_kwh)
        except (TypeError, ValueError):
            calibre_impose = None

    # A1 (revue adversariale Fable, 26/08/2026) — LE PIN N'EST PLUS UN
    # WHITELIST 5/10. ``module_batterie_du_devis`` (dimensionnement.py, F6)
    # rend N'IMPORTE QUEL calibre positif lu sur les lignes du devis (le
    # Deye BOS-B-Pack16, 16 kWh, est un produit RÉEL des gammes) : un pin qui
    # ne matchait QUE 5.0/10.0 laissait un devis 16 kWh retomber en silence
    # sur le choix économique 5/10 — repeindre la banque dans un calibre que
    # ce devis ne vend PAS, exactement la violation que ce chantier devait
    # fermer. Résolution par CALIBRE LE PLUS PROCHE dans le vivier COMPATIBLE
    # (tolérance ±1 kWh, la même que ``_compter_modules_batterie``/
    # ``module_batterie_du_devis``), pour N'IMPORTE QUEL calibre du vivier —
    # jamais restreinte à 5/10.
    #
    # PIN SANS CORRESPONDANCE ⇒ AUCUN REPLI ÉCONOMIQUE (nouveauté A1) :
    # « honest absence beats a wrong pairing » (Fable) — si le calibre déjà
    # vendu n'existe même pas dans le vivier compatible (ex. un système HAUTE
    # TENSION jamais composable sous un onduleur basse tension), retomber sur
    # le choix économique 5/10 fabriquerait une banque d'un AUTRE calibre que
    # celui du devis. La composition part alors SANS batterie (même chemin
    # honnête que le vivier vide), et — en amont — l'échelle de paliers
    # (``dimensionnement.echelle_paliers_batterie``) omet purement ses rangs
    # au lieu d'en proposer dans le mauvais calibre : chaque cible sondée
    # retombe sur une capacité nulle, ``reels`` reste vide, la fonction rend
    # ``[]``. Un pin qui MATCHE mais dont le plafond de modules rejette la
    # seule candidate possible garde en revanche le repli économique
    # ci-dessous (F3, comportement inchangé — un plafond n'est pas une
    # absence de calibre).
    candidat_impose = None
    pin_sans_correspondance = False
    if calibre_impose is not None:
        correspondance = next(
            ((cap, p) for cap, p in vivier_compat
             if abs(cap - calibre_impose) < 1.0), None)
        if correspondance is not None:
            cap_trouve, produit_trouve = correspondance
            candidat_impose = _candidat(cap_trouve, produit_trouve)
        else:
            pin_sans_correspondance = True

    candidats = []
    if candidat_impose is not None:
        candidats = [candidat_impose]
    elif not pin_sans_correspondance:
        # Aucun calibre imposé, OU un calibre imposé dont le plafond de
        # modules interdit la seule candidate qu'il permettrait : repli sur
        # le choix économique parmi les calibres 5/10 EN STOCK — jamais une
        # banque vide du seul fait d'un calibre non stocké ou plafonné, MAIS
        # jamais non plus un calibre hors stock ressuscité par ce repli
        # (F1 : le repli économique reste stock-gaté, seul le PIN d'origine
        # bypassait le stock).
        for calibre, produit in ((5, bat5_stock), (10, bat10_stock)):
            if produit is None:
                continue
            candidat = _candidat(calibre, produit)
            if candidat is not None:
                candidats.append(candidat)

    if veut_batterie and not candidats:
        # AUCUNE candidate — via le pin ou l'économie : la composition part
        # sans batterie (jamais une banque fabriquée), mais elle le DIT —
        # sinon le devis mentait par omission. C'est CETTE garde qui rend
        # l'option « avec batterie » honnêtement non-servable (``avec_ok``/
        # ``variantes_servables``, quote_engine/builder.py) : aucune ligne
        # batterie n'est composée, donc ``has_batterie`` retombe à faux tout
        # seul — aucune machinerie neuve à câbler ici.
        #
        # F5 — LE DIAGNOSTIC SUIT LA VRAIE CAUSE (quatre messages distincts,
        # jamais « changez d'onduleur » quand le vrai geste est de
        # réapprovisionner, d'augmenter un plafond, ou de vérifier le
        # calibre) :
        #   0. (A1) le devis vend DÉJÀ un calibre précis, et ce calibre
        #      N'EXISTE PAS dans le vivier compatible → message dédié,
        #      jamais confondu avec « aucune batterie compatible » (le
        #      vivier peut très bien porter D'AUTRES calibres compatibles).
        #   1. vivier COMPATIBLE vide → aucune batterie ne convient à cet
        #      onduleur (tension) : le message historique.
        #   2. vivier compatible non vide mais vivier STOCK vide, et aucun
        #      pin n'a résolu (F3/F1) → rupture de stock.
        #   3. sinon (du stock existait ou un pin compatible existait) mais
        #      ``candidats`` est quand même vide → le plafond de modules a
        #      rejeté toutes les candidates possibles (F3).
        if pin_sans_correspondance:
            message = avertissement_batterie_pin_sans_correspondance(
                calibre_impose)
        elif not vivier_compat:
            message = avertissement_vivier_batterie_vide(_plage_bat)
        elif not vivier_stock and candidat_impose is None:
            message = avertissement_batterie_rupture_stock()
        else:
            message = avertissement_batterie_plafond_banc()
        if avertissements is not None:
            avertissements.append(message)
        else:
            logger.warning(
                'PVOND: aucune banque batterie composable (%s) alors que le '
                'devis est demandé AVEC batterie — composition SANS '
                'batterie ; cet appelant ne porte aucun canal '
                'd\'avertissement.', message)

    bat5 = bat10 = None
    nb5, nb10 = 0, 0
    if candidats:
        candidats.sort(key=lambda c: (c[0], c[1]))
        _prix_retenu, n_retenu, calibre_retenu, produit_retenu = candidats[0]
        # ``produit_retenu`` — jamais ``bat5_stock``/``bat10_stock`` : un pin
        # (F1) résout depuis le vivier COMPATIBLE, qui peut désigner un
        # produit hors stock que le vivier stock-gaté ne connaît pas.
        if calibre_retenu == 5:
            bat5, nb5 = produit_retenu, n_retenu
        else:
            bat10, nb10 = produit_retenu, n_retenu

    # ── Structure : le type demandé (acier par défaut), une par panneau ──
    # PVMRQ — DEUX rôles distincts (``structure_acier`` / ``structure_alu``,
    # comme ``ROLES_AUTO_COMPOSITION``) : chacun a sa marque épinglée, appliquée
    # sur le sous-vivier déjà filtré par mot-clé (même patron que l'écran).
    voulu = ('alu' if _sans_accents(structure_type).startswith('alu')
             else 'acier')
    role_structure = 'structure_alu' if voulu == 'alu' else 'structure_acier'
    structure = next(iter(par_marque(
        [p for p in par_type.get('structure') or []
         if voulu in _sans_accents(getattr(p, 'nom', ''))],
        role_structure)), None)

    # ── Câbles Nexans 6 mm² AU MÈTRE (C4/PVCBL, fondateur 18-19/08) ─────────
    # VERROU DE CONDITIONNEMENT : le métrage est en MÈTRES, donc un produit
    # conditionné en ROULEAU/touret (« … (100m) ») ne doit JAMAIS entrer au
    # vivier — même chiffré, même seul candidat. L'incident fondateur du 19/08
    # (60 « unités » d'un rouleau de 100 m = 71 400 MAD de câble) vient
    # exactement de là. Sans candidat au mètre : aucune ligne, jamais un repli
    # silencieux sur un autre conditionnement.
    def choisir_cable(role):
        pool = par_marque(
            [p for p in par_type.get(role) or []
             if _est_au_metre(getattr(p, 'nom', ''))], role)
        # Préférence NEXANS : un fournisseur confirmé par le fondateur, pas une
        # préférence de gamme — elle joue DANS le vivier déjà filtré.
        return next(
            (p for p in pool
             if 'nexans' in _sans_accents(getattr(p, 'nom', ''))),
            next(iter(pool), None))

    cable_dc = choisir_cable('cable_dc')
    cable_terre = choisir_cable('cable_terre')

    # ── Paliers de 5 kWc — ne servent plus QUE au métrage du câble de terre ──
    blocs = max(1, _arrondi_js(kwp / 5))

    # ── L-FORFAIT (fondateur 24/08/2026) — les trois forfaits se cotent AU
    # PANNEAU, depuis le BARÈME PORTÉ PAR LE PRODUIT (cf. ``prix_forfait_ht``) :
    # plus de marches par bloc de 5 kWc, et plus aucune conversion TTC→HT —
    # c'est pourquoi ``taux_tva`` ne sert plus ici.
    #
    # Le barème est appliqué à ces TROIS rôles NOMMÉMENT, jamais dans
    # ``ajouter`` : une part « par panneau » posée par erreur sur un produit
    # vendu à la quantité (panneau, structure, socle…) se multiplierait alors
    # DEUX fois — une fois dans le prix, une fois dans la quantité.
    produit_accessoires = premier('accessoires')
    produit_tableau = premier('tableau')
    produit_installation = premier('installation')

    # ── Smart Meter + clé Wifi : UNIQUEMENT derrière un onduleur Huawei ──
    # (miroir du garde ``info_hw`` de l'ancien simulateur). L'écran teste les
    # DEUX onduleurs parce qu'il les propose tous les deux ; ici un seul est
    # vendu, donc c'est celui-là qui décide.
    # U2 — en forme DEUX OPTIONS les deux onduleurs sont vendus : le garde
    # Huawei teste alors les DEUX, exactement comme l'écran (autoFillLines),
    # sinon l'option Huawei partirait sans son Smart Meter.
    def _est_huawei(produit):
        return 'huawei' in _sans_accents(
            '%s %s' % (getattr(produit, 'marque', '') or '',
                       getattr(produit, 'nom', '') or ''))

    huawei = (_est_huawei(onduleur_reseau) or _est_huawei(onduleur_hybride)
              if deux_options else _est_huawei(onduleur))

    taguees = []

    def ajouter(role, produit, quantite, prix_ht=None):
        """Ajoute une ligne — sauf produit absent du catalogue ou quantité nulle.

        PVORD — chaque ligne est TAGUÉE de son rôle avant l'assemblage final,
        pour que ``ordre_lignes`` puisse la reclasser sans jamais reclassifier
        une désignation après coup.
        """
        if produit is None or quantite <= 0:
            return
        taguees.append((role, LigneKit(
            produit=produit,
            designation=produit.nom,
            quantite=int(quantite),
            prix_unitaire=(Decimal(produit.prix_vente) if prix_ht is None
                           else prix_ht))))

    # Ordre canonique du simulateur (onduleur, accessoires Huawei, panneaux,
    # batteries, structures, socles, forfaits, transport).
    # U2 — forme DEUX OPTIONS : les DEUX onduleurs entrent au devis (le PDF et
    # l'écran répartissent ensuite chaque ligne dans l'option qui la concerne).
    # Forme mono-option : un seul, celui qu'``avec_batterie`` a désigné.
    if deux_options:
        ajouter('onduleur_reseau', onduleur_reseau,
                quantite_onduleur(kw_reseau))
        ajouter('onduleur_hybride', onduleur_hybride,
                quantite_onduleur(kw_hybride))
    else:
        role_ond = ('onduleur_offgrid' if hors_reseau
                    else ('onduleur_hybride' if avec_batterie
                          else 'onduleur_reseau'))
        ajouter(role_ond, onduleur, quantite_onduleur(kw_onduleur))
    ajouter('smart_meter', premier('smart_meter'), 1 if huawei else 0)
    ajouter('wifi_dongle', premier('wifi_dongle'), 1 if huawei else 0)
    ajouter('panneau', panneau, nb)
    if veut_batterie:
        ajouter('batterie', bat5, nb5)
        ajouter('batterie', bat10, nb10)
    ajouter(role_structure, structure, nb)
    ajouter('socle', premier('socle'), nb * 2)
    # C4/PVCBL — métrage AU MÈTRE : le DC suit les paires de MPPT, la terre
    # suit les paliers de 5 kWc (25 m de base + 15 m par palier).
    ajouter('cable_dc', cable_dc, metre_cable_dc_par_paires(mppt_paires))
    ajouter('cable_terre', cable_terre, metre_cable_terre(blocs))
    # L-FORFAIT — une SEULE ligne par forfait, quantité 1, dont le prix
    # unitaire EST le total du barème (désignations inchangées). Barème absent
    # du produit ⇒ ``prix_forfait_ht`` rend ``None`` et ``ajouter`` retombe sur
    # le ``prix_vente`` catalogue, comme n'importe quelle autre ligne.
    ajouter('accessoires', produit_accessoires, 1,
            prix_forfait_ht(produit_accessoires, nb))
    ajouter('tableau', produit_tableau, 1,
            prix_forfait_ht(produit_tableau, nb))
    ajouter('installation', produit_installation, 1,
            prix_forfait_ht(produit_installation, nb))
    ajouter('transport', premier('transport'), 1)

    # ── PVORD — ordre PAR DÉFAUT des lignes ────────────────────────────────
    taguees = ordonner_par_role(taguees, ordre_lignes)

    lignes = CompositionLignes(ligne for _, ligne in taguees)
    lignes.roles = [role for role, _ in taguees]
    lignes.nb_panneaux = nb
    # Le wattage RÉELLEMENT retenu peut différer de celui demandé (substitution
    # « le plus proche » quand le catalogue n'a pas la puissance demandée) : on
    # rend le vrai, pour que personne n'affiche un kWc théorique divergent.
    _watt_reel = _parse_watt(getattr(panneau, 'nom', '')) if panneau else None
    lignes.panel_watt_reel = _watt_reel or watt
    lignes.kwc_reel = round(nb * float(lignes.panel_watt_reel) / 1000.0, 3)
    lignes.blocs = blocs
    lignes.marques_manquantes = marques_manquantes
    # DIM2 — LES CAPACITÉS RÉELLEMENT DISPONIBLES, en kWh nominaux, telles que
    # le vivier batterie les a retenues (compatibilité de tension avec
    # l'onduleur hybride comprise). Le balayage du stockage lit CETTE liste
    # pour construire ses paliers : sans elle il devrait redevine
    # « 5 et 10 kWh », c'est-à-dire recréer un second catalogue en dur qui
    # divergerait au premier module ajouté.
    lignes.capacites_batterie_vivier = sorted(
        {float(cap) for cap, _p in vivier_compat if cap and float(cap) > 0})
    return lignes


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
# LE REPLI DE SÉCURITÉ EST ABSOLU : quand les deux dimensionnements sont ÉGAUX
# (même nombre de panneaux, aucune cible de stockage distincte), la fusion
# n'entre JAMAIS en jeu — on rend la composition « deux options » HISTORIQUE,
# telle quelle, toutes lignes communes. Un devis d'aujourd'hui reste donc
# byte-identique tant que le moteur ne dit pas deux choses différentes.


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
                                 taux_tva=Decimal('20'), avertissements=None,
                                 marques=None, ordre_lignes=None,
                                 mppt_paires=1, phase=None):
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

    REPLI DE SÉCURITÉ ABSOLU — deux dimensionnements ÉGAUX (même nombre de
    panneaux ET aucune cible de stockage distincte) ⇒ la fusion n'est PAS
    jouée : on rend la composition « deux options » historique, toutes lignes
    communes, byte-identique à ce que ce dépôt produit aujourd'hui.

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
        taux_tva=taux_tva, avertissements=avertissements, marques=marques,
        ordre_lignes=ordre_lignes, mppt_paires=mppt_paires, phase=phase)

    # ── LE REPLI : les deux optimiseurs disent la même chose ────────────────
    if nb_avec == nb_sans and cible_stockage is None:
        return composition_residentielle(
            catalogue, kwc=kwc_s, nb_panneaux=nb_sans, deux_options=True,
            **commun)

    kit_sans = composition_residentielle(
        catalogue, kwc=kwc_s, nb_panneaux=nb_sans, avec_batterie=False,
        deux_options=False, **commun)
    kit_avec = composition_residentielle(
        catalogue, kwc=kwc_a, nb_panneaux=nb_avec, avec_batterie=True,
        deux_options=False, batterie_cible_kwh=cible_stockage, **commun)

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
    return lignes


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
    """
    return (classer_produit(ligne.designation or '')
            or classer_produit(getattr(ligne.produit, 'nom', '') or ''))


def _est_au_prix_catalogue(ligne):
    """La ligne est-elle restée au prix CATALOGUE, sans remise ?

    Un « non » vaut prix NÉGOCIÉ : une telle ligne n'est jamais supprimée en
    silence (le chemin appelant avertit à la place). Sans produit rattaché on
    ne peut RIEN prouver — donc on répond non, le doute profitant à la ligne.
    """
    produit = getattr(ligne, 'produit', None)
    if produit is None or not _has_price(produit):
        return False
    try:
        if Decimal(str(ligne.remise or 0)) != Decimal('0'):
            return False
        return (Decimal(str(ligne.prix_unitaire or 0))
                == Decimal(produit.prix_vente))
    except (TypeError, ValueError, ArithmeticError):
        return False


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
    phase = normaliser_phase(
        getattr(getattr(devis, 'lead', None), 'raccordement', None))

    catalogue = catalogue_de_la_societe(devis.company)
    taux_tva = (devis.taux_tva if devis.taux_tva is not None
                else Decimal('20'))
    # QJR221 — LA GAMME DU DEVIS, lue par LA fonction qui la lit partout
    # ailleurs dans la resynchro (``domain.gammes.gamme_nom``) : une seule
    # définition, jamais une seconde lecture d'``etude_params['gamme']``.
    from apps.ventes.domain.gammes import gamme_nom
    gamme_devis = gamme_nom(devis)

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
            # PVOND — ce chemin SAIT avertir : un vivier batterie vide remonte
            # à l'écran plutôt que de disparaître dans un kit silencieusement
            # amputé.
            avertissements=avertissements,
            variante=vue['variante'],
        ))
        par_classe = {}
        for spec in attendu:
            classe = classer_produit(spec.designation)
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
            spec = par_classe.get(classe)
            if spec is None:
                if classe not in deja_dit:
                    deja_dit.add(classe)
                    avertissements.append(AVERTISSEMENTS_KIT_ABSENT[classe])
                continue
            ordre += 1
            creer_ligne(
                devis, produit=spec.produit,
                designation=spec.designation,
                quantite=Decimal(str(spec.quantite)),
                prix_unitaire=Decimal(spec.prix_unitaire),
                remise=Decimal('0'), ordre=ordre,
                # QJR81 — l'option que cette ligne SERT. Vide (le cas de tout
                # devis non varianté) ⇒ ligne COMMUNE, comme avant.
                variante=getattr(spec, 'variante', '') or '')
            ajoutees += 1
    return ajoutees


def _refuser_couple_panneau_onduleur_impossible(devis, lignes, lignes_panneau,
                                                cible_panneaux, watt, gamme):
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

    # Le panneau CONCERNÉ : celui que la resynchro va ajuster (la ligne
    # dominante, même politique que l'écriture plus bas), ou celui qu'elle
    # créerait s'il n'y a encore aucune ligne panneau.
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

    onduleurs = [li.produit for li in lignes
                 if getattr(li, 'produit', None) is not None
                 and (_classe_ligne(li, _is_hybrid_inverter)
                      or _classe_ligne(li, _is_reseau_inverter))]
    for onduleur in onduleurs:
        verdict = verdict_panneau_onduleur(panneau, onduleur)
        if verdict.get('statut') != STATUT_INCOMPATIBLE:
            continue
        raisons = verdict.get('raisons') or []
        raise SyncLayoutError(
            '%d panneaux « %s » sont incompatibles avec « %s » : %s. '
            'Corrigez le nombre de panneaux ou changez d\'onduleur — le devis '
            'n\'a pas été modifié.'
            % (cible_panneaux, getattr(panneau, 'nom', '') or 'panneau',
               getattr(onduleur, 'nom', '') or 'onduleur',
               raisons[0] if raisons else
               'le couple sort des bornes de la fiche constructeur'),
            revision_possible=False)


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER : ils s'exécutent après toutes les définitions de
# ce module, et ils visent le module qui PORTE le corps — jamais la façade
# `services.py`, dont les ré-exports s'exécutent dans l'ordre des tâches et
# ne portent donc pas encore les noms des tâches suivantes.
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _arrondi_js,
    _batterie_compatible,
    _batterie_en_stock,
    _est_au_metre,
    _est_triphase,
    _filtrer_onduleurs_complets,
    _has_price,
    _is_hybrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    _marque_correspond,
    _max_modules_par_banc,
    _parse_kw,
    _parse_kwh,
    _parse_watt,
    _pick_product,
    _plage_batterie_de_l_onduleur,
    _prix_ttc_batterie,
    _sans_accents,
    catalogue_de_la_societe,
    classer_produit,
    metre_cable_dc_par_paires,
    metre_cable_terre,
    plafond_panneaux,
    prix_forfait_ht,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    _classe_ligne,
    _lignes_produit,
    cible_depuis_lignes,
    creer_ligne,
    lignes_de_variante,
)
from apps.ventes.domain.pipeline import (  # noqa: E402,F401
    COMPOSITION_AVEC,
    COMPOSITION_SANS,
    IntentionComposition,
    composer,
)
from apps.ventes.domain.resynchronisation import SyncLayoutError  # noqa: E402,F401
