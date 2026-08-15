# NTAI18 — Boucle de correction humaine des extractions (jeu d'or).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0002` de cette app, et ne
# dépend d'`authentication` que par la migration qui CRÉE `Company` (d'autres
# lanes ajoutent des migrations à cette app en parallèle).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0002_ntai17_documentaijob'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtractionCorrection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('champ', models.CharField(help_text='Clé du champ extrait (ex. « numero_cin »).', max_length=120)),
                ('valeur_ia', models.TextField(blank=True, default='', help_text="Valeur proposée par l'extraction.")),
                ('valeur_corrigee', models.TextField(blank=True, default='', help_text="Valeur retenue par l'humain.")),
                ('corrige_le', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('corrige_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_extraction_corrections', to=settings.AUTH_USER_MODEL)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='corrections', to='ai_governance.documentaijob')),
            ],
            options={
                'verbose_name': "Correction d'extraction",
                'verbose_name_plural': "Corrections d'extraction",
                'ordering': ['-corrige_le', '-id'],
                'indexes': [models.Index(fields=['company', 'job'], name='ai_gov_corr_co_job_idx')],
            },
        ),
    ]
