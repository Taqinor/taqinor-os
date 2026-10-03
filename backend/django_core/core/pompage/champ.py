"""AGR115 — champ PV du pompage dimensionné sur l'énergie du MOIS CRITIQUE,
chaînes vérifiées contre la fenêtre du variateur, variateur choisi sur la
PLAQUE de la pompe (noyau pur ``core.pompage``).

Avant (``solar.js:3181-3189``) : panneaux = max(2, ⌈1,4 × kW × 1000 / 710⌉),
sans irradiation ni contrôle de tension — une pompe 4 CV tri recevait 6
panneaux (Vmp 242 V) sous les 250 V minimum de son variateur (C5-02) ; et le
variateur = plus petit kW ≥ CV × 0,7355, si bien qu'une 3 CV mono (2,21 kW)
n'avait « AUCUN variateur » au lieu du 2,2 kW de sa plaque (C5-A1/C1-X2).

Ici :

* :func:`choisir_variateur` — plus petit kW ≥ kW PLAQUE de la pompe, tension
  et phases de sortie compatibles, courant de sortie ≥ courant nominal quand
  les deux sont publiés ; CV × 0,7355 (table AGR110) SEULEMENT sans kW de
  plaque, avec l'alerte « kW de plaque à relever ». Aucune plage VEICHI codée :
  tout vient de la fiche saisie (AGR101). ``selection.selection_variateur``
  (parité CAL158) reste intacte jusqu'à AGR132.
* :func:`kwc_depart` — E = 2,725 × V × HMT / 1000 (kWh/j, table AGR110) ;
  kWc = E / (η × E_d) ; η = rendement pompe × rendement MPPT PUBLIÉS, sinon le
  ``rendement_groupe`` « EST. » de la table AGR110.
* :func:`dimensionner_champ` — le plus petit nombre de panneaux dont la
  production AGR114 couvre le besoin RETENU au mois critique, puis la chaîne
  série par ``core.electrique.chaines.fenetre_admissible`` (températures TMY
  du site fournies par l'appelant, sinon les replis MENTIONNÉS du noyau
  électrique ``TEMP_FROID_DEFAUT_C`` / ``TEMP_CHAUD_DEFAUT_C``) ; chaîne trop
  longue ⇒ chaînes parallèles si le courant MPPT le permet, sinon variateur
  suivant. Variateur sans fiche ⇒ alerte « chaîne PV non vérifiable », jamais
  un blocage muet. Ratio kWc/kW hors de la bande AGR110 ⇒ alerte seule.

Toutes les entrées sont des dicts SIMPLES fournis par l'appelant (forme
``element_produits_pompage`` de ``stock/contract_samples/produit_pompage.json``
pour pompes et variateurs ; champs de ``core.electrique.types.SpecModule`` pour
le panneau) : le noyau ne lit rien.

Noyau PUR : stdlib + ``core.electrique`` seulement, aucune I/O.
"""
from __future__ import annotations

import math

from core.electrique.chaines import fenetre_admissible
from core.electrique.types import (
    TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C, SpecModule, SpecOnduleur,
)
from core.pompage.hydraulique import _flottant
from core.pompage.hypotheses import utilisees, valeur
from core.pompage.selection import TENSION_MONO_V, TENSION_TRI_V, tension_produit
from core.pompage.volumes import production_mensuelle

ROLE_VARIATEUR = "variateur_pompage"

#: Mention qui accompagne les températures de repli du noyau électrique quand
#: l'appelant ne fournit pas les températures TMY du site.
MENTION_TEMPERATURES_REPLI = (
    "températures de référence du noyau électrique (%s °C / %s °C, "
    "core/electrique/types.py), non sourcées : températures TMY du site "
    "absentes" % (int(TEMP_FROID_DEFAUT_C), int(TEMP_CHAUD_DEFAUT_C)))

#: Garde de BOUCLE de la recherche du nombre de panneaux (pas une valeur de
#: dimensionnement) : au-delà, le besoin est déclaré non couvert.
_ITERATIONS_MAX = 500

_CHAMPS_FENETRE = ("ond_mppt_v_min", "ond_mppt_v_max", "ond_v_max_abs")


def _alerte(code, champ, message):
    return {"code": code, "champ": champ, "message": message}


