# NTWFL18 — chatter du dossier transverse (`DossierActivity`) + marqueur
# anti-double-alerte d'échéance sur `Dossier`. Purement ADDITIF : une table
# neuve et un champ nullable, aucune donnée existante touchée.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_ntwfl17_dossier'),
        ('authentication', '0013_customuser_poste_ref'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='dossier',
            name='dernier_rappel_echeance_le',
            field=models.DateField(
                blank=True, null=True,
                help_text='Vide = jamais alerté ; une seule alerte par jour.',
                verbose_name="Dernier rappel d'échéance"),
        ),
        migrations.CreateModel(
            name='DossierActivity',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(
                    choices=[
                        ('creation', 'Création'),
                        ('modification', 'Modification'),
                        ('lien', 'Rattachement'),
                        ('note', 'Note'),
                    ],
                    default='note', max_length=16, verbose_name='Type')),
                ('field', models.CharField(
                    blank=True, default='', max_length=100,
                    verbose_name='Champ')),
                ('field_label', models.CharField(
                    blank=True, default='', max_length=150,
                    verbose_name='Libellé du champ')),
                ('old_value', models.TextField(
                    blank=True, default='',
                    verbose_name='Ancienne valeur')),
                ('new_value', models.TextField(
                    blank=True, default='',
                    verbose_name='Nouvelle valeur')),
                ('body', models.TextField(
                    blank=True, default='', verbose_name='Contenu')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activites', to='core.dossier',
                    verbose_name='Dossier')),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='core_dossier_activites',
                    to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
            ],
            options={
                'verbose_name': 'Activité de dossier',
                'verbose_name_plural': 'Activités de dossier',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='dossieractivity',
            index=models.Index(fields=['dossier', '-created_at'],
                               name='core_dosact_dos_date_idx'),
        ),
    ]
