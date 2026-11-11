"""NTPLT32 — (re)construit ``search_vector`` des entités de la recherche globale.

Remplissage initial après la migration (les lignes existantes naissent à
``NULL`` : la recherche leur applique alors ``icontains``), puis rattrapage à la
demande. Par LOTS sur la clé primaire (curseur keyset, jamais d'OFFSET) : un lot
= un ``UPDATE`` ensembliste borné, la table n'est jamais verrouillée longtemps.
Idempotent. Mêmes expressions que le signal (``core.recherche_fts.indexer``).

    python manage.py rebuild_search_index                 # toutes les entités
    python manage.py rebuild_search_index --app crm       # Lead + Client
    python manage.py rebuild_search_index --vides         # lignes NULL seulement
"""
import time

from django.core.management.base import BaseCommand, CommandError

from core import recherche_fts


class Command(BaseCommand):
    help = ('Recalcule les colonnes plein-texte (search_vector) de la recherche '
            'globale, par lots.')

    def add_arguments(self, parser):
        parser.add_argument('--app', help="Limiter à une app (ex. crm, sav).")
        parser.add_argument('--lot', type=int, default=1000,
                            help='Taille de lot (défaut 1000).')
        parser.add_argument('--pause-ms', type=int, default=50,
                            help='Pause entre deux lots (défaut 50 ms).')
        parser.add_argument('--vides', action='store_true',
                            help='Seulement les lignes jamais indexées (NULL).')

    def handle(self, *args, **options):
        lot = options['lot']
        if lot < 1:
            raise CommandError('--lot doit être un entier strictement positif.')
        modeles = recherche_fts.modeles(options.get('app'))
        if not modeles:
            raise CommandError(
                f"Aucune entité plein-texte pour l'app « {options.get('app')} ».")
        total = 0
        for modele in modeles:
            n = self._reconstruire(modele, lot, options['pause_ms'],
                                   options['vides'])
            total += n
            self.stdout.write(f'{modele._meta.label} : {n} ligne(s) indexée(s)')
        self.stdout.write(self.style.SUCCESS(f'Total : {total} ligne(s).'))

    @staticmethod
    def _reconstruire(modele, lot, pause_ms, vides):
        qs = modele._base_manager.order_by('pk')
        if vides:
            qs = qs.filter(search_vector__isnull=True)
        dernier, total = None, 0
        while True:
            tranche = qs if dernier is None else qs.filter(pk__gt=dernier)
            pks = list(tranche.values_list('pk', flat=True)[:lot])
            if not pks:
                return total
            total += recherche_fts.indexer(modele, pks)
            dernier = pks[-1]
            if len(pks) < lot:
                return total
            if pause_ms:
                time.sleep(pause_ms / 1000.0)
