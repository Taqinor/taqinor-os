"""AGR109 — sélection pompe / variateur (noyau pur ``core.pompage``).

Fonctions DÉPLACÉES telles quelles depuis ``apps/calepinage/services/pompage.py``
(CAL158, parité ``solar.js selectPompeByCurve`` / ``selectVariateurVeichi``).
Comportement OCTET-IDENTIQUE ; le module calepinage garde des ré-exports.

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O.
"""
from __future__ import annotations

import re

from core.pompage.hydraulique import _flottant, debit_a_hmt
from core.pompage.hypotheses import utilisees, valeur

#: Tensions standard du catalogue pompage (CLAUDE.md « Pompage sizing »).
TENSION_MONO_V = 220
TENSION_TRI_V = 380


# ═══════════════════════════════════════════════════════════════════════════
# CAL158 — pompe + variateur assortis, PARITÉ avec l'écran devis
# (frontend/src/features/ventes/solar.js selectPompeByCurve /
# selectVariateurVeichi), et la garde absolue « jamais de m³/jour sans
# courbe ».
# ═══════════════════════════════════════════════════════════════════════════

def tension_produit(produit):
    """La tension (V) d'un produit pompe/variateur — champ ``tension_v``
    d'abord, sinon lue dans le nom (« 220V »/« 380V »), sinon ``None``
    (inconnue — reste candidate, aucune régression sur les fiches sans
    tension). MÊME priorité que ``solar.js tensionOf``."""
    tension = produit.get('tension_v')
    if tension:
        val = _flottant(tension)
        if val:
            return int(val)
    nom = produit.get('nom') or ''
    if _RE_TENSION_MONO.search(nom):
        return TENSION_MONO_V
    if _RE_TENSION_TRI.search(nom):
        return TENSION_TRI_V
    return None


# ERR-QAH-DIFF-POMPAGE-TENSION-NOM-2200W — UNE règle stricte, jumelle de
# ``solar.js tensionOf`` : le NOMBRE ISOLÉ 220/380 immédiatement suivi de
# « V » (« 220V », « 220 V », « 220Vac », « 380 volts »). L'ancienne lecture
# (« 220 » n'importe où ET un « v » n'importe où) lisait 220 V dans
# « Variateur VEICHI … 2200W » : l'écran et le calepinage retenaient alors une
# pompe/un variateur DIFFÉRENT.
_RE_TENSION_MONO = re.compile(r'(?<![\d.,])220\s*v(?:olts?|ac)?(?![a-z0-9])',
                              re.IGNORECASE)
_RE_TENSION_TRI = re.compile(r'(?<![\d.,])380\s*v(?:olts?|ac)?(?![a-z0-9])',
                             re.IGNORECASE)


def _tension_alim(alim):
    return TENSION_MONO_V if alim == 'mono' else TENSION_TRI_V


def _a_prix(produit):
    return (_flottant(produit.get('prix_vente'), 0.0) or 0.0) > 0


def selection_pompe(pompes, *, hmt, debit_souhaite_m3h, type_pompe='immerge',
                    alim='tri'):
    """CAL158 — port Python de ``solar.js selectPompeByCurve`` : la plus
    petite pompe (kW) DONT LA COURBE délivre ≥ ``debit_souhaite_m3h`` à
    ``hmt``, tension assortie à ``alim``, jamais un produit sans prix.

    GARDE ABSOLUE « jamais de m³/jour sans courbe » : une pompe SANS
    ``courbe_pompe`` est structurellement exclue de ``pompes`` avant même
    d'être candidate — cette fonction ne peut donc jamais renvoyer un
    ``debit_hmt_m3h`` fabriqué, et ``apps.ventes.solar_design.
    pumping_cycle_yield`` refuse déjà un débit ``None`` de son côté (double
    verrou, jamais un chiffre inventé nulle part sur ce chemin).

    ``pompes`` : liste de dicts ``{id, nom, pompe_kw, courbe_pompe,
    tension_v, prix_vente}`` — typiquement
    ``apps.stock.selectors.produits_par_type_equipement(company, 'pompe',
    avec_prix=False)`` mis en forme par l'appelant (le prix nul est filtré
    ICI, jamais avant, pour que ``sans_prix`` reste informatif).

    Rend ``{pompe, debit_hmt_m3h, kw, sans_prix, ecart_phase}`` — ``pompe``
    vaut ``None`` si aucune candidate compatible et pricée n'existe.
    """
    h = _flottant(hmt)
    q = _flottant(debit_souhaite_m3h)
    if not h or not q or h <= 0 or q <= 0:
        return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
                'sans_prix': [], 'ecart_phase': False}

    veut_surface = type_pompe == 'surface'
    tension_voulue = _tension_alim(alim) if alim else None

    candidats = []
    for p in pompes:
        if not p.get('courbe_pompe'):
            continue  # GARDE ABSOLUE — jamais candidate sans courbe.
        kw = _flottant(p.get('pompe_kw'), 0.0)
        if not kw or kw <= 0:
            continue
        debit_hmt = debit_a_hmt(p['courbe_pompe'], h)
        if debit_hmt is None or debit_hmt < q:
            continue
        nom = (p.get('nom') or '').lower()
        if veut_surface and 'surface' not in nom:
            continue
        if not veut_surface and 'immerg' not in nom:
            continue
        candidats.append({'p': p, 'kw': kw, 'debit_hmt': debit_hmt,
                          'tension': tension_produit(p)})

    compatibles = [
        c for c in candidats
        if tension_voulue is None or c['tension'] is None
        or c['tension'] == tension_voulue]
    compatibles.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))

    pricees = [c for c in compatibles if _a_prix(c['p'])]
    if pricees:
        best = pricees[0]
        return {'pompe': best['p'], 'debit_hmt_m3h': best['debit_hmt'],
                'kw': best['kw'], 'sans_prix': [], 'ecart_phase': False}

    ecart_phase = bool(
        tension_voulue is not None
        and any(_a_prix(c['p']) and c['tension'] is not None
                and c['tension'] != tension_voulue for c in candidats))
    return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
            'sans_prix': [c['p'].get('nom') for c in compatibles],
            'ecart_phase': ecart_phase}


