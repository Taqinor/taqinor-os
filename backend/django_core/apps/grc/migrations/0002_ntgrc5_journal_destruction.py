# NTGRC5 — journal APPEND-ONLY des destructions/anonymisations réelles.
# Table NEUVE, aucune donnée existante. Les références vers les autres apps
# sont des identifiants TEXTE (jamais une FK) : la ligne survit à la
# disparition de l'objet qu'elle documente — c'est tout l'intérêt d'un journal
# de destruction.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalDestruction',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_objet', models.CharField(
                    help_text='Ex. « crm_lead », « stock_fournisseur ».',
                    max_length=60, verbose_name="Type d'objet")),
                ('objet_ref', models.CharField(
                    help_text="Identifiant technique de l'objet touché "
                              '(jamais son nom).',
                    max_length=64, verbose_name="Référence de l'objet")),
                ('action', models.CharField(
                    choices=[('supprime', 'Supprimé'),
                             ('anonymise', 'Anonymisé'),
                             ('archive', 'Archivé')],
                    max_length=12, verbose_name='Action')),
                ('politique_ref', models.CharField(
                    blank=True, default='',
                    help_text='Id de la `grc.PolitiqueRetentionObjet` '
                              'appliquée, si la destruction vient d\'un '
                              'balayage de rétention.',
                    max_length=64, verbose_name='Politique de rétention')),
                ('demande_droit_ref', models.CharField(
                    blank=True, default='',
                    help_text='Référence de la `core.DataSubjectRequest` à '
                              "l'origine de l'effacement, s'il vient d'une "
                              'demande de personne.',
                    max_length=64, verbose_name='Demande de droit')),
                ('executee_par', models.CharField(
                    blank=True, default='',
                    help_text="Instantané du nom d'utilisateur (survit à la "
                              'suppression du compte) ; vide pour un balayage '
                              'système.',
                    max_length=150, verbose_name='Exécutée par')),
                ('motif', models.TextField(
                    blank=True, default='', verbose_name='Motif')),
                ('empreinte_avant', models.CharField(
                    blank=True, default='',
                    help_text='SHA-256 de la valeur détruite — jamais la '
                              'valeur.',
                    max_length=64,
                    verbose_name='Empreinte avant destruction (SHA-256)')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Ligne du journal de destruction',
                'verbose_name_plural': 'Journal de destruction',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='journaldestruction',
            index=models.Index(fields=['company', 'type_objet'],
                               name='grc_journaldestr_co_type_idx'),
        ),
        migrations.AddIndex(
            model_name='journaldestruction',
            index=models.Index(fields=['company', '-created_at'],
                               name='grc_journaldestr_co_date_idx'),
        ),
    ]
