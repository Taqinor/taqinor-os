"""SCA21 — ``manage.py close_company <slug>`` : fermeture & purge d'un tenant.

Deux modes, DRY-RUN par défaut (rien de destructif sans flag explicite) :

* ``--soft-close`` : passe la société en FERMETURE (accès bloqué via SCA18,
  données intactes, délai de grâce de 30 j). Réversible (``--rouvrir``).
* ``--purge`` : purge RÉELLE (destructive). Exige TOUTES ces conditions :
    - la société est déjà en fermeture ;
    - le délai de grâce (30 j) est écoulé ;
    - un artefact d'export/backup terminé existe (sauvegarde préalable) ;
    - la double confirmation explicite ``--yes-je-confirme``.
  Sans ``--yes-je-confirme`` c'est un DRY-RUN : la commande explique seulement
  ce qui serait fait, et vérifie les préconditions SANS rien supprimer.

Journalisation complète (audit) à chaque action. Destructif PRÉ-APPROUVÉ mais
tracé (cf. NOTE DONE LOG).
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Fermeture (soft-close) puis purge gâchée d'un tenant. Dry-run par "
            "défaut ; purge derrière --yes-je-confirme + backup préalable.")

    def add_arguments(self, parser):
        parser.add_argument('slug', help='Slug de la société cible.')
        parser.add_argument(
            '--soft-close', action='store_true',
            help='Passe la société en fermeture (accès bloqué, données '
                 'intactes, délai de grâce).')
        parser.add_argument(
            '--rouvrir', action='store_true',
            help='Annule la fermeture (réactive la société).')
        parser.add_argument(
            '--purge', action='store_true',
            help='Purge RÉELLE (destructive). Dry-run sans --yes-je-confirme.')
        parser.add_argument(
            '--yes-je-confirme', action='store_true',
            dest='confirme',
            help='Confirmation explicite EXIGÉE pour exécuter réellement la '
                 'purge (sinon dry-run).')

    def handle(self, *args, **options):
        from authentication.models import Company
        from authentication import services

        slug = options['slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Aucune société avec le slug « {slug} ».")

        if options['rouvrir']:
            services.rouvrir(company)
            self.stdout.write(self.style.SUCCESS(
                f"Société « {company.nom} » réactivée (fermeture annulée)."))
            return

        if options['soft_close']:
            services.mettre_en_fermeture(company)
            self.stdout.write(self.style.SUCCESS(
                f"Société « {company.nom} » passée en fermeture. Accès bloqué, "
                f"données intactes, délai de grâce de "
                f"{services.GRACE_PERIOD_DAYS} j démarré."))
            return

        if options['purge']:
            # Toujours vérifier les préconditions AVANT de rien détruire.
            try:
                services.verifier_purge_possible(company)
            except services.PurgeRefusee as exc:
                raise CommandError(f"Purge refusée : {exc}")

            if not options['confirme']:
                # DRY-RUN : préconditions OK mais pas de confirmation → on
                # explique seulement, aucune suppression.
                self.stdout.write(self.style.WARNING(
                    f"[DRY-RUN] Purge possible pour « {company.nom} » "
                    f"(#{company.id}). Préconditions satisfaites (fermeture + "
                    f"délai de grâce + backup vérifié). Relancez avec "
                    f"--yes-je-confirme pour PURGER RÉELLEMENT."))
                return

            resultat = services.purger_tenant(company)
            self.stdout.write(self.style.SUCCESS(
                f"Tenant #{resultat['company_id']} PURGÉ. DSR: {resultat['dsr']}"))
            return

        raise CommandError(
            "Aucune action : précisez --soft-close, --rouvrir ou --purge.")
