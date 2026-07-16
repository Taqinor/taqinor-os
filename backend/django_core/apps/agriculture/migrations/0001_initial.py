# Hand-authored (NTAGR1) — host env's Django 6.0.6 diverges from the project's
# pinned Django (CheckConstraint `check=` kwarg removed upstream in
# apps/stock/models.py under Django 6), so `manage.py makemigrations` cannot
# run on this host. Mirrors the shape `makemigrations` would generate,
# following apps/qhse/migrations/0001_initial.py's hand-verified conventions.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
    ]

    operations = [
        migrations.CreateModel(
            name="Exploitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("adresse", models.CharField(blank=True, default="", max_length=500)),
                ("superficie_totale_ha", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("responsable_id", models.IntegerField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exploitations_agricoles", to="authentication.company")),
            ],
            options={
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="EquipeSaisonniere",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("chef_equipe_id", models.IntegerField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="equipes_saisonnieres", to="authentication.company")),
            ],
            options={
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="IntrantAgricole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("produit_id", models.IntegerField(unique=True)),
                ("categorie", models.CharField(choices=[("semence", "Semence"), ("engrais", "Engrais"), ("phyto", "Phytosanitaire")], max_length=20)),
                ("dose_reference_par_ha", models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ("delai_avant_recolte_jours", models.IntegerField(blank=True, null=True)),
                ("matiere_active", models.CharField(blank=True, default="", max_length=255)),
                ("numero_amm", models.CharField(blank=True, default="", max_length=100)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="intrants_agricoles", to="authentication.company")),
            ],
            options={
                "ordering": ["categorie", "id"],
            },
        ),
        migrations.CreateModel(
            name="Parcelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("code", models.CharField(blank=True, default="", max_length=50)),
                ("superficie_ha", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("geometrie_gps", models.JSONField(blank=True, null=True)),
                ("culture_principale", models.CharField(blank=True, default="", max_length=100)),
                ("type_sol", models.CharField(blank=True, default="", max_length=100)),
                ("statut", models.CharField(choices=[("en_culture", "En culture"), ("jachere", "Jachère"), ("preparation", "Préparation")], default="preparation", max_length=20)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parcelles_agricoles", to="authentication.company")),
                ("exploitation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="parcelles", to="agriculture.exploitation")),
            ],
            options={
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="CampagneCulturale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("culture", models.CharField(max_length=100)),
                ("variete", models.CharField(blank=True, default="", max_length=100)),
                ("date_semis", models.DateField(blank=True, null=True)),
                ("date_recolte_prevue", models.DateField(blank=True, null=True)),
                ("date_recolte_reelle", models.DateField(blank=True, null=True)),
                ("statut", models.CharField(choices=[("planifiee", "Planifiée"), ("en_cours", "En cours"), ("recoltee", "Récoltée"), ("cloturee", "Clôturée")], default="planifiee", max_length=20)),
                ("rendement_prevu_qtl_ha", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campagnes_agricoles", to="authentication.company")),
                ("parcelle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campagnes", to="agriculture.parcelle")),
            ],
            options={
                "ordering": ["-date_creation"],
            },
        ),
        migrations.CreateModel(
            name="EtapeCampagne",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type_etape", models.CharField(choices=[("semis", "Semis"), ("traitement", "Traitement"), ("irrigation", "Irrigation"), ("desherbage", "Désherbage"), ("fertilisation", "Fertilisation"), ("recolte", "Récolte"), ("autre", "Autre")], max_length=20)),
                ("date", models.DateField()),
                ("description", models.TextField(blank=True, default="")),
                ("cout_mad", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="etapes_campagne_agricole", to="authentication.company")),
                ("campagne", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="etapes", to="agriculture.campagneculturale")),
                ("intrant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="etapes", to="agriculture.intrantagricole")),
            ],
            options={
                "ordering": ["date", "id"],
            },
        ),
        migrations.CreateModel(
            name="PointageAgricole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("travailleur_nom", models.CharField(blank=True, default="", max_length=255)),
                ("date", models.DateField()),
                ("tache", models.CharField(max_length=255)),
                ("nombre_journees", models.DecimalField(decimal_places=2, max_digits=6)),
                ("taux_journalier_mad", models.DecimalField(decimal_places=2, max_digits=10)),
                ("employe_id", models.IntegerField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pointages_agricoles", to="authentication.company")),
                ("equipe", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pointages", to="agriculture.equipesaisonniere")),
                ("campagne", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pointages", to="agriculture.campagneculturale")),
                ("parcelle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pointages", to="agriculture.parcelle")),
            ],
            options={
                "ordering": ["-date", "-id"],
            },
        ),
    ]
