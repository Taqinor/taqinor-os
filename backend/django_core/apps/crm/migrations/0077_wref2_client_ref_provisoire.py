"""WREF2-PONT (fondateur 21/08/2026) — le code provisoire reste retrouvable.

La référence serveur « NOM-N » prend désormais ``Lead.client_ref`` ; mais le
site (transfert fire-and-forget, zéro-perte) continue d'AFFICHER au client le
code provisoire « TQ-XXXX » généré navigateur. Ce champ le conserve pour que
le code réellement dicté sur WhatsApp retrouve toujours le lead — sans lui,
on recréait exactement le bug d'origine (« TQ-PKEA introuvable »).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0076_ntmig26_certification_partenaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='client_ref_provisoire',
            field=models.CharField(
                blank=True, max_length=24, null=True,
                verbose_name='Référence provisoire affichée par le site'),
        ),
    ]
