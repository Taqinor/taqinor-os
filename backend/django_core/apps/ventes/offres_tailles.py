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
* **Max** = la plus grande taille admissible : le PLAFOND DU TOIT quand le
  devis porte un calepinage (:func:`~apps.ventes.dimensionnement.
  plafond_toit_du_devis`), sinon la dernière taille éligible du balayage — qui
  porte déjà ses propres bornes (facteur falaise, ``MAX_PANNEAUX_BALAYAGE``).
  Jamais un panneau au-delà d'une borne physique.

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


def _materiel_de_composition(lignes, roles):
    """``[{role, famille, marque, modele, garantie_ans}]`` pour les 3 familles.

    Chaque champ est OMIS quand il n'existe pas réellement : un produit sans
    marque renseignée n'invente pas de marque, un produit sans fiche de
    garantie n'affiche pas de garantie. Le ``modele`` est la DÉSIGNATION
    catalogue de la ligne — c'est le nom que le client lit sur son devis.
    """
    materiel, deja_vues = [], set()
    for index, ligne in enumerate(lignes or []):
        role = roles[index] if index < len(roles or ()) else None
        famille = _FAMILLES.get(role)
        if famille not in _FAMILLES_MATERIEL or famille in deja_vues:
            continue
        deja_vues.add(famille)
        produit = getattr(ligne, 'produit', None)
        entree = {'role': role, 'famille': famille}
        marque = (getattr(produit, 'marque', '') or '').strip()
        if marque:
            entree['marque'] = marque
        modele = (getattr(ligne, 'designation', '') or '').strip()
        if modele:
            entree['modele'] = modele
        garantie = _garantie_ans(produit)
        if garantie is not None:
            entree['garantie_ans'] = garantie
        materiel.append(entree)
    materiel.sort(key=lambda e: _ORDRE_MATERIEL.get(e['famille'], 9))
    return materiel


def _materiel_du_devis(devis):
    """Le même bloc, lu sur les LIGNES RÉELLES du devis (carte Recommandé).

    La carte Recommandé ne recompose rien : elle lit ce que le client achète.
    Les lignes réservées à l'option SANS batterie (L-2OPT) sont exclues du
    relevé batterie par construction (elles n'en portent pas).
    """
    from apps.ventes.dimensionnement import _lignes_produit_du_devis
    from apps.ventes.services import (
        _is_battery, _is_hybrid_inverter, _is_panel, _is_reseau_inverter)

    detecteurs = (
        ('panneau', 'panneau', _is_panel),
        ('onduleur', 'onduleur_hybride', _is_hybrid_inverter),
        ('onduleur', 'onduleur_reseau', _is_reseau_inverter),
        ('batterie', 'batterie', _is_battery),
    )
    materiel, deja_vues = [], set()
    for ligne in _lignes_produit_du_devis(devis):
        designation = (getattr(ligne, 'designation', '') or '').strip()
        if not designation:
            continue
        for famille, role, detecteur in detecteurs:
            if famille in deja_vues:
                continue
            try:
                reconnu = bool(detecteur(designation))
            except Exception:  # noqa: BLE001 — un libellé exotique n'est pas
                # une panne : il n'est simplement pas reconnu.
                reconnu = False
            if not reconnu:
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
            break
    materiel.sort(key=lambda e: _ORDRE_MATERIEL.get(e['famille'], 9))
    return materiel


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

