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

import html

from ..lecture_pure import nombre_normalise
from .mentions import mentions_ci
import logging

logger = logging.getLogger(__name__)

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
#: AMOT39 (C-AMOT-048) — TOUTES les feuilles que ``domain/etude_ci.
#: _consommation`` peut retenir (sept sorties), dans SON ordre de priorité :
#: ``kwh_mensuel_declare`` (kWh mensuel déclaré au lead), ``releve_kwh``
#: (relevés de factures du lead), ``facture_hiver_mad`` (une facture d'hiver
#: convertie) et ``bill_kwh`` (repli QJR662) manquaient — la couverture
#: imprimait alors « non résolue » à côté d'une couverture chiffrée.
CLES_CONSOMMATION = ("kwh_mensuels", "consommation", "kwh_mensuel_declare",
                     "factures_mad", "releve_kwh", "registres_mt",
                     "kwh_annuel", "facture_hiver_mad", "bill_kwh")

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
#: AMOT62 (C-AMOT-052) — écart toléré entre le kWc SERVI et celui de
#: l'étude C&I (``taille.retenue_kwc``) : la garde 2 % du moteur horaire
#: (``pricing._HORAIRE_TOLERANCE_KWC``). Au-delà, production et taux de
#: l'étude décrivent une AUTRE installation : ils ne sont pas servis.
TOLERANCE_KWC_ETUDE = 0.02
MOTIF_ETUDE_AUTRE_PUISSANCE = (
    "étude C&I calculée pour une autre puissance que l'option servie : "
    "production et taux non servis")
MOTIF_PRODUCTION_ABSENTE = (
    "production non servie : seule la production du moteur C&I est imprimée, "
    "jamais une production par ville à côté de taux d'un autre modèle")
MOTIF_BASELINE_ABSENTE = (
    "consommation de référence non résolue par le moteur C&I")
#: AMOT80 — en mots du CLIENT (jamais « moteur C&I »).
MOTIF_ETUDE_A_FAIRE = (
    "étude détaillée de votre site à finaliser : chiffres préliminaires")
LIBELLE_VISITE = "Relevé du site à la visite technique"

#: CIQ304 — ce qui manque quand le moteur n'a pas chiffré l'argent : ce que
#: le CLIENT peut fournir (ses factures), jamais « votre répartition
#: horaire ». Texte du contrat partagé ``proposal_data.json``.
MOTIF_ARGENT_BT = "vos 12 dernières factures"
MOTIF_ARGENT_MT = ("vos 12 dernières factures MT : prix des trois postes, "
                   "prime fixe, puissance souscrite")
#: VAN et LCOE : INDUSTRIEL seulement (D-CIQ-10). En commercial ces clés sont
#: retirées du bloc recopié (jamais recalculées). Le payback actualisé suit la
#: VAN (il n'existe que sur un taux déclaré) : un seul payback servi, celui du
#: flux (``indicateurs.retour_ans``). AMOT97 (D-ACI-15=a) — les sensibilités
#: restent servies au commercial (son scénario prudent est imprimé).
CLES_INDUSTRIEL_SEUL = frozenset({
    "van_mad", "van_motif", "lcoe_mad_kwh", "lcoe_actualise",
    "retour_actualise_ans"})
#: Entrées de listes ``{cle: …}`` (omissions, hypothèses) qui ne parlent que
#: de la VAN — retirées avec elle en commercial.
ENTREES_INDUSTRIEL_SEUL = frozenset({"van_mad", "taux_actualisation_pct"})


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


def _kwh_an_moteur(etude_ci):
    """AMOT41 — la consommation annuelle de référence DU MOTEUR : la somme
    des 12 mois résolus de son bilan (``bilan.par_mois[].consommation_kwh``).
    ``None`` dès qu'un mois manque : jamais une somme partielle, jamais la
    saisie d'écran ``etude.conso_annuelle``."""
    par_mois = _dict(_dict(etude_ci).get("bilan")).get("par_mois")
    if not isinstance(par_mois, (list, tuple)):
        return None
    mois = {}
    for m in par_mois:
        if not isinstance(m, dict):
            continue
        kwh = _num(m.get("consommation_kwh"))
        numero = _num(m.get("mois"))
        if kwh is None or numero is None:
            continue
        mois[int(numero)] = kwh
    if sorted(mois) != list(range(1, 13)):
        return None
    return round(sum(mois.values()), 1)


