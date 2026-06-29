"""FG242 — ConcurrentPerte model (suivi des concurrents sur deals perdus).

Additif : nouvelle table, aucune colonne existante modifiée. Company-scoped via
FK ; saisi_par optionnel (FK à CustomUser, SET_NULL). Capture le concurrent
gagnant + son prix sur un lead perdu (intelligence concurrentielle).

Nom d'index ≤ 30 chars (règle CI-enforced) : crm_concperte_co_lead_idx.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0028_objectifcommercial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConcurrentPerte',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('concurrent_nom', models.CharField(
                    max_length=200, verbose_name='Concurrent gagnant')),
                ('concurrent_prix', models.DecimalField(
                    max_digits=12, decimal_places=2,
                    null=True, blank=True,
                    validators=[
                        django.core.validators.MinValueValidator(0)],
                    verbose_name='Prix du concurrent',
                    help_text='Prix proposé par le concurrent. Vide si inconnu.',
                )),
                ('devise', models.CharField(
                    max_length=8, default='MAD', blank=True,
                    verbose_name='Devise')),
                ('motif', models.CharField(
                    max_length=255, blank=True, null=True,
                    verbose_name='Motif de la perte')),
                ('notes', models.TextField(
                    blank=True, null=True, verbose_name='Notes')),
                ('saisi_le', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='concurrents_perte',
                    to='authentication.company',
                )),
                ('lead', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='concurrents_perte',
                    to='crm.lead',
                    verbose_name='Lead perdu',
                )),
                ('saisi_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='concurrents_perte_saisis',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Saisi par',
                )),
            ],
            options={
                'verbose_name': 'Concurrent (deal perdu)',
                'verbose_name_plural': 'Concurrents (deals perdus)',
                'ordering': ['-saisi_le'],
            },
        ),
        migrations.AddIndex(
            model_name='concurrentperte',
            index=models.Index(
                fields=['company', 'lead'],
                name='crm_concperte_co_lead_idx',
            ),
        ),
    ]
