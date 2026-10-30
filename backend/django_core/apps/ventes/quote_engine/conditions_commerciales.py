"""SPL164 — phase E de ``build_quote_data`` : conditions commerciales (move only).

Déplacés tels quels de ``builder.py`` : le corps de ``build_quote_data`` du
marqueur « Q5 — DÉLAIS COMMERCIAUX » jusqu'à la note de TVA (juste avant le
dict ``data``), en TROIS fonctions pour garder des interfaces courtes :

* ``delais_validite_et_kit`` (E1) — délais indicatifs Q5, validité M7, nom du
  client, branche une-page CHOIX-AVEC, dégradation kit L-NIV, ``all_items`` ;
* ``remises_et_puces`` (E2) — remise globale ligne à ligne QJRREM, puces des
  cartes, type d'installation, ``include_etude`` ;
* ``conditions_et_liens`` (E3) — étude bancable PV77, termes de paiement,
  textes société, identité, site du tenant SCA27, lien de proposition QX6
  (ShareLink LU, jamais créé ni dupliqué), contact QG7, note de TVA ;

et les helpers de paiement / mentions de niveau module (``PAYMENT_TERMS_BY_MODE``,
répartition et tranches d'échéancier, note de TVA, textes gelés, logo, hôte du
site). Chaque fonction reçoit ses entrées en arguments NOMMÉS et rend ses
sorties dans l'ordre que ``build_quote_data`` dépaquette dans les MÊMES noms
locaux (``avec_items`` / ``sans_items`` / ``all_items`` passent et reviennent) ;
``PUCE_AVEC_BATTERIE_DIFFEREE`` reste une constante de ``builder`` (helpers de
composition) et arrive en argument. Rendu pur (règle #4) : aucun statut touché.

Ce module n'importe JAMAIS ``builder`` (cycle) : les helpers de classement
viennent de ``lignes_classement``.
"""
from __future__ import annotations

import copy
import logging
from decimal import Decimal

# L-NIV — LA règle d'agrégation « kit » du niveau standard, partagée avec la
# charge utile JSON publique et le comparatif de gammes (une seule vérité).
from apps.ventes.utils.anticopie import agreger_lignes_kit

from . import i18n_labels as _i18n
from .lignes_classement import (
    _LigneArgentPdf, _battery_kwh_from_items, _is_battery, _is_hybrid_inverter,
    _is_offgrid_inverter, _is_panel, _is_reseau_inverter, _parse_marque,
)

logger = logging.getLogger(__name__)


# ── Conditions de paiement par mode d'installation (SOURCE UNIQUE) ──
# Décision propriétaire 2026-06-12. Tous les formats PDF ET l'échéancier
# devis → factures (acompte/tranches) lisent CE mapping ; plus aucun
# pourcentage de paiement en dur ailleurs. Agricole = 30/60/10 CONSERVÉ
# (décision du 02/10/2026, AGR219 : MESURER avant tout autre réglage, comme
# CAD52) ; la trésorerie « après récolte » se dit par la ``date_prevue``
# facultative d'une tranche (``utils/echeancier.py``), jamais par un autre %.
PAYMENT_TERMS_BY_MODE = {
    "residentiel": {"acompte": 30, "materiel": 60, "solde": 10},
    # CIQ212 — décision fondateur D-CIQ-13 du 03/10/2026 : échéancier C&I à N
    # JALONS (remplace la valeur industrielle 50/40/10 du 12/06/2026 et le
    # 50/40/10 commercial provisoire de QX43). Défauts SOCIÉTÉ éditables
    # (Paramètres → Devis, ``CompanyProfile.payment_terms[mode]`` en liste de
    # jalons) ; la réception définitive est un SOLDE.
    "industriel": [
        {"jalon": "commande", "pct": 30},
        {"jalon": "livraison_materiel", "pct": 40},
        {"jalon": "mise_en_service", "pct": 20},
        {"jalon": "reception_definitive", "pct": 10},
    ],
    "commercial": [
        {"jalon": "commande", "pct": 40},
        {"jalon": "livraison_materiel", "pct": 50},
        {"jalon": "mise_en_service", "pct": 10},
    ],
    "agricole": {"acompte": 30, "materiel": 60, "solde": 10},
}


class _PasDeLienSigner(Exception):
    """ADEV68 — signal interne : aucun lien « signer » pour ce rendu."""


def _normalize_site_host(site: str) -> str:
    """SCA27 — forme d'AFFICHAGE d'un site tenant (comme le littéral fondateur
    ``exemple.ma``) : sans schéma, sans ``www.``, sans chemin ni slash final.

    ``https://www.helios.ma/`` → ``helios.ma``. Chaîne vide/None → '' (le moteur
    garde alors ses littéraux historiques). N'invente jamais de domaine.
    """
    s = (site or "").strip()
    if not s:
        return ""
    # Retire le schéma (http/https/…) puis un éventuel www.
    if "://" in s:
        s = s.split("://", 1)[1]
    if s.lower().startswith("www."):
        s = s[4:]
    # Garde uniquement l'hôte (coupe au premier / ? #).
    for sep in ("/", "?", "#"):
        if sep in s:
            s = s.split(sep, 1)[0]
    return s.strip().rstrip("/")


def _taux_libelle(taux) -> str:
    """``20`` → ``'20'`` ; ``5.5`` → ``'5,5'`` (virgule française)."""
    t = float(taux)
    if t == int(t):
        return str(int(t))
    return f"{t:g}".replace(".", ",")


def _pct_simple(valeur):
    """``Decimal('40.00')`` → ``40`` ; ``33.5`` → ``33.5`` (jamais un Decimal :
    le dict de rendu est sérialisé — empreinte PVFRESH, proposition JSON)."""
    try:
        f = float(valeur)
    except (TypeError, ValueError):
        return valeur
    return int(f) if f == int(f) else round(f, 2)


