"""AGR119 — kit pompage « minimum + options NOMMÉES » (D-AGR-8), composé par
le noyau pur ``core.pompage``.

Avant (``solar.js autoFillPompage``, l.3486-3541) : pompe, variateur,
afficheur, panneaux, structures, socles, câble à 20 m par DÉFAUT, installation
et transport — ni protections, ni câble de descente (profondeur inutilisée),
ni compteur, et rien ne disait ce qui était exclu.

Ici :

* D'OFFICE (``inclus``) : pompe (si neuve), variateur, panneaux, structure
  (+ socles comme aujourd'hui : 2 par panneau, ``solar.js``), installation,
  transport. Installation = ``INST-PMP`` (rôle ``installation_pompage``) si
  son barème ``prix_fixe_ht``/``prix_par_panneau_ht`` est saisi, sinon le
  produit de rôle ``installation`` du catalogue société (AGQ5 : trouvé par
  rôle, jamais par un SKU codé) avec l'alerte INTERNE « barème toiture
  appliqué à un pompage ». AGQ5 — un barème saisi vaut PRIX CONNU : la ligne
  est chiffrée par le barème à l'écriture (``domain/lignes.py``).
  Câble DC champ → variateur SEULEMENT si la distance est SAISIE (jamais 20 m
  par défaut, P6). D-ACAL-112 / D-ACAL-118 (fondateur 25/11/2026) : les
  protections — UN coffret de protection DC choisi pour le champ, un
  disjoncteur AC et un parafoudre AC entre le variateur et la pompe
  (:func:`choisir_protections`) — quittent les options pour le kit minimum.
* OPTIONS NOMMÉES trouvées par ``role_pompage`` (vocabulaire
  ``ROLES_POMPAGE`` de ``stock/contract_samples/produit_pompage.json``) :
  afficheur (cochée par défaut avec un variateur VEICHI — règle CLAUDE.md
  « one AFFICHEUR SI22 by default »), protections, sonde de niveau, compteur
  d'eau (non cochée, loi 36-15 / dossier FDA 2024), câble de descente
  (profondeur de calage + marge du réglage AGR107, sinon quantité à saisir),
  colonne, clapet, tuyauterie, bassin (volume saisi), entretien, antivol,
  clôture. Option sans produit pricé ⇒ « prix à renseigner », JAMAIS 0 MAD.
* ``non_inclus`` = forage, génie civil. Aucune batterie, aucun onduleur.

Toutes les entrées sont des dicts simples fournis par l'appelant ; un produit
peut porter ``prix_ttc`` (prix unitaire TTC calculé par l'appelant) pour le
``total_ttc`` du kit — aucune clé ``prix_achat`` ni marge n'est lue ni rendue.

Noyau PUR : stdlib seulement, aucune I/O.
"""
from __future__ import annotations

import math
import re
import unicodedata

from core.pompage.hydraulique import _flottant
from core.pompage.selection import prix_connu

NON_INCLUS = ("forage", "genie_civil")
SUFFIXE_PRIX = " — prix à renseigner"
MENTION_COMPTEUR = "exigé par la loi 36-15 et le dossier FDA 2024"

#: (clé, rôle ``role_pompage``, libellé) — ordre d'affichage des options.
#: D-ACAL-112 / D-ACAL-118 (fondateur 25/11/2026) : l'ancienne option
#: « Protections DC/AC » (``protection_dc``) n'est plus une option — les
#: protections entrent au kit minimum (:data:`PROTECTIONS`). Un devis déjà
#: créé garde ses lignes et son étude figée (libellé ``agr_option_protection_dc``
#: toujours servi au rendu).
OPTIONS = (
    ("afficheur_variateur", "afficheur_variateur", "Afficheur du variateur"),
    ("sonde_niveau", "sonde_niveau", "Sonde de niveau (marche à sec)"),
    ("compteur_eau", "compteur_eau", "Compteur d'eau"),
    ("cable_descente", "cable_descente", "Câble de descente"),
    ("colonne_refoulement", "colonne_refoulement", "Colonne de refoulement"),
    ("clapet", "clapet", "Clapet anti-retour"),
    ("tuyauterie", "tuyauterie", "Tuyauterie"),
    ("bassin", "bassin", "Bassin"),
    ("entretien_pompage", "entretien_pompage", "Contrat d'entretien"),
    ("antivol", "antivol", "Fixations antivol"),
    ("cloture", "cloture", "Clôture du champ"),
)

