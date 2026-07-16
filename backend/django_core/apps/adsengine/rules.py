"""ADSENG4 — Catalogue de RÈGLES (templates) + barème de sévérité (gardien).

Source de vérité, style ``STAGES.py`` : les ``RulePolicy`` ne portent QUE des
paramètres ; la logique (condition, sévérité, action par défaut) vit ICI, dans
un registre code (jamais dupliqué en base). Module PLAIN — aucun import de
modèle (évite tout cycle : ``models`` importe ce module, jamais l'inverse).

Sévérité (dd-guardian, table A6) :
  * 🔴 CRITICAL — Urgent  — cooldown 6 h  (dépense sans résultat, plafond franchi)
  * 🟠 WARNING  — Attention — cooldown 24 h (délivre mais ne convertit rien)
  * 🔵 INFO     — Info     — cooldown 72 h

Escalade : une alerte WARNING non résolue sur ``ESCALATION_THRESHOLD`` (3)
cycles consécutifs monte en CRITICAL (leçon Madgicx : jamais un signal ignoré).
"""
from __future__ import annotations

# Valeurs de sévérité — IDENTIQUES à ``EngineAlert.Severity`` (jamais un import
# croisé models ↔ rules : ce sont des littéraux partagés).
SEVERITY_CRITICAL = 'critical'
SEVERITY_WARNING = 'warning'
SEVERITY_INFO = 'info'

SEVERITY_LABELS_FR = {
    SEVERITY_CRITICAL: 'Urgent',
    SEVERITY_WARNING: 'Attention',
    SEVERITY_INFO: 'Info',
}

# Emoji du canal WhatsApp (rendu seulement — jamais dans un getByRole côté front).
SEVERITY_EMOJI = {
    SEVERITY_CRITICAL: '🔴',
    SEVERITY_WARNING: '🟠',
    SEVERITY_INFO: '🔵',
}

# Fenêtre de dédup par défaut, PAR sévérité (heures).
DEFAULT_COOLDOWN_HOURS = {
    SEVERITY_CRITICAL: 6,
    SEVERITY_WARNING: 24,
    SEVERITY_INFO: 72,
}

# Nombre de cycles NON RÉSOLUS après lequel une WARNING monte en CRITICAL.
ESCALATION_THRESHOLD = 3


# Catalogue des templates de règles (clé stable → métadonnées FR). Les params
# éditables sont whitelistés par template (jamais arbitraires).
RULE_TEMPLATES = {
    'cost_per_signature_ceiling': {
        'label_fr': 'Plafond coût par signature',
        'severity': SEVERITY_CRITICAL,
        'default_action': 'pause',
        'editable_params': ['threshold_mad', 'window_days', 'min_samples'],
    },
    'zero_delivery': {
        'label_fr': 'Zéro delivery (dépense sans impression)',
        'severity': SEVERITY_CRITICAL,
        'default_action': 'pause',
        'editable_params': ['hours', 'min_spend_mad'],
    },
    'zero_results': {
        'label_fr': 'Zéro résultat (délivre sans convertir)',
        'severity': SEVERITY_WARNING,
        'default_action': 'propose',
        'editable_params': ['hours', 'min_spend_mad'],
    },
    'frequency_high': {
        'label_fr': 'Fréquence élevée (fatigue créative)',
        'severity': SEVERITY_WARNING,
        'default_action': 'propose',
        'editable_params': ['frequency_max', 'window_days'],
    },
    'budget_pacing_breach': {
        'label_fr': "Franchissement d'enveloppe budgétaire",
        'severity': SEVERITY_CRITICAL,
        'default_action': 'pause',
        'editable_params': ['ceiling_mad'],
    },
}


def rule_template_choices():
    """Paires (clé, libellé FR) prêtes pour ``choices=`` (ordre stable)."""
    return [(key, RULE_TEMPLATES[key]['label_fr']) for key in RULE_TEMPLATES]


def default_cooldown_hours(severity):
    """Cooldown par défaut pour une sévérité (repli WARNING si inconnue)."""
    return DEFAULT_COOLDOWN_HOURS.get(severity, DEFAULT_COOLDOWN_HOURS[
        SEVERITY_WARNING])


# Choix pré-calculé (évite de rappeler la fonction dans plusieurs migrations).
RULE_TEMPLATE_CHOICES = rule_template_choices()
