"""Marqueurs de chiffres client — UN chiffre, UNE valeur, sur TOUTES les surfaces.

POURQUOI. Sur les 30 bugs « chiffre faux » recensés par l'audit QA
(docs/decisions/COUV-HOR/audit-qa-complet.md), 12 étaient le MÊME chiffre
affiché différemment entre l'écran du devis, le PDF, la page publique et
l'API (PV86, PVCOV, PVUNI, 3e355126, ERR-QAH-TOTAL-DIVERGENCE, 0113…).
Chacun a donné naissance à UN test écrit à la main pour UNE paire de
chiffres. Ce module remplace cette approche par une vérification GÉNÉRIQUE :
chaque chiffre client porte une étiquette lisible par machine, et une seule
comparaison confronte toutes les étiquettes de toutes les surfaces. Tout
chiffre étiqueté demain est couvert gratuitement.

LA CONVENTION (une seule, pour tout le dépôt)
---------------------------------------------
* ``data-figure="<clé>"`` — la clé, OBLIGATOIREMENT déclarée dans
  ``FIGURE_KEYS`` ci-dessous (un test de garde refuse toute clé inconnue).
* ``data-figure-option="sans|avec"`` — l'option du devis que le chiffre
  décrit, quand le document en porte plusieurs (absent = chiffre du document
  entier).
* ``data-figure-taux="20"`` — le taux de TVA d'une ligne ``tva_taux``.
* La VALEUR est, par ordre de priorité :
    1. l'attribut ``data-figure-value`` s'il est présent ;
    2. sinon le TEXTE de l'élément porteur (écran React, page publique).

Deux formes, un même lecteur (``extract_figures``) :

* écran / page web : l'attribut est posé SUR l'élément qui imprime le nombre
  (``<strong data-figure="total_ttc" data-figure-option="avec">94 832 MAD``) ;
* PDF (gabarits Python) : une ANCRE vide et masquée est posée JUSTE APRÈS
  l'élément qui imprime le nombre, avec le MÊME texte formaté en
  ``data-figure-value`` (``ancre()``). Raison : des dizaines de tests épinglent
  le HTML exact des gabarits (``<div class="c1-kpi-v">5,68``) ; une ancre
  voisine ne modifie AUCUNE chaîne existante, et ``style="display:none"``
  (+ ``hidden``) la retire du rendu — le style EN LIGNE l'emporte sur toute
  feuille des gabarits, aucune boîte n'est créée : zéro changement visuel,
  zéro changement de pagination (règle #4 : le moteur ne fait que RENDRE).
  Aucun gabarit n'utilise de sélecteur d'adjacence (``+``, ``~``) ni de
  ``:nth-child`` sur les parents où les ancres sont posées (vérifié).
  Le donut de couverture est une IMAGE : l'ancre est la seule façon de dire
  son chiffre.

L'ancre reçoit toujours la chaîne DÉJÀ formatée qui est imprimée à côté (même
variable Python) : ce qui est comparé est ce que le client lit, pas une
valeur interne recalculée.

LES TOLÉRANCES
--------------
Deux mesures d'une même identité sont égales si leur écart est au plus
``max(tolerance(clé), max(résolution_a, résolution_b) / 2)``, où la
résolution est le pas d'affichage (« 94 832 » → 1 ; « 94 832,40 » → 0,01 ;
une valeur JSON → 0). Argent au centime, ou au demi-dirham quand une surface
affiche le dirham entier (un dirham d'écart entre deux affichages entiers est
donc un vrai écart — c'est le bug QJR53 troncature/arrondi) ; pourcentages à
1 point ; énergie au kWh (l'ancien moteur TRONQUE là où le nouveau ARRONDIT
les kWh : ±1 kWh n'est pas une seconde vérité) ; puissance au centième.

Module PUR : aucune dépendance Django, aucune BD — utilisable par les tests,
le qa-explorer et un futur auditeur.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

ATTR = "data-figure"
ATTR_OPTION = "data-figure-option"
ATTR_TAUX = "data-figure-taux"
ATTR_VALEUR = "data-figure-value"

#: Les options qu'un devis peut porter (``totaux_sans`` / ``totaux_avec``).
OPTIONS = ("sans", "avec")

_ARGENT = Decimal("0.01")
_POINT = Decimal("1")
_KWH = Decimal("1")
_KWC = Decimal("0.01")
_ANS = Decimal("0.05")
_UNITE_FINE = Decimal("0.1")


@dataclass(frozen=True)
class Cle:
    """Une clé du vocabulaire : description FR, unité, tolérance."""
    description: str
    unite: str
    tolerance: Decimal
    #: Vrai quand l'affichage porte un signe typographique qui n'est pas celui
    #: de la donnée (« − 1 200 » pour une remise de 1 200) : on compare les
    #: valeurs absolues.
    absolu: bool = False


#: LE vocabulaire. Ajouter une clé ici, puis poser ``data-figure`` sur les
#: surfaces qui l'impriment : la parité la couvre sans autre code.
FIGURE_KEYS: dict[str, Cle] = {
    # ── Chaîne de totaux (par option : data-figure-option) ──────────────────
    "sous_total_ht": Cle("Sous-total HT (avant remise)", "MAD", _ARGENT),
    "remise": Cle("Montant de la remise", "MAD", _ARGENT, absolu=True),
    "total_ht": Cle("Total HT après remise", "MAD", _ARGENT),
    "tva": Cle("Montant total de TVA", "MAD", _ARGENT),
    "tva_taux": Cle("Montant de TVA d'UN taux (data-figure-taux)", "MAD",
                    _ARGENT),
    "total_ttc": Cle("Total TTC de l'option", "MAD", _ARGENT),
    "total_affiche": Cle(
        "Total TTC d'affichage du devis (liste, en-tête, une page)", "MAD",
        _ARGENT),
    "prix_kwc": Cle("Prix TTC par kWc installé", "MAD/kWc", _POINT),
    # ── Système ─────────────────────────────────────────────────────────────
    "puissance_kwc": Cle("Puissance crête installée", "kWc", _KWC),
    "production_annuelle_kwh": Cle("Production solaire annuelle", "kWh/an",
                                   _KWH),
    # ── Économie client ─────────────────────────────────────────────────────
    "economie_annuelle": Cle("Économie annuelle", "MAD/an", _ARGENT),
    "payback_ans": Cle("Retour sur investissement", "ans", _ANS),
    "facture_annuelle_avant": Cle("Facture d'électricité annuelle actuelle",
                                  "MAD/an", _ARGENT),
    "facture_annuelle_apres": Cle("Facture annuelle avec le solaire",
                                  "MAD/an", _ARGENT),
    "facture_mensuelle_avant": Cle("Facture mensuelle actuelle (moyenne)",
                                   "MAD/mois", _ARGENT),
    "facture_mensuelle_apres": Cle("Facture mensuelle avec le solaire",
                                   "MAD/mois", _ARGENT),
    "reduction_facture_pct": Cle("Baisse de facture « −N % »", "%", _POINT),
    "couverture_pct": Cle(
        "Part de la consommation assurée par le solaire (donut)", "%",
        _POINT),
    "autoconsommation_pct": Cle("Taux d'autoconsommation", "%", _POINT),
    # ── Pompage ─────────────────────────────────────────────────────────────
    "pompe_hmt_m": Cle("Hauteur manométrique totale", "m", _UNITE_FINE),
    "pompe_debit_m3h": Cle("Débit de la pompe à la HMT", "m³/h", _UNITE_FINE),
    "pompe_volume_m3_jour": Cle("Volume d'eau pompé par jour", "m³/jour",
                                _POINT),
}


# ── Identité d'un chiffre ────────────────────────────────────────────────────

def identite(cle: str, option: str | None = None,
             taux: str | None = None) -> str:
    """``cle[:taux][@option]`` — la clé de comparaison entre surfaces."""
    ident = cle
    if taux not in (None, ""):
        ident += f":{_taux_canonique(taux)}"
    if option not in (None, ""):
        ident += f"@{option}"
    return ident


def cle_de(ident: str) -> str:
    """La clé nue d'une identité (``total_ttc@avec`` → ``total_ttc``)."""
    return ident.split("@", 1)[0].split(":", 1)[0]


