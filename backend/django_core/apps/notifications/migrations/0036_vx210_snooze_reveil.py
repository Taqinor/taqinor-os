# VX210 — le snooze devient un rappel ACTIF : (a) nouvel EventType
# `snooze_reveil` (AlterField des choices — additif, aucun DDL destructif) ;
# (b) table générique `SnoozedItem` pour snoozer une approbation hétérogène
# depuis « Ma file » (clé texte `(user, source, object_id)`, patron
# `ApprovalReminderState` sans ContentType).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CHOICES = [
    ('lead_assigned', 'Nouveau lead assigné'),
    ('lead_new', 'Nouveau lead site web'),
    ('devis_accepted', 'Devis accepté'),
    ('devis_opened', 'Proposition ouverte par le client'),
    ('devis_reply', 'Réponse email du client sur un devis'),
    ('devis_nudge_due', 'Relance de devis à faire'),
    ('hot_lead_unread', 'Lead chaud non contacté (escalade)'),
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
    ('stock_expiration_soon', 'Lot bientôt périmé'),
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
    ('bcf_relance_proposee', 'Brouillon de relance BCF proposé'),
    ('projet_retard', 'Retard planning projet'),
    ('flotte_budget_depassement', 'Dépassement budget flotte'),
    ('flotte_zone_alerte', 'Alerte géofencing véhicule'),
    ('flotte_dtc_critique', 'Code défaut moteur critique (DTC)'),
    ('ged_signature_expiration_proche', 'Demande de signature bientôt expirée'),
    ('devis_expired', 'Devis expiré'),
    ('incident_critical', 'Incident QHSE critique'),
    ('post_social_rappel', 'Post social à publier (rappel)'),
    ('nps_promoteur', 'Client promoteur — proposer le parrainage'),
    ('facture_payee', 'Facture intégralement réglée'),
    ('bon_commande_cree', 'Bon de commande créé'),
    ('contrat_signe', 'Contrat signé'),
    ('sav_ticket_resolu', 'Ticket SAV résolu'),
    ('sav_equipement_remplace', 'Équipement SAV remplacé'),
    ('projet_statut_change', 'Statut de projet modifié'),
    ('monitoring_rapport', 'Rapport O&M envoyé au client'),
    ('paie_rib_divergence', 'Divergence RIB paie ↔ RH'),
    ('paie_run_pret', 'Run de paie prêt (validé)'),
    ('chantier_assigne', 'Nouveau chantier assigné'),
    ('da_decidee', "Demande d'achat décidée"),
    ('da_soumise_stale', "Demande d'achat en attente (SLA)"),
    ('snooze_reveil', '⏰ De retour'),
]


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('notifications', '0035_vx213_handoff_aval_events'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='event_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationpreference',
            name='event_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationroutingrule',
            name='event_type',
            field=models.CharField(
                choices=CHOICES, max_length=40,
                verbose_name="Type d'événement"),
        ),
        migrations.CreateModel(
            name='SnoozedItem',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('source', models.CharField(max_length=20)),
                ('object_id', models.PositiveIntegerField()),
                ('snoozed_until', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='snoozed_items', to='authentication.company')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='snoozed_items', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Item reporté (snooze, VX210)',
                'verbose_name_plural': 'Items reportés (snooze, VX210)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='snoozeditem',
            constraint=models.UniqueConstraint(
                fields=('user', 'source', 'object_id'),
                name='notif_snoozed_item_user_source_obj_uniq'),
        ),
    ]
