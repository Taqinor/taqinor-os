from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0036_xqhs7_analyse_ncr'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conformiteenvironnementale',
            name='type_conformite',
            field=models.CharField(
                choices=[
                    ('autorisation', 'Autorisation environnementale'),
                    ('etude_impact', "Étude d'impact (EIE)"),
                    ('enregistrement_dechets', 'Enregistrement déchets (loi 28-00)'),
                    ('rejets', 'Conformité rejets (eau / air)'),
                    ('commission_locale', 'Commission locale (sécurité)'),
                    ('verification_electrique', 'Vérification électrique périodique'),
                    ('reglement_interieur', 'Règlement intérieur'),
                    ('csh', 'CSH (comité sécurité et hygiène)'),
                    ('urbanisme', 'Urbanisme / autorisation chantier'),
                    ('assurance', 'Assurance obligatoire'),
                    ('autre', 'Autre'),
                ],
                default='autorisation', max_length=25, verbose_name='Type',
            ),
        ),
        migrations.AddField(
            model_name='conformiteenvironnementale',
            name='thematique',
            field=models.CharField(
                choices=[
                    ('environnement', 'Environnement'),
                    ('securite', 'Sécurité'),
                    ('travail', 'Travail'),
                    ('technique', 'Technique'),
                    ('autre', 'Autre'),
                ],
                default='environnement', max_length=15, verbose_name='Thématique',
            ),
        ),
        migrations.AddField(
            model_name='conformiteenvironnementale',
            name='date_derniere_evaluation',
            field=models.DateField(blank=True, null=True, verbose_name='Date de la dernière évaluation'),
        ),
        migrations.AddField(
            model_name='conformiteenvironnementale',
            name='resultat_derniere_evaluation',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Résultat de la dernière évaluation'),
        ),
    ]
