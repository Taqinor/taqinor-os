import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0057_xmfg6_ordreassemblageligne'),
        ('stock', '0026_fg67_frais_annexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SerieAssemblage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_serie', models.CharField(max_length=120)),
                ('role', models.CharField(choices=[('composite', 'Composite produit'), ('composant', 'Composant consommé')], max_length=12)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_series_assemblage', to='authentication.company')),
                ('composite_ref', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='composants_lies', to='installations.serieassemblage')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_series_assemblage_crees', to=settings.AUTH_USER_MODEL)),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='series', to='installations.ordreassemblage')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_series_assemblage', to='stock.produit')),
            ],
            options={
                'verbose_name': "Série d'assemblage",
                'verbose_name_plural': "Séries d'assemblage",
                'ordering': ['ordre_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='serieassemblage',
            index=models.Index(fields=['ordre', 'role'], name='idx_serieasm_ordre_role'),
        ),
        migrations.AddIndex(
            model_name='serieassemblage',
            index=models.Index(fields=['numero_serie'], name='idx_serieasm_numero'),
        ),
    ]
