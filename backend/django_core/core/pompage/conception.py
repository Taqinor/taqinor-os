"""AGR116 — débit de conception tiré du besoin RETENU (déclaré d'abord),
plafonné par le forage et l'autorisation ABH (noyau pur ``core.pompage``).

D-AGR-3 : le besoin retenu est le volume DÉCLARÉ (m³/j + mois), sinon le
besoin ACTUEL déclaré (débit actuel × heures ACTUELLES — jamais des heures
solaires), sinon le besoin FAO-56 d'AGR112, nommé « besoin agronomique plein ».
JAMAIS le maximum des deux : quand deux besoins existent, les deux sont servis
avec leur écart, SANS seuil (le 2× des kWh résidentiels n'est pas repris).

Débit de conception = besoin du mois critique ÷ heures-pic du profil PVGIS de ce
mois (Σ G / G_max). Plafond DUR = débit d'exploitation déclaré × part du réglage
AGR107 (s'il est saisi) et débit autorisé ABH. Contrôle de conception -5/+20 %
(bornes = la tolérance de la table AGR110, aucun autre seuil), jamais bloquant.
Autonomie = volume de réservoir DÉCLARÉ ÷ besoin (CAL155) : aucun bassin
dimensionné.

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O.
"""
from __future__ import annotations

from core.pompage.hydraulique import _flottant
from core.pompage.hypotheses import utilisees, valeur
from core.pompage.volumes import JOURS_PAR_MOIS, couverture_besoin_eau

NATURE_DECLARE = "declare"
NATURE_AGRONOMIQUE = "agronomique_plein"


def _alerte(code, champ, message):
    return {"code": code, "champ": champ, "message": message}


def _serie_declaree(volume_m3_jour, mois_irrigation):
    """12 valeurs m³/j : le volume déclaré sur les mois d'irrigation déclarés
    (1-12), 0 sur les autres ; sans mois déclarés, les 12 mois."""
    if mois_irrigation:
        mois = {int(m) for m in mois_irrigation if 1 <= int(m) <= 12}
    else:
        mois = set(range(1, 13))
    return [float(volume_m3_jour) if (i + 1) in mois else 0.0
            for i in range(12)]


def heures_pic(profil_horaire):
    """Heures-pic d'une journée type : Σ G / G_max (``None`` si profil nul)."""
    valeurs = [max(0.0, _flottant(g, 0.0) or 0.0) for g in profil_horaire or ()]
    pic = max(valeurs) if valeurs else 0.0
    if pic <= 0:
        return None
    return sum(valeurs) / pic


def besoin_retenu(*, volume_declare_m3_jour=None, mois_irrigation=None,
                  debit_actuel_m3h=None, heures_actuelles=None,
                  besoin_agronomique=None, provenance_declaree=None):
    """D-AGR-3 — le besoin RETENU et, s'il existe, l'AUTRE besoin connu.

    ``besoin_agronomique`` = la sortie de
    :func:`core.pompage.agronomie.besoin_agronomique` (ou ``None``).
    Rend ``{m3_jour_mois, nature, source_et0, autre_besoin, provenance}`` ;
    ``m3_jour_mois`` vaut ``None`` quand aucun besoin n'est connu."""
    declare = None
    detail = None
    volume = _flottant(volume_declare_m3_jour)
    if volume is not None and volume > 0:
        declare = _serie_declaree(volume, mois_irrigation)
        detail = "volume déclaré"
    else:
        debit = _flottant(debit_actuel_m3h)
        heures = _flottant(heures_actuelles)
        if debit and heures and debit > 0 and heures > 0:
            declare = _serie_declaree(debit * heures, mois_irrigation)
            detail = "débit actuel × heures actuelles de la pompe déclarée"

    agro = None
    source_et0 = None
    if besoin_agronomique and besoin_agronomique.get("m3_jour_mois"):
        agro = [float(v) for v in besoin_agronomique["m3_jour_mois"]]
        source_et0 = besoin_agronomique.get("source_et0")

    if declare is not None:
        provenance = dict(provenance_declaree or {"origine": "saisie",
                                                  "detail": None,
                                                  "date": None})
        if not provenance.get("detail"):
            provenance["detail"] = detail
        autre = None
        if agro is not None:
            autre = {
                "nature": NATURE_AGRONOMIQUE,
                "m3_jour_mois": [round(v, 1) for v in agro],
                "source_et0": source_et0,
                "ecart_pointe_m3_jour": round(max(agro) - max(declare), 1),
            }
        return {"m3_jour_mois": [round(v, 1) for v in declare],
                "nature": NATURE_DECLARE, "source_et0": None,
                "autre_besoin": autre, "provenance": provenance}
    if agro is not None:
        return {"m3_jour_mois": [round(v, 1) for v in agro],
                "nature": NATURE_AGRONOMIQUE, "source_et0": source_et0,
                "autre_besoin": None,
                "provenance": {"origine": "calculee",
                               "detail": "FAO-56 (AGR112)", "date": None}}
    return {"m3_jour_mois": None, "nature": None, "source_et0": None,
            "autre_besoin": None, "provenance": None}


