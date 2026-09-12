# NTGRC23 — trames réutilisables de questionnaire + trace du modèle d'origine.
# Une table NEUVE + un champ texte ADDITIF sur le questionnaire (chaîne vide
# par défaut : toutes les lignes existantes restent valides).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0013_ntgrc22_questionnaire_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionnairefournisseur',
            name='modele_ref',
            field=models.CharField(
                blank=True, default='', max_length=64,
                verbose_name="Modèle d'origine"),
        ),
        migrations.CreateModel(
            name='ModeleQuestionnaire',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(
                    help_text='Clé stable du modèle (seed idempotent).',
                    max_length=80, verbose_name='Code')),
                ('nom', models.CharField(
                    max_length=200, verbose_name='Nom')),
                ('type', models.CharField(
                    choices=[('securite', 'Sécurité'),
                             ('rgpd', 'RGPD / données personnelles'),
                             ('qualite', 'Qualité'), ('rse', 'RSE')],
                    default='rgpd', max_length=10, verbose_name='Type')),
                ('questions', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste de {intitule, obligatoire, '
                              'type_reponse} — ex. [{"intitule": "Où '
                              'hébergez-vous les données ?", "obligatoire": '
                              'true, "type_reponse": "texte"}].',
                    verbose_name='Questions')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Modèle de questionnaire',
                'verbose_name_plural': 'Modèles de questionnaire',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='modelequestionnaire',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='grc_modelequestionnaire_co_code'),
        ),
    ]
