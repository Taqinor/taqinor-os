"""CIQ303 — ``synthese_ci(data)`` (1/2) : UNE fonction serveur PURE qui dit le
système, l'énergie, la provenance et le degré de certitude d'un devis
commercial ou industriel.

POURQUOI. Le PDF C&I imprimait la production serveur par ville (``prod_kwh``
de ``pricing``, ≈ 1 536 kWh/kWc) à côté de taux d'autoconsommation et de
couverture calculés en JS sur un autre productible (≈ 1 256 kWh/kWc) : deux
modèles sur une même page (C3-04). Aucun support ne disait d'où venaient les
chiffres (factures, profil déclaré, profil type — C3-07), ni qu'il était
préliminaire (W4-22), ni ce que voulaient dire les deux taux (W4-01).

CE QU'ELLE LIT — ``data`` SEUL (la charge utile de ``build_quote_data``) :
  * ``data['etude']['etude_ci']`` : la sortie du moteur serveur C&I (clés
    déclarées par CIQ117, contrat ``etude_ci_preview.json``, CIQ2) —
    ``entrees_resolues``, ``profil_charge``, ``bilan``,
    ``sous_reserve_visite``… La production servie est CELLE-LÀ, et elle seule.
  * ``data['puissance_kwc']`` / ``data['nb_panneaux']`` : le kWc des LIGNES
    (QJR625), jamais celui d'une étude ;
  * ``data['option_servie']`` / ``data['option_batterie']`` (CIQ302) ;
  * ``data['payment_terms']`` + le total TTC de l'offre servie ;
  * ``data['_entrees_ci_lead']`` : ``crm.selectors.entrees_ci_du_lead`` posé
    par le builder (CIQ405) — ses ``manquants`` disent ce qui reste à relever.

CE QU'ELLE REND — les clés « cœur » de la forme ``synthese_ci`` du contrat
partagé ``contract_samples/proposal_data.json`` (CIQ4) : ``version``,
``segment``, ``statut_etude``, ``a_confirmer``, ``provenance``, ``systeme``,
``baseline?``, ``energie?``, ``option_servie``, ``option_batterie?``,
``echeancier``, ``omissions`` — et, moitié 2/2 (CIQ304), ``argent?`` : le
bloc PUBLIC ``data['economie_ci']`` (contrat ``economie_ci.json``, CIQ3)
recopié tel quel, sans recalcul ni arrondi propre.
Une clé optionnelle est ABSENTE quand elle n'a rien d'honnête à montrer, et
son motif est nommé dans ``omissions``.

CE QU'ELLE NE FAIT JAMAIS : aucun calcul d'énergie ni d'argent (les taux sont
ceux du moteur, seulement exprimés en %), aucun taux fixe (D-CIQ-1), aucun
``prix_achat``, aucun accès base de données, aucune lecture de
``apps.visites``, aucun changement de statut (règle #4).
"""
from __future__ import annotations

from ..lecture_pure import nombre_normalise
from .mentions import mentions_ci

#: Version de la forme servie (contrat CIQ4).
VERSION = 1

SEGMENTS_CI = ("commercial", "industriel")

STATUT_SOUS_RESERVE = "estimation_sous_reserve_visite"
STATUT_FERME = "offre_ferme"

#: Méthode du profil de charge du moteur (contrat CIQ2 ›
#: ``profil_charge.methode``) → méthode servie au client. Le profil TYPE
#: (archétype) est toujours dit « estimation » (D-CIQ-1).
METHODES = {
    "declare": "horaire_declare",
    "courbe_mesuree": "horaire_mesure",
    "registres_mt": "registres_mt",
    "archetype": "archetype_estimation",
}
METHODE_INCONNUE = "estimation"

#: Définitions des deux taux (IEA PVPS T1-28:2016 : autoconsommation = part
#: de la production consommée sur place ; couverture — « autarcie » — = part
#: de la consommation couverte par la production). Trois langues ; la langue
#: du document choisit, repli français.
DEFINITIONS = {
    "fr": {
        "autoconso": "part de la production consommée sur place",
        "couverture": "part de votre consommation couverte par le solaire",
    },
    "en": {
        "autoconso": "share of the solar production consumed on site",
        "couverture": "share of your consumption covered by solar",
    },
    "ar": {
        "autoconso": "حصة الإنتاج المستهلكة في عين المكان",
        "couverture": "حصة استهلاككم المغطاة بالطاقة الشمسية",
    },
}

