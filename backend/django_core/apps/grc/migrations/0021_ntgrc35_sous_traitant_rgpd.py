# NTGRC35 — sous-traitants au sens de l'art. 28 RGPD / loi 09-08.
# Table NEUVE, purement additive. Le fournisseur et le questionnaire de
# conformité sont référencés par des identifiants TEXTE (string-FK) : tous les
# sous-traitants ne sont pas des fournisseurs référencés, et la fiche survit à
# la disparition de l'un comme de l'autre.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0020_ntgrc33_cadre_conformite'),
    ]

    operations = [
        migrations.CreateModel(
            name='SousTraitantRGPD',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(
                    max_length=200, verbose_name='Nom')),
                ('fournisseur_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du stock.Fournisseur '
                              '(string-FK), quand le sous-traitant est aussi '
                              'un fournisseur référencé.',
                    max_length=64, verbose_name='Fournisseur')),
                ('finalites', models.JSONField(
                    blank=True, default=list,
                    help_text='Ce pour quoi il traite les données POUR NOUS '
                              '— ex. ["hébergement", "paie"].',
                    verbose_name='Finalités')),
                ('categories_donnees', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Catégories de données')),
                ('localisation_donnees', models.CharField(
                    blank=True, default='',
                    help_text='Pays/région où les données sont effectivement '
                              'stockées.',
                    max_length=200,
                    verbose_name='Localisation des données')),
                ('clause_signee', models.BooleanField(
                    default=False,
                    verbose_name='Clause de sous-traitance signée')),
                ('date_clause', models.DateField(
                    blank=True, null=True, verbose_name='Date de la clause')),
                ('questionnaire_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du '
                              'grc.QuestionnaireFournisseur (string-FK).',
                    max_length=64,
                    verbose_name='Questionnaire de conformité')),
                ('niveau_risque', models.CharField(
                    choices=[('faible', 'Faible'), ('moyen', 'Moyen'),
                             ('eleve', 'Élevé')],
                    default='moyen', max_length=8,
                    verbose_name='Niveau de risque')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Sous-traitant (RGPD)',
                'verbose_name_plural': 'Sous-traitants (RGPD / art. 28)',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='soustraitantrgpd',
            index=models.Index(fields=['company', 'clause_signee'],
                               name='grc_soustraitant_co_cla_idx'),
        ),
    ]
