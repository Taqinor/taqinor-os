"""AGR304 — ``synthese_agricole(data)`` : UNE fonction serveur PURE qui dit
l'eau, la pompe, les hypothèses et leur provenance d'un devis de pompage.

POURQUOI. Le une-page agricole et la page /proposition racontaient deux
histoires : le PDF lisait quelques clés v1 de l'étude, la page recalculait
dans le navigateur (bassin « ×2 », FDA, carburant). Le canon résidentiel a
déjà le bon patron — ``residential/renderer.synthese_economies``, servie telle
quelle aux deux supports (PVCOV). Ce module est son jumeau agricole : le PDF
(renderer agricole, AGR310) et ``proposal_data`` (AGR308) appellent LA MÊME
fonction sur le MÊME ``data``.

CE QU'ELLE LIT — ``data`` SEUL (la charge utile de ``build_quote_data``) :
  * ``data['etude']`` : les clés ``etude_params`` pompage v2 du contrat
    partagé ``contract_samples/etude_pompage_preview.json`` (AGR2 :
    ``mode_pompe``, ``plaque``, ``besoin``, ``source``, ``besoin_mensuel``,
    ``production``, ``conception``, ``champ``, ``ha_irrigables``,
    ``provenance_pompage``…) et les dérivées v1 que le NOUVEAU moteur écrit
    pour son rendu (``pompe_cv``, ``pompe_kw``, ``hmt_m``, ``debit_hmt_m3h``,
    ``m3_jour``, ``heures_pompage``, ``champ_kwc`` — D-AGR-13) ;
  * ``data['all_items']`` : chaque item de ligne porte ``role_pompage`` et
    ``courbe_pompe`` copiés du produit par le builder (contrat stock
    ``produit_pompage.json`` › ``item_ligne_devis_rendu``, AGR7) ;
  * ``data['options_proposees']`` : le bloc XSAL5 existant (supplément
    canonique QJR616).

CE QU'ELLE REND — la forme ``synthese_agricole`` du contrat partagé
``contract_samples/proposal_data.json`` › ``exemple_agricole`` (AGR4). Une
sous-clé optionnelle (``besoin_vs_livre``, ``point_fonctionnement``,
``pompe.plaque``) est ABSENTE quand elle n'a rien d'honnête à montrer, et son
motif est nommé dans ``omissions`` — jamais un zéro, jamais un tiret chiffré.

CE QU'ELLE NE FAIT JAMAIS :
  * aucun accès base de données, aucun appel réseau (fonction pure) ;
  * aucun RECALCUL : besoin, production, mois critique, hectares sont lus tels
    que servis par le moteur pompage (AGR2) ;
  * aucune constante ressuscitée de ``ce7e9f01^`` (``agricole/economics.py``,
    ``constants.py``, ``cover.py`` : litres/h/CV, prix des carburants, % FDA) ;
  * aucun ``prix_achat`` ni marge (les items ne sont jamais recopiés en bloc) ;
  * aucun changement de statut (règle #4 : le moteur ne fait que RENDRE).
"""
from __future__ import annotations

from ..lecture_pure import nombre_normalise
from .garanties import garanties_pompage_et_omissions
from .mentions import formalites, regle_fda
from .schema import schema_svg

#: Version de la forme servie (contrat AGR4).
VERSION = 2

#: D-AGR-8 — ce que le kit de pompage n'inclut JAMAIS, dit au client.
NON_INCLUS = ("forage", "genie_civil")

#: Vocabulaire ``detail`` d'une provenance qui vaut MESURE du point d'eau
#: (contrat crm ``lead_pompage.json`` : ``mesure_visite`` ; contrat AGR2 :
#: ``foreur`` = essai de débit du foreur). Tout le reste (déclaration du
#: client, site web, dérivé) reste « à confirmer par la visite » (D-AGR-4).
DETAILS_MESURES = frozenset({"mesure_visite", "foreur"})

#: Entrées du point d'eau dont la MESURE conditionne le devis (D-AGR-4), dans
#: l'ordre d'affichage.
ENTREES_POINT_D_EAU = (
    "niveau_statique_m",
    "niveau_dynamique_m",
    "debit_exploitation_m3h",
    "profondeur_forage_m",
)

#: Les trois clés, et les trois seulement, d'une provenance (contrat AGR2).
CLES_PROVENANCE = ("origine", "detail", "date")