#: Entrées de consommation du moteur (``entrees_resolues``), par priorité.
CLES_CONSOMMATION = ("kwh_mensuels", "consommation", "factures_mad",
                     "registres_mt", "kwh_annuel")

#: ``detail`` d'une provenance qui vaut FACTURE relevée (contrat CIQ2).
DETAILS_FACTURE = frozenset({"facture", "mesure_visite"})

#: Manquants du lead (CIQ405) qui relèvent de la visite (D-CIQ-5), et ce que
#: le document en dit. Plusieurs colonnes « toit » ne font qu'une ligne.
A_CONFIRMER_LEAD = {
    "tension_raccordement": (
        "tension", "Tension de raccordement (BT ou MT), à relever à la visite"),
    "compteur_puissance_kva": (
        "puissance_souscrite_kva",
        "Puissance souscrite, à relever sur la facture ou à la visite"),
    "type_toiture": (
        "toit", "Type et charge admissible de la toiture, à la visite"),
    "type_surface": (
        "toit", "Type et charge admissible de la toiture, à la visite"),
    "surface_toiture_m2": (
        "toit", "Type et charge admissible de la toiture, à la visite"),
}

#: Jalons de l'échéancier, dans l'ordre des créneaux de
#: ``PAYMENT_TERMS_BY_MODE`` (contrat CIQ4 › ``echeancier``).
JALONS = (
    ("acompte", "À la commande", "commande"),
    ("materiel", "À la livraison", "livraison"),
    ("solde", "À la mise en service", "mise_en_service"),
)

MOTIF_SANS_ETUDE = (
    "étude du moteur C&I absente : taux d'autoconsommation et de couverture "
    "non servis (aucun taux fixe)")
MOTIF_TAUX_ABSENTS = (
    "bilan du moteur C&I sans taux : autoconsommation et couverture non "
    "servies")
MOTIF_PRODUCTION_ABSENTE = (
    "production non servie : seule la production du moteur C&I est imprimée, "
    "jamais une production par ville à côté de taux d'un autre modèle")
MOTIF_BASELINE_ABSENTE = (
    "consommation de référence non résolue par le moteur C&I")
MOTIF_ETUDE_A_FAIRE = (
    "étude du moteur C&I à faire : chiffres préliminaires")
LIBELLE_VISITE = "Relevé du site à la visite technique"

#: CIQ304 — ce qui manque quand le moteur n'a pas chiffré l'argent : ce que
#: le CLIENT peut fournir (ses factures), jamais « votre répartition
#: horaire ». Texte du contrat partagé ``proposal_data.json``.
MOTIF_ARGENT_BT = "vos 12 dernières factures"
MOTIF_ARGENT_MT = ("vos 12 dernières factures MT : prix des trois postes, "
                   "prime fixe, puissance souscrite")
#: VAN, LCOE et sensibilités : INDUSTRIEL seulement (D-CIQ-10). En commercial
#: ces clés sont retirées du bloc recopié (jamais recalculées). Le payback
#: actualisé suit la VAN (il n'existe que sur un taux déclaré) : un seul
#: payback servi, celui du flux (``indicateurs.retour_ans``).
CLES_INDUSTRIEL_SEUL = frozenset({
    "van_mad", "van_motif", "lcoe_mad_kwh", "lcoe_actualise",
    "retour_actualise_ans", "sensibilites"})
#: Entrées de listes ``{cle: …}`` (omissions, hypothèses) qui ne parlent que
#: de la VAN — retirées avec elle en commercial.
ENTREES_INDUSTRIEL_SEUL = frozenset({"van_mad", "taux_actualisation_pct",
                                     "sensibilites"})


# ── utilitaires purs ────────────────────────────────────────────────────────

def _dict(v):
    return v if isinstance(v, dict) else {}


_num = nombre_normalise


def _pct(fraction):
    """Une fraction du moteur (0.728) exprimée en % (72.8) — un changement
    d'unité, pas un calcul : aucun arrondi propre au-delà du dixième."""
    f = _num(fraction)
    return None if f is None else round(f * 100, 1)


def _provenance(p):
    """La forme UNIQUE ``{origine, detail, date}`` (contrats AGR2 / CIQ2)."""
    if not isinstance(p, dict) or not p.get("origine"):
        return None
    return {"origine": p.get("origine"), "detail": p.get("detail"),
            "date": p.get("date")}


