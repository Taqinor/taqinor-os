# NTHCM10 — grille 9-box (performance × potentiel).
#
# Purement ADDITIF : une table, aucun champ touché sur l'existant.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0089_nthcm8_okr_entreprise'),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationNeufBox',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('axe_performance', models.PositiveSmallIntegerField(
                    choices=[(1, 'Faible'), (2, 'Solide'), (3, 'Fort')],
                    default=2, verbose_name='Axe performance')),
                ('axe_potentiel', models.PositiveSmallIntegerField(
                    choices=[(1, 'Limité'), (2, 'Modéré'), (3, 'Élevé')],
                    default=2, verbose_name='Axe potentiel')),
                ('case_calculee', models.PositiveSmallIntegerField(
                    default=5, verbose_name='Case (1-9)')),
                ('notes', models.TextField(
                    blank=True, default='', verbose_name='Notes')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campagne', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='evaluations_neuf_box',
                    to='rh.campagneevaluation',
                    verbose_name="Campagne d'évaluation")),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evaluations_neuf_box',
                    to='rh.dossieremploye', verbose_name='Employé')),
                ('evalue_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='evaluations_neuf_box',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Évalué par')),
            ],
            options={
                'verbose_name': 'Évaluation 9-box',
                'verbose_name_plural': 'Évaluations 9-box',
                'ordering': ['employe__nom', 'employe__prenom'],
            },
        ),
        migrations.AddIndex(
            model_name='evaluationneufbox',
            index=models.Index(
                fields=['company', 'campagne'],
                name='rh_neufbox_comp_camp_idx'),
        ),
        migrations.AddConstraint(
            model_name='evaluationneufbox',
            constraint=models.UniqueConstraint(
                fields=('employe', 'campagne'),
                name='rh_neufbox_employe_campagne_uniq'),
        ),
        migrations.AddConstraint(
            model_name='evaluationneufbox',
            constraint=models.UniqueConstraint(
                condition=models.Q(('campagne__isnull', True)),
                fields=('employe',),
                name='rh_neufbox_employe_sans_camp_uniq'),
        ),
    ]