def _fr(nombre, chiffres=1):
    """« 2,2 » — nombre à la française, sans zéro inutile."""
    if nombre is None:
        return "?"
    texte = ("%%.%df" % chiffres) % nombre
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def prix_connu(produit):
    """Un prix de vente est-il saisi ? ``prix_connu`` (forme du sélecteur
    AGR103) d'abord, sinon ``prix_vente`` > 0."""
    if produit is None:
        return False
    if "prix_connu" in produit:
        return bool(produit.get("prix_connu"))
    return (_flottant(produit.get("prix_vente"), 0.0) or 0.0) > 0


def _cle_tri(produit, kw):
    return (kw, _flottant(produit.get("prix_vente"), 0.0) or 0.0,
            produit.get("id") or 0)


def _est_variateur(produit):
    role = produit.get("role_pompage")
    if role:
        return role == ROLE_VARIATEUR
    nom = (produit.get("nom") or "").lower()
    return "variateur" in nom and "afficheur" not in nom


def _fiche(produit):
    fiche = (produit or {}).get("fiche")
    return fiche if isinstance(fiche, dict) else {}


def fiche_saisie(variateur):
    """La fiche variateur publie-t-elle au moins une borne de tension ?"""
    fiche = _fiche(variateur)
    return any(_flottant(fiche.get(c)) for c in _CHAMPS_FENETRE)


def tension_sortie_variateur(variateur):
    """Tension de SORTIE (V) : ``var_v_sortie_v`` de la fiche, sinon la
    tension du produit (champ ``tension_v`` ou nom)."""
    v = _flottant(_fiche(variateur).get("var_v_sortie_v"))
    if v:
        return int(v)
    return tension_produit(variateur)


def phases_sortie_variateur(variateur):
    """Phases de sortie publiées (``ond_phases``) ou ``None``."""
    phases = _flottant(_fiche(variateur).get("ond_phases"))
    return int(phases) if phases else None


def _tension_alim(alimentation):
    if alimentation == "mono":
        return TENSION_MONO_V
    if alimentation == "tri":
        return TENSION_TRI_V
    return None


def _phases_alim(alimentation):
    return {"mono": 1, "tri": 3}.get(alimentation)