def _bloc_baseline(entrees, etude_ci=None):
    """``(bloc, motif)`` — la consommation de référence et sa source, lues
    dans la provenance du moteur (jamais devinées). AMOT41 : le bloc porte
    aussi ``kwh_an`` (somme des 12 mois résolus du moteur) quand le bilan la
    donne."""
    bloc, motif = _bloc_baseline_source(entrees)
    if bloc is not None:
        kwh_an = _kwh_an_moteur(etude_ci)
        if kwh_an is not None:
            bloc["kwh_an"] = kwh_an
    return bloc, motif


def _bloc_baseline_source(entrees):
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


def _surplus(bilan):
    """AMOT89 — le surplus annuel du bilan horaire, en kWh SERVIS
    (``surplus_kwh``, ``injecte_valorise_kwh``, ``non_valorise_kwh``) et la
    part non valorisée exprimée en % de la production (un changement
    d'unité, au point près) ; None quand le bilan ne le dit pas."""
    production = _num(bilan.get("production_kwh"))
    surplus = _num(bilan.get("surplus_kwh"))
    non_valorise = _num(bilan.get("non_valorise_kwh"))
    if not production or production <= 0 or surplus is None \
            or non_valorise is None:
        return None
    return {
        "kwh_an": surplus,
        "valorise_kwh_an": _num(bilan.get("injecte_valorise_kwh")) or 0,
        "non_valorise_kwh_an": non_valorise,
        "non_valorise_pct_production": round(non_valorise / production * 100),
    }


def _bloc_energie(etude_ci, langue):
    bilan = _dict(etude_ci.get("bilan"))
    autoconso = _pct(bilan.get("taux_autoconso"))
    couverture = _pct(bilan.get("taux_couverture"))
    if autoconso is None or couverture is None:
        return None, MOTIF_TAUX_ABSENTS
    methode = _dict(etude_ci.get("profil_charge")).get("methode")
    energie = {
        "taux_autoconso_pct": autoconso,
        "taux_couverture_pct": couverture,
        "methode": METHODES.get(methode, METHODE_INCONNUE),
        "definitions": dict(DEFINITIONS.get(langue) or DEFINITIONS["fr"]),
    }
    surplus = _surplus(bilan)
    if surplus is not None:
        energie["surplus"] = surplus
    par_mois = _par_mois(bilan)
    if par_mois is not None:
        energie["par_mois"] = par_mois
    return energie, None


#: AMOT90 — les kWh d'un mois du bilan horaire (``bilan.par_mois[]``).
CLES_MOIS_BILAN = ("production_kwh", "consommation_kwh", "autoconso_kwh",
                   "surplus_kwh")


def _par_mois(bilan):
    """AMOT90 — les 12 mois du bilan horaire du moteur (kWh de production,
    de consommation, autoconsommés et en surplus) recopiés tels quels, dans
    l'ordre des mois ; None dès qu'un mois ou une valeur manque (jamais un
    graphique sur 11 mois)."""
    mois = {}
    for m in bilan.get("par_mois") or []:
        if not isinstance(m, dict) or _num(m.get("mois")) not in range(1, 13):
            continue
        valeurs = {cle: _num(m.get(cle)) for cle in CLES_MOIS_BILAN}
        if all(v is not None and v >= 0 for v in valeurs.values()):
            mois[int(_num(m["mois"]))] = dict(valeurs, mois=int(_num(m["mois"])))
    if sorted(mois) != list(range(1, 13)):
        return None
    return [mois[i] for i in range(1, 13)]


def _bloc_estimation(etude_ci, coherente):
    """AMOT91 — ce sur quoi l'estimation repose, lu sur l'étude du moteur :
    la base de production (``production.source`` / ``inclinaison_deg`` /
    ``azimut_deg``) et la règle de dimensionnement (``taille.pas_kwc`` /
    ``horizon_marginal_annees``, D-CIQ-2 — seulement quand l'étude décrit le
    kWc servi). None quand l'étude ne dit rien de tel."""
    sortie = {}
    production = _dict(etude_ci.get("production"))
    if production.get("source") in ("pvgis", "calepinage"):
        sortie["production"] = {
            "source": production["source"],
            "inclinaison_deg": _num(production.get("inclinaison_deg")),
            "azimut_deg": _num(production.get("azimut_deg"))}
    taille = _dict(etude_ci.get("taille"))
    pas = _num(taille.get("pas_kwc"))
    horizon = _num(taille.get("horizon_marginal_annees"))
    if coherente and taille.get("statut") == "calculee" and pas and horizon:
        sortie["dimensionnement"] = {"pas_kwc": pas, "horizon_annees": horizon}
    return sortie or None


