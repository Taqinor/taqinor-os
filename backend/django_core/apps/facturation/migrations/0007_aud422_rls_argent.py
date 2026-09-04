"""AUD422 — Row Level Security Postgres sur ``ventes_facture`` et
``ventes_paiement``.

Volet ``facturation`` du premier lot RLS « tables argent » (voir la docstring
détaillée de ``apps/compta/migrations/0126_aud422_rls_argent.py`` : mêmes
garanties, même générateur SQL unique ``core.rls.enable_sql``, même absence
d'effet tant que le rôle applicatif NOBYPASSRLS n'est pas en service).

Les tables gardent leurs noms historiques ``ventes_*`` (``db_table`` explicite,
ODX17) alors que les modèles vivent ici : la policy est posée sur la TABLE,
donc les deux noms coexistent sans ambiguïté.

À SAVOIR — ``Paiement.company`` est NULLABLE. Une policy
``company_id = current_setting(...)`` ne matche JAMAIS une ligne à
``company_id`` NULL : sous le rôle applicatif, un paiement hérité sans société
deviendrait invisible. C'est le comportement fail-closed voulu (une ligne
d'argent sans tenant ne doit appartenir à personne), mais c'est à VÉRIFIER en
staging avant d'activer ``POSTGRES_RLS_ENABLED``/``DB_APP_USER`` :
``SELECT COUNT(*) FROM ventes_paiement WHERE company_id IS NULL;`` doit valoir
0, sinon rattacher ces lignes AVANT la bascule de rôle.

RÉVERSIBLE : ``python manage.py migrate facturation 0006``. NO-OP hors
PostgreSQL.
"""
from django.db import migrations

from core import rls

LABELS = ('facturation.Facture', 'facturation.Paiement')

appliquer, revenir = rls.migration_functions(LABELS)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0006_aud188_paiement_contre_passation'),
    ]

    operations = [
        migrations.RunPython(appliquer, revenir),
    ]