def choisir_variateur(variateurs, *, kw_plaque=None, cv=None, tension_v=None,
                      phases=None, alimentation=None, courant_nominal_a=None):
    """AGR115 — le plus petit variateur pricé dont le kW ≥ kW PLAQUE.

    ``kw_plaque`` : ``Produit.pompe_kw`` ou plaque saisie. Sans lui, ``cv`` ×
    ``cv_vers_kw`` (table AGR110) avec l'alerte « kW de plaque à relever ».
    Tension voulue = ``tension_v``, sinon déduite de ``alimentation`` (220 V
    mono, 380 V tri — CLAUDE.md « tension 220/380 assortie »). Phases voulues =
    ``phases``, sinon déduites de ``alimentation`` ; contrôlées seulement si la
    fiche publie ``ond_phases``. Courant : ``var_i_sortie_nominal_a`` ≥
    ``courant_nominal_a`` quand les deux sont publiés.

    Rend ``{variateur, kw_requis, source_kw, tension_v, candidats, sans_prix,
    alertes, motif, hypotheses}`` ; ``candidats`` = variateurs compatibles,
    pricés, de kW ≥ requis, du plus petit au plus gros (le premier est
    ``variateur`` — les suivants servent au « variateur suivant » d'AGR115).
    """
    alertes = []
    cles = set()
    kw = _flottant(kw_plaque)
    source_kw = None
    if kw is not None and kw > 0:
        source_kw = "plaque"
    else:
        kw = None
        cv_val = _flottant(cv)
        if cv_val is not None and cv_val > 0:
            cles.add("cv_vers_kw")
            kw = cv_val * valeur("cv_vers_kw")
            source_kw = "cv"
            alertes.append(_alerte(
                "kw_plaque_a_relever", "plaque.kw",
                "kW de plaque à relever : variateur choisi sur %s CV × 0,7355 "
                "= %s kW, en attendant la plaque de la pompe."
                % (_fr(cv_val), _fr(kw, 2))))
    tension = _flottant(tension_v)
    tension = int(tension) if tension else _tension_alim(alimentation)
    phases_voulues = phases or _phases_alim(alimentation)
    courant = _flottant(courant_nominal_a)

    sortie = {"variateur": None, "kw_requis": (round(kw, 2) if kw else None),
              "source_kw": source_kw, "tension_v": tension, "candidats": [],
              "sans_prix": [], "alertes": alertes, "motif": None,
              "hypotheses": utilisees(cles)}
    if kw is None:
        sortie["motif"] = ("puissance de la pompe inconnue (ni kW de plaque, "
                           "ni CV) : variateur non choisi")
        return sortie

    compatibles = []
    for produit in variateurs or ():
        if not _est_variateur(produit):
            continue
        pk = _flottant(produit.get("pompe_kw"), 0.0)
        if not pk or pk <= 0:
            continue
        if tension is not None and tension_sortie_variateur(produit) != tension:
            continue
        ph = phases_sortie_variateur(produit)
        if phases_voulues and ph is not None and ph != phases_voulues:
            continue
        i_sortie = _flottant(_fiche(produit).get("var_i_sortie_nominal_a"))
        if courant and i_sortie and i_sortie < courant:
            continue
        compatibles.append((produit, pk))
    compatibles.sort(key=lambda c: _cle_tri(c[0], c[1]))

    assez = [c for c in compatibles if c[1] >= kw - 1e-9]
    pricees = [c for c in assez if prix_connu(c[0])]
    sortie["sans_prix"] = [c[0].get("nom") for c in assez
                           if not prix_connu(c[0])]
    if pricees:
        sortie["variateur"] = pricees[0][0]
        sortie["candidats"] = [c[0] for c in pricees]
        return sortie

    libelle_tension = ("%d V " % tension) if tension else ""
    compatibles_pricees = [c for c in compatibles if prix_connu(c[0])]
    if compatibles_pricees:
        plus_gros = compatibles_pricees[-1][1]
        message = ("Aucun variateur %s≥ %s kW au catalogue (le plus gros "
                   "compatible : %s kW)." % (libelle_tension, _fr(kw, 2),
                                             _fr(plus_gros, 2)))
    elif sortie["sans_prix"]:
        message = ("Aucun variateur %s≥ %s kW chiffrable : prix à renseigner "
                   "(%s)." % (libelle_tension, _fr(kw, 2),
                              ", ".join(sortie["sans_prix"])))
    else:
        message = ("Aucun variateur %s≥ %s kW au catalogue."
                   % (libelle_tension, _fr(kw, 2)))
    alertes.append(_alerte("aucun_variateur", "variateur", message))
    sortie["motif"] = message
    return sortie


def rendement_systeme(pompe=None, variateur=None):
    """η = rendement pompe × rendement MPPT, PUBLIÉS tous les deux (fiches
    ``pompe_rendement_pct`` / ``var_rendement_mppt_pct``) ; sinon le
    ``rendement_groupe`` « EST. » de la table AGR110.

    Rend ``{valeur, source, cle_hypothese}``."""
    r_pompe = _flottant(_fiche(pompe).get("pompe_rendement_pct"))
    r_mppt = _flottant(_fiche(variateur).get("var_rendement_mppt_pct"))
    if r_pompe and r_mppt and 0 < r_pompe <= 100 and 0 < r_mppt <= 100:
        return {"valeur": r_pompe / 100.0 * r_mppt / 100.0,
                "source": "fiches publiées (rendement pompe × rendement MPPT)",
                "cle_hypothese": None}
    return {"valeur": valeur("rendement_groupe"),
            "source": "EST. — table AGR110 › rendement_groupe",
            "cle_hypothese": "rendement_groupe"}


def energie_hydraulique_kwh_jour(volume_m3_jour, hmt_m):
    """E = 2,725 × V × HMT / 1000 (kWh/j) — constante physique AGR110."""
    v = _flottant(volume_m3_jour)
    h = _flottant(hmt_m)
    if v is None or h is None or v <= 0 or h <= 0:
        return None
    return valeur("energie_hydraulique_wh_par_m3_m") * v * h / 1000.0


