"""SOL2(a) — retire la contrainte de clé étrangère `sante` devenue orpheline.

`NonConformite.cycle_sterilisation_id` est désormais une référence NON
CONTRAINTE (voir la migration 0057, réécrite) : `qhse` est gardé dans l'édition
solaire alors que `sante` en est parqué, et une contrainte référentielle vers
une table qu'une base vierge ne crée pas empêcherait `migrate` d'aboutir.

Cette migration est **DB-only et idempotente** :

* sur une base DÉJÀ migrée (production), la colonne existe avec l'ancienne
  contrainte de clé étrangère — on la retire, **sans toucher aux données** :
  chaque `cycle_sterilisation_id` déjà enregistré reste tel quel ;
* sur une base vierge, 0057 n'a créé aucune contrainte — le bloc ne trouve rien
  et ne fait rien ;
* sur un moteur non PostgreSQL, elle est inerte.

Réversible (no-op) : revenir en arrière ne recrée pas la contrainte, ce qui est
volontaire — la ré-appliquer exigerait que `sante` soit chargée.
"""
from django.db import migrations

_TABLE = 'qhse_nonconformite'
_COLONNE = 'cycle_sterilisation_id'

_SQL_TROUVER_CONTRAINTE = """
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    JOIN pg_attribute att
      ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
    WHERE con.contype = 'f'
      AND rel.relname = %s
      AND att.attname = %s
      AND nsp.nspname = ANY(current_schemas(false))
"""


def _retirer_contrainte(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(_SQL_TROUVER_CONTRAINTE, [_TABLE, _COLONNE])
        noms = [ligne[0] for ligne in cursor.fetchall()]
        for nom in noms:
            cursor.execute(
                'ALTER TABLE {} DROP CONSTRAINT IF EXISTS {}'.format(
                    connection.ops.quote_name(_TABLE),
                    connection.ops.quote_name(nom)))


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0057_ntsan23_ncr_cycle_sterilisation'),
    ]

    operations = [
        migrations.RunPython(
            _retirer_contrainte,
            migrations.RunPython.noop,
            elidable=False,
        ),
    ]
