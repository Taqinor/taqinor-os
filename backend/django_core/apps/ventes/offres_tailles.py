"""TAILLES (ordre fondateur, 26/08/2026) — Éco / Recommandé / Max.

LES TROIS TAILLES D'INSTALLATION EXPLORABLES, dérivées du MÊME moteur que le
reste de la page client, servies dans leurs deux variantes ``sans`` / ``avec``
batterie pour qu'UNE bascule au-dessus des cartes les recalcule toutes les
trois sans le moindre aller-retour réseau.

CE QUE CE MODULE N'EST PAS. Ce n'est pas un devis, ni une variante de devis
(:class:`~apps.ventes.models.Devis` ``variante_de`` / ``variante_tier``, qui
crée un vrai brouillon), ni un second optimiseur. C'est une couche
d'EXPLORATION : elle ne crée aucun devis, ne touche aucune ligne, aucun total,
aucun statut (règle #4). Le devis officiel reste la seule source contractuelle.

LES TROIS DÉFINITIONS, ET POURQUOI ELLES NE PEUVENT PAS DÉRIVER.

* **Recommandé** = LE DEVIS. Ses nombres ne sont pas recalculés : ils sont
  REPRIS des valeurs DÉJÀ SERVIES à la page (``build_quote_data``). C'est la
  discipline du palier ``retenu`` de l'échelle batterie, et la parade à
  l'incident « 21 contre 22 » : deux calculs voisins, deux arrondis, deux
  chiffres pour la même chose. Un seul calcul, une seule vérité.
* **Éco** = le point de MEILLEUR PAYBACK du balayage moteur, lu par
  :func:`~apps.ventes.dimensionnement.point_depart_meilleur_payback` — la
  FONCTION MÊME dont ``choisir_recommandation`` fait son point de départ. Les
  deux ne peuvent donc jamais désigner deux tailles différentes.
* **Max** = la plus grande taille admissible : LA CONTENANCE RÉELLE DU TOIT
  quand le devis porte un calepinage (:func:`~apps.ventes.calepinage_options.
  capacite_toit_du_devis` — panneaux conservés + extension maximale PROUVÉE à
  l'intérieur du polygone réel), sinon la dernière taille éligible du balayage,
  qui porte déjà ses propres bornes (facteur falaise, ``MAX_PANNEAUX_BALAYAGE``),
  PLAFONNÉE par le mur physique du tracé client (:func:`~apps.ventes.
  dimensionnement.plafond_physique_du_devis` — aire ÷ empreinte d'un panneau).
  Jamais un panneau au-delà d'une borne physique.

  ET LE COMPTE DESSINÉ NE LA PINCE PLUS (28/08/2026) : un devis AUTOMATIQUE
  naît avec un layout CONTOUR-SEUL dont ``result.panels`` n'est que la cible
  VENDUE. Rien n'y étant mesurable, le lire comme un plafond de toit effondrait
  Max sur Recommandé sur TOUS les devis automatiques — et court-circuitait en
  prime le repli « dernière taille éligible ».

  ELLE NE S'ANCRE PLUS SUR ``plafond_toit_du_devis`` (26/08/2026, devis live
  test15) : cette fonction rend le nombre de panneaux DESSINÉS par le
  commercial. Recommandé étant resynchronisé sur ce même dessin, Max valait
  Recommandé sur TOUT devis calepiné — la troisième carte s'effondrait
  toujours. Le dessiné reste la bonne cible pour la resynchronisation ; il n'a
  jamais été la contenance.

CONVERGENCE : quand deux tailles désignent le même champ (l'optimum EST déjà
le devis, ou le toit est déjà saturé), la liste COLLAPSE — deux cartes, voire
une. JAMAIS une taille intermédiaire fabriquée pour remplir un troisième
emplacement.

OMISSION PLUTÔT QUE SUBSTITUTION. Chaque champ de carte est facultatif,
exactement comme les ``_card_if`` du PDF : sans donnée réelle, le champ est
OMIS — jamais un zéro, jamais un forfait. Une carte peut être plus pauvre
qu'une autre ; c'est la vérité de ce devis-là.

LA BANQUE EST TOUJOURS CELLE DU DEVIS (BATHOMO, fondateur 26/08/2026) : le
module vient des LIGNES du devis (:func:`~apps.ventes.dimensionnement.
module_batterie_du_devis`), la banque est HOMOGÈNE, et elle grandit en N
modules de CE calibre — jamais un re-choix catalogue qui basculerait vers un
autre calibre en cours d'échelle.

CE MODULE N'ÉCRIT RIEN sur le chemin de LECTURE et ne lève JAMAIS depuis
:func:`offres_tailles_publique`. Les seules écritures sont celles que le
vendeur demande explicitement (:func:`enregistrer_config`,
:func:`regenerer_taille`), et elles ne touchent QUE
``Devis.offres_tailles_config``.

Contrat partagé : ``apps/ventes/contract_samples/offres_tailles.json``.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Les trois clés, dans l'ordre d'affichage (Éco → Recommandé → Max).
CLES = ('eco', 'recommande', 'max')

#: Le titre FR de chaque taille (noms approuvés par le fondateur).
TITRES = {'eco': 'Éco', 'recommande': 'Recommandé', 'max': 'Max'}

#: TVA de repli — MÊME réglage que ``rafraichir_dimensionnement_devis`` et que
#: l'échelle de paliers : chaque produit porte DÉJÀ son taux
#: (``_lire_composition``), celui-ci n'est que le repli.
_TVA_REPLI = Decimal('20')

#: Les rôles de composition, regroupés en FAMILLES. ANTICOPIE : la comparaison
#: « ce qui change » entre deux tailles ne nomme que des familles — jamais un
#: calibre, jamais une quantité de nomenclature. Un rôle inconnu (le jour où le
#: catalogue en référence un) tombe dans ``None`` et n'est cité nulle part,
#: plutôt que reclassé de force dans une famille voisine.
_FAMILLES = {
    'panneau': 'panneau',
    'onduleur_reseau': 'onduleur',
    'onduleur_hybride': 'onduleur',
    'batterie': 'batterie',
    'structure_acier': 'structure',
    'structure_alu': 'structure',
    'socle': 'structure',
    'cable_dc': 'cablage',
    'cable_terre': 'cablage',
    'tableau': 'protections',
    'smart_meter': 'accessoires',
    'wifi_dongle': 'accessoires',
    'accessoires': 'accessoires',
    'installation': 'services',
    'transport': 'services',
    'suivi': 'services',
}

#: Les familles dont la page publie la MARQUE et le MODÈLE. Les marques sont
#: TOUJOURS affichées (décision fondateur) ; la carte reste néanmoins courte —
#: le client compare trois installations, pas trois nomenclatures.
_FAMILLES_MATERIEL = ('panneau', 'onduleur', 'batterie')

#: Ordre de tri des rôles pour ``materiel`` (le panneau d'abord, comme le PDF).
_ORDRE_MATERIEL = {'panneau': 0, 'onduleur': 1, 'batterie': 2}

#: LES SEULES ENTRÉES qu'un vendeur peut écrire sur une taille.
#: Tout le reste est DÉRIVÉ, donc réestampillé par le moteur à chaque lecture.
CHAMPS_CONFIG = ('nb_panneaux', 'batterie_nb_modules', 'equipements')

#: LES NOMBRES DÉRIVÉS — refusés en 400 par le sérialiseur, jamais ignorés en
#: silence. C'est la règle « zéro chiffre inventé » rendue STRUCTURELLE : il
#: n'existe aucun chemin par lequel un prix, une économie ou un payback tapé à
#: la main puisse entrer dans le stockage, donc aucun par lequel il puisse
#: ressortir sur une page client. Un refus BRUYANT vaut mieux qu'un champ
#: silencieusement ignoré : le vendeur qui essaie apprend la règle.
CHAMPS_DERIVES = (
    'prix_ttc', 'prix_par_kwc_ttc', 'economie_annuelle_mad', 'payback_annees',
    'couverture_pct', 'taux_autoconsommation_pct', 'production_annuelle_kwh',
    'economies_cumulees_25_ans_mad', 'puissance_kwc', 'capacite_utile_kwh',
    'batterie', 'materiel', 'familles', 'familles_diff', 'toit_ok',
    'est_le_devis', 'recommande', 'titre',
)


# ════════════════════════════════════════════════════════════════════════════
# Petits lecteurs — tolérants, jamais un chiffre fabriqué
# ════════════════════════════════════════════════════════════════════════════

def _num(valeur, defaut=0.0):
    """Flottant tolérant : ``None``/illisible ⇒ ``defaut`` (jamais une levée)."""
    if valeur is None:
        return defaut
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def _positif(valeur):
    """La valeur en flottant si elle est STRICTEMENT positive, sinon ``None``.

    C'est le filtre d'OMISSION : un zéro n'est pas une mesure, c'est l'absence
    de mesure. Le champ disparaît de la carte plutôt que d'afficher « 0 ».
    """
    nombre = _num(valeur, 0.0)
    return nombre if nombre > 0 else None


def _pct(fraction):
    """Une fraction [0,1] du moteur en POURCENTAGE affichable, ou ``None``.

    ``0.0`` est légitime ici (une couverture réellement nulle est une
    information), mais ``None`` reste ``None`` : le moteur n'a pas répondu.
    """
    if fraction is None:
        return None
    return round(_num(fraction) * 100.0, 1)


def _payback(cout, economie):
    """Payback simple, ou ``None`` quand il n'est pas chiffrable.

    MÊME formule que l'échelle de paliers, et MÊME base : le coût passé ici est
    DÉJÀ remisé, donc le payback affiché correspond au prix affiché. Sans cela,
    la carte annoncerait un prix remisé et un retour calculé sur le catalogue.
    """
    if cout is None or economie is None or cout <= 0 or economie <= 0:
        return None
    return round(cout / economie, 2)


def _prix_par_kwc(prix_ttc, kwc):
    """Le prix au kWc TTC, arrondi COMME le moteur de rendu l'arrondit.

    ``quote_engine.builder`` calcule ``round(total / kwc)`` (un entier de MAD)
    et le PDF l'imprime tel quel. On reprend la MÊME expression pour que la
    carte et le PDF ne puissent pas afficher deux valeurs à une unité près —
    la page ne crée pas une seconde surface d'arrondi.
    """
    if not prix_ttc or not kwc or kwc <= 0:
        return None
    return float(round(prix_ttc / kwc))


# ════════════════════════════════════════════════════════════════════════════
# Le matériel d'une carte — marque, modèle, garantie DE LA FICHE
# ════════════════════════════════════════════════════════════════════════════

def _garantie_ans(produit):
    """La garantie en ANNÉES, LUE SUR LA FICHE du produit, ou ``None``.

    RÈGLE DE LA FICHE SEULEMENT (``_gar_de_la_fiche`` du moteur de rendu) : la
    garantie affichée vient de ``stock.Produit.garantie_mois`` et de nulle part
    ailleurs. Pas de fiche ⇒ pas de garantie affichée — jamais une durée
    « standard » supposée, jamais une promesse que personne n'a signée.

    Moins de douze mois ⇒ ``None`` : la carte parle en années, et « 0 an »
    serait un mensonge sur une garantie de six mois.
    """
    mois = _num(getattr(produit, 'garantie_mois', None), 0.0)
    if mois < 12:
        return None
    return int(mois // 12)


def _materiel_de_composition(lignes, roles, substitutions=None):
    """``[{role, famille, marque, modele, garantie_ans}]`` pour les 3 familles.

    Chaque champ est OMIS quand il n'existe pas réellement : un produit sans
    marque renseignée n'invente pas de marque, un produit sans fiche de
    garantie n'affiche pas de garantie. Le ``modele`` est la DÉSIGNATION
    catalogue de la ligne — c'est le nom que le client lit sur son devis.

    ``substitutions`` — LA CARTE DOIT NOMMER CE QU'ELLE FACTURE. Quand le
    vendeur a remplacé un produit sur cette taille, c'est le REMPLAÇANT qui
    donne la marque, le modèle et la garantie : afficher le produit du moteur
    à côté du prix du remplaçant décrirait une installation qui n'existe pas.
    """
    substitutions = substitutions or {}
    materiel, deja_vues = [], set()
    for index, ligne in enumerate(lignes or []):
        role = roles[index] if index < len(roles or ()) else None
        famille = _FAMILLES.get(role)
        if famille not in _FAMILLES_MATERIEL or famille in deja_vues:
            continue
        deja_vues.add(famille)
        remplacant = substitutions.get(role)
        produit = remplacant if remplacant is not None else getattr(
            ligne, 'produit', None)
        entree = {'role': role, 'famille': famille}
        marque = (getattr(produit, 'marque', '') or '').strip()
        if marque:
            entree['marque'] = marque
        modele = (getattr(produit, 'nom', '') or '').strip() \
            if remplacant is not None \
            else (getattr(ligne, 'designation', '') or '').strip()
        if modele:
            entree['modele'] = modele
        garantie = _garantie_ans(produit)
        if garantie is not None:
            entree['garantie_ans'] = garantie
        materiel.append(entree)
    materiel.sort(key=lambda e: _ORDRE_MATERIEL.get(e['famille'], 9))
    return materiel


def _materiel_du_devis(devis, variante):
    """``(materiel, tout_classe)`` lu sur les LIGNES RÉELLES (carte Recommandé).

    La carte Recommandé ne recompose rien : elle lit ce que le client achète,
    POUR LA VARIANTE DEMANDÉE (lignes communes + lignes de cette option).

    ``tout_classe`` dit si CHAQUE ligne a pu être rattachée à un rôle
    catalogue. À ``False``, l'appelant s'interdit de publier « ce qui change » :
    une famille manquée côté référence ferait accuser les autres tailles d'un
    ajout ou d'un retrait imaginaire.
    """
    from apps.ventes.dimensionnement import _lignes_produit_du_devis

    admises = ('', 'sans') if variante == 'sans' else ('', 'avec')
    materiel, deja_vues, tout_classe = [], set(), True
    for ligne in _lignes_produit_du_devis(devis):
        # L-2OPT — LA VARIANTE DÉCIDE. Un devis à deux options porte les lignes
        # des DEUX (onduleur réseau côté « sans », onduleur hybride + batterie
        # côté « avec ») plus les lignes communes. Les lire toutes faisait
        # nommer l'onduleur RÉSEAU sur la carte « avec » (première ligne
        # rencontrée) et lister la BATTERIE sur la carte « sans » — deux
        # descriptions fausses de la même page. C'est la discipline que
        # ``_compter_modules_du_devis`` et ``facteur_remise_du_devis``
        # appliquent déjà ; elle manquait ici.
        if (getattr(ligne, 'variante', '') or '') not in admises:
            continue
        designation = (getattr(ligne, 'designation', '') or '').strip()
        if not designation:
            continue
        role = _role_de_la_ligne(designation)
        if role is None:
            tout_classe = False
            continue
        famille = _FAMILLES.get(role)
        if famille not in _FAMILLES_MATERIEL or famille in deja_vues:
            continue
        deja_vues.add(famille)
        entree = {'role': role, 'famille': famille, 'modele': designation}
        produit = getattr(ligne, 'produit', None)
        marque = (getattr(produit, 'marque', '') or '').strip()
        if marque:
            entree['marque'] = marque
        garantie = _garantie_ans(produit)
        if garantie is not None:
            entree['garantie_ans'] = garantie
        materiel.append(entree)
    materiel.sort(key=lambda e: _ORDRE_MATERIEL.get(e['famille'], 9))
    return materiel, tout_classe


def _role_de_la_ligne(designation):
    """Le RÔLE catalogue d'une désignation de ligne, ou ``None``.

    MÊME CLASSIFIEUR DES DEUX CÔTÉS. Les cartes Éco et Max lisent les rôles que
    ``composition_residentielle`` a POSÉS sur sa composition ; la carte
    Recommandé, elle, part de libellés de lignes. Utiliser ici une seconde
    heuristique par mots-clés créait une ASYMÉTRIE DE SOURCE : une ligne
    d'onduleur nommée hors convention n'était pas reconnue côté devis, et « ce
    qui change » annonçait alors « Éco AJOUTE : onduleur » — une différence qui
    n'existe pas. On appelle donc ``services.classer_produit``, LE classifieur
    catalogue (le même que le générateur et la composition).

    Les détecteurs par mots-clés ne servent plus que de REPLI, pour les
    libellés qu'un classifieur strict laisse tomber (il exige « onduleur
    hybride » ou « onduleur réseau/injection » explicites). ``None`` = la ligne
    reste NON CLASSÉE : l'appelant le signale plutôt que de deviner.
    """
    from apps.ventes.services import (
        _is_battery, _is_hybrid_inverter, _is_panel, _is_reseau_inverter,
        classer_produit)

    try:
        role = classer_produit(designation)
    except Exception:  # noqa: BLE001 — un libellé exotique n'est pas une panne
        role = None
    if role:
        return role
    for role_repli, detecteur in (('onduleur_hybride', _is_hybrid_inverter),
                                  ('onduleur_reseau', _is_reseau_inverter),
                                  ('panneau', _is_panel),
                                  ('batterie', _is_battery)):
        try:
            if detecteur(designation):
                return role_repli
        except Exception:  # noqa: BLE001
            continue
    return None


def _familles(materiel_ou_roles, roles=None):
    """Les FAMILLES présentes, triées — jamais un calibre, jamais une quantité.

    BORNÉES À :data:`_FAMILLES_MATERIEL` (panneau / onduleur / batterie), et
    c'est une CONDITION DE COMPARABILITÉ, pas une coquetterie : la carte
    Recommandé lit les LIGNES du devis tandis qu'Éco et Max lisent une
    composition catalogue. Les deux lectures ne voient pas les mêmes rôles
    accessoires (ferrure, câblage, transport…), si bien qu'une liste complète
    d'un côté et partielle de l'autre ferait dire à « ce qui change » que
    l'offre Éco ajoute la structure et le transport — un mensonge d'artefact.
    Les trois familles retenues sont d'ailleurs les SEULES qui distinguent
    réellement deux tailles : tout le reste est présent partout par
    construction.
    """
    if roles is not None:
        presentes = {_FAMILLES.get(role) for role in (roles or ())}
    else:
        presentes = {e.get('famille') for e in (materiel_ou_roles or [])}
    return sorted(f for f in presentes if f in _FAMILLES_MATERIEL)


def _diff_familles(familles, reference):
    """``{ajoutees, retirees}`` de cette carte FACE À la carte Recommandé.

    ANTICOPIE : une différence se dit en familles (« il n'y a pas de
    batterie »), jamais en nomenclature (« il manque 2 × BAT-XX 5 kWh »). Le
    bloc est OMIS quand rien ne diffère — une table de comparaison vide
    n'apprend rien.
    """
    ajoutees = sorted(set(familles) - set(reference))
    retirees = sorted(set(reference) - set(familles))
    if not ajoutees and not retirees:
        return None
    return {'ajoutees': ajoutees, 'retirees': retirees}


# ════════════════════════════════════════════════════════════════════════════
# LES 25 ANS — sans hausse tarifaire supposée, et la page le DIT
# ════════════════════════════════════════════════════════════════════════════

def _cumul_servi(data, variante, prix_ttc):
    """Le cumul 25 ans de la carte Recommandé, LU SUR LA COURBE DE LA PAGE.

    ``data['cashflow_sans'|'cashflow_avec']`` EST la série cumulée que la page
    et le PDF tracent déjà (``pricing`` la publie depuis ``cf['cumulative']``).
    Son dernier point est la position nette à 25 ans ; y ré-ajouter le prix
    donne les économies ENCAISSÉES sur l'horizon.

    POURQUOI ON NE LA RECALCULE PAS. ``pricing`` appelle
    ``compute_cashflow_payback`` avec DEUX arguments de plus que la signature
    par défaut : ``inverter_replace_cost`` (le prix TTC RÉEL de la ligne
    onduleur, décision fondateur Q1 du 20/08) et ``battery_share`` (la part de
    l'économie qui transite VRAIMENT par la batterie — Z5, même date). Sans
    ``battery_share``, le moteur retombe sur l'abattement forfaitaire de 0,90
    sur TOUTE l'économie : précisément le bug que le fondateur a fait corriger.
    Recalculer ici « à peu près pareil » aurait donc affiché, sous la courbe de
    la page, un total qui ne finit pas où la courbe finit.

    ``None`` dès que la série manque — jamais une projection reconstituée.
    """
    serie = (data or {}).get('cashflow_%s' % variante)
    if not isinstance(serie, (list, tuple)) or not serie or not prix_ttc:
        return None
    return round(_num(serie[-1]) + float(prix_ttc), 2)


def _cumul_moteur(prix_ttc, economie_annuelle, *, stockage, part_batterie,
                  cout_onduleur_ttc):
    """Le cumul 25 ans d'une taille DÉRIVÉE — mêmes arguments que la page.

    ``compute_cashflow_payback`` reçoit ici les DEUX arguments que
    ``pricing.calculate_savings_roi`` lui passe pour le devis officiel, dérivés
    de CETTE taille : la provision de remplacement d'onduleur (Q1 — le prix TTC
    réel de SA ligne onduleur, jamais un pourcentage) et la part réellement
    stockée (Z5 — sans elle, l'abattement de 0,90 frapperait aussi l'énergie
    autoconsommée au fil du soleil, qui n'entre jamais dans la batterie).

    ``TARIFF_ESCALATION`` reste à 0 et n'est pas touché : la projection est à
    tarif PLAT, et le bloc sert ``escalade_tarifaire_pct`` pour que la page
    imprime « aucune hausse tarifaire supposée » AU-DESSUS du chiffre.
    """
    if not prix_ttc or not economie_annuelle:
        return None
    try:
        from .quote_engine.pricing import compute_cashflow_payback
        resultat = compute_cashflow_payback(
            float(prix_ttc), float(economie_annuelle),
            battery=bool(stockage), battery_share=part_batterie,
            inverter_replace_cost=cout_onduleur_ttc)
    except Exception:  # noqa: BLE001 — un cumul indisponible s'omet
        logger.warning('cumul 25 ans indisponible', exc_info=True)
        return None
    cumul = (resultat or {}).get('cumulative') or []
    if not cumul:
        return None
    return round(_num(cumul[-1]) + float(prix_ttc), 2)


def _part_batterie(annuel):
    """La part de l'économie qui transite RÉELLEMENT par la batterie (Z5).

    Formule REPRISE de ``pricing.calculate_savings_roi`` au caractère près :
    le socle ``taux_autoconso_sans`` est autoconsommé DIRECTEMENT au fil du
    soleil (aucune charge/décharge), seul le supplément apporté par la capacité
    est stocké puis restitué. ``None`` quand les taux manquent — le moteur
    retombe alors sur son propre défaut documenté.
    """
    avec = _num((annuel or {}).get('taux_autoconso_avec'))
    sans = _num((annuel or {}).get('taux_autoconso_sans'))
    if avec <= 0:
        return None
    return max(0.0, avec - sans) / avec


def _cout_onduleur_ttc(lignes, roles, facteur_remise):
    """Le prix TTC RÉEL des lignes onduleur d'une composition (Q1), ou ``None``.

    C'est la provision de remplacement que le cashflow 25 ans retranche à
    l'année :data:`~apps.ventes.quote_engine.pricing.INVERTER_REPLACE_YEAR`.
    Décision fondateur du 20/08 : le prix RÉEL de la ligne, jamais un
    pourcentage du total ; aucune ligne onduleur ⇒ AUCUNE provision (``None``),
    jamais un forfait de repli.

    Remisé comme le prix de la carte : les deux doivent partager une base.
    """
    total = 0.0
    for index, ligne in enumerate(lignes or []):
        role = roles[index] if index < len(roles or ()) else None
        if role not in ('onduleur_reseau', 'onduleur_hybride'):
            continue
        quantite = _num(getattr(ligne, 'quantite', 0))
        pu_ht = _num(getattr(ligne, 'prix_unitaire', 0))
        tva = _num(getattr(getattr(ligne, 'produit', None), 'tva', None),
                   defaut=-1.0)
        facteur = 1.0 + (tva if tva >= 0 else float(_TVA_REPLI)) / 100.0
        total += quantite * pu_ht * facteur
    total *= float(facteur_remise or 1.0)
    return round(total, 2) if total > 0 else None


def _horizon_et_escalade():
    """``(horizon_annees, escalade_pct)`` LUS sur le moteur, jamais codés ici."""
    try:
        from .quote_engine.pricing import CASHFLOW_YEARS, TARIFF_ESCALATION
        return int(CASHFLOW_YEARS), round(float(TARIFF_ESCALATION) * 100.0, 2)
    except Exception:  # noqa: BLE001
        return None, None


# ════════════════════════════════════════════════════════════════════════════
# LE CONTEXTE DE DÉRIVATION — lu UNE fois, partagé par les trois tailles
# ════════════════════════════════════════════════════════════════════════════

class _Contexte:
    """Tout ce qu'une dérivation de taille a besoin de savoir sur ce devis.

    Construit UNE fois par appel : catalogue, marques épinglées, ordre des
    lignes, wattage réel du panneau, bornes du champ, module batterie du devis,
    facteur de remise. Les trois tailles le partagent — sans quoi trois
    lectures du même devis pourraient diverger.
    """

    def __init__(self, devis, entrees, panel_watt, catalogue, marques, ordre):
        self.devis = devis
        self.entrees = entrees
        self.panel_watt = panel_watt
        self.catalogue = catalogue
        self.marques = marques
        self.ordre = ordre
        from apps.ventes.calepinage_options import capacite_toit_du_devis
        from apps.ventes.dimensionnement import (
            facteur_remise_du_devis, module_batterie_du_devis,
            plafond_toit_du_devis)
        self.module_batterie_kwh = module_batterie_du_devis(devis)
        self.facteur_remise = facteur_remise_du_devis(devis)
        #: Ce que le commercial a DESSINÉ (``layout.result.panels``) — la cible
        #: de resynchronisation, PAS la contenance du toit.
        self.plafond_toit = plafond_toit_du_devis(devis)
        #: Ce que la géométrie RÉELLE du toit tient (panneaux conservés +
        #: extension maximale prouvée à l'intérieur du polygone). Mémoïsé sur
        #: le devis : UN seul balayage par requête, partagé par les six cartes.
        self.capacite_toit = capacite_toit_du_devis(devis)

    @property
    def plafond_physique(self):
        """LE MUR PHYSIQUE du tracé client (aire ÷ empreinte d'un panneau).

        LU PARESSEUSEMENT, ET C'EST VOULU : il lit le catalogue (le produit
        panneau et sa fiche technique), or il ne sert QUE lorsqu'aucun
        calepinage n'est mesurable. Le calculer d'office ajouterait une requête
        à chaque dérivation d'un devis calepiné, pour un nombre que
        :meth:`toit_max` jetterait. Le résultat est mémoïsé sur l'instance de
        devis, donc le relire ne coûte rien.
        """
        from apps.ventes.dimensionnement import plafond_physique_du_devis
        return plafond_physique_du_devis(self.devis)

    @property
    def toit_max(self):
        """Le plus grand nombre de panneaux que ce toit accepte, ou ``None``.

        LA RÈGLE VIT DANS ``dimensionnement.plus_grande_contenance`` — UN SEUL
        endroit, partagé avec la borne de champ de l'échelle de paliers
        batterie. Deux expressions voisines de « ce toit accepte N panneaux »
        finiraient par diverger, et c'est précisément une divergence de ce
        genre (le dessiné se faisant passer pour la contenance) qui a effondré
        cette carte-ci.

        SANS CALEPINAGE MESURABLE, C'EST LE MUR PHYSIQUE DU TRACÉ, jamais le
        compte dessiné (28/08/2026) — sur un devis AUTOMATIQUE, ``result.panels``
        ne porte que la cible VENDUE, et la prendre pour un plafond de toit
        effondrait Max sur Recommandé.
        """
        from apps.ventes.dimensionnement import plus_grande_contenance
        physique = None if self.capacite_toit else self.plafond_physique
        return plus_grande_contenance(self.capacite_toit, self.plafond_toit,
                                      physique)

    @property
    def etude_kwargs(self):
        return {
            'conso_kwh_mensuelles': self.entrees['conso_kwh_mensuelles'],
            'ville': self.entrees['ville'],
            'lat': self.entrees['lat'],
            'lon': self.entrees['lon'],
            'occupation': self.entrees['occupation'],
            'equipements': self.entrees['equipements'],
        }

    def composer(self, nb_panneaux, *, avec_batterie, cible_kwh=None):
        """Une composition catalogue RÉELLE, ou ``None`` — jamais une levée.

        Le pin ``batterie_module_kwh`` porte la règle fondateur : la banque
        grandit en N modules du calibre DÉJÀ vendu par ce devis, homogène,
        jamais un re-choix catalogue.
        """
        from apps.ventes.services import composition_residentielle
        kwc = nb_panneaux * self.panel_watt / 1000.0
        try:
            return composition_residentielle(
                self.catalogue, kwc=kwc, panel_watt=self.panel_watt,
                nb_panneaux=nb_panneaux, avec_batterie=avec_batterie,
                structure_type='acier', taux_tva=_TVA_REPLI,
                avertissements=[], deux_options=False, marques=self.marques,
                ordre_lignes=self.ordre,
                batterie_cible_kwh=cible_kwh,
                batterie_module_kwh=self.module_batterie_kwh)
        except Exception:  # noqa: BLE001 — une taille impossible ne fait pas
            # tomber les deux autres.
            logger.warning('composition de taille impossible à %s panneaux',
                           nb_panneaux, exc_info=True)
            return None


def _contexte(devis):
    """Le contexte, ou ``None`` quand ce devis n'est pas dérivable DU TOUT.

    Les gardes sont celles de l'échelle de paliers, dans le même ordre :
    résidentiel + société (``entrees_dimensionnement_du_devis`` refuse tout le
    reste), profil de consommation RÉEL, catalogue qui compose vraiment un
    panneau. Aucune n'est franchie par défaut — sans profil réel, la section
    disparaît au lieu d'afficher une estimation.
    """
    from apps.ventes.services import (
        _AUTO_PANEL_WATT, carte_marques_composition, catalogue_de_la_societe,
        composition_residentielle, entrees_dimensionnement_du_devis,
        ordre_lignes_societe)

    entrees = entrees_dimensionnement_du_devis(devis)
    if not entrees or not entrees.get('conso_kwh_mensuelles'):
        return None
    company = entrees['company']
    catalogue = catalogue_de_la_societe(company)
    marques = carte_marques_composition(company, None)
    ordre = ordre_lignes_societe(company)
    # Le wattage RÉELLEMENT retenu par le catalogue — lu, jamais supposé
    # (même sonde que ``balayer_tailles`` et que l'échelle de paliers).
    sonde = composition_residentielle(
        catalogue, kwc=_AUTO_PANEL_WATT / 1000.0, panel_watt=_AUTO_PANEL_WATT,
        nb_panneaux=1, avec_batterie=False, structure_type='acier',
        taux_tva=_TVA_REPLI, avertissements=[], deux_options=False,
        marques=marques, ordre_lignes=ordre)
    panel_watt = _num(getattr(sonde, 'panel_watt_reel', 0))
    if panel_watt <= 0:
        return None
    return _Contexte(devis, entrees, panel_watt, catalogue, marques, ordre)


# ════════════════════════════════════════════════════════════════════════════
# LES CHAMPS DES TROIS TAILLES
# ════════════════════════════════════════════════════════════════════════════

def _tableau_du_devis(devis):
    """Le TABLEAU de dimensionnement DÉJÀ POSÉ sur ce devis, ou ``[]``.

    LECTURE SEULE, DÉLIBÉRÉMENT. Le tableau est rafraîchi par tous les chemins
    d'ÉCRITURE du devis (``services.rafraichir_etudes_du_devis``) ; le rejouer
    ici relancerait un balayage complet — des dizaines de compositions et de
    simulations journalières — sur un endpoint public NON CACHÉ, et écrirait
    sur le devis depuis un chemin de lecture. Pas de tableau ⇒ pas de section :
    elle apparaît dès la prochaine écriture du devis.
    """
    etude_params = getattr(devis, 'etude_params', None) or {}
    dimensionnement = etude_params.get('dimensionnement') or {}
    if not isinstance(dimensionnement, dict):
        return []
    tableau = dimensionnement.get('tableau')
    return tableau if isinstance(tableau, list) else []


def _champs_des_tailles(contexte, nb_panneaux_devis):
    """``{cle: nb_panneaux}`` — le champ PV de chacune des trois tailles.

    Une clé ABSENTE = cette taille n'est pas dérivable (ou a convergé vers une
    autre) : la liste collapse, elle ne se remplit jamais d'un intermédiaire
    fabriqué.
    """
    from apps.ventes.dimensionnement import (
        point_depart_meilleur_payback, tailles_eligibles)

    champs = {}
    if nb_panneaux_devis:
        champs['recommande'] = int(nb_panneaux_devis)

    eligibles = tailles_eligibles(_tableau_du_devis(contexte.devis))
    if not eligibles:
        return champs

    depart, _meilleur, _egalite = point_depart_meilleur_payback(eligibles)
    if depart and _num(depart.get('panneaux')) > 0:
        champs['eco'] = int(depart['panneaux'])

    # MAX — LA CONTENANCE RÉELLE DU TOIT quand le devis porte un calepinage.
    #
    # CE QUI A CHANGÉ, ET POURQUOI (ordre fondateur, 26/08/2026, diagnostiqué
    # sur le devis live test15). Cette borne était ``plafond_toit_du_devis``,
    # c'est-à-dire le nombre de panneaux DESSINÉS par le commercial. Or
    # « Recommandé » est resynchronisé sur ce MÊME dessin : Max valait donc
    # Recommandé sur TOUT devis calepiné, la carte s'effondrait toujours, et le
    # fondateur ne voyait jamais trois cartes. Ce que le commercial a dessiné
    # n'est pas ce que le toit accepte — la contenance se MESURE, et c'est
    # ``calepinage_options.capacite_toit_du_devis`` qui la mesure, avec la MÊME
    # machinerie d'extension que le dessin (donc sans qu'aucune carte ne puisse
    # annoncer un nombre que son propre calepinage ne saurait dessiner).
    #
    # LA GARDE EST « ``capacite_toit``, PAS ``toit_max`` » (28/08/2026) : c'est
    # la MESURE qui ouvre cette branche-là, jamais la simple existence d'une
    # borne — sans quoi le mur physique du tracé, qui ne fait que refuser
    # l'impossible, se mettrait à PROPOSER un champ (voir le repli plus bas).
    #
    # LE PLANCHER À « RECOMMANDÉ » GARDE LA CONVERGENCE HONNÊTE : un toit déjà
    # saturé (contenance == dessiné) redonne le champ du devis, la signature
    # collapse les deux cartes, et la liste ne se remplit JAMAIS d'un
    # intermédiaire fabriqué pour occuper un troisième emplacement.
    if contexte.capacite_toit:
        champs['max'] = max(int(contexte.toit_max),
                            int(nb_panneaux_devis or 0))
        return champs

    # AUCUN CALEPINAGE MESURABLE — LE REPLI, ET SA BORNE (28/08/2026).
    #
    # C'est l'état de TOUT devis AUTOMATIQUE : ``zone_toit_depuis_contour`` pose
    # le tracé du client et écrit ``result.panels`` = la cible VENDUE, sans
    # sérialiser un seul panneau. Rien n'est donc mesurable — et le compte
    # dessiné, qui n'est ici que ce qu'on vient de vendre, n'a JAMAIS eu le
    # droit de dire « ce toit accepte N ». Il le disait pourtant : Max valait
    # Recommandé, la troisième carte s'effondrait sur tous les devis
    # automatiques, et la simple présence du layout court-circuitait ce
    # repli-ci.
    #
    # Le repli est la dernière taille ÉLIGIBLE du balayage (qui porte déjà ses
    # propres bornes : facteur falaise + ``MAX_PANNEAUX_BALAYAGE``) — PLAFONNÉE
    # par le mur physique du tracé quand il est connu (``toit_max`` vaut alors
    # exactement ``plafond_physique_du_devis``). Ce mur ne PROPOSE rien : il ne
    # fait que refuser une taille physiquement impossible.
    admissibles = [int(x['panneaux']) for x in eligibles
                   if _num(x.get('panneaux')) > 0]
    if admissibles:
        maximum = max(admissibles)
        if contexte.toit_max:
            maximum = min(maximum, int(contexte.toit_max))
        # LE MÊME PLANCHER QUE LA BRANCHE MESURÉE (revue Fable, 28/08/2026) :
        # sans lui, un balayage court ou un tracé PARTIEL (le client n'a dessiné
        # qu'un pan) rendait une carte Max PLUS PETITE que le devis officiel —
        # un ordre Éco → Recommandé → Max incohérent pour le client. Le champ du
        # devis est la réalité vendue : Max ne descend jamais dessous, et
        # l'égalité fait collapser les deux cartes au lieu de mentir.
        champs['max'] = max(maximum, int(nb_panneaux_devis or 0))
    return champs


# ════════════════════════════════════════════════════════════════════════════
# UNE CARTE — dérivée du moteur (Éco / Max) ou REPRISE du devis (Recommandé)
# ════════════════════════════════════════════════════════════════════════════

def _carte_moteur(contexte, nb_panneaux, config=None, *, avec_servable=True):
    """Les deux variantes d'une taille, composées et chiffrées par le moteur.

    UN SEUL passage horaire pour les DEUX variantes : ``calculer_etude_horaire``
    rend ``economie_sans_mad`` ET ``economie_avec_mad``, les deux couvertures et
    les deux taux d'autoconsommation sur la MÊME intégration — deux appels
    séparés pourraient diverger d'un arrondi.

    ``avec_servable=False`` court-circuite TOUT le chemin batterie (composition,
    bornes de puissance, verdict de remplissage) : sans lui, un devis sans
    option batterie composait puis balayait douze jours types pour JETER le
    résultat — deux passages horaires gaspillés par taille, sur un endpoint
    public non caché.

    Renvoie ``{'sans': carte|None, 'avec': carte|None}``.
    """
    from apps.ventes.dimensionnement import _compter_modules_batterie
    from apps.ventes.dimensionnement import _lire_composition
    from apps.ventes.etude_horaire import (
        calculer_etude_horaire, puissances_batterie_des_lignes)

    kwc = round(nb_panneaux * contexte.panel_watt / 1000.0, 3)
    # Les substitutions sont RÉSOLUES UNE FOIS : le prix, la capacité de la
    # banque et le nom affiché doivent décrire LE MÊME produit. Les résoudre
    # trois fois séparément, c'est se donner trois occasions d'en oublier une
    # — et afficher le panneau du moteur au-dessus du prix du remplaçant.
    substitutions = _resoudre_substitutions(
        (config or {}).get('equipements'),
        company=(contexte.entrees or {}).get('company'))

    cible = None
    modules_demandes = (config or {}).get('batterie_nb_modules')
    if modules_demandes and contexte.module_batterie_kwh:
        cible = float(modules_demandes) * float(contexte.module_batterie_kwh)

    lignes_sans = contexte.composer(nb_panneaux, avec_batterie=False)
    lignes_avec = (contexte.composer(nb_panneaux, avec_batterie=True,
                                     cible_kwh=cible)
                   if avec_servable else None)
    if lignes_sans is None and lignes_avec is None:
        return {'sans': None, 'avec': None}

    vue_sans = _substituer(_lire_composition(lignes_sans, _TVA_REPLI),
                           lignes_sans, substitutions) if lignes_sans else None
    vue_avec = _substituer(_lire_composition(lignes_avec, _TVA_REPLI),
                           lignes_avec, substitutions) if lignes_avec else None

    capacite = _positif((vue_avec or {}).get('batterie_kwh'))
    bornes = {}
    if lignes_avec is not None and capacite:
        try:
            puissances = puissances_batterie_des_lignes(
                lignes_avec, roles=getattr(lignes_avec, 'roles', None))
            bornes = {
                'batterie_puissance_decharge_kw':
                    puissances['packs_decharge_kw'],
                'batterie_puissance_decharge_onduleur_kw':
                    puissances['ond_decharge_kw'],
                'batterie_puissance_charge_kw': puissances['charge_kw'],
            }
        except Exception:  # noqa: BLE001 — sans bornes lues, le moteur
            # retombe sur son régime établi : jamais une borne inventée.
            bornes = {}

    try:
        etude = calculer_etude_horaire(
            kwc=kwc, batterie_kwh_utile=capacite,
            **bornes, **contexte.etude_kwargs)
    except Exception:  # noqa: BLE001
        logger.warning('étude horaire indisponible à %s panneaux',
                       nb_panneaux, exc_info=True)
        etude = None
    annuel = (etude or {}).get('annuel') or {}
    production = _positif(annuel.get('production_kwh'))

    cartes = {'sans': None, 'avec': None}
    for variante, vue, lignes in (('sans', vue_sans, lignes_sans),
                                  ('avec', vue_avec, lignes_avec)):
        if vue is None:
            continue
        if variante == 'avec' and not capacite:
            # Une variante « avec batterie » sans batterie composée n'est pas
            # une variante : elle est ABSENTE, jamais une copie du « sans ».
            continue
        prix = _positif(_num(vue.get('cout_ttc')) * contexte.facteur_remise)
        economie = _positif(annuel.get('economie_%s_mad' % variante))
        carte = {
            'nb_panneaux': int(nb_panneaux),
            'puissance_kwc': kwc,
        }
        if prix is not None:
            carte['prix_ttc'] = round(prix, 2)
            prix_kwc = _prix_par_kwc(prix, kwc)
            if prix_kwc is not None:
                carte['prix_par_kwc_ttc'] = prix_kwc
        if economie is not None:
            carte['economie_annuelle_mad'] = round(economie, 2)
        paye = _payback(prix, economie)
        if paye is not None:
            carte['payback_annees'] = paye
        _ajouter_taux(carte, annuel, variante)
        if production is not None:
            carte['production_annuelle_kwh'] = round(production, 2)
        cumul = _cumul_moteur(
            prix, economie,
            stockage=bool(variante == 'avec' and capacite),
            part_batterie=(_part_batterie(annuel) if variante == 'avec'
                           else None),
            cout_onduleur_ttc=_cout_onduleur_ttc(
                lignes, list(getattr(lignes, 'roles', ()) or ()),
                contexte.facteur_remise))
        if cumul is not None:
            carte['economies_cumulees_25_ans_mad'] = cumul
        if variante == 'avec':
            banque = _banque(
                contexte, vue, capacite,
                _compter_modules_batterie(vue.get('lignes')),
                remplissage_ok=_remplissage_ok(contexte, kwc, capacite,
                                               bornes),
                substitutions=substitutions)
            if banque:
                carte['batterie'] = banque
        roles = list(getattr(lignes, 'roles', ()) or ())
        materiel = _materiel_de_composition(lignes, roles, substitutions)
        if materiel:
            carte['materiel'] = materiel
        familles = _familles(None, roles=roles)
        if familles:
            carte['familles'] = familles
        _ajouter_toit(carte, contexte, nb_panneaux)
        cartes[variante] = carte
    return cartes


def _ajouter_taux(carte, annuel, variante):
    """Couverture et taux d'autoconsommation — UNE seule définition partout.

    Ce sont les DEUX taux du moteur horaire canonique : la couverture est la
    part de la CONSOMMATION réellement servie par l'installation
    (``autoconsommé / consommation``), le taux d'autoconsommation la part de la
    PRODUCTION réellement consommée sur place. Les trois cartes les lisent au
    même endroit — la page n'introduit AUCUNE seconde métrique
    d'« indépendance ».
    """
    couverture = _pct(annuel.get('couverture_%s' % variante))
    if couverture is not None:
        carte['couverture_pct'] = couverture
    autoconso = _pct(annuel.get('taux_autoconso_%s' % variante))
    if autoconso is not None:
        carte['taux_autoconsommation_pct'] = autoconso


def _ajouter_toit(carte, contexte, nb_panneaux):
    """``toit_ok`` — SEULEMENT quand un calepinage MESURÉ existe.

    Sans calepinage MESURABLE, le devis ne sait pas ce que ce toit accepte : le
    champ est OMIS. Jamais un « ça rentre » supposé sur une surface que personne
    n'a mesurée — et jamais un « ça dépasse » non plus (revue Fable,
    28/08/2026) : le mur PHYSIQUE du tracé est une borne large calculée sur un
    contour que le client a pu ne tracer QUE PARTIELLEMENT ; s'en servir pour
    imprimer « Cette taille dépasse ce que votre toit peut accueillir » — y
    compris sur la carte du devis OFFICIEL — accuserait d'impossible une
    installation que personne n'a mesurée. Le mur PLAFONNE la carte Max
    (:func:`_champs_des_tailles`) ; il ne prononce aucun verdict par carte.

    LE VERDICT SE LIT SUR LA CONTENANCE (``toit_max``), PAS SUR LE DESSIN. La
    page imprime « Cette taille dépasse ce que votre toit peut accueillir » dès
    que ce champ vaut ``False`` : le comparer au nombre de panneaux DESSINÉS
    aurait collé cette note à la carte Max le jour même où elle se met enfin à
    proposer davantage — c'est-à-dire à la traiter d'impossible alors que la
    géométrie vient de prouver le contraire.
    """
    if not contexte.capacite_toit or not contexte.toit_max:
        return
    carte['toit_ok'] = bool(int(nb_panneaux) <= int(contexte.toit_max))


def _remplissage_ok(contexte, kwc, capacite, bornes):
    """CE CHAMP CHARGE-T-IL CETTE BANQUE TOUS LES JOURS ? ``None`` = inconnu.

    LA RÈGLE FONDATEUR (« batteries toujours pleines », 24/08/2026) doit se
    LIRE sur la carte : une banque que le champ ne remplit pas est montrée
    grisée avec sa raison, jamais vendue en silence.

    ``balayer_stockage_horaire`` est LA source de ce verdict — la même que
    l'échelle de paliers, au même endroit, avec le même plafond de
    remplissage. Un second critère « à peu près équivalent » calculé ici
    finirait par griser des paliers que l'échelle accepte, et l'inverse.

    UN PASSAGE DE PLUS, ASSUMÉ. ``calculer_etude_horaire`` rend les DEUX
    variantes en un parcours mais ne publie aucun verdict de remplissage ;
    celui-ci en demande un second, restreint à LA capacité de cette taille.
    ``None`` (moteur muet) ⇒ le champ est OMIS de la banque : on ne prétend
    pas qu'une banque se remplit quand on ne l'a pas vérifié.
    """
    if not capacite or not kwc:
        return None
    from apps.ventes.etude_horaire import balayer_stockage_horaire
    try:
        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=[round(capacite, 2)],
            puissances_par_capacite=(
                {round(capacite, 2): {
                    'decharge_kw': bornes.get(
                        'batterie_puissance_decharge_kw'),
                    'decharge_onduleur_kw': bornes.get(
                        'batterie_puissance_decharge_onduleur_kw'),
                    'charge_kw': bornes.get('batterie_puissance_charge_kw'),
                }} if bornes else None),
            **contexte.etude_kwargs)
    except Exception:  # noqa: BLE001 — un verdict indisponible s'omet
        logger.warning('verdict de remplissage indisponible', exc_info=True)
        return None
    for palier in ((energie or {}).get('paliers') or []):
        return bool(palier.get('se_remplit_tous_les_jours'))
    return None


def _banque(contexte, vue, capacite, compteurs, remplissage_ok=None,
            substitutions=None):
    """``{nb_modules, module_kwh, capacite_utile_kwh, remplissage_ok}``.

    ``capacite_utile_kwh`` est la capacité UTILE réellement livrée (règle
    CAPUTIL, lue sur les fiches), tandis que ``module_kwh`` reste le NOMINAL de
    l'étiquette — la grandeur avec laquelle le fondateur et le client comptent
    (« deux batteries de 5 »). Les deux coexistent volontairement : l'une se
    compte, l'autre se mesure.

    ``nb_modules``/``module_kwh`` sont OMIS quand la banque composée ne se lit
    pas en modules d'un seul calibre — plutôt qu'un « N × quelque chose »
    approximé.
    """
    if not capacite:
        return None
    banque = {'capacite_utile_kwh': round(capacite, 2)}
    if remplissage_ok is not None:
        banque['remplissage_ok'] = bool(remplissage_ok)
    if substitutions and 'batterie' in substitutions:
        # LE VENDEUR A CHANGÉ LE MODULE : le pin du devis et les compteurs
        # 5/10 de l'échelle décrivent alors l'ANCIEN module. On lit le calibre
        # sur le REMPLAÇANT (le nominal de son nom, la grandeur avec laquelle
        # le client compte) — jamais l'ancien, qui ne serait plus dans la
        # banque, et jamais une division approchée de la capacité utile.
        from apps.ventes.services import _parse_kwh
        modules = sum(int(_num(ligne.get('quantite')))
                      for ligne in (vue.get('lignes') or [])
                      if ligne.get('role') == 'batterie')
        nominal = _num(_parse_kwh(
            getattr(substitutions['batterie'], 'nom', '') or ''))
        if modules > 0:
            banque['nb_modules'] = modules
            if nominal > 0:
                banque['module_kwh'] = round(nominal, 2)
        return banque
    cinq, dix = compteurs
    if cinq and not dix:
        banque['nb_modules'], banque['module_kwh'] = int(cinq), 5.0
    elif dix and not cinq:
        banque['nb_modules'], banque['module_kwh'] = int(dix), 10.0
    elif contexte.module_batterie_kwh:
        # Un calibre HORS 5/10 (le vrai BOS-B-Pack16, par exemple) : les deux
        # compteurs de l'échelle l'ignorent volontairement, mais le pin, lui,
        # sait quel module ce devis vend. On compte alors les LIGNES batterie
        # de la composition, jamais une division approchée de la capacité.
        modules = sum(int(_num(ligne.get('quantite')))
                      for ligne in (vue.get('lignes') or [])
                      if ligne.get('role') == 'batterie')
        if modules > 0:
            banque['nb_modules'] = modules
            banque['module_kwh'] = round(
                float(contexte.module_batterie_kwh), 2)
    return banque


def _resoudre_substitutions(equipements, company=None):
    """``{role: Produit}`` — les remplacements demandés, résolus UNE fois.

    LA GARDE DE SOCIÉTÉ EST POSÉE PAR LE SÉRIALISEUR, qui refuse en 400 tout
    identifiant hors de la société du devis : c'est LÀ que la frontière
    multi-société se décide, et une garde recopiée finit par diverger de son
    original. Le ``company`` accepté ici est une DÉFENSE EN PROFONDEUR, pas la
    règle : il borne la lecture même si un jour une configuration entrait par
    un autre chemin (une reprise de données, un import, un futur endpoint qui
    oublierait le sérialiseur). Une configuration stockée hier reste par
    ailleurs lisible longtemps après l'écriture qui l'a validée.

    Un identifiant devenu introuvable (produit supprimé depuis l'ajustement)
    est IGNORÉ : la taille garde le produit du moteur plutôt que de faire
    disparaître la carte.
    """
    if not equipements:
        return {}
    from apps.stock.models import Produit

    par_role = {}
    for role, produit_id in (equipements or {}).items():
        try:
            requete = Produit.objects.filter(pk=int(produit_id))
        except (TypeError, ValueError):
            continue
        if company is not None:
            requete = requete.filter(company=company)
        produit = requete.first()
        if produit is not None:
            par_role[role] = produit
    return par_role


def _substituer(vue, lignes, substitutions):
    """Rechiffre une composition avec les produits que le vendeur a substitués.

    PORTÉE VOLONTAIREMENT ÉTROITE, ET DITE. Un remplacement change le PRIX, la
    CAPACITÉ (quand c'est une batterie) et l'IDENTITÉ affichée — rien d'autre.
    La composition reste celle du moteur : mêmes rôles, mêmes quantités, même
    règle des 80 % sur l'onduleur d'origine. La compatibilité électrique du
    produit substitué n'est PAS revérifiée : une taille est une EXPLORATION,
    et le devis officiel — la seule pièce contractuelle — n'est jamais touché.

    LA CAPACITÉ SUIT LA BATTERIE. Sans cela, remplacer la batterie changeait le
    prix mais laissait la carte annoncer la capacité de l'ancienne : la banque
    affichée aurait décrit une installation qui n'existe pas, et l'étude
    horaire aurait été calculée sur cette capacité fantôme.
    """
    if not substitutions or not vue:
        return vue
    from apps.ventes.dimensionnement import capacite_utile_batterie

    roles = list(getattr(lignes, 'roles', ()) or ())
    cout_ht = cout_ttc = batterie_kwh = 0.0
    for index, ligne in enumerate(lignes):
        role = roles[index] if index < len(roles) else None
        quantite = _num(getattr(ligne, 'quantite', 0))
        remplacant = substitutions.get(role)
        if remplacant is not None:
            pu_ht = _num(getattr(remplacant, 'prix_vente', 0))
            tva = _num(getattr(remplacant, 'tva', None), defaut=-1.0)
        else:
            pu_ht = _num(getattr(ligne, 'prix_unitaire', 0))
            tva = _num(getattr(getattr(ligne, 'produit', None), 'tva', None),
                       defaut=-1.0)
        facteur = 1.0 + (tva if tva >= 0 else float(_TVA_REPLI)) / 100.0
        cout_ht += quantite * pu_ht
        cout_ttc += quantite * pu_ht * facteur
        if role == 'batterie':
            produit = remplacant if remplacant is not None else getattr(
                ligne, 'produit', None)
            nom = (getattr(produit, 'nom', '') or ''
                   if remplacant is not None
                   else getattr(ligne, 'designation', '') or '')
            # RÈGLE CAPUTIL, lue par la MÊME fonction que la composition :
            # fiche ``kwh_usable``, sinon nominal × DoD, jamais le kWh du nom
            # seul quand une fiche existe.
            kwh = _num(capacite_utile_batterie(produit, nom))
            if kwh > 0:
                batterie_kwh += kwh * quantite
    vue = dict(vue)
    vue['cout_ht'] = round(cout_ht, 2)
    vue['cout_ttc'] = round(cout_ttc, 2)
    if 'batterie' in substitutions:
        vue['batterie_kwh'] = round(batterie_kwh, 2) if batterie_kwh else 0.0
    return vue


def _carte_du_devis(contexte, data, variante):
    """La carte Recommandé — REPRISE des valeurs SERVIES, jamais recalculée.

    C'est la règle centrale de ce module. Le prix, l'économie, le payback, la
    production, le kWc et le nombre de panneaux viennent TELS QUELS de
    ``build_quote_data`` — la source que la page affiche déjà partout ailleurs.
    Aucun second calcul, aucun second arrondi : la carte « Recommandé » ne peut
    donc pas annoncer un chiffre différent de l'offre officielle juste à côté.

    Les deux taux (couverture, autoconsommation) viennent du bloc horaire DÉJÀ
    POSÉ sur le devis (``etude_params['etude_horaire']``) — le même que celui
    dont la page tire ses économies mensuelles — et sont OMIS s'il est absent.
    """
    suffixe = 'sans' if variante == 'sans' else 'avec'
    totaux = (data or {}).get('totaux_%s' % suffixe) or {}
    prix = _positif(totaux.get('ttc'))
    nb_panneaux = _positif((data or {}).get('nb_panneaux_%s' % suffixe))
    kwc = _positif((data or {}).get('puissance_kwc_%s' % suffixe))
    if nb_panneaux is None or kwc is None:
        return None

    carte = {'nb_panneaux': int(nb_panneaux), 'puissance_kwc': round(kwc, 3)}
    if prix is not None:
        carte['prix_ttc'] = round(prix, 2)
        prix_kwc = _prix_par_kwc(prix, kwc)
        if prix_kwc is not None:
            carte['prix_par_kwc_ttc'] = prix_kwc
    economie = _positif((data or {}).get(
        'eco_s_ann' if variante == 'sans' else 'eco_a_ann'))
    if economie is not None:
        carte['economie_annuelle_mad'] = round(economie, 2)
    # Le payback SERVI d'abord (``roi_s``/``roi_a``, ce que la page affiche) ;
    # il n'est recalculé QUE s'il n'a pas été servi — jamais en concurrence.
    paye = _positif((data or {}).get(
        'roi_s' if variante == 'sans' else 'roi_a'))
    if paye is None:
        paye = _payback(prix, economie)
    if paye is not None:
        carte['payback_annees'] = round(paye, 2)
    production = _positif((data or {}).get('prod_kwh_%s' % suffixe))
    if production is not None:
        carte['production_annuelle_kwh'] = round(production, 2)

    _ajouter_taux(carte, _annuel_frais(contexte.devis, kwc), suffixe)

    cumul = _cumul_servi(data, suffixe, prix)
    if cumul is not None:
        carte['economies_cumulees_25_ans_mad'] = cumul

    if variante == 'avec':
        banque = _banque_du_devis(contexte, kwc)
        if banque:
            carte['batterie'] = banque
    materiel, tout_classe = _materiel_du_devis(contexte.devis, variante)
    if materiel:
        carte['materiel'] = materiel
        familles = _familles(materiel)
        if familles:
            carte['familles'] = familles
    # Champ PRIVÉ (préfixe ``_``), retiré avant de servir : il dit seulement si
    # « ce qui change » a le droit de se prononcer contre cette référence.
    carte['_familles_fiables'] = bool(tout_classe and materiel)
    _ajouter_toit(carte, contexte, nb_panneaux)
    return carte


def _annuel_frais(devis, kwc):
    """Le bloc horaire annuel de ce devis, SEULEMENT s'il est encore À JOUR.

    LA GARDE ANTI-PÉRIMÉ (CJ2a) EST LA MÊME QUE PARTOUT AILLEURS. Le bloc
    ``etude_params['etude_horaire']`` dit pour quelle puissance il a été
    calculé ; ``pricing._lire_etude_horaire`` REFUSE de le rendre dès que le
    devis ne fait plus cette puissance (tolérance ``_HORAIRE_TOLERANCE_KWC``),
    parce que ses chiffres décrivent alors une AUTRE installation. Tous les
    autres consommateurs passent par cette garde ; lire le bloc brut, comme je
    le faisais, aurait fait afficher « couverture 61 % » à côté du prix d'un
    devis redimensionné depuis — un chiffre précis et faux, la pire espèce.

    ``{}`` quand la garde refuse : les deux taux sont alors simplement OMIS de
    la carte (règle d'omission), jamais remplacés par une estimation.
    """
    from .quote_engine.pricing import _lire_etude_horaire

    etude_params = getattr(devis, 'etude_params', None) or {}
    bloc = etude_params.get('etude_horaire')
    if not isinstance(bloc, dict):
        return {}
    try:
        if _lire_etude_horaire(bloc, kwc) is None:
            return {}
    except Exception:  # noqa: BLE001 — un doute vaut une omission
        logger.warning('fraîcheur du bloc horaire illisible', exc_info=True)
        return {}
    return bloc.get('annuel') or {}


def _banque_du_devis(contexte, kwc):
    """La banque RÉELLEMENT vendue par ce devis (jamais l'optimum du moteur).

    Le verdict de remplissage se lit avec la MÊME fonction que les deux autres
    tailles (:func:`_remplissage_ok`) : trois cartes, un seul critère.
    """
    from apps.ventes.dimensionnement import capacite_batterie_des_lignes

    capacite = _positif(capacite_batterie_des_lignes(contexte.devis))
    if capacite is None:
        return None
    banque = {'capacite_utile_kwh': round(capacite, 2)}
    remplissage = _remplissage_ok(contexte, kwc, capacite, {})
    if remplissage is not None:
        banque['remplissage_ok'] = bool(remplissage)
    modules = _compter_modules_du_devis(contexte.devis)
    if modules and contexte.module_batterie_kwh:
        banque['nb_modules'] = modules
        banque['module_kwh'] = round(float(contexte.module_batterie_kwh), 2)
    return banque


def _compter_modules_du_devis(devis):
    """Le NOMBRE de modules batterie des lignes réelles (0 = aucun)."""
    from apps.ventes.dimensionnement import _lignes_produit_du_devis
    from apps.ventes.services import _is_battery

    total = 0
    for ligne in _lignes_produit_du_devis(devis):
        if (getattr(ligne, 'variante', '') or '') == 'sans':
            continue
        if not _is_battery(getattr(ligne, 'designation', '') or ''):
            continue
        total += int(_num(getattr(ligne, 'quantite', 0)))
    return total


# ════════════════════════════════════════════════════════════════════════════
# LA DÉRIVATION COMPLÈTE
# ════════════════════════════════════════════════════════════════════════════

def deriver(devis, data):
    """Le bloc ``offres_tailles`` complet, ou ``None``. PEUT lever.

    Les appelants publics passent par :func:`offres_tailles_publique`, qui pose
    le filet. Cette fonction reste nue pour que les tests voient l'erreur.
    """
    contexte = _contexte(devis)
    if contexte is None:
        return None

    avec_servable = 'avec' in list((data or {}).get('variantes_servables') or [])
    stockees = lire_config_stockee(devis)

    nb_devis = _positif((data or {}).get('nb_panneaux_sans')) \
        or _positif((data or {}).get('nb_panneaux_avec'))
    champs = _champs_des_tailles(contexte, nb_devis)
    if 'recommande' not in champs:
        # Sans le champ du devis lui-même, il n'y a pas d'ancre : les deux
        # autres tailles n'auraient rien à quoi se comparer.
        return None

    # L'ORDRE DE DÉDUPLICATION N'EST PAS L'ORDRE D'AFFICHAGE, et la nuance est
    # LE point délicat de la convergence. Affiché, c'est Éco → Recommandé →
    # Max. Mais quand deux tailles désignent le MÊME champ, celle qui doit
    # survivre est TOUJOURS Recommandé : c'est le devis officiel, la seule
    # carte qui a le droit d'ouvrir la signature. Dédupliquer dans l'ordre
    # d'affichage aurait laissé « Éco » absorber le devis et fait disparaître
    # la carte Recommandé d'un dossier dont l'optimum EST déjà le devis — le
    # cas le plus fréquent d'un devis bien dimensionné.
    offres, champs_vus = [], {}
    for cle in ('recommande', 'eco', 'max'):
        nb_panneaux = champs.get(cle)
        entree = stockees.get(cle) or {}
        config = entree.get('config') or {}
        ajuste = bool(entree.get('ajuste'))
        if config.get('nb_panneaux'):
            nb_panneaux = int(config['nb_panneaux'])
        if not nb_panneaux:
            continue
        # CONVERGENCE — deux tailles sur le MÊME champ, sans configuration
        # ajustée qui les distinguerait, sont UNE taille. La liste collapse ;
        # elle ne se remplit jamais d'un intermédiaire fabriqué.
        signature = (nb_panneaux, _signature_config(config))
        if signature in champs_vus:
            continue
        champs_vus[signature] = cle

        # HONNÊTETÉ, ET ELLE SE DÉCIDE AVANT DE CALCULER. La bascule « avec
        # batterie » n'existe que si ce devis SERT réellement l'option
        # (``variantes_servables`` — la capacité PHYSIQUE des lignes, pas le
        # scénario déclaré) ; sinon la variante disparaît PARTOUT, CTA compris.
        # Le drapeau descend jusqu'au calcul plutôt que de filtrer après coup :
        # composer une banque puis balayer douze jours types pour JETER le
        # résultat coûtait deux passages horaires par taille sur un endpoint
        # public NON CACHÉ.
        if cle == 'recommande' and not ajuste:
            cartes = {
                'sans': _carte_du_devis(contexte, data, 'sans'),
                'avec': (_carte_du_devis(contexte, data, 'avec')
                         if avec_servable else None),
            }
        else:
            cartes = _carte_moteur(contexte, nb_panneaux, config,
                                   avec_servable=avec_servable)
        if cartes.get('sans') is None and cartes.get('avec') is None:
            continue

        offre = {
            'cle': cle,
            'titre': TITRES[cle],
            'recommande': cle == 'recommande',
            'est_le_devis': bool(cle == 'recommande' and not ajuste),
            'ajuste': ajuste,
            'config': _config_publique(cartes, contexte),
        }
        for variante in ('sans', 'avec'):
            carte = cartes.get(variante)
            if carte is not None:
                offre[variante] = carte
        if 'sans' not in offre and 'avec' not in offre:
            continue
        offres.append(offre)

    if not offres:
        return None
    # Retour à l'ORDRE D'AFFICHAGE (Éco → Recommandé → Max) après la
    # déduplication, qui, elle, priorisait le devis.
    offres.sort(key=lambda o: CLES.index(o['cle']))
    _poser_diff_familles(offres)
    _retirer_champs_prives(offres)

    horizon, escalade = _horizon_et_escalade()
    bloc = {'avec_servable': bool(avec_servable), 'offres': offres}
    if contexte.module_batterie_kwh:
        bloc['module_batterie_kwh'] = round(
            float(contexte.module_batterie_kwh), 2)
    if contexte.capacite_toit and contexte.toit_max:
        # LA CONTENANCE MESURÉE, ET ELLE SEULE. La clé s'appelle « plafond du
        # toit » : publier sous ce nom le nombre de panneaux DESSINÉS était le
        # même mensonge que celui qui effondrait la carte Max, et y publier le
        # MUR PHYSIQUE (aire ÷ empreinte, large par construction) en serait un
        # autre — ce mur sert à refuser une taille impossible, jamais à
        # annoncer au client ce que son toit tient. Sans mesure : pas de clé.
        bloc['plafond_toit_panneaux'] = int(contexte.toit_max)
    if escalade is not None:
        bloc['escalade_tarifaire_pct'] = escalade
    if horizon is not None:
        bloc['horizon_annees'] = horizon
    return bloc


def _signature_config(config):
    """Ce qui rend DEUX tailles réellement différentes à champ égal."""
    equipements = (config or {}).get('equipements') or {}
    return (
        (config or {}).get('batterie_nb_modules'),
        tuple(sorted((str(k), str(v)) for k, v in equipements.items())),
    )


def _config_publique(cartes, contexte):
    """La configuration à préremplir dans la demande de modification.

    C'est ce que le vendeur LIRA quand le client clique « Demander cette
    configuration » : le champ, la banque, le calibre. Rien de plus — ni prix,
    ni marge, ni nomenclature.
    """
    # LE CHAMP DE BASE VIENT DE « SANS », PAS DE « AVEC ». Sur un devis L-2OPT
    # dont les deux options portent des champs différents (22 sans / 26 avec),
    # prendre « avec » aurait fait dire au CTA « 26 panneaux » alors que la
    # carte affichée en dit 22 : le vendeur aurait reçu une demande que le
    # client n'a pas faite. Éco et Max, eux, portent le même champ des deux
    # côtés — la préférence n'y change rien.
    reference = cartes.get('sans') or cartes.get('avec') or {}
    config = {'nb_panneaux': int(reference.get('nb_panneaux') or 0)}
    banque = (cartes.get('avec') or {}).get('batterie') or {}
    config['batterie_nb_modules'] = int(banque.get('nb_modules') or 0)
    if config['batterie_nb_modules'] and contexte.module_batterie_kwh:
        config['batterie_module_kwh'] = round(
            float(contexte.module_batterie_kwh), 2)
    return config


def _poser_diff_familles(offres):
    """« Ce qui change » — familles seulement, et JAMAIS sur la référence.

    SE TAIT QUAND LA RÉFÉRENCE N'EST PAS SÛRE. Si une ligne du devis n'a pas pu
    être rattachée à un rôle catalogue (``_familles_fiables`` faux), la liste
    de familles de la référence est peut-être incomplète — et un « Éco ajoute :
    onduleur » calculé contre une référence trouée serait une accusation
    fausse. Mieux vaut aucune table de comparaison qu'une table qui ment.
    """
    reference = next((o for o in offres if o['cle'] == 'recommande'), None)
    if reference is None:
        return
    for offre in offres:
        if offre['cle'] == 'recommande':
            continue
        for variante in ('sans', 'avec'):
            carte = offre.get(variante)
            base_carte = reference.get(variante) or {}
            base = base_carte.get('familles')
            if carte is None or not base or not carte.get('familles'):
                continue
            if base_carte.get('_familles_fiables') is False:
                continue
            diff = _diff_familles(carte['familles'], base)
            if diff:
                carte['familles_diff'] = diff


def _retirer_champs_prives(offres):
    """Retire les champs de travail ``_*`` — ils ne sortent JAMAIS du serveur.

    Ils portent des décisions internes (la référence est-elle fiable ?), pas
    des faits sur l'installation : les servir agrandirait le contrat public
    d'un champ que personne n'a demandé et que la page devrait ignorer.
    """
    for offre in offres:
        for variante in ('sans', 'avec'):
            carte = offre.get(variante)
            if not isinstance(carte, dict):
                continue
            for cle in [c for c in carte if str(c).startswith('_')]:
                carte.pop(cle, None)


def offres_tailles_publique(devis, data, cles_servies=None):
    """Le bloc pour le payload public — best-effort, ne lève JAMAIS.

    MÊME patron que ``_echelle_paliers_batterie_publique`` : toute exception
    est journalisée et la clé DISPARAÎT du payload. Un bloc additif ne fait
    jamais tomber la page d'un client.

    Servi IDENTIQUE aux deux niveaux de partage : il ne porte que des natures
    de nombres DÉJÀ publiques ailleurs sur la page (tailles, prix TTC,
    économies, payback, couverture) — jamais un prix d'achat, jamais une marge
    (règle #4), jamais un calibre ni une nomenclature (anticopie).

    ENVOI 1/2/3 OPTIONS (fondateur, 28/08/2026). ``cles_servies`` est
    l'ensemble des tailles que CE LIEN sert (``{'eco', 'recommande', 'max'}``
    au maximum), lu par l'appelant sur ``ShareLink.sections`` — ``None``
    (défaut) = tout est servi, donc tout lien existant garde ses trois cartes.
    Le filtrage a lieu ICI, sur le bloc DÉJÀ dérivé, et jamais dans la
    dérivation : « ce qui change » (``familles_diff``) se calcule contre
    « Recommandé », et la convergence collapse en le regardant lui aussi.
    Retirer une taille en amont changerait donc les CHIFFRES des cartes
    restantes — le client verrait deux pages différentes pour un même devis
    selon ce que le vendeur a coché.

    DEUX TAILLES MINIMUM, ET LE SEUIL PORTE SUR LES CARTES SERVIES. Une
    section « Explorer d'autres tailles » qui n'en montre qu'UNE n'explore
    rien : la clé est alors ABSENTE plutôt que servie à moitié — c'est
    exactement ce que le vendeur DEMANDE quand il n'envoie qu'une option.
    L'API vendeur, elle, sert TOUT ce qui est dérivable (même une seule
    taille) — c'est un écran d'édition, pas une comparaison.
    """
    try:
        bloc = deriver(devis, data)
    except Exception:  # noqa: BLE001
        logger.warning('offres_tailles indisponible', exc_info=True)
        return None
    if not bloc:
        return None
    if cles_servies is not None:
        # « Recommandé » n'est jamais retirable : c'est LE devis (la seule
        # carte autorisée à ouvrir la signature).
        gardees = set(cles_servies) | {'recommande'}
        bloc = dict(bloc)
        bloc['offres'] = [o for o in (bloc.get('offres') or [])
                          if o.get('cle') in gardees]
    if len(bloc.get('offres') or []) < 2:
        return None
    return bloc


# ════════════════════════════════════════════════════════════════════════════
# LA CONFIGURATION STOCKÉE — les seules écritures de ce module
# ════════════════════════════════════════════════════════════════════════════

def lire_config_stockee(devis):
    """``{cle: {config, ajuste, modifie_le, modifie_par}}`` — jamais ``None``.

    Une forme illisible (un devis dont le champ a été édité à la main) est
    traitée comme VIDE : la dérivation moteur reprend la main, jamais une
    demi-configuration appliquée.
    """
    brut = getattr(devis, 'offres_tailles_config', None)
    if not isinstance(brut, dict):
        return {}
    propre = {}
    for cle in CLES:
        entree = brut.get(cle)
        if isinstance(entree, dict) and isinstance(entree.get('config'), dict):
            propre[cle] = entree
    return propre


def enregistrer_config(devis, cle, config, *, utilisateur=None):
    """Écrit la configuration d'UNE taille et la marque « ajustée ».

    LES DEUX AUTRES TAILLES SONT INTOUCHÉES, bit à bit — leur configuration
    comme leur marqueur. C'est l'indépendance par taille que l'écran vendeur
    promet, garantie ici plutôt qu'espérée côté écran.

    AUCUNE ligne, AUCUN total, AUCUN statut du devis n'est touché (règle #4) :
    seul ``offres_tailles_config`` est écrit.
    """
    if cle not in CLES:
        raise ValueError('taille inconnue : %s' % cle)
    stockees = dict(lire_config_stockee(devis))
    stockees[cle] = {
        'config': dict(config or {}),
        'ajuste': True,
        'modifie_le': timezone.now().isoformat(),
        'modifie_par': getattr(utilisateur, 'pk', None),
    }
    _ecrire_colonne(devis, stockees)
    return stockees


def regenerer_taille(devis, cle):
    """Efface la configuration d'UNE taille — le moteur la redérive.

    Les deux autres restent intouchées, marqueur ``ajuste`` compris. C'est
    l'équivalent honnête du « Régénérer depuis le moteur » par taille : on ne
    remplace pas une configuration par une autre, on RETIRE celle du vendeur
    pour que la dérivation reprenne la main.
    """
    if cle not in CLES:
        raise ValueError('taille inconnue : %s' % cle)
    stockees = dict(lire_config_stockee(devis))
    if cle not in stockees:
        return stockees
    stockees.pop(cle, None)
    _ecrire_colonne(devis, stockees or None)
    return stockees


def _ecrire_colonne(devis, valeur):
    """Écrit ``offres_tailles_config`` — CETTE COLONNE, ET RIEN D'AUTRE.

    POURQUOI PAS ``devis.save(update_fields=…)``. ``Devis.save`` porte deux
    effets de bord légitimes pour une vraie modification de devis, mais faux
    pour une exploration :

    * SCA47 — il DÉRIVE ET GÈLE ``prix_par_kwc`` (write-once) dès qu'un kWc et
      un total existent. Enregistrer une taille aurait donc pu figer, au
      passage, une colonne interne que rien dans ce geste ne concerne ;
    * VX98 — ``updated_at`` (``auto_now``) aurait avancé, et la page aurait
      affiché « modifié il y a N minutes » sur un devis dont AUCUNE ligne,
      AUCUN total et AUCUN statut n'a bougé.

    Un ``UPDATE`` d'une seule colonne rend donc VRAIE la promesse de ce module
    (règle #4 : une taille est une exploration, le devis officiel ne bouge
    pas) au lieu de se contenter de la déclarer. L'instance en mémoire est
    resynchronisée pour que l'appelant relise ce qu'il vient d'écrire.
    """
    type(devis).objects.filter(pk=devis.pk).update(
        offres_tailles_config=valeur)
    devis.offres_tailles_config = valeur
