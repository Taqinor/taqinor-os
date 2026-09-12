"""NTSRV3 - Canal WhatsApp entrant (gated) : nouveaux CHOIX seulement.

Aucune donnee touchee, aucune colonne ajoutee : `Ticket.canal_ouverture`
gagne la valeur `whatsapp` et `TicketActivity.kind` la valeur `whatsapp`.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0052_ntsrv1_ticket_email_thread'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='canal_ouverture',
            field=models.CharField(
                choices=[
                    ('manuel', 'Manuel (back-office)'),
                    ('email', 'E-mail'),
                    ('portail', 'Portail client'),
                    ('whatsapp', 'WhatsApp'),
                ],
                default='manuel',
                help_text='Par quel canal la demande est arrivée (manuel, '
                          'e-mail, portail client…).',
                max_length=12,
                verbose_name="Canal d'ouverture",
            ),
        ),
        migrations.AlterField(
            model_name='ticketactivity',
            name='kind',
            field=models.CharField(
                choices=[
                    ('creation', 'Création'),
                    ('modification', 'Modification'),
                    ('note', 'Note'),
                    ('email', 'E-mail'),
                    ('whatsapp', 'WhatsApp'),
                ],
                max_length=15,
            ),
        ),
    ]