#: D-ACAL-112 / D-ACAL-118 (fondateur 25/11/2026, « DC box + AC protection »)
#: — les protections du kit MINIMUM des nouveaux devis : UN coffret de
#: protection DC choisi pour le champ, un disjoncteur AC et un parafoudre AC
#: entre le variateur et la pompe. (clé, rôle ``role_pompage``, libellé).
PROTECTIONS = (
    ("coffret_dc", "protection_dc", "Coffret de protection DC"),
    ("disjoncteur_ac", "protection_ac", "Disjoncteur AC variateur → pompe"),
    ("parafoudre_ac", "protection_ac", "Parafoudre AC variateur → pompe"),
)


def _alerte(code, champ, message, interne=False):
    alerte = {"code": code, "champ": champ, "message": message}
    if interne:
        alerte["interne"] = True
    return alerte


#: Le droit qui permet de saisir un prix ou un barème au catalogue (libellé du
#: registre ``catalogue_prix_modifier``).
DROIT_PRIX_CATALOGUE = "Modifier les prix du catalogue"


def message_pose_au_tarif_toiture(installation_pompage):
    """T4-V2-004 — la phrase vendeur quand la pose du pompage est chiffrée au
    tarif toiture : ce qui se passe, où saisir le tarif, qui peut le faire."""
    nom = (installation_pompage or {}).get("nom")
    if nom:
        return ("Le tarif de pose du pompage n'est pas saisi : la pose est "
                "chiffrée au tarif toiture. À saisir dans Stock, article « %s » "
                "(droit « %s »)." % (nom, DROIT_PRIX_CATALOGUE))
    return ("Aucun article de pose du pompage au catalogue : la pose est "
            "chiffrée au tarif toiture. À créer dans Stock (droit « %s »)."
            % DROIT_PRIX_CATALOGUE)


def _fr(nombre):
    texte = "%.1f" % nombre
    texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _ligne(cle, role, produit, designation_defaut, quantite):
    """Une ligne ``inclus`` : produit pricé, produit sans prix (« prix à
    renseigner ») ou placeholder sans produit."""
    if produit is None:
        return {"cle": cle, "role_pompage": role, "produit": None,
                "designation": designation_defaut + SUFFIXE_PRIX,
                "quantite": quantite, "prix_connu": False}
    # AGQ5 (C-AGQ-004) — un barème saisi (prix fixe / par panneau) est un
    # prix connu : l'écrivain de lignes chiffre la ligne par ce barème.
    connu = prix_connu(produit) or bareme_saisi(produit)
    nom = produit.get("nom") or designation_defaut
    return {"cle": cle, "role_pompage": role, "produit": produit.get("id"),
            "designation": nom if connu else nom + SUFFIXE_PRIX,
            "quantite": quantite, "prix_connu": connu}


def _par_role(produits, role):
    """Le premier produit PRICÉ de ce rôle, sinon le premier sans prix."""
    candidats = [p for p in produits or () if p.get("role_pompage") == role]
    pricees = [p for p in candidats if prix_connu(p)]
    if pricees:
        return pricees[0]
    return candidats[0] if candidats else None


def bareme_saisi(produit):
    """Le barème ``prix_fixe_ht`` / ``prix_par_panneau_ht`` est-il saisi ?"""
    if not produit:
        return False
    return any((_flottant(produit.get(c), 0.0) or 0.0) > 0
               for c in ("prix_fixe_ht", "prix_par_panneau_ht"))


