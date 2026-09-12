"""NTWFL12/13 — formulaires dynamiques rattachés aux processus (additive,
réversible).

``FormulaireDefinition`` (+ bibliothèque ``FormulaireChampReutilisable``),
``WorkflowStepDefinition.formulaire`` (FK nullable) et
``WorkflowStepInstance.donnees_formulaire`` (JSON additif).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0053_ntwfl10_groupe_parallele'),
    ]

    operations = [
        migrations.CreateModel(
            name='FormulaireDefinition',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(
                    help_text='Identifiant stable par société (ex. « '
                              'demande_conge »).',
                    max_length=64, verbose_name='Code')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('schema', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste ordonnée de champs typés {nom, type, '
                              'requis, options?, repetable?}.',
                    verbose_name='Schéma')),
                ('champs_conditionnels', models.JSONField(
                    blank=True, default=dict,
                    help_text='{nom_champ: {"visible_si": <condition '
                              'core.rules>}}.',
                    verbose_name='Champs conditionnels')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Formulaire dynamique',
                'verbose_name_plural': 'Formulaires dynamiques',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='formulairedefinition',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='core_formdef_company_code_uniq'),
        ),
        migrations.CreateModel(
            name='FormulaireChampReutilisable',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('type', models.CharField(
                    choices=[
                        ('texte', 'Texte'), ('nombre', 'Nombre'),
                        ('date', 'Date'), ('choix', 'Choix'),
                        ('booleen', 'Booléen')],
                    max_length=20, verbose_name='Type')),
                ('options', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste des choix possibles (type « choix » '
                              'uniquement).',
                    verbose_name='Options')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Champ de formulaire réutilisable',
                'verbose_name_plural': 'Champs de formulaire réutilisables',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddField(
            model_name='workflowstepdefinition',
            name='formulaire',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='etapes', to='core.formulairedefinition',
                verbose_name='Formulaire dynamique'),
        ),
        migrations.AddField(
            model_name='workflowstepinstance',
            name='donnees_formulaire',
            field=models.JSONField(
                blank=True, default=dict, verbose_name='Données du formulaire'),
        ),
    ]
