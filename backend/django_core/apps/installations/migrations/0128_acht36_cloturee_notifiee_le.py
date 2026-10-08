# ACHT36 — `cloturee_notifiee_le` : instant de la première clôture notifiée
# d'une intervention (garde de l'événement `intervention_completed`). Additive,
# nullable, revertable. Rempli pour les interventions DÉJÀ terminées/validées
# (à leur date de réalisation, sinon à l'instant de la migration) afin qu'un
# recul puis une re-clôture ne rejoue pas l'événement.

from django.db import migrations, models
from django.db.models import DateTimeField
from django.db.models.functions import Cast, Now


def remplir_deja_terminees(apps, schema_editor):
    Intervention = apps.get_model('installations', 'Intervention')
    terminees = Intervention.objects.filter(
        statut__in=['terminee', 'validee'], cloturee_notifiee_le__isnull=True)
    terminees.filter(date_realisee__isnull=False).update(
        cloturee_notifiee_le=Cast('date_realisee', DateTimeField()))
    terminees.filter(date_realisee__isnull=True).update(
        cloturee_notifiee_le=Now())


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0127_acht32_consommationligne_date_modification'),
    ]

    operations = [
        migrations.AddField(
            model_name='intervention',
            name='cloturee_notifiee_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(remplir_deja_terminees, migrations.RunPython.noop),
    ]
