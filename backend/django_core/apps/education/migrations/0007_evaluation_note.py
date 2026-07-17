# NTEDU15 — Évaluations et notes.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0006_matiere_matiereclasse'),
    ]

    operations = [
        migrations.CreateModel(
            name='Evaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type', models.CharField(choices=[('controle', 'Contrôle'), ('examen', 'Examen'), ('devoir', 'Devoir')], default='controle', max_length=10, verbose_name="Type d'évaluation")),
                ('date', models.DateField(verbose_name='Date')),
                ('coefficient_evaluation', models.DecimalField(decimal_places=2, default=Decimal('1'), max_digits=4, verbose_name="Coefficient de l'évaluation")),
                ('bareme', models.DecimalField(decimal_places=2, default=Decimal('20'), max_digits=5, verbose_name='Barème')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('matiere_classe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='education.matiereclasse', verbose_name='Matière de classe')),
            ],
            options={
                'verbose_name': 'Évaluation',
                'verbose_name_plural': 'Évaluations',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='Note',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('valeur', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Valeur')),
                ('appreciation', models.CharField(blank=True, default='', max_length=255, verbose_name='Appréciation')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('eleve', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='education.eleve', verbose_name='Élève')),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='education.evaluation', verbose_name='Évaluation')),
            ],
            options={
                'verbose_name': 'Note',
                'verbose_name_plural': 'Notes',
                'ordering': ['-evaluation__date'],
                'constraints': [models.UniqueConstraint(fields=('evaluation', 'eleve'), name='education_note_unique_par_evaluation_eleve')],
            },
        ),
    ]