def _cumul_25_ans(prix_ttc, economie_annuelle, *, avec_batterie):
    """Les économies CUMULÉES sur l'horizon, ou ``None``.

    Source unique : ``quote_engine.pricing.compute_cashflow_payback`` — la
    fonction qui porte DÉJÀ la dégradation des panneaux, le rendement
    aller-retour de la batterie et la provision de remplacement d'onduleur.
    ``TARIFF_ESCALATION`` y vaut ``0`` et n'est PAS touché ici : la projection
    est à tarif PLAT, et la page sert le drapeau
    ``escalade_tarifaire_pct`` pour pouvoir imprimer « aucune hausse tarifaire
    supposée » AU-DESSUS du chiffre au lieu de laisser croire à une projection
    optimiste.

    ``None`` dès qu'une entrée manque — jamais une projection sur un prix ou
    une économie inventés.
    """
    if not prix_ttc or not economie_annuelle:
        return None
    try:
        from .quote_engine.pricing import compute_cashflow_payback
        resultat = compute_cashflow_payback(
            float(prix_ttc), float(economie_annuelle),
            battery=bool(avec_batterie))
    except Exception:  # noqa: BLE001 — un cumul indisponible s'omet
        logger.warning('cumul 25 ans indisponible', exc_info=True)
        return None
    flux = (resultat or {}).get('cashflow') or []
    if not flux:
        return None
    # LE CUMUL DES ÉCONOMIES (ce que le client encaisse sur l'horizon), pas le
    # gain NET : le prix de l'installation est affiché juste au-dessus sur la
    # MÊME carte, le soustraire une seconde fois dans le même bloc serait
    # illisible. On somme donc les flux annuels — jamais ``cumulative[-1]``,
    # qui part de ``-investissement`` et demanderait de ré-ajouter le prix
    # (une soustraction puis une addition = deux occasions de se tromper).
    return round(sum(_num(annee) for annee in flux), 2)


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
        from apps.ventes.dimensionnement import (
            facteur_remise_du_devis, module_batterie_du_devis,
            plafond_toit_du_devis)
        self.module_batterie_kwh = module_batterie_du_devis(devis)
        self.facteur_remise = facteur_remise_du_devis(devis)
        self.plafond_toit = plafond_toit_du_devis(devis)

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

    # MAX — la plus grande taille éligible, bornée par le TOIT quand le devis
    # porte un calepinage. Le balayage porte déjà ses propres bornes (facteur
    # falaise + ``MAX_PANNEAUX_BALAYAGE``) : on ne les repousse pas, on les lit.
    admissibles = [int(x['panneaux']) for x in eligibles
                   if _num(x.get('panneaux')) > 0]
    if contexte.plafond_toit:
        admissibles = [n for n in admissibles if n <= int(contexte.plafond_toit)]
    if admissibles:
        champs['max'] = max(admissibles)
    return champs


# ════════════════════════════════════════════════════════════════════════════
# UNE CARTE — dérivée du moteur (Éco / Max) ou REPRISE du devis (Recommandé)
# ════════════════════════════════════════════════════════════════════════════

def _carte_moteur(contexte, nb_panneaux, config=None):
    """Les deux variantes d'une taille, composées et chiffrées par le moteur.

    UN SEUL passage horaire pour les DEUX variantes : ``calculer_etude_horaire``
    rend ``economie_sans_mad`` ET ``economie_avec_mad``, les deux couvertures et
    les deux taux d'autoconsommation sur la MÊME intégration — deux appels
    séparés pourraient diverger d'un arrondi.

    Renvoie ``{'sans': carte|None, 'avec': carte|None}``.
    """
    from apps.ventes.dimensionnement import _compter_modules_batterie
    from apps.ventes.dimensionnement import _lire_composition
    from apps.ventes.etude_horaire import (
        calculer_etude_horaire, puissances_batterie_des_lignes)

    kwc = round(nb_panneaux * contexte.panel_watt / 1000.0, 3)
    equipements = (config or {}).get('equipements') or {}

    cible = None
    modules_demandes = (config or {}).get('batterie_nb_modules')
    if modules_demandes and contexte.module_batterie_kwh:
        cible = float(modules_demandes) * float(contexte.module_batterie_kwh)

    lignes_sans = contexte.composer(nb_panneaux, avec_batterie=False)
    lignes_avec = contexte.composer(nb_panneaux, avec_batterie=True,
                                    cible_kwh=cible)
    if lignes_sans is None and lignes_avec is None:
        return {'sans': None, 'avec': None}

    vue_sans = _substituer(_lire_composition(lignes_sans, _TVA_REPLI),
                           lignes_sans, equipements) if lignes_sans else None
    vue_avec = _substituer(_lire_composition(lignes_avec, _TVA_REPLI),
                           lignes_avec, equipements) if lignes_avec else None

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
        cumul = _cumul_25_ans(prix, economie,
                              avec_batterie=(variante == 'avec'))
        if cumul is not None:
            carte['economies_cumulees_25_ans_mad'] = cumul
        if variante == 'avec':
            banque = _banque(contexte, vue, capacite,
                             _compter_modules_batterie(vue.get('lignes')))
            if banque:
                carte['batterie'] = banque
        roles = list(getattr(lignes, 'roles', ()) or ())
        materiel = _materiel_de_composition(lignes, roles)
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
    """``toit_ok`` — SEULEMENT quand un calepinage réel existe.

    Sans calepinage, le devis ne sait pas ce que ce toit accepte : le champ est
    OMIS. Jamais un « ça rentre » supposé sur une surface que personne n'a
    mesurée.
    """
    if not contexte.plafond_toit:
        return
    carte['toit_ok'] = bool(int(nb_panneaux) <= int(contexte.plafond_toit))