def kwc_depart(volume_m3_jour, hmt_m, e_d_kwh_par_kwc, rendement):
    """kWc = E / (η × E_d) ; ``None`` si une entrée manque."""
    energie = energie_hydraulique_kwh_jour(volume_m3_jour, hmt_m)
    e_d = _flottant(e_d_kwh_par_kwc)
    eta = _flottant(rendement)
    if energie is None or not e_d or e_d <= 0 or not eta or eta <= 0:
        return None
    return energie / (eta * e_d)


def e_d_depuis_profils(profils_horaires):
    """E_d mensuel (kWh/kWc/j) = Σ G / 1000 de chaque journée type — même
    convention que la production AGR114 (P = kWc × G / 1000)."""
    if not profils_horaires or len(profils_horaires) != 12:
        return None
    sortie = []
    for profil in profils_horaires:
        if not profil:
            return None
        sortie.append(sum(max(0.0, _flottant(g, 0.0) or 0.0)
                          for g in profil) / 1000.0)
    return sortie


def spec_module(panneau):
    """``SpecModule`` depuis un dict panneau (noms de champ du noyau
    électrique) ; ``None`` si une valeur STC manque."""
    if not panneau:
        return None
    valeurs = {c: _flottant(panneau.get(c))
               for c in ("vmp_v", "voc_v", "isc_a", "imp_a", "pmax_wc")}
    if any(v is None or v <= 0 for v in valeurs.values()):
        return None
    extra = {}
    sources = []
    for coef in ("temp_coeff_voc_pct_c", "temp_coeff_pmax_pct_c"):
        val = _flottant(panneau.get(coef))
        if val is not None:
            extra[coef] = val
            sources.append(coef)
    return SpecModule(designation=panneau.get("nom") or "",
                      coefficients_sources=tuple(sources), **valeurs, **extra)


def spec_variateur(variateur):
    """``SpecOnduleur`` depuis la fiche ``variateur_pompage`` (champs
    onduleur réutilisés). Une borne non publiée vaut 0 (« n'exige rien » pour
    les bornes basses, « non vérifiable » pour les hautes — règles de
    ``fenetre_admissible``). Un seul MPPT : la fiche ne publie pas de nombre
    d'entrées, et les chaînes parallèles sont contrôlées ici sur le courant."""
    fiche = _fiche(variateur)

    def lire(cle):
        return _flottant(fiche.get(cle), 0.0) or 0.0

    phases = phases_sortie_variateur(variateur) or 1
    demarrage = _flottant(fiche.get("ond_v_demarrage_v"))
    return SpecOnduleur(
        n_mppt=1, mppt_v_min=lire("ond_mppt_v_min"),
        mppt_v_max=lire("ond_mppt_v_max"), v_max_abs=lire("ond_v_max_abs"),
        i_max_mppt_a=lire("ond_i_max_mppt_a"),
        ac_kw=_flottant(variateur.get("pompe_kw"), 0.0) or 0.0,
        phases=phases, v_demarrage_v=demarrage or None,
        designation=variateur.get("nom") or "")


def _production(nb, pmax_wc, **kwargs):
    return production_mensuelle(kwc=nb * pmax_wc / 1000.0, **kwargs)


def _couvre(prod, besoin, mois):
    serie = prod.get("m3_jour_mois") if prod else None
    if not serie or not mois:
        return False
    return (serie[mois - 1] or 0.0) >= besoin[mois - 1] - 1e-9


def _mois_critique_energie(besoin, e_d):
    meilleur, rapport_max = None, None
    for i in range(12):
        b = _flottant(besoin[i])
        if b is None or b <= 0 or not e_d[i] or e_d[i] <= 0:
            continue
        rapport = b / e_d[i]
        if rapport_max is None or rapport > rapport_max:
            meilleur, rapport_max = i + 1, rapport
    return meilleur


def _chaines_vides(motif):
    return {"serie": None, "paralleles": None, "voc_froid_v": None,
            "vmp_chaud_v": None, "verifiable": False, "motif": motif,
            "temperatures": None}


def _temperatures(temperatures):
    """(froid, chaud, source, mention) — TMY de l'appelant sinon replis
    MENTIONNÉS du noyau électrique."""
    temperatures = temperatures or {}
    froid = _flottant(temperatures.get("froid_c"))
    chaud = _flottant(temperatures.get("chaud_c"))
    if froid is not None and chaud is not None:
        return froid, chaud, temperatures.get("source") or "tmy_site", ""
    return (TEMP_FROID_DEFAUT_C, TEMP_CHAUD_DEFAUT_C, None,
            MENTION_TEMPERATURES_REPLI)