def controle_conception(besoin_m3_jour_mois, production_m3_jour_mois,
                        mois):
    """Contrôle -5/+20 % au mois critique (bornes de la table AGR110).

    Rend ``{tolerance_pct, couverture_mois_critique_pct, statut,
    source_tolerance}`` ; statut ``conforme | couverture_insuffisante |
    surdimensionnement | non_verifiable``. Jamais bloquant."""
    tolerance = valeur("tolerance_conception_pct")
    sortie = {
        "tolerance_pct": tolerance.en_dict(),
        "couverture_mois_critique_pct": None,
        "statut": "non_verifiable",
        "source_tolerance": ("hypotheses_pompage.json › "
                             "tolerance_conception_pct (source secondaire)"),
    }
    if not mois or not besoin_m3_jour_mois or not production_m3_jour_mois:
        return sortie
    besoin = _flottant(besoin_m3_jour_mois[mois - 1])
    prod = _flottant(production_m3_jour_mois[mois - 1])
    if besoin is None or besoin <= 0 or prod is None:
        return sortie
    couverture = prod / besoin * 100
    sortie["couverture_mois_critique_pct"] = round(couverture)
    if couverture < 100 + tolerance.min:
        sortie["statut"] = "couverture_insuffisante"
    elif couverture > 100 + tolerance.max:
        sortie["statut"] = "surdimensionnement"
    else:
        sortie["statut"] = "conforme"
    return sortie


