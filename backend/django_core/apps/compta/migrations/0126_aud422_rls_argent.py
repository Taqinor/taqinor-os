"""AUD422 — Row Level Security Postgres sur les DEUX tables argent de compta.

CE QUI N'AVAIT JAMAIS ÉTÉ FAIT. Toute l'infrastructure RLS existe depuis
NTPLT1/2/3 — GUC ``app.current_company`` posé en ``SET LOCAL``
(``core/tenant_context.py``, middleware déjà câblé), génération SQL par
introspection (``core/rls.py``), rôle applicatif NOBYPASSRLS
(``backend/db/rls_roles.sql``), bascule de rôle au runtime (``settings/base.py``)
— mais elle n'avait été appliquée à AUCUNE table : ``manage.py rls`` était
tout-ou-rien sur les ~1 280 tables company-scopées, donc le seul geste possible
était un big-bang que personne n'ose lancer. Décision fondateur : commencer par
les tables ARGENT, par migration.

CE QUE CETTE MIGRATION FAIT, EXACTEMENT. Pour ``compta_ecriturecomptable`` et
``compta_ligneecriture`` : ``ENABLE`` + ``FORCE ROW LEVEL SECURITY`` et une
policy ``company_id = current_setting('app.current_company')``. Le SQL vient de
``core.rls.enable_sql`` — la MÊME génération que ``manage.py rls``, jamais un
second générateur.

CE QU'ELLE NE CHANGE POUR PERSONNE AUJOURD'HUI. Un rôle SUPERUSER contourne RLS
inconditionnellement, et le rôle owner reçoit ``BYPASSRLS`` en production
(``rls_roles.sql``) : migrations, seeds, dumps, tests et le service applicatif
tant que ``POSTGRES_RLS_ENABLED``/``DB_APP_USER`` ne sont pas posés voient donc
exactement les mêmes lignes qu'avant. La policy ne mord que sous le rôle
applicatif ``app_rls`` (NOBYPASSRLS) — c'est le but : un filet SOUS le scoping
applicatif, qui reste en place et n'est JAMAIS retiré.

RÉVERSIBLE : ``python manage.py migrate compta 0125`` rejoue ``revert_sql``
(DROP POLICY + NO FORCE + DISABLE) et ramène les tables à leur état exact
d'avant. NO-OP hors PostgreSQL.
"""
from django.db import migrations

from core import rls

#: Les tables argent DE CETTE APP (le registre historique d'une migration ne
#: contient pas nécessairement les modèles des autres apps à ce point du plan).
LABELS = ('compta.EcritureComptable', 'compta.LigneEcriture')

appliquer, revenir = rls.migration_functions(LABELS)


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0125_aud188_contraintes_ligne_ecriture'),
    ]

    operations = [
        migrations.RunPython(appliquer, revenir),
    ]