#: Clés d'une plaque de pompe existante (contrat AGR2 › ``corps.plaque``).
CLES_PLAQUE = ("kw", "tension_v", "phases", "cv", "courant_a")

#: Omissions de principe, vraies pour TOUT devis agricole aujourd'hui.
OMISSIONS_DE_PRINCIPE = (
    {"bloc": "preuve_realisation",
     "motif": "aucune réalisation de pompage saisie (D-AGR-10) : jamais un "
              "toit à la place"},
    {"bloc": "co2",
     "motif": "aucun facteur d'émission diesel ou GPL relu à une source "
              "primaire : bloc masqué en agricole"},
)

MOTIF_SANS_COURBE = (
    "courbe constructeur non disponible pour cette pompe : point de "
    "fonctionnement omis (aucune pompe à courbe chiffrée — QXG3)")
MOTIF_POINT_INCONNU = (
    "HMT ou débit retenu inconnu : point de fonctionnement omis")
MOTIF_SERIES_ABSENTES = (
    "série mensuelle de besoin ou d'eau livrée absente : comparaison omise")
MOTIF_CULTURE_INCONNUE = (
    "culture ou région inconnue : besoin agronomique non calculable, "
    "comparaison omise")
MOTIF_ET0_NON_SOURCEE = (
    "ET0 sans source : besoin agronomique non publiable, comparaison omise")
MOTIF_MODE_POMPE_INCONNU = (
    "mode de pompe (neuve ou existante) non renseigné")
MOTIF_ECONOMIES_ABSENTES = (
    "aucune dépense actuelle déclarée par le client (énergie, consommation, "
    "prix payé) : économies non chiffrées")
MOTIF_ENERGIE_NON_DECLAREE = (
    "énergie actuelle non déclarée par le client : jamais la valeur par "
    "défaut de l'écran")

#: AGR307 — clés du bloc AGR3 qui ne sortent JAMAIS vers un client (contrat
#: ``economie_pompage.json`` › ``vue_interne`` : VAN, repère « butane au coût
#: réel » D-AGR-5, aide FDA indicative…).
CLES_INTERNES_AGR3 = ("vue_interne",)

#: AGR307 — la condition de toute économie agricole, dite au client à côté du
#: bloc (texte STRUCTUREL imprimé par le renderer — jamais ajouté au bloc
#: AGR3, qui est recopié champ à champ).
CONDITION_ECONOMIES = {
    "fr": "Si le solaire remplace tout votre pompage actuel, à volume pompé "
          "égal.",
    "en": "If solar replaces all of your current pumping, for the same "
          "volume pumped.",
    "ar": "إذا عوّضت الطاقة الشمسية كل ضخّكم الحالي، بنفس حجم الماء المضخوخ.",
}


# ── utilitaires purs ────────────────────────────────────────────────────────

_num = nombre_normalise


def _dict(v):
    return v if isinstance(v, dict) else {}


def _serie_12(v):
    """Série mensuelle de 12 nombres, ou None (jamais complétée de zéros)."""
    if isinstance(v, dict):
        v = v.get("m3_jour_mois")
    if not isinstance(v, (list, tuple)) or len(v) != 12:
        return None
    serie = [_num(x) for x in v]
    if any(x is None for x in serie):
        return None
    return serie


def _provenance(p):
    """Une provenance réduite à la forme UNIQUE {origine, detail, date}."""
    if not isinstance(p, dict) or not p.get("origine"):
        return None
    return {cle: p.get(cle) for cle in CLES_PROVENANCE}


def _est_mesure(p):
    return bool(p) and p.get("detail") in DETAILS_MESURES


# ── blocs ───────────────────────────────────────────────────────────────────

#: AMOT43 — LISTE BLANCHE d'affichage de la provenance (bloc page 1, borné :
#: aucun débordement) : le point d'eau, la HMT saisie, le volume, l'énergie.
PROVENANCE_AFFICHEE = ENTREES_POINT_D_EAU + (
    "hmt_m", "volume_m3_jour", "energie_actuelle")
#: AMOT43 — clé de la HMT SAISIE dans ``entrees_resolues`` (producteur
#: ``domain/pompage.CHEMINS`` : ``hmt.saisie_m``) → clé d'affichage ``hmt_m``.
CLE_HMT_SAISIE = "hmt_saisie_m"


