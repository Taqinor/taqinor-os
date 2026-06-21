"""Audit de cohérence des données inter-modules (LECTURE SEULE).

Pourquoi : tous les liens inter-modules de l'ERP sont de vrais FK
(`db_constraint=True`), donc la base GARANTIT déjà que la ligne référencée existe
(pas d'orphelin possible). Ce qu'un FK ne garantit PAS : que la ligne référencée
soit dans la BONNE société. Un `Devis` (société A) peut pointer un `Client`
(société B) sans que la base s'y oppose. C'est la « fuite » inter-sociétés — la
donnée doit rester connectée DANS sa société.

Générique via le registre d'apps Django : couvre AUTOMATIQUEMENT tout modèle,
présent ou FUTUR, portant un FK `company`. Pour chaque FK d'un tel modèle vers un
autre modèle qui porte aussi `company`, on vérifie que les deux côtés partagent la
même société. Aucun import statique de modèle métier → aucun couplage, le scan
s'étend tout seul quand on ajoute une fonctionnalité.

Usage :
    python manage.py check_data_integrity            # rapport + exit 1 si fuite
    python manage.py check_data_integrity --quiet     # n'imprime que les anomalies
"""
import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import F, ForeignKey


def _has_company_fk(model):
    """Le modèle porte-t-il un FK `company` (scope multi-tenant) ?"""
    try:
        field = model._meta.get_field('company')
    except Exception:
        return False
    return isinstance(field, ForeignKey)


def cross_company_fk_pairs():
    """[(model, fk_name)] — FK reliant deux modèles porteurs de `company`.

    Introspection PURE (aucune requête) : testable sans base de données.
    """
    pairs = []
    for model in apps.get_models():
        if not _has_company_fk(model):
            continue
        for field in model._meta.get_fields():
            if not isinstance(field, ForeignKey) or field.name == 'company':
                continue
            target = field.related_model
            if target is not None and _has_company_fk(target):
                pairs.append((model, field.name))
    return pairs


def find_cross_company_leaks():
    """Retourne [(label, fk_name, count, sample_pks)] des liens inter-sociétés."""
    leaks = []
    for model, col in cross_company_fk_pairs():
        qs = (model.objects
              .filter(**{f'{col}__isnull': False})
              .exclude(**{f'{col}__company_id': F('company_id')}))
        count = qs.count()
        if count:
            sample = list(qs.values_list('pk', flat=True)[:5])
            leaks.append((model._meta.label, col, count, sample))
    return leaks


class Command(BaseCommand):
    help = ("Audit lecture seule de la cohérence inter-modules : détecte les "
            "liens FK pointant vers une AUTRE société (fuites multi-tenant).")

    def add_arguments(self, parser):
        parser.add_argument('--quiet', action='store_true',
                            help="N'imprime que les anomalies.")

    def handle(self, *args, **options):
        quiet = options['quiet']
        pairs = cross_company_fk_pairs()
        if not quiet:
            self.stdout.write(
                f"Audit cohérence inter-modules — {len(pairs)} lien(s) FK "
                f"inter-sociétés analysé(s)…")
        leaks = find_cross_company_leaks()
        if not leaks:
            self.stdout.write(self.style.SUCCESS(
                "OK — aucune fuite inter-sociétés détectée."))
            return
        for label, col, count, sample in leaks:
            self.stderr.write(self.style.ERROR(
                f"FUITE — {label}.{col} : {count} ligne(s) pointent vers une "
                f"AUTRE société (ex. pk={sample})."))
        # Exit non-zéro → utilisable comme garde-fou (CI release-verify / cron).
        sys.exit(1)
