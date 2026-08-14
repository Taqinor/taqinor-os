"""NTWMS13 — comptage tournant ABC récurrent (cycle counting).

NOUVEAU modèle purement additif : la fréquence de recomptage d'une classe ABC.
Il ne remplace RIEN — les sessions générées sont les ``InventaireSession``
existantes, jamais un mécanisme d'inventaire parallèle.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0094_ntwms12_mode_liberation'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanComptageTournant',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classe_abc', models.CharField(
                    choices=[('A', 'A — forte rotation'),
                             ('B', 'B — rotation moyenne'),
                             ('C', 'C — faible rotation')],
                    max_length=1)),
                ('frequence_jours', models.PositiveIntegerField(default=30)),
                ('actif', models.BooleanField(default=True)),
                ('date_dernier_comptage', models.DateField(
                    blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Plan de comptage tournant',
                'verbose_name_plural': 'Plans de comptage tournant',
                'ordering': ['classe_abc'],
            },
        ),
        migrations.AddConstraint(
            model_name='plancomptagetournant',
            constraint=models.UniqueConstraint(
                fields=('company', 'classe_abc'),
                name='stock_plancomptage_company_classe_uniq'),
        ),
    ]
