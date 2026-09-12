# NTAI7 — Consentement & désactivation IA par module (défaut ACTIF).
#
# CHAÎNE DE MIGRATIONS : enchaîne EXPLICITEMENT sur `0006` de cette app.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_governance', '0006_ntai5_prompttemplate'),
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AiFeatureToggle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('feature_key', models.CharField(help_text="Clé de la feature IA (ex. « ai.rediger »), telle qu'elle apparaît aussi dans le journal d'usage.", max_length=120)),
                ('actif', models.BooleanField(default=True, help_text='Décoché = la feature devient inopérante pour cette société.')),
                ('motif', models.CharField(blank=True, default='', help_text='Pourquoi la société a coupé cette feature (traçabilité).', max_length=255)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Consentement IA',
                'verbose_name_plural': 'Consentements IA',
                'ordering': ['feature_key'],
            },
        ),
        migrations.AddConstraint(
            model_name='aifeaturetoggle',
            constraint=models.UniqueConstraint(fields=('company', 'feature_key'), name='uniq_aifeaturetoggle_co_key'),
        ),
    ]