def _banque(contexte, vue, capacite, compteurs):
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


def _substituer(vue, lignes, equipements):
    """Applique les remplacements de produits demandés par le vendeur.

    PORTÉE VOLONTAIREMENT ÉTROITE. Remplacer un produit change son PRIX et son
    IDENTITÉ (marque/modèle/garantie) dans cette taille — rien d'autre. La
    composition reste celle du moteur (mêmes quantités, mêmes rôles), et le
    devis officiel n'est JAMAIS touché : une taille est une exploration.

    Un identifiant introuvable est IGNORÉ (la taille garde le produit du
    moteur) plutôt que de faire disparaître la carte : le sérialiseur, lui,
    a déjà refusé en 400 tout identifiant hors société.
    """
    if not equipements or not vue:
        return vue
    from apps.stock.models import Produit

    # LA GARDE DE SOCIÉTÉ VIT DANS LE SÉRIALISEUR, pas ici : il a déjà refusé
    # en 400 tout identifiant hors de la société du devis, et c'est LÀ que la
    # frontière multi-société doit se tenir (une garde recopiée ici finirait
    # par diverger). Ce filtre-ci ne fait que retrouver le produit.
    par_role = {}
    for role, produit_id in (equipements or {}).items():
        try:
            produit = Produit.objects.filter(pk=int(produit_id)).first()
        except (TypeError, ValueError):
            continue
        if produit is not None:
            par_role[role] = produit
    if not par_role:
        return vue

    roles = list(getattr(lignes, 'roles', ()) or ())
    cout_ttc = 0.0
    cout_ht = 0.0
    for index, ligne in enumerate(lignes):
        role = roles[index] if index < len(roles) else None
        quantite = _num(getattr(ligne, 'quantite', 0))
        remplacant = par_role.get(role)
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
    vue = dict(vue)
    vue['cout_ht'] = round(cout_ht, 2)
    vue['cout_ttc'] = round(cout_ttc, 2)
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

    etude_params = getattr(contexte.devis, 'etude_params', None) or {}
    annuel = ((etude_params.get('etude_horaire') or {}).get('annuel')
              if isinstance(etude_params.get('etude_horaire'), dict) else None)
    _ajouter_taux(carte, annuel or {}, suffixe)

    cumul = _cumul_25_ans(prix, economie, avec_batterie=(variante == 'avec'))
    if cumul is not None:
        carte['economies_cumulees_25_ans_mad'] = cumul

    if variante == 'avec':
        banque = _banque_du_devis(contexte)
        if banque:
            carte['batterie'] = banque
    materiel = _materiel_du_devis(contexte.devis)
    if materiel:
        carte['materiel'] = materiel
        familles = _familles(materiel)
        if variante == 'sans':
            familles = [f for f in familles if f != 'batterie']
        if familles:
            carte['familles'] = familles
    _ajouter_toit(carte, contexte, nb_panneaux)
    return carte


