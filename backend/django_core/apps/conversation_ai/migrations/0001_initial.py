# NTAI21 — Enregistrements d'appels commerciaux (upload + transcription).
#
# CHAÎNE DE MIGRATIONS : on dépend des migrations qui CRÉENT les modèles
# référencés (`authentication.Company`, `crm.Client`, `crm.Lead`) et non des
# dernières en date — d'autres lanes ajoutent des migrations à ces apps en
# parallèle, et une dépendance sur leur tête entrerait en collision.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0003_company_alter_customuser_groups_and_more'),
        ('crm', '0003_lead'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppelCommercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fichier_key', models.CharField(blank=True, default='', help_text="Clé de l'objet audio dans le stockage (préfixée société).", max_length=500)),
                ('mime', models.CharField(blank=True, default='', max_length=120)),
                ('duree_s', models.PositiveIntegerField(default=0, help_text="Durée de l'appel en secondes (0 = inconnue).")),
                ('transcript', models.TextField(blank=True, default='', help_text='Transcription produite par le fournisseur STT.')),
                ('statut', models.CharField(choices=[('non_transcrit', 'Non transcrit'), ('en_cours', 'Transcription en cours'), ('transcrit', 'Transcrit'), ('erreur', 'Erreur')], default='non_transcrit', max_length=20)),
                ('message', models.TextField(blank=True, default='', help_text="Message d'erreur capturé (statut « erreur »).")),
                ('transcrit_le', models.DateTimeField(blank=True, null=True)),
                ('client', models.ForeignKey(blank=True, help_text="Client auquel l'appel est rattaché (facultatif).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appels_commerciaux', to='crm.client')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('lead', models.ForeignKey(blank=True, help_text="Lead auquel l'appel est rattaché (facultatif).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appels_commerciaux', to='crm.lead')),
            ],
            options={
                'verbose_name': 'Appel commercial',
                'verbose_name_plural': 'Appels commerciaux',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['company', 'statut'], name='conv_ai_appel_co_stat_idx'), models.Index(fields=['company', 'lead'], name='conv_ai_appel_co_lead_idx')],
            },
        ),
    ]