def _onduleurs_au_devis(etude_ci, data):
    """AMOT93 — les onduleurs de la composition sont-ils ceux des lignes du
    devis (désignations) ? Sinon leur puissance AC décrirait une AUTRE
    installation que celle imprimée au tableau."""
    composition = _dict(etude_ci.get("composition"))
    noms = {_norme(li.get("designation"))
            for li in composition.get("lignes") or []
            if isinstance(li, dict)
            and str(li.get("role") or "").startswith("onduleur")}
    au_devis = {_norme(it.get("designation"))
                for it in _dict(data).get("all_items") or []
                if isinstance(it, dict) and not it.get("optionnelle")}
    return bool(noms) and noms <= au_devis


def _bloc_installation(etude_ci, coherente, data=None):
    """AMOT93 — ce que la fiche « Votre installation » lit sur l'étude : la
    puissance AC des onduleurs de la composition (``composition.onduleurs.
    combinaison`` — seulement quand l'étude décrit le kWc servi ET que ses
    onduleurs sont ceux du devis), le type de pose et la surface disponible
    DÉCLARÉS (``entrees_resolues``). None quand rien n'est servi — jamais
    une surface occupée estimée ici."""
    sortie = {}
    combinaison = _dict(_dict(etude_ci.get("composition")).get(
        "onduleurs")).get("combinaison")
    if coherente and isinstance(combinaison, list) \
            and _onduleurs_au_devis(etude_ci, data):
        onduleurs = [{"kw_ac": _num(c.get("kw_ac")),
                      "quantite": _num(c.get("quantite")) or 1}
                     for c in combinaison
                     if isinstance(c, dict) and _num(c.get("kw_ac"))]
        if onduleurs:
            sortie["onduleurs"] = onduleurs
            # AMOT93 — la puissance AC totale, servie UNE fois ici (le
            # gabarit l'imprime telle quelle, sans la recalculer).
            sortie["kw_ac_total"] = sum(o["kw_ac"] * o["quantite"]
                                        for o in onduleurs)
    entrees = _dict(etude_ci.get("entrees_resolues"))
    pose = _dict(entrees.get("type_pose")).get("valeur")
    if isinstance(pose, str) and pose.strip():
        sortie["type_pose"] = pose.strip()
    surface = _num(_dict(entrees.get("surface_utile_m2")).get("valeur"))
    if surface and surface > 0:
        sortie["surface_disponible_m2"] = surface
    return sortie or None


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


def _etude_decrit_kwc(etude_ci, kwc):
    """AMOT62 — l'étude C&I décrit-elle ce kWc (à 2 % près) ? Vrai quand
    l'une des deux puissances est inconnue (rien à comparer)."""
    kwc_etude = _num(_dict(etude_ci.get("taille")).get("retenue_kwc"))
    if kwc is None or kwc_etude is None or kwc_etude <= 0:
        return True
    return abs(float(kwc) - float(kwc_etude)) / float(kwc_etude) \
        <= TOLERANCE_KWC_ETUDE


def _systeme(data, etude_ci, option):
    suffixe = "avec" if option == "avec_batterie" else "sans"
    kwc = _num(data.get(f"puissance_kwc_{suffixe}"))
    if kwc is None:
        kwc = _num(data.get("puissance_kwc"))
    nb = _num(data.get(f"nb_panneaux_{suffixe}"))
    if nb is None:
        nb = _num(data.get("nb_panneaux"))
    # AMOT62 — la production de l'étude n'est servie que si l'étude décrit
    # le kWc SERVI (sinon : ``None`` + motif publié par ``synthese_ci``).
    production = (_num(_dict(etude_ci.get("bilan")).get("production_kwh"))
                  if _etude_decrit_kwc(etude_ci, kwc) else None)
    return {
        "kwc": kwc,
        "nb_panneaux": nb,
        # UNE production : celle du moteur C&I, jamais ``prod_kwh``.
        "production_kwh_an": production,
    }