def selection_variateur(variateurs, kw, alim):
    """CAL158 — port Python de ``solar.js selectVariateurVeichi`` : le plus
    petit variateur VEICHI (mot « variateur », jamais un « afficheur ») dont
    ``kW ≥ kw`` demandé, tension assortie à ``alim``, jamais un produit sans
    prix. Repli JAMAIS silencieux : des variateurs compatibles existent mais
    aucun n'atteint le kW requis ⇒ ``insuffisant: True`` (pas le plus gros
    disponible sous-dimensionné).
    """
    tension_voulue = _tension_alim(alim)
    candidats = []
    for p in variateurs:
        nom = (p.get('nom') or '').lower()
        if 'variateur' not in nom or 'afficheur' in nom:
            continue
        pk = _flottant(p.get('pompe_kw'), 0.0)
        if not pk or pk <= 0 or not _a_prix(p):
            continue
        if tension_produit(p) != tension_voulue:
            continue
        candidats.append({'p': p, 'kw': pk})
    candidats.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))
    fit = next((c for c in candidats if c['kw'] >= kw), None)
    return {'variateur': fit['p'] if fit else None,
            'insuffisant': fit is None and bool(candidats)}


# ═══════════════════════════════════════════════════════════════════════════
# AGR117 — pompe NEUVE choisie sur le débit de conception (D-AGR-7), jamais
# une ligne pompe absente, jamais une alimentation incompatible.
# ``selection_pompe`` ci-dessus (parité CAL158) reste intacte jusqu'à AGR132.
# ═══════════════════════════════════════════════════════════════════════════

ETIQUETTE_A_CONFIRMER = "à confirmer sur la courbe constructeur"
PREFIXE_PLACEHOLDER = "Pompe — prix à renseigner : "


def prix_connu(produit):
    """Un prix de vente est-il saisi ? ``prix_connu`` (forme du sélecteur
    AGR103) d'abord, sinon ``prix_vente`` > 0."""
    if produit is None:
        return False
    if "prix_connu" in produit:
        return bool(produit.get("prix_connu"))
    return (_flottant(produit.get("prix_vente"), 0.0) or 0.0) > 0


def _fr(nombre, chiffres=2):
    texte = ("%%.%df" % chiffres) % nombre
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def alimentation_produit(produit):
    """``mono`` | ``tri`` | ``dc`` | ``None`` — champ ``alimentation`` (AGR100)
    d'abord, sinon la tension (220 V → mono, 380 V → tri), sinon le nom."""
    alim = (produit.get("alimentation") or "").strip().lower()
    if alim in ("mono", "tri", "dc"):
        return alim
    tension = tension_produit(produit)
    if tension == TENSION_MONO_V:
        return "mono"
    if tension == TENSION_TRI_V:
        return "tri"
    nom = (produit.get("nom") or "").lower()
    if "monophas" in nom:
        return "mono"
    if "triphas" in nom:
        return "tri"
    return None


def _norme_type(type_pompe):
    t = (type_pompe or "").strip().lower()
    if t.startswith("immerg"):
        return "immergee"
    return t or None


