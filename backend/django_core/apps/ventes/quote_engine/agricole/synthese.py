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

import re
import unicodedata

from core.pompage.hypotheses import valeur as hypothese_valeur
from core.pompage.kit import MENTION_COMPTEUR

from ..i18n_labels import est_rtl, libelle
from ..lecture_pure import nombre_normalise
from .garanties import garanties_pompage_et_omissions
from .mentions import etapes_suivantes, formalites, regle_fda
from .schema import schema_svg

#: Version de la forme servie (contrat AGR4).
VERSION = 2

#: D-AGR-8 — ce que le kit de pompage n'inclut JAMAIS, dit au client.
NON_INCLUS = ("forage", "genie_civil")

#: Vocabulaire ``detail`` d'une provenance qui vaut MESURE du point d'eau
#: (contrat crm ``lead_pompage.json`` : ``mesure_visite`` ; contrat AGR2 :
#: ``foreur`` = essai de débit du foreur). Tout le reste (déclaration du
#: client, site web, dérivé) reste « à confirmer par la visite » (D-AGR-4).
DETAILS_MESURES = frozenset({"mesure_visite", "foreur", "essai"})

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


#: D-AGQ-13 — motif d'omission du bloc SAV.
MOTIF_SAV_NON_SAISI = ("délai d'intervention non saisi dans Paramètres "
                       "(aucun délai inventé)")


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

#: AMOT43 (C-AMOT-054) — LISTE BLANCHE d'affichage des provenances : le
#: point d'eau, le volume, l'énergie et la HMT saisie — le bloc page 1 ne
#: dépasse jamais ces entrées (aucun débordement par 30 clés techniques).
LISTE_BLANCHE_PROVENANCE = ENTREES_POINT_D_EAU + (
    "volume_m3_jour", "energie_actuelle", "hmt_m")
#: Clés du producteur (``domain.pompage`` › ``entrees_resolues``) renommées
#: dans le vocabulaire du rendu.
_ALIAS_PROVENANCE = {"hmt_saisie_m": "hmt_m"}


def _bloc_provenance(etude):
    """AMOT43 — la provenance RÉELLE du point d'eau, lue dans la forme du
    PRODUCTEUR (``domain.pompage.derivees_de_l_etude`` :
    ``provenance_pompage = {'entrees': {cle: provenance}, '_empreinte': …}``)
    — ``_empreinte`` ignorée, ``hmt_saisie_m`` lue comme ``hmt_m``, seules les
    entrées de :data:`LISTE_BLANCHE_PROVENANCE` gardées."""
    entrees = _dict(_dict(etude.get("provenance_pompage")).get("entrees"))
    sortie = {}
    for cle, p in entrees.items():
        cle = _ALIAS_PROVENANCE.get(cle, cle)
        if cle not in LISTE_BLANCHE_PROVENANCE:
            continue
        prov = _provenance(p)
        if prov is not None:
            # AGQ28 — la VALEUR à côté de sa provenance (lue, jamais
            # recalculée) ; None quand l'étude ne la porte pas.
            prov["valeur"] = _valeur_entree(etude, cle)
            sortie[cle] = prov
    return sortie


def _valeur_entree(etude, cle):
    """AGQ28 — la valeur d'une entrée de provenance telle que servie :
    saisie du devis (``besoin``, ``source``), sinon valeur résolue du lead
    (``entrees_pompage``) ; l'énergie actuelle est un mot (``butane``…)."""
    if cle == "energie_actuelle":
        return (_energie_actuelle(etude) or {}).get("valeur")
    if cle == "hmt_m":
        return _num(etude.get("hmt_m"))
    if cle == "volume_m3_jour":
        saisie = _dict(etude.get("besoin")).get("volume_m3_jour")
    else:
        saisie = _dict(etude.get("source")).get(cle)
    return _num(_resolue(etude, saisie, cle))


def _controle_forage(eau, etude):
    """AGQ28 — « pompe X m³/h ≤ forage Y m³/h » : le débit retenu de la
    pompe contre le débit d'exploitation du forage ; None sans l'un des
    deux (aucun débit supposé)."""
    pompe = eau.get("debit_hmt_m3h")
    forage = _valeur_entree(etude, "debit_exploitation_m3h")
    if pompe is None or forage is None:
        return None
    return {"debit_pompe_m3h": pompe, "debit_forage_m3h": forage,
            "conforme": pompe <= forage}


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
    # AMOT65 (D-AMOT-6 = a) — quand le noyau sert ses ``etiquettes`` (AGM8),
    # elles FONT foi : une courbe calculée par similitude (P ∝ n³) ou sans
    # rendement publié est une estimation, même sur PVGIS.
    if "etiquettes" in production:
        return bool(production.get("etiquettes"))
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


