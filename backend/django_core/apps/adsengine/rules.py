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


# Registre HISTORIQUE ADSENG4 (clé stable → métadonnées FR). ⚠ Ce n'est PLUS le
# catalogue affiché : le catalogue RÉEL (celui que ``/regles/catalogue/`` rend et
# que le fondateur arme) vit dans ``rule_templates.RULE_TEMPLATES`` (ADSENG14 +
# ADSDEEP38). Ce registre-ci ne survit que pour les clés HISTORIQUES encore
# portées par des lignes en base (``cost_per_signature_ceiling``,
# ``zero_results``) et par le seed ADSENG4 — il n'est JAMAIS la liste de choix.
# Voir ``rule_template_choices()`` : les choix du modèle sont DÉRIVÉS des deux
# registres, jamais recopiés à la main (une divergence a rendu 400 tout
# armement d'un gabarit du catalogue réel).
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
    """Paires (clé, libellé FR) prêtes pour ``choices=`` (ordre stable).

    **DÉRIVÉES, jamais recopiées.** La liste est calculée à partir des registres
    vivants, dans cet ordre :

    1. ``rule_templates.RULE_TEMPLATES`` — le catalogue FIXE réel (ADSENG14 +
       ADSDEEP38), celui que ``GET /regles/catalogue/`` rend et dans lequel le
       fondateur choisit ; son ``label_fr`` gagne pour les clés partagées ;
    2. les clés HISTORIQUES d'ADSENG4 (ci-dessus) absentes du catalogue, pour ne
       jamais invalider une ``RulePolicy`` déjà en base.

    C'est le correctif de fond d'une divergence RÉELLE : les deux registres
    avaient été recopiés à la main, si bien qu'armer ``stop_loss_cpl`` — le
    PREMIER gabarit du catalogue affiché — partait en 400 « n'est pas un choix
    valide ». Ajouter un gabarit au catalogue le rend désormais armable
    AUTOMATIQUEMENT : la divergence est structurellement impossible.

    Import DIFFÉRÉ de ``rule_templates`` (qui importe ce module pour les
    constantes de sévérité) : appelée à la demande par Django (``choices`` est
    passé en CALLABLE au champ), donc jamais pendant l'import de ce module — le
    cycle ``rules`` ↔ ``rule_templates`` ne peut pas se produire.
    """
    from .rule_templates import RULE_TEMPLATES as CATALOGUE

    choices = [(key, tpl['label_fr']) for key, tpl in CATALOGUE.items()]
    connues = {key for key, _ in choices}
    choices.extend(
        (key, tpl['label_fr']) for key, tpl in RULE_TEMPLATES.items()
        if key not in connues)
    return choices


def default_cooldown_hours(severity):
    """Cooldown par défaut pour une sévérité (repli WARNING si inconnue)."""
    return DEFAULT_COOLDOWN_HOURS.get(severity, DEFAULT_COOLDOWN_HOURS[
        SEVERITY_WARNING])