def _taux_canonique(taux) -> str:
    try:
        d = Decimal(str(taux).replace(",", ".").strip().rstrip("%").strip())
    except (InvalidOperation, ValueError):
        return str(taux)
    return format(d.normalize(), "f")


# ── Production des marqueurs (gabarits Python) ───────────────────────────────

def attrs(cle: str, option: str | None = None, taux=None,
          valeur: str | None = None) -> str:
    """Les attributs ``data-figure*`` (préfixés d'une espace) d'un élément."""
    out = f' {ATTR}="{_html.escape(cle, quote=True)}"'
    if option:
        out += f' {ATTR_OPTION}="{_html.escape(option, quote=True)}"'
    if taux not in (None, ""):
        out += f' {ATTR_TAUX}="{_taux_canonique(taux)}"'
    if valeur is not None:
        out += f' {ATTR_VALEUR}="{_html.escape(str(valeur), quote=True)}"'
    return out


def ancre(cle: str, texte, option: str | None = None, taux=None) -> str:
    """Ancre VIDE et masquée qui étiquette le nombre imprimé juste avant.

    ``texte`` est la chaîne DÉJÀ formatée que le gabarit imprime (avec ou sans
    unité : seul le premier nombre est lu). Ne lève jamais : un rendu client
    ne doit pas casser pour un marqueur — la clé inconnue est refusée par le
    test de garde, pas en production. Un texte SANS nombre (« — ») n'est pas
    un chiffre : aucune ancre.
    """
    texte = _html.unescape(str(texte))
    if normaliser(texte)[0] is None:
        return ""
    return (f"<span{attrs(cle, option, taux, texte)} "
            f"style=\"display:none\" hidden></span>")


