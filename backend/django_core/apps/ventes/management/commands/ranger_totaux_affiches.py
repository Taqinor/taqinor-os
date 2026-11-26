"""ADEV162 — range tout de suite le total affiché des devis en jeu (le même
écrivain que le balayage planifié toutes les 10 min) : à lancer après un
déploiement pour que l'en-tête de la liste soit rapide sans attendre.

Idempotent (un devis dont l'empreinte concorde n'est pas recalculé) ; n'écrit
que les deux colonnes de cache ``total_affiche_range`` /
``total_affiche_empreinte`` — ni statut, ni ``updated_at``, ni rien qu'un client
ou un PDF lit. La synthèse reste juste SANS cette commande (elle recalcule).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Range le total affiché des devis en jeu (cache de l'en-tête de la liste)."

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None,
                            help="Limiter à une société (id).")

    def handle(self, *args, **options):
        from apps.ventes.domain.etudes import ranger_totaux_affiches
        from apps.ventes.models import Devis
        qs = Devis.objects.filter(is_active=True)
        if options['company']:
            qs = qs.filter(company_id=options['company'])
        ranges = ranger_totaux_affiches(qs)
        self.stdout.write('%d devis rangé(s).' % ranges)
