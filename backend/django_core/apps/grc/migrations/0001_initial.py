# NTGRC4 — première migration du module GRC : politique de rétention par TYPE
# D'OBJET (société × type d'objet). Table NEUVE, aucune donnée existante.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolitiqueRetentionObjet',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_objet', models.CharField(
                    choices=[('crm_lead', 'Lead CRM'),
                             ('crm_client', 'Client CRM'),
                             ('ventes_facture', 'Facture'),
                             ('sav_ticket', 'Ticket SAV'),
                             ('audit_log', "Ligne du journal d'audit")],
                    max_length=30, verbose_name="Type d'objet")),
                ('duree_conservation_mois', models.PositiveIntegerField(
                    default=36,
                    help_text="Au-delà de cette durée, l'objet est échu.",
                    verbose_name='Durée de conservation (mois)')),
                ('action_echeance', models.CharField(
                    choices=[('signaler', 'Signaler seulement'),
                             ('anonymiser', 'Anonymiser'),
                             ('archiver', 'Archiver')],
                    default='signaler',
                    help_text="Une action que l'app cible ne sait pas "
                              'exécuter retombe sur « signaler » — jamais sur '
                              'une suppression inventée.',
                    max_length=12, verbose_name="Action à l'échéance")),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Active')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Politique de rétention par type d'objet",
                'verbose_name_plural': (
                    "Politiques de rétention par type d'objet"),
                'ordering': ['type_objet', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='politiqueretentionobjet',
            constraint=models.UniqueConstraint(
                fields=('company', 'type_objet'),
                name='grc_politiqueretentionobjet_co_type'),
        ),
    ]
