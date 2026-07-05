"""XMKT5 — Listes de diffusion nommées + abonnements.

Additif : ``ListeDiffusion`` + ``AbonnementListe`` (dédoublonnage par
destinataire normalisé par liste), et un M2M ``Campagne.listes`` pour cibler
une campagne par liste en plus du segment JSON existant.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0069_suppressionmarketing'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListeDiffusion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom de la liste')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listes_diffusion', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Liste de diffusion',
                'verbose_name_plural': 'Listes de diffusion',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='AbonnementListe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destinataire', models.CharField(max_length=255, verbose_name='Destinataire (email/téléphone normalisé)')),
                ('contact_ref', models.CharField(blank=True, default='', max_length=255, verbose_name='Référence contact (lead/client, opaque)')),
                ('statut', models.CharField(choices=[('inscrit', 'Inscrit'), ('desinscrit', 'Désinscrit')], default='inscrit', max_length=10, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('date_maj', models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abonnements_liste', to='authentication.company', verbose_name='Société')),
                ('liste', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='abonnements', to='compta.listediffusion', verbose_name='Liste')),
            ],
            options={
                'verbose_name': 'Abonnement à une liste',
                'verbose_name_plural': 'Abonnements à une liste',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='abonnementliste',
            constraint=models.UniqueConstraint(fields=('liste', 'destinataire'), name='uniq_abonnement_par_destinataire_liste'),
        ),
        migrations.AddField(
            model_name='campagne',
            name='listes',
            field=models.ManyToManyField(blank=True, related_name='campagnes', to='compta.listediffusion', verbose_name='Listes de diffusion ciblées (XMKT5)'),
        ),
    ]
