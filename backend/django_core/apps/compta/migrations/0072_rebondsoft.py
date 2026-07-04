"""XMKT12 — Gestion des rebonds hard/soft.

Additif : ``RebondSoft`` (compteur par destinataire, à travers toutes les
campagnes). Ne touche à aucun modèle existant.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0071_segmentmarketing'),
    ]

    operations = [
        migrations.CreateModel(
            name='RebondSoft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destinataire', models.CharField(max_length=255, verbose_name='Destinataire')),
                ('compte', models.PositiveIntegerField(default=0, verbose_name='Nombre de rebonds soft')),
                ('date_maj', models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rebonds_soft', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Rebond soft',
                'verbose_name_plural': 'Rebonds soft',
                'ordering': ['-date_maj'],
            },
        ),
        migrations.AddConstraint(
            model_name='rebondsoft',
            constraint=models.UniqueConstraint(fields=('company', 'destinataire'), name='uniq_rebond_soft_par_destinataire'),
        ),
    ]
