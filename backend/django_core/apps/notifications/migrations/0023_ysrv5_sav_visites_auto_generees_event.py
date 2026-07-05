# YSERV5 — nouvel événement « sav_visites_auto_generees » (génération
# automatique nocturne de visites préventives dues). Additif : seul le jeu de
# choices des colonnes event_type change (aucune donnée touchée). Reprend la
# liste COMPLÈTE actuelle de ``EventType`` (0021 avait omis quelques
# événements déjà présents en base — flotte_zone_alerte, flotte_dtc_critique,
# ged_signature_expiration_proche, devis_expired, incident_critical —
# restaurés ici pour ne pas régresser plus loin).

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
        ('notifications', '0022_alter_approvalreminderconfig_escalade_days'),
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
