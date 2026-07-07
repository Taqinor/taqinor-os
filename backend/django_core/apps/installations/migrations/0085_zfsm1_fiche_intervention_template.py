import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZFSM1 — gabarit de fiche d'intervention configurable par type (Odoo
    Worksheet Template). Ajoute FicheInterventionTemplate + Champ + Releve +
    Valeur, matérialisé paresseusement par intervention. Additive — aucune
    migration destructive, aucun champ existant modifié."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0084_yserv1_client_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='FicheInterventionTemplate',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('type_intervention', models.CharField(max_length=20)),
                ('actif', models.BooleanField(default=True)),
                ('protege', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiche_intervention_templates',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': "Gabarit de fiche d'intervention",
                'verbose_name_plural': "Gabarits de fiche d'intervention",
                'ordering': ['type_intervention', 'nom'],
            },
        ),
        migrations.CreateModel(
            name='FicheInterventionChamp',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('cle', models.CharField(max_length=40)),
                ('libelle', models.CharField(max_length=150)),
                ('type_champ', models.CharField(choices=[
                    ('case', 'Case à cocher'), ('texte', 'Texte court'),
                    ('nombre', 'Nombre'), ('mesure', 'Mesure (avec unité)'),
                ], max_length=10)),
                ('unite', models.CharField(blank=True, default='', max_length=20)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('obligatoire', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiche_intervention_champs',
                    to='authentication.company')),
                ('template', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='champs',
                    to='installations.ficheinterventiontemplate')),
            ],
            options={
                'verbose_name': 'Champ de fiche (gabarit)',
                'verbose_name_plural': 'Champs de fiche (gabarit)',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='FicheInterventionReleve',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiche_intervention_releves',
                    to='authentication.company')),
                ('intervention', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiche_releve', to='installations.intervention')),
                ('template', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='releves',
                    to='installations.ficheinterventiontemplate')),
            ],
            options={
                'verbose_name': "Relevé de fiche d'intervention",
                'verbose_name_plural': "Relevés de fiche d'intervention",
                'ordering': ['intervention_id'],
            },
        ),
        migrations.CreateModel(
            name='FicheInterventionValeur',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('valeur', models.TextField(blank=True, default='')),
                ('renseigne_le', models.DateTimeField(blank=True, null=True)),
                ('champ', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='valeurs', to='installations.ficheinterventionchamp')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fiche_intervention_valeurs',
                    to='authentication.company')),
                ('releve', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='valeurs', to='installations.ficheinterventionreleve')),
            ],
            options={
                'verbose_name': "Valeur de fiche d'intervention",
                'verbose_name_plural': "Valeurs de fiche d'intervention",
                'ordering': ['champ__ordre', 'id'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='ficheinterventiontemplate',
            unique_together={('company', 'type_intervention')},
        ),
        migrations.AlterUniqueTogether(
            name='ficheinterventionchamp',
            unique_together={('template', 'cle')},
        ),
        migrations.AlterUniqueTogether(
            name='ficheinterventionvaleur',
            unique_together={('releve', 'champ')},
        ),
    ]
