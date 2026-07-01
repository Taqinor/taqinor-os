"""FG393 — Rendu SÛR des modèles de message (PDF / email / WhatsApp).

Couche de FONDATION : rend un texte de modèle en remplaçant les placeholders
``{{ variable }}`` par les valeurs d'un contexte fourni — SANS exécuter de code
(pas de ``eval``, pas de moteur de template arbitraire) et SANS que ``core``
n'importe une app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Les variables sont fournies par
l'appelant ; un placeholder inconnu est laissé vide (ou conservé tel quel selon
``strict``).
"""
from __future__ import annotations

import re

# Placeholder : {{ nom.de.variable }} (lettres, chiffres, _, ., espaces autour).
_PLACEHOLDER = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}')


def variables_utilisees(texte):
    """Liste ordonnée et dédupliquée des placeholders présents dans ``texte``."""
    seen = []
    for m in _PLACEHOLDER.finditer(texte or ''):
        name = m.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def _resolve(name, context):
    """Résout ``a.b.c`` dans ``context`` (dicts imbriqués / attributs simples)."""
    cur = context
    for part in name.split('.'):
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def rendre(texte, context=None, *, strict=False):
    """Rend ``texte`` en substituant les placeholders depuis ``context``.

    Substitution PUREMENT littérale (aucune exécution de code). Un placeholder
    sans valeur est remplacé par une chaîne vide ; en mode ``strict`` il est
    conservé tel quel (``{{ var }}``) pour signaler le manque.
    """
    context = dict(context or {})

    def _sub(match):
        name = match.group(1)
        value = _resolve(name, context)
        if value is None:
            return match.group(0) if strict else ''
        return str(value)

    return _PLACEHOLDER.sub(_sub, texte or '')


def rendre_modele(template, context=None, *, strict=False):
    """Rend un ``MessageTemplate`` : ``(sujet_rendu, corps_rendu)``."""
    return (rendre(template.sujet, context, strict=strict),
            rendre(template.corps, context, strict=strict))
