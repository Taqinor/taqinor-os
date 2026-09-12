import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('publicapi', '0017_ntapi19_oauthclient'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartenaireEdi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200)),
                ('type_identifiant', models.CharField(choices=[('gln', 'GLN (GS1)'), ('duns', 'DUNS')], default='gln', max_length=8)),
                ('identifiant', models.CharField(help_text='GLN (13 chiffres) ou DUNS (9 chiffres) du partenaire.', max_length=64)),
                ('format', models.CharField(choices=[('edifact', 'EDIFACT (UN/CEFACT)'), ('x12', 'ANSI X12')], default='edifact', max_length=10)),
                ('mapping_sku', models.JSONField(blank=True, default=dict)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Partenaire EDI',
                'verbose_name_plural': 'Partenaires EDI',
                'ordering': ['nom', 'id'],
                'indexes': [models.Index(fields=['company', 'actif'], name='publicapi_pedi_co_actif_idx')],
                'constraints': [models.UniqueConstraint(fields=('company', 'identifiant'), name='publicapi_partenaireedi_co_ident')],
            },
        ),
    ]
