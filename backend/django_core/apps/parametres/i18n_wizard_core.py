"""NTI18N32 — cœur (logique PURE) de l'assistant de migration
« chaîne en dur → clé i18n ».

Consommé par la commande ``manage.py i18n_wizard`` (management/commands/
i18n_wizard.py), qui fait le SEUL I/O (lecture/écriture du fichier JSX cible
et des 3 catalogues) — ce module ne touche jamais au disque, ce qui le rend
testable sans fixtures fichier.

Outil INTERNE pour développeurs (pas d'écran UI) : accélère le rollout
NTI18N1 (câbler un ``t()`` déjà présent dans le cadre i18n léger) SANS
automatiser la TRADUCTION elle-même — seule la valeur FR est réelle ; EN/AR
reçoivent un ``TODO_TRADUCTION`` explicite, à relire par un humain.

Limites ASSUMÉES (documentées, pas un bug) : détecte les littéraux JSX texte
simples entre balises (``>texte<``) et la valeur de quelques attributs usuels
(label/title/placeholder/aria-label) sur UNE SEULE ligne — ne traite pas les
expressions JS multi-lignes ni les template literals. Ne modifie JAMAIS un
import ou un hook ``useT()`` : après le remplacement, le développeur reste
responsable de s'assurer que ``t`` est bien en scope dans le composant.
"""
from __future__ import annotations

import os
import re
import unicodedata

#: Attributs JSX dont la valeur littérale est un texte candidat.
ATTRIBUTS_CANDIDATS = ('label', 'title', 'placeholder', 'aria-label')

#: Un littéral est candidat s'il contient au moins une lettre (on ne migre
#: jamais un littéral purement numérique/symbolique).
_LETTRE_RE = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]')

#: Texte JSX enfant : entre `>` et `<`, sans accolade (jamais une expression
#: JS ``{...}``, jamais du texte déjà interpolé).
_TEXTE_ENFANT_RE = re.compile(r'>([^<>{}\n]+)<')

#: Valeur d'un attribut candidat : ``label="..."`` (guillemets doubles).
_ATTRIBUT_RE = re.compile(
    r'\b(' + '|'.join(ATTRIBUTS_CANDIDATS) + r')="([^"\n{}]+)"')


def _slugifier(texte: str, max_len: int = 40) -> str:
    """``texte`` -> segment de clé ASCII minuscule (accents retirés)."""
    normalise = unicodedata.normalize('NFKD', texte)
    sans_accents = ''.join(c for c in normalise if not unicodedata.combining(c))
    minuscule = sans_accents.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', minuscule).strip('_')
    return slug[:max_len].strip('_') or 'texte'


def domaine_et_section(chemin_fichier: str) -> tuple[str, str]:
    """(domaine, section) dérivés du chemin — dossier parent + nom de
    fichier, tous deux slugifiés. Un fichier sans dossier parent significatif
    reçoit le domaine générique ``'ui'``."""
    dossier = os.path.basename(os.path.dirname(chemin_fichier))
    fichier = os.path.splitext(os.path.basename(chemin_fichier))[0]
    domaine = _slugifier(dossier) if dossier else 'ui'
    section = _slugifier(fichier)
    return domaine, section


def litteraux_candidats(contenu: str) -> list[dict]:
    """Littéraux FR candidats détectés dans ``contenu`` (source JSX).

    Chaque entrée : ``{'texte', 'type': 'enfant'|'attribut',
    'attribut': str|None, 'span': (debut, fin)}`` — ``span`` permet un
    remplacement par POSITION (jamais un ``str.replace`` global, qui
    toucherait à tort une occurrence identique ailleurs dans le fichier).
    """
    resultats = []
    for m in _TEXTE_ENFANT_RE.finditer(contenu):
        brut = m.group(1)
        texte = brut.strip()
        if texte and _LETTRE_RE.search(texte):
            decalage = len(brut) - len(brut.lstrip())
            debut = m.start(1) + decalage
            resultats.append({
                'texte': texte, 'type': 'enfant', 'attribut': None,
                'span': (debut, debut + len(texte)),
            })
    for m in _ATTRIBUT_RE.finditer(contenu):
        attribut, texte = m.group(1), m.group(2)
        if texte and _LETTRE_RE.search(texte):
            # Le span couvre LES GUILLEMETS inclus (``m.start(2) - 1`` à
            # ``m.end(2) + 1``) : un attribut JSX passe de
            # ``title="Enregistrer"`` à ``title={t('cle')}`` — remplacer
            # SEULEMENT le texte entre guillemets produirait
            # ``title="{t('cle')}"``, syntaxiquement invalide (chaîne
            # littérale au lieu d'une expression JSX).
            resultats.append({
                'texte': texte, 'type': 'attribut', 'attribut': attribut,
                'span': (m.start(2) - 1, m.end(2) + 1),
            })
    resultats.sort(key=lambda r: r['span'][0])
    return resultats


def proposer_cle(domaine: str, section: str, texte: str) -> str:
    """Clé ``domaine.section.libelle`` générée automatiquement."""
    return f'{domaine}.{section}.{_slugifier(texte)}'


def appliquer_remplacements(contenu: str, remplacements: list[dict]) -> str:
    """Remplace chaque littéral confirmé (``remplacements[i]['cle']`` posé
    par l'appelant) par ``{t('cle')}``, par POSITION — en partant de la FIN
    du fichier pour ne jamais décaler les spans déjà calculés."""
    resultat = contenu
    for r in sorted(remplacements, key=lambda x: x['span'][0], reverse=True):
        debut, fin = r['span']
        resultat = resultat[:debut] + "{t('" + r['cle'] + "')}" + resultat[fin:]
    return resultat


def entrees_catalogues(remplacements: list[dict]) -> dict:
    """``{'fr': {cle: texte_reel}, 'en': {cle: 'TODO_TRADUCTION'}, 'ar': {...}}``.

    ``fr`` est TOUJOURS le texte réel détecté (jamais un TODO) ; ``en``/``ar``
    portent explicitement ``'TODO_TRADUCTION'`` — jamais une traduction
    automatique inventée."""
    fr, en, ar = {}, {}, {}
    for r in remplacements:
        fr[r['cle']] = r['texte']
        en[r['cle']] = 'TODO_TRADUCTION'
        ar[r['cle']] = 'TODO_TRADUCTION'
    return {'fr': fr, 'en': en, 'ar': ar}
