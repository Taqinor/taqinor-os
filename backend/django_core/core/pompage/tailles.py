"""AGR120 — trois tailles tirées du CATALOGUE + hectares irrigables (noyau
pur ``core.pompage``).

Avant : l'agricole n'avait aucune alternative (``DevisOffresTailles.jsx`` ne
sert que le résidentiel, inchangé ici) et la surface irrigable n'était jamais
calculée (``agronomy.py:34-38``, code mort).

* « Recommandée » = plus petite pompe CHIFFRABLE qui couvre le besoin RETENU
  (AGR116, déclaré d'abord) au mois critique — couverture ≥ 100 % + borne
  basse de la tolérance de conception (table AGR110), jamais un autre seuil.
* « Inférieure » = palier précédent du catalogue (couverture < 100 %
  affichée) ; « Supérieure » = palier suivant. Palier inexistant ⇒ taille
  omise AVEC motif. Défaut = Recommandée : jamais une variante « besoin
  agronomique plein » proposée par défaut (GIZ 2019 : éviter le
  surdimensionnement).
* Chaque taille porte sa composition (AGR119), son total TTC (si chaque ligne
  est chiffrée), son champ (AGR115), ses m³/j mois par mois (si courbe), sa
  couverture et ses hectares irrigables = m³/j livrés au mois critique ÷
  besoin par hectare de ce mois — seulement avec un besoin agronomique,
  « estimation » si l'ET0 est ``EST.``.
* Mode existante ⇒ une seule taille (pompe imposée), avec le motif.

Noyau PUR : stdlib seulement, aucune I/O.
"""
from __future__ import annotations

from core.pompage.champ import choisir_variateur, dimensionner_champ
from core.pompage.conception import NOM_POMPE_EXISTANTE, pompe_existante
from core.pompage.hydraulique import _flottant, debit_a_hmt
from core.pompage.hypotheses import valeur
from core.pompage.kit import composer_kit
from core.pompage.selection import _sortie_pompe, kw_pompe

CLES = ("inferieure", "recommandee", "superieure")
MOTIF_EXISTANTE = "pompe existante imposée : une seule taille"
MOTIF_AUCUNE = "aucune pompe chiffrable au catalogue"
MOTIF_INFERIEURE = ("aucun palier de pompe chiffrable sous la recommandée au "
                    "catalogue")
MOTIF_SUPERIEURE = ("aucun palier de pompe chiffrable au-dessus de la "
                    "recommandée au catalogue")
MOTIF_HA_VOLUME = ("besoin déclaré en volume : aucun besoin par hectare connu "
                   "(hectares calculés seulement sur un besoin agronomique)")


def _couverture(production, besoin, mois):
    """(couverture % par mois, couverture % au mois critique) — NON
    plafonnées ; ``None`` sans production."""
    serie = production.get("m3_jour_mois") if production else None
    if not serie or not besoin:
        return None, None
    mois_pct = [(round(serie[i] / besoin[i] * 100) if besoin[i] else None)
                for i in range(12)]
    critique = mois_pct[mois - 1] if mois else None
    return mois_pct, critique


def hectares_irrigables(production, mois, besoin_agronomique):
    """{valeur, base, motif} — m³/j livrés au mois critique ÷ besoin par ha
    de ce mois (``m3_ha_jour_mois`` d'AGR112)."""
    par_ha = (besoin_agronomique or {}).get("m3_ha_jour_mois")
    if not par_ha:
        return {"valeur": None, "base": None, "motif": MOTIF_HA_VOLUME}
    serie = production.get("m3_jour_mois") if production else None
    if not serie or not mois:
        return {"valeur": None, "base": None,
                "motif": "production non publiée : hectares non calculés"}
    besoin_ha = _flottant(par_ha[mois - 1])
    if not besoin_ha or besoin_ha <= 0:
        return {"valeur": None, "base": None,
                "motif": "besoin par hectare nul au mois critique"}
    est = besoin_agronomique.get("source_et0") == "EST."
    return {
        "valeur": round(serie[mois - 1] / besoin_ha, 1),
        "base": ("m³/j livrés au mois critique (%s) ÷ besoin agronomique "
                 "par hectare de ce mois (%s m³/ha/j)"
                 % (mois, round(besoin_ha, 1))),
        "motif": ("estimation : ET0 de la région « EST. » (AGR113)"
                  if est else None),
    }


