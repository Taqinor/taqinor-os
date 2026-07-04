# YEVNT9 — relance/escalade des approbations en attente : nouveaux
# EventTypes (APPROVAL_REMINDER / APPROVAL_ESCALATED) + deux nouveaux modèles
# (ApprovalReminderConfig singleton par société, ApprovalReminderState
# générique par approbation). Additif : aucune donnée existante touchée.
import django.db.models.deletion
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
]


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('authentication', '0010_customuser_supervisor'),
        ('notifications', '0016_yevnt8_approval_events'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalReminderConfig',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('relance_days', models.PositiveSmallIntegerField(
                    default=2, verbose_name='Seuil relance (jours ouvrés)')),
                ('escalade_days', models.PositiveSmallIntegerField(
                    default=4, verbose_name='Seuil escalade admin (jours ouvrés)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='approval_reminder_config',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Configuration relance approbations',
                'verbose_name_plural': 'Configurations relance approbations',
            },
        ),
        migrations.CreateModel(
            name='ApprovalReminderState',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('palier', models.PositiveSmallIntegerField(default=0)),
                ('derniere_action_le', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='approval_reminder_states',
                    to='authentication.company')),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'État de relance approbation',
                'verbose_name_plural': 'États de relance approbation',
                'ordering': ['-derniere_action_le'],
            },
        ),
        migrations.AddConstraint(
            model_name='approvalreminderstate',
            constraint=models.UniqueConstraint(
                fields=('content_type', 'object_id'),
                name='notif_approval_reminder_state_uniq'),
        ),
        migrations.AddIndex(
            model_name='approvalreminderstate',
            index=models.Index(
                fields=['company', 'content_type'],
                name='notificatio_company_5429ae_idx'),
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
