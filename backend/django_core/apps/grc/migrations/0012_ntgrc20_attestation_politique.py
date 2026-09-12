# NTGRC20 — attestation de lecture d'une politique interne (loi 53-05).
# Table NEUVE, purement additive. L'unicité (politique, version, employé) est
# CONDITIONNELLE : les lignes sans dossier employé (attestation saisie pour un
# tiers non salarié) ne doivent pas s'agréger sur la chaîne vide.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0011_ntgrc19_politique_interne'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttestationPolitique',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version_attestee', models.PositiveIntegerField(
                    help_text='Numéro de la version FIGÉE que la personne '
                              "déclare avoir lue (jamais 0 : une politique "
                              "non publiée ne s'atteste pas).",
                    verbose_name='Version attestée')),
                ('employe_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du rh.DossierEmploye '
                              '(string-FK).',
                    max_length=64, verbose_name='Dossier employé')),
                ('attestant_nom', models.CharField(
                    blank=True, default='',
                    help_text="Instantané du nom d'affichage (survit au "
                              'départ).',
                    max_length=160, verbose_name='Attestant')),
                ('nom_saisi', models.CharField(
                    blank=True, default='',
                    help_text="Nom tapé par la personne au moment d'attester "
                              '— son geste de signature électronique simple.',
                    max_length=160,
                    verbose_name='Nom saisi (loi 53-05)')),
                ('date_attestation', models.DateTimeField(
                    blank=True, null=True,
                    help_text='Horodatage SERVEUR, posé à la création.',
                    verbose_name="Date d'attestation")),
                ('preuve', models.JSONField(
                    blank=True, default=dict,
                    help_text='IP et user-agent du poste attestant, posés '
                              'côté serveur.',
                    verbose_name='Preuve')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('politique', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attestations', to='grc.politiqueinterne',
                    verbose_name='Politique')),
            ],
            options={
                'verbose_name': 'Attestation de politique',
                'verbose_name_plural': 'Attestations de politique',
                'ordering': ['-date_attestation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='attestationpolitique',
            index=models.Index(fields=['company', 'politique'],
                               name='grc_attestation_co_pol_idx'),
        ),
        migrations.AddConstraint(
            model_name='attestationpolitique',
            constraint=models.UniqueConstraint(
                condition=models.Q(('employe_ref', ''), _negated=True),
                fields=('politique', 'version_attestee', 'employe_ref'),
                name='grc_attestation_pol_ver_emp'),
        ),
    ]