# ── blocs ───────────────────────────────────────────────────────────────────

def _bloc_provenance(entrees):
    sortie = {}
    for cle, entree in entrees.items():
        prov = _provenance(_dict(entree).get("provenance"))
        if prov is not None:
            sortie[cle] = prov
    return sortie


def _serie_kwh(valeur):
    """Douze kWh mensuels lus tels quels, ou None. Accepte la liste de
    nombres ou la liste de relevés ``{mois, kwh}`` (CIQ405)."""
    if not isinstance(valeur, (list, tuple)):
        return None
    serie = [_num(v.get("kwh")) if isinstance(v, dict) else _num(v)
             for v in valeur]
    return serie


def _bloc_baseline(entrees):
    """``(bloc, motif)`` — la consommation de référence et sa source, lues
    dans la provenance du moteur (jamais devinées)."""
    for cle in CLES_CONSOMMATION:
        entree = _dict(entrees.get(cle))
        if not entree:
            continue
        prov = _dict(entree.get("provenance"))
        serie = _serie_kwh(entree.get("valeur"))
        interpoles = entree.get("mois_interpoles") or entree.get("interpoles")
        if serie is not None:
            complets = (len(serie) == 12
                        and all(v is not None for v in serie))
            if not complets or interpoles:
                return {"source": "mois_interpoles", "estimation": True}, None
            if prov.get("detail") in DETAILS_FACTURE:
                return {"source": "factures", "estimation": False,
                        "factures_mensuelles": serie}, None
        return {"source": "kwh_declares", "estimation": True}, None
    return None, MOTIF_BASELINE_ABSENTE


def _bloc_energie(etude_ci, langue):
    bilan = _dict(etude_ci.get("bilan"))
    autoconso = _pct(bilan.get("taux_autoconso"))
    couverture = _pct(bilan.get("taux_couverture"))
    if autoconso is None or couverture is None:
        return None, MOTIF_TAUX_ABSENTS
    methode = _dict(etude_ci.get("profil_charge")).get("methode")
    return {
        "taux_autoconso_pct": autoconso,
        "taux_couverture_pct": couverture,
        "methode": METHODES.get(methode, METHODE_INCONNUE),
        "definitions": dict(DEFINITIONS.get(langue) or DEFINITIONS["fr"]),
    }, None


def _option_servie(data):
    servie = data.get("option_servie")
    if servie == "avec":
        return "avec_batterie"
    if servie == "sans":
        return "sans_batterie"
    # Mono-option : le seul panier publié dit s'il porte une batterie.
    if data.get("avec_ok") and not data.get("sans_ok"):
        return "avec_batterie"
    return "sans_batterie"


def _systeme(data, etude_ci, option):
    suffixe = "avec" if option == "avec_batterie" else "sans"
    kwc = _num(data.get(f"puissance_kwc_{suffixe}"))
    if kwc is None:
        kwc = _num(data.get("puissance_kwc"))
    nb = _num(data.get(f"nb_panneaux_{suffixe}"))
    if nb is None:
        nb = _num(data.get("nb_panneaux"))
    return {
        "kwc": kwc,
        "nb_panneaux": nb,
        # UNE production : celle du moteur C&I, jamais ``prod_kwh``.
        "production_kwh_an": _num(
            _dict(etude_ci.get("bilan")).get("production_kwh")),
    }


def _statut_et_a_confirmer(etude_ci, lead):
    a_confirmer = []
    vus = set()

    def _ajoute(cle, libelle):
        if cle not in vus:
            vus.add(cle)
            a_confirmer.append({"cle": cle, "libelle": libelle})

    if not etude_ci:
        statut = STATUT_SOUS_RESERVE
        _ajoute("etude_ci", MOTIF_ETUDE_A_FAIRE)
    else:
        reserve = _dict(etude_ci.get("sous_reserve_visite"))
        statut = STATUT_SOUS_RESERVE if reserve.get("valeur") else STATUT_FERME
        if reserve.get("valeur"):
            _ajoute("visite", reserve.get("motif") or LIBELLE_VISITE)
    for manquant in _dict(lead).get("manquants") or []:
        if manquant in A_CONFIRMER_LEAD:
            _ajoute(*A_CONFIRMER_LEAD[manquant])
    return statut, a_confirmer