#: AMOT88 — rôle d'un poste « à chiffrer après la visite » (``composition.
#: lignes[].role``) → ses mots pour le client (le texte servi est français ;
#: les gabarits le traduisent par ``i18n_labels['ci_role_<rôle>']``).
ROLES_POSTES_CLIENT = {
    "cable_dc": "câble DC", "cable_ac": "câble AC",
    "structure_ci": "structure de fixation", "coffret_dc": "coffret DC",
    "coffret_ac": "coffret AC", "protection_ac": "protection AC",
    "onduleur_string_tri": "onduleur", "onduleur_string_mono": "onduleur",
}
PREFIXE_HORS_TOTAL = "À chiffrer après la visite technique, hors total : "


def _norme(texte):
    # C-L3-DOC-07 (24/10/2026) — les désignations de ``all_items`` arrivent
    # ÉCHAPPÉES HTML (« Structure C&amp;I ») alors que la composition garde
    # le texte brut : sans ``html.unescape``, un poste au nom à « & » ajouté
    # au devis restait listé « à chiffrer après la visite » (titre « hors
    # postes » et légende du retour maintenus sur un prix pourtant complet).
    return " ".join(html.unescape(str(texte or "")).split()).casefold()


def postes_hors_total(data, etude_ci):
    """AMOT86 (D-ACI-2=a) — les postes de la composition « à chiffrer après
    la visite » (``composition.a_chiffrer_visite``) restés HORS des lignes du
    devis (même règle que ``economie_ci`` : une ligne ajoutée au devis n'est
    plus hors total), avec leur rôle, leur quantité et leur unité lus sur
    ``composition.lignes`` — jamais un prix. Rend ``[]`` sans poste."""
    composition = _dict(_dict(etude_ci).get("composition"))
    noms = [str(x.get("designation") if isinstance(x, dict) else x)
            for x in composition.get("a_chiffrer_visite") or [] if x]
    au_devis = {_norme(it.get("designation"))
                for it in _dict(data).get("all_items") or []
                if isinstance(it, dict) and not it.get("optionnelle")}
    lignes = {}
    for li in composition.get("lignes") or []:
        if isinstance(li, dict) and li.get("designation"):
            lignes.setdefault(_norme(li["designation"]), li)
    postes = []
    for nom in noms:
        if _norme(nom) in au_devis:
            continue
        ligne = lignes.get(_norme(nom)) or {}
        postes.append({"role": ligne.get("role"), "designation": nom,
                       "quantite": _num(ligne.get("quantite")),
                       "unite": ligne.get("unite"),
                       "catalogue": ligne.get("produit") is not None})
    return postes


def libelle_poste(poste, roles=None):
    """AMOT88 — « câble DC — Câble solaire Nexans… » (article du catalogue)
    ou « structure de fixation » (libellé générique du moteur) ; un rôle
    inconnu garde la désignation telle quelle. ``roles`` : la table des mots
    du client (français par défaut)."""
    role = (roles or ROLES_POSTES_CLIENT).get(poste.get("role"))
    if role is None:
        return poste.get("designation") or ""
    return f"{role} — {poste['designation']}" if poste.get("catalogue") \
        else role


def texte_postes(postes, roles=None):
    """Les postes dans l'ordre, sans doublon (deux câbles AC génériques ne
    font qu'un « câble AC »)."""
    vus = []
    for poste in postes:
        texte_poste = libelle_poste(poste, roles)
        if texte_poste and texte_poste not in vus:
            vus.append(texte_poste)
    return ", ".join(vus)