def conception(*, besoin, profils_horaires=None, agricole_pump_hours=None,
               debit_exploitation_m3h=None, provenance_exploitation=None,
               part_reglage_pct=None, debit_autorise_m3h=None,
               volume_autorise_m3_an=None, production_m3_jour_mois=None,
               niveau_eau_m=None, hmt_m=None, debit_actuel_m3h=None,
               pompe_actuelle_kw=None, volume_reservoir_m3=None):
    """AGR116 — débit de conception, plafonds, contrôle et alertes.

    ``besoin`` = la sortie de :func:`besoin_retenu`. ``production_m3_jour_mois``
    (AGR114, optionnelle) alimente le contrôle de conception, la couverture et
    le volume annuel simulé. Rend ``{besoin, conception, controle_conception,
    couverture_pct_mois, autonomie_reservoir_jours, alertes, hypotheses}``.
    """
    alertes = []
    cles = {"tolerance_conception_pct"}
    serie = besoin.get("m3_jour_mois") if besoin else None

    # Heures-pic par mois : profil PVGIS, sinon repli réglage société.
    heures = None
    source_heures = None
    if profils_horaires and len(profils_horaires) == 12:
        heures = [heures_pic(p) for p in profils_horaires]
        source_heures = "pvgis"
    else:
        repli = _flottant(agricole_pump_hours)
        if repli is not None and repli > 0:
            heures = [repli] * 12
            source_heures = "repli"

    mois = None
    debit_conception = None
    if serie and heures:
        meilleur = None
        for i in range(12):
            if not serie[i] or serie[i] <= 0 or not heures[i]:
                continue
            debit = serie[i] / heures[i]
            if meilleur is None or debit > meilleur:
                meilleur, mois = debit, i + 1
        debit_conception = meilleur
    elif serie is None:
        alertes.append(_alerte(
            "besoin_inconnu", "besoin.volume_declare_m3_jour",
            "Aucun besoin connu (ni volume déclaré, ni pompe actuelle, ni "
            "culture avec profil FAO-56) : débit de conception non calculé."))
    else:
        alertes.append(_alerte(
            "heures_pic_inconnues", "agricole_pump_hours",
            "Profil PVGIS indisponible et heures de pompage du réglage "
            "société non renseignées : débit de conception non calculé."))

    # Plafonds durs : forage (× part du réglage AGR107) et autorisation ABH.
    exploitation = _flottant(debit_exploitation_m3h)
    part = _flottant(part_reglage_pct)
    autorise = _flottant(debit_autorise_m3h)
    candidats = []
    if exploitation is not None and exploitation > 0:
        candidats.append(("forage", exploitation * part / 100.0
                          if part is not None and part > 0 else exploitation))
    if autorise is not None and autorise > 0:
        candidats.append(("abh", autorise))
    plafond = min(candidats, key=lambda c: c[1]) if candidats else None
    atteint = bool(plafond and debit_conception is not None
                   and debit_conception > plafond[1])
    debit_retenu = debit_conception
    if atteint:
        debit_retenu = plafond[1]
        if plafond[0] == "forage":
            alertes.append(_alerte(
                "plafond_forage", "debit_exploitation_m3h",
                "Le besoin exige %.1f m³/h mais le forage n'en donne que "
                "%.1f m³/h : débit plafonné, le besoin du mois critique ne "
                "sera pas couvert." % (debit_conception, plafond[1])))
        else:
            alertes.append(_alerte(
                "plafond_abh", "debit_autorise_m3h",
                "Le besoin exige %.1f m³/h au-delà du débit autorisé ABH "
                "(%.1f m³/h) : débit plafonné."
                % (debit_conception, plafond[1])))

    # Volume annuel simulé vs volume autorisé ABH.
    livre = None
    if production_m3_jour_mois:
        livre = [_flottant(v, 0.0) or 0.0 for v in production_m3_jour_mois]
    elif debit_retenu is not None and heures:
        livre = [debit_retenu * (h or 0.0) for h in heures]
    volume_autorise = _flottant(volume_autorise_m3_an)
    if livre is not None and volume_autorise is not None \
            and volume_autorise > 0:
        annuel = sum(v * j for v, j in zip(livre, JOURS_PAR_MOIS))
        if annuel > volume_autorise:
            alertes.append(_alerte(
                "volume_autorise_depasse", "volume_autorise_m3_an",
                "Volume annuel simulé %.0f m³ supérieur au volume autorisé "
                "ABH (%.0f m³)." % (annuel, volume_autorise)))

    # D-AGR-4 — relevé du point d'eau requis.
    if niveau_eau_m is None or exploitation is None:
        manque = [nom for nom, val in (("niveau d'eau", niveau_eau_m),
                                       ("débit du forage", exploitation))
                  if val is None]
        alertes.append(_alerte(
            "releve_point_eau_requis",
            "niveau_eau_m" if niveau_eau_m is None else "debit_exploitation_m3h",
            "Relevé du point d'eau requis avant le devis (D-AGR-4) : %s "
            "inconnu." % " et ".join(manque)))

    # Incohérence physique de la pompe actuelle déclarée : même à 100 % de
    # rendement, Q × HMT × 2,725 Wh/m³/m dépasserait sa puissance (borne
    # PHYSIQUE, aucun seuil inventé).
    q_actuel = _flottant(debit_actuel_m3h)
    h = _flottant(hmt_m)
    p_actuelle = _flottant(pompe_actuelle_kw)
    if q_actuel and h and p_actuelle and q_actuel > 0 and h > 0 \
            and p_actuelle > 0:
        cles.add("energie_hydraulique_wh_par_m3_m")
        p_hydraulique_kw = (q_actuel * h
                            * valeur("energie_hydraulique_wh_par_m3_m") / 1000)
        if p_hydraulique_kw > p_actuelle:
            alertes.append(_alerte(
                "debit_actuel_incoherent", "debit_actuel_m3h",
                "Débit actuel déclaré %.1f m³/h à %.0f m : %.1f kW "
                "hydrauliques, impossible pour une pompe de %.1f kW — "
                "vérifier le débit." % (q_actuel, h, p_hydraulique_kw,
                                        p_actuelle)))

    # Couverture mois par mois (production ÷ besoin, NON plafonnée).
    couverture = None
    if production_m3_jour_mois and serie:
        couverture = [
            (round(_flottant(production_m3_jour_mois[i], 0.0) / serie[i] * 100)
             if serie[i] else None) for i in range(12)]

    controle = controle_conception(serie, production_m3_jour_mois, mois)
    if controle["statut"] in ("couverture_insuffisante", "surdimensionnement"):
        alertes.append(_alerte(
            controle["statut"], "conception.debit_conception_m3h",
            "Couverture au mois critique : %s %% (tolérance -5/+20 %%)."
            % controle["couverture_mois_critique_pct"]))

    # Autonomie d'un réservoir DÉCLARÉ (CAL155) — aucun bassin dimensionné.
    autonomie = {"valeur": None, "motif": "aucun réservoir déclaré"}
    reservoir = _flottant(volume_reservoir_m3)
    if reservoir is not None and reservoir > 0:
        if serie:
            res = couverture_besoin_eau(
                besoin_m3_mois=[v * j for v, j in zip(serie, JOURS_PAR_MOIS)],
                volume_reservoir_m3=reservoir)
            autonomie = {"valeur": res["autonomie_jours"], "motif": None}
        else:
            autonomie = {"valeur": None, "motif": "besoin inconnu"}

    return {
        "besoin": besoin,
        "conception": {
            "mois_critique": mois,
            "debit_conception_m3h": (round(debit_retenu, 1)
                                     if debit_retenu is not None else None),
            "debit_besoin_m3h": (round(debit_conception, 1)
                                 if debit_conception is not None else None),
            "source_heures_pic": source_heures,
            "plafonds": {
                "debit_exploitation_m3h": exploitation,
                "provenance_exploitation": provenance_exploitation,
                "part_reglage_pct": part,
                "debit_autorise_m3h": autorise,
                "plafond_retenu_m3h": (round(plafond[1], 1)
                                       if plafond else None),
                "atteint": atteint,
            },
        },
        "controle_conception": controle,
        "couverture_pct_mois": couverture,
        "autonomie_reservoir_jours": autonomie,
        "alertes": alertes,
        "hypotheses": utilisees(cles),
    }


