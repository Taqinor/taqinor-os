# NTCRM21 — Token d'accès dédié au portail apporteur (lecture seule).
#
# Migration en 3 TEMPS (YDATA/check_migration_safety, ADDFIELD_UNIQUE_ONESHOT) :
# `Apporteur` est créé par la migration 0071, donc dans un environnement qui a
# déjà appliqué 0071 la table peut contenir des lignes. Un
# `AddField(unique=True)` en un seul temps y poserait un index UNIQUE sur une
# table peuplée dont toutes les lignes valent NULL — toléré par Postgres, mais
# il laisserait chaque apporteur existant SANS jeton (portail mort jusqu'au
# prochain `save()`). On fait donc :
#   1. ajout NULLABLE sans contrainte ;
#   2. `RunPython` de remplissage — un `secrets.token_urlsafe(32)` DISTINCT par
#      ligne (jamais une constante partagée : ce jeton est le SEUL secret
#      d'accès à `GET /apporteur-portail/<token>/mes-deals/`), idempotent
#      (ne touche que les lignes sans jeton) et donc rejouable ;
#   3. `AlterField(unique=True)` une fois toutes les valeurs distinctes posées.
import secrets

from django.db import migrations, models

TOKEN_BYTES = 32


def _remplir_tokens(apps, schema_editor):
    """Pose un jeton distinct sur chaque apporteur qui n'en a pas encore.

    Idempotent : rejouable sans écraser un jeton déjà attribué. Fonctionne sur
    une table non vide comme sur une table vide.
    """
    Apporteur = apps.get_model('crm', 'Apporteur')
    db = schema_editor.connection.alias
    qs = Apporteur.objects.using(db)

    # Jetons déjà en base (si la migration est rejouée après un remplissage
    # partiel) — garantit l'unicité globale avant de poser l'index UNIQUE.
    deja_pris = set(
        qs.exclude(token_acces__isnull=True)
        .exclude(token_acces='')
        .values_list('token_acces', flat=True)
    )

    a_remplir = qs.filter(token_acces__isnull=True) | qs.filter(token_acces='')
    for apporteur in a_remplir.only('pk', 'token_acces').iterator():
        token = secrets.token_urlsafe(TOKEN_BYTES)
        while token in deja_pris:  # collision ~impossible (256 bits), mais on ne parie pas dessus
            token = secrets.token_urlsafe(TOKEN_BYTES)
        deja_pris.add(token)
        qs.filter(pk=apporteur.pk).update(token_acces=token)


def _vider_tokens(apps, schema_editor):
    """Reverse : on remet le champ à NULL (l'étape 1 le supprimera ensuite)."""
    Apporteur = apps.get_model('crm', 'Apporteur')
    db = schema_editor.connection.alias
    Apporteur.objects.using(db).update(token_acces=None)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0071_apporteur_deal_enregistre'),
    ]

    operations = [
        # 1 — ajout nullable, SANS contrainte d'unicité.
        migrations.AddField(
            model_name='apporteur',
            name='token_acces',
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                verbose_name="Token d'accès portail"),
        ),
        # 2 — remplissage avec des valeurs DISTINCTES.
        migrations.RunPython(_remplir_tokens, _vider_tokens),
        # 3 — l'unicité, une fois les valeurs posées.
        migrations.AlterField(
            model_name='apporteur',
            name='token_acces',
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                unique=True, verbose_name="Token d'accès portail"),
        ),
    ]
