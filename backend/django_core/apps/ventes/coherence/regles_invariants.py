"""AMOT49 (C-AMOT-038) — règles nocturnes des INVARIANTS MAISON du moteur de
devis, et le tableau de gouvernance ``INVARIANTS_MAISON → règle``.

Deux invariants que le dépôt martèle (CLAUDE.md) n'avaient AUCUNE règle de
nuit : le registre comptait 22 règles, aucune ne visait la marge ni le
pompage. Ils sont gardés ici, sur la donnée RÉELLE (``ctx.donnees_devis``,
le dict que le moteur imprime) :

* ``DOC_RENDU_SANS_MARGE`` — ``Produit.prix_achat`` ne doit JAMAIS atteindre
  un PDF ni une sortie client : aucune clé ``prix_achat`` / ``marge*`` /
  ``cout_achat`` dans le dict de rendu, et aucune valeur numérique égale au
  ``prix_achat`` d'une ligne du devis à une clé qui n'est pas un prix de
  VENTE ;
* ``DOC_POMPAGE_SANS_ONDULEUR_BATTERIE`` — une composition de pompage
  (``mode_installation = 'agricole'``) ne contient NI onduleur NI batterie ;
* ``DOC_POMPAGE_M3_SANS_COURBE`` (AMOT56, D-AMOT-7 = a) — un m³/jour imprimé
  exige une pompe à courbe constructeur OU un débit déclaré étiqueté.

Lecture pure : aucune écriture, aucun changement de statut (règle #4).
"""
from __future__ import annotations

from .registre import GRAVITE_CRITIQUE, PORTEE_DEVIS, regle

#: Clés INTERDITES dans le dict de rendu (préfixes compris pour ``marge``).
CLES_INTERDITES = ("prix_achat", "cout_achat")
PREFIXES_INTERDITS = ("marge",)

#: Clés de PRIX DE VENTE légitimes : une égalité de valeur avec un prix
#: d'achat y est un hasard de catalogue, jamais une fuite.
_CLES_PRIX_VENTE = {
    "prix_unit_ht", "prix_unit_ttc", "pu_ht_remise", "total_ht_remise",
    "total_ht", "total_ttc", "ttc", "ht_brut", "ht_net", "tva", "remise",
}


def _cles_interdites(objet, chemin=""):
    """Chemins des clés interdites trouvées dans ``objet`` (récursif)."""
    trouves = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            c = str(cle).lower()
            ici = f"{chemin}.{cle}" if chemin else str(cle)
            if c in CLES_INTERDITES or c.startswith(PREFIXES_INTERDITS):
                trouves.append(ici)
            trouves.extend(_cles_interdites(valeur, ici))
    elif isinstance(objet, (list, tuple)):
        for i, valeur in enumerate(objet):
            trouves.extend(_cles_interdites(valeur, f"{chemin}[{i}]"))
    return trouves


def _valeurs_egales(objet, cibles, chemin=""):
    """Chemins dont la valeur numérique égale un ``prix_achat`` de ligne, hors
    clés de prix de vente."""
    trouves = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            ici = f"{chemin}.{cle}" if chemin else str(cle)
            if (isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
                    and str(cle) not in _CLES_PRIX_VENTE
                    and float(valeur) in cibles):
                trouves.append(ici)
            else:
                trouves.extend(_valeurs_egales(valeur, cibles, ici))
    elif isinstance(objet, (list, tuple)):
        for i, valeur in enumerate(objet):
            trouves.extend(_valeurs_egales(valeur, cibles, f"{chemin}[{i}]"))
    return trouves


def _prix_achat_des_lignes(devis):
    cibles = set()
    for ligne in devis.lignes.all():
        produit = getattr(ligne, "produit", None)
        pa = getattr(produit, "prix_achat", None)
        try:
            v = float(pa)
        except (TypeError, ValueError):
            continue
        # Un prix d'achat nul/unitaire de fixture n'identifie rien.
        if v > 1:
            cibles.add(round(v, 2))
    return cibles


