"""AUD137 — UNE seule intention de paiement `initie` par (société, facture).

``PortailClientFactures.jsx`` → ``MesFacturesPortailViewSet.payer`` créait un
``PaiementFacturePortail`` INCONDITIONNEL à chaque appel (``views_client.py``),
sans jamais chercher une intention ``initie`` existante, et le montant était
figé au ``facture.montant_du`` du moment du clic. Le défaut était aggravé par
une facture ANNULÉE présentée comme « payable » (``Facture.montant_du`` ignore
le statut) : trois clics sur « Payer » empilaient trois intentions du même
client pour la même facture, à des montants divergents, dans la file de
rapprochement.

Cette migration :

1. DÉDOUBLONNE les intentions ``initie`` existantes par (company, facture) :
   pour chaque groupe en double, on GARDE la plus ANCIENNE (plus petit id) et
   on supprime les autres. Une intention ``initie`` ne porte AUCUN paiement
   réel — tant que ``CMI_ENABLED`` est OFF, ``initier_paiement_facture`` ne
   fait aucun appel réseau (compta/services.py) — sa suppression ne perd donc
   aucun argent. Les intentions déjà ``paye``/``echoue`` ne sont jamais
   touchées : elles ne violent pas la contrainte, qui ne porte que sur
   ``statut='initie'``.
2. Pose une contrainte PARTIELLE ``UniqueConstraint(['company', 'facture'],
   condition=Q(statut='initie'))`` : ``views_client.payer`` peut désormais
   réutiliser l'intention existante par ``get_or_create`` sans jamais risquer
   d'en créer une seconde sous course (double-clic).

Réversible : la contrainte se retire ; le dédoublonnage est une suppression
de données et sa réciproque est un no-op déclaré (les doublons n'ont pas à
être ressuscités — ils étaient le défaut).
"""
from django.db import migrations, models


def _dedoublonner(apps, schema_editor):
    Paiement = apps.get_model('portail', 'PaiementFacturePortail')
    db = schema_editor.connection.alias

    groupes = (
        Paiement.objects.using(db)
        .filter(statut='initie')
        .exclude(facture_id__isnull=True)
        .values('company_id', 'facture_id')
        .annotate(n=models.Count('id'))
        .filter(n__gt=1)
    )
    for groupe in groupes:
        lignes = list(
            Paiement.objects.using(db)
            .filter(company_id=groupe['company_id'],
                    facture_id=groupe['facture_id'], statut='initie')
            .order_by('id')
        )
        gardee = lignes[0]
        (Paiement.objects.using(db)
         .filter(company_id=groupe['company_id'],
                 facture_id=groupe['facture_id'], statut='initie')
         .exclude(id=gardee.id)
         .delete())


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0005_aud145_uniq_acceptation_portail_devis'),
    ]

    operations = [
        migrations.RunPython(_dedoublonner, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='paiementfactureportail',
            constraint=models.UniqueConstraint(
                fields=('company', 'facture'),
                condition=models.Q(statut='initie'),
                name='uniq_paiement_portail_facture_initie'),
        ),
    ]