def repartition_paiement(total, termes, tranches_montant=None) -> dict:
    """QJR623 — les cases « Modalités de paiement » du Devis final, au CENTIME.

    Remplace l'ancienne répartition du moteur legacy (``_repartir_paiement`` :
    cases arrondies au MILLIER, reliquat sur un total arrondi au dirham —
    ERR120). Les montants viennent de ``utils.echeancier.montants_tranches``
    (reliquat sur la dernière tranche) : acompte + matériel + solde ==
    ``total`` au centime.

    * ``termes`` : ``{acompte, materiel, solde}`` en pourcentages (échéancier
      RÉEL du devis, QJR622) ; la part matériel imprimée est ``100 − a − s``
      (un échéancier à deux tranches n'a pas de case matériel) ;
    * ``tranches_montant`` (QJR624, D-QJR5-10) — les tranches normalisées
      de ``Devis.echeancier`` quand l'une d'elles est déclarée en DIRHAMS
      (l'« acompte personnalisé » du dialogue PDF y écrit l'acompte) : chaque
      case vaut alors EXACTEMENT ce que ``next_tranche`` facturera sur un devis
      sans facture émise (montant déclaré, ou ``total × pct`` au centime, la
      dernière = reliquat) ; deux tranches ⇒ DEUX cases (acompte + solde2).

    Pure : aucun statut, aucune écriture (règle #4). Montants en ``float``.
    """
    from decimal import ROUND_HALF_UP
    from decimal import Decimal as _D

    from apps.ventes.utils.echeancier import montants_tranches

    tot = _D(str(total or 0)).quantize(_D("0.01"), rounding=ROUND_HALF_UP)
    pa = _D(str(termes.get("acompte", 30) or 0))
    ps = _D(str(termes.get("solde", 10) or 0))
    pm = _D(100) - pa - ps
    m = montants_tranches(tot, [("acompte", pa), ("materiel", max(pm, _D(0))),
                                ("solde", ps)])
    acompte, materiel, solde = m["acompte"], m["materiel"], m["solde"]
    pct_a, pct_m, pct_s = pa, pm, ps
    if pm <= 0:
        # Échéancier sans tranche matériel : le reliquat va au solde.
        solde = tot - acompte
        materiel = _D(0)
    if tranches_montant:
        montants = []
        for i, tr in enumerate(tranches_montant):
            if i == len(tranches_montant) - 1:
                montants.append(tot - sum(montants, _D(0)))
            else:
                # ROUND_HALF_UP : la règle de ``next_tranche`` (facture).
                if tr.get("unite") == "montant":
                    m = _D(str(tr.get("valeur") or 0)).quantize(
                        _D("0.01"), rounding=ROUND_HALF_UP)
                else:
                    m = (tot * _D(str(tr.get("valeur") or 0)) / 100).quantize(
                        _D("0.01"), rounding=ROUND_HALF_UP)
                # Borné au reste (ERR76) : aucune case négative.
                montants.append(max(_D(0), min(m, tot - sum(montants, _D(0)))))
        acompte = montants[0]
        materiel = montants[1] if len(montants) == 3 else _D(0)
        solde = montants[-1]
        pct_a = ((acompte / tot * 100).quantize(_D("1"), rounding=ROUND_HALF_UP)
                 if tot else _D(0))
        pct_m = ((materiel / tot * 100).quantize(_D("1"), rounding=ROUND_HALF_UP)
                 if tot else _D(0))
        pct_s = 100 - pct_a - pct_m
    deux_cases = materiel <= 0
    if tot <= 0:
        # Total nul (devis sans ligne chiffrée) : tous les montants valent 0,
        # donc « matériel = 0 » ne dit RIEN de la forme de l'échéancier — la
        # forme (2 ou 3 cases) vient du nombre de tranches / de la part
        # matériel déclarée, sinon un 30/60/10 s'imprimait 30/0/70.
        deux_cases = (len(tranches_montant) == 2 if tranches_montant
                      else pm <= 0)
    solde2 = tot - acompte
    pct_s2 = 100 - pct_a
    return {
        "total": float(tot),
        "acompte": float(acompte), "materiel": float(max(materiel, _D(0))),
        "solde": float(solde),
        "pct_a": _pct_simple(pct_a), "pct_m": _pct_simple(pct_m),
        "pct_s": _pct_simple(pct_s),
        "deux_cases": bool(deux_cases),
        "solde2": float(solde2), "pct_s2": _pct_simple(pct_s2),
    }


def tranches_echeancier_en_montant(devis):
    """QJR624 — les tranches normalisées de l'échéancier du devis quand il
    compte 2 ou 3 tranches dont au moins une déclarée en DIRHAMS, sinon
    ``None`` (le chemin en pourcentages reste celui de QJR623). Lecture
    tolérante (``tranches_normalisees``) ; jamais une exception."""
    if devis is None:
        return None
    try:
        from apps.ventes.utils.echeancier import (UNITE_MONTANT,
                                                  tranches_normalisees)
        tranches = tranches_normalisees(devis)
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
        logger.warning("builder.tranches_echeancier_en_montant : erreur ignorée (mode dégradé)", exc_info=True)
        return None
    if len(tranches) in (2, 3) and any(
            t.get("unite") == UNITE_MONTANT for t in tranches):
        return tranches
    return None


