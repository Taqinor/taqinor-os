"""YDATA2 — argent et preuve légale du portail : ``SET_NULL`` -> ``PROTECT``.

Revue des suppressions financières sur les deux FK posées par WIR95
(``portail/0003_wir95_fk_references``), toutes deux ``SET_NULL`` :

1. ``PaiementFacturePortail.facture`` (-> ``facturation.Facture``). Supprimer
   une facture laissait une ligne de paiement portant un ``montant`` MAD réel
   — et parfois un ``statut='paye'`` — pointant sur RIEN : de l'argent
   orphelin, impossible à rapprocher. ``db_constraint=False`` fait qu'aucune
   protection base n'existait non plus.
2. ``AcceptationDevisPortail.devis`` (-> ``ventes.Devis``). Supprimer un devis
   orphelinait la preuve d'acceptation électronique du client (nom du
   signataire, IP, horodatage — preuve loi 53-05) : l'enregistrement ne disait
   plus QUEL devis avait été signé.

C'est atteignable en production : ``DELETE /api/django/ventes/devis/<id>/`` est
un endpoint LIVE (rôle admin, ModelViewSet complet, aucune suppression douce) ;
le côté facture est comparable. ``PROTECT`` refuse désormais la suppression
tant qu'un paiement / une acceptation la référence — même patron que
``ventes/0090_ydata2_protect_dossier_devis`` (``RegulatoryDossier.devis``,
``SubventionDossier.devis``) et que ``FactureSource.devis``.

PROTECT EST BIEN APPLIQUÉ MALGRÉ ``db_constraint=False`` : ``on_delete`` est
appliqué par le *collector* de Django (``django/db/models/deletion.py`` —
``Collector.collect()`` interroge les objets liés via l'ORM puis appelle
``PROTECT``, qui lève ``ProtectedError``), jamais par la base. ``db_constraint``
ne pilote QUE la pose (ou non) de la contrainte ``FOREIGN KEY`` physique : il
n'a aucune influence sur le collector. Les deux champs restent donc
``db_constraint=False`` (règle CLAUDE.md de découplage cross-app des apps
domaine) et gardent leur ``null=True``/``blank=True`` d'origine. Vérifié par
les tests de régression ``apps/portail/tests/test_wir95_fk_references.py``
(``assertRaises(ProtectedError)`` + les deux lignes toujours présentes après
coup).

Changement d'``on_delete`` uniquement : opération d'ÉTAT, AUCUN SQL émis (Django
range ``on_delete`` dans ``Field.non_db_attrs``, donc
``BaseDatabaseSchemaEditor._field_should_be_altered`` renvoie False et
``alter_field`` ne produit rien), aucune donnée touchée — RÉVERSIBLE à
l'identique (``migrate portail 0003`` rétablit ``SET_NULL``, sans SQL ni perte).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0003_wir95_fk_references'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acceptationdevisportail',
            name='devis',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='acceptations_portail', to='ventes.devis',
                verbose_name='Devis'),
        ),
        migrations.AlterField(
            model_name='paiementfactureportail',
            name='facture',
            field=models.ForeignKey(
                blank=True, null=True, db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='paiements_portail', to='facturation.facture',
                verbose_name='Facture'),
        ),
    ]
