# YEVNT8 — nouveaux EventTypes APPROVAL_REQUESTED / APPROVAL_DECIDED.
# Additif : seul le jeu de choices des colonnes event_type change (aucune
# donnée touchée), comme 0012/0014/0015.
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
    ('approval_requested', 'Approbation demandée'),
    ('approval_decided', 'Approbation décidée'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0015_xkb6_annonce_read_reminder'),
    ]

    operations = [
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
