"""PUB126 — Étiquette « généré par IA » : le VOCABULAIRE, en module FEUILLE.

Extrait de ``creative_factory`` (contrat import-linter ENG20) : ``policy`` doit
pouvoir juger la divulgation IA sans tirer la fabrique entière — la fabrique
importe ``installations.selectors`` (photos de chantier), qui atteint depuis le
20/09 les selectors calepinage→crm : ``adsengine.models → policy →
creative_factory`` re-liait donc transitivement les MODÈLES adsengine aux
modèles business-core. Ce module n'importe RIEN d'app : policy ET la fabrique
le consomment, l'edge policy→fabrique est coupé.

La règle métier est inchangée : une variante DÉRIVÉE d'un asset IA reste de
l'IA (héritage du parent) ; une substitution d'assets réels n'est jamais
sur-étiquetée. La divulgation suit le CONTENU, pas la plomberie.
"""

AI_GENERATED_LANES = frozenset({'gen', 'recombine', 'fal'})


def lane_is_ai_generated(source_lane):
    """PUB126 — Vrai si la lane de fabrique ``source_lane`` produit du contenu
    généré par IA (donc à divulguer). Lane inconnue / vide ⇒ ``False``."""
    return str(source_lane or '') in AI_GENERATED_LANES


def asset_is_ai_generated(source_lane, parent=None):
    """PUB126 — Étiquette IA d'un asset en PRODUCTION : sa lane génère de l'IA,
    OU il dérive d'un parent déjà étiqueté (une variante d'un asset IA reste de
    l'IA). Jamais vrai pour une substitution d'assets réels."""
    return (lane_is_ai_generated(source_lane)
            or bool(getattr(parent, 'ai_generated', False)))
