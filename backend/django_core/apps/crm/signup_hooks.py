"""CAD125 — hook de seed « à la création d'une société » côté CRM.

Les deux playbooks de SEGMENT (dossier d'autoproduction 82-21 pour
l'industriel/commercial, dossier de subvention agricole FDA) n'ont de valeur
que s'ils EXISTENT pour la société : un playbook qu'aucun code ne pose est
exactement le défaut que l'audit du 21/09/2026 a relevé sur ``reveil_b`` — un
contenu écrit, validé, et branché à rien.

Même patron que ``apps/parametres/signup_hooks.py`` et
``authentication/signup_seeds.py`` : idempotent (``get_or_create``), additif,
rejouable sans doublon, et jamais bloquant pour la création de la société
(``core.signup_hooks`` isole chaque hook).
"""
from __future__ import annotations


def seed_playbooks_segment_hook(company, *, user=None):
    """Pose les playbooks de segment de CAD125 — idempotent."""
    from .services import seed_playbooks_segment
    seed_playbooks_segment(company)


def register_crm_signup_hooks():
    """Branche le hook de seed au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook(
        'playbooks_segment', seed_playbooks_segment_hook, priority=30)
