# NTGRC8 — mise sous séquestre TRANSVERSE (legal hold au-delà du document).
# Table NEUVE, aucune donnée existante. `ged.LegalHold` (GED24) reste en place
# et n'est pas touché : le séquestre transverse le COMPOSE (le selector
# `objets_sous_hold` lit les deux), il ne le duplique ni ne le remplace.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0003_ntgrc6_violation_donnees'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegalHold',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('motif', models.CharField(
                    choices=[('litige', 'Contentieux / litige'),
                             ('enquete', 'Enquête interne'),
                             ('reglementaire', 'Demande réglementaire')],
                    default='litige', max_length=15, verbose_name='Motif')),
                ('perimetre', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste de {type_objet, filtre} — ex. '
                              '[{"type_objet": "crm_client", '
                              '"filtre": {"identifiant": "a@b.ma"}}].',
                    verbose_name='Périmètre')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                ('statut', models.CharField(
                    choices=[('actif', 'Actif'), ('leve', 'Levé')],
                    default='actif', max_length=8, verbose_name='Statut')),
                ('demandeur', models.CharField(
                    blank=True, default='',
                    help_text='Qui demande le séquestre (avocat, autorité, '
                              'direction).',
                    max_length=160, verbose_name='Demandeur')),
                ('base_juridique', models.TextField(
                    blank=True, default='', verbose_name='Base juridique')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Mise sous séquestre (legal hold)',
                'verbose_name_plural': 'Mises sous séquestre (legal holds)',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='legalhold',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_legalhold_co_statut_idx'),
        ),
    ]
