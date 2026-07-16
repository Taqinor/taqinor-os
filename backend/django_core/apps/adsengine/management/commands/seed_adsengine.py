"""ENG14 — Seed idempotent du moteur publicitaire.

Pose les valeurs par DÉFAUT non-« live » nécessaires au moteur :
  * une ``GuardrailConfig`` par défaut pour chaque société opérationnelle (jamais
    d'écrasement d'une config existante — additif seulement) ;
  * la ``CreativePolicy`` par défaut (ENG16 : jamais de faux chantiers/clients/
    témoignages ni de chiffre non vérifié ; explainers/B-roll/rendus OK) ;
  * les templates de phrases FR du brief sont RÉSIDENTS DU CODE (``brief.py``,
    déterministe) — aucune donnée à seeder pour eux.

RIEN de « live » n'est créé (aucune ``MetaConnection``, aucun token, aucune
campagne). **Idempotent** : une double exécution laisse EXACTEMENT le même état
(``get_or_create`` ne touche jamais une ligne existante).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Seed idempotent du moteur publicitaire "
            "(GuardrailConfig + CreativePolicy par défaut ; rien de 'live').")

    def handle(self, *args, **options):
        from authentication.selectors import active_companies

        guardrails_created = self._seed_guardrails(active_companies())
        policies_created = self._seed_policies(active_companies())
        rules_created = self._seed_rule_policies(active_companies())

        self.stdout.write(self.style.SUCCESS(
            f"seed_adsengine : {guardrails_created} GuardrailConfig(s), "
            f"{policies_created} CreativePolicy(s), "
            f"{rules_created} RulePolicy(s) créée(s)."))
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

    def _seed_policies(self, companies):
        from apps.adsengine.policy import ensure_default_policy

        created = 0
        for company in companies:
            _, was_created = ensure_default_policy(company)
            if was_created:
                created += 1
        return created

    def _seed_rule_policies(self, companies):
        """ADSENG4 — Seed une ``RulePolicy`` par template du catalogue, PAR
        société, en DÉFAUT SÛR : ``enabled=False`` + ``dry_run=True`` (rien ne
        se déclenche tant que le fondateur n'a pas opté). Idempotent : jamais
        d'écrasement d'une règle existante (``get_or_create`` sur
        ``(company, template_key)``)."""
        from apps.adsengine.models import RulePolicy
        from apps.adsengine.rules import RULE_TEMPLATES

        created = 0
        for company in companies:
            for template_key in RULE_TEMPLATES:
                _, was_created = RulePolicy.objects.get_or_create(
                    company=company, template_key=template_key,
                    defaults={'enabled': False, 'dry_run': True})
                if was_created:
                    created += 1
        return created