def _statut_et_a_confirmer(etude_ci, lead, data=None):
    a_confirmer = []
    vus = set()

    def _ajoute(cle, libelle, **extra):
        if cle not in vus:
            vus.add(cle)
            a_confirmer.append(dict({"cle": cle, "libelle": libelle}, **extra))

    if not etude_ci:
        statut = STATUT_SOUS_RESERVE
        _ajoute("etude_ci", MOTIF_ETUDE_A_FAIRE)
    else:
        reserve = _dict(etude_ci.get("sous_reserve_visite"))
        statut = STATUT_SOUS_RESERVE if reserve.get("valeur") else STATUT_FERME
        if reserve.get("valeur"):
            _ajoute("visite", reserve.get("motif") or LIBELLE_VISITE)
        # ADEV79 (D-ACI-2=a) — des lignes « à chiffrer après la visite »
        # (structure, câbles) hors total : le document est une estimation sous
        # réserve de visite et DIT ce qui reste à chiffrer. AMOT88 — chaque
        # poste dit son rôle en mots simples (« câble DC », « structure de
        # fixation ») ; ``postes`` sert la forme structurée aux gabarits.
        hors_total = postes_hors_total(data, etude_ci)
        if hors_total:
            statut = STATUT_SOUS_RESERVE
            _ajoute("a_chiffrer_visite",
                    PREFIXE_HORS_TOTAL + texte_postes(hors_total),
                    postes=hors_total)
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


#: CIQ331 — jalon CIQ212 (``data['jalons_paiement']``) → (jalon, libellé)
#: du contrat ``proposal_data.json`` › ``synthese_ci.echeancier``.
JALONS_N = {
    "commande": ("commande", "À la commande"),
    "acompte": ("commande", "À la commande"),
    "livraison_materiel": ("livraison", "À la livraison"),
    "materiel": ("livraison", "À la livraison"),
    "mise_en_service": ("mise_en_service", "À la mise en service"),
    "solde": ("mise_en_service", "À la mise en service"),
    "reception_definitive": ("reception_definitive",
                             "À la réception définitive"),
}


def _echeancier_n(jalons):
    """CIQ331 — les N jalons servis par le builder (CIQ212,
    ``jalons_paiement_devis`` : montants au centime, le dernier reçoit le
    reliquat) recopiés dans la forme du contrat — aucun recalcul."""
    sortie = []
    for j in jalons:
        if not isinstance(j, dict) or _num(j.get("pct")) is None:
            continue
        cle = str(j.get("jalon") or "")
        jalon, libelle = JALONS_N.get(cle, (cle, str(j.get("libelle") or cle)))
        montant = _num(j.get("montant_ttc"))
        sortie.append({"libelle": libelle, "pct": _num(j.get("pct")),
                       "montant_ttc": montant, "jalon": jalon})
    return sortie


def _echeancier(data, option):
    jalons = data.get("jalons_paiement")
    if isinstance(jalons, list) and jalons:
        sortie = _echeancier_n(jalons)
        if sortie:
            return sortie
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
        # AMOT81 — ou ``tension`` (clé d'un brouillon auto C&I).
        tension = (_dict(data.get("etude")).get("tension_raccordement")
                   or _dict(data.get("etude")).get("tension"))
    if isinstance(tension, str) and tension.strip().lower() in ("mt", "ht"):
        return True
    return _dict(_dict(economie).get("tarif")).get("contrat") == "mt_general"


def est_site_mt(data):
    """AMOT89 — le site est-il raccordé en MT/HT (entrée résolue du moteur,
    sinon tension déclarée à l'écran, sinon contrat MT du tarif servi) ?
    La même lecture que le motif d'argent MT — jamais devinée."""
    data = _dict(data)
    etude_ci = _dict(_dict(data.get("etude")).get("etude_ci"))
    return _est_mt(data, etude_ci, data.get("economie_ci"))


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


#: CIQ314 — libellé d'une garantie lue sur une fiche produit.
LIBELLE_GARANTIE_FABRICANT = "garantie du fabricant"
#: Composants dont la garantie vient du FABRICANT (``theme.warranties_for``) ;
#: la pose (« Installation ») est un engagement de l'installateur, pas d'un
#: fabricant.
COMPOSANTS_FABRICANT = {"Onduleur": "onduleur", "Panneaux": "panneaux",
                        "Performance": "panneaux_performance",
                        "Batterie": "batterie"}


