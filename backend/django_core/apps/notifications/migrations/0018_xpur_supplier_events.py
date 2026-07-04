# XPUR1/XPUR7 — nouveaux événements « supplier_doc_expiring » (document de
# conformité fournisseur expiré/bientôt expiré) et « bcf_late » (bon de
# commande fournisseur en retard). Additif : seul le jeu de choices des
# colonnes event_type change (aucune donnée touchée).
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
    ('supplier_doc_expiring', 'Document fournisseur bientôt expiré'),
    ('bcf_late', 'Bon de commande fournisseur en retard'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0017_yevnt9_approval_reminders'),
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