# ═══════════════════════════════════════════════════════════════════════════
# AGR118 — mode ``existante`` (D-AGR-7) : la pompe déjà dans le forage est
# CONSERVÉE ; variateur et champ dimensionnés sur sa PLAQUE.
# ═══════════════════════════════════════════════════════════════════════════

NOM_POMPE_EXISTANTE = "Pompe existante conservée"


def _norme_plaque(plaque):
    plaque = plaque or {}
    kw = _flottant(plaque.get("kw"))
    cv = _flottant(plaque.get("cv"))
    tension = _flottant(plaque.get("tension_v"))
    phases = _flottant(plaque.get("phases"))
    courant = _flottant(plaque.get("courant_a"))
    return {"kw": kw if kw and kw > 0 else None,
            "tension_v": int(tension) if tension else None,
            "phases": int(phases) if phases else None,
            "cv": cv if cv and cv > 0 else None,
            "courant_a": courant if courant and courant > 0 else None}


def pompe_existante(*, plaque, variateurs, panneau=None,
                    besoin_m3_jour_mois=None, hmt_m=None,
                    debit_declare_m3h=None, type_pompe=None,
                    profils_horaires=None, e_d_kwh_kwc_mois=None,
                    temperatures=None, salissure_pct=None,
                    agricole_pump_hours=None, mois_critique=None,
                    coordonnees=None, reponse_pvgis=None):
    """AGR118 — pompe existante : aucune ligne pompe, variateur sur la plaque.

    * ``plaque`` : ``{kw, tension_v, phases, cv, courant_a}`` (saisie ou
      relevé de visite D-AGR-4) ;
    * variateur = :func:`core.pompage.champ.choisir_variateur` sur le kW
      PLAQUE, parmi les variateurs dont la SORTIE (tension, phases) égale la
      plaque (:func:`core.pompage.selection.variateurs_compatibles_plaque`) ;
      plaque triphasée 220 V sans fiche publiant cette sortie ⇒ variateur
      220 V proposé avec l'alerte « compatibilité à vérifier sur la fiche » ;
    * kW plaque absent (CV seul) ⇒ alerte « kW de plaque à relever », AUCUN
      variateur choisi : la conversion 0,7355 ne sert qu'à l'affichage ;
    * champ = AGR115 ; production : courbe inconnue ⇒ ``None``, sauf débit
      DÉCLARÉ de la pompe actuelle ⇒ estimation étiquetée (AGR114).

    Rend ``{pompe, variateur, prix_a_renseigner, puissance_retenue, champ,
    production, alertes, hypotheses}`` (formes du contrat
    ``etude_pompage_preview.json``).
    """
    from core.pompage.champ import (
        choisir_variateur, dimensionner_champ, fiche_saisie,
        phases_sortie_variateur, tension_sortie_variateur,
    )
    from core.pompage.selection import (
        TENSION_MONO_V, TENSION_TRI_V, prix_connu,
        variateurs_compatibles_plaque,
    )

    alertes = []
    cles = {"cv_vers_kw"}
    p = _norme_plaque(plaque)
    phases = p["phases"]
    tension = p["tension_v"]
    if tension is None and phases is not None:
        tension = TENSION_MONO_V if phases == 1 else TENSION_TRI_V
    alimentation = {1: "mono", 3: "tri"}.get(phases)

    affiche_kw = p["kw"]
    if affiche_kw is None and p["cv"]:
        affiche_kw = p["cv"] * valeur("cv_vers_kw")
    affiche_cv = p["cv"] or (p["kw"] / valeur("cv_vers_kw")
                             if p["kw"] else None)

    pompe = {
        "mode": "existante", "produit": None, "nom": NOM_POMPE_EXISTANTE,
        "placeholder": False, "classement": None, "type_pompe": type_pompe,
        "alimentation": alimentation, "kw": p["kw"], "tension_v": tension,
        "plaque": dict(p), "courbe": None, "point_fonctionnement": None,
        "debit_a_hmt_m3h": None, "prix_connu": None,
    }
    variateur = {"produit": None, "nom": None, "kw": None, "tension_v": None,
                 "phases_sortie": None, "fiche_saisie": False,
                 "prix_connu": False, "motif": None}
    candidats = []

    if p["kw"] is None:
        motif = ("kW de plaque à relever (visite « relevé du point d'eau », "
                 "D-AGR-4) : variateur non choisi")
        alertes.append(_alerte(
            "kw_plaque_a_relever", "plaque.kw",
            "kW de plaque de la pompe existante à relever (D-AGR-4) : le "
            "variateur n'est pas choisi sur le CV (conversion × 0,7355 "
            "affichée seulement)."))
        variateur["motif"] = motif
    else:
        compatibles, a_verifier = variateurs_compatibles_plaque(
            variateurs, tension_v=tension, phases=phases)
        choix = choisir_variateur(
            compatibles, kw_plaque=p["kw"], tension_v=tension, phases=phases,
            courant_nominal_a=p["courant_a"])
        if choix["variateur"] is None and a_verifier:
            choix = choisir_variateur(
                a_verifier, kw_plaque=p["kw"], tension_v=tension,
                phases=phases, courant_nominal_a=p["courant_a"])
            if choix["variateur"] is not None:
                alertes.append(_alerte(
                    "compatibilite_a_verifier", "variateur.fiche",
                    "Plaque triphasée %d V : compatibilité à vérifier sur la "
                    "fiche du variateur %s (sortie triphasée %d V non "
                    "publiée)." % (tension, choix["variateur"].get("nom"),
                                   tension)))
        alertes.extend(a for a in choix["alertes"]
                       if a["code"] != "kw_plaque_a_relever")
        candidats = choix["candidats"]
        retenu = choix["variateur"]
        if retenu is not None:
            variateur.update({
                "produit": retenu.get("id"), "nom": retenu.get("nom"),
                "kw": _flottant(retenu.get("pompe_kw")),
                "tension_v": tension_sortie_variateur(retenu),
                "phases_sortie": phases_sortie_variateur(retenu),
                "fiche_saisie": fiche_saisie(retenu),
                "prix_connu": prix_connu(retenu)})
            if not variateur["fiche_saisie"]:
                variateur["motif"] = ("fiche variateur à saisir : tension et "
                                      "phases de sortie non vérifiées sur la "
                                      "fiche")
        else:
            variateur["motif"] = choix["motif"]

    champ = None
    production = None
    if panneau is not None:
        champ = dimensionner_champ(
            besoin_m3_jour_mois=besoin_m3_jour_mois, hmt_m=hmt_m,
            panneau=panneau, variateurs_candidats=candidats, pompe=None,
            p_plaque_kw=p["kw"], debit_declare_m3h=debit_declare_m3h,
            profils_horaires=profils_horaires,
            e_d_kwh_kwc_mois=e_d_kwh_kwc_mois, temperatures=temperatures,
            salissure_pct=salissure_pct,
            agricole_pump_hours=agricole_pump_hours,
            mois_critique=mois_critique, coordonnees=coordonnees,
            reponse_pvgis=reponse_pvgis)
        production = champ["production"]
        alertes.extend(champ["alertes"])
    if production is None:
        alertes.append(_alerte(
            "production_omise", "production",
            "Pompe existante sans courbe ni débit déclaré : production d'eau "
            "omise (jamais de m³/jour sans courbe)."))

    return {
        "pompe": pompe, "variateur": variateur, "prix_a_renseigner": [],
        "puissance_retenue": {
            "kw": round(affiche_kw, 2) if affiche_kw else None,
            "cv": round(affiche_cv, 1) if affiche_cv else None},
        "champ": champ, "production": production, "alertes": alertes,
        "hypotheses": utilisees(cles),
    }
