"""U3-900 (fondateur 29/08/2026) — retrait de ``panneaux_par_900mad``.

La règle « panneaux par tranche de 900 MAD de facture hiver » a été supprimée
du dimensionnement résidentiel (backend + écran générateur, PR #577,
027d83eb) : le réglage ne pilotait plus aucun calcul, seulement un champ
Paramètres → Avancé qui s'enregistrait sans effet. ``RemoveField`` — une
inversion de cette migration restaure la colonne avec son défaut (8), sans
perte de données observable (le champ n'a jamais été lu que par le code
retiré)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0079_companyprofile_devis_auto_depuis_tunnel'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='companyprofile',
            name='panneaux_par_900mad',
        ),
    ]
