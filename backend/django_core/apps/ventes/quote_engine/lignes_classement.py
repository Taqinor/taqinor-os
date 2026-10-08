"""SPL162 — helpers de CLASSEMENT de ligne du moteur de devis (move only).

Déplacés tels quels de ``quote_engine/builder.py`` (rejeu r4/qe/b3 : 17
touches depuis le 15/08) : lecteurs de puissance panneau (fiche technique puis
désignation), de marque et de capacité batterie, prédicats de classification
(alias de ``solar_classification``, la table backend unique — QJR78),
adaptateur ``_LigneArgentPdf`` du noyau monétaire, ``_line_to_item`` et les
lecteurs du nombre de panneaux. C'est aussi le CASSE-CYCLE de SPL163/SPL164 :
ce module n'importe JAMAIS ``builder`` ; ``_item_classement``/``_item_marque``
gardent leurs imports ``utils.options`` LOCAUX (``utils/options.py`` importe
ces prédicats au niveau module). Les helpers de COMPOSITION restent dans
``builder`` (``_variante_de_ligne``, ``_repartir_options``…).

Rendu seulement (règle #4) : aucun statut, aucun chemin PDF client nouveau.
"""
from __future__ import annotations

import re
from decimal import Decimal

from apps.ventes import solar_classification as _sc

_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)


# Repli SÛR quand une ligne panneau n'a aucune puissance lisible dans sa
# désignation ni dans le nom du produit lié : on prend le STANDARD du catalogue
# (710 W — « Panneau Canadien Solar 710W »/« Panneau Jinko 710W », cf.
# seed_catalogue + generate_devis_premium.watt_par_panneau), JAMAIS l'ancien 450
# obsolète. Le chemin normal lit la VRAIE puissance sur la fiche technique du
# produit (PV11, _fiche_watt) puis, à défaut, via _parse_watt(nom produit).
_DEFAULT_WATT = 710


# Brand tokens from the simulator catalogue — longest/most specific first so
# 'Deyness'/'Dyness' win over the substring 'Deye'.
# TOLÉRANCE HISTORIQUE : la marque de batteries s'écrit « Dyness » (correction
# fondateur 2026-08-18) mais les désignations FIGÉES des devis déjà émis disent
# « Deyness ». Les deux jetons restent reconnus — un vieux devis doit continuer
# d'afficher sa marque —, le premier de la liste étant l'orthographe correcte.
_BRAND_TOKENS = [
    "Canadien Solar", "Canadian Solar", "Dyness", "Deyness", "Jinko",
    "Huawei", "Deye", "Lithium", "Gel",
]


def _parse_marque(*texts) -> str:
    """Extract the product brand from designation/product name (one-page badge)."""
    blob = " ".join(t for t in texts if t).lower()
    for brand in _BRAND_TOKENS:
        if brand.lower() in blob:
            return brand
    return ""


def _parse_watt(*texts) -> int | None:
    """Pull a panel wattage (e.g. '450W', '550 Wc') from any of the given strings."""
    for t in texts:
        if not t:
            continue
        m = _WATT_RE.search(str(t))
        if m:
            return int(m.group(1))
    return None


# PV11 — types de fiche technique dont le Pmax décrit bien un MODULE : les
# fiches historiques (antérieures à PV5) ont un ``type_fiche`` vide et portent
# déjà un ``pmax_wc`` de panneau ; une fiche onduleur/batterie n'en décrit pas un.
_WATT_FICHE_TYPES = ("", "module")


