from django.db import migrations, models


class Migration(migrations.Migration):
    """NTDMO8 — deux booléens additifs sur ``Company`` (défaut False).

    Introduits ici (lane Démo NTDMO1) parce que ``seed_demo_company`` marque la
    société de démonstration ``est_demo=True`` dès sa création et que le endpoint
    reset-demo (NTDMO7) en dépend avant la position de NTDMO8 dans la file. Purement
    additifs : toute société existante garde ``est_demo=False`` /
    ``mode_presentation_actif=False`` → comportement strictement inchangé.
    """

    dependencies = [
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='est_demo',
            field=models.BooleanField(
                default=False, verbose_name='Société de démonstration',
                help_text="True pour un tenant de démonstration "
                          "(seed_demo_company). Jamais posé via l'API publique."),
        ),
        migrations.AddField(
            model_name='company',
            name='mode_presentation_actif',
            field=models.BooleanField(
                default=False, verbose_name='Mode présentation actif',
                help_text="Quand True, masque les coordonnées PII des "
                          "clients/leads en LECTURE seule (jamais en écriture, "
                          "jamais les factures). Réservé aux sociétés démo."),
        ),
    ]
