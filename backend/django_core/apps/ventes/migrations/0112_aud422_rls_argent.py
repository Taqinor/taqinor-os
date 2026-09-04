"""AUD422 — Row Level Security Postgres sur la table ``ventes_devis``.

Volet ``ventes`` du premier lot RLS « tables argent » (voir la docstring
détaillée de ``apps/compta/migrations/0126_aud422_rls_argent.py`` : mêmes
garanties, même générateur SQL unique ``core.rls.enable_sql``, même absence
d'effet tant que le rôle applicatif NOBYPASSRLS n'est pas en service).

``Facture`` et ``Paiement`` ne sont PAS ici : elles vivent dans l'app
``facturation`` depuis ODX17 (``apps.ventes.models`` n'en garde qu'un
ré-export), et la chaîne de migrations de chaque app reste mono-écrivain —
leur volet est ``apps/facturation/migrations/0007_aud422_rls_argent.py``.

RÉVERSIBLE : ``python manage.py migrate ventes 0110``. NO-OP hors PostgreSQL.
"""
from django.db import migrations

from core import rls

LABELS = ('ventes.Devis',)

appliquer, revenir = rls.migration_functions(LABELS)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0111_aud107_notedebit_remise_globale'),
    ]

    operations = [
        migrations.RunPython(appliquer, revenir),
    ]
