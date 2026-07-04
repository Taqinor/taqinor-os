# XFSM1 — Facturation SAV hors garantie depuis le ticket. Champs additifs :
# `heures_main_oeuvre` (base de la ligne MO) + `facture_id_ext` (idempotence,
# même patron que `devis_id_ext` XSAV3).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0029_xpos9_equipement_client_vente'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='heures_main_oeuvre',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=6, null=True,
                help_text="Temps passé (heures) — base de la ligne "
                          "main-d'œuvre facturée (XFSM1)."),
        ),
        migrations.AddField(
            model_name='ticket',
            name='facture_id_ext',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='ID de la Facture ventes générée depuis ce ticket '
                          '(XFSM1).'),
        ),
    ]
