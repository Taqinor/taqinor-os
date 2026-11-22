"""R4-02 (recette en direct du 22/11/2026) — « nouveaux rendus seulement » pour
l'étiquette de la consommation sur la couverture du PDF industriel.

Le moteur étiquetait « d'après vos kWh déclarés » une consommation CONVERTIE
d'une facture en dirhams (``facture_hiver_mad``, ``factures_mad`` en montants) ;
il dit désormais « consommation estimée à partir de votre facture en dirhams »
(``quote_engine/ci/synthese.py::_bloc_baseline_source``). Un devis déjà envoyé
garde ce que le client a reçu : cette migration pose le drapeau de rendu
``etude_params['regles_source_conso_historique'] = True`` sur tout devis
commercial / industriel NON brouillon (même critère que 0159 : tout sauf les
brouillons jamais envoyés) dont l'étude existe ; le moteur lui garde l'ancienne
étiquette. Le niveau de règles n'est pas utilisé : un niveau 16 courant
activerait le niveau 15 (déclaré, pas courant).

Seule la clé du drapeau est écrite (``update`` : ni ``updated_at``, ni jeton
d'édition, ni statut, ni autre clé de l'étude). Aucun import de code
applicatif (modèles historiques). Réversible : le retour retire le drapeau.
"""
from django.db import migrations

DRAPEAU = 'regles_source_conso_historique'
SEGMENTS_CI = ('commercial', 'industriel')


def doit_marquer(etude_params, mode_installation):
    """Une étude non vide d'un devis C&I (ou portant une étude C&I)."""
    if not isinstance(etude_params, dict) or not etude_params:
        return False
    if etude_params.get(DRAPEAU):
        return False
    mode = (mode_installation or '').strip().lower()
    return mode in SEGMENTS_CI or 'etude_ci' in etude_params


def marquer(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    lignes = (Devis.objects.exclude(statut='brouillon', date_envoi__isnull=True)
              .exclude(etude_params__isnull=True)
              .only('pk', 'etude_params', 'mode_installation')
              .order_by('pk').iterator(chunk_size=500))
    for devis in lignes:
        if not doit_marquer(devis.etude_params, devis.mode_installation):
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
        ('ventes', '0159_regles_calcul_niveau_14'),
    ]

    operations = [
        migrations.RunPython(marquer, retirer),
    ]
