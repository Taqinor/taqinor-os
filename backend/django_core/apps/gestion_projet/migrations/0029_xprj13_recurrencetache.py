import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0028_xprj10_tache_assigne_priorite_etiquettes'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecurrenceTache',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('charge_estimee', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True,
                    verbose_name='Charge estimée (j-h)')),
                ('regle', models.CharField(
                    choices=[
                        ('hebdomadaire', 'Hebdomadaire'),
                        ('mensuelle', 'Mensuelle'),
                    ],
                    max_length=15, verbose_name='Règle')),
                ('intervalle', models.PositiveSmallIntegerField(
                    default=1, verbose_name='Intervalle')),
                ('prochaine_echeance', models.DateField(
                    verbose_name='Prochaine échéance')),
                ('date_fin', models.DateField(
                    blank=True, null=True,
                    verbose_name='Fin de récurrence')),
                ('nb_occurrences', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name="Nombre d'occurrences")),
                ('nb_generees', models.PositiveIntegerField(
                    default=0, verbose_name='Occurrences générées')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Active')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('assigne', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurrences_tache',
                    to='gestion_projet.ressourceprofil',
                    verbose_name='Assigné')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gp_recurrences_tache',
                    to='authentication.company', verbose_name='Société')),
                ('phase', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurrences_tache',
                    to='gestion_projet.phaseprojet', verbose_name='Phase')),
                ('projet', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recurrences_tache',
                    to='gestion_projet.projet', verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Récurrence de tâche',
                'verbose_name_plural': 'Récurrences de tâches',
                'ordering': ['prochaine_echeance', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='recurrencetache',
            index=models.Index(
                fields=['actif', 'prochaine_echeance'],
                name='gp_recur_actif_echeance_idx'),
        ),
    ]