# ── Lecture des nombres à la française ───────────────────────────────────────

_ESPACES = "      "
_NOMBRE_RE = re.compile(
    r"(?P<signe>[-−–]?)\s*"
    r"(?P<entier>\d{1,3}(?:[" + _ESPACES + r"]\d{3})+|\d+)"
    r"(?:[,.](?P<dec>\d+))?")


def normaliser(texte) -> tuple[Decimal | None, Decimal]:
    """« 117 391,16 MAD » → (117391.16, 0.01) ; « 37 % » → (37, 1) ;
    « 8,5 kWc » → (8.5, 0.1) ; « 4.7 » → (4.7, 0.1). Illisible → (None, 0).

    Le second élément est la RÉSOLUTION d'affichage (pas du dernier chiffre
    imprimé). Accepte les nombres Python/JSON (résolution 0 : valeur exacte).
    """
    if texte is None:
        return None, Decimal(0)
    if isinstance(texte, bool):
        return None, Decimal(0)
    if isinstance(texte, (int, float, Decimal)):
        try:
            d = Decimal(str(texte))
        except InvalidOperation:
            return None, Decimal(0)
        if not d.is_finite():
            return None, Decimal(0)
        return d, Decimal(0)
    s = _html.unescape(str(texte))
    m = _NOMBRE_RE.search(s)
    if not m:
        return None, Decimal(0)
    entier = re.sub(f"[{_ESPACES}]", "", m.group("entier"))
    dec = m.group("dec") or ""
    brut = entier + ("." + dec if dec else "")
    try:
        valeur = Decimal(brut)
    except InvalidOperation:
        return None, Decimal(0)
    if m.group("signe"):
        valeur = -valeur
    resolution = Decimal(1).scaleb(-len(dec)) if dec else Decimal(1)
    return valeur, resolution


@dataclass(frozen=True)
class Mesure:
    """Une lecture d'un chiffre sur une surface."""
    valeur: Decimal | None
    resolution: Decimal
    texte: str


def mesure(texte) -> Mesure:
    valeur, resolution = normaliser(texte)
    return Mesure(valeur, resolution, str(texte))


# ── Extraction depuis un HTML ────────────────────────────────────────────────

