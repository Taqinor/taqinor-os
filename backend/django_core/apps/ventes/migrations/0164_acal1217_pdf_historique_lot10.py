"""ACAL1217 / ACAL1266 (lot 10) — « nouveaux rendus seulement » pour deux
textes du PDF client, sur le patron de 0160 (R4-02).

* Le une-page imprime l'adresse jointe à la ville sans la répéter
  (« Quartier Founty, Agadir », plus « Agadir, Agadir ») et le téléphone mis en
  forme au résidentiel (« +212 6 12 34 56 78 ») —
  ``quote_engine/legacy_onepage.py::page_onepage``, ``ci/onepage.py``.
* Le PDF agricole cite une entrée du point d'eau déclarée et non mesurée sur
  UNE ligne « …, à confirmer par la visite » (plus deux listes) —
  ``quote_engine/agricole/pages.py::page1``.

Un devis déjà envoyé garde ce que le client a reçu : cette migration pose le
drapeau de rendu ``etude_params['regles_pdf_historique_lot10'] = True`` sur
tout devis NON brouillon (même critère que 0159 / 0160 : tout sauf les
brouillons jamais envoyés) dont l'étude n'est pas vide, quel que soit le
marché (le une-page sert tous les marchés). Une étude vide n'est pas écrite
(``a_etude`` du résumé de liste ne bouge pas) : le moteur rend lui aussi
l'ancien texte quand l'étude est vide (``ci/onepage.pdf_historique_lot10``).

Seule la clé du drapeau est écrite (``update`` : ni ``updated_at``, ni jeton
d'édition, ni statut, ni autre clé de l'étude). Aucun import de code
applicatif (modèles historiques). Réversible : le retour retire le drapeau.
"""
from django.db import migrations

DRAPEAU = 'regles_pdf_historique_lot10'


def doit_marquer(etude_params):
    """Une étude non vide, pas encore marquée."""
    if not isinstance(etude_params, dict) or not etude_params:
        return False
    return not etude_params.get(DRAPEAU)


def marquer(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    lignes = (Devis.objects.exclude(statut='brouillon', date_envoi__isnull=True)
              .exclude(etude_params__isnull=True)
              .only('pk', 'etude_params')
              .order_by('pk').iterator(chunk_size=500))
    for devis in lignes:
        if not doit_marquer(devis.etude_params):
            continue
        etude = dict(devis.etude_params)
        etude[DRAPEAU] = True
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)


def retirer(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    lignes = (Devis.objects.filter(**{f'etude_params__{DRAPEAU}': True})
              .only('pk', 'etude_params').order_by('pk').iterator(chunk_size=500))
    for devis in lignes:
        etude = dict(devis.etude_params or {})
        etude.pop(DRAPEAU, None)
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0163_adev162_total_affiche_range'),
    ]

    operations = [
        migrations.RunPython(marquer, retirer),
    ]
