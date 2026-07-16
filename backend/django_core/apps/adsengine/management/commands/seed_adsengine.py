"""ENG14 — Seed idempotent du moteur publicitaire.

Pose les valeurs par DÉFAUT non-« live » nécessaires au moteur :
  * une ``GuardrailConfig`` par défaut pour chaque société opérationnelle (jamais
    d'écrasement d'une config existante — additif seulement) ;
  * les templates de phrases FR du brief sont RÉSIDENTS DU CODE (``brief.py``,
    déterministe) — aucune donnée à seeder pour eux.

RIEN de « live » n'est créé (aucune ``MetaConnection``, aucun token, aucune
campagne). **Idempotent** : une double exécution laisse EXACTEMENT le même état
(``get_or_create`` ne touche jamais une ligne existante).

ENG16 étendra cette commande pour seeder aussi la ``CreativePolicy`` Taqinor par
défaut (même contrat idempotent).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Seed idempotent du moteur publicitaire "
            "(GuardrailConfig par défaut ; rien de 'live').")

    def handle(self, *args, **options):
        from authentication.selectors import active_companies

        guardrails_created = self._seed_guardrails(active_companies())

        self.stdout.write(self.style.SUCCESS(
            f"seed_adsengine : {guardrails_created} GuardrailConfig(s) "
            f"créée(s)."))
        return None

    def _seed_guardrails(self, companies):
        from apps.adsengine.models import GuardrailConfig

        created = 0
        for company in companies:
            _, was_created = GuardrailConfig.objects.get_or_create(
                company=company)
            if was_created:
                created += 1
        return created