class _Extracteur(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.figures: dict[str, list[Mesure]] = {}
        # Captures ouvertes : [tag, profondeur, identité, morceaux de texte]
        self._ouvertes: list[list] = []

    def _noter(self, ident, texte):
        self.figures.setdefault(ident, []).append(mesure(texte))

    def _debut(self, tag, attributs, auto_fermant):
        a = dict(attributs)
        for capture in self._ouvertes:
            if capture[0] == tag and not auto_fermant:
                capture[1] += 1
        if ATTR not in a:
            return
        ident = identite(a.get(ATTR) or "", a.get(ATTR_OPTION),
                         a.get(ATTR_TAUX))
        if ATTR_VALEUR in a:
            self._noter(ident, a.get(ATTR_VALEUR) or "")
        elif not auto_fermant:
            self._ouvertes.append([tag, 1, ident, []])

    def handle_starttag(self, tag, attributs):
        self._debut(tag, attributs, tag in _VIDES)

    def handle_startendtag(self, tag, attributs):
        self._debut(tag, attributs, True)

    def handle_endtag(self, tag):
        restantes = []
        for capture in self._ouvertes:
            if capture[0] == tag:
                capture[1] -= 1
                if capture[1] == 0:
                    self._noter(capture[2], "".join(capture[3]).strip())
                    continue
            restantes.append(capture)
        self._ouvertes = restantes

    def handle_data(self, data):
        for capture in self._ouvertes:
            capture[3].append(data)


_VIDES = frozenset(("area", "base", "br", "col", "embed", "hr", "img",
                    "input", "link", "meta", "source", "track", "wbr"))


def extract_figures(html: str) -> dict[str, list[Mesure]]:
    """``{identité: [Mesure, …]}`` de tous les éléments ``data-figure``."""
    p = _Extracteur()
    p.feed(html or "")
    p.close()
    return p.figures


def cles_inconnues(figures: dict) -> list[str]:
    """Les identités dont la clé n'est pas déclarée dans ``FIGURE_KEYS``."""
    return sorted(i for i in figures if cle_de(i) not in FIGURE_KEYS)


# ── Comparaison ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Mismatch:
    """Un même chiffre affiché différemment sur deux surfaces (ou deux fois
    sur la même)."""
    identite: str
    surface_a: str
    texte_a: str
    surface_b: str
    texte_b: str
    ecart: Decimal | None
    tolerance: Decimal
    raison: str = "écart"

    @property
    def signature(self) -> tuple[str, str, str]:
        """``(identité, surface, surface)`` — la forme des KNOWN_MISMATCHES."""
        return (self.identite, self.surface_a, self.surface_b)

    def __str__(self):
        if self.raison != "écart":
            return (f"{self.identite} : {self.raison} sur {self.surface_a} "
                    f"({self.texte_a!r})")
        return (f"{self.identite} : {self.surface_a} affiche "
                f"{self.texte_a!r}, {self.surface_b} affiche "
                f"{self.texte_b!r} (écart {self.ecart}, tolérance "
                f"{self.tolerance})")


def tolerance_de(ident: str) -> Decimal:
    cle = FIGURE_KEYS.get(cle_de(ident))
    return cle.tolerance if cle else Decimal(0)


def compare_surfaces(surfaces: dict[str, dict[str, list[Mesure]]]
                     ) -> list[Mismatch]:
    """Toutes les incohérences entre surfaces ``{nom: extract_figures(...)}``.

    Pour chaque identité, chaque mesure est confrontée à la mesure la plus
    PRÉCISE de cette identité (toutes surfaces confondues) : une surface qui
    affiche un nombre deux fois est aussi vérifiée contre elle-même. Une
    identité présente sur une seule surface, une seule fois, n'a rien à
    comparer. Une mesure illisible (texte sans nombre) est toujours signalée.
    """
    ecarts: list[Mismatch] = []
    par_ident: dict[str, list[tuple[str, Mesure]]] = {}
    for nom, figures in surfaces.items():
        for ident, mesures in (figures or {}).items():
            for m in mesures:
                par_ident.setdefault(ident, []).append((nom, m))
    for ident in sorted(par_ident):
        lectures = par_ident[ident]
        cle = FIGURE_KEYS.get(cle_de(ident))
        lisibles = []
        for nom, m in lectures:
            if m.valeur is None:
                ecarts.append(Mismatch(ident, nom, m.texte, nom, m.texte,
                                       None, Decimal(0), "valeur illisible"))
            else:
                lisibles.append((nom, m))
        if len(lisibles) < 2:
            continue
        ref_nom, ref = min(lisibles, key=lambda nm: nm[1].resolution)
        tol = cle.tolerance if cle else Decimal(0)
        absolu = bool(cle and cle.absolu)
        vref = abs(ref.valeur) if absolu else ref.valeur
        deja = set()
        for nom, m in lisibles:
            if m is ref:
                continue
            v = abs(m.valeur) if absolu else m.valeur
            permis = max(tol, max(ref.resolution, m.resolution) / 2)
            ecart = abs(v - vref)
            if ecart > permis:
                sig = (nom, m.texte)
                if sig in deja:
                    continue
                deja.add(sig)
                ecarts.append(Mismatch(ident, ref_nom, ref.texte, nom,
                                       m.texte, ecart, permis))
    return ecarts


def identites_comparees(surfaces: dict[str, dict]) -> set[str]:
    """Identités lues au moins DEUX fois (donc réellement confrontées)."""
    compte: dict[str, int] = {}
    for figures in surfaces.values():
        for ident, mesures in (figures or {}).items():
            compte[ident] = compte.get(ident, 0) + len(mesures)
    return {i for i, n in compte.items() if n >= 2}


# ── Surfaces JSON → mêmes clés ───────────────────────────────────────────────

@dataclass
class _Collecte:
    figures: dict[str, list[Mesure]] = field(default_factory=dict)

    def mettre(self, cle, valeur, option=None, taux=None, *,
               zero_ok=False):
        if valeur is None or isinstance(valeur, bool):
            return
        v, _res = normaliser(valeur)
        if v is None:
            return
        if not zero_ok and v == 0:
            return
        self.figures.setdefault(identite(cle, option, taux), []).append(
            Mesure(v, Decimal(0), str(valeur)))


def _num(v):
    valeur, _ = normaliser(v) if v is not None else (None, None)
    return valeur


def _totaux(c: _Collecte, totaux, option):
    if not isinstance(totaux, dict):
        return
    c.mettre("sous_total_ht", totaux.get("ht_brut"), option)
    c.mettre("remise", totaux.get("remise"), option)
    c.mettre("total_ht", totaux.get("ht_net"), option)
    c.mettre("tva", totaux.get("tva"), option)
    for b in totaux.get("tva_par_taux") or []:
        if isinstance(b, dict):
            c.mettre("tva_taux", b.get("montant"), option, b.get("taux"))
    c.mettre("total_ttc", totaux.get("ttc"), option)


def options_affichees(quote: dict) -> tuple[str, ...]:
    """Les options que le document PRÉSENTE (miroir de ``cover.build`` /
    ``options.build_pages`` : deux cartes, sinon la seule option réelle)."""
    if quote.get("deux_options", True):
        return OPTIONS
    return ("avec",) if quote.get("avec_ok", True) else ("sans",)


def option_economique(quote: dict) -> str:
    """L'option que décrit la synthèse −N % / donut
    (``renderer.synthese_economies`` : ``_avec``)."""
    opt = quote.get("eco_option")
    if opt in OPTIONS:
        return opt
    avec = bool(quote.get("deux_options", True)) or bool(
        quote.get("avec_ok", True))
    return "avec" if avec else "sans"


def _divergent(quote: dict, cle: str) -> bool:
    """Miroir des gardes de ``cover.build`` : deux valeurs PAR OPTION ne sont
    imprimées que sur un document à deux options dont les champs PV divergent
    (``panneaux_divergents``) et dont les deux valeurs existent et diffèrent."""
    if not (quote.get("panneaux_divergents")
            and quote.get("deux_options", True)):
        return False
    s, a = _num(quote.get(f"{cle}_sans")), _num(quote.get(f"{cle}_avec"))
    return s is not None and a is not None and s > 0 and a > 0 and s != a


def figures_depuis_proposition(payload: dict) -> dict[str, list[Mesure]]:
    """Charge utile de ``GET /api/django/public/proposal/<token>/data/`` →
    mêmes clés que les documents. Ne mappe que des champs SERVIS : aucune
    valeur n'est recalculée ici, sauf les deux dérivations DÉFINITIONNELLES
    que les documents impriment (moyenne mensuelle = annuel ÷ 12, prix au kWc
    = TTC de l'option ÷ kWc de l'option)."""
    c = _Collecte()
    payload = payload or {}
    quote = payload.get("quote") or {}
    ot = payload.get("option_totals") or {}
    affichees = options_affichees(quote) if quote else OPTIONS
    for opt, cle_ot in (("sans", "sans_batterie"), ("avec", "avec_batterie")):
        if opt in affichees:
            _totaux(c, ot.get(cle_ot) or quote.get(f"totaux_{opt}"), opt)
    # Chaîne SANS option : celle du une-page « liste libre » et des documents
    # C&I, qui impriment ``totaux_all`` (le devis entier).
    _totaux(c, quote.get("totaux_all"), None)
    # ERR-QAC-MULTIVILLA-TOTAL-XN — un devis ×N villas affiche (liste) et
    # facture le total ×N que le document imprime : c'est LUI le total affiché.
    if quote.get("display_total_multi") is not None:
        c.mettre("total_affiche", quote.get("display_total_multi"))
    else:
        c.mettre("total_affiche", ot.get("display_total")
                 if ot.get("display_total") is not None
                 else quote.get("display_total"))

    kwc_div = _divergent(quote, "puissance_kwc")
    if not kwc_div:
        c.mettre("puissance_kwc", quote.get("puissance_kwc"))
    prod_div = _divergent(quote, "prod_kwh")
    if not prod_div:
        c.mettre("production_annuelle_kwh", quote.get("prod_kwh"))
    for opt in affichees:
        if kwc_div:
            c.mettre("puissance_kwc", quote.get(f"puissance_kwc_{opt}"), opt)
        if prod_div:
            c.mettre("production_annuelle_kwh", quote.get(f"prod_kwh_{opt}"),
                     opt)
        suffixe = "s" if opt == "sans" else "a"
        c.mettre("economie_annuelle", quote.get(f"eco_{suffixe}_ann"), opt)
        c.mettre("payback_ans", quote.get(f"roi_{suffixe}"), opt)
        ttc = _num((ot.get(f"{opt}_batterie") or {}).get("ttc")
                   if isinstance(ot.get(f"{opt}_batterie"), dict)
                   else (quote.get(f"totaux_{opt}") or {}).get("ttc"))
        kwc = _num(quote.get(f"puissance_kwc_{opt}")) if kwc_div else None
        kwc = kwc or _num(quote.get("puissance_kwc"))
        if ttc and kwc:
            c.mettre("prix_kwc", ttc / kwc, opt)

    # Couverture PAR OPTION calculée par le moteur horaire (fraction 0..1) :
    # celle que l'écran du générateur affiche (« Taux de couverture (sans) »)
    # et que le donut du PDF reprend pour son option (COUV-HOR).
    for opt in OPTIONS:
        v = _num(quote.get(f"couverture_{opt}"))
        if v is not None and 0 < v <= 1:
            c.mettre("couverture_pct", v * 100, opt)

    eco_opt = option_economique(quote)
    c.mettre("reduction_facture_pct", payload.get("pct_cut"), eco_opt,
             zero_ok=True)
    c.mettre("couverture_pct", payload.get("coverage_pct"), eco_opt)
    avant = _num(payload.get("annual_before"))
    apres = _num(payload.get("annual_after"))
    c.mettre("facture_annuelle_avant", avant)
    c.mettre("facture_annuelle_apres", apres, eco_opt, zero_ok=True)
    if avant is not None:
        c.mettre("facture_mensuelle_avant", avant / 12)
    if apres is not None:
        c.mettre("facture_mensuelle_apres", apres / 12, eco_opt,
                 zero_ok=True)

    kpis = payload.get("mode_kpis") or {}
    mode = (payload.get("mode_installation") or quote.get(
        "mode_installation") or "").strip().lower()
    if mode in ("industriel", "commercial"):
        c.mettre("autoconsommation_pct", kpis.get("taux_autoconso"))
        c.mettre("couverture_pct", kpis.get("taux_couverture"))
        c.mettre("economie_annuelle", kpis.get("economies_annuelles"))
        c.mettre("payback_ans", kpis.get("payback"))
    elif mode == "agricole":
        c.mettre("pompe_hmt_m", kpis.get("hmt_m"))
        c.mettre("pompe_debit_m3h", kpis.get("debit_hmt_m3h"))
        c.mettre("pompe_volume_m3_jour", kpis.get("m3_jour"))
    return c.figures


def figures_depuis_devis_api(detail: dict) -> dict[str, list[Mesure]]:
    """``GET /api/django/ventes/devis/<id>/`` (écran interne, liste) → clés.

    ``comparaison_options`` n'existe que sur un devis à deux options ; son
    bloc ``roi`` est la sortie du MÊME ``build_quote_data``."""
    c = _Collecte()
    detail = detail or {}
    c.mettre("total_affiche", detail.get("total_affiche")
             if detail.get("total_affiche") is not None
             else detail.get("total_ttc"))
    comp = detail.get("comparaison_options") or {}
    for opt in OPTIONS:
        bloc = comp.get(opt) or {}
        c.mettre("total_ttc", bloc.get("ttc"), opt)
        c.mettre("total_ht", bloc.get("ht_net"), opt)
        c.mettre("remise", bloc.get("remise"), opt)
    roi = comp.get("roi") or {}
    c.mettre("production_annuelle_kwh", roi.get("prod_kwh"))
    c.mettre("economie_annuelle", roi.get("eco_s_ann"), "sans")
    c.mettre("economie_annuelle", roi.get("eco_a_ann"), "avec")
    c.mettre("payback_ans", roi.get("roi_s"), "sans")
    c.mettre("payback_ans", roi.get("roi_a"), "avec")
    return c.figures
