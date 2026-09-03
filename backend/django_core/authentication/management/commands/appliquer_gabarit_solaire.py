"""SOL10 — `manage.py appliquer_gabarit_solaire <slug>` : met un tenant en
forme solaire (idempotent, sortie en français).

Compose l'existant : modules rares éteints (SOL8), plan de licence « Solaire »
(SOL9), rôles types, STRUCTURE de catalogue solaire, cartes de tableau de bord
solaires. Aucun modèle nouveau, aucune donnée inventée.

`--avec-catalogue` ajoute le catalogue PRODUIT du dépôt — prix RÉELS en MAD,
donc réservé à un tenant MAROCAIN. Hors Maroc le drapeau est ignoré : il
n'existe aucune source de prix EUR, et un prix converti serait un chiffre
inventé (règle checked-facts).
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("Met une société en forme SOLAIRE (modules rares éteints, plan "
            "Solaire, rôles types, structure de catalogue, dashboard). "
            "Idempotent.")

    def add_arguments(self, parser):
        parser.add_argument('slug', help="Slug de la société à mettre en forme.")
        parser.add_argument(
            '--avec-catalogue', action='store_true',
            help="Seede AUSSI le catalogue produit (prix réels en MAD) — "
                 "ignoré si le tenant n'est pas marocain.")

    def handle(self, *args, **options):
        from authentication.models import Company
        from authentication.tenant_templates import appliquer_gabarit_solaire

        slug = options['slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Aucune société avec le slug « {slug} ».")

        rapport = appliquer_gabarit_solaire(
            company, avec_catalogue_produits=options['avec_catalogue'])

        self.stdout.write(
            f"Société « {company.nom} » ({company.slug}), pays "
            f"{rapport.get('pays') or '?'}")
        self.stdout.write(
            f"  Modules éteints à la création : "
            f"{', '.join(rapport.get('modules_eteints') or []) or 'aucun (déjà posés)'}")
        self.stdout.write(f"  Plan de licence assigné : {rapport.get('plan')}")
        roles = rapport.get('roles') or []
        self.stdout.write(f"  Rôles types : {len(roles)} ({', '.join(roles)})")
        catalogue = rapport.get('catalogue') or {}
        if isinstance(catalogue, dict):
            crees = catalogue.get('categories') or []
            self.stdout.write(
                f"  Catégories de catalogue créées : {len(crees)}")
            self.stdout.write(
                "  Catalogue produit : "
                + ("seedé (prix réels MAD)" if catalogue.get('produits')
                   else "NON seedé — structure seule "
                        "(aucun prix inventé hors Maroc)"))
        else:
            self.stdout.write(f"  Catalogue : {catalogue}")
        self.stdout.write(
            f"  Tableau de bord solaire posé pour : "
            f"{', '.join(rapport.get('dashboard') or []) or 'aucun (déjà posé)'}")
        self.stdout.write(self.style.SUCCESS('Gabarit solaire appliqué.'))
