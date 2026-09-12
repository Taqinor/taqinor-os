# NTPAY2 — Interface comptable PARAMÉTRABLE de la paie.
#
# `services.journal_de_paie` codait en dur les comptes CGNC de l'écriture de
# paie (6171/6174/4441/4452/4443/4432). `SchemaComptablePaie` les rend
# éditables par société, par POSTE SYSTÈME ou par RUBRIQUE, avec une section
# analytique optionnelle (string-FK vers `compta.CentreCout`).
#
# Migration purement ADDITIVE : une nouvelle table, aucun champ existant
# touché. Sans aucune ligne de schéma, le journal de paie reste identique au
# centime (rétro-compatibilité stricte, vérifiée par les tests).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0047_aud721_bulletin_protect'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchemaComptablePaie',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('code_systeme', models.CharField(
                    blank=True,
                    choices=[
                        ('brut', 'Brut (rémunérations)'),
                        ('charges_patronales',
                         'Charges sociales patronales'),
                        ('cnss_organismes',
                         'Organismes sociaux (CNSS/AMO/AF/TFP)'),
                        ('ir', 'IR retenu à la source'),
                        ('cimr', 'CIMR'),
                        ('net', 'Net à payer (dû au personnel)'),
                    ],
                    default='', max_length=24, verbose_name='Poste système')),
                ('compte_debit', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Compte de débit')),
                ('compte_credit', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Compte de crédit')),
                ('section_analytique_id', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Section analytique (ID, compta.CentreCout)')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paie_schemas_comptables',
                    to='authentication.company', verbose_name='Société')),
                ('rubrique', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='schemas_comptables', to='paie.rubrique',
                    verbose_name='Rubrique')),
            ],
            options={
                'verbose_name': 'Ligne de plan comptable paie',
                'verbose_name_plural': 'Plan comptable paie',
                'ordering': ['ordre', 'code_systeme', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='schemacomptablepaie',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(('rubrique__isnull', True))
                    & ~models.Q(('code_systeme', ''))
                ) | (
                    models.Q(('rubrique__isnull', False))
                    & models.Q(('code_systeme', ''))
                ),
                name='schema_paie_systeme_xor_rubrique'),
        ),
        migrations.AddConstraint(
            model_name='schemacomptablepaie',
            constraint=models.UniqueConstraint(
                condition=models.Q(('rubrique__isnull', True)),
                fields=('company', 'code_systeme'),
                name='uniq_schema_paie_code_systeme'),
        ),
        migrations.AddConstraint(
            model_name='schemacomptablepaie',
            constraint=models.UniqueConstraint(
                condition=models.Q(('rubrique__isnull', False)),
                fields=('company', 'rubrique'),
                name='uniq_schema_paie_rubrique'),
        ),
    ]