def _taille(cle, *, pompe_sortie, champ, kit, besoin, mois,
            besoin_agronomique, motif=None):
    production = champ.get("production") if champ else None
    mois_pct, critique = _couverture(production, besoin, mois)
    return {
        "cle": cle,
        "pompe_produit": pompe_sortie.get("produit"),
        "pompe_nom": pompe_sortie.get("nom"),
        "puissance_kw": pompe_sortie.get("kw"),
        "champ_kwc": champ.get("kwc") if champ else None,
        "nb_panneaux": champ.get("nb_panneaux") if champ else None,
        "couverture_mois_critique_pct": critique,
        "total_ttc": kit.get("total_ttc") if kit else None,
        "prix_connu": bool(kit and kit["inclus"]
                           and all(x["prix_connu"] for x in kit["inclus"])),
        "retenue": cle == "recommandee",
        "motif": motif,
        "m3_jour_mois": (production.get("m3_jour_mois")
                         if production else None),
        "couverture_pct_mois": mois_pct,
        "ha_irrigables": hectares_irrigables(production, mois,
                                             besoin_agronomique),
        "champ": champ,
        "composition": kit,
    }


def proposer_tailles(*, mode_pompe="neuve", choix_pompe=None, plaque=None,
                     debit_declare_m3h=None, besoin_m3_jour_mois=None,
                     hmt_m=None, alimentation=None, type_pompe=None,
                     variateurs=(), panneau=None, mois_critique=None,
                     besoin_agronomique=None, profils_horaires=None,
                     e_d_kwh_kwc_mois=None, temperatures=None,
                     salissure_pct=None, agricole_pump_hours=None,
                     kit=None, coordonnees=None, reponse_pvgis=None):
    """AGR120 — ``{tailles, tailles_omises, defaut, alertes}``.

    * mode ``neuve`` : ``choix_pompe`` = sortie de
      :func:`core.pompage.selection.choisir_pompe` (ses ``paliers`` et
      ``index_palier``) ;
    * mode ``existante`` : ``plaque`` (+ ``debit_declare_m3h``) — une taille ;
    * ``kit`` : paramètres de :func:`core.pompage.kit.composer_kit` autres que
      ``mode_pompe``/``pompe``/``variateur``/``panneau``/``nb_panneaux``.

    ``tailles`` est ordonnée du plus petit au plus gros palier.
    """
    kit = dict(kit or {})
    commun = dict(profils_horaires=profils_horaires,
                  e_d_kwh_kwc_mois=e_d_kwh_kwc_mois,
                  temperatures=temperatures, salissure_pct=salissure_pct,
                  agricole_pump_hours=agricole_pump_hours,
                  mois_critique=mois_critique, coordonnees=coordonnees,
                  reponse_pvgis=reponse_pvgis)
    alertes = []

    if mode_pompe == "existante":
        res = pompe_existante(
            plaque=plaque, variateurs=variateurs, panneau=panneau,
            besoin_m3_jour_mois=besoin_m3_jour_mois, hmt_m=hmt_m,
            debit_declare_m3h=debit_declare_m3h, type_pompe=type_pompe,
            **commun)
        champ = res["champ"] or {}
        composition = composer_kit(
            mode_pompe="existante", variateur=champ.get("variateur"),
            panneau=panneau, nb_panneaux=champ.get("nb_panneaux"), **kit)
        mois = mois_critique or champ.get("mois_critique")
        taille = _taille("recommandee", pompe_sortie=dict(
            res["pompe"], nom=NOM_POMPE_EXISTANTE), champ=champ,
            kit=composition, besoin=besoin_m3_jour_mois, mois=mois,
            besoin_agronomique=besoin_agronomique, motif=MOTIF_EXISTANTE)
        return {"tailles": [taille],
                "tailles_omises": [{"cle": "inferieure",
                                    "motif": MOTIF_EXISTANTE},
                                   {"cle": "superieure",
                                    "motif": MOTIF_EXISTANTE}],
                "defaut": "recommandee", "alertes": alertes}

    paliers = list((choix_pompe or {}).get("paliers") or ())
    index = (choix_pompe or {}).get("index_palier")
    if not paliers or index is None:
        return {"tailles": [],
                "tailles_omises": [{"cle": c, "motif": MOTIF_AUCUNE}
                                   for c in ("recommandee", "inferieure",
                                             "superieure")],
                "defaut": None, "alertes": alertes}

    etape = choix_pompe.get("etape")
    tolerance = valeur("tolerance_conception_pct")
    seuil = 100 + tolerance.min
    cache = {}

    def evaluer(i):
        if i in cache:
            return cache[i]
        produit = paliers[i]
        kw, _source = kw_pompe(produit)
        fiche = produit.get("fiche") if isinstance(produit.get("fiche"),
                                                   dict) else {}
        choix_var = choisir_variateur(
            variateurs, kw_plaque=produit.get("pompe_kw"),
            cv=produit.get("pompe_cv"), alimentation=alimentation,
            courant_nominal_a=fiche.get("pompe_i_nominal_a"))
        champ = dimensionner_champ(
            besoin_m3_jour_mois=besoin_m3_jour_mois, hmt_m=hmt_m,
            panneau=panneau, variateurs_candidats=choix_var["candidats"],
            pompe=produit if etape == "courbe" else None, p_plaque_kw=kw,
            **commun)
        if etape != "courbe":
            champ = dict(champ, production=None)
        debit = (debit_a_hmt(produit["courbe_pompe"], hmt_m)
                 if etape == "courbe" else None)
        sortie = _sortie_pompe(produit, kw=kw, debit_hmt=debit, hmt=hmt_m)
        sortie["prix_ttc"] = produit.get("prix_ttc")
        composition = composer_kit(
            mode_pompe="neuve", pompe=sortie,
            variateur=champ.get("variateur"), panneau=panneau,
            nb_panneaux=champ.get("nb_panneaux"), **kit)
        mois = mois_critique or champ.get("mois_critique")
        cache[i] = (sortie, champ, composition, mois, choix_var)
        return cache[i]

    recommande = index
    if etape == "courbe":
        i = index
        while i < len(paliers):
            sortie, champ, _kit, mois, _var = evaluer(i)
            _mp, critique = _couverture(champ.get("production"),
                                        besoin_m3_jour_mois, mois)
            if critique is not None and critique >= seuil:
                recommande = i
                break
            i += 1
        else:
            alertes.append({
                "code": "aucune_taille_couvrante", "champ": "tailles",
                "message": ("Aucun palier chiffrable du catalogue ne couvre "
                            "le besoin au mois critique (≥ %s %%) : la "
                            "recommandée est la pompe choisie, couverture "
                            "affichée." % int(seuil))})

    tailles, omises = [], []
    for cle, j in (("inferieure", recommande - 1),
                   ("recommandee", recommande),
                   ("superieure", recommande + 1)):
        if j < 0 or j >= len(paliers):
            omises.append({"cle": cle, "motif": (MOTIF_INFERIEURE
                                                 if cle == "inferieure"
                                                 else MOTIF_SUPERIEURE)})
            continue
        sortie, champ, composition, mois, _var = evaluer(j)
        motif = None
        if etape != "courbe":
            motif = ("pompe sans courbe constructeur : couverture non "
                     "calculée (à confirmer sur la courbe)")
        tailles.append(_taille(cle, pompe_sortie=sortie, champ=champ,
                               kit=composition, besoin=besoin_m3_jour_mois,
                               mois=mois,
                               besoin_agronomique=besoin_agronomique,
                               motif=motif))
    return {"tailles": tailles, "tailles_omises": omises,
            "defaut": "recommandee", "alertes": alertes}
