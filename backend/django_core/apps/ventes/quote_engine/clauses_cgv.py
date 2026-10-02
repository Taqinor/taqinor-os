"""QJR668 (décision fondateur 01/10/2026) — le bloc « Clauses particulières »
imprimé par TOUS les gabarits du devis (résidentiel, commercial, industriel,
legacy plein format et une page).

Source unique : ``data['clauses_cgv']`` posé par ``builder`` depuis le
snapshot ``Devis.clauses_appliquees`` (gelé à l'envoi, re-gelé à chaque
correction par ``domain/cycle_vie``). Le moteur ne fait que RENDRE : aucune
clause n'est choisie ni recalculée ici.

Les textes arrivent DÉJÀ échappés (``builder.echapper_textes_client`` pour
les gabarits maison, ``apply_quote_data`` pour le legacy) : rien n'est
ré-échappé. Sans clause → chaîne vide (document octet-identique).

QJR668 (décision fondateur 01/10/2026, « figer le texte CGV à l'envoi ») —
ce module porte aussi LA fonction pure qui remplit les cases du texte CGV
société (``{acompte}``, ``{materiel}``, ``{solde}``, ``{tva_note}``,
``{validite_offre}``) avec les valeurs d'un devis : :func:`remplir_cgv`. Le
moteur (rendu en direct, ``_cgv_bullets_html``) et le gel
(``domain/cycle_vie.clauses_applicables_devis``) l'appellent TOUS LES DEUX —
jamais deux copies. Module pur (stdlib seule) : importable hors Django.
"""
import re

TITRE = "Clauses particulières"

#: Titre historique du bloc « Conditions générales » (repli quand la société
#: n'a pas saisi le sien). ``DEFAULT_DOC_TEXTS['cgv_titre']`` du moteur le lit
#: ici : une seule source.
CGV_TITRE_DEFAUT = "Conditions générales du devis"

#: Marque l'entrée de ``Devis.clauses_appliquees`` qui porte le texte CGV
#: SOCIÉTÉ figé (titre + puces remplies). Le builder la sert au bloc
#: « Conditions générales » (``data['cgv_figees']``) et la RETIRE des
#: « Clauses particulières » : la CGV n'est jamais imprimée deux fois.
SOURCE_CGV_SOCIETE = "cgv_societe"

_CASE = re.compile(r"\{(\w*)\}")


def pourcentage_affiche(valeur, defaut):
    """Pourcentage d'échéancier tel qu'imprimé : ``40.0`` → ``40``, ``33.5``
    → ``33.5`` (QJR623 : la décimale n'est plus tronquée) ; illisible →
    ``defaut``. Partagé par l'ingestion du moteur et le gel CGV."""
    try:
        f = float(valeur if valeur is not None else defaut)
    except (TypeError, ValueError):
        f = float(defaut)
    return int(f) if f == int(f) else round(f, 2)


def termes_paiement_affiches(data):
    """``(acompte, materiel, solde)`` imprimés pour une charge utile
    ``build_quote_data`` (repli historique 30/60/10)."""
    terms = (data or {}).get("payment_terms") or {}
    return (pourcentage_affiche(terms.get("acompte"), 30),
            pourcentage_affiche(terms.get("materiel"), 60),
            pourcentage_affiche(terms.get("solde"), 10))


def valeurs_cgv(*, acompte, materiel, solde, tva_note, valid_until):
    """Les valeurs des cases du texte CGV pour un devis.

    ``validite_offre`` porte la VRAIE échéance (M7) ou rien : échéance
    inconnue ⇒ chaîne vide ⇒ la puce qui ne contient qu'elle disparaît."""
    valid_until = (valid_until or "").strip()
    return {
        "acompte": acompte,
        "materiel": materiel,
        "solde": solde,
        "tva_note": tva_note or "",
        "validite_offre": (
            "Validit&#233; de l&#8217;offre&#160;: jusqu&#8217;au "
            f"{valid_until}" if valid_until else ""),
    }


def remplir_cgv(puces, valeurs):
    """FONCTION PURE — les puces CGV avec leurs cases remplies.

    * chaque ``{cle}`` connue de ``valeurs`` est remplacée par sa valeur ;
    * une case INCONNUE (faute de frappe société) est remplacée par une
      chaîne vide — une case ``{…}`` brute n'est JAMAIS imprimée ;
    * une puce vide après remplissage est omise.

    Les puces ne sont pas échappées : ce sont des fragments éditoriaux de la
    société qui portent leurs entités HTML (``&#160;``, ``&#37;``), imprimés
    tels quels par le moteur — le texte figé l'est donc à l'identique.
    """
    sortie = []
    for brute in puces or []:
        texte = _CASE.sub(
            lambda m: str(valeurs.get(m.group(1), "") if valeurs else ""),
            str(brute))
        if texte.strip():
            sortie.append(texte)
    return sortie


def bloc_clauses_html(clauses, *, couleur_titre="#0f2a44",
                      couleur_texte="#334155", taille_pt="7.5"):
    """HTML compact des clauses gelées, ou ``""`` quand il n'y en a pas."""
    lignes = []
    for c in clauses or []:
        if not isinstance(c, dict):
            continue
        nom = str(c.get("nom") or "").strip()
        corps = str(c.get("corps_texte") or "").strip()
        if not nom and not corps:
            continue
        tete = f"<b>{nom}</b>" + (" &#8212; " if nom and corps else "")
        lignes.append(f'<div style="margin-top:2px;">{tete}{corps}</div>')
    if not lignes:
        return ""
    return (
        f'<div class="clauses-cgv" style="margin-top:8px;font-size:{taille_pt}pt;'
        f'line-height:1.35;color:{couleur_texte};">'
        f'<div style="font-weight:700;color:{couleur_titre};'
        'text-transform:uppercase;letter-spacing:.8px;">'
        f'{TITRE}</div>{"".join(lignes)}</div>')
