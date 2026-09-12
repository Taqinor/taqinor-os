# NTGRC19 — politiques internes versionnées + snapshots immuables.
# Deux tables NEUVES. Le numéro de version est unique PAR POLITIQUE : deux
# politiques différentes portent légitimement une « v1 ».

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0010_ntgrc18_deficience_controle'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolitiqueInterne',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('categorie', models.CharField(
                    choices=[('securite', 'Sécurité'),
                             ('rh', 'Ressources humaines'),
                             ('achats', 'Achats'), ('qualite', 'Qualité'),
                             ('conformite', 'Conformité'),
                             ('it', 'Informatique')],
                    default='conformite', max_length=12,
                    verbose_name='Catégorie')),
                ('contenu', models.TextField(
                    blank=True, default='', verbose_name='Contenu')),
                ('version', models.PositiveIntegerField(
                    default=0,
                    help_text='Incrémentée SERVEUR à chaque publication '
                              '(0 = jamais publiée).',
                    verbose_name='Version')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'),
                             ('publiee', 'Publiée'),
                             ('obsolete', 'Obsolète')],
                    default='brouillon', max_length=10,
                    verbose_name='Statut')),
                ('date_publication', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Date de publication')),
                ('proprietaire', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Propriétaire')),
                ('cible', models.CharField(
                    choices=[('tous', 'Tout le monde'), ('role', 'Un rôle'),
                             ('departement', 'Un département')],
                    default='tous', max_length=12, verbose_name='Cible')),
                ('cible_valeur', models.CharField(
                    blank=True, default='',
                    help_text="Rôle ou département visé quand la cible n'est "
                              'pas « tout le monde ».',
                    max_length=120, verbose_name='Valeur de la cible')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Politique interne',
                'verbose_name_plural': 'Politiques internes',
                'ordering': ['titre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='PolitiqueVersion',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.PositiveIntegerField(
                    verbose_name='Numéro de version')),
                ('contenu', models.TextField(
                    blank=True, default='', verbose_name='Contenu figé')),
                ('auteur', models.CharField(
                    blank=True, default='',
                    help_text="Instantané du nom d'utilisateur (survit à la "
                              'suppression du compte).',
                    max_length=150, verbose_name='Auteur')),
                ('publiee_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Publiée le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('politique', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions', to='grc.politiqueinterne',
                    verbose_name='Politique')),
            ],
            options={
                'verbose_name': 'Version de politique',
                'verbose_name_plural': 'Versions de politique',
                'ordering': ['-numero', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='politiqueinterne',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_politique_co_statut_idx'),
        ),
        migrations.AddConstraint(
            model_name='politiqueversion',
            constraint=models.UniqueConstraint(
                fields=('politique', 'numero'),
                name='grc_politiqueversion_pol_num'),
        ),
    ]
