"""YJPB3 — « Quels problèmes les utilisateurs ont-ils rencontrés cette
semaine ? » en UNE commande.

Lecture seule : affiche le journal `reporting.ProblemeClient` (YJPB1) des N
derniers jours, regroupé par (genre, méthode, route, statut HTTP), du plus
fréquent au moins fréquent, avec le nombre d'utilisateurs DISTINCTS touchés.
Ne corrige RIEN, n'écrit RIEN.

Run (dans le conteneur django_core, ou avec les variables DB) :
  python manage.py problemes_utilisateurs                      # 7 j, toutes sociétés
  python manage.py problemes_utilisateurs --jours 1
  python manage.py problemes_utilisateurs --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError

from apps.reporting.journal_problemes import resume_problemes


class Command(BaseCommand):
    help = (
        "Liste les problèmes vécus par les utilisateurs (requêtes sans "
        "réponse, 5xx, erreurs JavaScript) des N derniers jours, regroupés "
        "par route, statut et code. Lecture seule."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--jours', type=int, default=7,
            help="Fenêtre en jours (défaut : 7).")
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société (défaut : toutes).")

    def handle(self, *args, **options):
        from authentication.models import Company

        jours = options['jours']
        if jours < 1:
            raise CommandError('--jours doit valoir au moins 1.')

        slug = options.get('company')
        company = None
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError(f"Aucune société avec le slug '{slug}'.")

        lignes = resume_problemes(jours=jours, company=company)
        portee = f"société {slug}" if slug else "toutes sociétés"
        self.stdout.write(
            f"Problèmes vécus par les utilisateurs — {jours} dernier(s) "
            f"jour(s), {portee}.")
        if not lignes:
            self.stdout.write(self.style.SUCCESS(
                'Aucun problème signalé sur la fenêtre.'))
            return

        self.stdout.write(
            f"{'occ':>5}  {'pers':>4}  {'statut':>6}  genre     "
            f"dernier cas       {'code':<22} route")
        for ligne in lignes:
            statut = ligne['statut_reponse']
            self.stdout.write(
                f"{ligne['occurrences']:>5}  {ligne['utilisateurs']:>4}  "
                f"{(statut if statut is not None else '-'):>6}  "
                f"{ligne['genre']:<9} "
                f"{ligne['dernier']:%Y-%m-%d %H:%M}  "
                f"{(ligne['code'] or '-'):<22} "
                f"{(ligne['methode'] + ' ' if ligne['methode'] else '')}"
                f"{ligne['route'] or '(écran)'}")
        total = sum(ligne['occurrences'] for ligne in lignes)
        self.stdout.write(self.style.WARNING(
            f"{total} occurrence(s) sur {len(lignes)} problème(s) distinct(s)."))