def type_produit(produit):
    """``immergee`` | ``surface`` | ``dc`` | ``None`` — champ ``type_pompe``
    d'abord, sinon le nom."""
    t = _norme_type(produit.get("type_pompe"))
    if t:
        return t
    nom = (produit.get("nom") or "").lower()
    if "immerg" in nom:
        return "immergee"
    if "surface" in nom:
        return "surface"
    return None


def kw_pompe(produit):
    """(kW, source) — ``pompe_kw`` (plaque), sinon ``pompe_cv`` × 0,7355
    (table AGR110), sinon (None, None)."""
    kw = _flottant(produit.get("pompe_kw"))
    if kw and kw > 0:
        return kw, "plaque"
    cv = _flottant(produit.get("pompe_cv"))
    if cv and cv > 0:
        return cv * valeur("cv_vers_kw"), "cv"
    return None, None


def _a_courbe(produit):
    courbe = produit.get("courbe_pompe")
    return bool(courbe and courbe.get("debits_m3h") and courbe.get("hmt_m"))


def _fiche_pompe(produit):
    fiche = produit.get("fiche")
    return fiche if isinstance(fiche, dict) else {}


def _sortie_pompe(produit, *, kw, debit_hmt, hmt, placeholder_nom=None,
                  type_pompe=None, alimentation=None):
    """La forme ``pompe`` du contrat ``etude_pompage_preview.json``."""
    if produit is None:
        return {"mode": "neuve", "produit": None, "nom": placeholder_nom,
                "placeholder": True, "classement": None,
                "type_pompe": type_pompe, "alimentation": alimentation,
                "kw": None, "tension_v": None, "plaque": None, "courbe": None,
                "point_fonctionnement": None, "debit_a_hmt_m3h": None,
                "prix_connu": False}
    courbe = produit.get("courbe_pompe") if _a_courbe(produit) else None
    return {
        "mode": "neuve", "produit": produit.get("id"),
        "nom": produit.get("nom"), "placeholder": False,
        "classement": produit.get("classement"),
        "type_pompe": type_produit(produit),
        "alimentation": alimentation_produit(produit),
        "kw": round(kw, 2) if kw else None,
        "tension_v": tension_produit(produit), "plaque": None,
        "courbe": courbe,
        "point_fonctionnement": ({"debit_m3h": round(debit_hmt, 1),
                                  "hmt_m": hmt}
                                 if debit_hmt is not None else None),
        "debit_a_hmt_m3h": (round(debit_hmt, 1)
                            if debit_hmt is not None else None),
        "prix_connu": prix_connu(produit),
    }


def _cle(entree):
    p = entree["p"]
    return (entree["kw"], _flottant(p.get("prix_vente"), 0.0) or 0.0,
            p.get("id") or 0)


