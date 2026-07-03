# XKB5 — Annonces internes ciblées et programmées. Additif : nouveau modèle,
# aucune donnée existante touchée. Ajoute aussi l'EventType ANNONCE_PUBLISHED
# (comme 0012, seul le jeu de choices des colonnes event_type change).
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
]


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0010_customuser_supervisor'),
        ('notifications', '0013_xmkt25_whatsapptemplate_approval'),
    ]

    operations = [
        migrations.CreateModel(
            name='Annonce',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('titre', models.CharField(max_length=200, verbose_name='Titre')),
                ('corps', models.TextField(blank=True, default='', verbose_name='Corps')),
                ('cible_type', models.CharField(
                    choices=[
                        ('tous', 'Toute la société'),
                        ('role', 'Par rôle'),
                        ('departement', 'Par département'),
                    ],
                    default='tous', max_length=15, verbose_name='Type de ciblage')),
                ('cible_role', models.CharField(
                    blank=True, default='', max_length=20, verbose_name='Rôle cible')),
                ('cible_departement_nom', models.CharField(
                    blank=True, default='', max_length=120,
                    verbose_name='Département cible')),
                ('date_publication', models.DateTimeField(
                    blank=True, null=True, verbose_name='Publier le')),
                ('date_expiration', models.DateTimeField(
                    blank=True, null=True, verbose_name='Expire le')),
                ('publiee', models.BooleanField(default=False, verbose_name='Publiée')),
                ('date_publication_effective', models.DateTimeField(
                    blank=True, null=True, verbose_name='Publiée le (effectif)')),
                ('epinglee', models.BooleanField(default=False, verbose_name='Épinglée')),
                ('lecture_obligatoire', models.BooleanField(
                    default=False, verbose_name='Lecture obligatoire')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('auteur', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='annonces_creees', to=settings.AUTH_USER_MODEL,
                    verbose_name='Auteur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='annonces', to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Annonce',
                'verbose_name_plural': 'Annonces',
                'ordering': ['-epinglee', '-date_publication_effective', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['company', 'publiee'], name='notificatio_company_0f3808_idx'),
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['company', 'date_publication'], name='notificatio_company_e22080_idx'),
        ),
        migrations.AddIndex(
            model_name='annonce',
            index=models.Index(fields=['company', 'epinglee'], name='notificatio_company_a08c51_idx'),
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