@regle('DOC_RENDU_SANS_MARGE',
       "Le dict de rendu du devis porte un prix d'achat ou une marge",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def rendu_sans_marge(r, devis, ctx):
    """Invariant maison (CLAUDE.md) : ``Produit.prix_achat`` n'apparaît dans
    AUCUN PDF ni sortie client — le dict de ``build_quote_data`` (source de
    tous les rendus et de la charge utile publique) ne porte ni clé
    ``prix_achat`` / ``marge*`` / ``cout_achat``, ni valeur égale au prix
    d'achat d'une ligne hors prix de vente."""
    data = ctx.donnees_devis(devis)
    out = [r.violation(
        devis, f"Clé interdite « {chemin} » dans le rendu du devis.",
        valeurs={"cle": chemin}, cle={"cle": chemin})
        for chemin in _cles_interdites(data)]
    cibles = _prix_achat_des_lignes(devis)
    if cibles:
        # Les seules LIGNES imprimées : une égalité fortuite avec une grandeur
        # du document (kWh, kWc…) n'est pas une fuite.
        for cle in ("all_items", "sans_items", "avec_items",
                    "options_proposees"):
            out.extend(r.violation(
                devis, f"Valeur « {chemin} » égale à un prix d'achat de "
                       "ligne.",
                valeurs={"cle": chemin}, cle={"valeur": chemin})
                for chemin in _valeurs_egales(data.get(cle), cibles, cle))
    return out


@regle('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
       "Un devis de pompage contient un onduleur ou une batterie",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def pompage_sans_onduleur_batterie(r, devis, ctx):
    """Invariant maison (CLAUDE.md, « Pompage sizing ») : une composition de
    pompage ne contient NI onduleur NI batterie. Lu sur les lignes IMPRIMÉES
    (``all_items``) par les MÊMES mots-clés que le moteur
    (``utils.options._is_*`` via ``builder``)."""
    mode = (getattr(devis, "mode_installation", "") or "").strip().lower()
    if mode != "agricole":
        return []
    from apps.ventes import solar_classification as sc
    from apps.ventes.utils.options import texte_classement
    data = ctx.donnees_devis(devis)
    out = []
    for it in data.get("all_items") or []:
        if not isinstance(it, dict) or (it.get("quantite") or 0) <= 0:
            continue
        texte = texte_classement(it.get("designation", ""),
                                 it.get("_produit_nom", ""))
        if (sc.is_battery(texte) or sc.is_inverter(texte)
                or sc.is_hybrid_inverter(texte)
                or sc.is_offgrid_inverter(texte)):
            designation = it.get("designation") or ""
            out.append(r.violation(
                devis, f"Ligne « {designation} » : onduleur ou batterie dans "
                       "un devis de pompage.",
                valeurs={"designation": designation},
                cle={"designation": designation}))
    return out


@regle('DOC_POMPAGE_M3_SANS_COURBE',
       "Un m³/jour imprimé pour une pompe sans courbe ni débit déclaré",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def pompage_m3_sans_courbe(r, devis, ctx):
    """Invariant maison (CLAUDE.md « Pompage sizing », amendé par D-AMOT-7 =
    a) : le m³/jour que le document IMPRIME (``synthese_agricole`` — la
    source du une-page, du document 3 pages et de /proposition) n'existe
    que pour une pompe à courbe constructeur, OU sur le débit DÉCLARÉ d'une
    pompe existante, que les gabarits étiquettent « débit déclaré par vous »
    (``synthese.debit_declare_sans_courbe``, la MÊME fonction)."""
    mode = (getattr(devis, "mode_installation", "") or "").strip().lower()
    if mode != "agricole":
        return []
    from apps.ventes.quote_engine.agricole import synthese as S
    data = ctx.donnees_devis(devis)
    m3 = ((S.synthese_agricole(data).get("eau") or {}).get("m3_jour"))
    if m3 is None:
        return []
    pompe = S._item_pompe(data.get("all_items") or [])
    if S._courbe_points((pompe or {}).get("courbe_pompe")) is not None:
        return []
    if S.debit_declare_sans_courbe(data):
        return []
    return [r.violation(
        devis, f"m³/jour imprimé ({m3}) pour une pompe sans courbe "
               "constructeur ni débit déclaré.",
        valeurs={"m3_jour": m3}, cle={"m3_jour": "sans_courbe"})]


#: Le tableau de GOUVERNANCE : chaque invariant maison → la règle qui le
#: garde, ou la RAISON écrite de son absence. Un invariant listé sans l'un
#: ni l'autre fait échouer ``test_coherence_amot49_invariants_maison``.
INVARIANTS_MAISON = {
    "prix_achat jamais client-facing": "DOC_RENDU_SANS_MARGE",
    "pompage sans onduleur ni batterie": "DOC_POMPAGE_SANS_ONDULEUR_BATTERIE",
    "total imprimé = noyau": "DOC_TOTAL_IMPRIME_NE_NOYAU",
    "chaîne des totaux imprimés au centime": "DOC_TOTAUX_IMPRIMES",
    "m³/jour jamais imprimé pour une pompe sans courbe":
        "DOC_POMPAGE_M3_SANS_COURBE",
}
