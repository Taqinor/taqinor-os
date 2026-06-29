"""Services d'écriture / d'orchestration de la Gestion des contrats.

Point d'entrée ÉCRITURE de l'app `contrats` (pendant lecture de
``selectors.py``). Conformément à la frontière cross-app (CLAUDE.md), toute
orchestration interne au contrat passe ici ; aucun import direct des
``models``/``views`` d'une autre app de domaine n'est fait depuis ce module.

Contenu :

- CONTRAT10 — **Génération du contrat par fusion (merge tokens)** :
  ``contexte_fusion`` / ``rendre_contrat`` construisent le texte final d'un
  contrat en fusionnant des jetons ``{{ jeton }}`` dans un gabarit (le corps du
  ``ModeleContrat`` ou un corps fourni). La fusion est volontairement
  DÉPENDANCE-LÉGÈRE : un simple remplacement de jetons par expression
  régulière (``re``) de la bibliothèque standard — aucun moteur de gabarit
  tiers, aucune exécution de code, pas d'injection possible.

- CONTRAT12 — **Machine d'états du cycle de vie + transitions gardées** :
  ``TRANSITIONS_AUTORISEES`` décrit le graphe d'états du ``Contrat.statut`` et
  ``changer_statut`` applique une transition en la gardant (transition permise,
  parties suffisantes pour finaliser). Voir ``machine_etats.py`` — réexporté
  ici pour garder un point d'entrée unique côté services.
"""
import html as _html
import re

from .machine_etats import (  # noqa: F401 — réexport (point d'entrée services)
    TRANSITIONS_AUTORISEES,
    TransitionInterdite,
    changer_statut,
    statuts_suivants,
)

# ---------------------------------------------------------------------------
# CONTRAT10 — Génération par fusion (merge tokens)
# ---------------------------------------------------------------------------

# Un jeton de fusion : ``{{ nom_du_jeton }}`` (espaces optionnels autour du nom).
# Le nom est limité à [A-Za-z0-9_.] pour rester prévisible et inoffensif.
_JETON_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def _fmt_montant(montant, devise):
    """Formate un montant + devise de façon stable (ex. ``12 500.00 MAD``)."""
    try:
        valeur = f"{montant:,.2f}".replace(",", " ")
    except (TypeError, ValueError):  # pragma: no cover - défensif
        valeur = str(montant)
    return f"{valeur} {devise}".strip()


def _fmt_date(valeur):
    """Date au format ISO (``AAAA-MM-JJ``) ou chaîne vide si absente."""
    return valeur.isoformat() if valeur else ""


def contexte_fusion(contrat):
    """Construit le dictionnaire de jetons de fusion d'un ``Contrat``.

    Les clés sont les noms de jetons disponibles dans un gabarit ; les valeurs
    sont des chaînes prêtes à l'affichage. Lecture seule : ne modifie jamais le
    contrat. Inclut les champs du contrat, un résumé des parties et la liste
    ordonnée des clauses résolues.
    """
    parties = list(contrat.parties.all().order_by("ordre", "id"))
    client = next(
        (p for p in parties if p.type_partie == p.TypePartie.CLIENT), None
    )
    prestataire = next(
        (p for p in parties if p.type_partie == p.TypePartie.PRESTATAIRE), None
    )

    lignes_parties = [
        f"- {p.nom}"
        + (f" ({p.fonction})" if p.fonction else "")
        + f" — {p.get_type_partie_display()}"
        for p in parties
    ]

    clauses = list(contrat.clauses_resolues.all().order_by("ordre", "id"))
    blocs_clauses = [
        f"{i}. {c.titre}\n{c.corps}" for i, c in enumerate(clauses, start=1)
    ]

    return {
        "reference": contrat.reference or "",
        "objet": contrat.objet or "",
        "type_contrat": contrat.get_type_contrat_display(),
        "statut": contrat.get_statut_display(),
        "montant": _fmt_montant(contrat.montant, contrat.devise),
        "devise": contrat.devise or "",
        "date_debut": _fmt_date(contrat.date_debut),
        "date_fin": _fmt_date(contrat.date_fin),
        "confidentialite": contrat.get_confidentialite_display(),
        # Parties
        "client": client.nom if client else "",
        "prestataire": prestataire.nom if prestataire else "",
        "parties": "\n".join(lignes_parties),
        # Clauses résolues (CONTRAT9)
        "clauses": "\n\n".join(blocs_clauses),
    }


