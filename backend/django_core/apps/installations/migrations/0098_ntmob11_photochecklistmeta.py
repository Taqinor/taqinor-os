"""NTMOB11 — capture multi-photos horodatées géotaguées par étape de
checklist : nouveau modèle ``PhotoChecklistMeta`` (adjacent à
``PhotoAnnotation``), additif pur — aucune migration existante modifiée."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('records', '0013_vx210_snooze_trigger_event'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
        ('installations', '0097_protect_produit_donnees_reelles'),
    ]

    operations = [
        migrations.CreateModel(
            name='PhotoChecklistMeta',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('latitude', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True)),
                ('precision_m', models.FloatField(blank=True, null=True)),
                ('horodatage_capture', models.DateTimeField(auto_now_add=True)),
                ('attachment', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklist_meta', to='records.attachment')),
                ('checklist_item', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='photos',
                    to='installations.chantierchecklistitem')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='photo_checklist_metas',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Métadonnées photo checklist',
                'verbose_name_plural': 'Métadonnées photos checklist',
                'ordering': ['-horodatage_capture'],
            },
        ),
        migrations.AddIndex(
            model_name='photochecklistmeta',
            index=models.Index(
                fields=['checklist_item'],
                name='installatio_checkli_10cc06_idx'),
        ),
    ]