def _norme(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "").lower())
    return "".join(c for c in texte if not unicodedata.combining(c))


def _premier_price(candidats):
    """Le premier PRICÉ, sinon le premier (règle de :func:`_par_role`)."""
    pricees = [p for p in candidats if prix_connu(p)]
    return (pricees or list(candidats) or [None])[0]


def _phase_article(produit):
    """``mono`` / ``tri`` lu sur l'article (alimentation servie, sinon le nom :
    « monophasé », « triphasé » / « tétrapolaire ») ; ``None`` = non publié."""
    alim = (produit or {}).get("alimentation")
    if alim in ("mono", "tri"):
        return alim
    nom = _norme((produit or {}).get("nom"))
    if "monophas" in nom:
        return "mono"
    if "triphas" in nom or "tetrapolaire" in nom:
        return "tri"
    return None


def _nombre_du_nom(produit, motif):
    trouve = re.search(motif, _norme((produit or {}).get("nom")))
    return float(trouve.group(1).replace(",", ".")) if trouve else None


def _de_la_phase(candidats, phase):
    """Les articles de la phase voulue ; à défaut, ceux qui n'en publient
    aucune (jamais un article de l'autre phase)."""
    exacts = [p for p in candidats if phase and _phase_article(p) == phase]
    return exacts or [p for p in candidats if _phase_article(p) is None]


def _plus_petit_suffisant(candidats, taille, besoin):
    """Le plus petit article dont la ``taille`` publiée couvre ``besoin``
    (même règle que le variateur : plus petit kW ≥ pompe), le premier pricé à
    taille égale ; ``None`` si aucun ne suffit."""
    suffisants = [(taille(p), p) for p in candidats
                  if taille(p) is not None and taille(p) + 1e-9 >= besoin]
    if not suffisants:
        return None
    mini = min(t for t, _p in suffisants)
    return _premier_price([p for t, p in suffisants if t == mini])


def courant_deduit_pompe(pompe_kw, tension_v, alimentation):
    """D-ACAL-124 (fondateur 25/11/2026, « Derive from kW and voltage ») —
    ``(courant_a | None, motif | None)`` : le courant de la pompe DÉDUIT de son
    kW (``pompe_kw``) et de sa tension (``tension_v``), relation électrique
    seule : I = P / U en monophasé, I = P / (√3 · U) en triphasé (même relation
    que ``core.electrique.protections.courant_emploi_ac``, à la tension de la
    pompe). AUCUN facteur de puissance ni rendement du moteur n'est supposé (le
    dépôt n'en publie aucun) : la valeur SOUS-ESTIME le courant réel d'un
    moteur. ``motif`` nomme le champ manquant."""
    kw, tension = _flottant(pompe_kw), _flottant(tension_v)
    if not kw or kw <= 0:
        return None, ("calibre du disjoncteur AC à choisir : ni courant "
                      "nominal ni kW de la pompe (pompe_kw) sur sa fiche")
    if not tension or tension <= 0:
        return None, ("calibre du disjoncteur AC à choisir : ni courant "
                      "nominal ni tension de la pompe (tension_v) sur sa fiche")
    if alimentation not in ("mono", "tri"):
        return None, ("calibre du disjoncteur AC à choisir : ni courant "
                      "nominal ni phase (mono / tri) connus pour la pompe")
    diviseur = tension * (math.sqrt(3.0) if alimentation == "tri" else 1.0)
    return kw * 1000.0 / diviseur, None


def phrase_calibre_deduit(pompe_kw, tension_v, courant):
    """D-ACAL-124 — l'hypothèse DITE (écran, hypothèses internes ; jamais au
    PDF client) et le champ qui la lève."""
    return ("Calibre du disjoncteur AC déduit des %s kW et %s V de la pompe "
            "(courant estimé %s A, sans facteur de puissance ni rendement du "
            "moteur : sous-estimé) ; saisir le courant nominal de la pompe sur "
            "sa fiche du catalogue le remplace."
            % (_fr(_flottant(pompe_kw)), _fr(_flottant(tension_v)),
               _fr(courant)))