def _entrees_provenance(etude):
    """AMOT43 — les provenances RÉELLES du producteur
    (``domain.pompage.derivees_de_l_etude`` : ``provenance_pompage =
    {'entrees': {clé: provenance}, '_empreinte': …}``) ; les clés internes
    (``_empreinte``) ne sont jamais des entrées. La HMT saisie est lue sous
    sa clé d'affichage ``hmt_m``."""
    entrees = dict(_dict(_dict(etude.get("provenance_pompage")).get("entrees")))
    if CLE_HMT_SAISIE in entrees and "hmt_m" not in entrees:
        entrees["hmt_m"] = entrees[CLE_HMT_SAISIE]
    return entrees


def _bloc_provenance(etude):
    entrees = _entrees_provenance(etude)
    sortie = {}
    for cle in PROVENANCE_AFFICHEE:
        prov = _provenance(entrees.get(cle))
        if prov is not None:
            sortie[cle] = prov
    return sortie


def _hmt_est_calculee(etude):
    """HMT calculée depuis ses composantes (niveau dynamique + pertes…) plutôt
    que saisie d'un bloc (contrat AGR2 › ``hmt.source``)."""
    return bool(_dict(etude.get("hmt_composantes")))


def _a_confirmer_par_visite(etude, provenance):
    """Entrées du point d'eau qui ne sont PAS mesurées (D-AGR-4).

    Une liste vide veut dire : niveau, débit du forage et profondeur sont
    mesurés (visite ou essai du foreur). Une HMT SAISIE d'un bloc sans
    mesure est elle aussi à confirmer ; une HMT CALCULÉE suit la mesure du
    niveau dynamique, déjà vérifiée ci-dessus.
    """
    a_confirmer = [cle for cle in ENTREES_POINT_D_EAU
                   if not _est_mesure(provenance.get(cle))]
    if (not _hmt_est_calculee(etude)
            and not _est_mesure(provenance.get("hmt_m"))):
        a_confirmer.append("hmt_m")
    return a_confirmer


def _estimation(etude):
    """Le m³/jour est-il une estimation ? Non seulement quand il sort de la
    courbe constructeur sur l'irradiation PVGIS du site (contrat AGR2 ›
    ``production.mode`` / ``source_irradiation``) ; toute autre origine
    (débit déclaré, repli plat, aucune production) est une estimation."""
    production = _dict(etude.get("production"))
    return not (production.get("mode") == "courbe"
                and production.get("source_irradiation") == "pvgis")


def _item_pompe(items):
    """La ligne POMPE : par son ``role_pompage`` (contrat AGR7) ; repli sur la
    seule ligne qui porte une courbe constructeur (une courbe n'existe que sur
    une pompe) — jamais un nouveau mot-clé ad hoc sur la désignation."""
    items = [it for it in (items or []) if isinstance(it, dict)]
    for it in items:
        if it.get("role_pompage") == "pompe":
            return it
    avec_courbe = [it for it in items if it.get("courbe_pompe")]
    return avec_courbe[0] if len(avec_courbe) == 1 else None


def _courbe_points(courbe):
    """``{debits_m3h, hmt_m}`` → ``[[debit, hmt], …]`` ; None si la courbe ne
    respecte pas le contrat (deux listes de même longueur, ≥ 2 points)."""
    courbe = _dict(courbe)
    debits = courbe.get("debits_m3h")
    hmts = courbe.get("hmt_m")
    if (not isinstance(debits, (list, tuple))
            or not isinstance(hmts, (list, tuple))
            or len(debits) != len(hmts) or len(debits) < 2):
        return None
    points = [[_num(q), _num(h)] for q, h in zip(debits, hmts)]
    if any(q is None or h is None for q, h in points):
        return None
    return points


def _bloc_besoin_vs_livre(etude):
    """(bloc, motif) — bloc None quand il est omis, motif dit pourquoi."""
    besoin_mensuel = etude.get("besoin_mensuel")
    besoin_saisi = _dict(etude.get("besoin"))
    nature = (_dict(besoin_mensuel).get("nature")
              or besoin_saisi.get("nature"))
    if nature == "agronomique_plein":
        cultures = besoin_saisi.get("cultures") or []
        cultures_connues = bool(cultures) and all(
            isinstance(c, dict) and c.get("crop") for c in cultures)
        if not cultures_connues or not besoin_saisi.get("region"):
            return None, MOTIF_CULTURE_INCONNUE
        if not _dict(besoin_mensuel).get("source_et0"):
            return None, MOTIF_ET0_NON_SOURCEE
    besoin = _serie_12(besoin_mensuel)
    livre = _serie_12(_dict(etude.get("production")))
    if besoin is None or livre is None:
        return None, MOTIF_SERIES_ABSENTES
    return {
        "mois": [{"besoin_m3_jour": b, "livre_m3_jour": q}
                 for b, q in zip(besoin, livre)],
        "mois_le_plus_serre": _num(
            _dict(etude.get("conception")).get("mois_critique")),
        "hectares_irrigables": _num(
            _dict(etude.get("ha_irrigables")).get("valeur")),
        "base_besoin": nature,
    }, None