def _chaines_pour(variateur, module, nb, temperatures):
    """Une tentative de câblage sur ``variateur`` : rend ``(nb, chaines,
    alertes, suivant)`` ; ``suivant`` True ⇒ essayer le variateur suivant."""
    nom = variateur.get("nom") or "variateur"
    if not fiche_saisie(variateur):
        motif = ("chaîne PV non vérifiable : fiche du variateur %s non saisie"
                 % nom)
        return nb, _chaines_vides(motif), [_alerte(
            "chaine_non_verifiable", "variateur.fiche",
            "Chaîne PV non vérifiable : la fiche du variateur %s n'est pas "
            "saisie." % nom)], False

    froid, chaud, source, mention = _temperatures(temperatures)
    onduleur = spec_variateur(variateur)
    fenetre = fenetre_admissible(module, onduleur, froid, chaud,
                                 temp_source=source, temp_mention=mention)
    alertes = []
    if fenetre.trop_etroite:
        alertes.append(_alerte("fenetre_trop_etroite", "variateur.fiche",
                               "Variateur %s : %s." % (nom, fenetre.motif)))
        return nb, _chaines_vides(fenetre.motif), alertes, True

    if nb < fenetre.longueur_min:
        alertes.append(_alerte(
            "champ_impose_fenetre", "champ.nb_panneaux",
            "Champ imposé par la fenêtre du variateur : %d panneaux relevés à "
            "%d, minimum de chaîne pour la plage MPPT de %s (Vmp à %s °C)."
            % (nb, fenetre.longueur_min, nom, _fr(chaud, 0))))
        nb = fenetre.longueur_min
    paralleles = 1
    serie = nb
    if not fenetre.admet(nb):
        paralleles = int(math.ceil(nb / float(fenetre.longueur_max)))
        serie = max(int(math.ceil(nb / float(paralleles))),
                    fenetre.longueur_min)
        if serie * paralleles != nb:
            alertes.append(_alerte(
                "champ_arrondi_chaines", "champ.nb_panneaux",
                "Champ porté de %d à %d panneaux : %d chaînes égales de %d."
                % (nb, serie * paralleles, paralleles, serie)))
        nb = serie * paralleles

    i_max = onduleur.i_max_mppt_a
    if paralleles > 1:
        if i_max > 0 and paralleles * module.imp_a > i_max:
            alertes.append(_alerte(
                "courant_mppt_depasse", "variateur.fiche",
                "%d chaînes en parallèle (%s A) dépassent le courant MPPT de "
                "%s (%s A)." % (paralleles, _fr(paralleles * module.imp_a),
                                nom, _fr(i_max))))
            return nb, None, alertes, True
        if i_max <= 0:
            alertes.append(_alerte(
                "courant_mppt_non_verifiable", "variateur.fiche",
                "Courant MPPT de %s non publié : %d chaînes en parallèle non "
                "vérifiées." % (nom, paralleles)))

    voc_froid = serie * fenetre.voc_froid_unitaire_v
    vmp_chaud = serie * fenetre.vmp_chaud_unitaire_v
    fiche = _fiche(variateur)
    reco_min = _flottant(fiche.get("var_voc_reco_min_v"))
    reco_max = _flottant(fiche.get("var_voc_reco_max_v"))
    if (reco_min and voc_froid < reco_min) or (reco_max and voc_froid > reco_max):
        alertes.append(_alerte(
            "champ_impose_fenetre", "champ.chaines",
            "Champ imposé par la fenêtre du variateur : Voc à froid %s V hors "
            "de la plage recommandée %s-%s V de %s."
            % (_fr(voc_froid, 0), _fr(reco_min, 0), _fr(reco_max, 0), nom)))
    if fenetre.bornes_non_verifiables:
        alertes.append(_alerte(
            "bornes_non_verifiables", "variateur.fiche",
            "Bornes non vérifiables sur la fiche de %s : %s."
            % (nom, ", ".join(fenetre.bornes_non_verifiables))))
    chaines = {
        "serie": serie, "paralleles": paralleles,
        "voc_froid_v": round(voc_froid), "vmp_chaud_v": round(vmp_chaud),
        "verifiable": True, "motif": None,
        "temperatures": {"froid_c": froid, "chaud_c": chaud,
                         "source": source, "mention": mention or None},
    }
    return nb, chaines, alertes, False