def choisir_protections(produits, *, nb_chaines=None, alimentation=None,
                        courant_pompe_a=None, pompe_kw=None, tension_v=None):
    """D-ACAL-118 — ``{cle: (produit | None, motif | None)}`` des trois
    protections du kit, choisies sur les données publiées SEULEMENT :

    * coffret DC (rôle ``protection_dc``, « coffret » au nom) : le plus petit
      dont le nombre de chaînes publié au nom (« 2 strings ») couvre les
      chaînes en parallèle du champ ; sans coffret à capacité publiée qui
      suffise, un coffret qui n'en publie aucune ;
    * disjoncteur AC (rôle ``protection_ac``) : de la phase de la pompe ; un
      seul calibre au catalogue = celui-là (s'il couvre le courant) ;
      plusieurs = le plus petit calibre ≥ courant de la pompe (Ib ≤ In) —
      courant PUBLIÉ, sinon déduit de son kW et de sa tension (D-ACAL-124,
      :func:`courant_deduit_pompe`, hypothèse dite) ;
    * parafoudre AC (rôle ``protection_ac``) : de la phase, sinon générique.

    ``motif`` dit pourquoi aucun article n'est retenu (jamais une valeur
    supposée)."""
    produits = list(produits or ())
    choix = {}

    coffrets = [p for p in produits if p.get("role_pompage") == "protection_dc"
                and "coffret" in _norme(p.get("nom"))]
    besoin = max(int(_flottant(nb_chaines, 1) or 1), 1)
    capacite = lambda p: _nombre_du_nom(  # noqa: E731
        p, r"(\d+)\s*(?:strings?|chaines?|entrees?)\b")
    coffret = _plus_petit_suffisant(coffrets, capacite, besoin)
    if coffret is None:
        coffret = _premier_price([p for p in coffrets if capacite(p) is None])
    choix["coffret_dc"] = (coffret, None if coffret is not None else (
        "aucun coffret DC du catalogue n'accepte %d chaîne%s en parallèle"
        % (besoin, "s" if besoin > 1 else "") if coffrets else None))

    ac = [p for p in produits if p.get("role_pompage") == "protection_ac"]
    disjoncteurs = _de_la_phase(
        [p for p in ac if "disjoncteur" in _norme(p.get("nom"))
         and "parafoudre" not in _norme(p.get("nom"))], alimentation)
    calibre = lambda p: _nombre_du_nom(p, r"(\d+(?:[.,]\d+)?)\s*a\b")  # noqa: E731
    calibres = {calibre(p) for p in disjoncteurs}
    courant = _flottant(courant_pompe_a)
    motif = None
    # D-ACAL-124 — le courant PUBLIÉ gagne ; sinon déduit du kW et de la
    # tension de la pompe (hypothèse dite), sinon le champ manquant est nommé.
    motif_deduit = None
    if (courant is None or courant <= 0) and disjoncteurs:
        courant, motif_deduit = courant_deduit_pompe(
            pompe_kw, tension_v, alimentation)
        if courant is not None:
            choix["_hypothese_disjoncteur"] = phrase_calibre_deduit(
                pompe_kw, tension_v, courant)
    if not disjoncteurs:
        disjoncteur = None
    elif len(calibres) == 1 and (courant is None or None in calibres
                                 or calibres.pop() + 1e-9 >= courant):
        disjoncteur = _premier_price(disjoncteurs)
    elif courant is not None and courant > 0:
        disjoncteur = _plus_petit_suffisant(disjoncteurs, calibre, courant)
        if disjoncteur is None:
            motif = ("aucun disjoncteur AC du catalogue n'atteint le courant "
                     "%s de la pompe (%s A)" % (
                         "estimé" if choix.get("_hypothese_disjoncteur")
                         else "nominal", _fr(courant)))
    else:
        disjoncteur = None
        motif = motif_deduit
    choix["disjoncteur_ac"] = (disjoncteur, motif)

    parafoudres = _de_la_phase(
        [p for p in ac if "parafoudre" in _norme(p.get("nom"))], alimentation)
    choix["parafoudre_ac"] = (_premier_price(parafoudres), None)
    return choix


