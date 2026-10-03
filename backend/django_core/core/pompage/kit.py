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
  son barème ``prix_fixe_ht``/``prix_par_panneau_ht`` est saisi, sinon
  ``INST-CAT`` avec l'alerte INTERNE « barème toiture appliqué à un pompage ».
  Câble DC champ → variateur SEULEMENT si la distance est SAISIE (jamais 20 m
  par défaut, P6).
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

from core.pompage.hydraulique import _flottant
from core.pompage.selection import prix_connu

NON_INCLUS = ("forage", "genie_civil")
SUFFIXE_PRIX = " — prix à renseigner"
MENTION_COMPTEUR = "exigé par la loi 36-15 et le dossier FDA 2024"

#: (clé, rôle ``role_pompage``, libellé) — ordre d'affichage des options.
OPTIONS = (
    ("afficheur_variateur", "afficheur_variateur", "Afficheur du variateur"),
    ("protection_dc", "protection_dc", "Protections DC/AC"),
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


def _alerte(code, champ, message, interne=False):
    alerte = {"code": code, "champ": champ, "message": message}
    if interne:
        alerte["interne"] = True
    return alerte


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
    connu = prix_connu(produit)
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
        "afficheur_variateur": (1, None), "protection_dc": (1, None),
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
                 options_cochees=None):
    """AGR119 — ``{inclus, options, non_inclus, lignes, total_ttc, alertes}``.

    * ``pompe`` : forme ``pompe`` du contrat (sortie AGR117) — ignorée en
      mode ``existante`` (aucune ligne pompe) ;
    * ``variateur``, ``panneau``, ``structure``, ``socle``, ``transport`` :
      dicts produit ; ``installation_pompage`` = INST-PMP (avec son barème),
      ``installation_toiture`` = INST-CAT ;
    * ``produits_options`` : éléments ``produits_pompage`` (tous rôles) ;
    * ``options_cochees`` : liste de clés cochées, ``None`` = défauts.

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
        if bareme_saisi(installation_pompage):
            ajouter(_ligne("installation", "installation_pompage",
                           installation_pompage, "Installation pompage", 1),
                    installation_pompage)
        elif installation_toiture is not None:
            ajouter(_ligne("installation", "", installation_toiture,
                           "Installation", 1), installation_toiture)
            alertes.append(_alerte(
                "bareme_installation_toiture", "kit.installation",
                "Barème toiture appliqué à un pompage — renseigner INST-PMP "
                "(alerte interne).", interne=True))
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