def _option_batterie(data):
    bloc = data.get("option_batterie")
    if not isinstance(bloc, dict):
        return None
    # Jamais les lignes recopiées en bloc ici (la page a déjà ses lignes) :
    # les totaux de l'option et la valeur chiffrée par le moteur, ou son motif.
    return {"totaux": bloc.get("totaux"),
            "valeur_chiffree": bloc.get("valeur_chiffree"),
            "motif": bloc.get("motif")}


def _echeancier(data, option):
    termes = _dict(data.get("payment_terms"))
    paires = [(cle, termes.get(cle)) for cle, _l, _j in JALONS
              if termes.get(cle) is not None]
    total = _num(data.get(
        "total_avec" if option == "avec_batterie" else "total_sans"))
    montants = {}
    if paires and total is not None:
        from apps.ventes.utils.echeancier import montants_tranches
        montants = montants_tranches(total, paires)
    sortie = []
    for cle, libelle, jalon in JALONS:
        if termes.get(cle) is None:
            continue
        montant = montants.get(cle)
        sortie.append({
            "libelle": libelle,
            "pct": _num(termes.get(cle)),
            "montant_ttc": float(montant) if montant is not None else None,
            "jalon": jalon,
        })
    return sortie


def _sans_industriel(valeur):
    """Copie de ``valeur`` sans les clés VAN / LCOE / sensibilités
    (commercial, D-CIQ-10) — un retrait, jamais un calcul."""
    if isinstance(valeur, dict):
        return {k: _sans_industriel(v) for k, v in valeur.items()
                if k not in CLES_INDUSTRIEL_SEUL}
    if isinstance(valeur, list):
        return [_sans_industriel(v) for v in valeur
                if not (isinstance(v, dict)
                        and v.get("cle") in ENTREES_INDUSTRIEL_SEUL)]
    return valeur


def _est_mt(data, etude_ci, economie):
    tension = _dict(_dict(etude_ci.get("entrees_resolues")).get(
        "tension")).get("valeur")
    if not isinstance(tension, str) or not tension.strip():
        # Sans moteur : la tension DÉCLARÉE à l'écran (une saisie, pas un
        # chiffre calculé).
        tension = _dict(data.get("etude")).get("tension_raccordement")
    if isinstance(tension, str) and tension.strip().lower() in ("mt", "ht"):
        return True
    return _dict(_dict(economie).get("tarif")).get("contrat") == "mt_general"


def _bloc_argent(data, etude_ci, segment):
    """``(argent, motif)`` — CIQ304 : le bloc ``economie_ci`` PUBLIC recopié
    tel quel (valeurs au centime), ou ``None`` + ce qui manque."""
    from apps.ventes.economie_ci import STATUT_CALCULE, economie_ci_publique

    economie = data.get("economie_ci")
    if isinstance(economie, dict) and \
            economie.get("statut") == STATUT_CALCULE:
        # ``economie_ci_publique`` rend une COPIE sans rien d'interne.
        argent = economie_ci_publique(economie)
        if segment != "industriel":
            argent = _sans_industriel(argent)
        return argent, None
    motif = (MOTIF_ARGENT_MT if _est_mt(data, etude_ci, economie)
             else MOTIF_ARGENT_BT)
    return None, motif


# ── la fonction publique ────────────────────────────────────────────────────

def synthese_ci(data):
    """La synthèse C&I d'un devis : dict → dict, PURE ; ``None`` hors C&I
    (la clé est alors ABSENTE de la charge utile, jamais ``null``)."""
    data = data if isinstance(data, dict) else {}
    segment = str(data.get("mode_installation") or "").strip().lower()
    if segment not in SEGMENTS_CI:
        return None
    etude_ci = _dict(_dict(data.get("etude")).get("etude_ci"))
    entrees = _dict(etude_ci.get("entrees_resolues"))
    langue = data.get("langue_sortie") or "fr"
    omissions = []

    statut, a_confirmer = _statut_et_a_confirmer(
        etude_ci, data.get("_entrees_ci_lead"))
    option = _option_servie(data)

    synthese = {
        "version": VERSION,
        "segment": segment,
        "statut_etude": statut,
        "a_confirmer": a_confirmer,
        "provenance": _bloc_provenance(entrees),
        "systeme": _systeme(data, etude_ci, option),
    }
    if synthese["systeme"]["production_kwh_an"] is None:
        omissions.append({"bloc": "systeme.production_kwh_an",
                          "motif": MOTIF_PRODUCTION_ABSENTE})

    baseline, motif = _bloc_baseline(entrees)
    if baseline is not None:
        synthese["baseline"] = baseline
    else:
        omissions.append({"bloc": "baseline", "motif": motif})

    if not etude_ci:
        omissions.append({"bloc": "energie", "motif": MOTIF_SANS_ETUDE})
    else:
        energie, motif = _bloc_energie(etude_ci, langue)
        if energie is not None:
            synthese["energie"] = energie
        else:
            omissions.append({"bloc": "energie", "motif": motif})

    synthese["option_servie"] = option
    option_batterie = _option_batterie(data)
    if option_batterie is not None:
        synthese["option_batterie"] = option_batterie
    argent, motif = _bloc_argent(data, etude_ci, segment)
    if argent is not None:
        synthese["argent"] = argent
    else:
        omissions.append({"bloc": "argent", "motif": motif})
    # CIQ305 — les phrases client C&I, sourcées et trilingues (une table).
    synthese["hypotheses"] = mentions_ci(
        data, sous_reserve=statut == STATUT_SOUS_RESERVE)
    synthese["echeancier"] = _echeancier(data, option)
    synthese["omissions"] = omissions
    return synthese


