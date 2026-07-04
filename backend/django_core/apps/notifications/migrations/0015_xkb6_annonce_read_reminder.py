# XKB6 — Accusé de lecture obligatoire + relance.
#
# Crée AnnonceLecture (l'accusé de lecture lui-même — son CreateModel avait
# été omis par erreur de la migration 0014, qui n'a créé QUE Annonce ; corrigé
# ici, avant tout déploiement de 0014, donc sans risque de perte de données)
# et AnnonceRelance (état de relance des non-lecteurs, distinct de
# AnnonceLecture pour ne jamais corrompre la sémantique « lu »). Ajoute aussi
# le nouvel EventType ANNONCE_READ_REMINDER (comme 0012/0014, seul le jeu de
# choices des colonnes event_type change).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


EVENT_CHOICES = [
    ('lead_assigned', 'Nouveau lead assigné'),
    ('lead_new', 'Nouveau lead site web'),
    ('devis_accepted', 'Devis accepté'),
    ('devis_opened', 'Proposition ouverte par le client'),
    ('client_contact_request', 'Client souhaite être contacté'),
    ('devis_superior_contact_requested',
     'Avis du supérieur demandé sur un devis'),
    ('chantier_due', 'Chantier à installer'),
    ('facture_overdue', 'Facture en retard'),
    ('warranty_expiring', 'Garantie bientôt expirée'),
    ('maintenance_due', 'Visite de maintenance due'),
    ('stock_low', 'Stock bas'),
    ('sav_ticket_opened', 'Ticket SAV ouvert'),
    ('sav_ticket_breaching', 'Ticket SAV proche de son délai'),
    ('chat_message', 'Nouveau message'),
    ('chat_mention', 'Vous avez été mentionné'),
    ('digest', 'Récapitulatif'),
    ('annonce_published', 'Nouvelle annonce interne'),
    ('annonce_read_reminder', 'Relance lecture obligatoire'),
]


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0010_customuser_supervisor'),
        ('notifications', '0014_xkb5_annonce'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnonceLecture',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('date_lecture', models.DateTimeField(auto_now_add=True)),
                ('annonce', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lectures', to='notifications.annonce')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonce_lectures', to='authentication.company')),
                ('utilisateur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonce_lectures', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Accusé de lecture',
                'verbose_name_plural': 'Accusés de lecture',
                'ordering': ['-date_lecture'],
            },
        ),
        migrations.AddConstraint(
            model_name='annoncelecture',
            constraint=models.UniqueConstraint(
                fields=('annonce', 'utilisateur'),
                name='notif_annonce_lecture_uniq'),
        ),
        migrations.AddIndex(
            model_name='annoncelecture',
            index=models.Index(
                fields=['company', 'annonce'], name='notificatio_company_92a841_idx'),
        ),
        migrations.CreateModel(
            name='AnnonceRelance',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('relances_envoyees', models.PositiveSmallIntegerField(default=0)),
                ('derniere_relance_le', models.DateTimeField(blank=True, null=True)),
                ('annonce', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='relances', to='notifications.annonce')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonce_relances', to='authentication.company')),
                ('utilisateur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonce_relances', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Relance de lecture',
                'verbose_name_plural': 'Relances de lecture',
                'ordering': ['-derniere_relance_le'],
            },
        ),
        migrations.AddConstraint(
            model_name='annoncerelance',
            constraint=models.UniqueConstraint(
                fields=('annonce', 'utilisateur'),
                name='notif_annonce_relance_uniq'),
        ),
        migrations.AddIndex(
            model_name='annoncerelance',
            index=models.Index(
                fields=['company', 'annonce'], name='notificatio_company_fa7d15_idx'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='event_type',
            field=models.CharField(choices=EVENT_CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationpreference',
            name='event_type',
            field=models.CharField(choices=EVENT_CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationroutingrule',
            name='event_type',
            field=models.CharField(
                choices=EVENT_CHOICES, max_length=40,
                verbose_name="Type d'événement"),
        ),
    ]
