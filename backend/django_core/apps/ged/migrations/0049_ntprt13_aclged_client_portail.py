# NTPRT13 — "Mes documents" (GED partagée) : le principal d'une entrée ACL
# peut désormais être un `crm.Client` (portail) en plus d'un utilisateur ou
# d'un rôle — un document/dossier partagé avec un CLIENT est visible par TOUS
# ses comptes portail (NTPRT6 peut en multiplier plusieurs), sans dupliquer
# le modèle de partage (réutilise `AclGed` tel quel, colonne additive).
#
# String-FK ('crm.Client', db_constraint=False) : jamais un import de
# `apps.crm.models` (contrat CI `ged-models-decoupled`).
#
# La contrainte `ged_acl_principal_required` (au moins un principal) est
# REMPLACÉE par `ged_acl_principal_required_v2` (utilisateur OU rôle OU
# client) — additive et rétro-compatible : toute ligne existante (qui porte
# déjà utilisateur ou rôle) continue de satisfaire la nouvelle contrainte.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ged", "0048_guide_visite_suivi_commercial"),
    ]

    operations = [
        migrations.AddField(
            model_name="aclged",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ged_acls",
                to="crm.client",
                verbose_name="client (portail)",
            ),
        ),
        migrations.AddIndex(
            model_name="aclged",
            index=models.Index(fields=["client"], name="ged_acl_client_idx"),
        ),
        migrations.RemoveConstraint(
            model_name="aclged",
            name="ged_acl_principal_required",
        ),
        migrations.AddConstraint(
            model_name="aclged",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(utilisateur__isnull=False)
                    | models.Q(role__isnull=False)
                    | models.Q(client__isnull=False)
                ),
                name="ged_acl_principal_required_v2",
            ),
        ),
    ]
