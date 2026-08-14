# NTMFG14 — Maintenance préventive des postes de charge (outillage/machine de
# production INTERNE, distinct du parc CLIENT `sav.Equipement`/`PlanEntretien`).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mrp', '0009_operationgamme_company'),
    ]

    operations = [
        migrations.AddField(
            model_name='postedecharge',
            name='usage_reinitialise_le',
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Compteur d'usage réinitialisé le"),
        ),
        migrations.CreateModel(
            name='PlanEntretienPoste',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.CharField(max_length=200, verbose_name='Description')),
                ('intervalle_jours', models.PositiveIntegerField(blank=True, null=True, verbose_name='Intervalle (jours)')),
                ('intervalle_heures_usage', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Intervalle (heures d'usage)")),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('poste_charge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans_entretien', to='mrp.postedecharge', verbose_name='Poste de charge')),
            ],
            options={
                'verbose_name': "Plan d'entretien de poste",
                'verbose_name_plural': "Plans d'entretien de poste",
                'ordering': ['poste_charge_id', 'id'],
                'indexes': [models.Index(fields=['poste_charge', 'actif'], name='mrp_planent_poste_actif_idx')],
            },
        ),
        migrations.CreateModel(
            name='EcheanceEntretienPoste',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_prevue', models.DateField(verbose_name='Date prévue')),
                ('statut', models.CharField(choices=[('a_faire', 'À faire'), ('planifie', 'Planifié'), ('fait', 'Fait')], default='a_faire', max_length=10)),
                ('date_realisee', models.DateField(blank=True, null=True)),
                ('note', models.CharField(blank=True, default='', max_length=300)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeances', to='mrp.planentretienposte')),
            ],
            options={
                'verbose_name': "Échéance d'entretien de poste",
                'verbose_name_plural': "Échéances d'entretien de poste",
                'ordering': ['plan_id', 'date_prevue'],
                'indexes': [models.Index(fields=['plan', 'statut'], name='mrp_echeanceent_plan_statut_idx')],
            },
        ),
    ]
