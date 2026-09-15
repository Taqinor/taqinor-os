"""MSGACC1 — Message d'accueil : posé par un responsable/admin pour UN employé
précis, affiché en plein écran à sa première ouverture de l'ERP à partir d'une
heure choisie. Nouvelle table, purement additive. CE N'EST PAS UNE
NOTIFICATION : aucun ``EventType`` touché, aucune ligne du centre de
notifications — voir la docstring de ``MessageAccueil`` (models.py).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('notifications', '0057_eventtype_visite_cadence'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageAccueil',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('visible_a_partir_de', models.DateTimeField(
                    db_index=True, verbose_name='Visible à partir de')),
                ('corps', models.TextField(verbose_name='Corps')),
                ('lu_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Lu le')),
                ('cree_le', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('auteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='messages_accueil_envoyes',
                    to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages_accueil',
                    to='authentication.company')),
                ('destinataire', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages_accueil_recus',
                    to=settings.AUTH_USER_MODEL, verbose_name='Destinataire')),
            ],
            options={
                'verbose_name': "Message d'accueil",
                'verbose_name_plural': "Messages d'accueil",
                'ordering': ['visible_a_partir_de', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='messageaccueil',
            index=models.Index(
                fields=['company', 'destinataire', 'lu_le'],
                name='notif_msgacc_dest_lu_idx'),
        ),
        migrations.AddIndex(
            model_name='messageaccueil',
            index=models.Index(
                fields=['company', 'auteur'],
                name='notif_msgacc_auteur_idx'),
        ),
    ]