def _mois(v):
    """Un numéro de mois 1-12, sinon None."""
    n = _num(v)
    return int(n) if n is not None and n == int(n) and 1 <= n <= 12 else None


def _au_plus_bas(etude):
    """AGQ3 — ``(m³/j, mois)`` le plus bas de l'ANNÉE sur la série livrée
    servie (``production.m3_jour_mois``) ; ``(None, None)`` sans série."""
    serie = _serie_12(_dict(etude.get("production")))
    if serie is None:
        return None, None
    return min(serie), serie.index(min(serie)) + 1


def _mois_sous_tolerance(etude):
    """AGQ3 (D-AGQ-2) — ``[{mois, couverture_pct}]`` de chaque mois
    d'irrigation sous la tolérance de conception, LUS dans
    ``controle_conception.mois_sous_tolerance`` et ``couverture_pct_mois``
    servis par le moteur (AGQ2) — aucun recalcul ; [] sinon."""
    couverture = etude.get("couverture_pct_mois")
    if not isinstance(couverture, (list, tuple)) or len(couverture) != 12:
        couverture = [None] * 12
    mois = _dict(etude.get("controle_conception")).get("mois_sous_tolerance")
    return [{"mois": m, "couverture_pct": _num(couverture[m - 1])}
            for m in (_mois(v) for v in mois or []) if m is not None]


def texte_heures_eau(eau, langue, fmt):
    """AGQ3 (D-AGQ-2) — « sur 5,1 h de pompage équivalentes à plein débit en
    octobre, mois de conception · au plus bas : 73,2 m³/j en novembre » :
    LA phrase du héro (3 pages) et de la carte eau (une-page). ``fmt``
    formate un nombre à la française (gabarit appelant). "" quand l'étude
    ne nomme aucun mois (devis v1 : l'appelant garde son texte d'hier)."""
    mois = _mois(eau.get("mois_conception"))
    if mois is None:
        return ""
    nom = libelle(f"agr_mois_{mois}", langue)
    heures = eau.get("heures_pompage")
    texte = (libelle("agr_heures_equivalentes_mois", langue).format(
        heures=fmt(heures), mois=nom) if heures is not None else
        libelle("agr_hero_mois_conception", langue).format(mois=nom))
    bas, mois_bas = eau.get("m3_jour_min"), _mois(eau.get("mois_m3_jour_min"))
    if bas is not None and mois_bas not in (None, mois):
        texte += " · " + libelle("agr_au_plus_bas", langue).format(
            m3=fmt(bas), mois=libelle(f"agr_mois_{mois_bas}", langue))
    return texte


# AGQ38 (C-AGQ-032) — liste BLANCHE des alertes du noyau dites au client :
# code → clé i18n (le rendement non publié se dit selon la fiche en cause).
# Toute alerte hors de cette liste reste INTERNE, jamais servie.
CODES_NOTES_CLIENT = {
    "ratio_champ_pompe": "agr_note_ratio_champ_pompe",
    "variateur_suivant": "agr_note_variateur_suivant",
    "site_inconnu": "agr_note_site_inconnu",
    "pvgis_indisponible": "agr_note_irradiation_repli",
    "plafond_forage": "agr_note_plafond_forage",
}
# AGC1 (rien d'incertain imprimé, ci-decisions-2610) — « rendement non publié
# … borne haute / rendement prudent » reste une alerte VENDEUR : le client lit
# seulement « estimation » sous le m³/jour (AMOT65, étiquettes du noyau). Les
# clés i18n restent au catalogue (anciens rendus, liste figée des libellés).
_NOTES_RENDEMENT = {}


def _fr_nombre(v, dec=2):
    """« 1,51 » — nombre à la française, sans zéro inutile (forme du noyau)."""
    n = _num(v)
    if n is None:
        return "?"
    return f"{n:.{dec}f}".rstrip("0").rstrip(".").replace(".", ",")


