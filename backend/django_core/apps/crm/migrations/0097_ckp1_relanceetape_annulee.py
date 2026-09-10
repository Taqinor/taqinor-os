"""CKP1 — « Annulée (moteur) » : la vérité des touches sautées.

DEUX MOITIÉS, toutes deux ADDITIVES (aucune contrainte posée, aucune colonne
supprimée — YDATA20 sans les trois temps) :

  1. le CHOIX ``annulee`` s'ajoute à ``RelanceEtape.statut`` (``AlterField``
     pur : ``choices`` ne touche pas le schéma Postgres, la colonne reste un
     ``varchar(10)``) ;
  2. une DATA MIGRATION rétrodate l'historique : les touches ``sautee`` qui
     portent un MOTIF DE MOTEUR CONNU passent à ``annulee`` et perdent leur
     ``traite_par`` (le moteur n'est pas un humain — c'est précisément ce que
     l'ancien code écrivait à tort).

POURQUOI RÉTRODATER. Sans cette moitié, la vue d'adhérence (CKP3) lirait
l'historique existant comme des milliers de « manquements » de Meryem alors
que ce sont des cadences que le moteur a arrêtées parce que le client avait
répondu, signé, ou refusé. Un KPI qui démarre faux ne se rattrape jamais.

LA LISTE DES MOTIFS EST FERMÉE, et c'est voulu. Ce sont les chaînes ÉCRITES
PAR LE CODE (``arreter_cadence`` et ses six déclencheurs, la reprise MRY23, le
placement MRY30) — jamais une heuristique sur du texte libre. Un saut dont la
note ne correspond à aucun motif moteur RESTE ``sautee`` : dans le doute, on
laisse la décision au compte de l'humain, jamais l'inverse.

RÉVERSIBLE. Le reverse remet ``sautee`` sur toutes les touches ``annulee`` —
le champ ``note`` porte le motif dans les deux sens, donc rien n'est perdu.
``traite_par`` ne peut pas être restauré (l'information n'existe plus) : c'est
assumé et documenté ici, elle était de toute façon FAUSSE.
"""
from django.db import migrations, models

#: Les motifs ÉCRITS PAR LE MOTEUR, en minuscules. Comparaison sur la note
#: normalisée (strip + casefold), jamais une correspondance partielle : deux
#: motifs distincts ne doivent pas se recouvrir.
MOTIFS_MOTEUR = (
    'joint',
    'refus au téléphone',
    'lead signé',
    'lead passé en froid',
    'devis accepté',
    'devis envoyé',
    'devis refusé',
    'reprise : déjà passée',
    'passée avant le moteur',
)


#: Taille des lots d'écriture. La table des touches de relance grossit d'une
#: dizaine de lignes par lead : un `.update()` global sur une base de
#: production la verrouillerait le temps de tout réécrire. On écrit par
#: tranches de pk, chacune en une transaction courte.
LOT = 1000


def _reecrire_par_lots(modele, filtres, valeurs):
    """Applique ``valeurs`` aux lignes de ``filtres``, par tranches de pk."""
    pks = list(modele.objects.filter(**filtres)
               .values_list('pk', flat=True).iterator(chunk_size=LOT))
    for debut in range(0, len(pks), LOT):
        modele.objects.filter(pk__in=pks[debut:debut + LOT]).update(**valeurs)
    return len(pks)


def basculer_vers_annulee(apps, schema_editor):
    RelanceEtape = apps.get_model('crm', 'RelanceEtape')
    # `note` est un TextField : la comparaison se fait en base sur la valeur
    # EXACTE (les motifs sont écrits tels quels par le code) — jamais un
    # `icontains`, qui ferait basculer un « pas joint » saisi à la main.
    _reecrire_par_lots(
        RelanceEtape,
        {'statut': 'sautee', 'note__in': list(MOTIFS_MOTEUR)},
        {'statut': 'annulee', 'traite_par': None})


def revenir_a_sautee(apps, schema_editor):
    """Reverse : tout ce qui est ``annulee`` redevient ``sautee``.

    ``traite_par`` reste NULL — l'acteur d'origine n'est plus connu, et il
    était de toute façon celui de l'ÉVÉNEMENT déclencheur, pas d'un saut."""
    RelanceEtape = apps.get_model('crm', 'RelanceEtape')
    _reecrire_par_lots(
        RelanceEtape, {'statut': 'annulee'}, {'statut': 'sautee'})


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0096_vt1_visite_terrain'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relanceetape',
            name='statut',
            field=models.CharField(
                choices=[('a_faire', 'À faire'), ('fait', 'Fait'),
                         ('sautee', 'Sautée'), ('annulee', 'Annulée (moteur)')],
                default='a_faire', max_length=10),
        ),
        migrations.RunPython(basculer_vers_annulee, revenir_a_sautee),
    ]
