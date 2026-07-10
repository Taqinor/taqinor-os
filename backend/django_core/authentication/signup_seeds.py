"""SCA20 — Hooks de seed « à la création d'une société » côté authentication.

Migre les seeds INLINE historiques de ``RegisterCompanyView`` (types d'activité
Odoo + niveaux de relance) en hooks idempotents enregistrés dans
``core.signup_hooks``. Le comportement du signup est PRÉSERVÉ à l'identique : les
mêmes lignes sont créées, avec ``get_or_create`` (rejouable sans doublon).

Les rôles système et le ``CompanyProfile`` restent posés INLINE dans la vue car
elle en a besoin pour créer l'administrateur (``admin_role``) — ils sont
néanmoins ré-appliqués idempotemment par ``seed_company`` via ces mêmes hooks au
besoin (voir la commande). Ici on migre les seeds « satellites » sans valeur de
retour consommée par la vue.
"""
from __future__ import annotations


def seed_activity_types(company, *, user=None):
    """Types d'activité par défaut (style Odoo) — idempotent, additif."""
    from apps.records.models import ActivityType
    for nom, icone, ordre, delai in [
        ('Appel', '📞', 10, 0), ('Email', '✉️', 20, 0),
        ('Réunion', '👥', 30, 0), ('Relance', '📅', 40, 3),
        ('À faire', '✔️', 50, 0),
    ]:
        ActivityType.objects.get_or_create(
            company=company, nom=nom,
            defaults={'icone': icone, 'ordre': ordre,
                      'delai_defaut_jours': delai, 'est_systeme': True})


def seed_followup_levels(company, *, user=None):
    """Niveaux de relance par défaut (J+7 / J+15 / J+30) — idempotent."""
    from apps.ventes.models import FollowupLevel
    for ordre, nom, delai in [
        (1, 'Rappel courtois', 7), (2, 'Relance', 15),
        (3, 'Relance ferme', 30),
    ]:
        FollowupLevel.objects.get_or_create(
            company=company, ordre=ordre,
            defaults={'nom': nom, 'delai_jours': delai})


def register_authentication_signup_hooks():
    """Branche les hooks de seed satellites au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook('activity_types', seed_activity_types, priority=20)
    register_signup_hook('followup_levels', seed_followup_levels, priority=20)
