"""BATHOMO (fondateur 26/08/2026) — LE PLAFOND DE MODULES PAR BANQUE.

« add it as parameter... for now keep it very high for 5kwh — maybe 200 » :
un PLAFOND fondateur-éditable du nombre de modules IDENTIQUES qu'une même
banque batterie peut empiler pour un produit donné (une limite fabricant
d'assemblage série/parallèle — jamais une limite inventée par le moteur).
``bat_max_modules_par_banc`` rejoint le bloc BATTERIE de ``FicheTechnique``,
lu par ``apps.ventes.services.composition_residentielle`` pour REJETER (pas
tronquer) une banque candidate qui exigerait plus de modules que ce plafond.

Additif pur, ``null=True``/``blank=True`` : aucune fiche existante n'est
impactée par le schéma — ``None`` reste ILLIMITÉ, byte-identique à
l'historique où aucun produit n'était borné.

LE REMPLISSAGE, MÊME PATRON QUE 0130/0125 : ``seed_catalogue`` tourne au
déploiement pour UNE SEULE société — cette migration comble la valeur
fondateur (200 sur le Dyness 5 kWh, ``FICHES_TECHNIQUES['BAT-DEY-5']``,
importée, jamais recopiée) sur TOUTES les sociétés, mais SEULEMENT le champ
actuellement vide. Une valeur déjà saisie par le fondateur n'est JAMAIS
touchée, et aucune fiche n'est CRÉÉE ici (contrairement à 0125) : ce lot
n'ajoute qu'une colonne à des fiches qui existent déjà.

GARDE DE ROBUSTESSE (identique à 0125/0130) : si le dictionnaire ou la garde
a été renommé côté seeder, l'import échoue et la migration ne fait RIEN
plutôt que de casser un déploiement.

RÉVERSIBLE : non — ``noop``. Même doctrine que 0125/0126/0127/0130 : on ne
peut pas distinguer après coup un champ comblé ici d'une saisie postérieure.
"""
from django.db import migrations, models

_CHAMP = 'bat_max_modules_par_banc'


def combler_max_modules_par_banc(apps, schema_editor):
    """Comble ``bat_max_modules_par_banc``, VIDE UNIQUEMENT, depuis le seeder."""
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
        if _CHAMP not in valeurs:
            continue
        # SKU apparié à travers TOUTES les sociétés (``Produit`` est scopé
        # par société) — même règle multi-tenant que 0125/0130.
        for fiche in FicheTechnique.objects.filter(
                produit__sku=sku).iterator():
            if _fiche_champ_vide(getattr(fiche, _CHAMP, None)):
                setattr(fiche, _CHAMP, valeurs[_CHAMP])
                fiche.save(update_fields=[_CHAMP])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0131_prix_fondateur_bat5_deye5m'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_max_modules_par_banc',
            field=models.PositiveIntegerField(blank=True, help_text='Nombre MAXIMUM de modules identiques dans une même banque. Vide = illimité.', null=True),
        ),
        migrations.RunPython(combler_max_modules_par_banc,
                             migrations.RunPython.noop),
    ]
