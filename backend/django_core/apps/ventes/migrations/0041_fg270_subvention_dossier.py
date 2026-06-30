"""FG270 — SubventionDossier : éligibilité & suivi des subventions.

Additive only : crée la table de suivi des dossiers de subvention/incitation
(MASEN/IRESEN/Tatwir) rattachée à un ``Devis``. Entièrement revertable.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0040_fg269_dossier_exchange'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SubventionDossier',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('programme', models.CharField(
                    choices=[('masen', 'MASEN'), ('iresen', 'IRESEN'),
                             ('tatwir', 'Tatwir (PME)'),
                             ('autre', 'Autre programme')],
                    default='autre', max_length=10,
                    verbose_name='Programme')),
                ('statut', models.CharField(
                    choices=[('a_qualifier', 'À qualifier'),
                             ('eligible', 'Éligible'),
                             ('non_eligible', 'Non éligible'),
                             ('depose', 'Déposé'),
                             ('accorde', 'Accordé'),
                             ('refuse', 'Refusé'),
                             ('verse', 'Versé')],
                    default='a_qualifier', max_length=14,
                    verbose_name='Statut')),
                ('montant_demande', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name='Montant demandé (MAD)')),
                ('montant_accorde', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name='Montant accordé (MAD)')),
                ('reference', models.CharField(
                    blank=True, max_length=120, null=True,
                    verbose_name='Référence dossier')),
                ('eligibilite_note', models.TextField(
                    blank=True, null=True,
                    verbose_name="Note d'éligibilité")),
                ('pieces', models.JSONField(
                    blank=True, default=list, verbose_name='Pièces')),
                ('date_depot', models.DateField(
                    blank=True, null=True, verbose_name='Date de dépôt')),
                ('date_decision', models.DateField(
                    blank=True, null=True, verbose_name='Date de décision')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subvention_dossiers',
                    to='authentication.company', verbose_name='Société')),
                ('devis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subvention_dossiers',
                    to='ventes.devis', verbose_name='Devis')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='subvention_dossiers_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Dossier de subvention',
                'verbose_name_plural': 'Dossiers de subvention',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='subventiondossier',
            index=models.Index(fields=['company', 'statut'],
                               name='ix_subv_comp_statut'),
        ),
    ]
