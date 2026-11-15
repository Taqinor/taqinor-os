# flake8: noqa  (sonde HÔTE de contre-visite « vérifie ACNC » — sans Django, sans base, sans Docker)
"""C-ACNC-VER4-400 — après ACNC73, la seule barrière contre un second règlement fournisseur identique est l'ÉCRAN.

ACNC73 relit la fiche facture fournisseur après une réponse perdue (`FacturesFournisseur.jsx::FactureDetail`, branche
`!err?.response` d'`ajouter`). Le serveur, lui, n'a toujours AUCUN contrôle du « paiement identique » que D-ACNC-1 impose côté
client (`apps/ventes/domain/encaissements.py::encaisser_sur_facture` : même montant + même date ⇒ 409 `paiement_similaire`
sans `confirmer_doublon`). Les deux portes de règlement fournisseur — `FactureFournisseurViewSet._ajouter_paiement`
(suffixe d'idempotence `paiements.<pk>`) et `PaiementFournisseurViewSet.perform_create` (registre, autre espace de clés) — ne
refusent que l'excédent du solde dû (`verrouiller_facture_fournisseur_et_verifier_solde`). Un second règlement identique sous
une autre clé passe donc en silence quand l'écran n'a pas montré le premier :
  (a) délai de 20 s dépassé (toast « … réessayez ») alors que le POST est encore en vol : la relecture d'ACNC73 part
      aussitôt, non attendue, et lit la facture AVANT le commit (« Aucun paiement », solde 10 000) ;
  (b) relecture elle-même en échec (réseau toujours coupé) : la fiche garde sa copie périmée ;
  (c) deux onglets, ou la fiche ET le registre, pour la même facture.

Partie serveur : on rejoue, par le harnais de `C-ACNC-VER3-300.py` (VRAIS `IdempotentCreateMixin`, `_reserver`, `_liberer`,
`_fingerprint`, `verrouiller_facture_fournisseur_et_verifier_solde` extraits par ast ; seuls IdempotencyRecord et le solde sont
en mémoire), deux corps identiques sous deux clés. Partie statique : lecture des VRAIES portes fournisseur (aucun contrôle
`montant`/`date_paiement` sur les paiements existants) et de la vraie porte client (contrôle présent). Partie écran : la
relecture d'ACNC73 est un `.then(...)` non attendu ; `finally { setBusy(false) }` rend le bouton avant son retour.
Contrôle : même clé, même corps ⇒ rejeu, un règlement (ce que l'écran protège bien)."""
SONDE = {"constat": "C-ACNC-VER4-400", "sha": "d9164c12e2",
         "attendu": "deux règlements identiques de 3 000 sous deux clés sur une facture de 10 000 : 201 puis 201, aucun 409 "
                    "`paiement_similaire`, solde 4 000 ; côté client la même saisie rend 409"}
import ast, importlib.util, json, pathlib, re, sys
sys.dont_write_bytecode = True
ICI = pathlib.Path(__file__).resolve()
RACINE = ICI.parents[4]
VUE_FF = "backend/django_core/apps/stock/views/facture_fournisseur.py"
VUE_REG = "backend/django_core/apps/stock/views/paiement_fournisseur.py"
CLIENT = "backend/django_core/apps/ventes/domain/encaissements.py"
JSX = "frontend/src/pages/stock/FacturesFournisseur.jsx"
GARDE = re.compile(r"confirmer_doublon|paiement_similaire|paiements\.filter\(|PaiementFournisseur\.objects\.filter\(")


def _harnais():
    spec = importlib.util.spec_from_file_location("sonde_ver3_300", ICI.parent / "C-ACNC-VER3-300.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _source(chemin, classe, methode):
    arbre = ast.parse((RACINE / chemin).read_text(encoding="utf-8"))
    for n in ast.walk(arbre):
        if isinstance(n, ast.ClassDef) and n.name == classe:
            for f in n.body:
                if isinstance(f, ast.FunctionDef) and f.name == methode:
                    return ast.get_source_segment((RACINE / chemin).read_text(encoding="utf-8"), f)
    return None


def _fonction(chemin, nom):
    texte = (RACINE / chemin).read_text(encoding="utf-8")
    for n in ast.parse(texte).body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.get_source_segment(texte, n)
    return None


def _statique():
    portes = {"FactureFournisseurViewSet._ajouter_paiement": _source(VUE_FF, "FactureFournisseurViewSet", "_ajouter_paiement"),
              "PaiementFournisseurViewSet.create": _source(VUE_REG, "PaiementFournisseurViewSet", "create"),
              "PaiementFournisseurViewSet.perform_create": _source(VUE_REG, "PaiementFournisseurViewSet", "perform_create")}
    client = _fonction(CLIENT, "encaisser_sur_facture") or ""
    return {"portes_fournisseur_lues": {k: v is not None for k, v in portes.items()},
            "garde_identique_fournisseur": {k: bool(v and GARDE.search(v)) for k, v in portes.items()},
            "garde_identique_client_D_ACNC_1": bool(re.search(r"confirmer_doublon", client) and "paiement_similaire" in client)}


def _ecran():
    src = (RACINE / JSX).read_text(encoding="utf-8")
    debut = src.index("export function FactureDetail(")
    fiche = src[debut:src.index("\nexport ", debut + 10)]
    ajouter = re.search(r"const ajouter = async \(\) => \{(.*?)\n  \}\n", fiche, re.S).group(1)
    return {"relecture_presente": "getFactureFournisseur(facture.id)" in ajouter,
            "relecture_attendue_avant_de_rendre_le_bouton": bool(re.search(r"await\s+stockApi\.getFactureFournisseur", ajouter)),
            "bouton_rendu_en_finally": bool(re.search(r"finally\s*\{\s*setBusy\(false\)", ajouter)),
            "remise_de_cle_sur": (re.search(r"cleReglement\.current = null \}, \[([^\]]*)\]", fiche) or [None, None])[1]}


def sonde(ctx=None):
    h = _harnais()
    c_fiche = {"montant": 3000, "date_paiement": "2026-11-15", "mode": "virement"}
    deux_portes = h._jouer([("cle-fiche", c_fiche), ("cle-onglet-2", dict(c_fiche))])          # (c) deux onglets / fiche + registre
    c1 = {"montant": 3000, "date_paiement": None, "mode": "virement"}
    delai = h._jouer([("cle-K1", c1), ("cle-K2", c_fiche)])  # (a)/(b) relecture lue avant le commit ou en échec, date remplie
    controle = h._jouer([("cle-K1", c1), ("cle-K1", c1)])
    st, ec = _statique(), _ecran()
    aucune_garde = not any(st["garde_identique_fournisseur"].values()) and all(st["portes_fournisseur_lues"].values())
    repro = (aucune_garde and st["garde_identique_client_D_ACNC_1"]
             and deux_portes["codes"] == [201, 201] and len(deux_portes["reglements"]) == 2
             and len(delai["reglements"]) == 2)
    return {"repro": repro, "observe": {
        "methode": "rejeu serveur par le harnais de C-ACNC-VER3-300 (code réel extrait par ast) + lecture des vraies portes "
                   "fournisseur et client + lecture du vrai FactureDetail",
        "statique": st, "ecran": ec,
        "deux_portes_meme_corps": deux_portes, "relecture_avant_commit_puis_date_remplie": delai,
        "controle_meme_cle_meme_corps": controle}}


if __name__ == "__main__":
    import os
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str)); sys.stdout.flush()
    os._exit(0)
