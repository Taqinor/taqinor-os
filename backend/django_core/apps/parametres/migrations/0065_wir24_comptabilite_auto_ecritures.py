# Generated for WIR24 — écritures comptables automatiques par société.
# Additif et réversible : un seul BooleanField, défaut False (comportement
# historique inchangé — rien n'est passé au grand livre tant que le réglage
# n'est pas activé).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0064_ntsec25_dormant_days'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='comptabilite_auto_ecritures',
            field=models.BooleanField(default=False, help_text="Passe automatiquement au grand livre l'écriture de chaque facture, paiement et avoir émis (partie double, idempotent). Désactivé par défaut : aucune écriture n'est générée tant que ce réglage n'est pas activé.", verbose_name='Écritures comptables automatiques'),
        ),
    ]
