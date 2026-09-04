"""AUD145 — UNE seule preuve d'acceptation portail par (société, devis).

``portail/views_client.accepter`` posait la trace FG229 par
``AcceptationDevisPortail.objects.get_or_create(company=…, devis=…)`` HORS
transaction et APRÈS ``ventes.services.accept_devis``. Le verrou anti-course
d'``accept_devis`` (``select_for_update`` sur le groupe de variantes) protège
le DEVIS : le second POST devient bien un no-op idempotent sur le statut, mais
il retombe quand même sur ce ``get_or_create``. Or ``Meta`` ne déclarait
AUCUNE contrainte (là où ``ComptePortailClient`` porte
``uniq_compte_portail_client``) : un double-clic du client sur « J'accepte »
produisait DEUX preuves d'acceptation du même devis, avec deux horodatages —
une pièce juridique ambiguë.

Cette migration :

1. DÉDOUBLONNE l'existant (``_dedoublonner``). Pour chaque groupe
   (company, devis) en double, on GARDE la ligne SIGNÉE la plus ancienne
   (``signe_le`` non nul, plus petit ``id``) — c'est l'acceptation réelle ; à
   défaut, la plus ancienne tout court. Les autres sont supprimées. Les lignes
   à ``devis`` NULL ne sont jamais touchées (elles ne violent pas la
   contrainte : en PostgreSQL les NULL restent distincts).
2. Pose ``UniqueConstraint(['company', 'devis'])``.

Réversible : la contrainte se retire ; le dédoublonnage, lui, est une
suppression de données et sa réciproque est un no-op déclaré (les doublons
n'ont pas à être ressuscités — ils étaient le défaut).
"""
from django.db import migrations, models


def _dedoublonner(apps, schema_editor):
    Acceptation = apps.get_model('portail', 'AcceptationDevisPortail')
    db = schema_editor.connection.alias

    groupes = (
        Acceptation.objects.using(db)
        .exclude(devis_id__isnull=True)
        .values('company_id', 'devis_id')
        .annotate(n=models.Count('id'))
        .filter(n__gt=1)
    )
    for groupe in groupes:
        lignes = list(
            Acceptation.objects.using(db)
            .filter(company_id=groupe['company_id'],
                    devis_id=groupe['devis_id'])
            .order_by('id')
        )
        signees = [ligne for ligne in lignes if ligne.signe_le is not None]
        gardee = (signees or lignes)[0]
        (Acceptation.objects.using(db)
         .filter(company_id=groupe['company_id'],
                 devis_id=groupe['devis_id'])
         .exclude(id=gardee.id)
         .delete())


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0004_ydata2_protect_paiement_acceptation'),
    ]

    operations = [
        migrations.RunPython(_dedoublonner, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='acceptationdevisportail',
            constraint=models.UniqueConstraint(
                fields=('company', 'devis'),
                name='uniq_acceptation_portail_devis'),
        ),
    ]