def choisir_pompe(pompes, *, hmt_m, debit_conception_m3h, alimentation,
                  type_pompe="immergee", diametre_tubage_mm=None,
                  profondeur_calage_m=None, niveau_dynamique_m=None):
    """AGR117 — la pompe NEUVE du devis, ou un placeholder NOMMÉ.

    ``pompes`` : éléments de ``stock.selectors.produits_pompage`` (forme
    ``element_produits_pompage``) de rôle ``pompe`` — fournis par l'appelant.

    1. Plus petite pompe PRICÉE à courbe, de la bonne alimentation et du bon
       type, dont le débit à la HMT ≥ débit de conception (point nominal de la
       courbe, n = 1 des lois de similitude d'AGR114 ; la couverture mois par
       mois est confirmée par le champ AGR115).
    2. Sinon pré-dimensionnement : kW min = Q × HMT × 2,725 / (1000 × η EST.)
       (table AGR110), plus petite pompe pricée SANS courbe de la bonne
       alimentation, étiquetée « à confirmer sur la courbe constructeur »,
       production non publiable ; les pompes à courbe sans prix qui
       conviendraient sont listées dans ``prix_a_renseigner``.
    3. Rien de pricé ⇒ placeholder « Pompe — prix à renseigner : <noms> »
       (patron QJR131 : jamais un article gratuit).

    JAMAIS une alimentation incompatible (une pompe d'alimentation inconnue
    n'est pas candidate). Le CV n'est pas une entrée : ``puissance_retenue``
    {kw, cv} est une SORTIE. ``couverture`` sert le débit demandé à côté du
    débit livré, sans seuil de surdimensionnement (écartés 1,5×/2×).

    Rend ``{pompe, etape, prix_a_renseigner, puissance_retenue, couverture,
    production_publiable, paliers, index_palier, alertes, hypotheses}`` ;
    ``paliers`` = pompes pricées de la même famille (à courbe livrant à cette
    HMT, ou sans courbe en pré-dimensionnement), du plus petit au plus gros
    kW — l'entrée des trois tailles AGR120.
    """
    alertes = []
    cles = {"cv_vers_kw"}
    type_voulu = _norme_type(type_pompe) or "immergee"
    alim = (alimentation or "").strip().lower() or None
    h = _flottant(hmt_m)
    q = _flottant(debit_conception_m3h)

    def alerte(code, champ, message):
        alertes.append({"code": code, "champ": champ, "message": message})

    def resultat(pompe, etape, *, prix_a_renseigner=(), kw=None,
                 debit_livre=None, paliers=(), index=None):
        cv = kw / valeur("cv_vers_kw") if kw else None
        couverture = {
            "debit_demande_m3h": round(q, 1) if q else None,
            "debit_livre_m3h": (round(debit_livre, 1)
                                if debit_livre is not None else None),
            "couverture_pct": (round(debit_livre / q * 100)
                               if debit_livre is not None and q else None),
        }
        return {"pompe": pompe, "etape": etape,
                "prix_a_renseigner": list(prix_a_renseigner),
                "puissance_retenue": {"kw": round(kw, 2) if kw else None,
                                      "cv": round(cv, 1) if cv else None},
                "couverture": couverture,
                "production_publiable": etape == "courbe",
                "paliers": list(paliers), "index_palier": index,
                "alertes": alertes, "hypotheses": utilisees(cles)}

    if not h or not q or h <= 0 or q <= 0:
        alerte("debit_conception_inconnu", "conception.debit_conception_m3h",
               "HMT ou débit de conception inconnu : pompe non choisie "
               "(ligne pompe à compléter).")
        return resultat(_sortie_pompe(
            None, kw=None, debit_hmt=None, hmt=h,
            placeholder_nom=("Pompe — à choisir : HMT ou débit de conception "
                             "inconnu"),
            type_pompe=type_voulu, alimentation=alim), "placeholder")

    famille = []  # bon type ET bonne alimentation
    for p in pompes or ():
        if p.get("role_pompage") and p.get("role_pompage") != "pompe":
            continue
        if type_produit(p) != type_voulu or alimentation_produit(p) != alim:
            continue
        kw, source_kw = kw_pompe(p)
        entree = {"p": p, "kw": kw, "source_kw": source_kw,
                  "courbe": _a_courbe(p), "debit": None}
        if entree["courbe"]:
            entree["debit"] = debit_a_hmt(p["courbe_pompe"], h)
        famille.append(entree)

    a_courbe = sorted([e for e in famille if e["courbe"] and e["kw"]],
                      key=_cle)
    convient = [e for e in a_courbe
                if e["debit"] is not None and e["debit"] >= q]
    sans_prix_courbe = [e["p"].get("nom") for e in convient
                        if not prix_connu(e["p"])]

    choisie = None
    etape = None
    paliers = []
    pricees_courbe = [e for e in convient if prix_connu(e["p"])]
    if pricees_courbe:
        choisie = pricees_courbe[0]
        etape = "courbe"
        paliers = [e for e in a_courbe if prix_connu(e["p"])
                   and e["debit"] is not None and e["debit"] > 0]

    cles.update({"energie_hydraulique_wh_par_m3_m", "rendement_groupe"})
    kw_min = (q * h * valeur("energie_hydraulique_wh_par_m3_m")
              / (1000.0 * valeur("rendement_groupe")))
    sans_courbe = sorted([e for e in famille if not e["courbe"] and e["kw"]],
                         key=_cle)
    if choisie is None:
        pre = [e for e in sans_courbe
               if e["kw"] >= kw_min and prix_connu(e["p"])]
        if pre:
            choisie = pre[0]
            etape = "pre_dimensionnement"
            paliers = [e for e in sans_courbe if prix_connu(e["p"])]
            alerte("pompe_sans_courbe", "pompe",
                   "Pompe pré-dimensionnée (kW min %s = Q × HMT × 2,725 / "
                   "(1000 × η EST.)) : %s ; aucun m³/jour publié tant que la "
                   "courbe manque." % (_fr(kw_min), ETIQUETTE_A_CONFIRMER))

    if choisie is None:
        noms = list(sans_prix_courbe) or [
            e["p"].get("nom") for e in sans_courbe
            if e["kw"] >= kw_min and not prix_connu(e["p"])]
        nom = PREFIXE_PLACEHOLDER + (", ".join(noms) if noms else
                                     "aucune pompe compatible au catalogue")
        alerte("aucune_pompe_chiffrable", "pompe",
               "Aucune pompe chiffrable ne couvre %s m³/h à %s m (%s). "
               "Production et couverture non calculées."
               % (_fr(q, 1), _fr(h, 1),
                  "prix à renseigner" if noms
                  else "aucune pompe compatible au catalogue"))
        if alim == "mono":
            kws_mono = [e["kw"] for e in famille if e["kw"]]
            if kws_mono:
                message = ("Gamme monophasée du catalogue : %s kW max — "
                           "insuffisante pour ce débit à cette HMT."
                           % _fr(max(kws_mono)))
            else:
                message = "Aucune pompe monophasée au catalogue."
            alerte("gamme_monophasee", "alim", message)
        return resultat(
            _sortie_pompe(None, kw=None, debit_hmt=None, hmt=h,
                          placeholder_nom=nom, type_pompe=type_voulu,
                          alimentation=alim), "placeholder",
            prix_a_renseigner=noms)

    p = choisie["p"]
    sortie = _sortie_pompe(p, kw=choisie["kw"], debit_hmt=choisie["debit"],
                           hmt=h)
    if etape == "pre_dimensionnement":
        sortie["etiquette"] = ETIQUETTE_A_CONFIRMER
    if choisie["source_kw"] == "cv":
        alerte("kw_plaque_a_relever", "pompe.kw",
               "kW de plaque de « %s » non saisi : puissance estimée sur le "
               "CV (× 0,7355)." % p.get("nom"))

    fiche = _fiche_pompe(p)
    diametre = _flottant(fiche.get("pompe_diametre_ext_mm"))
    tubage = _flottant(diametre_tubage_mm)
    if diametre and tubage and diametre >= tubage:
        alerte("diametre_tubage", "source.diametre_tubage_mm",
               "Diamètre extérieur de la pompe (%s mm) ≥ tubage du forage "
               "(%s mm)." % (_fr(diametre, 0), _fr(tubage, 0)))
    immersion = _flottant(fiche.get("pompe_immersion_min_m"))
    calage = _flottant(profondeur_calage_m)
    if immersion and calage:
        nd = _flottant(niveau_dynamique_m)
        disponible = calage - nd if nd is not None else calage
        if immersion > disponible:
            alerte("immersion_minimale", "source.profondeur_calage_m",
                   "Immersion minimale de la pompe (%s m) > %s (%s m)."
                   % (_fr(immersion, 1),
                      "hauteur d'eau au-dessus de la pompe" if nd is not None
                      else "profondeur de calage", _fr(disponible, 1)))

    index = next((i for i, e in enumerate(paliers) if e is choisie), None)
    return resultat(sortie, etape, prix_a_renseigner=sans_prix_courbe,
                    kw=choisie["kw"], debit_livre=choisie["debit"],
                    paliers=[e["p"] for e in paliers], index=index)


