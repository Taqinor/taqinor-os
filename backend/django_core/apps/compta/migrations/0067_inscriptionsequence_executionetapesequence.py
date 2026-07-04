"""XMKT1 — Moteur d'exécution réel des séquences de relance.

Additif : ``InscriptionSequence`` (un lead inscrit dans une séquence, une seule
inscription ACTIVE à la fois par (séquence, lead)) + ``ExecutionEtapeSequence``
(trace par étape exécutée). Ne touche à aucun modèle existant.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0066_effet_escompte_endossement'),
    ]

    operations = [
        migrations.CreateModel(
            name='InscriptionSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lead_id', models.PositiveIntegerField(verbose_name='Lead (référence opaque)')),
                ('lead_reference', models.CharField(blank=True, default='', max_length=255, verbose_name='Référence lisible du lead')),
                ('statut', models.CharField(choices=[('actif', 'Actif'), ('sorti', 'Sorti'), ('termine', 'Terminé')], default='actif', max_length=10, verbose_name='Statut')),
                ('motif_sortie', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif de sortie')),
                ('declenchee_le', models.DateTimeField(auto_now_add=True, verbose_name='Déclenchée le')),
                ('sortie_le', models.DateTimeField(blank=True, null=True, verbose_name='Sortie le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscriptions_sequence', to='authentication.company', verbose_name='Société')),
                ('etape_courante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inscriptions_en_cours', to='compta.etapesequence', verbose_name='Étape courante')),
                ('sequence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inscriptions', to='compta.sequencerelance', verbose_name='Séquence')),
            ],
            options={
                'verbose_name': 'Inscription à une séquence',
                'verbose_name_plural': 'Inscriptions à une séquence',
                'ordering': ['-declenchee_le'],
            },
        ),
        migrations.CreateModel(
            name='ExecutionEtapeSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('execute_le', models.DateTimeField(auto_now_add=True, verbose_name='Exécutée le')),
                ('canal', models.CharField(blank=True, default='', max_length=10, verbose_name='Canal')),
                ('resultat', models.CharField(default='planifie', max_length=20, verbose_name='Résultat (planifie/envoye/erreur)')),
                ('erreur', models.CharField(blank=True, default='', max_length=500, verbose_name='Erreur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions_etape_sequence', to='authentication.company', verbose_name='Société')),
                ('etape', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='compta.etapesequence', verbose_name='Étape')),
                ('inscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='compta.inscriptionsequence', verbose_name='Inscription')),
            ],
            options={
                'verbose_name': "Exécution d'étape de séquence",
                'verbose_name_plural': "Exécutions d'étape de séquence",
                'ordering': ['-execute_le'],
            },
        ),
        migrations.AddConstraint(
            model_name='inscriptionsequence',
            constraint=models.UniqueConstraint(condition=models.Q(('statut', 'actif')), fields=('sequence', 'lead_id'), name='uniq_inscription_active_par_lead'),
        ),
    ]