def _quantites_options(*, profondeur_calage_m, marge_cable_m,
                       longueur_conduite_m, volume_bassin_m3):
    """{clé: (quantité, motif)} — quantité ``None`` = à saisir, jamais une
    valeur supposée."""
    calage = _flottant(profondeur_calage_m)
    marge = _flottant(marge_cable_m)
    if calage is not None and calage > 0 and marge is not None and marge >= 0:
        descente = (round(calage + marge, 1), None)
    elif calage is None or calage <= 0:
        descente = (None, "profondeur de calage inconnue : quantité à saisir")
    else:
        descente = (None, "marge de câble non réglée : quantité à saisir")
    conduite = _flottant(longueur_conduite_m)
    tuyauterie = ((round(conduite, 1), None) if conduite and conduite > 0
                  else (None, "longueur de conduite inconnue : quantité à "
                        "saisir"))
    volume = _flottant(volume_bassin_m3)
    bassin = ((1, None) if volume and volume > 0
              else (None, "volume du bassin à saisir"))
    a_saisir = (None, "quantité à saisir")
    return {
        "afficheur_variateur": (1, None),
        "sonde_niveau": (1, None), "compteur_eau": (1, None),
        "cable_descente": descente, "colonne_refoulement": a_saisir,
        "clapet": (1, None), "tuyauterie": tuyauterie, "bassin": bassin,
        "entretien_pompage": (1, None), "antivol": a_saisir,
        "cloture": a_saisir,
    }


