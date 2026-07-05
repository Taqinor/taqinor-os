from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0045_yhire9_mode_garde_habilitation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtemplate',
            name='cle',
            field=models.CharField(choices=[
                ('devis', 'Devis'),
                ('facture', 'Facture'),
                ('relance', 'Rappel de paiement'),
                ('notification', 'Notification'),
                ('ticket_recu', 'Ticket SAV reçu'),
                ('ticket_planifie', 'Ticket SAV planifié'),
                ('ticket_resolu', 'Ticket SAV résolu'),
                ('pre_echeance', 'Rappel pré-échéance'),
                ('livraison_en_transit', 'Livraison en transit'),
                ('livraison_livree', 'Livraison livrée'),
                ('envoi_devis', 'Envoi de devis'),
            ], max_length=40),
        ),
    ]
