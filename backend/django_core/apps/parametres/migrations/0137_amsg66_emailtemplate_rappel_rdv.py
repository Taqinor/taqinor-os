# AMSG66 — clé « rappel_rdv » du modèle d'e-mail : sujet du rappel de pose
# J-1 éditable par la société et traduit (choix seulement, aucune donnée).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0136_companyprofile_devise_tenant'),
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
                ('rappel_rdv', 'Rappel de RDV (J-1)'),
            ], max_length=40),
        ),
    ]
