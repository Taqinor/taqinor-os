"""PUB71/PUB72 — Mine de questions (commentaires) + mine d'objections (CRM).

``comments.py`` (ADSDEEP53) synchronise déjà TOUS les commentaires organiques/
dark-post ; ce module en extrait les QUESTIONS récurrentes (prix ? garantie ?
subvention ? durée ?), agrégées par thème → candidats prêts pour amorcer
``generation.generate_grounded_variants(seed_brief=...)`` + une section FAQ
pour le reporting créatif.

PUB72 étend le même patron d'extraction PURE (mots-clés simples, JAMAIS un
LLM) aux OBJECTIONS de vente : ``motif_perte`` + notes de chatter
``LeadActivity`` (texte libre), lues via ``apps.crm.selectors`` UNIQUEMENT
(jamais un import de ``apps.crm.models`` côté adsengine), résolues PAR AD via
la même échelle de résolution que ``attribution.variant_attribution``
(ADSENG6) — l'or que aucun SaaS pub concurrent ne peut toucher (il n'a pas le
CRM). Les angles suggérés qui en sortent restent des RECOMMANDATIONS, jamais
une action automatique.

Tout ici est extraction PURE (regex / listes de mots-clés FR-Darija) —
aucune I/O réseau, aucun appel LLM.
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


# ── §2 — PUB72 : Thèmes d'OBJECTION (CRM : motif_perte + notes chatter) ────
OBJECTION_PRIX = 'prix'
OBJECTION_CONFIANCE = 'confiance'
OBJECTION_DELAI = 'delai'
OBJECTION_TECHNIQUE = 'technique'
OBJECTION_AUTRE = 'autre'

OBJECTION_LABELS_FR = {
    OBJECTION_PRIX: 'Prix',
    OBJECTION_CONFIANCE: 'Confiance',
    OBJECTION_DELAI: 'Délai',
    OBJECTION_TECHNIQUE: 'Technique',
    OBJECTION_AUTRE: 'Autre',
}

_OBJECTION_KEYWORDS = {
    OBJECTION_PRIX: (
        'prix', 'cher', 'chere', 'coûte', 'coute', 'budget', 'moyens',
        'tarif', 'trop cher', 'onéreux', 'onereux',
    ),
    OBJECTION_CONFIANCE: (
        'confiance', 'arnaque', 'fiable', 'sérieux', 'serieux', 'doute',
        'avis', 'sceptique', 'méfiant', 'mefiant', 'crédible', 'credible',
    ),
    OBJECTION_DELAI: (
        'délai', 'delai', 'attente', 'lent', 'retard', 'tarde', 'longtemps',
    ),
    OBJECTION_TECHNIQUE: (
        'technique', 'panne', 'installation', 'qualité', 'qualite',
        'ne marche pas', 'ne fonctionne pas', 'problème', 'probleme',
        'défaut', 'defaut',
    ),
}

# Angle FR suggéré par thème d'objection — une RECOMMANDATION versée au
# backlog créatif, jamais une action (aucune écriture Meta/CRM ici).
_SUGGESTED_ANGLES_FR = {
    OBJECTION_PRIX: (
        "Mettre en avant le financement / paiement échelonné (objection "
        "prix récurrente)."),
    OBJECTION_CONFIANCE: (
        "Mettre en avant témoignages vérifiés et certifications (objection "
        "confiance récurrente)."),
    OBJECTION_DELAI: (
        "Communiquer sur le délai réel d'installation (objection délai "
        "récurrente)."),
    OBJECTION_TECHNIQUE: (
        "Mettre en avant la garantie technique et le SAV (objection "
        "technique récurrente)."),
}


def classify_objection_theme(text):
    """Thème d'objection (prix/confiance/délai/technique), tags mots-clés
    PURS (jamais un LLM). ``None`` si ``text`` est vide. ``autre`` si le
    texte est non vide mais ne matche aucun mot-clé connu (jamais silencieux
    — le texte existe toujours quelque part dans le rapport brut)."""
    t = (text or '').strip().lower()
    if not t:
        return None
    for theme, keywords in _OBJECTION_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return theme
    return OBJECTION_AUTRE


def _themes_to_rows(themes):
    rows = [
        {'theme': theme, 'label_fr': OBJECTION_LABELS_FR.get(theme, theme),
         'count': slot['count'], 'echantillons': slot['echantillons']}
        for theme, slot in themes.items()
    ]
    rows.sort(key=lambda r: r['count'], reverse=True)
    return rows


def mine_ad_objections(company):
    """PUB72 — Top objections PAR VARIANTE d'annonce, minées depuis
    ``motif_perte`` + les notes de chatter ``LeadActivity`` (texte libre,
    lues via ``apps.crm.selectors.objection_mining_rows`` — jamais un import
    de ``apps.crm.models``), résolues à l'ad via la MÊME échelle de
    résolution que ``attribution.variant_attribution`` (ADSENG6, réutilisée
    telle quelle — aucune logique de jointure dupliquée). Renvoie ::

        {'par_ad': [{'meta_id', 'name', 'objections': [...],
                     'angles_suggeres': [...]}, ...],   # triées, + demandé
         'non_resolues': {'objections': [...]}}

    Un lead sans texte exploitable (ni motif_perte, ni note) est simplement
    ignoré (jamais un thème fabriqué). Les angles restent des SUGGESTIONS
    (backlog) — aucune action automatique."""
    from apps.crm.selectors import objection_mining_rows

    from .attribution import _resolve_ad_id
    from .models import AdMirror

    ads = list(AdMirror.objects.filter(company=company))
    by_meta = {a.meta_id: a for a in ads}
    name_to_meta = {}
    for a in ads:
        if a.name:
            name_to_meta.setdefault(a.name, a.meta_id)

    buckets = {m: {} for m in by_meta}
    unresolved = {}

    for row in objection_mining_rows(company):
        texts = list(row.get('notes') or [])
        if row.get('motif_perte'):
            texts.append(row['motif_perte'])
        if not texts:
            continue
        meta_id = _resolve_ad_id(row, by_meta, name_to_meta)
        target = buckets[meta_id] if meta_id is not None else unresolved
        for text in texts:
            theme = classify_objection_theme(text)
            if theme is None:
                continue
            slot = target.setdefault(theme, {'count': 0, 'echantillons': []})
            slot['count'] += 1
            if len(slot['echantillons']) < 3:
                slot['echantillons'].append(text)

    par_ad = []
    for meta_id, themes in buckets.items():
        if not themes:
            continue
        rows = _themes_to_rows(themes)
        angles = [
            _SUGGESTED_ANGLES_FR[r['theme']] for r in rows
            if r['theme'] in _SUGGESTED_ANGLES_FR
        ]
        ad = by_meta[meta_id]
        par_ad.append({
            'meta_id': meta_id, 'name': ad.name or '',
            'objections': rows, 'angles_suggeres': angles,
        })
    par_ad.sort(
        key=lambda r: sum(o['count'] for o in r['objections']), reverse=True)

    return {
        'par_ad': par_ad,
        'non_resolues': {'objections': _themes_to_rows(unresolved)},
    }
