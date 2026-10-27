"""Une-page agricole — cartes du résumé pompage (AGR313, déplacées par AGC2).

Le gabarit du une-page reste au moteur legacy (``legacy_onepage.py``) : ce
module ne rend QUE les cartes du résumé pompage, lues dans
``synthese_agricole`` (mêmes formats que le 3 pages ; une carte sans valeur
est OMISE). ``g`` est le module ``generate_devis_premium`` du rendu en cours
(ses globales ``_L``, ``ETUDE``, ``KWC``… sont celles de CE devis).
"""
from .. import i18n_labels, i18n_labels_agricole
from .synthese import debit_declare_sans_courbe


def _lg(g):
    """La langue du rendu en cours (repli français)."""
    return g.LANGUE_SORTIE if g.LANGUE_SORTIE in ("fr", "en", "ar") else "fr"


def _carte_eau(g, eau):
    """La carte « Eau / jour ». AMOT56 (D-AMOT-7 = a) — m³/jour sur débit
    DÉCLARÉ : la carte le dit. AMOT65 — « estimation » quand la synthèse le
    sert (étiquettes du noyau). AGQ3 (D-AGQ-2) — mois de conception nommé
    (la phrase longue reste au héro du 3 pages, AGC12). AGC2 — aucun
    « (hypothèse) » : rien d'incertain imprimé au-delà de « estimation »."""
    m3j, hrs = eau.get("m3_jour"), eau.get("heures_pompage")
    if m3j is None or hrs is None:
        return None
    if debit_declare_sans_courbe(
            {"etude": g.ETUDE, "all_items": g.SANS_ITEMS + g.AVEC_ITEMS}):
        est = (f"{g._L('estimation')} &#183; "
               f"{g._L('lg_debit_declare_par_vous')}, ")
    elif eau.get("estimation"):
        est = f"{g._L('estimation')}, "
    else:
        est = ""
    # AGC12 — libellé COURT (le une-page n'a qu'une étiquette de carte) :
    # « 4,4 h/j en novembre » (mois de conception servi) ; la phrase longue
    # reste au héro du 3 pages.
    lg = _lg(g)
    h = g._fdec_fr(hrs, 1)
    mois = eau.get("mois_conception")
    if isinstance(mois, int) and 1 <= mois <= 12:
        heures = i18n_labels_agricole.libelle("agr_op_heures_mois", lg).format(
            heures=h, mois=i18n_labels.libelle(f"agr_mois_{mois}", lg))
    else:
        heures = i18n_labels_agricole.libelle("agr_op_heures", lg).format(
            heures=h)
    return (f"{g._L('eau_jour')} &#8212; {est}{heures}",
            f"&#8776; {g.fnum(m3j)} m&#179;",
            g._ancre_figure("pompe_volume_m3_jour", g.fnum(m3j)))


def _carte_besoin_livre(g, bvl):
    """La carte « besoin / livré » du mois le plus serré — seulement si la
    synthèse la sert."""
    if not isinstance(bvl, dict):
        return None
    try:
        m = (bvl.get("mois") or [])[int(bvl.get("mois_le_plus_serre")) - 1]
    except (TypeError, ValueError, IndexError):
        return None
    if not isinstance(m, dict) or m.get("besoin_m3_jour") is None \
            or m.get("livre_m3_jour") is None:
        return None
    return (g._L("besoin_livre_mois_serre"),
            f"{g.fnum(m['besoin_m3_jour'])} / "
            f"{g.fnum(m['livre_m3_jour'])} m&#179;")


def cartes_pompage(g, synthese):
    """Les cartes du résumé pompage du une-page, dans l'ordre : pompe, HMT,
    débit à la HMT, eau / jour, besoin / livré, champ PV."""
    eau = synthese.get("eau") or {}
    pompe = synthese.get("pompe") or {}
    cellules = []
    pcv, pkw = pompe.get("cv"), pompe.get("kw")
    if pcv is not None:
        cellules.append((
            g._L("puissance_pompe"),
            f"{g._fdec_fr(pcv)} CV ({g._fdec_fr(pkw)} kW)" if pkw is not None
            else f"{g._fdec_fr(pcv)} CV"))
    hmt = eau.get("hmt_m")
    if hmt is not None:
        cellules.append((i18n_labels_agricole.libelle("agr_op_hmt", _lg(g)),
                         f"{g._fdec_fr(hmt)} m",
                         g._ancre_figure("pompe_hmt_m", hmt)))
    dq = eau.get("debit_hmt_m3h")
    if dq is not None and hmt is not None:
        cellules.append(
            (g._L("debit_a_hmt").format(hmt=g._fdec_fr(hmt)),
             f"{g._fdec_fr(dq, 1)} m&#179;/h",
             g._ancre_figure("pompe_debit_m3h", g._fdec_fr(dq, 1))))
    for carte in (_carte_eau(g, eau),
                  _carte_besoin_livre(g, synthese.get("besoin_vs_livre"))):
        if carte is not None:
            cellules.append(carte)
    if g.KWC > 0:
        cellules.append((g._L("champ_pv"), f"{g.kwc_fr(g.KWC)} kWc",
                         g._ancre_figure("puissance_kwc", g.kwc_fr(g.KWC))))
    return cellules
