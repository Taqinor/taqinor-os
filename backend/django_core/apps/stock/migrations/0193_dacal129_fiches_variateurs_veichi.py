"""D-ACAL-129 (fondateur 25/11/2026, « Yes, 780 V for 380 V models ») — fiche
technique « variateur de pompage » des 15 variateurs VEICHI du catalogue, qui
n'en ont aucune en production : sans elle, le kit ne vérifie pas les chaînes PV
(``core.pompage.champ.fiche_saisie``).

Valeurs PUBLIÉES par le constructeur (copie FIGÉE, jamais importée du seeder) :
  · SI22 220 V — « si22-solar-pump-inverter-manual-simple-v1-0.pdf », §2,
    tableau p. 2 : entrée DC max 400 V, Voc recommandée 360-400 V ;
  · SI23 220 V (D3) — « si23-solar-pump-inverter-manual-complete.pdf », §1.4
    « Technical Specification » p. 4 : 450 V, Voc recommandée 360-430 V ;
  · SI23 380 V (D5, T3) — même tableau : 800 V imprimé, déclenchement logiciel
    de surtension à 780 VDC → 780 V retenu par le fondateur ; Voc recommandée
    620-750 V.
Fenêtre MPPT et courant d'entrée DC NON publiés : laissés vides.

Additive, idempotente, par société : une fiche est CRÉÉE seulement pour un
variateur (SKU, casse ignorée) qui n'a AUCUNE fiche — jamais une fiche
existante complétée ni réécrite. Le retour supprime les seules fiches qui
portent encore EXACTEMENT ce que la migration a écrit et rien d'autre.
"""
from decimal import Decimal

from django.db import migrations

_SI22_220 = {'ond_v_max_abs': Decimal('400.0'),
             'var_voc_reco_min_v': Decimal('360.0'),
             'var_voc_reco_max_v': Decimal('400.0')}
_SI23_220 = {'ond_v_max_abs': Decimal('450.0'),
             'var_voc_reco_min_v': Decimal('360.0'),
             'var_voc_reco_max_v': Decimal('430.0')}
_SI23_380 = {'ond_v_max_abs': Decimal('780.0'),
             'var_voc_reco_min_v': Decimal('620.0'),
             'var_voc_reco_max_v': Decimal('750.0')}

#: SKU → champs de la fiche ``variateur_pompage``.
FICHES = {
    'VEI-SI22-2.2-220': _SI22_220,
    'VEI-SI23-2.2-220': _SI23_220,
    **{'VEI-SI23-%s-380' % kw: _SI23_380 for kw in (
        '2.2', '4', '5.5', '7.5', '11', '15', '18', '22', '30', '37', '45',
        '55', '75')},
}
TYPE_FICHE = 'variateur_pompage'
_HORS_CONTENU = {'id', 'company', 'produit', 'date_creation', 'date_mise_a_jour'}


def _vide(champ, valeur):
    if valeur is None:
        return True
    if hasattr(valeur, 'name') and not isinstance(valeur, str):  # FieldFile
        return not valeur.name
    return valeur == '' or valeur == champ.get_default()


def fiche_de_la_migration(fiche, valeurs):
    """Vrai si ``fiche`` porte EXACTEMENT ce que la migration écrit (type et
    trois champs) et aucun autre champ renseigné."""
    if fiche.type_fiche != TYPE_FICHE:
        return False
    for champ in fiche._meta.concrete_fields:
        if champ.name in _HORS_CONTENU or champ.name == 'type_fiche':
            continue
        actuel = getattr(fiche, champ.name)
        if champ.name in valeurs:
            if actuel is None or Decimal(actuel) != valeurs[champ.name]:
                return False
        elif not _vide(champ, actuel):
            return False
    return True


def creer_fiches(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    for sku, valeurs in FICHES.items():
        for produit in Produit.objects.filter(sku__iexact=sku):
            if FicheTechnique.objects.filter(produit=produit).exists():
                continue
            FicheTechnique.objects.create(
                company_id=produit.company_id, produit=produit,
                type_fiche=TYPE_FICHE, **valeurs)


def supprimer_fiches(apps, schema_editor):
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    for sku, valeurs in FICHES.items():
        for fiche in FicheTechnique.objects.filter(
                produit__sku__iexact=sku, type_fiche=TYPE_FICHE):
            if fiche_de_la_migration(fiche, valeurs):
                fiche.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0192_dacal128_prix_parafoudre_ac'),
    ]

    operations = [
        migrations.RunPython(creer_fiches, supprimer_fiches),
    ]