def _cle_note(alerte):
    code = alerte.get("code")
    if code == "rendement_non_publie":
        return _NOTES_RENDEMENT.get(alerte.get("champ"))
    return CODES_NOTES_CLIENT.get(code)


def _valeurs_note(code, etude, items, alertes):
    """Les valeurs du gabarit, LUES (champ servi, table du noyau, lignes)."""
    if code == "ratio_champ_pompe":
        bande = hypothese_valeur("ratio_champ_pompe_bande_alerte")
        return {"ratio": _fr_nombre(_dict(etude.get("champ")).get("ratio")),
                "min": _fr_nombre(bande.min), "max": _fr_nombre(bande.max)}
    if code == "variateur_suivant":
        lignes = [it for it in items
                  if str(it.get("role_pompage") or "").startswith("variateur")]
        nom = ((lignes[0].get("designation") if lignes else None)
               or _dict(etude.get("variateur")).get("nom") or "")
        return {"nom": nom,
                "n": sum(1 for a in alertes if a.get("code") == code)}
    if code == "plafond_forage":
        return {"plafond": _fr_nombre(
            _dict(etude.get("production")).get("plafond_forage_m3h"), 1)}
    return {}


def _bloc_notes(etude, items):
    """AGQ38 — ``[{code, textes{fr,en,ar}}]`` : les alertes de la liste
    blanche, dites au client en trois langues, une note par (code, fiche) ;
    ``[]`` sans alerte. Aucun recalcul : valeurs lues telles que servies."""
    alertes = [a for a in (etude.get("alertes_pompage") or [])
               if isinstance(a, dict)]
    vues, notes = set(), []
    for alerte in alertes:
        cle = _cle_note(alerte)
        if cle is None or cle in vues:
            continue
        vues.add(cle)
        valeurs = _valeurs_note(alerte.get("code"), etude, items, alertes)
        notes.append({"code": alerte.get("code"), "textes": {
            lg: libelle(cle, lg).format(**valeurs)
            for lg in ("fr", "en", "ar")}})
    return notes


def _bloc_besoin_vs_livre(etude):
    """(bloc, motif) — bloc None quand il est omis, motif dit pourquoi."""
    besoin_mensuel = etude.get("besoin_mensuel")
    besoin_saisi = _dict(etude.get("besoin"))
    nature = (_dict(besoin_mensuel).get("nature")
              or besoin_saisi.get("nature"))
    if nature == "agronomique_plein":
        # AMOT63 — saisie du devis d'abord, sinon la valeur RÉSOLUE par le
        # moteur (lead) qu'il a réellement utilisée.
        cultures = _resolue(etude, besoin_saisi.get("cultures"),
                            "cultures") or []
        region = _resolue(etude, besoin_saisi.get("region"), "region")
        cultures_connues = bool(cultures) and isinstance(cultures, list) \
            and all(isinstance(c, dict) and c.get("crop") for c in cultures)
        if not cultures_connues or not region:
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
        # AGQ28 (D-AGQ-7) — une surface irrigable n'est une estimation
        # honnête que d'un besoin AGRONOMIQUE (FAO-56) ; besoin déclaré ⇒
        # aucune surface (le client a donné la sienne).
        "hectares_irrigables": _num(
            _dict(etude.get("ha_irrigables")).get("valeur"))
        if nature == "agronomique_plein" else None,
        "base_besoin": nature,
        "mois_sous_tolerance": _mois_sous_tolerance(etude),
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


def _resolue(etude, saisie, cle):
    """AMOT63 — la saisie du devis si elle existe (priorité corps > devis >
    lead), sinon la valeur RÉSOLUE persistée par le moteur
    (``etude_params['entrees_pompage']``, producteur
    ``domain.pompage.derivees_de_l_etude``)."""
    if saisie not in (None, "", [], {}):
        return saisie
    return _dict(etude.get("entrees_pompage")).get(cle)


def _bloc_schema(etude, eau):
    source = _dict(etude.get("source"))
    return {
        "profondeur_m": _num(_resolue(
            etude, source.get("profondeur_forage_m"), "profondeur_forage_m")),
        "niveau_m": _num(_resolue(
            etude, source.get("niveau_dynamique_m"), "niveau_dynamique_m")),
        "distance_m": _num(_resolue(
            etude, etude.get("distance_champ_m"), "distance_champ_m")),
        "hmt_m": eau.get("hmt_m"),
        # Bassin dessiné seulement s'il est DÉCLARÉ (aucun bassin dimensionné,
        # aucun « ×2 » — AGR301) : son volume déclaré, sinon None.
        "bassin": _num(_resolue(
            etude, source.get("volume_reservoir_m3"), "volume_reservoir_m3")),
    }


