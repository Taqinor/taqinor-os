"""ADSENG-ODOO — Diagnostic LECTURE SEULE du connecteur Odoo.

    python manage.py odoo_pull --company <slug-ou-id> [--since YYYY-MM-DD]

Vérifie la connexion après que le fondateur a posé les 4 variables ODOO_* :
imprime « configuré ? / authentifié ? / N leads / N signés / dépense Meta /
coût-par-signature ». **N'ÉCRIT RIEN** — ni dans Odoo (connecteur lecture seule)
ni dans la base ERP. Sans configuration, sort proprement en rappelant les
variables à poser.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Diagnostic LECTURE SEULE du connecteur Odoo (configuré ? "
            "authentifié ? N leads / N signés / dépense / coût-par-signature).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société ERP propriétaire du connecteur "
                 "(ODOO_COMPANY_ID) — OBLIGATOIRE (ASEC40).")
        parser.add_argument(
            '--since', dest='since', default=None,
            help="Borne la lecture (YYYY-MM-DD) sur la date de création / "
                 "commande.")

    def _resolve_company(self, raw):
        from authentication.models import Company
        if raw is not None:
            company = Company.objects.filter(slug=raw).first()
            if company is None and str(raw).isdigit():
                company = Company.objects.filter(pk=int(raw)).first()
            return company
        # ASEC40 — plus de repli « première société » : la société est
        # explicite et doit être la propriétaire du connecteur.
        return None

    def handle(self, *args, **options):
        from apps.adsengine import odoo_client, odoo_selectors

        # ASEC40 — société EXPLICITE, propriétaire du connecteur.
        company = self._resolve_company(options.get('company'))
        if company is None:
            raise CommandError(
                "Société requise : passez --company <slug|id> (la société "
                "ERP propriétaire du connecteur, ODOO_COMPANY_ID).")

        configured = odoo_client.is_configured(company)
        self.stdout.write(f"Configuré ?      {'oui' if configured else 'non'}")
        if not configured:
            self.stdout.write(self.style.WARNING(
                "Connecteur Odoo non configuré pour cette société — posez ces "
                "5 variables d'environnement :\n"
                "  ODOO_URL        (ex. https://taqinor-solutions.odoo.com)\n"
                "  ODOO_DB         (ex. taqinor-solutions)\n"
                "  ODOO_USERNAME   (le login utilisateur)\n"
                "  ODOO_API_KEY    (la clé d'API Odoo)\n"
                "  ODOO_COMPANY_ID (id de la société ERP propriétaire)\n"
                "Rien n'a été lu (no-op propre)."))
            return

        client = odoo_client.OdooClient.from_env(company=company)
        since = options.get('since')
        try:
            uid = client.authenticate()
            self.stdout.write(f"Authentifié ?    oui (uid={uid})")
        except odoo_client.OdooError as exc:
            self.stdout.write(self.style.ERROR(f"Authentifié ?    NON — {exc}"))
            return

        try:
            leads = client.read_leads(since)
            deals = odoo_selectors.signed_deals(since=since, client=client)
            stage_counts = odoo_selectors.lead_stage_counts(client=client)
        except odoo_client.OdooError as exc:
            self.stdout.write(self.style.ERROR(f"Lecture Odoo échouée — {exc}"))
            return

        self.stdout.write(f"Leads Odoo :     {len(leads)}")
        self.stdout.write(f"Signés (deals) : {len(deals)}")
        if stage_counts:
            self.stdout.write("Répartition par étape :")
            for label, count in sorted(stage_counts.items()):
                self.stdout.write(f"  - {label} : {count}")

        from apps.adsengine.odoo_metrics import odoo_cost_per_signature
        result = odoo_cost_per_signature(company, since=since, client=client)
        self.stdout.write(
            f"Dépense Meta :   {result['total_spend']} MAD "
            f"(société « {getattr(company, 'nom', company.pk)} »)")
        cost = result['cost_per_signature']
        self.stdout.write(
            f"Coût/signature : {cost if cost else 'N/A (0 signature)'}")
        attr = result['attribution']
        self.stdout.write(
            f"Attribution :    {attr['attributed']} attribué(s) / "
            f"{attr['unattributed']} non attribué(s) par campagne.")
        self.stdout.write(self.style.SUCCESS(
            "Diagnostic terminé (aucune écriture — lecture seule)."))