def _fiche_watt(produit) -> int | None:
    """PV11 — puissance panneau LUE SUR LA FICHE TECHNIQUE (Pmax Wc réel).

    La fiche constructeur (``stock.FicheTechnique``, OneToOne ``fiche_technique``)
    porte la VRAIE puissance du module ; elle prime donc sur la regex de
    désignation, qui reste le repli. Accès identique à celui déjà pratiqué ici
    pour ``marque``/``description``/``garantie`` (attributs du produit lié, via
    ``getattr`` gardés) — aucun import ni requête supplémentaire.

    Renvoie ``None`` (→ repli regex, comportement inchangé) dès que la valeur
    n'est pas exploitable : produit absent, pas de fiche, fiche onduleur ou
    batterie, ``pmax_wc`` nul, négatif ou illisible.
    """
    fiche = getattr(produit, "fiche_technique", None)
    if fiche is None:
        return None
    if (getattr(fiche, "type_fiche", "") or "") not in _WATT_FICHE_TYPES:
        return None
    pmax = getattr(fiche, "pmax_wc", None)
    if pmax is None:
        return None
    try:
        watt = int(round(float(pmax)))
    except (TypeError, ValueError):
        return None
    return watt if watt > 0 else None


# QJR78 — LA CLASSIFICATION PRODUIT N'A PLUS QU'UNE TABLE BACKEND. Elle vit
# dans ``apps/ventes/solar_design.py`` ; ce module l'IMPORTE au lieu d'en garder
# une copie. C'est la copie qui avait divergé : le 19/08/2026 la détection
# panneau a été élargie ICI seulement, laissant `solar_design` et l'ex-
# `services.py` à la version étroite — un « Module PV 550 W » était panneau pour
# le PDF et pas pour l'écran. Les alias ci-dessous gardent les noms locaux, donc
# aucun appelant de ce fichier ne change.
_is_battery = _sc.is_battery


# Capacité batterie lisible sur une désignation (« Batterie 5 kWh », « 10kwh »).
# Même expression que ``solar.js KWH_RE`` — la parité des deux lecteurs est
# VÉRIFIÉE par la fixture de contrat
# ``apps/ventes/contract_samples/classification_lignes.json`` (QJR2) et le test
# de parité QJR91, jamais par cette phrase.
_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kwh\b", re.IGNORECASE)


# QJR609 — UN lecteur de kWh : celui du catalogue (``domain.catalogue``), même
# expression ; la copie locale a été supprimée.
from apps.ventes.domain.catalogue import _parse_kwh  # noqa: E402


