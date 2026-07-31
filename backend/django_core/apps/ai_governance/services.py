"""Services du module « ai_governance » — copilotes IA NO-OP-safe (Groupe NTAI).

Tout ce qui vit ici respecte trois invariants :

  1. **Key-gated / NO-OP-safe** — sans fournisseur LLM configuré (``GROQ_API_KEY``
     ou équivalent), AUCUN appel réseau n'est fait et l'appelant reçoit une
     erreur métier explicite (503 douce côté vue) ; jamais une 500.
  2. **Jamais d'écriture implicite** — ces services PROPOSENT un brouillon.
     L'application de la proposition reste une action utilisateur explicite,
     par les endpoints métier existants.
  3. **Confidentialité des données internes** — les faits envoyés au
     fournisseur externe sont construits par une ALLOWLIST explicite de champs,
     jamais par sérialisation d'un objet entier : un champ interne ajouté plus
     tard au modèle ne peut pas fuiter tout seul.

Note NTAI5 : les prompts par défaut vivent en constantes de module. Quand la
bibliothèque de prompts éditables (``PromptTemplate`` + ``render_prompt``)
sera posée, ces constantes deviendront le « défaut code » sur lequel elle
retombe — le corps des fonctions ci-dessous ne change pas.
"""
from __future__ import annotations

from core.ai.registry import get_provider, is_capability_configured


class AiCopiloteUnavailable(Exception):
    """Levée quand un copilote ne peut pas produire de brouillon.

    ``configured=False`` → aucune clé LLM/STT (503 douce côté vue, aucun appel
    réseau) ; ``configured=True`` → entrée invalide ou refus fournisseur (400).
    """

    def __init__(self, message, *, configured=True):
        super().__init__(message)
        self.configured = configured


# ─────────────────────────────────────────────────────────────────────────────
# NTAI13 — Génération de description produit (catalogue)
# ─────────────────────────────────────────────────────────────────────────────
#
# GARDE DE CONFIDENTIALITÉ (règle du dépôt) : ``Produit.prix_achat`` est une
# donnée INTERNE (elle alimente l'indicateur de marge du générateur de devis)
# et ne doit JAMAIS quitter le système, a fortiori vers un fournisseur LLM
# externe. Même motif que ``core.ai.services.CAMPAIGN_PROMPT_FORBIDDEN_TERMS``
# (XMKT34), mais renforcé : au lieu de filtrer une chaîne déjà construite, on
# construit le prompt à partir d'une ALLOWLIST de champs (aucun prix, ni
# d'achat ni de vente) et on VÉRIFIE ensuite l'absence des termes interdits.

#: Champs de ``Produit`` autorisés dans le prompt de description. Toute donnée
#: hors de cette liste (prix d'achat, prix de vente, marge, stock, fournisseur)
#: est structurellement absente du prompt.
PRODUIT_DESCRIPTION_ALLOWED_FIELDS = ('nom', 'marque', 'categorie', 'garantie')

#: Termes dont la présence dans le prompt construit signale une fuite de donnée
#: commerciale interne (garde de dernier recours, testée).
PRODUIT_DESCRIPTION_FORBIDDEN_TERMS = (
    'prix_achat', 'prix d\'achat', 'prix achat', 'marge',
    'coût interne', 'cout interne', 'prix_vente',
)

#: Prompt système par défaut (futur « défaut code » de NTAI5, clé
#: ``ai.description_produit``).
PRODUIT_DESCRIPTION_SYSTEM = (
    "Tu es un rédacteur catalogue pour un installateur solaire au Maroc. "
    "À partir des seules caractéristiques fournies, rédige en français : "
    "(1) une description commerciale de 3 à 5 phrases, factuelle et concrète ; "
    "(2) sur une dernière ligne préfixée « COURT : », une variante d'une seule "
    "phrase. N'invente aucune caractéristique technique, aucun prix, aucun "
    "délai et aucune certification qui ne figure pas ci-dessous."
)


