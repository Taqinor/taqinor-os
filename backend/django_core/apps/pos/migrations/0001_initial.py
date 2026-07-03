import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.pos.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("crm", "0034_qk1_lead_qualification"),
        ("stock", "0028_dc34_fournisseur_type_soustraitantprofile"),
        ("ventes", "0047_qs3_sharelink_bcf"),
        ("compta", "0043_dc32_compte_portail_client_fk"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfigMaterielPOS",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("imprimante_ip", models.CharField(blank=True, default="", max_length=100)),
                ("imprimante_port", models.PositiveIntegerField(default=9100)),
                ("imprimante_active", models.BooleanField(default=False)),
                ("company", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="config_materiel_pos", to="authentication.company")),
            ],
            options={
                "verbose_name": "Configuration matériel POS",
                "verbose_name_plural": "Configurations matériel POS",
            },
        ),
        migrations.CreateModel(
            name="SessionCaisse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("statut", models.CharField(
                    choices=[("ouverte", "Ouverte"), ("cloturee", "Clôturée")],
                    default="ouverte", max_length=10)),
                ("fond_ouverture", models.DecimalField(
                    decimal_places=2, default=0, max_digits=12,
                    verbose_name="Fond de caisse (ouverture)")),
                ("date_ouverture", models.DateTimeField(auto_now_add=True)),
                ("date_cloture", models.DateTimeField(blank=True, null=True)),
                ("montant_compte_cloture", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True)),
                ("montant_tpe_compte", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name="Montant TPE compté (clôture)")),
                ("ecart_tpe", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name="Écart TPE (compté − attendu)")),
                ("commentaire", models.TextField(blank=True, default="")),
                ("caisse_comptable", models.ForeignKey(
                    help_text="Caisse d'espèces compta (FG124) rattachée à cette session.",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="sessions_pos", to="compta.caisse")),
                ("caissier", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sessions_caisse_pos", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sessions_caisse_pos", to="authentication.company")),
                ("cloture_caisse_comptable", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sessions_pos", to="compta.cloturecaisse")),
            ],
            options={
                "verbose_name": "Session de caisse (POS)",
                "verbose_name_plural": "Sessions de caisse (POS)",
                "ordering": ["-date_ouverture"],
            },
        ),
        migrations.CreateModel(
            name="VenteComptoir",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=50)),
                ("statut", models.CharField(
                    choices=[("brouillon", "Brouillon"), ("validee", "Validée"),
                             ("annulee", "Annulée")],
                    default="brouillon", max_length=15)),
                ("taux_tva", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("note", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_validation", models.DateTimeField(blank=True, null=True)),
                ("caissier", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventes_comptoir_caisse", to=settings.AUTH_USER_MODEL)),
                ("client", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="ventes_comptoir", to="crm.client")),
                ("company", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ventes_comptoir", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventes_comptoir_creees", to=settings.AUTH_USER_MODEL)),
                ("facture", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventes_comptoir", to="ventes.facture")),
                ("session_caisse", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ventes", to="pos.sessioncaisse")),
            ],
            options={
                "verbose_name": "Vente comptoir",
                "verbose_name_plural": "Ventes comptoir",
                "ordering": ["-date_creation"],
                "unique_together": {("company", "reference")},
            },
        ),
        migrations.CreateModel(
            name="LigneVenteComptoir",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("designation", models.CharField(max_length=255)),
                ("quantite", models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ("prix_unitaire_ttc", models.DecimalField(decimal_places=2, max_digits=10)),
                ("remise", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("taux_tva", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    help_text="Taux TVA de la ligne (%). Vide = taux de la vente.")),
                ("numeros_serie", models.JSONField(blank=True, default=list, null=True)),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lignes_vente_comptoir", to="stock.produit")),
                ("vente", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes", to="pos.ventecomptoir")),
            ],
            options={
                "verbose_name": "Ligne de vente comptoir",
                "verbose_name_plural": "Lignes de vente comptoir",
            },
        ),
        migrations.CreateModel(
            name="ShareLinkTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("token", models.CharField(
                    default=apps.pos.models._default_share_token,
                    editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(
                    default=apps.pos.models._default_share_expiry)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="share_links_ticket", to="authentication.company")),
                ("vente", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="share_links", to="pos.ventecomptoir")),
            ],
            options={
                "verbose_name": "Lien public — ticket de caisse",
                "verbose_name_plural": "Liens publics — tickets de caisse",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CommandeRetrait",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=50)),
                ("statut", models.CharField(
                    choices=[("a_preparer", "À préparer"), ("pret", "Prêt au retrait"),
                             ("retire", "Retiré"), ("annule", "Annulé")],
                    default="a_preparer", max_length=12)),
                ("code_retrait", models.CharField(
                    blank=True, default=apps.pos.models.default_code_retrait,
                    max_length=12)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_pret", models.DateTimeField(blank=True, null=True)),
                ("date_retrait", models.DateTimeField(blank=True, null=True)),
                ("client", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="commandes_retrait", to="crm.client")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="commandes_retrait", to="authentication.company")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="commandes_retrait_creees", to=settings.AUTH_USER_MODEL)),
                ("devis", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="commandes_retrait", to="ventes.devis")),
                ("vente_comptoir", models.ForeignKey(
                    blank=True, null=True,
                    help_text="Encaissement comptoir associé (paiement au retrait, XPOS6).",
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="commandes_retrait", to="pos.ventecomptoir")),
            ],
            options={
                "verbose_name": "Commande retrait magasin",
                "verbose_name_plural": "Commandes retrait magasin",
                "ordering": ["-date_creation"],
                "unique_together": {("company", "reference")},
            },
        ),
        migrations.CreateModel(
            name="LigneCommandeRetrait",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("quantite", models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ("commande", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes", to="pos.commanderetrait")),
                ("produit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lignes_commande_retrait", to="stock.produit")),
            ],
            options={
                "verbose_name": "Ligne de commande retrait",
                "verbose_name_plural": "Lignes de commande retrait",
            },
        ),
    ]
