# Generated for ZSTK13 — réglages société stock (barcode/lots-séries/
# colisage/scan), additifs, tous True par défaut (comportement inchangé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0059_ntsec10_session_policy'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='stock_lots_series_actif',
            field=models.BooleanField(default=True, help_text="Affiche les champs lot/série (réception, registre d'expiration, étiquettes). Désactiver masque ces champs sans supprimer les données existantes.", verbose_name='Lots & numéros de série'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='stock_colisage_actif',
            field=models.BooleanField(default=True, help_text="Affiche l'écran de colisage (préparation/contrôle des colis avant expédition). Désactiver masque l'écran sans supprimer les colis existants.", verbose_name='Colisage'),
        ),
        migrations.AddField(
            model_name='companyprofile',
            name='stock_scan_actif',
            field=models.BooleanField(default=True, help_text='Affiche les panneaux de réception/scan code-barres. Désactiver masque ces panneaux (la saisie manuelle reste disponible).', verbose_name='Scan code-barres'),
        ),
    ]