def composer_kit(*, mode_pompe, pompe=None, variateur=None, panneau=None,
                 nb_panneaux=None, structure=None, socle=None,
                 installation_pompage=None, installation_toiture=None,
                 transport=None, produits_options=(), distance_champ_m=None,
                 profondeur_calage_m=None, marge_cable_m=None,
                 longueur_conduite_m=None, volume_bassin_m3=None,
                 options_cochees=None, nb_chaines=None, alimentation=None,
                 courant_pompe_a=None, pompe_kw=None, tension_pompe_v=None):
    """AGR119 — ``{inclus, options, non_inclus, lignes, total_ttc, alertes}``.

    * ``pompe`` : forme ``pompe`` du contrat (sortie AGR117) — ignorée en
      mode ``existante`` (aucune ligne pompe) ;
    * ``variateur``, ``panneau``, ``structure``, ``socle``, ``transport`` :
      dicts produit ; ``installation_pompage`` = INST-PMP (avec son barème),
      ``installation_toiture`` = l'installation de rôle ``installation``
      du catalogue (repli trouvé par rôle, AGQ5) ;
    * ``produits_options`` : éléments ``produits_pompage`` (tous rôles) ;
    * ``options_cochees`` : liste de clés cochées, ``None`` = défauts ;
    * ``nb_chaines`` (chaînes en parallèle du champ), ``alimentation``
      (``mono``/``tri``) et ``courant_pompe_a`` (courant nominal publié de la
      pompe) choisissent les protections (:func:`choisir_protections`) ;
      sans courant publié, ``pompe_kw`` et ``tension_pompe_v`` le déduisent
      (D-ACAL-124).

    D-ACAL-112 / D-ACAL-118 — ``inclus`` porte les trois protections
    (:data:`PROTECTIONS`) : coffret DC dès que le champ est dimensionné,
    disjoncteur et parafoudre AC dès qu'un variateur est retenu. Sans article
    retenu, la ligne reste « — prix à renseigner » sans produit, avec son
    ``motif`` quand il y en a un.

    ``lignes`` = inclus + options cochées, prêtes pour une composition de
    devis (désignation suffixée « — prix à renseigner » quand aucun prix
    n'est saisi). ``total_ttc`` = Σ quantité × ``prix_ttc`` quand CHAQUE
    ligne en porte un, sinon ``None``.
    """
    alertes = []
    inclus = []
    prix_par_ligne = []

    def ajouter(ligne, produit):
        inclus.append(ligne)
        prix_par_ligne.append((ligne, produit))

    pompe_placeholder = bool(pompe and pompe.get("placeholder"))
    if mode_pompe == "neuve" and pompe:
        produit_pompe = None
        if not pompe_placeholder and pompe.get("produit") is not None:
            produit_pompe = {"id": pompe.get("produit"),
                             "nom": pompe.get("nom"),
                             "prix_connu": pompe.get("prix_connu"),
                             "prix_ttc": pompe.get("prix_ttc")}
        ligne = (_ligne("pompe", "pompe", produit_pompe, "Pompe", 1)
                 if produit_pompe else
                 {"cle": "pompe", "role_pompage": "pompe", "produit": None,
                  "designation": pompe.get("nom"), "quantite": 1,
                  "prix_connu": False})
        ajouter(ligne, produit_pompe)

    if not pompe_placeholder:
        if variateur is not None:
            ajouter(_ligne("variateur", "variateur_pompage", variateur,
                           "Variateur", 1), variateur)
        nb = int(nb_panneaux) if nb_panneaux else None
        if nb:
            ajouter(_ligne("panneaux", "", panneau, "Panneaux", nb), panneau)
            ajouter(_ligne("structure", "structure_sol", structure,
                           "Structure au sol", nb), structure)
            if socle is not None:
                ajouter(_ligne("socles", "", socle, "Socles", nb * 2), socle)
        distance = _flottant(distance_champ_m)
        if distance is not None and distance > 0:
            cable_dc = _par_role(produits_options, "cable_dc")
            ajouter(_ligne("cable_dc", "cable_dc", cable_dc,
                           "Câble DC champ → variateur (m)",
                           round(distance, 1)), cable_dc)
        protections = choisir_protections(
            produits_options, nb_chaines=nb_chaines,
            alimentation=alimentation, courant_pompe_a=courant_pompe_a,
            pompe_kw=pompe_kw, tension_v=tension_pompe_v)
        for cle, role, libelle in PROTECTIONS:
            if (cle == "coffret_dc" and not nb) or (
                    cle != "coffret_dc" and variateur is None):
                continue
            produit, motif = protections[cle]
            ligne = _ligne(cle, role, produit, libelle, 1)
            if motif:
                ligne["motif"] = motif
            hypothese = protections.get("_hypothese_disjoncteur")
            if cle == "disjoncteur_ac" and hypothese:
                # D-ACAL-124 — l'hypothèse dite à l'écran (alerte INTERNE).
                ligne["hypothese"] = hypothese
                alertes.append(_alerte("calibre_disjoncteur_deduit",
                                       "kit.disjoncteur_ac", hypothese,
                                       interne=True))
            ajouter(ligne, produit)
        if bareme_saisi(installation_pompage):
            ajouter(_ligne("installation", "installation_pompage",
                           installation_pompage, "Installation pompage", 1),
                    installation_pompage)
        elif installation_toiture is not None:
            ajouter(_ligne("installation", "", installation_toiture,
                           "Installation", 1), installation_toiture)
            # T4-V2-004 — ni code article ni « alerte interne » : ce qui est
            # chiffré, où le saisir et qui peut le faire.
            alertes.append(_alerte(
                "bareme_installation_toiture", "kit.installation",
                message_pose_au_tarif_toiture(installation_pompage),
                interne=True))
        elif installation_pompage is not None:
            ajouter(_ligne("installation", "installation_pompage",
                           dict(installation_pompage, prix_connu=False),
                           "Installation pompage", 1), None)
        if transport is not None:
            ajouter(_ligne("transport", "", transport, "Transport", 1),
                    transport)

    options = []
    if not pompe_placeholder:
        quantites = _quantites_options(
            profondeur_calage_m=profondeur_calage_m,
            marge_cable_m=marge_cable_m,
            longueur_conduite_m=longueur_conduite_m,
            volume_bassin_m3=volume_bassin_m3)
        veichi = "veichi" in ((variateur or {}).get("nom") or "").lower()
        fiche_var = (variateur or {}).get("fiche") or {}
        for cle, role, libelle in OPTIONS:
            produit = _par_role(produits_options, role)
            quantite, motif = quantites[cle]
            mentions = []
            if produit is None:
                mentions.append("aucun produit au catalogue")
            elif not prix_connu(produit):
                mentions.append("prix à renseigner")
            if motif:
                mentions.append(motif)
            if cle == "compteur_eau":
                mentions.append("mention : " + MENTION_COMPTEUR)
            if cle == "sonde_niveau" and fiche_var.get(
                    "var_protection_marche_a_sec"):
                mentions.append("le variateur publie une protection marche à "
                                "sec intégrée")
            if cle == "bassin" and quantite:
                libelle = "%s (%s m³)" % (libelle, _fr(
                    _flottant(volume_bassin_m3)))
            if options_cochees is None:
                cochee = cle == "afficheur_variateur" and veichi
            else:
                cochee = cle in options_cochees
            options.append({
                "cle": cle, "libelle": libelle,
                "produit": produit.get("id") if produit else None,
                "prix_connu": prix_connu(produit), "cochee": cochee,
                "quantite": quantite,
                "motif": " — ".join(mentions) if mentions else None,
                "_produit": produit, "_role": role,
            })
        # ACAL808 — ni sonde cochée ni protection publiée : alerte INTERNE
        # (hors ``CODES_NOTES_CLIENT``), jamais une sonde cochée d'office.
        protection = fiche_var.get("var_protection_marche_a_sec")
        sonde = any(o["cle"] == "sonde_niveau" and o["cochee"] for o in options)
        if variateur is not None and not sonde and not protection:
            # T4-V2-010 — dire OÙ saisir l'information manquante.
            message = ("Ni sonde de niveau ni protection marche à sec du "
                       "variateur : la pompe tournerait à sec si le puits se "
                       "vide" if protection is False else
                       "Ni sonde de niveau cochée ni protection marche à sec "
                       "connue : la fiche du variateur « %s » ne dit pas s'il "
                       "protège la pompe de la marche à sec. À saisir dans "
                       "Stock, fiche du variateur (protection marche à sec), "
                       "ou cocher l'option « Sonde de niveau »."
                       % (variateur.get("nom") or "retenu"))
            alertes.append(_alerte("marche_a_sec_non_protegee",
                                   "kit.options.sonde_niveau", message))

    lignes = [dict(ligne) for ligne in inclus]
    for option in options:
        if not option["cochee"]:
            continue
        produit = option["_produit"]
        ligne = _ligne(option["cle"], option["_role"], produit,
                       option["libelle"], option["quantite"])
        lignes.append(ligne)
        prix_par_ligne.append((ligne, produit))
    for ligne in lignes:
        if not ligne["prix_connu"]:
            ligne["produit"] = None  # jamais enregistrée comme article gratuit

    total = 0.0
    for ligne, produit in prix_par_ligne:
        prix = _flottant((produit or {}).get("prix_ttc"))
        if (not ligne["prix_connu"] or prix is None or prix <= 0
                or not ligne["quantite"]):
            total = None
            break
        total += prix * ligne["quantite"]
    for option in options:
        option.pop("_produit")
        option.pop("_role")
    return {"inclus": inclus, "options": options,
            "non_inclus": list(NON_INCLUS), "lignes": lignes,
            "total_ttc": round(total, 2) if total is not None and inclus
            else None,
            "alertes": alertes}
