# NTGRC6 — registre des violations de données personnelles + délai légal 72 h.
# Table NEUVE, aucune donnée existante. `reference` est unique PAR SOCIÉTÉ
# (deux sociétés peuvent légitimement porter le même numéro) et posée par la
# numérotation race-safe `core.numbering`, jamais par un count()+1.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0002_ntgrc5_journal_destruction'),
    ]

    operations = [
        migrations.CreateModel(
            name='ViolationDonnees',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Référence')),
                ('date_detection', models.DateTimeField(
                    help_text='Moment où la violation a été CONNUE — '
                              "c'est elle qui déclenche le délai de 72 h.",
                    verbose_name='Date de détection')),
                ('date_incident', models.DateTimeField(
                    blank=True, null=True,
                    help_text="Moment où la violation s'est produite, si "
                              'connu.',
                    verbose_name="Date de l'incident")),
                ('nature', models.CharField(
                    choices=[
                        ('confidentialite', 'Atteinte à la confidentialité'),
                        ('integrite', "Atteinte à l'intégrité"),
                        ('disponibilite', 'Atteinte à la disponibilité')],
                    default='confidentialite', max_length=20,
                    verbose_name='Nature')),
                ('categories_donnees', models.JSONField(
                    blank=True, default=list,
                    help_text='Ex. ["identite", "contact", '
                              '"donnees_bancaires"].',
                    verbose_name='Catégories de données touchées')),
                ('nombre_personnes_estime', models.PositiveIntegerField(
                    default=0,
                    verbose_name='Nombre de personnes concernées (estimé)')),
                ('gravite', models.CharField(
                    choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'),
                             ('elevee', 'Élevée'), ('critique', 'Critique')],
                    default='moyenne', max_length=10,
                    verbose_name='Gravité')),
                ('risque_personnes', models.TextField(
                    blank=True, default='',
                    verbose_name='Risque pour les personnes')),
                ('mesures_prises', models.TextField(
                    blank=True, default='', verbose_name='Mesures prises')),
                ('notification_cndp_requise', models.BooleanField(
                    default=True, verbose_name='Notification CNDP requise')),
                ('date_notification_cndp', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Date de notification CNDP')),
                ('date_echeance_72h', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Détection + 72 h. Posée à la création, jamais '
                              'reculée.',
                    verbose_name='Échéance de notification (72 h)')),
                ('personnes_notifiees', models.BooleanField(
                    default=False,
                    verbose_name='Personnes concernées informées')),
                ('statut', models.CharField(
                    choices=[('ouverte', 'Ouverte'),
                             ('en_analyse', 'En analyse'),
                             ('notifiee', 'Notifiée'),
                             ('cloturee', 'Clôturée')],
                    default='ouverte', max_length=12,
                    verbose_name='Statut')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='grc_violationdonnees_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Violation de données',
                'verbose_name_plural': 'Registre des violations de données',
                'ordering': ['-date_detection', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='violationdonnees',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='grc_violationdonnees_co_ref'),
        ),
        migrations.AddIndex(
            model_name='violationdonnees',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_violation_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='violationdonnees',
            index=models.Index(fields=['company', 'date_echeance_72h'],
                               name='grc_violation_co_ech_idx'),
        ),
    ]
