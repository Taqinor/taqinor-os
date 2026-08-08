"""VAO24 — ``ExecutionCollecte`` : le journal d'exécution de la veille.

Additive et revertable : un seul ``CreateModel`` sur une app NEUVE, aucun
index posé sur une table vivante (les deux index naissent AVEC la table).
``source`` est ``SET_NULL`` à dessein — le journal doit SURVIVRE à la
suppression d'une source, sinon on perd la trace de ce qui a été lu le jour
où quelqu'un nettoie le catalogue.
"""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('veille_ao', '0004_vao10_regleexclusion'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExecutionCollecte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('debut', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Début')),
                ('fin', models.DateTimeField(blank=True, null=True, verbose_name='Fin')),
                ('mots_cles_interroges', models.JSONField(blank=True, default=list, help_text='Ce qui a réellement été demandé — sans quoi « 0 résultat » est illisible.', verbose_name='Mots-clés interrogés')),
                ('examines', models.PositiveIntegerField(default=0, verbose_name='Avis examinés')),
                ('nouveaux', models.PositiveIntegerField(default=0, verbose_name='Avis nouveaux')),
                ('mis_a_jour', models.PositiveIntegerField(default=0, verbose_name='Avis mis à jour')),
                ('auto_ignores', models.PositiveIntegerField(default=0, verbose_name='Avis auto-ignorés')),
                ('erreurs', models.JSONField(blank=True, default=list, verbose_name='Erreurs')),
                ('verdict', models.CharField(choices=[('succes', 'Réussie'), ('anomalie', 'Réussie avec anomalie'), ('echec', 'Échouée')], default='succes', max_length=12, verbose_name='Verdict')),
                ('message', models.CharField(blank=True, default='', max_length=500, verbose_name='Message')),
                ('declencheur', models.CharField(choices=[('planifie', 'Tâche planifiée (06:00)'), ('manuel', 'Déclenchement manuel')], default='planifie', max_length=12, verbose_name='Déclencheur')),
                ('alarme_notifiee', models.BooleanField(default=False, verbose_name='Alarme déjà notifiée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='executions', to='veille_ao.sourceveille', verbose_name='Source')),
            ],
            options={
                'verbose_name': 'Exécution de collecte',
                'verbose_name_plural': 'Exécutions de collecte',
                'ordering': ['-debut', '-id'],
                'indexes': [models.Index(fields=['company', '-debut'], name='veille_ao_exec_co_debut_idx'), models.Index(fields=['company', 'verdict'], name='veille_ao_exec_co_verdict_idx')],
            },
        ),
    ]