def fusionner(gabarit, contexte):
    """Remplace chaque jeton ``{{ x }}`` du ``gabarit`` par ``contexte['x']``.

    Un jeton inconnu (absent du contexte) est rendu par une chaîne vide — on ne
    laisse jamais un ``{{ ... }}`` brut dans le rendu et on n'exécute jamais de
    code. Dépendance-légère : ``re`` de la bibliothèque standard uniquement.
    """
    if not gabarit:
        return ""

    def _remplacer(match):
        nom = match.group(1)
        valeur = contexte.get(nom, "")
        return str(valeur) if valeur is not None else ""

    return _JETON_RE.sub(_remplacer, gabarit)


def rendre_contrat(contrat, gabarit=None):
    """Rend le texte final d'un contrat par fusion de jetons.

    - ``gabarit`` : le corps-modèle à fusionner. Si ``None``, on tente le corps
      du ``ModeleContrat`` lié via ``contrat.modele`` (CONTRAT10 le pose), sinon
      on compose un corps par défaut à partir des clauses résolues.
    - Renvoie un dict ``{'gabarit', 'rendu', 'jetons'}`` : le gabarit utilisé,
      le texte fusionné, et le contexte de jetons (utile pour le débogage et le
      rendu PDF de CONTRAT11).

    Lecture seule : ne persiste rien.
    """
    contexte = contexte_fusion(contrat)

    if gabarit is None:
        modele = getattr(contrat, "modele", None)
        if modele is not None and modele.corps:
            gabarit = modele.corps
        else:
            gabarit = _gabarit_par_defaut(contexte)

    return {
        "gabarit": gabarit,
        "rendu": fusionner(gabarit, contexte),
        "jetons": contexte,
    }


# ---------------------------------------------------------------------------
# CONTRAT11 — Rendu PDF interne du contrat (hors /proposal)
# ---------------------------------------------------------------------------

def _contrat_html(contrat):
    """Construit le HTML interne (français) d'un contrat à partir de son rendu.

    Le texte fusionné (CONTRAT10) est échappé puis inséré dans un gabarit HTML
    sobre. Aucun jeton non résolu ni HTML utilisateur n'est interprété (tout est
    échappé) — pas d'injection possible.
    """
    rendu = rendre_contrat(contrat)["rendu"]
    corps = _html.escape(rendu).replace("\n", "<br/>")
    titre = _html.escape(contrat.objet or "Contrat")
    reference = _html.escape(contrat.reference or "")
    return (
        "<html><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:11pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;"
        "padding-bottom:6px;}"
        ".ref{color:#555;font-size:10pt;margin-bottom:18px;}"
        ".corps{white-space:normal;}"
        "</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<div class='ref'>Référence : {reference}</div>"
        f"<div class='corps'>{corps}</div>"
        "</body></html>"
    )


def rendre_contrat_pdf(contrat):
    """Rend un PDF INTERNE du contrat (bytes) — hors ``/proposal``.

    PDF de travail interne : ce N'EST PAS un PDF de devis client (``/proposal``
    reste l'unique chemin des PDF de devis). Import de ``weasyprint``
    FONCTION-LOCAL pour ne pas alourdir le chargement du module ni casser les
    environnements sans la lib.
    """
    import weasyprint  # import local : lib lourde, chargée à la demande

    html_str = _contrat_html(contrat)
    return weasyprint.HTML(string=html_str).write_pdf()


def _gabarit_par_defaut(contexte):
    """Gabarit de repli (français) quand aucun corps de modèle n'est fourni.

    Produit un contrat lisible à partir des seuls jetons disponibles — sert de
    filet pour qu'un contrat sans gabarit donne tout de même un rendu propre.
    """
    return (
        "CONTRAT — {{ objet }}\n"
        "Référence : {{ reference }}\n"
        "Type : {{ type_contrat }}\n"
        "Montant : {{ montant }}\n"
        "Période : {{ date_debut }} → {{ date_fin }}\n\n"
        "Parties :\n{{ parties }}\n\n"
        "Clauses :\n{{ clauses }}\n"
    )