# ── CIQ307 — les chiffres-clés LUS par les gabarits ET par /proposition ─────

#: Méthode des taux (``energie.methode``) → ligne de méthode imprimée.
LIBELLES_METHODE = {
    "horaire_declare": "Taux calculés heure par heure sur vos horaires "
                       "déclarés.",
    "horaire_mesure": "Taux calculés heure par heure sur votre courbe de "
                      "charge mesurée.",
    "registres_mt": "Taux calculés sur vos registres de compteur MT.",
    "archetype_estimation": "Taux calculés sur un profil type de votre "
                            "activité — estimation.",
    METHODE_INCONNUE: "Taux calculés par estimation.",
}


def chiffres_cles(synthese):
    """Les chiffres d'une ``synthese_ci`` que la couverture, la page
    /proposition et la parité lisent — UNE projection, aucun calcul.

    L'économie de l'année 1 est celle de la base principale (D-CIQ-3) :
    TTC quand la TVA n'est pas récupérable, HT sinon (``economie_ci`` :
    ``total_mad`` = HT, ``total_mad_ttc`` = TTC). Le payback est le seul
    servi : ``argent.indicateurs.retour_ans`` (celui du flux)."""
    s = _dict(synthese)
    systeme = _dict(s.get("systeme"))
    energie = _dict(s.get("energie"))
    argent = _dict(s.get("argent"))
    economie = _dict(argent.get("economie_annee1"))
    revente = _dict(argent.get("revente"))
    if argent.get("base") == "ttc" and \
            economie.get("total_mad_ttc") is not None:
        valeur, libelle_base = economie.get("total_mad_ttc"), "TTC"
    else:
        valeur = economie.get("total_mad")
        libelle_base = "HT" if valeur is not None else None
    methode = energie.get("methode")
    motif_argent = next((o.get("motif") for o in s.get("omissions") or []
                         if isinstance(o, dict) and o.get("bloc") == "argent"),
                        None)
    pointe = next((h for h in s.get("hypotheses") or []
                   if isinstance(h, dict) and h.get("cle") == "pointe"), None)
    return {
        "kwc": _num(systeme.get("kwc")),
        "production_kwh_an": _num(systeme.get("production_kwh_an")),
        "taux_autoconso_pct": _num(energie.get("taux_autoconso_pct")),
        "taux_couverture_pct": _num(energie.get("taux_couverture_pct")),
        "methode": methode,
        "libelle_methode": LIBELLES_METHODE.get(methode) if methode else None,
        "economie_annuelle_mad": _num(valeur),
        "base_economie": libelle_base,
        "payback_ans": _num(_dict(argent.get("indicateurs")).get(
            "retour_ans")),
        "revente_kwh_an": _num(revente.get("kwh_an")),
        "revente_mad_an": _num(revente.get("valeur_mad_an")),
        "sous_reserve": s.get("statut_etude") == STATUT_SOUS_RESERVE,
        "a_confirmer": [a.get("libelle") for a in s.get("a_confirmer") or []
                        if isinstance(a, dict) and a.get("libelle")],
        "motif_argent": motif_argent,
        "argent_mt": motif_argent == MOTIF_ARGENT_MT,
        "note_pointe": _dict(_dict(pointe).get("textes")).get("fr"),
    }