def _om_option(data):
    lignes = [li for li in data.get("om_ci_lignes") or []
              if isinstance(li, dict)]
    if not lignes:
        return None
    souscrites = [li for li in lignes if not li.get("optionnelle")]
    retenues = souscrites or lignes
    prix = [_num(li.get("ht")) for li in retenues]
    sans_prix = any(p is None or p <= 0 for p in prix)
    if sans_prix:
        statut = "tarif_a_renseigner"
    else:
        statut = "souscrit" if souscrites else "propose"
    return {
        "statut": statut,
        "libelle": " ; ".join(str(li.get("designation") or "")
                              for li in retenues),
        # Les montants des LIGNES, recopiés tels que le builder les sert.
        "lignes": [{"designation": li.get("designation"),
                    "total_ht": _num(li.get("ht")),
                    "total_ttc": _num(li.get("ttc"))} for li in retenues],
    }


def _om_composition(data):
    """AMOT83 (D-ACI-12=a) — l'option O&M NOMMÉE par la composition C&I
    (``options[cle='om']``) quand le devis ne porte aucune ligne ``om_ci`` :
    statut « tarif à renseigner », jamais un prix."""
    composition = _dict(_dict(_dict(data.get("etude")).get("etude_ci")).get(
        "composition"))
    om = next((o for o in composition.get("options") or []
               if isinstance(o, dict) and o.get("cle") == "om"), None)
    libelle = html.escape(str((om or {}).get("libelle") or "").strip(),
                          quote=False)
    if not libelle:
        return None
    return {"statut": "tarif_a_renseigner", "libelle": libelle,
            "lignes": [{"designation": libelle, "total_ht": None,
                        "total_ttc": None}]}


def _garanties(data):
    try:
        from ..residential import theme
        bande = theme.warranties_for(data) or []
    except Exception:  # noqa: BLE001 — un rendu ne casse jamais ici (D-ENF22-BLE001)
        logger.warning("synthese._garanties : erreur ignorée (mode dégradé)", exc_info=True)
        return []
    sortie = []
    for n, unite, libelle, _sous in bande:
        composant = COMPOSANTS_FABRICANT.get(libelle)
        if composant is None or not str(n).strip():
            continue
        sortie.append({"composant": composant,
                       "texte": f"{libelle} : {n} {unite}",
                       "source": LIBELLE_GARANTIE_FABRICANT})
    return sortie


