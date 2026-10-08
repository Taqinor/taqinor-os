# ACHT4 (C-ACHT-004) — un seul chantier par devis : contrainte unique
# partielle (company, devis) quand devis est renseigné. Additive et
# revertable. Un doublon existant fait échouer la migration LISIBLEMENT
# (liste des devis concernés) avant toute écriture — jamais de correction
# silencieuse des données.

from django.db import migrations, models
from django.db.models import Count


def refuser_si_doublons(apps, schema_editor):
    Installation = apps.get_model('installations', 'Installation')
    doublons = list(
        Installation.objects.filter(devis__isnull=False)
        .values('company_id', 'devis_id')
        .annotate(n=Count('id')).filter(n__gt=1)
        .values_list('company_id', 'devis_id', 'n'))
    if doublons:
        detail = ', '.join(
            f'société {c} / devis {d} ({n} chantiers)'
            for c, d, n in doublons[:20])
        raise RuntimeError(
            'ACHT4 — plusieurs chantiers portent le même devis ; '
            'fusionnez-les avant la migration : ' + detail)


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0124_astk57_serie_retourne'),
    ]

    operations = [
        migrations.RunPython(refuser_si_doublons, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='installation',
            constraint=models.UniqueConstraint(
                condition=models.Q(('devis__isnull', False)),
                fields=('company', 'devis'),
                name='installation_unique_devis_par_societe'),
        ),
    ]
