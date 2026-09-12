"""XPLT17 — génération de la valeur d'un champ IA (LLM), à la demande.

Réutilise le service LLM générique de la fondation (``core.ai``), le même
que ``core.ai.services.summarize_thread``/``draft_reply``. NO-OP-safe : sans
clé LLM configurée, ``generate_ia_value`` renvoie un message dégradé clair et
n'écrit rien — jamais d'exception, jamais d'appel réseau. La génération est
TOUJOURS déclenchée par une action utilisateur explicite (bouton « Générer »)
— jamais de génération automatique en masse (aucun job planifié n'appelle
cette fonction).
"""
from __future__ import annotations

from dataclasses import dataclass

# XPLT17 — placeholders JAMAIS autorisés dans un prompt de champ IA : le
# fondateur exige qu'un champ IA ne puisse pas référencer prix_achat ni la
# marge (cf. `Produit.prix_achat` = indicateur GÉNÉRATEUR-ONLY, jamais dans un
# PDF ni une sortie client — un prompt LLM est une sortie potentiellement
# visible par l'utilisateur, donc soumise à la même garde).
FORBIDDEN_PROMPT_PLACEHOLDERS = (
    'prix_achat', 'marge', 'cout_horaire', 'coût_horaire',
)


@dataclass
class IAFieldResult:
    """Résultat de la génération d'un champ IA."""

    ok: bool = False
    configured: bool = False
    text: str = ''
    source: str = 'noop'
    error: str = ''

    @property
    def available(self) -> bool:
        return self.ok and bool(self.text)


def validate_ia_prompt(prompt: str) -> list[str]:
    """Valide qu'un prompt admin de champ IA ne référence AUCUN placeholder
    interdit (whitelist inversée — comme les gabarits existants FG353/354).
    Renvoie une liste d'erreurs (vide ⇒ valide). N'évalue rien, ne lève pas."""
    errors: list[str] = []
    lowered = (prompt or '').lower()
    for forbidden in FORBIDDEN_PROMPT_PLACEHOLDERS:
        if forbidden in lowered:
            errors.append(
                f"Le prompt ne peut pas référencer « {forbidden} » "
                "(champ interne, jamais exposé).")
    return errors


def render_prompt(template: str, context: dict) -> str:
    """Substitue les placeholders ``{code}`` du prompt par les valeurs de
    ``context`` (dict plat fourni par l'appelant — un code absent du contexte
    est laissé tel quel, jamais d'exception sur une clé manquante)."""
    class _SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'
    return (template or '').format_map(_SafeDict(context or {}))


def valider_formule_definition(formule: str, sibling_codes) -> tuple[bool, str]:
    """NTEXT1 — valide une formule de champ CALCULÉ à la DÉFINITION.

    Réutilise ``core.formula.valider_formule`` (syntaxe sûre, AST — jamais
    ``eval``) contre les ``code`` des champs FRÈRES (mêmes société+module),
    et applique la MÊME garde que les prompts IA : une formule ne peut
    JAMAIS référencer ``prix_achat``/``marge`` (``FORBIDDEN_PROMPT_
    PLACEHOLDERS``), même si un champ frère porte ce nom. Renvoie
    ``(ok, erreur)`` — n'exécute aucun effet de bord.
    """
    from core.formula import valider_formule

    if not (formule or '').strip():
        return False, 'La formule est vide.'
    lowered = formule.lower()
    for forbidden in FORBIDDEN_PROMPT_PLACEHOLDERS:
        if forbidden in lowered:
            return False, (
                f'La formule ne peut pas référencer « {forbidden} » '
                '(champ interne, jamais exposé).')
    return valider_formule(formule, list(sibling_codes or []))


def evaluer_champ_formule(field_def, context: dict):
    """NTEXT1 — calcule la valeur d'UN champ FORMULA à la LECTURE.

    ``context`` = les autres champs custom de l'enregistrement. Les clés
    interdites (``FORBIDDEN_PROMPT_PLACEHOLDERS`` — prix_achat/marge…) sont
    retirées du contexte AVANT évaluation, même garde que les prompts IA :
    une formule ne peut jamais lire ces valeurs, même par accident. Ne lève
    jamais : une formule invalide/non évaluable renvoie ``None`` (dégradation
    propre, jamais un 500 sur une fiche existante)."""
    from core.formula import evaluer_formule, FormulaError

    safe_context = {
        k: v for k, v in dict(context or {}).items()
        if str(k).lower() not in FORBIDDEN_PROMPT_PLACEHOLDERS
    }
    try:
        return evaluer_formule(field_def.formule, safe_context)
    except FormulaError:
        return None


def calculer_champs_formule(module: str, company, data: dict) -> dict:
    """NTEXT1 — calcule TOUS les champs FORMULA actifs d'un module pour un
    ``data``/``custom_data`` donné. Renvoie ``{code: valeur}`` — JAMAIS
    persisté par cette fonction, à fusionner par l'appelant dans sa réponse
    de LECTURE uniquement (jamais dans les valeurs sauvegardées)."""
    from .models import CustomFieldDef

    defs = CustomFieldDef.objects.filter(
        company=company, module=module, actif=True,
        type=CustomFieldDef.FieldType.FORMULA)
    return {d.code: evaluer_champ_formule(d, data) for d in defs}


def generate_ia_value(*, field_def, context: dict) -> IAFieldResult:
    """Génère la valeur d'un champ IA à partir de son prompt + du contexte de
    l'enregistrement (dict plat fourni par l'appelant — jamais de modèle
    métier importé ici, cohérent avec core.ai.services).

    NO-OP-safe : sans fournisseur LLM configuré, renvoie ``configured=False``
    avec un message dégradé clair — l'appelant affiche alors ce message sans
    écrire dans custom_data (jamais un champ IA sans clé n'est silencieusement
    vide)."""
    from core.ai.registry import get_provider

    prompt_errors = validate_ia_prompt(field_def.ia_prompt)
    if prompt_errors:
        return IAFieldResult(ok=False, configured=False, text='',
                             source='noop', error='; '.join(prompt_errors))

    provider = get_provider('llm')
    if getattr(provider, 'key', 'noop') == 'noop':
        return IAFieldResult(
            ok=False, configured=False, text='', source='noop',
            error="Génération IA indisponible (aucune clé LLM configurée).")

    prompt = render_prompt(field_def.ia_prompt, context)
    if not prompt.strip():
        return IAFieldResult(
            ok=False, configured=True, text='', source=provider.key,
            error='Prompt vide — rien à générer.')

    system = (
        "Tu assistes un utilisateur ERP marocain (solaire). Réponds en "
        "français, de façon concise et factuelle. N'invente aucune donnée "
        "chiffrée absente du contexte fourni."
    )
    res = provider.complete(prompt=prompt, system=system, max_tokens=300)
    if res.ok and res.data.get('text'):
        return IAFieldResult(ok=True, configured=True,
                             text=res.data['text'].strip(),
                             source=res.provider)
    return IAFieldResult(
        ok=False, configured=True, text='', source=res.provider,
        error=res.error or 'Échec de la génération.')
