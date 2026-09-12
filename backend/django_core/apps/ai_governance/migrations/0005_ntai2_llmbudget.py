# NTAI2 — Budget IA mensuel par société + coupe-circuit.
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0004` de cette app, et ne
# dépend d'`authentication` que par la migration qui CRÉE `Company`.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0004_ntai1_llmusagerecord'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LlmBudget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('montant_mensuel_mad', models.DecimalField(decimal_places=2, help_text='Plafond de dépense IA du mois, en MAD.', max_digits=12)),
                ('seuil_alerte_pct', models.PositiveSmallIntegerField(default=80, help_text='Pourcentage du plafond déclenchant une alerte (défaut 80).')),
                ('actif', models.BooleanField(default=True, help_text="Un budget inactif ne bride rien et n'alerte pas.")),
                ('alerte_periode', models.CharField(blank=True, default='', help_text="Période « AAAA-MM » de la dernière alerte émise — rend l'alerte idempotente sur le mois.", max_length=7)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Budget IA',
                'verbose_name_plural': 'Budgets IA',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='llmbudget',
            constraint=models.UniqueConstraint(fields=('company',), name='uniq_llmbudget_company'),
        ),
    ]
