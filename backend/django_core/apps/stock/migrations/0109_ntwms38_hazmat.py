# NTWMS38 — marchandises dangereuses : classe de danger produit + casiers
# compatibles. Additive : la classe par défaut est AUCUNE, donc aucun produit
# existant ne change de comportement et le rangement guidé ne filtre rien tant
# qu'aucune compatibilité n'est déclarée.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('installations', '0100_photochecklistmeta_tenantmodel_timestamps'),
        ('stock', '0108_ntwms37_pesee_ligne_reception'),
    ]

    operations = [
        migrations.AddField(
            model_name='produit',
            name='classe_danger',
            field=models.CharField(choices=[('AUCUNE', 'Aucune'), ('BATTERIE_LITHIUM', 'Batterie lithium'), ('INFLAMMABLE', 'Inflammable'), ('CORROSIF', 'Corrosif')], default='AUCUNE', help_text='Matière dangereuse : conditionne les casiers autorisés au rangement (NTWMS38).', max_length=20, verbose_name='Classe de danger'),
        ),
        migrations.CreateModel(
            name='CompatibiliteHazmatCasier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classe_danger', models.CharField(help_text='Valeur de Produit.ClasseDanger acceptée dans ce casier.', max_length=20)),
                ('bin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compatibilites_hazmat_stock', to='installations.binlocation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Compatibilité casier ↔ matière dangereuse',
                'verbose_name_plural': 'Compatibilités casier ↔ matières dangereuses',
                'ordering': ['bin_id', 'classe_danger'],
                'indexes': [models.Index(fields=['company', 'classe_danger'], name='idx_hazmatbin_co_classe')],
            },
        ),
        migrations.AddConstraint(
            model_name='compatibilitehazmatcasier',
            constraint=models.UniqueConstraint(fields=('company', 'bin', 'classe_danger'), name='stock_hazmatbin_company_bin_classe_uniq'),
        ),
    ]
