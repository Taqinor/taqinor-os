"""GED22 — Liste les documents ÉCHUS au regard de leur politique de rétention.

Pour chaque société (ou une seule via ``--company``), résout la politique de
rétention ACTIVE la plus spécifique applicable à chaque document et affiche ceux
dont l'âge (depuis la date de création) dépasse la durée de conservation.

Usage :

    python manage.py lister_documents_echus [--company <slug-ou-id>] [--today YYYY-MM-DD]

Conception :

  * STRICTEMENT consultatif (lecture seule). La rétention est un SIGNAL : cette
    commande ne SUPPRIME, n'ARCHIVE ni ne modifie JAMAIS aucun document — même
    pour une politique d'action « supprimer » (qui reste une décision séparée,
    explicite et manuelle). Jamais destructif par défaut.

  * Multi-tenant. Chaque document est évalué dans SA société, contre les
    politiques de SA société (jamais cross-société). ``--company`` borne le
    traitement à une seule société.

  * ``--today`` (date ISO) permet de simuler une date de référence pour le
    calcul d'âge (utile en test / planification). Par défaut : la date du jour.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.ged import selectors


class Command(BaseCommand):
    help = (
        "Liste (sans rien modifier) les documents GED échus au regard de leur "
        "politique de rétention applicable."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Limite à une société (slug ou id).')
        parser.add_argument(
            '--today', dest='today', default=None,
            help="Date de référence ISO (YYYY-MM-DD) pour le calcul d'âge.")

    def handle(self, *args, **options):
        from authentication.models import Company

        today = None
        if options.get('today'):
            try:
                today = datetime.date.fromisoformat(options['today'])
            except ValueError as exc:
                raise CommandError(f"--today invalide : {exc}")

        companies = Company.objects.all()
        ident = options.get('company')
        if ident:
            if str(ident).isdigit():
                companies = companies.filter(pk=int(ident))
            else:
                companies = companies.filter(slug=ident)
            if not companies.exists():
                raise CommandError(f"Société introuvable : {ident}")

        total = 0
        for company in companies:
            echus = selectors.documents_echus(company, today=today)
            if not echus:
                continue
            self.stdout.write(self.style.WARNING(
                f"\n{company.nom} — {len(echus)} document(s) échu(s) :"))
            for document, politique, depasses in echus:
                total += 1
                self.stdout.write(
                    f"  · #{document.id} « {document.nom} » — "
                    f"politique « {politique.nom} » "
                    f"({politique.duree_conservation_jours} j, "
                    f"action={politique.action_echeance}) — "
                    f"dépassé de {depasses} j")

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "Aucun document échu (rien à signaler)."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nTotal : {total} document(s) échu(s) — "
                f"SIGNALÉS uniquement, aucun n'a été modifié ni supprimé."))