def tva_note_des_lignes(lignes, taux_defaut, langue=None) -> str:
    """QJR626 — la mention TVA du PDF, dérivée des taux RÉELS des lignes.

    * un seul taux ``r`` (ou aucune ligne : taux du devis) →
      « TVA r % appliquée sur l'ensemble des équipements et travaux. » ;
    * {10, 20} avec TOUTES les lignes à 10 % classées panneau (même
      classifieur que le builder) et tout le reste à 20 % → le texte 10 / 20 ;
    * sinon → « TVA appliquée ligne par ligne : a % / b % — taux indiqué dans
      le tableau », avec les SEULS taux présents sur les lignes.

    Une ligne sans taux propre (devis historique) porte le taux du devis.
    AGR217 — une ligne À 0 % (taux propre) ⇒ « TVA appliquée ligne par
    ligne : 0 % / … — exonération : <base légale saisie> », une mention par
    base distincte ; sans ligne à 0 %, texte identique à l'octet.
    Lecture pure : aucun statut écrit (règle #4).
    APDF10 — ``langue`` (en/ar) : les mêmes phrases tirées d'``i18n_labels``
    (``tva_*``), mêmes taux ; français (défaut) inchangé à l'octet.
    """
    def _t(cle, fr, **valeurs):
        if _i18n.normaliser(langue) == "fr":
            return fr
        return _i18n.libelle(cle, langue).format(**valeurs)

    par_taux = {}
    bases = []
    zero_ligne = False
    for li in lignes:
        taux = getattr(li, "taux_tva", None)
        if taux is not None and float(taux) == 0.0:
            zero_ligne = True
        if taux is None:
            taux = taux_defaut
        taux = float(taux)
        produit_nom = getattr(getattr(li, "produit", None), "nom", "") or ""
        par_taux.setdefault(taux, []).append(
            _is_panel(getattr(li, "designation", "") or "", produit_nom))
        # AGR217 — la base légale SAISIE d'une ligne exonérée (une mention
        # par base distincte, dans l'ordre des lignes).
        base = (getattr(li, "tva_base_legale", "") or "").strip()
        if taux == 0.0 and base and base not in bases:
            bases.append(base)
    if zero_ligne:
        # AGR217 — un 0 % présent : la note le dit ligne par ligne et CITE
        # la base légale saisie (jamais un texte proposé par défaut).
        taux_txt = " / ".join(
            f"{_taux_libelle(t)} %" for t in sorted(par_taux))
        mentions = " ; ".join(_t("tva_exoneration", f"exonération : {b}",
                                 base=b) for b in bases)
        return (_t("tva_ligne_par_ligne",
                   f"TVA appliquée ligne par ligne : {taux_txt}",
                   taux=taux_txt)
                + (f" — {mentions}" if mentions else ""))
    if len(par_taux) <= 1:
        taux = next(iter(par_taux)) if par_taux else float(taux_defaut)
        return _t("tva_unique", f"TVA {_taux_libelle(taux)} % appliquée "
                  "sur l'ensemble des équipements et travaux.",
                  taux=_taux_libelle(taux))
    if (set(par_taux) == {10.0, 20.0}
            and all(par_taux[10.0]) and not any(par_taux[20.0])):
        return _t("tva_10_20", "TVA : 10% panneaux photovoltaïques · "
                  "20% autres équipements et prestations")
    taux_txt = " / ".join(f"{_taux_libelle(t)} %" for t in sorted(par_taux))
    return (_t("tva_ligne_par_ligne",
               f"TVA appliquée ligne par ligne : {taux_txt}", taux=taux_txt)
            + _t("tva_taux_tableau", " — taux indiqué dans le tableau"))


def _doc_texts_geles(devis):
    """APDF14 (C-APDF-006) — textes contractuels GELÉS à l'envoi (entrée
    ``doc_texts_geles`` d'APDF20) d'un devis envoyé ou signé, réduits à ses
    vraies surcharges (≠ défaut du moteur, comme ``as_doc_texts``), ou
    ``None`` : brouillon, ou envoyé d'avant ce gel (comportement inchangé)."""
    if getattr(devis, "statut", None) == "brouillon":
        return None
    for c in (getattr(devis, "clauses_appliquees", None) or []):
        if (isinstance(c, dict) and c.get("type") == "doc_texts_geles"
                and isinstance(c.get("textes"), dict)):
            from .generate_devis_premium import DEFAULT_DOC_TEXTS
            return {cle: copy.deepcopy(val)
                    for cle, val in c["textes"].items()
                    if val not in (None, "", [], {})
                    and val != DEFAULT_DOC_TEXTS.get(cle)}
    return None


def _doc_texts_envoyes(devis, doc_texts):
    """Textes de document d'un devis : ceux GELÉS à l'envoi, sinon les vifs.

    ERR-QJR668 — les puces CGV de la société GELÉES à l'envoi (entrée
    ``cgv_gelees`` de ``Devis.clauses_appliquees``) remplacent les puces
    vives dans le bloc CGV STANDARD : un texte édité après l'envoi ne change
    pas ce que le client a reçu. Copie : le dict mémoïsé est partagé.
    Brouillon / jamais envoyé → pas d'entrée → textes vifs, inchangé.
    APDF12 — une variante C&I gelée (entrée portant un ``mode``) n'est
    JAMAIS recopiée ici : elle est servie par ``cgv_ci`` (titre compris,
    marqueurs substitués), via ``clauses_cgv.cgv_imprimees``.
    APDF14 — devis envoyé ou signé : l'ENSEMBLE des textes gelés à l'envoi
    (CGV, titre, garanties, bon pour accord…) prime sur les textes vifs ; la
    boucle ERR-QJR668 ne sert plus qu'aux envoyés d'avant ce gel.
    Les puces ``cgv_gelees`` (posées à l'ENVOI) priment toujours, appliquées
    APRÈS le choix des textes : un ``doc_texts_geles`` posé plus tard par une
    correction sur place d'un envoyé d'avant APDF20 porte les CGV du jour.
    """
    _geles = _doc_texts_geles(devis)
    doc_texts = doc_texts if _geles is None else _geles
    for _c in (getattr(devis, "clauses_appliquees", None) or []):
        if (isinstance(_c, dict) and _c.get("type") == "cgv_gelees"
                and not _c.get("mode")
                and isinstance(_c.get("bullets"), list) and _c["bullets"]):
            return dict(doc_texts, cgv_bullets=[
                str(b) for b in _c["bullets"]])
    return doc_texts


