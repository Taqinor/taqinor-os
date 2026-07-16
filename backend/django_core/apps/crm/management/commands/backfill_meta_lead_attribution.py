"""ADSENG1 — Backfill idempotent de l'attribution par variante des leads Lead
Ads existants (créés avant la capture de ad_id/adgroup_id/form_id).

Récupère les identifiants Meta natifs de chaque lead ``meta_lead_ads`` dont
``meta_ad_id`` est vide, résout les noms via les miroirs adsengine, et remplit
``utm_content = ad-<ad_id>`` + ``utm_campaign``. Idempotent : un lead déjà
backfillé est sauté ; une seconde exécution ne change rien.

Le token vient de ``--access-token`` ou du réglage ``META_LEAD_ADS_ACCESS_TOKEN``
(jamais d'un corps de requête). Sans token, la commande n'appelle rien et sort
proprement (aucune écriture).
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("ADSENG1 — Backfill idempotent de l'attribution par variante des "
            "leads Meta Lead Ads existants (ad_id + noms résolus + utm_*).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Limiter à une société (défaut : toutes).')
        parser.add_argument(
            '--access-token', default='',
            help='Token de page Meta (défaut : réglage '
                 'META_LEAD_ADS_ACCESS_TOKEN).')
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Nombre maximum de leads à traiter (défaut : tous).')

    def handle(self, *args, **options):
        from apps.crm.services import backfill_meta_lead_attribution

        access_token = (
            options.get('access_token')
            or getattr(settings, 'META_LEAD_ADS_ACCESS_TOKEN', '')
            or '')
        if not access_token:
            self.stdout.write(self.style.WARNING(
                'Aucun token Meta (META_LEAD_ADS_ACCESS_TOKEN) — rien à faire.'))
            return None

        company = None
        company_id = options.get('company_id')
        if company_id:
            from authentication.models import Company
            company = Company.objects.filter(pk=company_id).first()
            if company is None:
                self.stdout.write(self.style.ERROR(
                    f'Société #{company_id} introuvable.'))
                return None

        stats = backfill_meta_lead_attribution(
            company=company, access_token=access_token,
            limit=options.get('limit'))
        self.stdout.write(self.style.SUCCESS(
            f"backfill_meta_lead_attribution : {stats['scanned']} scanné(s), "
            f"{stats['updated']} mis à jour, {stats['skipped']} sauté(s), "
            f"{stats['failed']} en échec."))
        return None
