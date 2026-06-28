"""DC17 — ``CustomUser.poste`` (texte libre) → référentiel ``rh.Poste`` (FG160).

Ajoute un FK nullable ``poste_ref`` (vers ``rh.Poste``, SET_NULL) puis backfill
non destructif : par société, déduplique les intitulés distincts en lignes
``rh.Poste`` et y rattache les comptes. La colonne texte ``poste`` est CONSERVÉE
intacte — la migration est entièrement réversible (le sens inverse détache les
FK, sans rien supprimer du texte legacy).
"""
import django.db.models.deletion
from django.db import migrations, models

from authentication.poste_sync import backfill_poste_ref


def backfill(apps, schema_editor):
    User = apps.get_model('authentication', 'CustomUser')
    Poste = apps.get_model('rh', 'Poste')
    backfill_poste_ref(User, Poste)


def unbackfill(apps, schema_editor):
    """Réversible sans perte : on détache les ``poste_ref`` posés par ce
    backfill (le texte ``poste`` legacy reste la source). On NE supprime PAS les
    lignes ``rh.Poste`` créées — elles peuvent déjà être consommées ailleurs
    (DossierEmploye, organigramme) ; les retirer serait destructif."""
    User = apps.get_model('authentication', 'CustomUser')
    User.objects.exclude(poste_ref__isnull=True).update(poste_ref=None)


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0007_dossieremploye_date_sortie_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="poste_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="auth_users",
                to="rh.poste",
            ),
        ),
        migrations.RunPython(backfill, unbackfill),
    ]
