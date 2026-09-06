"""MRY0 (lot A) — État du webhook Meta « leadgen » en ligne de commande.

    python manage.py meta_webhook_status --company <slug-ou-id> [--subscribe]

Même logique que la tuile de l'écran Connexion (``webhook_leadgen``), pour le
runbook ``docs/crm/arrivee_leads.md`` et pour le serveur. Code retour 1 quand
le câblage n'est pas complet — utilisable dans un contrôle de déploiement.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.adsengine.webhook_leadgen import (
    abonner_page_leadgen, etat_webhook_leadgen)


class Command(BaseCommand):
    help = ("État du webhook Meta « leadgen » (app souscrite, Page abonnée, "
            "dernier lead reçu en temps réel).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Slug ou id de la société (défaut : toutes les sociétés '
                 'ayant une connexion Meta).')
        parser.add_argument(
            '--subscribe', action='store_true',
            help="Abonne la Page au champ leadgen quand elle ne l'est pas.")

    def _companies(self, raw):
        from apps.adsengine.models import MetaConnection
        from authentication.models import Company

        if raw is None:
            return [c.company for c in MetaConnection.objects.select_related(
                'company').all()]
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        if company is None:
            raise CommandError(
                f'Société introuvable : {raw!r} (slug ou id attendu).')
        return [company]

    def handle(self, *args, **options):
        companies = self._companies(options.get('company'))
        if not companies:
            self.stdout.write(self.style.WARNING(
                'Aucune connexion Meta enregistrée — rien à vérifier.'))
            return
        tout_ok = True
        for company in companies:
            etat = etat_webhook_leadgen(company)
            if options.get('subscribe') and not etat.get('page_subscribed'):
                resultat = abonner_page_leadgen(company)
                self.stdout.write(
                    ('Abonnement de la Page : ' + str(resultat.get('detail'))))
                if resultat.get('ok'):
                    etat = etat_webhook_leadgen(company)
            self._afficher(company, etat)
            tout_ok = tout_ok and bool(etat.get('ok'))
        if not tout_ok:
            # Code retour 1 pour le runbook / le contrôle de déploiement.
            raise SystemExit(1)

    def _afficher(self, company, etat):
        style = self.style.SUCCESS if etat.get('ok') else self.style.WARNING
        self.stdout.write(style(
            f'[{company.slug}] webhook leadgen : '
            f'{"OK" if etat.get("ok") else "À RÉPARER"}'))
        self.stdout.write(f'  app souscrite      : {etat.get("app_subscribed")}')
        self.stdout.write(f'  Page abonnée       : {etat.get("page_subscribed")}')
        self.stdout.write(
            '  pages_manage_metadata : '
            f'{etat.get("has_pages_manage_metadata")}')
        self.stdout.write(
            f'  dernier POST webhook : {etat.get("dernier_post_webhook")}')
        if etat.get('erreur'):
            self.stdout.write(self.style.WARNING(
                f'  erreur Meta        : {etat["erreur"]}'))
        self.stdout.write(f'  → {etat.get("detail")}')