def _services(data):
    """``{om_option?, suivi_production?, garanties[]}`` (contrat CIQ4) :
    l'O&M NOMMÉE du devis (prix saisi ou « à renseigner »), le délai
    d'intervention SAISI par la société, les garanties des fabricants.
    Clé absente quand le devis ne la porte pas — jamais un défaut."""
    services = {}
    om = _om_option(data) or _om_composition(data)
    if om is not None:
        services["om_option"] = om
    # AMOT83 (D-ACI-12=a) — le suivi de production est NOMMÉ ; son délai
    # n'est imprimé que s'il est saisi (jamais un défaut).
    delai = _num(data.get("delai_intervention_suivi_heures"))
    services["suivi_production"] = {"delai_intervention": delai or None}
    # AMOT83 (D-ACI-11=a) — régime 82-21 calculé ⇒ le dossier est monté par
    # la société (phrase fixe, jamais le texte de loi, D-CIQ-6).
    regime = _dict(_dict(_dict(data.get("etude")).get("etude_ci")).get(
        "regime_8221_suggere")).get("regime")
    if regime and regime != "aucun":
        services["raccordement"] = {"regime": regime}
    services["garanties"] = _garanties(data)
    return services


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
        etude_ci, data.get("_entrees_ci_lead"), data)
    option = _option_servie(data)

    synthese = {
        "version": VERSION,
        "segment": segment,
        "statut_etude": statut,
        "a_confirmer": a_confirmer,
        "provenance": _bloc_provenance(entrees),
        "systeme": _systeme(data, etude_ci, option),
    }
    etude_coherente = _etude_decrit_kwc(etude_ci, synthese["systeme"]["kwc"])
    if synthese["systeme"]["production_kwh_an"] is None:
        omissions.append({"bloc": "systeme.production_kwh_an",
                          "motif": (MOTIF_PRODUCTION_ABSENTE if etude_coherente
                                    else MOTIF_ETUDE_AUTRE_PUISSANCE)})

    baseline, motif = _bloc_baseline(entrees, etude_ci)
    if baseline is not None:
        synthese["baseline"] = baseline
    else:
        omissions.append({"bloc": "baseline", "motif": motif})

    if not etude_ci:
        omissions.append({"bloc": "energie", "motif": MOTIF_SANS_ETUDE})
    elif not etude_coherente:
        # AMOT62 — taux d'une autre installation : non servis, motif publié.
        omissions.append({"bloc": "energie",
                          "motif": MOTIF_ETUDE_AUTRE_PUISSANCE})
    else:
        energie, motif = _bloc_energie(etude_ci, langue)
        if energie is not None:
            synthese["energie"] = energie
        else:
            omissions.append({"bloc": "energie", "motif": motif})

    estimation = _bloc_estimation(etude_ci, etude_coherente)
    if estimation is not None:
        synthese["estimation"] = estimation
    installation = _bloc_installation(etude_ci, etude_coherente, data)
    if installation is not None:
        synthese["installation"] = installation
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
    # CIQ330 — le contenu par catégorie commerciale (UNE table trilingue).
    if segment == "commercial":
        from .categories import categorie_ci
        synthese["categorie"] = categorie_ci(data, synthese)
    # CIQ344 — décarbonation (industriel) : CBAM seulement pour un
    # exportateur UE DÉCLARÉ de ciment ou d'engrais, sinon la phrase générique.
    if segment == "industriel":
        from .mentions import decarbonation_ci
        synthese["decarbonation"] = decarbonation_ci(data)
    # CIQ314 — services : seulement ce que le devis porte (D-CIQ-12).
    synthese["services"] = _services(data)
    synthese["echeancier"] = _echeancier(data, option)
    # CIQ309 — l'entreprise cliente, recopiée telle que le builder la sert.
    entreprise = data.get("entreprise_client")
    if isinstance(entreprise, dict) and any(entreprise.values()):
        synthese["entreprise_client"] = dict(entreprise)
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
    baseline = _dict(s.get("baseline"))
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
    # AMOT80 / ADEV81 — investissement non chiffré : son motif (omission
    # ``investissement_mad`` du bloc servi), jamais un retour.
    motif_investissement = next(
        (o.get("motif") for o in argent.get("omissions") or []
         if isinstance(o, dict) and o.get("cle") == "investissement_mad"),
        None)
    # AMOT86 — postes « à chiffrer après la visite » restés hors total.
    hors_total = next(
        (a.get("postes") for a in s.get("a_confirmer") or []
         if isinstance(a, dict) and a.get("cle") == "a_chiffrer_visite"), None)
    return {
        "kwc": _num(systeme.get("kwc")),
        "production_kwh_an": _num(systeme.get("production_kwh_an")),
        # AMOT41 — la consommation de référence du MOTEUR (Σ 12 mois).
        "conso_kwh_an": _num(baseline.get("kwh_an")),
        "taux_autoconso_pct": _num(energie.get("taux_autoconso_pct")),
        "taux_couverture_pct": _num(energie.get("taux_couverture_pct")),
        "methode": methode,
        "libelle_methode": LIBELLES_METHODE.get(methode) if methode else None,
        "economie_annuelle_mad": _num(valeur),
        "base_economie": libelle_base,
        # AMOT95 — base « deux » : la TTC servie, imprimée à côté de la HT.
        "economie_annuelle_ttc_mad": _num(economie.get("total_mad_ttc"))
        if argent.get("base") == "deux" and valeur is not None else None,
        "payback_ans": _num(_dict(argent.get("indicateurs")).get(
            "retour_ans")),
        "revente_kwh_an": _num(revente.get("kwh_an")),
        "revente_mad_an": _num(revente.get("valeur_mad_an")),
        "sous_reserve": s.get("statut_etude") == STATUT_SOUS_RESERVE,
        "a_confirmer": [a.get("libelle") for a in s.get("a_confirmer") or []
                        if isinstance(a, dict) and a.get("libelle")],
        "motif_argent": motif_argent,
        "argent_mt": motif_argent == MOTIF_ARGENT_MT,
        "motif_investissement": motif_investissement,
        "postes_hors_total": list(hors_total or []),
        # AMOT89 — définitions servies des deux taux et surplus du bilan.
        "definitions": dict(_dict(energie.get("definitions"))),
        "surplus": _dict(energie.get("surplus")) or None,
        "note_pointe": _dict(_dict(pointe).get("textes")).get("fr"),
    }