def _norme(texte):
    """Texte comparable : sans accents, sans parenthèse, minuscules."""
    texte = re.sub(r"\s*\(.*?\)", "", str(texte or ""))
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().replace("’", "'").split())


def _ligne_de_l_option(cle, libelle, proposees, prises):
    """L'index de la ligne optionnelle chiffrée (``options_proposees``) qui
    porte l'option ``cle`` du kit : par son ``role_pompage`` quand la ligne en
    porte un, sinon par sa désignation qui commence par le libellé du kit
    (« Compteur d'eau / débitmètre » ↔ « Compteur d'eau ») ; None sinon."""
    base = _norme(libelle)
    for i, o in enumerate(proposees):
        if i in prises:
            continue
        if o.get("role_pompage") == cle or (
                base and _norme(o.get("designation")).startswith(base)):
            return i
    return None


def _roles_des_lignes(items):
    return {it.get("role_pompage") for it in items or []
            if isinstance(it, dict) and it.get("role_pompage")}


def _bloc_options_kit(etude, items, options):
    """AGQ11 (D-AGR-8) — les options NOMMÉES du kit figé par le moteur
    (``etude['kit']['options']``, libellés de ``core.pompage.kit.OPTIONS``)
    fusionnées aux lignes optionnelles chiffrées (``options_proposees``,
    supplément canonique QJR616) : chaque option du kit est listée, avec son
    supplément quand une ligne le chiffre, sinon ``prix_connu`` faux (« prix
    sur devis » au rendu) — jamais omise. Une option déjà ligne du devis
    (comptée) n'est pas reproposée ; une ligne optionnelle sans option du
    kit reste listée telle quelle. Aucun prix recalculé."""
    proposees = [o for o in options or [] if isinstance(o, dict)]
    roles = _roles_des_lignes(items)
    sortie, prises = [], set()
    for opt in _dict(etude.get("kit")).get("options") or []:
        cle = opt.get("cle") if isinstance(opt, dict) else None
        if not cle or cle in roles:
            continue
        i = _ligne_de_l_option(cle, opt.get("libelle"), proposees, prises)
        ligne = proposees[i] if i is not None else {}
        if i is not None:
            prises.add(i)
        total = _num(ligne.get("total_ttc"))
        sortie.append({
            "cle": cle,
            "ligne_id": ligne.get("id"),
            "designation": ligne.get("designation") or opt.get("libelle"),
            "total_ttc": total,
            "prix_connu": total is not None,
            "mention": MENTION_COMPTEUR if cle == "compteur_eau" else None,
        })
    for i, o in enumerate(proposees):
        if i in prises:
            continue
        total = _num(o.get("total_ttc"))
        sortie.append({
            "cle": None,
            "ligne_id": o.get("id"),
            "designation": o.get("designation"),
            "total_ttc": total,
            "prix_connu": total is not None,
            "mention": None,
        })
    return sortie


def _non_inclus(etude, items):
    """AGQ11 — « non inclus » : forage et génie civil (D-AGR-8), puis les
    éléments du kit absents des lignes du devis — un élément du kit minimum
    resté SANS prix (omis du devis), et chaque option non retenue."""
    roles = _roles_des_lignes(items)
    kit = _dict(etude.get("kit"))
    sortie = list(NON_INCLUS)
    for ligne in kit.get("inclus") or []:
        if not isinstance(ligne, dict):
            continue
        role = ligne.get("role_pompage")
        if (role and role not in roles and not ligne.get("prix_connu")
                and ligne.get("cle") and ligne["cle"] not in sortie):
            sortie.append(ligne["cle"])
    for opt in kit.get("options") or []:
        cle = opt.get("cle") if isinstance(opt, dict) else None
        if cle and cle not in roles and cle not in sortie:
            sortie.append(cle)
    return sortie


