"""Catalogue — classer un produit, en choisir un, le tarifer.

Les classifieurs de produit (panneau, batterie, structure, socle, câbles DC
et terre, onduleur hybride, onduleur réseau), le choix d'un produit dans le
vivier d'une société (`_pick_product`, `_pick_batterie`,
`_filtrer_onduleurs_complets`), le catalogue d'une société, les marques
préférées et l'ordre des lignes, les métrés de câble, le plafond de panneaux
et le barème des forfaits (`prix_forfait_ht`).

AUCUN MOT-CLÉ N'A ÉTÉ TOUCHÉ ICI. L'alignement des trois tables de
classification backend sur `solar_design` est une tâche à part (QJR78) : ce
module recopie les motifs tels quels, y compris là où ils divergent.

QJR71 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
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
from decimal import Decimal, ROUND_HALF_UP
import math
import re
import unicodedata

# QJR78 — LA table de classification produit du backend (voir plus bas).
# ``solar_design`` est du stdlib pur : cet import ne tire ni Django, ni
# modèle, ni I/O, et ne peut donc pas boucler.
from apps.ventes import solar_design as _sd


def marque_preferee(company, gamme_nom, role):
    """La marque préférée pour ce (société, gamme, rôle), ou ``None``.

    LA seule voie par laquelle un appelant apprend une préférence de marque —
    ``_pick_product`` la consulte, rien d'autre ne doit lire
    ``ParametresGammes.marques`` en direct. Ne lève JAMAIS : société sans
    réglage, rôle inconnu ou marque vide renvoient tous ``None`` (le caller
    retombe alors sur le comportement historique, sans préférence).

    RÉSOLUTION DU SLOT (F4/F7, fondateur 18/08/2026) — ``gamme_nom`` est le
    libellé LIBRE de la gamme du devis (celui que renvoie ``gamme_nom(devis)``
    plus haut dans ce fichier), résolu ici contre le réglage société pour
    retrouver le SLOT FIXE ('Essentielle'/'Premium') qui indexe réellement
    ``marques`` (ces clés ne bougent jamais, même si le libellé affiché est
    renommé) :

    * ``deux_gammes=False`` (offre à UNE seule gamme) — TOUJOURS le slot
      Essentielle, quel que soit ``gamme_nom`` (y compris un devis encore
      étiqueté « Premium » : une société à une gamme n'a qu'UNE carte de
      marques active — voir ``ParametresGammes``) ;
    * ``gamme_nom`` vide/``None``, ou égal (sans casse) à ``nom_essentielle``
      — slot Essentielle ;
    * ``gamme_nom`` égal (sans casse) à ``nom_premium`` — slot Premium ;
    * tout autre libellé (gamme inconnue de ce réglage — p. ex. un devis
      encore étiqueté « Premium » après un renommage fondateur Premium →
      Luxe) — slot Essentielle, JAMAIS ``None`` : un ``None`` laisserait
      ``_pick_product`` composer SANS aucune marque épinglée, alors que
      l'écran (DevisGenerator ``marquesActives``) retombe déjà sur la carte
      Essentielle dans ce cas — la composition automatique DÉSÉPINGLERAIT
      alors la marque en silence, l'exact inverse de l'ordre fondateur #5
      (jamais de substitution silencieuse).
    """
    from ..models import ParametresGammes, ROLES_AUTO_COMPOSITION

    role = str(role or '').strip()
    if role not in ROLES_AUTO_COMPOSITION:
        return None
    params = ParametresGammes.objects.filter(company=company).first()
    if params is None:
        return None
    nom = str(gamme_nom or '').strip()
    if not params.deux_gammes:
        # F7 — offre à UNE gamme : une seule carte de marques est
        # significative, quel que soit le libellé passé.
        slot = ParametresGammes.SLOT_ESSENTIELLE
    elif not nom:
        slot = ParametresGammes.SLOT_ESSENTIELLE
    elif nom.casefold() == (params.nom_essentielle or '').strip().casefold():
        slot = ParametresGammes.SLOT_ESSENTIELLE
    elif nom.casefold() == (params.nom_premium or '').strip().casefold():
        slot = ParametresGammes.SLOT_PREMIUM
    else:
        # F4 — gamme inconnue de ce réglage (renommage, libellé périmé…) :
        # repli explicite sur Essentielle, jamais un None qui désépinglerait
        # la composition en silence (voir la docstring ci-dessus).
        slot = ParametresGammes.SLOT_ESSENTIELLE
    marques = params.marques if isinstance(params.marques, dict) else {}
    carte = marques.get(slot)
    if not isinstance(carte, dict):
        return None
    marque = str(carte.get(role) or '').strip()
    return marque or None


#: U3 — libellé FR d'un rôle de composition. MIROIR EXACT des clés/libellés de
#: ``solar.js::PRODUCT_CATEGORIES`` : c'est ce que le commercial lit dans le
#: message « Marque épinglée introuvable au stock », des deux côtés.
LIBELLES_ROLES = {
    'onduleur_reseau': 'Onduleur Injection',
    'onduleur_hybride': 'Onduleur Hybride',
    'panneau': 'Panneaux',
    'batterie': 'Batterie',
    'structure_acier': 'Structures acier',
    'structure_alu': 'Structures aluminium',
    'socle': 'Socles',
    'cable_dc': 'Câble solaire DC',
    'cable_terre': 'Câble de terre AC',
    'smart_meter': 'Smart Meter',
    'wifi_dongle': 'Wifi Dongle',
    'accessoires': 'Accessoires',
    'tableau': 'Tableau De Protection AC/DC',
    'installation': 'Installation',
    'transport': 'Transport',
    'suivi': 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans',
}


def _libelle_role(role):
    """Libellé FR d'un rôle, ou le rôle brut s'il est inconnu (jamais None)."""
    return LIBELLES_ROLES.get(role, role)


def carte_marques_composition(company, gamme_nom_devis=None):
    """U3 — la carte ``{rôle: marque}`` à donner à ``composition_residentielle``.

    ``composition_residentielle`` est PURE (elle ne requête rien) : c'est ici
    que le réglage société est lu, et UNIQUEMENT via ``marque_preferee``, la
    seule voie de lecture de ``ParametresGammes.marques``. Société sans réglage
    ⇒ carte vide ⇒ composition byte-identique à l'historique.
    """
    from ..models import ROLES_AUTO_COMPOSITION

    carte = {}
    for role in ROLES_AUTO_COMPOSITION:
        marque = marque_preferee(company, gamme_nom_devis, role)
        if marque:
            carte[role] = marque
    return carte


def ordre_lignes_societe(company):
    """U3/PVORD — la séquence de rôles préférée de la société, ou ``None``.

    Même contrat que ``carte_marques_composition`` : lecture unique du réglage,
    absence de réglage ⇒ ``None`` ⇒ ordre canonique du simulateur.
    """
    from ..models import ParametresGammes

    params = ParametresGammes.objects.filter(company=company).first()
    if params is None:
        return None
    ordre = params.ordre_lignes
    return ordre if isinstance(ordre, list) and ordre else None


# QJR78 — LA CLASSIFICATION PRODUIT VIENT DE ``solar_design``, ET DE LÀ SEULE.
# Ce bloc annonçait « Kept ALIGNED with quote_engine/builder.py » ; il ne
# l'était plus. Le 19/08/2026, la détection panneau a été élargie DANS LE
# BUILDER seulement (module + qualifiant PV, marque + wattage, exclusions), et
# cette copie-ci est restée à « panneau / panneaux ». Un devis dont la ligne
# panneau s'appelle « Module PV 550 W » était donc rejeté à l'enregistrement
# comme n'ayant aucun panneau, pendant que le PDF la comptait — le patron exact
# de l'incident de PRODUCTION DEV-202608-0024 que ce fichier cite lui-même.
#
# Les alias gardent les noms locaux : aucun appelant de ce module ne change.
# ``_WATT_RE`` reste défini ici (``_parse_watt`` s'en sert), avec la MÊME
# expression que celle de ``solar_design``.
_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)

_is_panel = _sd.is_panel
_is_battery = _sd.is_battery


# ── PVCBL — les CÂBLES suivent la taille du calepinage (F8, fondateur
# 18/08/2026) ────────────────────────────────────────────────────────────
#
# Métrés : câble de terre AC 6 mm² à 25 m de base + 15 m par palier de 5 kWc
# — miroir exact de ``solar.js`` (CABLE_TERRE_M_BASE/CABLE_TERRE_M_PAR_PALIER),
# 40 m pour 5 kWc, 55 m pour 10 kWc. Pour le câble solaire DC, la COMPOSITION
# (``solar.js``, C4 du 19/08/2026) chiffre désormais 60 m × nb de PAIRES MPPT
# descendantes ; cette resynchro de calepinage, qui n'a pas de compte MPPT
# frais sous la main, garde l'approximation historique 60 m par palier de
# 5 kWc (≈ une paire par tranche de 5 kWc) — et ne touche que des lignes
# vendues AU MÈTRE (garde ``_est_au_metre`` ci-dessous).
CABLE_DC_M_PAR_PALIER = 60
CABLE_TERRE_M_BASE = 25
CABLE_TERRE_M_PAR_PALIER = 15


def metre_cable_dc(paliers):
    """Longueur (m) de câble solaire DC pour ``paliers`` blocs de 5 kWc."""
    n = max(1, int(round(float(paliers or 0))))
    return n * CABLE_DC_M_PAR_PALIER


def metre_cable_dc_par_paires(nb_paires=1):
    """C4/PVCBL (U3) — longueur (m) de câble solaire DC pour ``nb_paires``.

    Miroir EXACT de ``solar.js::metreCableDcParPaires`` : 30 m rouge + 30 m
    noir descendent du toit par PAIRE de MPPT réellement utilisée, soit 60 m.
    La règle « 60 m par palier de 5 kWc » (``metre_cable_dc`` ci-dessus) reste
    l'approximation des chemins qui n'ont pas de compte MPPT frais sous la main
    (resynchro de calepinage) ; la COMPOSITION, elle, chiffre par paire.

    Le nombre de paires est un paramètre EXPLICITE : il vit dans le moteur
    électrique (``solar_design.string_design``) et exige des données que la
    composition simple (kWc + nb de panneaux) n'a pas à ce stade. Sans lui,
    repli fondateur EXPLICITEMENT AUTORISÉ : 1 paire — jamais un calcul deviné.
    """
    n = max(1, int(round(float(nb_paires or 0))) or 1)
    return n * CABLE_DC_M_PAR_PALIER


def metre_cable_terre(paliers):
    """Longueur (m) de câble de terre AC pour ``paliers`` blocs de 5 kWc."""
    n = max(1, int(round(float(paliers or 0))))
    return CABLE_TERRE_M_BASE + n * CABLE_TERRE_M_PAR_PALIER


# Classification — même mot-clé que ``solar.js::classifyProduct`` : un câble
# de TERRE se reconnaît à « terre »/« mise à la terre », tout autre « câble »
# est un câble solaire DC (accents retirés — ``_sans_accents`` plus bas dans
# ce fichier, chargé par NOM au moment de l'appel, jamais au chargement du
# module).
def _is_cable_terre(name: str) -> bool:
    n = _sans_accents(name)
    return "cable" in n and ("terre" in n or "mise a la terre" in n)


def _is_cable_dc(name: str) -> bool:
    n = _sans_accents(name)
    return "cable" in n and not _is_cable_terre(name)


def _est_au_metre(name: str) -> bool:
    """Vrai pour un câble vendu AU MÈTRE (désignation « … (au mètre) »).

    Miroir du filtre de composition de ``solar.js`` (C4, 19/08/2026) : une
    cible de resynchro est un MÉTRAGE — la poser sur un SKU ROULEAU serait
    l'incident fondateur du 19/08 à l'envers (60 « unités » sur un rouleau
    de 100 m à 1 190 MAD = 71 400 MAD de câble).
    """
    return "au metre" in _sans_accents(name)


# ── PVSTR — les STRUCTURES et les SOCLES suivent le compte de panneaux
# (fondateur, 18/08/2026) ───────────────────────────────────────────────────
#
# Ratios de la composition résidentielle, source unique déjà en place :
# ``composition_residentielle`` pose ``ajouter(structure, nb)`` et
# ``ajouter(premier('socle'), nb * 2)`` — UNE structure par panneau, DEUX
# socles par panneau. Ces deux prédicats passent par le classifieur PARTAGÉ
# ``classer_produit`` (celui de la composition ET du moteur PDF) plutôt que par
# un mot-clé de plus : inventer une seconde classification ici ferait diverger
# « ce qu'on resynchronise » de « ce que le PDF montre ».
STRUCTURES_PAR_PANNEAU = 1
SOCLES_PAR_PANNEAU = 2


def _is_structure(name: str) -> bool:
    return classer_produit(name) == 'structure'


def _is_socle(name: str) -> bool:
    return classer_produit(name) == 'socle'


# ── PVG4 — Batterie Dyness HAUTE TENSION (16 kWh, décision fondateur
# 2026-08-18, SKU BAT-DYN-HV-16) : ne doit JAMAIS être choisie par
# l'auto-composition résidentielle BASSE TENSION (48 V). ``_is_battery``
# reconnaît "batterie" sans distinguer la tension — utilisé aussi bien pour
# l'AUTO-SÉLECTION (``_pick_product`` ci-dessous) que pour CLASSIFIER une
# ligne déjà présente dans un devis. Ce prédicat-ci sert UNIQUEMENT aux
# points d'auto-sélection : une batterie HV ajoutée À LA MAIN par un
# commercial (hors résidentiel) doit continuer d'être reconnue "batterie"
# par ``_is_battery`` pour le rendu PDF — donc on ne touche pas ce dernier,
# on lui substitue ce prédicat plus strict aux seuls call-sites qui PICK
# automatiquement une batterie dans le catalogue.
def _is_battery_basse_tension(name: str) -> bool:
    n = (name or "").lower()
    return "batterie" in n and "haute tension" not in n


# ── PVOND — LE GARDE BATTERIE EST DÉSORMAIS PILOTÉ PAR LA DONNÉE ────────────
#
# Le prédicat par mot-clé ci-dessus répondait à la seule question « le nom
# dit-il haute tension ? ». C'est une règle qui ne connaît qu'UN cas : elle
# laisserait passer une batterie 96 V mal nommée sur un onduleur 48 V, et elle
# refuserait une batterie HV sur un onduleur HV — qui est pourtant son
# appairage LÉGITIME. La vraie règle électrique est celle-ci, et elle ne
# demande que des chiffres déjà présents au catalogue :
#
#   une batterie s'accroche à un onduleur si sa TENSION NOMINALE tombe dans la
#   PLAGE DE TENSION BATTERIE que l'onduleur déclare.
#
# Les deux variables vivent côté Stock et se lisent par ses sélecteurs (jamais
# un import de ses models) : ``plage_batterie_onduleur`` (contrat PVOND) et
# ``specs_for_produit(batterie)['v_nominal']`` (FicheTechnique PV5).
#
# REPLI EXPLICITE, jamais silencieux : dès qu'une des deux données manque —
# onduleur sans plage déclarée, batterie sans fiche, ou aucun onduleur dans la
# composition — on retombe MOT POUR MOT sur ``_is_battery_basse_tension``.
# C'est ce qui garantit qu'aucun catalogue existant ne régresse le jour où ce
# code arrive : sans donnée, le comportement est byte-identique à hier.

def _plage_batterie_de_l_onduleur(onduleur):
    """``(v_min, v_max)`` déclarée par l'onduleur, ``(0, 0)`` s'il n'en prend
    aucune, ``None`` si la donnée manque. Lecture cross-app par sélecteur."""
    if onduleur is None:
        return None
    from apps.stock.selectors import plage_batterie_onduleur
    return plage_batterie_onduleur(onduleur)


def _tension_nominale_batterie(batterie):
    """Tension nominale (V) d'une batterie d'après sa fiche, ou ``None``."""
    if batterie is None:
        return None
    from apps.stock.selectors import specs_for_produit
    valeur = (specs_for_produit(batterie) or {}).get('v_nominal')
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def _max_modules_par_banc(batterie):
    """BATHOMO (fondateur 26/08/2026) — le plafond fondateur du nombre de
    modules IDENTIQUES admis dans un même banc pour CETTE batterie, ou
    ``None`` = ILLIMITÉ (aucune fiche, ou champ vide — comportement
    byte-identique à l'historique, où rien n'était borné)."""
    if batterie is None:
        return None
    from apps.stock.selectors import specs_for_produit
    valeur = (specs_for_produit(batterie) or {}).get('max_modules_par_banc')
    try:
        return int(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def _prix_ttc_batterie(produit, quantite, taux_repli):
    """Prix TTC total pour ``quantite`` modules de ``produit`` — le taux DU
    PRODUIT s'il en déclare un, sinon ``taux_repli`` (celui du devis). MÊME
    convention que ``dimensionnement._lire_composition`` (TVA par ligne),
    pour que le classement économique compare des bases identiques."""
    taux_produit = getattr(produit, 'tva', None)
    try:
        taux_pct = (float(taux_produit) if taux_produit is not None
                    else float(taux_repli))
    except (TypeError, ValueError):
        taux_pct = float(taux_repli)
    return float(quantite) * float(produit.prix_vente) * (1.0 + taux_pct / 100.0)


def _batterie_compatible(batterie, plage):
    """La batterie entre-t-elle dans la plage batterie de l'onduleur ?

    ``plage`` vient de ``_plage_batterie_de_l_onduleur`` :

    * ``(0, 0)`` — l'onduleur DÉCLARE ne prendre aucune batterie (réseau) :
      aucune ne convient, et ce n'est pas un repli, c'est un fait ;
    * ``None`` — L'ONDULEUR ne déclare AUCUNE plage : c'est le SEUL cas de
      repli mot-clé (comportement PVG4 d'hier, catalogue non renseigné) ;
    * sinon — verdict par la tension nominale, bornes incluses.

    RÈGLE CORRIGÉE (fondateur 2026-08-18) : quand l'onduleur DÉCLARE une plage,
    une candidate SANS donnée de tension est EXCLUE — jamais rattrapée par le
    mot-clé. L'ancien repli faisait exactement l'inverse de ce qu'il promettait
    sur le catalogue réel : sous un Deye 15 kW hybride (plage 160-700 V), il
    ÉCARTAIT les Dyness 5/10 kWh (51,2 V, correctement documentées) et
    ACCEPTAIT « Batterie Lithium 5 kWh » et « Batterie Gel 2.2 kWh » — deux
    références sans aucune fiche technique, l'une en 48 V, l'autre en plomb-gel
    12 V. Le devis partait avec 3 batteries 48 V sous un onduleur haute tension :
    une composition électriquement invalide, produite par un garde-fou. Dès que
    la plage existe, seule une tension MESURÉE peut prouver la compatibilité.
    """
    nom = getattr(batterie, 'nom', '') or ''
    if plage is None:
        return _is_battery_basse_tension(nom)
    v_min, v_max = plage
    if v_max <= 0:
        return False
    tension = _tension_nominale_batterie(batterie)
    if tension is None or tension <= 0:
        # Plage EXIGÉE + tension inconnue (ou 0 = donnée invalide) ⇒ exclue.
        return False
    return v_min <= tension <= v_max


def _pick_batterie(company, *, onduleur=None, gamme=None):
    """La batterie du catalogue COMPATIBLE avec l'onduleur de la composition.

    Même sélection que ``_pick_product`` (produits tarifés de la société et
    globaux, la moins chère l'emporte, PVMRQ : marque préférée en priorité)
    mais avec le garde data-driven ci-dessus au lieu du prédicat par mot-clé.
    ``onduleur=None`` (composition qui n'en a pas encore) ⇒ repli mot-clé, donc
    comportement historique intact. ``gamme`` (PVMRQ) est le libellé de gamme
    du devis appelant, transmis tel quel à ``_pick_product``.
    """
    plage = _plage_batterie_de_l_onduleur(onduleur)
    return _pick_product(
        company, _is_battery, role='batterie', gamme=gamme,
        produit_predicate=lambda p: _batterie_compatible(p, plage))


# ── PVOND — VERROU DE COMPLÉTUDE, la moitié BACKEND ─────────────────────────
#
# L'écran (``solar.js::pickInverter``) écarte déjà de l'auto-composition tout
# onduleur auquel il manque une variable du CONTRAT (puissance AC, phases,
# MPPT, tensions, courant, rendement, plage batterie, garantie) et le montre
# grisé avec son motif. Le backend, lui, ne l'appliquait NULLE PART :
# ``onduleur_specs_manquantes`` n'avait aucun appelant hors tests/sérialiseur.
# Deux moitiés de la MÊME auto-composition pouvaient donc retenir deux
# onduleurs différents pour la même demande — deux prix pour un seul devis,
# selon le bouton utilisé.
#
# La couture est ici, et elle passe par le canal cross-app LICITE (le
# ``selectors.py`` de stock, jamais ses models). Sur le catalogue d'aujourd'hui
# (table des incomplets VIDE depuis le dégrisage) ce filtre ne change RIEN :
# c'est la COUTURE qui compte, pas son effet du jour.
def _onduleur_complet(produit) -> bool:
    """L'onduleur porte-t-il TOUTES les variables du contrat PVOND ?

    ``True`` pour tout produit qui n'est PAS un onduleur (le contrat ne le
    concerne pas — ``stock.selectors`` rend alors une liste vide). Défensif :
    un sélecteur en panne ne doit jamais vider un catalogue."""
    try:
        from apps.stock.selectors import onduleur_specs_manquantes
        return not onduleur_specs_manquantes(produit)
    except Exception:  # noqa: BLE001 — jamais bloquer une composition
        return True


def _filtrer_onduleurs_complets(candidats):
    """Applique le verrou de complétude à un vivier — SANS jamais le vider.

    Le verrou trie entre onduleurs d'un MÊME catalogue : sur le catalogue du
    fondateur (16 réf. OND-* au contrat complet depuis le dégrisage) il ne
    change rien, et il écarte le jour où une référence part incomplète.

    LA SEULE différence assumée avec ``solar.js::pickInverter`` : si AUCUN
    candidat n'est complet, le vivier d'origine est rendu tel quel. Le backend
    est MULTI-TENANT — le catalogue d'une société qui n'a encore saisi aucune
    fiche technique ne doit pas devenir « non chiffrable » d'un coup, ce qui
    supprimerait purement et simplement la ligne d'onduleur de tous ses devis.
    Un verrou qui arbitre entre candidats reste un verrou ; un verrou qui vide
    la table est une panne."""
    complets = [c for c in candidats if _onduleur_complet(c)]
    return complets or candidats


# QJR78 — même table unique que ci-dessus (``solar_design``).
_is_hybrid_inverter = _sd.is_hybrid_inverter
_is_reseau_inverter = _sd.is_reseau_inverter
# QJR-OFFGRID — la TROISIÈME famille d'onduleur (autonome / site isolé).
_is_offgrid_inverter = _sd.is_offgrid_inverter


def _has_price(produit) -> bool:
    """A product is quotable only when it carries a real sell price.

    Mirrors the generator/auto-fill guard: a price-less catalogue item
    (e.g. the curve-only OSP pumps) is NEVER auto-quoted (CLAUDE.md).
    """
    return bool(produit.prix_vente and Decimal(produit.prix_vente) > 0)


def _batterie_en_stock(produit) -> bool:
    """BATHOMO (fondateur 26/08/2026) — ce module de batterie a-t-il du
    STOCK RÉELLEMENT SUIVI (``Produit.quantite_stock`` > 0) ?

    L'incident : le fondateur a mis le Dyness 10 kWh à 0 en stock (un
    MOUVEMENT de stock — jamais un archivage), mais RIEN ne consultait le
    stock au chiffrage : le module continuait d'apparaître dans les banques
    composées. Cette garde ne s'applique QU'AU RÔLE BATTERIE (jamais un
    filtre stock global — panneaux/onduleurs peuvent légitimement rester en
    stock NON SUIVI, cf. le reste du catalogue) : un module à 0 en stock
    sort du vivier exactement comme un module hors plage de tension, et
    quand le fondateur réapprovisionne, il redevient composable tout seul
    (aucun redéploiement, aucune intervention catalogue) — cf.
    ``apps.stock.management.commands.seed_catalogue`` (BATHOMO, même
    session : plus d'archivage forcé sur ce SKU).
    """
    if produit is None:
        return False
    if getattr(produit, 'is_archived', False):
        return False
    try:
        return int(getattr(produit, 'quantite_stock', 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def _marque_correspond(produit, marque):
    """PVMRQ — ``produit`` porte-t-il la marque préférée, sans tenir compte de
    la casse ?

    ``Produit.marque`` (champ structuré) prioritaire, exact une fois normalisé
    (espaces/casse) ; à défaut (marque non renseignée sur la fiche), son
    ``nom`` — une désignation complète comme « Panneau Jinko 550W Mono » — DOIT
    seulement CONTENIR la marque, jamais l'égaler."""
    cible = str(marque or '').strip().casefold()
    if not cible:
        return False
    marque_produit = str(getattr(produit, 'marque', '') or '').strip()
    if marque_produit:
        return marque_produit.casefold() == cible
    return cible in str(getattr(produit, 'nom', '') or '').casefold()


def _pick_product(company, predicate, *, watt=None, produit_predicate=None,
                  role=None, gamme=None):
    """Smallest-suitable quotable catalogue product matching ``predicate``.

    Scans the company's (and global) products, keeps only priced ones, and —
    for panels with a target wattage — prefers an exact watt match. Returns
    None when nothing priced matches (caller then skips that line).

    ``produit_predicate`` (PVOND) filtre sur le PRODUIT entier plutôt que sur
    son seul nom : le garde batterie data-driven a besoin de la fiche technique
    (tension nominale), pas d'un mot-clé. Il s'AJOUTE à ``predicate`` ; absent,
    la sélection est byte-identique à l'historique.

    ``role``/``gamme`` (PVMRQ, fondateur 18/08/2026) — quand ``role`` est
    fourni et qu'une marque préférée est réglée pour ce (société, gamme, rôle)
    via ``ParametresGammes``/``marque_preferee``, cette marque GAGNE
    TOUJOURS : les candidats sont restreints à elle AVANT toute logique de
    wattage/prix (inchangée, byte-identique à l'historique en aval). Si la
    marque est réglée mais qu'AUCUN candidat ne la porte, la fonction renvoie
    ``None`` sans jamais retomber en silence sur une autre marque — c'est
    l'appelant qui doit alors signaler le trou (comme il le fait déjà pour
    « aucun produit disponible »). ``role=None`` (défaut) laisse la sélection
    strictement inchangée — aucun appelant non migré ne régresse.
    """
    from apps.stock.models import Produit
    from django.db.models import Q

    # ``select_related`` inconditionnel : le verrou de complétude ci-dessous lit
    # la fiche technique de CHAQUE candidat onduleur — sans lui, une requête par
    # produit. Pour un panneau la fiche est simplement ignorée.
    qs = (Produit.objects
          .filter(Q(company=company) | Q(company__isnull=True),
                  is_archived=False)
          .select_related('fiche_technique'))
    candidates = [p for p in qs
                  if predicate(p.nom) and _has_price(p)
                  and (produit_predicate is None or produit_predicate(p))]
    # PVOND — VERROU DE COMPLÉTUDE (miroir de solar.js::pickInverter) : sur un
    # vivier d'onduleurs, ceux au contrat incomplet passent derrière. Sans
    # effet sur un panneau ou une batterie (le contrat ne les concerne pas).
    candidates = _filtrer_onduleurs_complets(candidates)
    if not candidates:
        return None
    if role:
        marque = marque_preferee(company, gamme, role)
        if marque:
            candidats_marque = [p for p in candidates
                                if _marque_correspond(p, marque)]
            if not candidats_marque:
                return None  # marque réglée, aucun match ⇒ JAMAIS un repli
            candidates = candidats_marque
    if watt:
        exact = [p for p in candidates
                 if _parse_watt(p.nom) == int(watt)]
        if exact:
            candidates = exact
    # Cheapest priced match keeps the quote sane and deterministic.
    return min(candidates, key=lambda p: Decimal(p.prix_vente))


def _parse_watt(name):
    m = _WATT_RE.search(name or "")
    return int(m.group(1)) if m else None


# ── L-FORFAIT (ordre fondateur 24/08/2026) — LES TROIS FORFAITS SE COTENT AU
# PANNEAU, PLUS PAR BLOCS DE 5 kWc ───────────────────────────────────────────
# Verbatim : « change the rule of calculating instalation cost to be per pannel
# plus 2000dh HT always there plus 250 dh HT per pannel, so 8 pannels is still
# 4000dh HT and 16 pannels is 6000dh HT. but now what is inbetween changes,
# also make the same for the tableau AC DC and the accesoirs, also now reduce
# the price of accesoirs by half and add 30% to tableau DC AC total price ».
#
# L'ANCIENNE RÈGLE (port littéral de ``auto_fill_from_power``) montait par
# MARCHES : 1 000 / 1 500 TTC par bloc de 5 kWc, et (blocs + 1) × 2 400 TTC
# pour l'installation, avec ``blocs = max(1, round(kWc / 5))``. Deux toitures
# différentes (8 et 12 panneaux) tombaient donc au MÊME prix tant qu'elles
# restaient dans le même bloc, puis sautaient d'une marche entière. La règle
# est désormais une DROITE en NOMBRE DE PANNEAUX : les deux ancrages du
# fondateur (8 → 4 000, 16 → 6 000 pour l'installation) sont conservés au
# centime près, et seul l'entre-deux change — il se lisse.
#
# Ces montants sont nativement HT (le fondateur les a dictés en HT) : ils ne
# passent PLUS par la conversion TTC→HT et ne dépendent donc plus du taux de
# TVA du devis. Le câble de terre, lui, reste indexé sur les paliers de 5 kWc
# (``blocs``) — cette règle-là n'est pas touchée.
#
# ⚠ LE BARÈME NE VIT PAS ICI (ordre fondateur, même jour : « dans le stock
# ceci devra être bien fait, c'est-à-dire chaque case de installation, tableau
# AC/DC et accessoires devra avoir une partie fixe et une par panneau que je
# pourrai changer par la suite »). Les deux parts sont des CHAMPS CATALOGUE —
# ``stock.Produit.prix_fixe_ht`` et ``prix_par_panneau_ht`` (migration
# ``stock/0128``, qui pose aussi les valeurs du fondateur) — que le fondateur
# modifie depuis le stock sans toucher au code. Ce module ne porte QUE la
# formule générique ci-dessous : aucun 2 000 / 250 / 52,08 / 203,125 en dur.
#
# Le montant de ces lignes vient donc du BARÈME, jamais du ``prix_vente`` du
# produit qui les porte — et un produit SANS barème (les deux champs vides,
# c'est-à-dire tout le reste du catalogue) garde exactement son ``prix_vente``.


def _au_centime(montant):
    """Arrondi MONÉTAIRE des forfaits : 2 décimales, moitié vers le haut.

    Même arrondi que le reste de la composition (l'ancienne conversion
    TTC→HT quantizait déjà ainsi) : un prix unitaire de devis n'a jamais plus
    de deux décimales.
    """
    return Decimal(montant).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def prix_forfait_ht(produit, nb_panneaux):
    """L-FORFAIT — le prix HT d'une ligne TARIFÉE AU PANNEAU, sinon ``None``.

    ``prix_fixe_ht + prix_par_panneau_ht × nb_panneaux``, arrondi au centime.
    Rend ``None`` — et l'appelant retombe alors sur le ``prix_vente``
    catalogue, comportement historique byte-identique — dès que le produit ne
    porte AUCUN barème (les deux champs vides), ce qui est le cas de tout le
    catalogue sauf les forfaits.

    UNE SEULE VÉRITÉ : tout chemin qui (re)compose le kit résidentiel —
    création depuis un calepinage, ``sync-layout``/PVHEAL, dry-run — passe par
    ``composition_residentielle``, donc par cette fonction. Changer le nombre
    de panneaux requote mécaniquement les forfaits ; changer le barème au
    stock les requote aussi, sans qu'aucun appelant n'ait sa propre copie de
    la règle.
    """
    if not porte_bareme_par_panneau(produit):
        return None
    fixe = getattr(produit, 'prix_fixe_ht', None)
    par_panneau = getattr(produit, 'prix_par_panneau_ht', None)
    n = int(nb_panneaux or 0)
    total = Decimal(str(fixe or 0))
    if n > 0:
        total += Decimal(str(par_panneau or 0)) * Decimal(n)
    return _au_centime(total)


def porte_bareme_par_panneau(produit):
    """QJR83 — ce produit est-il TARIFÉ AU BARÈME plutôt qu'au ``prix_vente`` ?

    Vrai dès qu'au moins une des deux parts du barème est renseignée
    (``prix_fixe_ht`` / ``prix_par_panneau_ht``) — c'est-à-dire pour les seuls
    forfaits (pose/installation, tableau AC/DC, accessoires, transport quand le
    fondateur le barème), et pour AUCUN autre produit du catalogue.

    Le prédicat est SORTI de ``prix_forfait_ht`` pour qu'un appelant puisse
    poser la question SANS calculer un prix : la re-tarification des lignes
    (``domain/lignes.retarifer_forfaits_par_panneau``) doit d'abord savoir
    QUELLES lignes la concernent, et ``None`` ne distinguait pas « pas de
    barème » de « barème à zéro panneau ».
    """
    if produit is None:
        return False
    return not (getattr(produit, 'prix_fixe_ht', None) is None
                and getattr(produit, 'prix_par_panneau_ht', None) is None)


_KW_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b", re.IGNORECASE)
_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kwh\b", re.IGNORECASE)
_TRI_RE = re.compile(r"tri\s*phas", re.IGNORECASE)


def _sans_accents(texte):
    """Minuscules sans accents — miroir exact du ``_norm`` de solar.js."""
    decompose = unicodedata.normalize('NFD', str(texte or '').lower())
    return ''.join(c for c in decompose
                   if unicodedata.category(c) != 'Mn')


def _arrondi_js(valeur):
    """``Math.round`` de JavaScript : la moitié part VERS LE HAUT.

    ``round()`` de Python arrondit au pair le plus proche (``round(2.5) == 2``)
    — l'utiliser ici ferait diverger d'un panneau, d'un bloc de prix ou d'un
    module de batterie entre l'écran et le serveur.
    """
    return int(math.floor(float(valeur) + 0.5))


# ── U1 (fondateur 20/08/2026) — LE COMPTE DE PANNEAUX EST UN PLAFOND ────────
# « 7 panneaux pour 5 kW : ça a TOUJOURS été 8 panneaux par 5 kW ». L'arrondi
# au plus proche sortait 7 panneaux pour 5 kWc en 710 Wc (round(7,042) = 7) :
# l'installation livrée était SOUS la puissance vendue. La règle est le
# PLAFOND — miroir EXACT de ``solar.js::plafondPanneaux``.
#
# ÉPSILON — un compte de panneaux fait ALLER-RETOUR par le kWc
# (``kwc = nb * 710 / 1000`` puis re-dérivation) et 8 × 710 / 1000 × 1000 / 710
# vaut 8.000000000000002 en flottant : sans garde, le plafond ajouterait un
# 9ᵉ panneau fantôme à chaque aller-retour. La tolérance ramène un « à peine
# au-dessus d'un entier » sur cet entier ; elle ne peut PAS masquer un vrai
# besoin partiel (7,042 reste bien au-dessus de 7).
PANNEAUX_CEIL_EPS = 1e-9


def plafond_panneaux(valeur):
    """``Math.ceil`` tolérant au flottant — miroir de ``plafondPanneaux``."""
    v = float(valeur or 0)
    if v <= 0:
        return 0
    return int(math.ceil(v - PANNEAUX_CEIL_EPS))


def _parse_kw(nom):
    """Puissance kW/kVA lue dans un nom — les « kWh » sont retirés d'abord
    (sans quoi « Batterie 5 kWh » passerait pour un onduleur de 5 kW)."""
    m = _KW_RE.search(_KWH_RE.sub(' ', nom or ''))
    return float(m.group(1).replace(',', '.')) if m else None


def _parse_kwh(nom):
    m = _KWH_RE.search(nom or '')
    return float(m.group(1).replace(',', '.')) if m else None


def _est_triphase(nom):
    return bool(_TRI_RE.search(nom or ''))


def classer_produit(nom):
    """Catégorie catalogue d'un produit — port de ``classifyProduct``.

    L'ORDRE des tests est signifiant et strictement celui de l'écran :
    « onduleur hybride » AVANT « onduleur réseau/injection », et un onduleur qui
    ne porte ni l'un ni l'autre (un micro-onduleur, par exemple) reste NON
    classé — donc jamais composé automatiquement, seulement choisi à la main.
    """
    n = _sans_accents(nom)
    if not n:
        return None
    if 'onduleur' in n and 'hybride' in n:
        return 'onduleur_hybride'
    # QJR-OFFGRID — AVANT le réseau, et ce n'est pas un détail : « hors réseau »
    # CONTIENT « réseau ». Sans ce rang, un onduleur autonome nommé en français
    # était classé RÉSEAU (donc composable sur un client raccordé) et un
    # « Off-Grid » anglais n'était classé nulle part (donc jamais composable).
    # Le prédicat est celui de la table unique ``solar_design`` — il tolère les
    # deux orthographes, accentuée et non.
    if _sd.is_offgrid_inverter(nom or ''):
        return 'onduleur_offgrid'
    if 'onduleur' in n and ('reseau' in n or 'injection' in n):
        return 'onduleur_reseau'
    if 'panneau' in n:
        return 'panneau'
    if 'batterie' in n:
        return 'batterie'
    if 'structure' in n:
        return 'structure'
    if 'socle' in n:
        return 'socle'
    # U3 — Câbles (règle fondateur 18/08) : MIROIR EXACT de
    # ``solar.js::classifyProduct``, mêmes mots-clés et MÊME RANG (après le
    # socle, avant le Smart Meter). Le classifieur Python les ignorait, si
    # bien que la composition serveur ne pouvait PAS composer de câble là où
    # l'écran en composait deux — l'écart le plus visible entre les deux
    # « sortes de devis ».
    if _is_cable_terre(nom or ''):
        return 'cable_terre'
    if _is_cable_dc(nom or ''):
        return 'cable_dc'
    if 'smart meter' in n:
        return 'smart_meter'
    if 'wifi' in n or 'dongle' in n:
        return 'wifi_dongle'
    if 'accessoire' in n:
        return 'accessoires'
    if 'tableau' in n:
        return 'tableau'
    if 'suivi' in n:
        return 'suivi'
    if 'installation' in n:
        return 'installation'
    if 'transport' in n:
        return 'transport'
    return None


def catalogue_de_la_societe(company):
    """Produits actifs visibles par ``company`` — les siens ET les globaux.

    Même périmètre que ``_pick_product`` (multi-tenant : le catalogue d'une
    autre société ne fuite jamais), trié par id pour que deux compositions aux
    mêmes entrées donnent exactement le même kit.
    """
    from django.db.models import Q

    from apps.stock.models import Produit

    # PVOND — la fiche technique est préchargée : le garde batterie data-driven
    # y lit la tension nominale, et la composition ne doit pas payer une
    # requête par batterie candidate.
    return list(Produit.objects.filter(
        Q(company=company) | Q(company__isnull=True),
        is_archived=False).select_related('fiche_technique').order_by('id'))