def dimensionner_champ(*, besoin_m3_jour_mois, hmt_m, panneau,
                       variateurs_candidats=(), pompe=None, p_plaque_kw=None,
                       debit_declare_m3h=None, profils_horaires=None,
                       e_d_kwh_kwc_mois=None, temperatures=None,
                       salissure_pct=None, agricole_pump_hours=None,
                       mois_critique=None, coordonnees=None,
                       reponse_pvgis=None):
    """AGR115 — nombre de panneaux, chaînes et variateur retenu.

    * ``besoin_m3_jour_mois`` : besoin RETENU (AGR116) ; ``hmt_m`` : HMT ;
    * ``pompe`` : dict produit (``courbe_pompe``, ``fiche``) ou ``None`` pour
      une pompe existante sans courbe ; ``p_plaque_kw`` : kW de plaque ;
      ``debit_declare_m3h`` : débit déclaré d'une pompe existante (AGR114) ;
    * ``variateurs_candidats`` : sortie ``candidats`` de
      :func:`choisir_variateur` (le premier est essayé d'abord) ;
    * ``panneau`` : dict aux noms de ``SpecModule`` (+ ``id``, ``nom``) ;
    * ``profils_horaires`` (12 × 24 W/m²) et/ou ``e_d_kwh_kwc_mois`` (12) ;
    * ``temperatures`` : ``{froid_c, chaud_c, source}`` TMY du site, sinon
      replis mentionnés.

    Rend ``{kwc, nb_panneaux, ratio, chaines, kwc_depart, rendement,
    mois_critique, production, variateur, alertes, hypotheses}``.
    """
    alertes = []
    cles = {"energie_hydraulique_wh_par_m3_m", "ratio_champ_pompe_bande_alerte"}
    variateurs_candidats = list(variateurs_candidats or ())
    variateur = variateurs_candidats[0] if variateurs_candidats else None
    sortie = {"kwc": None, "nb_panneaux": None, "ratio": None,
              "chaines": _chaines_vides(None), "kwc_depart": None,
              "rendement": None, "mois_critique": None, "production": None,
              "variateur": variateur, "alertes": alertes, "hypotheses": []}

    def fin(motif=None):
        if motif:
            sortie["chaines"]["motif"] = sortie["chaines"]["motif"] or motif
        sortie["hypotheses"] = utilisees(cles)
        return sortie

    module = spec_module(panneau)
    if module is None:
        alertes.append(_alerte(
            "panneau_sans_fiche", "panneau",
            "Panneau sans valeurs STC complètes (Pmax, Vmp, Voc, Isc, Imp) : "
            "champ non dimensionné."))
        return fin("panneau sans fiche électrique")
    besoin = besoin_m3_jour_mois
    if not besoin or len(besoin) != 12:
        alertes.append(_alerte(
            "besoin_inconnu", "besoin",
            "Besoin en eau inconnu : champ non dimensionné."))
        return fin("besoin inconnu")

    e_d = e_d_kwh_kwc_mois if e_d_kwh_kwc_mois else e_d_depuis_profils(
        profils_horaires)
    rendement = rendement_systeme(pompe, variateur)
    if rendement["cle_hypothese"]:
        cles.add(rendement["cle_hypothese"])
    sortie["rendement"] = {"valeur": round(rendement["valeur"], 3),
                           "source": rendement["source"]}
    mois = mois_critique or (_mois_critique_energie(besoin, e_d)
                             if e_d else None)
    sortie["mois_critique"] = mois
    kwc0 = None
    if e_d and mois:
        kwc0 = kwc_depart(besoin[mois - 1], hmt_m, e_d[mois - 1],
                          rendement["valeur"])
    sortie["kwc_depart"] = round(kwc0, 2) if kwc0 else None

    plaque = _flottant(p_plaque_kw)
    rendement_mppt = _flottant(_fiche(variateur).get("var_rendement_mppt_pct"))
    params = dict(
        profils_horaires=profils_horaires,
        courbe_pompe=(pompe or {}).get("courbe_pompe"), hmt_m=hmt_m,
        p_plaque_kw=plaque,
        rendement_mppt=(rendement_mppt / 100.0 if rendement_mppt else None),
        salissure_pct=salissure_pct, debit_declare_m3h=debit_declare_m3h,
        agricole_pump_hours=agricole_pump_hours, besoin_m3_jour_mois=besoin,
        coordonnees=coordonnees, reponse_pvgis=reponse_pvgis)
    pmax = module.pmax_wc

    nb = int(math.ceil(kwc0 * 1000.0 / pmax)) if kwc0 else None
    prod = _production(nb or 1, pmax, **params)
    heure_par_heure = (prod.get("m3_jour_mois") is not None
                       and prod.get("mode") in ("courbe", "debit_declare"))
    if heure_par_heure and mois:
        nb = nb or 1
        if _couvre(prod, besoin, mois):
            while nb > 1:
                essai = _production(nb - 1, pmax, **params)
                if not _couvre(essai, besoin, mois):
                    break
                nb, prod = nb - 1, essai
        else:
            couvert = False
            for _ in range(_ITERATIONS_MAX):
                nb += 1
                prod = _production(nb, pmax, **params)
                if _couvre(prod, besoin, mois):
                    couvert = True
                    break
            if not couvert:
                nb = int(math.ceil(kwc0 * 1000.0 / pmax)) if kwc0 else nb
                prod = _production(nb, pmax, **params)
                alertes.append(_alerte(
                    "besoin_non_couvert_champ", "pompe",
                    "Même avec un champ très surdimensionné, la pompe ne "
                    "couvre pas le besoin du mois critique : champ ramené au "
                    "kWc de départ (énergie hydraulique)."))
    elif nb is None:
        alertes.append(_alerte(
            "irradiation_inconnue", "production",
            "Irradiation du site inconnue (ni profil PVGIS, ni E_d) : champ "
            "non dimensionné."))
        sortie["production"] = prod if prod.get("m3_jour_mois") else None
        return fin("irradiation inconnue")
    else:
        raison = (prod.get("motif") or prod.get("mode")
                  or "production indisponible")
        alertes.append(_alerte(
            "champ_kwc_depart", "champ.nb_panneaux",
            "Production heure par heure non calculable (%s) : champ au kWc de "
            "départ E / (η × E_d)." % raison))

    # Chaînes : variateur retenu, sinon le suivant (courant / fenêtre).
    chaines = _chaines_vides("aucun variateur retenu")
    variateur_retenu = None
    nb_initial = nb
    for index, candidat in enumerate(variateurs_candidats):
        nb_essai, chaines_essai, alertes_essai, suivant = _chaines_pour(
            candidat, module, nb_initial, temperatures)
        dernier = index == len(variateurs_candidats) - 1
        if suivant and not dernier:
            alertes.extend(alertes_essai)
            alertes.append(_alerte(
                "variateur_suivant", "variateur",
                "Variateur %s écarté pour ce champ : variateur suivant essayé."
                % (candidat.get("nom") or "")))
            continue
        alertes.extend(alertes_essai)
        variateur_retenu = candidat
        nb = nb_essai
        chaines = chaines_essai or _chaines_vides(
            "aucun variateur du catalogue n'accepte ce champ")
        break
    if not variateurs_candidats:
        alertes.append(_alerte(
            "chaine_non_verifiable", "variateur",
            "Chaîne PV non vérifiable : aucun variateur retenu."))
    if nb != nb_initial:
        prod = _production(nb, pmax, **params)

    kwc = nb * pmax / 1000.0
    sortie.update({
        "kwc": round(kwc, 2), "nb_panneaux": nb, "chaines": chaines,
        "variateur": variateur_retenu or variateur,
        "production": prod if prod.get("m3_jour_mois") is not None else None,
    })
    if plaque and plaque > 0:
        ratio = kwc / plaque
        sortie["ratio"] = round(ratio, 2)
        bande = valeur("ratio_champ_pompe_bande_alerte")
        if ratio < bande.min or ratio > bande.max:
            alertes.append(_alerte(
                "ratio_champ_pompe", "champ.kwc",
                "Ratio champ/pompe %s× hors de la bande %s-%s× (alerte seule)."
                % (_fr(ratio, 2), _fr(bande.min), _fr(bande.max))))
    return fin()
