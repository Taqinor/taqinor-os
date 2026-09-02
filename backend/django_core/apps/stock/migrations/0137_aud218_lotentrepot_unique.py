"""AUD218 — unicité (company, produit, numero_lot) sur ``stock.LotEntrepot``.

``services.alimenter_lot_entrepot`` fait un
``get_or_create(company, produit, numero_lot)`` alors qu'AUCUNE contrainte ne
portait sur ce triplet (``Meta`` ne déclarait que deux Index NON uniques) :
deux confirmations de réception concurrentes du MÊME lot créaient DEUX
``LotEntrepot`` distincts — la course documentée de ``get_or_create`` — et la
traçabilité du lot se scindait en silence (FEFO, rappels, blocages qualité ne
voyant chacun qu'une moitié du lot).

DEUX MOITIÉS, DANS CET ORDRE (même patron que 0134 + 0135) :

1. ``fusionner_lots_doublons`` — nettoie les données AVANT la contrainte (sans
   quoi la migration échouerait sur une base en portant). Deux lignes de même
   ``(company, produit, numero_lot)`` décrivent le MÊME lot physique : on garde
   la plus ANCIENNE (plus petit ``pk``), on lui ADDITIONNE les quantités des
   suivantes, on complète sa ``date_peremption``/``emplacement`` si elle était
   vide, on REPOINTE vers elle les quatre références WMS
   (``LignePicking``, ``UniteLogistiqueLigne``, ``AlerteRappel``,
   ``BlocageQualite`` — toutes en ``SET_NULL``, donc jamais orphelines) puis on
   supprime les doublons devenus vides de sens. Aucune quantité n'est perdue :
   le total du lot est strictement conservé. Un résumé est imprimé pendant le
   ``migrate`` (visible dans le log de déploiement).

2. ``AddConstraint`` NU (pas de ``concurrent_index_migration``/YOPSB6) : une
   ``UniqueConstraint`` déclarée dans ``Meta`` DOIT être posée par
   ``AddConstraint`` pour que l'état Django reste aligné sur ``models.py`` ;
   ``stock_lotentrepot`` est une table de registre (quelques lignes par
   réception portant un numéro de lot), pas une table de flux.

RÉVERSIBILITÉ : la contrainte se retire sans perte
(``RemoveConstraint``, auto-généré) ; la FUSION, elle, est irréversible par
nature (on ne peut pas ré-inventer une scission accidentelle) — son sens
inverse est donc un no-op explicite.
"""
from django.db import migrations, models


def fusionner_lots_doublons(apps, schema_editor):
    LotEntrepot = apps.get_model('stock', 'LotEntrepot')
    # Les quatre porteurs d'une FK vers LotEntrepot (toutes SET_NULL) : on les
    # repointe sur le survivant AVANT toute suppression.
    porteurs = [apps.get_model('stock', nom) for nom in (
        'LignePicking', 'UniteLogistiqueLigne', 'AlerteRappel',
        'BlocageQualite')]

    survivants = {}   # (company_id, produit_id, numero_lot) -> pk du survivant
    fusions = []
    # ``pk`` croissant : le lot le plus ancien d'un triplet est vu en premier
    # et devient le survivant. ``iterator`` (jamais de ``.update()`` global) —
    # patron check_safe_migrations.
    for lot in LotEntrepot.objects.order_by(
            'company_id', 'produit_id', 'numero_lot', 'pk').iterator(
                chunk_size=500):
        cle = (lot.company_id, lot.produit_id, lot.numero_lot)
        if cle not in survivants:
            survivants[cle] = lot.pk
            continue

        survivant = LotEntrepot.objects.get(pk=survivants[cle])
        survivant.quantite_recue = (
            (survivant.quantite_recue or 0) + (lot.quantite_recue or 0))
        survivant.quantite_restante = (
            (survivant.quantite_restante or 0) + (lot.quantite_restante or 0))
        if not survivant.date_peremption and lot.date_peremption:
            survivant.date_peremption = lot.date_peremption
        if not survivant.emplacement_id and lot.emplacement_id:
            survivant.emplacement_id = lot.emplacement_id
        survivant.save(update_fields=[
            'quantite_recue', 'quantite_restante', 'date_peremption',
            'emplacement'])

        for porteur in porteurs:
            for obj in porteur.objects.filter(lot_id=lot.pk).iterator(
                    chunk_size=500):
                obj.lot_id = survivant.pk
                obj.save(update_fields=['lot'])

        fusions.append((lot.pk, survivant.pk, lot.numero_lot))
        lot.delete()

    if fusions:
        print(f"\nstock.0137 — {len(fusions)} lot(s) dupliqué(s) fusionné(s) "
              "dans leur lot d'origine (quantités additionnées, aucune perte) :")
        for pk, survivant_pk, numero in fusions:
            print(f"  lot #{pk} « {numero} » -> lot #{survivant_pk}")
    else:
        print("\nstock.0137 — aucun lot dupliqué "
              "(company, produit, numero_lot) trouvé.")


def sens_inverse(apps, schema_editor):
    """Une fusion de lots ne se défait pas : no-op explicite."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0136_qjr137_rendement_ar_batterie'),
    ]

    operations = [
        migrations.RunPython(fusionner_lots_doublons, sens_inverse),
        migrations.AddConstraint(
            model_name='lotentrepot',
            constraint=models.UniqueConstraint(
                fields=('company', 'produit', 'numero_lot'),
                name='lotentrepot_unique_company_produit_lot'),
        ),
    ]
