"""XACC22 — Révisions & scénarios budgétaires.

Additif : ``Budget.version`` (défaut 1 = comportement actuel mono-version
intact), ``Budget.figee`` (verrou lecture seule d'une version),
``Budget.budget_parent`` (chaînage des révisions) et ``Budget.scenario``
(défaut ``engage`` = LE budget consommé par XACC21/FG149 ; ``optimiste``/
``pessimiste`` sont des what-if informatifs). La contrainte d'unicité inclut
désormais version+scénario pour permettre plusieurs versions/scénarios du
même (année, libellé).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0058_budget_controle'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='budget',
            name='uniq_budget_an_lib',
        ),
        migrations.AddField(
            model_name='budget',
            name='version',
            field=models.PositiveIntegerField(default=1, verbose_name='Version'),
        ),
        migrations.AddField(
            model_name='budget',
            name='figee',
            field=models.BooleanField(default=False, verbose_name='Version figée (lecture seule)'),
        ),
        migrations.AddField(
            model_name='budget',
            name='scenario',
            field=models.CharField(choices=[('engage', 'Budget engagé (officiel)'), ('optimiste', 'Scénario optimiste'), ('pessimiste', 'Scénario pessimiste')], default='engage', max_length=12, verbose_name='Scénario'),
        ),
        migrations.AddField(
            model_name='budget',
            name='budget_parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revisions', to='compta.budget', verbose_name='Budget révisé (version précédente)'),
        ),
        migrations.AlterModelOptions(
            name='budget',
            options={'ordering': ['-annee', '-version', '-id'], 'verbose_name': 'Budget', 'verbose_name_plural': 'Budgets'},
        ),
        migrations.AddConstraint(
            model_name='budget',
            constraint=models.UniqueConstraint(fields=('company', 'annee', 'libelle', 'version', 'scenario'), name='uniq_budget_an_lib_version_scenario'),
        ),
    ]