# ═══════════════════════════════════════════════════════════════════════════
# AGR118 — pompe EXISTANTE conservée (D-AGR-7) : compatibilité de SORTIE du
# variateur avec la PLAQUE de la pompe.
# ═══════════════════════════════════════════════════════════════════════════

def _fiche_variateur(produit):
    fiche = produit.get("fiche")
    return fiche if isinstance(fiche, dict) else {}


def variateurs_compatibles_plaque(variateurs, *, tension_v, phases):
    """Tri des variateurs selon leur SORTIE face à la plaque.

    Sortie = ``var_v_sortie_v`` / ``ond_phases`` de la fiche (AGR101), sinon
    la tension du produit. Rend ``(compatibles, a_verifier)`` :

    * plaque monophasée 220 V → variateurs 220 V seulement (une fiche qui
      publie une sortie triphasée est écartée) ;
    * plaque triphasée 220 V → ``compatibles`` = fiche publiant une sortie
      TRIPHASÉE 220 V ; ``a_verifier`` = variateurs 220 V dont la fiche ne
      publie pas les phases (« compatibilité à vérifier sur la fiche ») ;
    * autre plaque → même tension, phases contrôlées quand publiées.
    """
    compatibles, a_verifier = [], []
    for produit in variateurs or ():
        fiche = _fiche_variateur(produit)
        tension = _flottant(fiche.get("var_v_sortie_v"))
        tension = int(tension) if tension else tension_produit(produit)
        if tension_v and tension != tension_v:
            continue
        ph = _flottant(fiche.get("ond_phases"))
        ph = int(ph) if ph else None
        if phases and ph is not None and ph != phases:
            continue
        if phases == 3 and tension_v == TENSION_MONO_V and ph is None:
            a_verifier.append(produit)
            continue
        compatibles.append(produit)
    return compatibles, a_verifier