def _entreprise_avec_logo(devis, entreprise, pdf_options):
    """APDF4 — logo TÉLÉVERSÉ de la société (``logo_key``), lu comme la facture
    (``utils/pdf`` : même téléchargement, même rognage, data URI), sur le
    seul chemin de RENDU (drapeau serveur de l'affiche) ; clé posée
    seulement quand un logo existe (charge publique et golden inchangés)."""
    if not (entreprise and (pdf_options or {}).get("_embed_roof_render")):
        return entreprise
    try:
        from django.conf import settings as _st
        from apps.parametres.models import CompanyProfile
        from apps.ventes.utils import pdf as _pdf
        _cle_logo = CompanyProfile.get(company=devis.company).logo_key
        _brut = _cle_logo and _pdf._download(
            _st.MINIO_BUCKET_UPLOADS, _cle_logo)
        if _brut:
            _rogne, _ext = _pdf._trim_image_whitespace(_brut)
            entreprise = dict(entreprise, logo_uri=_pdf._to_data_uri(
                _rogne, _ext or _cle_logo))
    except Exception:  # noqa: BLE001 — un logo illisible ne casse rien (D-ENF22-BLE001)
        logger.warning("builder._entreprise_avec_logo : erreur ignorée (mode dégradé)", exc_info=True)
        pass
    return entreprise


