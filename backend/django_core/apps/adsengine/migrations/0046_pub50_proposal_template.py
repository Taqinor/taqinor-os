# PUB50 — Gabarits de proposition réutilisables : ProposalTemplate (combinaison
# nommée budget/planning/portée) ré-appliquée en un clic pour PRÉ-REMPLIR un
# composeur PUB22 — n'exécute jamais rien.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0045_pub85_factentry_region'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProposalTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120, verbose_name='Nom du gabarit')),
                ('kind', models.CharField(max_length=40, verbose_name="Type d'action ciblé")),
                ('scope', models.CharField(blank=True, default='', max_length=20, verbose_name='Portée (campaign/adset/ad/global)')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='Valeurs pré-remplies (budget/planning/portée)')),
                ('reason_fr', models.CharField(blank=True, default='', max_length=255, verbose_name='Raison par défaut')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Gabarit de proposition',
                'verbose_name_plural': 'Gabarits de proposition',
                'ordering': ['name'],
            },
        ),
        migrations.AddConstraint(
            model_name='proposaltemplate',
            constraint=models.UniqueConstraint(fields=['company', 'name'], name='uniq_adseng_proposaltmpl_co_name'),
        ),
    ]
