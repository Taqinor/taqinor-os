# XFLT18 — nouvel événement « flotte_budget_depassement » (dépassement de
# budget flotte annuel). Additif : seul le jeu de choices des colonnes
# event_type change (aucune donnée touchée). Reprend la liste COMPLÈTE
# actuelle de ``EventType`` (0018 avait omis les événements annonce/
# approbation déjà présents en base depuis 0014-0017 — restauré ici).

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
    ('approval_reminder', "Relance d'approbation"),
    ('approval_escalated', 'Approbation escaladée'),
    ('supplier_doc_expiring', 'Document fournisseur bientôt expiré'),
    ('bcf_late', 'Bon de commande fournisseur en retard'),
    ('flotte_budget_depassement', 'Dépassement budget flotte'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0018_xpur_supplier_events'),
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
