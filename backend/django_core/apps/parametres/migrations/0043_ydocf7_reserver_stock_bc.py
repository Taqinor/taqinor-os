# YDOCF7 — BonCommande confirmé : toggle société pour réserver le stock (au
# lieu du seul décrément à la livraison). Défaut OFF = comportement actuel.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0042_xfac29_dgi_transmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="reserver_stock_bc",
            field=models.BooleanField(default=False),
        ),
    ]
