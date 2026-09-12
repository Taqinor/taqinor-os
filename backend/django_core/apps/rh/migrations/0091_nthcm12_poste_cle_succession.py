# NTHCM12 — postes-clés & plans de succession.
#
# Purement ADDITIF : deux tables, aucun champ touché sur l'existant. Un poste
# n'est CLÉ que s'il est explicitement marqué (aucun backfill automatique).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0090_nthcm10_evaluation_neuf_box'),
    ]

    operations = [
        migrations.CreateModel(
            name='PosteCle',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('criticite', models.CharField(
                    choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'),
                             ('haute', 'Haute'), ('critique', 'Critique')],
                    default='moyenne', max_length=10,
                    verbose_name='Criticité')),
                ('justification', models.TextField(
                    blank=True, default='', verbose_name='Justification')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('poste', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='marquages_cles', to='rh.poste',
                    verbose_name='Poste')),
            ],
            options={
                'verbose_name': 'Poste-clé',
                'verbose_name_plural': 'Postes-clés',
                'ordering': ['poste__intitule'],
            },
        ),
        migrations.CreateModel(
            name='PlanSuccession',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('rang', models.CharField(
                    choices=[('premier', '1er choix'), ('second', '2e choix'),
                             ('backup', 'Backup')],
                    default='premier', max_length=10, verbose_name='Rang')),
                ('readiness', models.CharField(
                    choices=[('pret_immediat', 'Prêt immédiatement'),
                             ('pret_1an', 'Prêt sous 1 an'),
                             ('pret_3ans', 'Prêt sous 3 ans')],
                    default='pret_1an', max_length=14,
                    verbose_name='Readiness')),
                ('plan_developpement', models.TextField(
                    blank=True, default='',
                    verbose_name='Plan de développement')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('poste_cle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='plans_succession', to='rh.postecle',
                    verbose_name='Poste-clé')),
                ('successeur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='plans_succession', to='rh.dossieremploye',
                    verbose_name='Successeur')),
            ],
            options={
                'verbose_name': 'Plan de succession',
                'verbose_name_plural': 'Plans de succession',
                'ordering': ['poste_cle', 'rang'],
            },
        ),
        migrations.AddConstraint(
            model_name='postecle',
            constraint=models.UniqueConstraint(
                fields=('company', 'poste'),
                name='rh_postecle_comp_poste_uniq'),
        ),
        migrations.AddConstraint(
            model_name='plansuccession',
            constraint=models.UniqueConstraint(
                fields=('poste_cle', 'successeur'),
                name='rh_plansucc_postecle_succ_uniq'),
        ),
    ]
