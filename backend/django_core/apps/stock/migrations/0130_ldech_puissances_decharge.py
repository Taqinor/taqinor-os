"""L-DECH (fondateur 24/08/2026) — LES PUISSANCES DE DÉCHARGE, ENFIN FICHÉES.

Deux ordres du même jour, un seul lot de champs :

  * « pour la décharge, source-la, mais en général c'est 100 A multiplié par
    les 52 V » → ``bat_max_decharge_kw`` sur la fiche BATTERIE. Le moteur
    horaire (L-GLITCH, ``apps/ventes/etude_horaire.py``) réclamait ce champ
    par son nom depuis sa livraison : sans décharge publiée il applique une
    règle conservatrice et laisse la pointe partir au réseau.
  * « mais l'onduleur aussi a un max de charge et de décharge, cherche bien
    et rajoute aussi ces numéros » → ``ond_bat_max_charge_kw`` /
    ``ond_bat_max_decharge_kw`` sur la fiche ONDULEUR. Le chemin batterie est
    borné par le PLUS PETIT des deux goulots : ``min(Σ packs, port onduleur)``,
    dans les deux sens.

Additif pur, les trois champs ``null=True``/``blank=True`` : aucune fiche
existante n'est impactée par le schéma.

LE REMPLISSAGE, LUI, NE PEUT PAS ATTENDRE LE SEEDER. ``seed_catalogue`` est
appelé au déploiement de façon NON BLOQUANTE et pour UNE SEULE société
(``$SEED_COMPANY_SLUG``) — c'est le trou que la migration 0125 a déjà dû
combler pour les fiches PVFCH. Même remède ici, et même garde : les valeurs
viennent EXCLUSIVEMENT du dictionnaire ``FICHES_TECHNIQUES`` du seeder
(importé, jamais recopié — un seul endroit à corriger si une datasheet est
révisée), et SEULS les champs actuellement vides sont comblés. Une valeur
déjà saisie par le fondateur, fût-elle fausse, n'est JAMAIS touchée, et
aucune fiche n'est CRÉÉE ici (contrairement à 0125) : ce lot ne fait
qu'ajouter trois colonnes à des fiches qui existent déjà.

GARDE DE ROBUSTESSE (identique à 0125) : si le dictionnaire ou la garde a été
renommé côté seeder, l'import échoue et la migration ne fait RIEN plutôt que
de casser un déploiement.

RÉVERSIBLE : non — ``noop``. Même doctrine que 0125/0126/0127 : on ne peut pas
distinguer après coup un champ comblé ici d'une saisie postérieure.
"""
from django.db import migrations, models

#: Les trois champs de ce lot — l'ordre n'a pas d'importance, la liste sert
#: uniquement à ne pas répéter les noms entre le schéma et le remplissage.
_CHAMPS = (
    'bat_max_decharge_kw',
    'ond_bat_max_charge_kw',
    'ond_bat_max_decharge_kw',
)


def combler_puissances_decharge(apps, schema_editor):
    """Comble les trois nouveaux champs, VIDES UNIQUEMENT, depuis le seeder."""
    try:
        from apps.stock.management.commands.seed_catalogue import (
            FICHES_TECHNIQUES, _fiche_champ_vide,
        )
    except ImportError:
        # Dictionnaire/garde renommés ou déplacés côté seeder — NO-OP plutôt
        # qu'une migration qui casse un déploiement.
        return

    FicheTechnique = apps.get_model('stock', 'FicheTechnique')

    for sku, valeurs in FICHES_TECHNIQUES.items():
        # Seuls les SKU qui portent au moins un des trois champs nous
        # concernent : les fiches module n'ont rien à recevoir ici.
        attendus = {champ: valeurs[champ] for champ in _CHAMPS
                    if champ in valeurs}
        if not attendus:
            continue
        # SKU apparié à travers TOUTES les sociétés (``Produit`` est scopé par
        # société) — même règle multi-tenant que 0125.
        for fiche in FicheTechnique.objects.filter(
                produit__sku=sku).iterator():
            combles = []
            for champ, valeur in attendus.items():
                if _fiche_champ_vide(getattr(fiche, champ, None)):
                    setattr(fiche, champ, valeur)
                    combles.append(champ)
            if combles:
                fiche.save(update_fields=combles)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0129_lforfait_tarif_au_panneau'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_max_decharge_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Puissance de décharge maximale (kW), par pack.', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_max_charge_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Puissance de CHARGE maximale du port batterie (kW). Onduleur hybride uniquement.', max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_bat_max_decharge_kw',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Puissance de DÉCHARGE maximale du port batterie (kW). Onduleur hybride uniquement.', max_digits=5, null=True),
        ),
        migrations.RunPython(combler_puissances_decharge,
                             migrations.RunPython.noop),
    ]
