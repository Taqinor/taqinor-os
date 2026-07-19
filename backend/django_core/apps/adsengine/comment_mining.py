"""PUB71 — Mine de questions des commentaires.

``comments.py`` (ADSDEEP53) synchronise déjà TOUS les commentaires organiques/
dark-post ; ce module en extrait les QUESTIONS récurrentes (prix ? garantie ?
subvention ? durée ?), agrégées par thème → candidats prêts pour amorcer
``generation.generate_grounded_variants(seed_brief=...)`` + une section FAQ
pour le reporting créatif.

Extraction PURE (regex / listes de mots-clés FR-Darija) — aucune I/O réseau,
aucun appel LLM.
"""
from __future__ import annotations

# ── §1 — Thèmes de QUESTION (commentaires) ────────────────────────────────
THEME_PRIX = 'prix'
THEME_GARANTIE = 'garantie'
THEME_SUBVENTION = 'subvention'
THEME_DUREE = 'duree'
THEME_AUTRE = 'autre'

THEME_LABELS_FR = {
    THEME_PRIX: 'Prix',
    THEME_GARANTIE: 'Garantie',
    THEME_SUBVENTION: 'Subvention / aide',
    THEME_DUREE: 'Durée / délai',
    THEME_AUTRE: 'Autre',
}

# Mots-clés FR + Darija (arabizi) courants — comparaison « contient »,
# insensible à la casse, jamais un LLM. Ordre du dict = ordre de priorité
# déterministe quand plusieurs thèmes matchent (le premier gagne).
_THEME_KEYWORDS = {
    THEME_PRIX: (
        'prix', 'coût', 'cout', 'tarif', 'combien', 'chhal', 'kddach',
        'kadech', 'montant', 'thaman', 'flous',
    ),
    THEME_GARANTIE: (
        'garantie', 'garanti', 'sav', 'panne', 'assurance',
    ),
    THEME_SUBVENTION: (
        'subvention', 'aide', 'prime', 'financement', 'crédit', 'credit',
        'facilité', 'facilite', 'onee',
    ),
    THEME_DUREE: (
        'durée', 'duree', 'délai', 'delai', 'combien de temps',
        'wa9t', 'lwa9t', 'temps',
    ),
}

# Marqueurs interrogatifs FR + Darija (arabizi) — un texte SANS « ? » mais
# portant l'un de ces marqueurs reste classé « question » (le point
# d'interrogation est souvent omis en commentaire Facebook/Instagram).
_QUESTION_MARKERS = (
    'combien', 'chhal', 'kddach', 'kadech', 'comment', 'kifach', 'kif',
    'pourquoi', 'ach7al', 'quand', 'wach', 'wash', 'waqtach',
    "qu'est-ce", 'est-ce', "c'est quoi", 'chno', 'chnou',
)


def is_question(text):
    """Vrai si ``text`` ressemble à une QUESTION : point d'interrogation OU
    marqueur interrogatif FR/Darija courant. Fonction PURE — aucune I/O,
    aucun LLM."""
    t = (text or '').strip().lower()
    if not t:
        return False
    if '?' in t:
        return True
    return any(marker in t for marker in _QUESTION_MARKERS)


def classify_question_theme(text):
    """Thème d'une QUESTION (prix/garantie/subvention/durée), ou ``autre`` si
    c'est bien une question mais qu'aucun mot-clé connu ne matche. Renvoie
    ``None`` si ``text`` n'EST PAS une question (jamais mal classé comme
    « autre » un commentaire qui n'interroge rien). Fonction PURE (aucun
    LLM) — le premier thème dont un mot-clé matche gagne (ordre déterministe
    du dict)."""
    if not is_question(text):
        return None
    t = text.lower()
    for theme, keywords in _THEME_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return theme
    return THEME_AUTRE


def mine_comment_questions(company, *, min_theme_count=1):
    """PUB71 — Mine les commentaires DÉJÀ synchronisés (``comments.py``,
    ADSDEEP53) de la société pour en extraire les QUESTIONS récurrentes,
    agrégées par thème. 100 % lecture (aucune écriture). Renvoie ::

        {'themes': [{'theme', 'label_fr', 'count', 'echantillons': [...]},
                    ...],  # triés par fréquence décroissante
         'seed_brief_candidates': [str, ...],
         'total_comments': int, 'total_questions': int}

    ``seed_brief_candidates`` = phrases FR prêtes à amorcer
    ``generation.generate_grounded_variants(seed_brief=...)`` (PUB16, un
    candidat par thème avec ``count >= min_theme_count``, le plus demandé
    d'abord)."""
    from .models import CommentMirror

    comments = CommentMirror.objects.filter(company=company).only('message')
    themes = {}
    total_questions = 0
    total_comments = 0
    for c in comments:
        total_comments += 1
        theme = classify_question_theme(c.message)
        if theme is None:
            continue
        total_questions += 1
        slot = themes.setdefault(theme, {'count': 0, 'echantillons': []})
        slot['count'] += 1
        if len(slot['echantillons']) < 5:
            slot['echantillons'].append(c.message)

    rows = [
        {'theme': theme, 'label_fr': THEME_LABELS_FR.get(theme, theme),
         'count': slot['count'], 'echantillons': slot['echantillons']}
        for theme, slot in themes.items() if slot['count'] >= min_theme_count
    ]
    rows.sort(key=lambda r: r['count'], reverse=True)

    seed_brief_candidates = [
        f"Répondre à la question fréquente sur {r['label_fr'].lower()} "
        f"({r['count']} commentaire(s)) — ex. « {r['echantillons'][0]} »"
        for r in rows if r['echantillons']
    ]

    return {
        'themes': rows,
        'seed_brief_candidates': seed_brief_candidates,
        'total_comments': total_comments,
        'total_questions': total_questions,
    }