def delais_validite_et_kit(*, _blob, _items_libres, avec_items, avec_lignes,
                           avec_ok, client, deux_options, devis, has_batterie,
                           has_reseau, option_servie, opts, sans_items,
                           scenario):
    # ── Q5 (décision fondateur du 20/08/2026) — DÉLAIS COMMERCIAUX ───────────
    # « visite sous 48-72 h » et « installation 7-14 jours » étaient codés en
    # dur dans quatre renderers ET rendus dans la boîte « Conditions » du PDF,
    # où ils se lisaient comme des engagements contractuels. Ils viennent
    # désormais des réglages société, s'affichent hors des Conditions et portent
    # « (indicatif) ». Réglage VIDÉ ⇒ le délai n'apparaît nulle part.
    _delais = {"visite_technique": "", "installation": ""}
    try:
        from apps.parametres.models import CompanyProfile
        _prof = CompanyProfile.get(getattr(devis, "company", None))
        _delais = {
            "visite_technique": (
                getattr(_prof, "delai_visite_technique", "") or "").strip(),
            "installation": (
                getattr(_prof, "delai_installation", "") or "").strip(),
        }
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais sur un réglage (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        _delais = {"visite_technique": "", "installation": ""}

    # ── M7 — date de validité RÉELLE du devis (voir le commentaire du dict) ───
    _valid_until_txt = None
    _validity_days = None
    try:
        from ..utils.expiry import date_expiration
        _exp = date_expiration(devis)
        _cree = devis.date_creation.date() if devis.date_creation else None
        if _exp and _cree:
            _jours = (_exp - _cree).days
            if _jours > 0:
                _valid_until_txt = _exp.strftime("%d/%m/%Y")
                _validity_days = _jours
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais sur une date (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        _valid_until_txt = _validity_days = None

    client_name = f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()

    # Liste d'articles du format UNE PAGE. RÈGLE D'INTÉGRITÉ : une facture ne
    # mélange JAMAIS deux options — un devis à deux vraies options (réseau ET
    # hybride+batterie) rend UNE SEULE option, avec une mention discrète vers
    # la proposition complète. Devis mono-option ou sans options (pompage,
    # liste libre) : toutes les lignes, comme avant.
    # QF6 — le scénario choisi pilote aussi la liste une-page : « Sans » → les
    # lignes de l'option sans batterie, « Avec » → celles de l'option avec
    # batterie, « Les deux » → l'option retenue ci-dessous (jamais deux
    # onduleurs), sinon tout le devis (liste libre/pompage).
    # ── LANE CHOIX-AVEC (fondateur, 25/08/2026) — CHOIX FORCÉ = AVEC BATTERIE ─
    # « Pour toute question où l'on est obligé de choisir une seule config et
    # ne peut pas montrer les deux, choisis l'option AVEC batterie. » Une
    # page qui ne peut imprimer qu'UNE option montrait jusqu'ici toujours
    # l'OPTION SANS (M4, 19/08/2026) — un choix arbitraire, pas une règle du
    # fondateur. ``deux_options`` implique ``avec_ok`` (cf. sa définition
    # plus haut : ``sans_ok and avec_ok and alternative_declaree``), donc
    # l'option avec est TOUJOURS servable ici — bascule sans repli à ajouter.
    # La note « voir la proposition complète » et la vignette économie
    # suivent déjà ``onepage_branche`` dynamiquement (rien d'autre à changer
    # dans ce fichier) ; le texte figé de la note elle-même est corrigé côté
    # ``generate_devis_premium.page_onepage``.
    # CIQ302 — MÊME bascule que ``_all_rows`` (le une-page imprime les lignes
    # dont ``totaux_all`` est le total) : un C&I sert l'offre réseau seule.
    if option_servie == 'sans':
        onepage_source, onepage_branche = sans_items, 'sans'
    elif deux_options:
        onepage_source, onepage_branche = avec_items, 'avec'
    elif scenario == 'Avec batterie' and avec_ok:
        onepage_source, onepage_branche = avec_items, 'avec'
    elif scenario == 'Sans batterie' and has_reseau:
        onepage_source, onepage_branche = sans_items, 'sans'
    else:
        # Liste libre / pompage : les lignes du devis entier. La branche se
        # déduit alors de la composition RÉELLEMENT facturée — un panier qui
        # porte une batterie est l'option « avec », sinon « sans ».
        # QJR124 — MÊME liste que ``_all_rows`` ci-dessus (filtrée en amont).
        onepage_source = _items_libres
        onepage_branche = 'avec' if has_batterie else 'sans'
    onepage_note_batterie = deux_options

    # ── L-NIV (24/08/2026) — anticopie « niveau standard » ───────────────────
    # ``opts['kit_agrege']`` (posé par les vues PUBLIQUES d'après
    # ``ShareLink.niveau``, jamais par un appel interne) regroupe les lignes
    # fixation/câblage/protection en UNE ligne au sous-total EXACT, sur TOUS
    # les formats : le 3-pages résidentiel lit ``sans_items``/``avec_items``,
    # le une-page et les renderers industriel/commercial/agricole lisent
    # ``all_items`` — les trois passent donc par LA MÊME règle partagée avec la
    # charge utile JSON publique (``utils/anticopie``). Ce que le lien montre à
    # l'écran et ce que son PDF imprime ne peuvent plus diverger.
    #
    # PLACÉ ICI, LE PLUS TARD POSSIBLE, ET SUR DES LISTES SÉPARÉES : tous les
    # totaux (``totaux_sans``/``totaux_avec``/``totaux_all``) et toutes les
    # dérivations techniques (kWc, kWh batterie, coût onduleur, classification
    # d'options) sont déjà figés au-dessus, sur les lignes RÉELLES. La
    # dégradation ne change donc que l'affichage — jamais un chiffre.

    # Dérivation technique lue APRÈS ce point : figée AVANT la dégradation,
    # sur les lignes RÉELLES (une ligne « protection batterie » agrégée ne peut
    # donc pas déplacer d'un kWh la capacité publiée).
    _batterie_kwh_total = _battery_kwh_from_items(avec_items, _blob) or None
    # QJR609 — la capacité UTILE vendue (fiche, puis nominal × DoD, puis nom),
    # lue sur les lignes ORM de l'option AVEC par LA lecture de la garde web
    # (``capacite_batterie_des_lignes``). Elle ne sert QU'À la garde « cet
    # optimum décrit votre devis » ; le kWh IMPRIMÉ reste le nominal ci-dessus.
    from apps.ventes.domain.dimensionnement_devis import (
        capacite_batterie_des_lignes)
    _batterie_kwh_utile_vendue = capacite_batterie_des_lignes(
        devis, lignes=avec_lignes)
    if opts.get('kit_agrege'):
        sans_items = agreger_lignes_kit(sans_items)
        avec_items = agreger_lignes_kit(avec_items)
        onepage_source = agreger_lignes_kit(onepage_source)

    all_items = [
        {
            **{k: v for k, v in it.items()
               if k not in ("_produit_nom", "_sans_quantite")},
            "marque": it["marque"] or _parse_marque(
                it["designation"], it.get("_produit_nom", "")),
        }
        for it in onepage_source
        if it["quantite"] > 0 or it.get("_sans_quantite")
    ]
    return (_batterie_kwh_total, _batterie_kwh_utile_vendue, _delais,
            _valid_until_txt, _validity_days, all_items, avec_items,
            client_name, onepage_branche, onepage_note_batterie, sans_items)


def remises_et_puces(*, PUCE_AVEC_BATTERIE_DIFFEREE, _corrige, _scal,
                     all_items, avec_batterie_differee, avec_items, mode, opts,
                     sans_items, totaux_all, totaux_avec, totaux_sans, tva_pct,
                     watt):
    # ── QJRREM — CHAQUE LIGNE PORTE LA REMISE GLOBALE ───────────────────────
    # Demande fondateur (07/09/2026) : « la remise de 5 % est gardée partout et
    # s'applique aussi à chaque poste de la liste des composants, de
    # l'installation, de tout ». Les quatre clés ajoutées sont un fait
    # d'AFFICHAGE : les clés historiques (``prix_unit_ht``, ``prix_unit_ttc``)
    # gardent leur sens CATALOGUE, aucun total ne bouge, et la répartition vient
    # du noyau (``domain.argent.repartir_remise_par_ligne``) — jamais d'une
    # seconde règle écrite ici.
    #
    # PLACÉ ICI, LE PLUS TARD POSSIBLE : après le découpage d'options, après
    # l'agrégation kit (L-NIV) et après la construction de ``all_items``, donc
    # sur EXACTEMENT les lignes que chaque format imprime. La répartition se
    # fait PAR PANIER (chaque option a son propre Total HT net), avec le montant
    # de remise que la chaîne canonique a déjà arrêté pour CE panier — la somme
    # des lignes remisées d'un panier vaut donc son « Total HT » au centime
    # (invariant #10).
    #
    # Les listes sont RECOPIÉES : un équipement commun aux deux options est le
    # MÊME dict dans ``sans_items`` et ``avec_items``, et les deux paniers n'ont
    # pas forcément le même centime résiduel — sans copie, la seconde annotation
    # écraserait la première.
    def _annoter_remise(rows, totaux_du_panier):
        """Les quatre clés « après remise » de chaque ligne de ``rows``.

        ``remise`` nulle ⇒ les clés valent MOT POUR MOT les valeurs catalogue
        (aucun arrondi introduit) : un devis sans remise globale est rendu
        octet pour octet comme avant.
        """
        from core.money import quantize_mad as _q

        from apps.ventes.domain.argent import pu_remise as _pu_remise
        from apps.ventes.domain.argent import (
            repartir_remise_par_ligne as _repartir,
        )

        rows = [dict(r) for r in rows]
        if not rows:
            return rows
        remise = Decimal(str((totaux_du_panier or {}).get("remise") or 0))
        parts = _repartir(
            [_LigneArgentPdf(r, tva_pct) for r in rows], remise)
        for row, part in zip(rows, parts):
            qte = Decimal(str(row.get("quantite") or 0))
            pu_ht_cat = Decimal(str(row.get("prix_unit_ht") or 0))
            pu_ttc_cat = Decimal(str(row.get("prix_unit_ttc") or 0))
            if remise == 0 or part is None:
                pu_ht, total_ht = pu_ht_cat, pu_ht_cat * qte
                pu_ttc, total_ttc = pu_ttc_cat, pu_ttc_cat * qte
            else:
                taux = Decimal(str(row.get("taux_tva", tva_pct) or 0))
                coef = Decimal(1) + taux / Decimal(100)
                total_ht = part
                pu_ht = _pu_remise(part, qte)
                pu_ttc = _q(pu_ht * coef)
                total_ttc = _q(total_ht * coef)
            row["pu_ht_remise"] = float(pu_ht)
            row["total_ht_remise"] = float(total_ht)
            row["pu_ttc_remise"] = float(pu_ttc)
            row["total_ttc_remise"] = float(total_ttc)
        return rows

    sans_items = _annoter_remise(sans_items, totaux_sans)
    avec_items = _annoter_remise(avec_items, totaux_avec)
    all_items = _annoter_remise(all_items, totaux_all)

    # Puces des cartes d'option de la page 1 — générées depuis l'équipement
    # RÉEL de chaque option, jamais du texte boilerplate.
    #
    # QJR17 — CALCULÉES ICI, AVANT que ``_produit_nom`` soit retiré des items :
    # la classification panneau doit voir les MÊMES entrées que le total compté
    # (``panneaux_et_watt_lu`` : désignation ET nom du produit lié). Au point où
    # ces puces étaient construites, la clé interne avait déjà été effacée —
    # d'où les deux lectures divergentes du même document.
    # AMOT16 (C-AMOT-014/015) — rôle d'une ligne pour les puces : le rôle
    # STOCKÉ (STKCAT23) d'abord, le classifieur catalogue en repli.
    from apps.ventes.domain.catalogue import (
        _sans_accents as _sa_puce, classer_produit as _classer_puce)

    def _role_puce(r):
        role = r.get("role_devis")
        if role:
            return role
        return (_classer_puce(r.get("designation", ""))
                or _classer_puce(r.get("_produit_nom", "")))

    def _porte_structure_et_pose(rows):
        vendues = [r for r in rows if (r.get("quantite") or 0) > 0]
        structure = any(
            (_role_puce(r) or "").startswith("structure")
            or _role_puce(r) == "socle" for r in vendues)
        pose = any(
            _role_puce(r) == "installation"
            or "pose" in _sa_puce(r.get("designation", "")).split()
            or "main d'oeuvre" in _sa_puce(r.get("designation", ""))
            for r in vendues)
        return structure and pose

    def _bullets(rows, watt_option=None):
        # AMOT16 — la puissance de CETTE option (watt de ses lignes panneau),
        # jamais un watt scalaire partagé par les deux cartes.
        watt = watt_option
        out = []
        # QJR17 (b) — MÊME PRÉDICAT, MÊMES ENTRÉES que le total compté :
        # « Module PV 550 W » était compté comme panneau par le scalaire et
        # ABSENT de la puce du même document (celle-ci ne lisait que la
        # désignation, et via une seconde écriture de la règle).
        panels = [r for r in rows
                  if _is_panel(r["designation"], r.get("_produit_nom", ""))
                  and r["quantite"] > 0]
        if panels:
            n = int(sum(r["quantite"] for r in panels))
            # QJR17 (a) — puissance unitaire ILLISIBLE (``watt`` vaut None
            # depuis M3) : la puce imprimait littéralement « 16 panneaux
            # None W ». Même doctrine que la vignette du moteur legacy — on
            # écrit « N panneaux » tout court, jamais un défaut catalogue.
            out.append(f"{n} panneaux {watt} W" if watt else f"{n} panneaux")
        for r in rows:
            if r["quantite"] <= 0:
                continue
            d = r["designation"]
            # QJR-OFFGRID — l'onduleur AUTONOME est une puce comme les deux
            # autres : sans lui, un « Onduleur hors réseau » (qui comptait
            # jusqu'ici pour un onduleur réseau) DISPARAÎTRAIT de la puce.
            if (_is_reseau_inverter(d) or _is_hybrid_inverter(d)
                    or _is_offgrid_inverter(d)):
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {d}" if q > 1 else d)
        for r in rows:
            if _is_battery(r["designation"]) and r["quantite"] > 0:
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {r['designation']}" if q > 1 else r["designation"])
        if any("smart meter" in r["designation"].lower() and r["quantite"] > 0 for r in rows):
            out.append("Smart Meter + monitoring")
        # AMOT16 — seulement si l'option porte une ligne de structure ET une
        # ligne de pose (jamais une prestation que le devis ne vend pas).
        # Règles d'origine (devis envoyé avant AMOT16) : la puce d'hier.
        if not _corrige or _porte_structure_et_pose(rows):
            out.append("Structures + installation complète")
        return out[:6]

    if _corrige:
        sans_bullets = _bullets(sans_items, _scal.get("watt_sans") or watt)
        avec_bullets = _bullets(avec_items, _scal.get("watt_avec") or watt)
    else:
        # Règles d'origine : le watt scalaire du document sur les deux cartes.
        sans_bullets = _bullets(sans_items, watt)
        avec_bullets = _bullets(avec_items, watt)
    if avec_batterie_differee:
        # BAT-DIFF — la carte de l'option « avec » DIT que la batterie est à
        # ajouter (aucune puce batterie ne sort de ``_bullets`` : la ligne est
        # absente ou à quantité 0). Juste après panneaux + onduleur, dans la
        # limite des six puces que la carte affiche.
        avec_bullets = list(avec_bullets)
        avec_bullets.insert(min(2, len(avec_bullets)),
                            PUCE_AVEC_BATTERIE_DIFFEREE)
        avec_bullets = avec_bullets[:6]

    # Strip the internal helper key before handing items to the generator.
    for rows in (sans_items, avec_items):
        for r in rows:
            r.pop("_produit_nom", None)
            r.pop("_sans_quantite", None)

    inst_type = {
        "residentiel": "Résidentielle",
        # QX43 — industriel et commercial séparés (le libellé industriel ne dit
        # plus « / Commerciale »).
        "industriel": "Industrielle",
        "commercial": "Commerciale",
        "agricole": "Agricole",
    }.get(mode, "Résidentielle")

    # CIQ332 (D-CIQ-9) / CIQ340 (D-CIQ-10) — l'étude n'est plus forcée pour
    # le C&I : elle est INTÉGRÉE aux pages premium (commercial 3, industriel
    # 4) ; la forcer ici ne servait que le legacy « avec étude ».
    include_etude = opts['include_etude']
    return (all_items, avec_bullets, avec_items, include_etude, inst_type,
            sans_bullets, sans_items)


def conditions_et_liens(*, _totaux_seuls, devis, etude, lignes, mode, opts,
                        pdf_options, tva_pct):
    # ── PV77 — étude bancable (PV69/PV74) portée jusqu'au moteur de rendu ─────
    # ``Devis.etude_params['simulation']`` (P50/P90, ratio de performance et son
    # arbre de pertes) est recopiée SOUS UNE CLÉ DÉDIÉE ``etude['bankable']`` —
    # jamais fondue dans les clés historiques de l'étude (additivité stricte,
    # PV69) : la table 5 villes QX38 reste la source canonique des chiffres
    # affichés, le bloc bancable ne fait que S'AJOUTER à côté.
    # Devis SANS simulation → AUCUNE clé nouvelle, donc charge utile (et
    # proposition publique, qui appelle ce même builder) strictement identique à
    # aujourd'hui — exactement la discipline de l'annexe technique PV46 au repos.
    # Posé APRÈS ``include_etude`` : la présence du bloc ne peut donc jamais
    # décider d'une page en plus — le nombre de pages du PDF ne bouge pas.
    _simulation = (getattr(devis, "etude_params", None) or {}).get("simulation")
    if isinstance(_simulation, dict) and _simulation:
        # Copie défensive : le rendu ne doit jamais pouvoir muter l'étude
        # stockée sur le devis (le builder ne fait que LIRE — règle #4).
        etude["bankable"] = copy.deepcopy(_simulation)

    # Conditions de paiement par mode — réglage éditable de la société, repli
    # sur PAYMENT_TERMS_BY_MODE (défaut historique → PDF identique).
    from apps.ventes.utils.company_settings import payment_terms_for
    from apps.ventes.utils.echeancier import termes_paiement_devis
    # QJR623 — l'échéancier RÉEL du devis (``Devis.echeancier``, FG46) prime,
    # par la MÊME correspondance que la page publique (QJR622) ; le réglage
    # société n'est plus que le repli. Les pourcentages sont rendus en nombres
    # simples (int si entiers) : le dict de rendu reste sérialisable JSON.
    _termes = termes_paiement_devis(
        devis, payment_terms_for(getattr(devis, "company", None), mode),
        lignes, avec_dates=True)
    # AGR219 — la date prévue par créneau (solde « après récolte »), hors
    # des pourcentages ; posée dans ``data`` SEULEMENT si une tranche en porte.
    _dates_prevues = _termes.pop("dates_prevues", None)
    payment_terms = {cle: _pct_simple(val) for cle, val in _termes.items()}

    # D2/N60/N67/N59 — textes éditables du devis (en-têtes/CGV/validité/garanties
    # /BPA/tampon). SURCHARGES non vides seulement ; toute clé absente → le moteur
    # applique son littéral historique, donc le PDF reste byte-identique tant que
    # rien n'est édité. Repli silencieux sur {} si la table n'existe pas encore.
    #
    # SCA43 / NTPLT16 — la LECTURE de config est mémorisée PAR REQUÊTE (contextvar,
    # en amont du moteur) : le dict de surcharges est constant par société le temps
    # d'une requête, donc la liste des devis ne relit plus DocumentTemplates une
    # fois par devis (dé-N+1). Hors requête (Celery/PDF) le mémo est inactif → même
    # lecture qu'avant. Le RENDU ne change pas : ``doc_texts`` est bit-identique.
    _company = getattr(devis, "company", None)

    def _load_doc_texts():
        try:
            from apps.parametres.models_documents import DocumentTemplates
            return DocumentTemplates.get(company=_company).as_doc_texts()
        except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus (D-ENF22-BLE001)
            logger.warning("builder.build_quote_data._load_doc_texts : erreur ignorée (mode dégradé)", exc_info=True)
            return {}

    from core import request_cache
    doc_texts = request_cache.memoize(
        ("ventes.devis_doc_texts", getattr(_company, "id", None)),
        _load_doc_texts)

    # ERR-QJR668 / APDF12 / APDF14 — un devis envoyé ou signé imprime les
    # textes GELÉS à l'envoi, jamais les textes vifs édités depuis.
    doc_texts = _doc_texts_envoyes(devis, doc_texts)

    # DC1 — identité société (multi-tenant) : nom/RC/ICE/RIB/banque/adresse/tel/
    # couleur lus depuis CompanyProfile via le sélecteur parametres. Le moteur
    # premium retombe sur ses littéraux historiques (Taqinor) pour toute valeur
    # vide, donc un devis sans profil enrichi reste rendu strictement à
    # l'identique. Fuite multi-tenant corrigée : plus aucune identité en dur.
    entreprise = {}
    try:
        from apps.parametres.selectors import company_identity
        entreprise = company_identity(getattr(devis, "company", None))
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        entreprise = {}
    # APDF4 — logo TÉLÉVERSÉ de la société, sur le seul chemin de RENDU.
    entreprise = _entreprise_avec_logo(devis, entreprise, pdf_options)

    # ── SCA27 (complément) — site du tenant câblé au moteur résidentiel ───────
    # ``build_quote_data`` peuplait ``entreprise`` (identité) mais laissait le
    # renderer retomber sur ``taqinor.ma`` pour la ligne « site » du pied de page
    # ET la base des fiches produits, faisant fuiter le site du fondateur sur le
    # PDF d'un autre tenant. On passe désormais SON site quand il est renseigné :
    #   • ``site_url`` = forme d'affichage de son site (helios.ma) ;
    #   • ``links["produits"]`` = son site + '/produits' → ``theme.fiche_href``
    #     omet naturellement les fiches taqinor.ma (base non-taqinor) ; les autres
    #     liens pointent sur son site (aucun 404 vers le fondateur).
    # Site ABSENT → aucune clé posée : le renderer garde ses littéraux historiques
    # (taqinor.ma) et le rendu fondateur/sans-profil reste byte-identique (DC1).
    _tenant_site = _normalize_site_host(entreprise.get("site_web") or "")

    # ── QX6 — CTA de signature : lien tokenisé VERS LA VRAIE proposition ──────
    # L'ancien « taqinor.ma/signer/<ref> » (404) est remplacé par un ShareLink
    # tokenisé vers la page proposition publique (<base>/proposition/<token>).
    # APDF104 — cette page est hébergée par la PLATEFORME, jamais par le site
    # de la société : le lien (et son QR) est ``url_proposition`` (base
    # ``SITE_URL``), le MÊME que le courriel d'envoi, site renseigné ou non.
    # Lecture d'un ShareLink existant — cela NE CHANGE AUCUN statut. Repli
    # silencieux : sur toute erreur, le renderer garde son lien historique
    # (aucun PDF ne casse ici).
    links = {}
    try:
        from apps.ventes.models import ShareLink
        from apps.ventes.utils.client_links import url_proposition
        _pk = getattr(devis, "pk", None)
        # APRF3 — aucun lien de partage lu sur le chemin des totaux de liste.
        if _pk is not None and not _totaux_seuls:
            # ── QRP1/A5 — LE QR SUIT LE LIEN QUI SERT CE DOCUMENT ────────────
            # ``ShareLink.for_devis`` rend le lien à l'EXPIRATION LA PLUS
            # LOINTAINE, sans regarder son niveau : un PDF rendu au niveau
            # STANDARD (filigrané, nomenclature dégradée) pouvait donc porter
            # un QR vers la page CONFIANCE — la dégradation anticopie du
            # document annulée par son propre code-barres. Quand l'appelant
            # public passe le jeton du lien qu'il vient de résoudre
            # (``pdf_options['share_token']``), c'est CELUI-LÀ qui est imprimé.
            # Le jeton n'est pas cru sur parole : il doit désigner un ShareLink
            # de CE devis, encore valide. Sinon (appel ERP/Celery, jeton
            # inconnu, périmé, ou d'un autre devis) → repli ``for_devis``,
            # strictement le comportement historique.
            _share = None
            _tok = (opts or {}).get("share_token")
            if _tok:
                from django.utils import timezone as _tz
                _share = ShareLink.objects.filter(
                    devis=devis, token=_tok,
                    expires_at__gt=_tz.now()).first()
            if _share is None:
                # ADEV68 (C-ADEV-004) — un BROUILLON rendu (aperçu, /proposal,
                # generer-pdf) ne frappe ni n'imprime de lien « signer » : un
                # PDF de brouillon transmis par erreur ne mène à aucune page
                # signable. Seul un appelant qui PASSE le jeton d'un lien déjà
                # créé (envoi par e-mail, juste avant ``mark_devis_sent``) le
                # voit imprimé. Lecture du statut seulement (règle #4).
                if getattr(devis, "statut", None) == "brouillon":
                    raise _PasDeLienSigner()
                # AMOT13 (C-AMOT-010) — LECTURE PURE : le lien valide EXISTANT
                # (même règle que ``ShareLink.for_devis`` : non révoqué, non
                # expiré ou prolongé par le suivi), jamais créé ni prolongé
                # par un rendu (GET de liste, de détail, page publique,
                # /proposal). Aucun lien ⇒ aucun « signer » imprimé ; le geste
                # d'ENVOI, lui, frappe et prolonge (``views/devis_envoi``).
                from django.db.models import Q as _Q
                from django.utils import timezone as _tz_lien
                _share = (ShareLink.objects.filter(
                    _Q(expires_at__gt=_tz_lien.now())
                    | _Q(suivi_prolonge_le__isnull=False),
                    devis=devis, revoque_le__isnull=True)
                    .order_by('-expires_at').first())
                if _share is None:
                    raise _PasDeLienSigner()
            links["signer"] = url_proposition(devis, _share.token)
    except _PasDeLienSigner:
        links = {}
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        links = {}

    # ── QG7 — contact du CRÉATEUR du devis (nom + téléphone) ─────────────────
    # Le bloc contact du PDF affichait uniquement la société (donc toujours le
    # fondateur). On expose le créateur (Devis.created_by : first_name/last_name/
    # phone_number) pour que le client sache qui le suit. Repli sur le contact
    # société quand l'utilisateur n'a pas de téléphone. Données seulement.
    seller = {"nom": "", "telephone": ""}
    try:
        _creator = getattr(devis, "created_by", None)
        if _creator is not None:
            _fn = (getattr(_creator, "first_name", "") or "").strip()
            _ln = (getattr(_creator, "last_name", "") or "").strip()
            _full = (f"{_fn} {_ln}").strip()
            _tel = (getattr(_creator, "phone_number", "") or "").strip()
            if _full:
                seller["nom"] = _full
            # Repli sur le téléphone société quand l'utilisateur n'en a pas.
            seller["telephone"] = _tel or (entreprise.get("telephone") or "")
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus (D-ENF22-BLE001)
        logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
        seller = {"nom": "", "telephone": ""}

    # Texte TVA UNIQUE, partagé par toutes les notes/conditions des PDF.
    # QJR626 — il décrit les taux RÉELLEMENT portés par les lignes comptées
    # (le builder décide, les gabarits impriment) : plus de texte 10/20 figé
    # qui contredisait un tableau à 20 % partout.
    tva_note = tva_note_des_lignes(lignes, tva_pct,
                                   langue=opts['langue_sortie'])
    return (_dates_prevues, _tenant_site, doc_texts, entreprise, links,
            payment_terms, seller, tva_note)