def _bloc_point_fonctionnement(items, eau):
    pompe = _item_pompe(items)
    courbe = _courbe_points((pompe or {}).get("courbe_pompe"))
    if courbe is None:
        return None, MOTIF_SANS_COURBE
    if eau.get("debit_hmt_m3h") is None or eau.get("hmt_m") is None:
        return None, MOTIF_POINT_INCONNU
    return {
        "courbe": courbe,
        "point": {"debit_m3h": eau["debit_hmt_m3h"], "hmt_m": eau["hmt_m"]},
    }, None


def _bloc_schema(etude, eau):
    source = _dict(etude.get("source"))
    return {
        "profondeur_m": _num(source.get("profondeur_forage_m")),
        "niveau_m": _num(source.get("niveau_dynamique_m")),
        "distance_m": _num(etude.get("distance_champ_m")),
        "hmt_m": eau.get("hmt_m"),
        # Bassin dessiné seulement s'il est DÉCLARÉ (aucun bassin dimensionné,
        # aucun « ×2 » — AGR301) : son volume déclaré, sinon None.
        "bassin": _num(source.get("volume_reservoir_m3")),
    }


def _bloc_options_kit(options):
    sortie = []
    for o in options or []:
        if not isinstance(o, dict):
            continue
        sortie.append({
            "ligne_id": o.get("id"),
            "designation": o.get("designation"),
            "total_ttc": _num(o.get("total_ttc")),
        })
    return sortie


def _mode_pompe(etude, items):
    mode = etude.get("mode_pompe")
    if mode in ("neuve", "existante"):
        return mode
    # Sans saisie explicite, une ligne pompe dans le devis veut dire « pompe
    # neuve fournie » (D-AGR-7) ; sans ligne pompe, on ne devine rien.
    return "neuve" if _item_pompe(items) is not None else None


def _bloc_economies(bloc):
    """AGR307 — ``(bloc, motif)`` : le bloc PUBLIC ``economie_pompage`` (AGR3)
    recopié champ à champ, SANS aucun recalcul ; ``vue_interne`` n'en sort
    jamais. Omis (motif) quand il est absent, omis par le moteur ou non
    publiable : un chiffre non publiable n'atteint pas le document."""
    if not isinstance(bloc, dict) or not bloc:
        return None, MOTIF_ECONOMIES_ABSENTES
    if bloc.get("statut") != "calcule" or not bloc.get("publiable_client"):
        motifs = [m for m in (bloc.get("motifs_non_publiable") or [])
                  if isinstance(m, str) and m]
        return None, ("; ".join(motifs) if motifs
                      else MOTIF_ECONOMIES_ABSENTES)
    return {cle: valeur for cle, valeur in bloc.items()
            if cle not in CLES_INTERNES_AGR3}, None


def _energie_actuelle(etude):
    """AGR307 — l'énergie actuelle DÉCLARÉE (``saisies_economie_pompage``,
    contrat AGR3), ou None : sans provenance, ce n'est pas une déclaration —
    l'ancienne clé ``current_fuel`` (défaut « butane » de l'écran) n'est
    JAMAIS lue."""
    saisie = _dict(_dict(etude.get("saisies_economie_pompage"))
                   .get("energie_actuelle"))
    valeur = saisie.get("valeur")
    provenance = _provenance(saisie.get("provenance"))
    if not valeur or provenance is None:
        return None
    return {"valeur": valeur, "provenance": provenance}


# ── la fonction publique ────────────────────────────────────────────────────