def produit_description_facts(produit) -> dict:
    """Faits envoyables au LLM pour ``produit`` — ALLOWLIST stricte.

    Ne lit QUE :data:`PRODUIT_DESCRIPTION_ALLOWED_FIELDS`. ``prix_achat`` (et
    tout autre champ interne) n'est jamais lu, donc jamais transmis.
    """
    categorie = getattr(produit, 'categorie', None)
    raw = {
        'nom': getattr(produit, 'nom', '') or '',
        'marque': getattr(produit, 'marque', '') or '',
        'categorie': getattr(categorie, 'nom', '') or '',
        'garantie': getattr(produit, 'garantie', '') or '',
    }
    return {
        cle: str(raw.get(cle) or '').strip()
        for cle in PRODUIT_DESCRIPTION_ALLOWED_FIELDS
    }


def build_description_produit_prompt(facts: dict) -> str:
    """Construit le prompt utilisateur à partir des faits allowlistés.

    Lève ``ValueError`` si un terme interdit (prix d'achat, marge…) apparaît
    dans le texte produit — garde de dernier recours contre une régression qui
    élargirait l'allowlist sans y penser.
    """
    labels = {
        'nom': 'Désignation',
        'marque': 'Marque',
        'categorie': 'Catégorie',
        'garantie': 'Garantie',
    }
    lignes = [
        f'{labels[cle]} : {facts[cle]}'
        for cle in PRODUIT_DESCRIPTION_ALLOWED_FIELDS
        if facts.get(cle)
    ]
    prompt = 'Caractéristiques du produit :\n' + '\n'.join(lignes)
    lowered = prompt.lower()
    fuite = [t for t in PRODUIT_DESCRIPTION_FORBIDDEN_TERMS if t in lowered]
    if fuite:
        raise ValueError(
            f'Donnée interne interdite dans le prompt produit : {sorted(fuite)}')
    return prompt


def _split_description(texte: str) -> tuple[str, str]:
    """Sépare la description longue de la variante courte (« COURT : … »)."""
    longue, courte = [], ''
    for ligne in (texte or '').splitlines():
        nu = ligne.strip()
        if nu.upper().startswith('COURT'):
            _, _, reste = nu.partition(':')
            courte = reste.strip()
            continue
        if nu:
            longue.append(nu)
    return '\n'.join(longue).strip(), courte


def generer_description_produit(*, company, produit_id, max_tokens=400) -> dict:
    """NTAI13 — Propose une description commerciale FR + une variante courte.

    N'ÉCRIT RIEN : renvoie un brouillon que l'utilisateur valide (puis applique
    via l'endpoint produit existant). ``prix_achat`` n'est jamais transmis au
    fournisseur (voir :func:`produit_description_facts`).

    Lève :class:`AiCopiloteUnavailable` si le produit est introuvable dans la
    société (``configured=True`` → 400) ou si aucune clé LLM n'est configurée
    (``configured=False`` → 503, aucun appel réseau).
    """
    from apps.stock.selectors import get_produit_scoped

    try:
        produit = get_produit_scoped(company, produit_id)
    except (TypeError, ValueError):
        produit = None
    if produit is None:
        raise AiCopiloteUnavailable('Produit introuvable.')

    facts = produit_description_facts(produit)
    if not facts.get('nom'):
        raise AiCopiloteUnavailable(
            'Le produit doit avoir une désignation pour être décrit.')

    if not is_capability_configured('llm'):
        raise AiCopiloteUnavailable(
            "Aucun fournisseur LLM n'est configuré (clé absente) — "
            'rédaction manuelle requise.', configured=False)

    prompt = build_description_produit_prompt(facts)
    res = get_provider('llm').complete(
        prompt=prompt, system=PRODUIT_DESCRIPTION_SYSTEM, max_tokens=max_tokens)
    if not res.ok or not (res.data or {}).get('text'):
        raise AiCopiloteUnavailable(
            "Le fournisseur n'a pas produit de description exploitable.")

    description, description_courte = _split_description(res.data['text'])
    return {
        'produit_id': produit.id,
        'description': description,
        'description_courte': description_courte,
        # Contrat explicite pour l'UI : rien n'a été enregistré.
        'applique': False,
        'source': res.provider,
    }
