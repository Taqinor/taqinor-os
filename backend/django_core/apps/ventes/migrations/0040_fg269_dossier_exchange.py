"""FG269 — DossierExchange : journal de la navette opérateur.

Additive only : crée la table des échanges (envoi/accusé/complément/refus/
approbation) rattachée à un ``RegulatoryDossier``. Entièrement revertable.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ventes', '0039_fg268_regulatory_dossier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierExchange',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('sens', models.CharField(
                    choices=[('envoi', 'Envoi (vers opérateur)'),
                             ('recu', 'Reçu (de opérateur)')],
                    default='envoi', max_length=5, verbose_name='Sens')),
                ('type_echange', models.CharField(
                    choices=[('depot', 'Dépôt de dossier'),
                             ('accuse', 'Accusé de réception'),
                             ('complement', 'Demande de complément'),
                             ('reponse_complement', 'Réponse au complément'),
                             ('refus', 'Refus'),
                             ('approbation', 'Approbation'),
                             ('relance', 'Relance'),
                             ('autre', 'Autre')],
                    default='autre', max_length=20,
                    verbose_name="Type d'échange")),
                ('date_echange', models.DateField(
                    verbose_name="Date de l'échange")),
                ('objet', models.CharField(
                    blank=True, max_length=200, null=True,
                    verbose_name='Objet')),
                ('detail', models.TextField(blank=True, null=True)),
                ('piece_jointe', models.CharField(
                    blank=True, max_length=500, null=True,
                    verbose_name='Pièce jointe (chemin/clé)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='dossier_exchanges',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='exchanges',
                    to='ventes.regulatorydossier', verbose_name='Dossier')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='dossier_exchanges_crees',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Échange de dossier",
                'verbose_name_plural': "Échanges de dossier",
                'ordering': ['-date_echange', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='dossierexchange',
            index=models.Index(fields=['company', 'dossier'],
                               name='ix_dosex_comp_dossier'),
        ),
    ]
