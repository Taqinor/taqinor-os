# QW4 — new events 'lead_callback_requested' + 'lead_callback_sla_breach'
# (a phone_ok lead callback obligation, distinct from a generic WhatsApp
# reply notice). Additive: only the event_type choices set changes.

from django.db import migrations, models


EVENT_CHOICES = [
    ('lead_assigned', 'Nouveau lead assigné'),
    ('lead_new', 'Nouveau lead site web'),
    ('devis_accepted', 'Devis accepté'),
    ('devis_opened', 'Proposition ouverte par le client'),
    ('client_contact_request', 'Client souhaite être contacté'),
    ('devis_superior_contact_requested',
     'Avis du supérieur demandé sur un devis'),
    ('lead_callback_requested', 'Rappel téléphonique demandé'),
    ('lead_callback_sla_breach', 'Rappel demandé non actionné (SLA)'),
    ('chantier_due', 'Chantier à installer'),
    ('facture_overdue', 'Facture en retard'),
    ('warranty_expiring', 'Garantie bientôt expirée'),
    ('maintenance_due', 'Visite de maintenance due'),
    ('stock_low', 'Stock bas'),
    ('sav_ticket_opened', 'Ticket SAV ouvert'),
    ('sav_ticket_breaching', 'Ticket SAV proche de son délai'),
    ('sav_activite_due', 'Activité SAV à échéance'),
    ('sav_ticket_followed_update', 'Mise à jour sur un ticket suivi'),
    ('sav_visites_auto_generees',
     'Visites préventives générées automatiquement'),
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
    ('bcf_cancelled', 'Bon de commande fournisseur annulé'),
    ('projet_retard', 'Retard planning projet'),
    ('flotte_budget_depassement', 'Dépassement budget flotte'),
    ('flotte_zone_alerte', 'Alerte géofencing véhicule'),
    ('flotte_dtc_critique', 'Code défaut moteur critique (DTC)'),
    ('ged_signature_expiration_proche', 'Demande de signature bientôt expirée'),
    ('devis_expired', 'Devis expiré'),
    ('incident_critical', 'Incident QHSE critique'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0023_ysrv5_sav_visites_auto_generees_event'),
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
