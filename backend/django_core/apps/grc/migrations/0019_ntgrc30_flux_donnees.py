# NTGRC30 — cartographie des flux de données personnelles. Table NEUVE,
# purement additive. `transfert_hors_maroc` est un drapeau DÉCLARÉ (défaut
# False) : jamais déduit du nom du pays, qui est une case libre.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0018_ntgrc27_analyse_dpia'),
    ]

    operations = [
        migrations.CreateModel(
            name='FluxDonnees',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('traitement_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du core.RegistreTraitement '
                              '(string-FK).',
                    max_length=64, verbose_name='Traitement')),
                ('source', models.CharField(
                    help_text="Application ou système d'origine (ex. « ERP — "
                              'CRM »).',
                    max_length=160, verbose_name='Source')),
                ('destination', models.CharField(
                    choices=[('interne', 'Service interne'),
                             ('sous_traitant', 'Sous-traitant'),
                             ('tiers', 'Tiers (destinataire autonome)')],
                    default='interne', max_length=15,
                    verbose_name='Type de destination')),
                ('destinataire', models.CharField(
                    blank=True, default='',
                    help_text='Nom du service, du sous-traitant ou du tiers.',
                    max_length=200, verbose_name='Destinataire')),
                ('categories_donnees', models.JSONField(
                    blank=True, default=list,
                    help_text='Ex. ["identite", "contact", '
                              '"donnees_bancaires"].',
                    verbose_name='Catégories de données')),
                ('transfert_hors_maroc', models.BooleanField(
                    default=False,
                    help_text='Déclaré explicitement — jamais déduit du nom '
                              'du pays.',
                    verbose_name='Transfert hors Maroc')),
                ('pays_destination', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Pays de destination')),
                ('garanties', models.CharField(
                    blank=True,
                    choices=[('', '— aucune garantie déclarée'),
                             ('cct', 'Clauses contractuelles types'),
                             ('adequation', "Décision d'adéquation"),
                             ('derogation',
                              'Dérogation (consentement, contrat…)')],
                    default='', max_length=12,
                    verbose_name='Garanties du transfert')),
                ('volume_estime', models.CharField(
                    blank=True, default='',
                    help_text='Ordre de grandeur (ex. « ~5 000 '
                              'enregistrements/mois »).',
                    max_length=120, verbose_name='Volume estimé')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Flux de données',
                'verbose_name_plural': 'Cartographie des flux de données',
                'ordering': ['source', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='fluxdonnees',
            index=models.Index(fields=['company', 'transfert_hors_maroc'],
                               name='grc_flux_co_horsmaroc_idx'),
        ),
        migrations.AddIndex(
            model_name='fluxdonnees',
            index=models.Index(fields=['company', 'traitement_ref'],
                               name='grc_flux_co_trait_idx'),
        ),
    ]