def synthese_agricole(data):
    """La synthèse agricole d'un devis : dict → dict, PURE.

    Mêmes entrées ⇒ même sortie, octet pour octet : c'est ce qui permet au PDF
    et à /proposition de servir les MÊMES chiffres (test de parité AGR308).
    """
    data = data if isinstance(data, dict) else {}
    etude = _dict(data.get("etude"))
    items = data.get("all_items") or []
    omissions = []

    eau = {
        "m3_jour": _num(etude.get("m3_jour")),
        "heures_pompage": _num(etude.get("heures_pompage")),
        "hmt_m": _num(etude.get("hmt_m")),
        "debit_hmt_m3h": _num(etude.get("debit_hmt_m3h")),
        "estimation": _estimation(etude),
    }
    provenance = _bloc_provenance(etude)
    champ = _dict(etude.get("champ"))

    synthese = {"version": VERSION}

    mode = _mode_pompe(etude, items)
    if mode is not None:
        synthese["mode_pompe"] = mode
    else:
        omissions.append({"bloc": "mode_pompe",
                          "motif": MOTIF_MODE_POMPE_INCONNU})

    synthese["eau"] = eau
    synthese["provenance"] = provenance
    synthese["a_confirmer_par_visite"] = _a_confirmer_par_visite(
        etude, provenance)

    pompe = {"cv": _num(etude.get("pompe_cv")),
             "kw": _num(etude.get("pompe_kw"))}
    if mode == "existante":
        plaque = _dict(etude.get("plaque"))
        if plaque:
            pompe["plaque"] = {cle: plaque.get(cle) for cle in CLES_PLAQUE}
        else:
            omissions.append({
                "bloc": "pompe.plaque",
                "motif": "pompe existante sans plaque relevée (kW, tension, "
                         "phases) : compatibilité non vérifiable"})
    synthese["pompe"] = pompe

    synthese["champ"] = {
        "kwc": _num(champ.get("kwc")) if champ.get("kwc") is not None
        else _num(etude.get("champ_kwc")),
        "nb_panneaux": _num(champ.get("nb_panneaux")),
    }

    besoin_vs_livre, motif = _bloc_besoin_vs_livre(etude)
    if besoin_vs_livre is not None:
        synthese["besoin_vs_livre"] = besoin_vs_livre
    else:
        omissions.append({"bloc": "besoin_vs_livre", "motif": motif})

    point, motif = _bloc_point_fonctionnement(items, eau)
    if point is not None:
        synthese["point_fonctionnement"] = point
    else:
        omissions.append({"bloc": "point_fonctionnement", "motif": motif})

    # AGR306 — la RÈGLE de l'aide FDA (jamais un montant propre au client) :
    # règle société saisie (AGR207, passée par le builder) sinon repli daté.
    synthese["aide_fda"] = regle_fda(
        data.get("regle_fda_societe"),
        nom_societe=_dict(data.get("entreprise")).get("nom"))

    # AGR305 — garanties par composant, lues sur les fiches des lignes
    # (jamais ``theme.WARRANTIES``) ; composants sans durée → omissions.
    garanties, omissions_garanties = garanties_pompage_et_omissions(items)
    synthese["garanties"] = garanties
    omissions.extend(omissions_garanties)

    synthese["schema"] = _bloc_schema(etude, eau)
    # AGR309 — UN seul dessin pour le PDF et la page : le SVG du schéma,
    # tracé sur les seules valeurs saisies, servi tel quel.
    synthese["schema_svg"] = schema_svg(
        synthese, langue=data.get("langue_sortie") or "fr")
    # AGR307 — l'argent : le bloc public AGR3 tel quel (posé par le builder
    # dans ``data['_economie_pompage']``), sinon absent et motivé.
    economies, motif = _bloc_economies(data.get("_economie_pompage"))
    if economies is not None:
        synthese["economies"] = economies
    else:
        omissions.append({"bloc": "economies", "motif": motif})
    energie = _energie_actuelle(etude)
    if energie is not None:
        synthese["energie_actuelle"] = energie
    else:
        omissions.append({"bloc": "energie_actuelle",
                          "motif": MOTIF_ENERGIE_NON_DECLAREE})
    synthese["options_kit"] = _bloc_options_kit(data.get("options_proposees"))
    synthese["non_inclus"] = list(NON_INCLUS)
    # AGR306 — les formalités du client (82-21 hors réseau, 36-15 eau).
    synthese["formalites"] = formalites()

    omissions.extend(dict(o) for o in OMISSIONS_DE_PRINCIPE)
    synthese["omissions"] = omissions
    return synthese