def _banque_du_devis(contexte):
    """La banque RÉELLEMENT vendue par ce devis (jamais l'optimum du moteur)."""
    from apps.ventes.dimensionnement import capacite_batterie_des_lignes

    capacite = _positif(capacite_batterie_des_lignes(contexte.devis))
    if capacite is None:
        return None
    banque = {'capacite_utile_kwh': round(capacite, 2)}
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

        if cle == 'recommande' and not ajuste:
            cartes = {'sans': _carte_du_devis(contexte, data, 'sans'),
                      'avec': _carte_du_devis(contexte, data, 'avec')}
        else:
            cartes = _carte_moteur(contexte, nb_panneaux, config)
        if cartes.get('sans') is None and cartes.get('avec') is None:
            continue

        if not avec_servable:
            # HONNÊTETÉ : la bascule « avec batterie » n'existe que si ce devis
            # SERT réellement l'option (``variantes_servables`` — la capacité
            # PHYSIQUE des lignes, pas le scénario déclaré). Sinon la variante
            # disparaît PARTOUT, y compris de la configuration préremplie du
            # CTA : proposer une banque sur un devis qui ne peut pas la servir
            # serait une promesse que la composition ne tient pas.
            cartes['avec'] = None

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

    horizon, escalade = _horizon_et_escalade()
    bloc = {'avec_servable': bool(avec_servable), 'offres': offres}
    if contexte.module_batterie_kwh:
        bloc['module_batterie_kwh'] = round(
            float(contexte.module_batterie_kwh), 2)
    if contexte.plafond_toit:
        bloc['plafond_toit_panneaux'] = int(contexte.plafond_toit)
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
    reference = cartes.get('avec') or cartes.get('sans') or {}
    config = {'nb_panneaux': int(reference.get('nb_panneaux') or 0)}
    banque = (cartes.get('avec') or {}).get('batterie') or {}
    config['batterie_nb_modules'] = int(banque.get('nb_modules') or 0)
    if config['batterie_nb_modules'] and contexte.module_batterie_kwh:
        config['batterie_module_kwh'] = round(
            float(contexte.module_batterie_kwh), 2)
    return config


def _poser_diff_familles(offres):
    """« Ce qui change » — familles seulement, et JAMAIS sur la référence."""
    reference = next((o for o in offres if o['cle'] == 'recommande'), None)
    if reference is None:
        return
    for offre in offres:
        if offre['cle'] == 'recommande':
            continue
        for variante in ('sans', 'avec'):
            carte = offre.get(variante)
            base = (reference.get(variante) or {}).get('familles')
            if carte is None or not base or not carte.get('familles'):
                continue
            diff = _diff_familles(carte['familles'], base)
            if diff:
                carte['familles_diff'] = diff


def offres_tailles_publique(devis, data):
    """Le bloc pour le payload public — best-effort, ne lève JAMAIS.

    MÊME patron que ``_echelle_paliers_batterie_publique`` : toute exception
    est journalisée et la clé DISPARAÎT du payload. Un bloc additif ne fait
    jamais tomber la page d'un client.

    Servi IDENTIQUE aux deux niveaux de partage : il ne porte que des natures
    de nombres DÉJÀ publiques ailleurs sur la page (tailles, prix TTC,
    économies, payback, couverture) — jamais un prix d'achat, jamais une marge
    (règle #4), jamais un calibre ni une nomenclature (anticopie).

    DEUX TAILLES MINIMUM. Une section « Explorer d'autres tailles » qui n'en
    montre qu'UNE n'explore rien : la clé est alors ABSENTE plutôt que servie
    à moitié. L'API vendeur, elle, sert TOUT ce qui est dérivable (même une
    seule taille) — c'est un écran d'édition, pas une comparaison.
    """
    try:
        bloc = deriver(devis, data)
    except Exception:  # noqa: BLE001
        logger.warning('offres_tailles indisponible', exc_info=True)
        return None
    if not bloc or len(bloc.get('offres') or []) < 2:
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
    devis.offres_tailles_config = stockees
    devis.save(update_fields=['offres_tailles_config'])
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
    devis.offres_tailles_config = stockees or None
    devis.save(update_fields=['offres_tailles_config'])
    return stockees
