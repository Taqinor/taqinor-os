# NTRET29 — Grille tarifaire par boutique/emplacement : PrixParEmplacement
# (override optionnel du prix catalogue par boutique) + SessionCaisse.boutique
# (résolution de la boutique tenue par une session). Additif — absent =
# repli sur le prix catalogue actuel (comportement historique inchangé).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0070_ntret8_parametrespos_boutiquepos"),
        ("stock", "0085_ntadm2_produit_entite"),
        ("pos", "0008_ntret25_ecart_arrondi_especes"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessioncaisse",
            name="boutique",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sessions_caisse_pos", to="parametres.boutiquepos"),
        ),
        migrations.CreateModel(
            name="PrixParEmplacement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("prix_ttc", models.DecimalField(decimal_places=2, max_digits=10)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="prix_par_emplacement", to="authentication.company")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="prix_par_emplacement", to="stock.produit")),
                ("boutique", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="prix_par_emplacement", to="parametres.boutiquepos")),
            ],
            options={
                "verbose_name": "Prix par emplacement",
                "verbose_name_plural": "Prix par emplacement",
            },
        ),
        migrations.AddConstraint(
            model_name="prixparemplacement",
            constraint=models.UniqueConstraint(
                fields=("company", "produit", "boutique"),
                name="pos_prixparemplacement_unique_produit_boutique"),
        ),
    ]
