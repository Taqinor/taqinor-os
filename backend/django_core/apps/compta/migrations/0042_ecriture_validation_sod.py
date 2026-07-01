# COMPTA40 — Séparation des tâches : traçabilité du second regard (validation).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('compta', '0041_pisteauditcomptable'),
    ]

    operations = [
        migrations.AddField(
            model_name='ecriturecomptable',
            name='valide_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ecritures_validees',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Validée par'),
        ),
        migrations.AddField(
            model_name='ecriturecomptable',
            name='date_validation',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Validée le'),
        ),
    ]
