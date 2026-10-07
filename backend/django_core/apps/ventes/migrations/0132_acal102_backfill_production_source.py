"""ACAL102 — backfill de ``etude_params['production_source']`` : AUCUN chiffre
imprimé d'un devis existant ne bouge.

Avant ACAL101/102, le moteur de devis (``quote_engine/builder.py``,
``_est_la_figure_du_calepinage`` au commit 818241faa) DEVINAIT qu'une figure
d'étude venait du calepinage par égalité ``int(round(stockée)) ==
int(round(layout))`` et la recalait alors sur les lignes. Il lit désormais la
MARQUE ``production_source``. Cette migration pose la marque sur chaque devis
existant (toutes sociétés, tous statuts) pour lequel l'ancienne heuristique
recalait : le rendu d'aujourd'hui est reproduit à l'identique.

Règle (copiée ici, aucun import de code applicatif — modèles historiques) :
pour chacune des deux figures (``production_annuelle`` ↔ ``result.annualKwh``,
``economies_annuelles`` ↔ ``result.savings``) présentes des DEUX côtés,
l'ancienne égalité dit « recalée » ou « souveraine ». La marque est posée
quand au moins une figure était recalée ET aucune ne l'était pas (la marque
couvre les deux figures). Un cas MIXTE (l'une recalée, l'autre non) n'est pas
représentable par une marque unique : il reste non marqué et la commande
``dryrun_acal102`` le liste.

Réversible : le retour retire ``production_source`` des seuls devis marqués
par cette migration (``production_source_backfill``).
"""
from django.db import migrations

#: Les deux figures que l'ancien moteur recalait, et leur clé du layout.
FIGURES = (('production_annuelle', 'annualKwh'),
           ('economies_annuelles', 'savings'))

MARQUE = 'production_source'
DRAPEAU = 'production_source_backfill'


def ancienne_egalite(valeur_stockee, valeur_layout):
    """``_est_la_figure_du_calepinage`` (builder.py @ 818241faa), mot pour
    mot."""
    try:
        return (int(round(float(valeur_stockee)))
                == int(round(float(valeur_layout))))
    except (TypeError, ValueError):
        return False


def verdicts_anciens(etude_params, roof_layout):
    """``{cle: True (recalée) | False (souveraine)}`` pour chaque figure que
    l'ancien moteur JUGEAIT (stockée et figure du layout toutes deux
    présentes) — exactement les conditions de l'ancienne boucle."""
    if not roof_layout:
        return {}
    resultat = ((roof_layout.get('result') or {})
                if isinstance(roof_layout, dict) else {})
    etude = etude_params if isinstance(etude_params, dict) else {}
    verdicts = {}
    for cle, cle_layout in FIGURES:
        brut = resultat.get(cle_layout)
        if not brut:  # l'ancienne boucle : ``if not _brut: continue``
            continue
        if not etude.get(cle):
            continue  # l'ancien moteur COMPLÉTAIT : inchangé aujourd'hui
        verdicts[cle] = ancienne_egalite(etude.get(cle), brut)
    return verdicts


def doit_marquer(etude_params, roof_layout):
    """La marque reproduit l'ancien rendu : au moins une figure recalée et
    aucune souveraine (sans marque déjà posée)."""
    etude = etude_params if isinstance(etude_params, dict) else {}
    if etude.get(MARQUE):
        return False
    verdicts = verdicts_anciens(etude, roof_layout)
    return bool(verdicts) and all(verdicts.values())


def est_mixte(etude_params, roof_layout):
    """Une figure recalée ET une souveraine : non représentable."""
    verdicts = verdicts_anciens(etude_params, roof_layout)
    return len(set(verdicts.values())) > 1


def marquer(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    lignes = (Devis.objects.exclude(roof_layout__isnull=True)
              .only('pk', 'etude_params', 'roof_layout')
              .iterator(chunk_size=500))
    for devis in lignes:
        if not doit_marquer(devis.etude_params, devis.roof_layout):
            continue
        etude = dict(devis.etude_params)
        etude[MARQUE] = 'calepinage'
        etude[DRAPEAU] = True
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)


def retirer(apps, schema_editor):
    Devis = apps.get_model('ventes', 'Devis')
    lignes = (Devis.objects.filter(**{f'etude_params__{DRAPEAU}': True})
              .only('pk', 'etude_params').iterator(chunk_size=500))
    for devis in lignes:
        etude = dict(devis.etude_params or {})
        etude.pop(DRAPEAU, None)
        etude.pop(MARQUE, None)
        Devis.objects.filter(pk=devis.pk).update(etude_params=etude)


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0131_ciq620_equipements_figes'),
    ]

    operations = [
        migrations.RunPython(marquer, retirer),
    ]
