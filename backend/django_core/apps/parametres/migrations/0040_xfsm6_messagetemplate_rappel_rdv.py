from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0039_xfac28_credit_hold'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=[
                    ('devis_unique', 'Devis (un seul)'),
                    ('devis_multi_entete', 'Devis (plusieurs) — en-tête'),
                    ('devis_multi_ligne', 'Devis (plusieurs) — ligne'),
                    ('facture', 'Facture'),
                    ('relance', 'Rappel de paiement'),
                    ('ticket_recu', 'Ticket SAV reçu'),
                    ('ticket_planifie', 'Ticket SAV planifié'),
                    ('ticket_resolu', 'Ticket SAV résolu'),
                    ('livraison_en_transit', 'Livraison en transit'),
                    ('livraison_livree', 'Livraison livrée'),
                    ('rappel_rdv', 'Rappel de RDV (J-1)'),
                ],
                max_length=40),
        ),
    ]