def _battery_kwh_from_items(rows, blob=None) -> float:
    """Capacité batterie TOTALE (kWh) d'une liste d'items : Σ quantité × kWh
    LUS sur la désignation.

    QJR92b (29/08/2026) — RÈGLE FONDATEUR « zéro chiffre inventé ». Une ligne
    batterie dont la désignation ne porte AUCUN kWh lisible (« Batterie Deye
    BOS-B-Pack ») contribuait un défaut fabriqué de 5,0 kWh, publié tel quel
    sur le PDF client : un nombre qu'aucune donnée ne soutient. Elle contribue
    désormais 0 — la capacité SOUS-ESTIME au lieu d'inventer, et les deux
    appelants (``or None``) rendent alors ``None``, donc le document OMET la
    valeur au lieu d'en afficher une fausse. C'est la règle BAT5DEF que
    ``solar.js batteryKwhFromLines`` applique depuis le 26/08 ; la parité des
    deux lecteurs est VÉRIFIÉE par
    ``apps/ventes/contract_samples/classification_lignes.json`` (QJR2) et le
    test de parité QJR91.
    """
    total = 0.0
    for it in rows or []:
        text = blob(it) if blob else (it.get("designation") or "")
        if not _is_battery(text):
            continue
        try:
            qty = float(it.get("quantite") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            continue
        total += qty * (_parse_kwh(text) or 0.0)
    return total


def _cout_onduleur(rows, blob=None):
    """Q1 — prix TTC RÉEL des lignes onduleur d'une option, ou ``None``.

    Décision fondateur du 20/08/2026 : la provision de remplacement de
    l'onduleur (année 12, principe mi-vie IEA PVPS) vaut le PRIX FACTURÉ de
    l'onduleur de ce devis — plus un pourcentage du CAPEX, qui ne correspondait
    au prix d'aucun onduleur réel. Aucune ligne onduleur identifiable ⇒ ``None``
    ⇒ aucune provision, et l'hypothèse affichée le dit.
    """
    total = 0.0
    for it in rows or []:
        text = blob(it) if blob else (it.get("designation") or "")
        if not _is_inverter(text):
            continue
        try:
            qty = float(it.get("quantite") or 0)
            pu = float(it.get("prix_unit_ttc") or 0)
        except (TypeError, ValueError):
            continue
        if qty > 0 and pu > 0:
            total += qty * pu
    return round(total, 2) if total > 0 else None


class _LigneArgentPdf:
    """QJR53 — UNE ligne d'items du PDF, vue par le NOYAU monétaire.

    ``domain.argent`` (donc ``selectors._canonical_totaux``) lit deux
    attributs sur une ligne : ``total_ht`` et ``taux_tva_effectif``. Les
    « lignes » du moteur PDF sont des dicts (``quantite`` × ``prix_unit_ht``,
    déjà nets de la remise de LIGNE) : cet adaptateur les présente sous la
    forme attendue, sans copier une seule règle de calcul.

    Il ne porte NI ``optionnelle`` NI ``type_ligne`` : le noyau les lit par
    ``getattr(..., défaut)`` et compte donc chaque ligne fournie — c'est
    exactement ce que le moteur veut, ses ``rows`` étant DÉJÀ la population
    qu'il a décidé d'imprimer.
    """

    __slots__ = ("total_ht", "taux_tva_effectif")

    def __init__(self, row, taux_defaut):
        from decimal import Decimal as _D
        self.total_ht = (_D(str(row.get("quantite") or 0))
                         * _D(str(row.get("prix_unit_ht") or 0)))
        self.taux_tva_effectif = _D(str(row.get("taux_tva", taux_defaut)))


_is_hybrid_inverter = _sc.is_hybrid_inverter


_is_reseau_inverter = _sc.is_reseau_inverter


# QJR-OFFGRID — la TROISIÈME famille d'onduleur (autonome / site isolé).
_is_offgrid_inverter = _sc.is_offgrid_inverter


# ── M2 — DÉTECTION PANNEAU ÉLARGIE (audit adversarial du 19/08/2026) ─────────
# Le seul mot « panneau » laissait passer les désignations que les vendeurs
# écrivent vraiment (« Module PV 550 W », « Canadian Solar TOPHiKu7 710 Wc ») :
# le devis n'avait alors AUCUNE ligne panneau à ses yeux, et l'ancien repli
# fabriquait un kWc depuis le prix. Élargir la détection, c'est supprimer la
# cause la plus fréquente de cette invention. Les marques ne suffisent JAMAIS
# seules — Canadian Solar, Huawei et consorts vendent aussi des onduleurs.
#
# QJR78 — CE JEU DE MOTS-CLÉS EST DÉSORMAIS CELUI DE ``solar_design`` : il y a
# été DÉPLACÉ tel quel (mêmes qualifiants, mêmes marques, mêmes exclusions,
# même ordre), et les trois lecteurs backend l'importent de là. Le PDF ne perd
# donc rien de l'élargissement du 19/08 ; l'écran, lui, le gagne.
_PANEL_MODULE_QUALIFIERS = _sc._PANEL_MODULE_QUALIFIERS


_PANEL_BRANDS = _sc._PANEL_BRANDS


_is_panel = _sc.is_panel


_is_inverter = _sc.is_inverter


_is_smart_meter = _sc.is_smart_meter


_is_wifi_dongle = _sc.is_wifi_dongle


# QJR301 — LES DEUX SEULS ADAPTATEURS D'ITEM (dicts) de la convention de texte
# du noyau. Le texte lui-même est déclaré UNE fois, dans
# ``apps.ventes.utils.options`` (``texte_classement`` / ``texte_marque``) ; il
# n'y a plus de copie ici. Import fonction-local : ``utils.options`` importe ce
# module à son sommet (cycle).
def _item_classement(it) -> str:
    """Texte de CLASSEMENT d'un item — désignation + nom du produit lié.

    QJR301 — c'était la désignation SEULE : un mot-clé qui ne vit que dans le
    NOM du produit était vu par le noyau et PAS par les paniers du PDF, donc
    les deux moitiés classaient la même ligne différemment.
    """
    from apps.ventes.utils.options import texte_classement
    return texte_classement(it.get("designation", ""),
                            it.get("_produit_nom", ""))


def _item_marque(it) -> str:
    """Texte de MARQUE d'un item : désignation + marque + nom du produit lié."""
    from apps.ventes.utils.options import texte_marque
    return texte_marque(it.get("designation", ""), it.get("marque", ""),
                        it.get("_produit_nom", ""))


def _line_to_item(ligne, taux_tva: Decimal) -> dict:
    """Convert an OS LigneDevis (HT prices) into a premium item dict.

    Carries both HT and TTC unit prices (the PDFs show per-line HT with an
    HT → TVA → TTC totals block) plus the product's commercial sheet
    (brand, description lines, warranty) for rich rendering.

    Réforme TVA : le taux de la LIGNE prime quand il existe (10 % panneaux,
    20 % le reste) ; une ligne historique (taux NULL) garde le taux du devis —
    son rendu ne change pas d'un centime.
    """
    ligne_taux = getattr(ligne, "taux_tva", None)
    if ligne_taux is None:
        ligne_taux = taux_tva
    # AMOT12 (C-AMOT-007) — même tolérance que le noyau monnaie : une ligne
    # produit SANS prix ou SANS quantité (``null=True`` au modèle) vaut 0 et
    # est DITE par ``avertissements_internes`` (``lignes_sans_montant``) —
    # jamais un 500 au rendu.
    _prix = ligne.prix_unitaire if ligne.prix_unitaire is not None else 0
    _remise = getattr(ligne, "remise", None) or 0
    pu_ht = Decimal(_prix) * (Decimal(1) - Decimal(_remise) / Decimal(100))
    pu_ttc = pu_ht * (Decimal(1) + Decimal(ligne_taux) / Decimal(100))
    produit = getattr(ligne, "produit", None)
    produit_nom = getattr(produit, "nom", "") or ""
    return {
        "designation": ligne.designation,
        "marque": (getattr(produit, "marque", "") or ""),
        "description": (getattr(produit, "description", "") or ""),
        "garantie": (getattr(produit, "garantie", "") or ""),
        # GAMMES (fondateur 2026-08-18) — durées STRUCTURÉES du catalogue : la
        # bande « Nos garanties » du PDF les dérive de la composition réelle
        # (theme.warranties_for) au lieu d'une constante unique, pour qu'une
        # gamme d'une autre marque affiche SES vraies garanties. None quand le
        # produit ne les renseigne pas → repli sur la constante, jamais un
        # chiffre inventé.
        "garantie_mois": getattr(produit, "garantie_mois", None),
        "garantie_production_mois": getattr(
            produit, "garantie_production_mois", None),
        "quantite": float(ligne.quantite or 0),
        # QJR410 (b) / S8-F8 — LE PRIX UNITAIRE REMISÉ N'EST PLUS ARRONDI
        # AVANT D'ÊTRE MULTIPLIÉ. Il l'était à 2 décimales ici, et
        # ``_LigneArgentPdf`` alimentait ensuite le noyau monnaie
        # (``domain.argent.totaux``) avec ce PU DÉJÀ arrondi, là où
        # ``Devis.total_ht`` appelle LE MÊME ``totaux()`` sur les lignes
        # BRUTES : même fonction, deux entrées — sur toute ligne remisée de
        # quantité > 1 les deux totaux dérivaient. L'ARRONDI EST UN FAIT
        # D'AFFICHAGE : les gabarits formatent déjà ce nombre à 2 décimales
        # (``residential/options.fmt``), et le total de ligne imprimé
        # (``prix_unit_ht × quantite``) devient du même coup celui que le
        # devis facture. Une ligne non remisée à prix rond est byte-identique.
        "prix_unit_ht": float(pu_ht),
        "prix_unit_ttc": float(round(pu_ttc, 2)),
        "taux_tva": float(ligne_taux),
        # XSAL14 — position d'affichage (0 par défaut) : sert à intercaler les
        # intertitres de section/notes au bon endroit dans la liste une-page.
        "ordre": getattr(ligne, "ordre", 0) or 0,
        # STKCAT23 — LE RÔLE STOCKÉ DE LA LIGNE, transporté tel quel. Le moteur
        # ne fait que le LIRE (règle #4 : il rend, il ne décide de rien) ; la
        # table d'icônes le consulte AVANT ses mots-clés. ``None`` sur toute
        # ligne historique ⇒ mots-clés, rendu inchangé.
        "role_devis": getattr(ligne, "role_devis", None) or None,
        # AGR304 — rôle POMPAGE et courbe constructeur COPIÉS du produit
        # (contrat stock ``produit_pompage.json`` › ``item_ligne_devis_rendu``,
        # AGR7) : ``agricole/synthese`` lit la ligne pompe et sa courbe sur
        # l'item, sans relire le catalogue ni reclasser par le nom. ``None``
        # quand le produit ne les porte pas (résidentiel, pompe sans courbe).
        "role_pompage": (getattr(produit, "role_pompage", None) or None),
        "courbe_pompe": (getattr(produit, "courbe_pompe", None) or None),
        "_produit_nom": produit_nom,
    }


def puissance_panneaux_lignes(lignes) -> tuple[int, int]:
    """``(nb_panneaux, watt)`` dérivés des lignes PANNEAU parmi ``lignes``.

    PVUNI (fondateur, 18/08/2026) — extrait de ``build_quote_data`` (la boucle
    « Derive power from the panel line(s) ») en fonction RÉUTILISABLE : la
    puissance SERVIE (page/PDF, via ``build_quote_data``) et celle des KPI
    internes (``reports.py`` « conçu vs vendu », ARC40) doivent juger le MÊME
    devis avec l'EXACTE même règle — une seconde dérivation qui diverge est
    précisément le défaut de l'incident DEV-202608-0007 (deux nombres de
    panneaux, deux coûts, dans le même document). ``lignes`` est la liste DÉJÀ
    filtrée (lignes produit non optionnelles, ``LigneDevis.compte_dans_totaux``)
    que l'appelant possède ; aucune requête n'est faite ici.

    ``watt`` retombe sur ``_DEFAULT_WATT`` (710 W) quand aucune ligne panneau
    n'est exploitable. CE REPLI NE SORT JAMAIS SUR UN DOCUMENT CLIENT : depuis
    M3 (audit du 19/08/2026) le moteur de devis lit ``panneaux_et_watt_lu``,
    qui rend ``None`` au lieu du défaut. Ce contrat-ci reste inchangé pour le
    KPI INTERNE « conçu vs vendu » (``apps/ventes/reports.py``), qui a besoin
    d'un ordre de grandeur et n'imprime rien au client.
    """
    nb_panneaux, watt = panneaux_et_watt_lu(lignes)
    return nb_panneaux, (watt or _DEFAULT_WATT)


def panneaux_et_watt_lu(lignes) -> tuple:
    """``(nb_panneaux, watt LU)`` — ``watt`` vaut ``None`` s'il est ILLISIBLE.

    M3 (audit adversarial du 19/08/2026) — « × 710 W » était imprimé sur des
    devis dont AUCUNE ligne ni fiche produit ne porte 710 W : le défaut
    catalogue passait pour une lecture. Une puissance unitaire non lue est
    désormais absente, et le document écrit « N panneaux » tout court.

    Ordre de lecture, inchangé : fiche technique du produit (PV11) puis
    désignation / nom du produit.
    """
    nb_panneaux = 0
    watt = None
    for li in lignes:
        designation = getattr(li, "designation", "") or ""
        produit = getattr(li, "produit", None)
        produit_nom = getattr(produit, "nom", "") or ""
        if _is_panel(designation, produit_nom):
            nb_panneaux += int(round(float(getattr(li, "quantite", 0) or 0)))
            watt = (watt
                    or _fiche_watt(produit)
                    or _parse_watt(designation, produit_nom))
    return nb_panneaux, watt
