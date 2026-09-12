# NTGRC27 — drapeau « données sensibles / haut risque » sur le registre des
# traitements (art. 35 RGPD / loi 09-08). Champ ADDITIF à défaut False : aucun
# traitement existant ne devient rétroactivement exigeant d'une AIPD — c'est
# une décision humaine, jamais un effet de bord de migration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_ntobs10_trustcenterentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='registretraitement',
            name='donnees_sensibles',
            field=models.BooleanField(
                default=False,
                help_text="Coché, le traitement exige une analyse d'impact "
                          '(AIPD) validée.',
                verbose_name='Données sensibles / haut risque'),
        ),
    ]
