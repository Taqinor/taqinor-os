# NTPAY24 — Gabarits de fichiers réglementaires versionnés (SIMT, télépaiement
# CNSS), éditables sans déploiement.
#
# Les gabarits à longueurs fixes étaient codés en dur dans `services` : un
# changement de format officiel imposait une livraison. `GabaritDeclaratif`
# permet d'en activer un custom, daté et versionné.
#
# REPLI STRICT : sans gabarit ACTIF pour un type, la génération garde le
# gabarit codé en dur — sortie identique à aujourd'hui.
#
# Migration purement ADDITIVE : une nouvelle table, aucun champ existant
# touché, aucune ligne créée.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0053_ntpay23_parametrage_paie_company'),
    ]

    operations = [
        migrations.CreateModel(
            name='GabaritDeclaratif',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type_fichier', models.CharField(
                    choices=[
                        ('simt', 'Virement SIMT (banque)'),
                        ('telepaiement_cnss', 'Télépaiement CNSS'),
                    ],
                    max_length=24, verbose_name='Type de fichier')),
                ('version', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Version')),
                ('structure_json', models.JSONField(
                    blank=True, null=True,
                    verbose_name='Structure (longueurs fixes)')),
                ('template_text', models.TextField(
                    blank=True, default='', verbose_name='Gabarit texte')),
                ('actif', models.BooleanField(
                    default=False, verbose_name='Actif')),
                ('date_effet', models.DateField(
                    verbose_name="Date d'effet")),
                # SCA4 — socle `core.models.TenantModel`.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Gabarit déclaratif',
                'verbose_name_plural': 'Gabarits déclaratifs',
                'ordering': ['type_fichier', '-date_effet', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='gabaritdeclaratif',
            constraint=models.UniqueConstraint(
                condition=models.Q(('actif', True)),
                fields=('company', 'type_fichier', 'date_effet'),
                name='uniq_gabarit_declaratif_actif_par_date'),
        ),
    ]