def _mode_pompe(etude, items):
    mode = _resolue(etude, etude.get("mode_pompe"), "mode_pompe")
    if mode in ("neuve", "existante"):
        return mode
    # Sans saisie explicite, une ligne pompe dans le devis veut dire « pompe
    # neuve fournie » (D-AGR-7).
    if _item_pompe(items) is not None:
        return "neuve"
    # AGC9 (rendu réel R1, devis auto « pompe existante » 15 CV) — le mode
    # étudié est désormais persisté (``entrees_pompage.mode_pompe``, lu
    # plus haut). Une étude persistée AVANT lui ne porte que la plaque
    # résolue : sans ligne pompe et avec une plaque relevée, c'est la pompe
    # existante conservée (D-AGR-7) ; sinon on ne devine rien.
    if _dict(_resolue(etude, etude.get("plaque"), "plaque")):
        return "existante"
    return None


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


def debit_declare_sans_courbe(data):
    """AMOT56 (D-AMOT-7 = a) — le m³/jour du devis vient-il d'un débit
    DÉCLARÉ (pompe existante, AGR114) faute de pompe à courbe constructeur ?

    Vrai seulement quand AUCUNE ligne pompe ne porte de courbe et que la
    production de l'étude est en mode ``debit_declare`` (ou ``repli_plat``,
    dont le seul débit possible sans courbe est le débit déclaré —
    ``core.pompage.volumes.production_mensuelle``). Les gabarits étiquettent
    alors le m³/jour « débit déclaré par vous » ; la règle nocturne
    ``DOC_POMPAGE_M3_SANS_COURBE`` lit la MÊME fonction. Pure."""
    data = data if isinstance(data, dict) else {}
    pompe = _item_pompe(data.get("all_items") or [])
    if _courbe_points((pompe or {}).get("courbe_pompe")) is not None:
        return False
    mode = _dict(_dict(data.get("etude")).get("production")).get("mode")
    return mode in ("debit_declare", "repli_plat")


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
        # AGQ3 — le mois du héro (mois de conception servi) et le plus bas.
        "mois_conception": _mois(
            _dict(etude.get("conception")).get("mois_critique")),
    }
    eau["m3_jour_min"], eau["mois_m3_jour_min"] = _au_plus_bas(etude)
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
    controle = _controle_forage(eau, etude)
    if controle is not None:
        synthese["controle_forage"] = controle
    synthese["a_confirmer_par_visite"] = _a_confirmer_par_visite(
        etude, provenance)

    pompe = {"cv": _num(etude.get("pompe_cv")),
             "kw": _num(etude.get("pompe_kw"))}
    if mode == "existante":
        plaque = _dict(_resolue(etude, etude.get("plaque"), "plaque"))
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
    # D-AGQ-13 — le SAV : délai d'intervention saisi par la société (jamais
    # un délai inventé : non saisi ⇒ bloc omis avec son motif).
    delai_sav = _num(data.get("delai_intervention_sav_heures"))
    if delai_sav and delai_sav > 0:
        synthese["sav"] = {"delai_intervention_heures": int(delai_sav)}
    else:
        omissions.append({"bloc": "sav", "motif": MOTIF_SAV_NON_SAISI})

    synthese["schema"] = _bloc_schema(etude, eau)
    # AGR309 — UN seul dessin pour le PDF et la page : le SVG du schéma,
    # tracé sur les seules valeurs saisies, servi tel quel.
    synthese["schema_svg"] = schema_svg(
        synthese, langue=data.get("langue_sortie") or "fr")
    # AGQ13 — en arabe, les textes du schéma en légendes HTML positionnées
    # (le PDF ne façonne pas l'arabe d'un ``<text>`` SVG) ; [] sinon.
    legendes = []
    if est_rtl(data.get("langue_sortie")):
        schema_svg(synthese, langue=data.get("langue_sortie"),
                   legendes=legendes)
    synthese["schema_legendes"] = legendes
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
    synthese["options_kit"] = _bloc_options_kit(
        etude, items, data.get("options_proposees"))
    synthese["non_inclus"] = _non_inclus(etude, items)
    # AGR306 — les formalités du client (82-21 hors réseau, 36-15 eau).
    synthese["formalites"] = formalites()
    # AGQ30 — les étapes suivantes, sans délai chiffré (D-AGR-10).
    synthese["etapes_suivantes"] = etapes_suivantes()
    # AGQ38 — les alertes client du noyau, dites au client (page 2 + page web).
    synthese["notes"] = _bloc_notes(etude, items)

    omissions.extend(dict(o) for o in OMISSIONS_DE_PRINCIPE)
    synthese["omissions"] = omissions
    return synthese
