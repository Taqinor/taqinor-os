"""R3-01 / R3-17 (Q2) — DRY-RUN : les documents déjà REMIS dont le résultat
rangé publie ses énergies sur la fenêtre ENTIÈRE (mode météo pluriannuel,
somme de N années au lieu de leur moyenne), à montrer au fondateur.

Une ligne par version remise (``records.Attachment`` rattachée au
calepinage, nom ``<code>__v<NNN>__<langue>[__<empreinte>].<ext>``,
``views/remise_document.py``) d'un calepinage dont le résultat rangé est
pluriannuel (N > 1) :

    société | calepinage | document remis | remis le | mode météo |
    années de la fenêtre | énergies rangées | calculé le

« énergies rangées » : ``fenêtre entière`` (arrivée de la cascade ≈ N × P50,
les kWh imprimés par le rapport d'étude et le diagramme de pertes sont faux
d'un facteur N), ``année moyenne`` (déjà juste) ou ``indéterminé``. Un
document remis AVANT le « calculé le » a été produit sur un calcul antérieur
dont le mode n'est plus lisible : la ligne le dit. Un calepinage pluriannuel
sans document remis est compté, pas listé.

LECTURE SEULE : aucun calepinage, aucun document n'est réécrit ni recalculé.

    python manage.py acal_dryrun_annee_moyenne --dry-run [--company <slug>]
"""
from __future__ import annotations

from django.apps import apps as registre
from django.core.management.base import BaseCommand, CommandError

from apps.calepinage.services import annee_moyenne as _annee_moyenne

#: Le libellé de la colonne « énergies rangées ».
LIBELLES_ENERGIES = {True: 'fenêtre entière', False: 'année moyenne',
                     None: 'indéterminé'}


def _remis_avant_le_calcul(remis_le, calcule_le):
    """Vrai quand la remise précède le calcul rangé (comparaison ISO, les
    deux en UTC ``…Z`` / ``+00:00``) ; ``False`` sans date lisible."""
    if remis_le is None or not calcule_le:
        return False
    return remis_le.strftime('%Y-%m-%dT%H:%M:%S') < str(calcule_le)[:19]


class Command(BaseCommand):
    help = ('R3-01 (Q2) — liste (lecture seule) les documents remis dont le '
            'résultat rangé publie ses énergies sur la fenêtre entière.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Obligatoire : la commande ne fait que lire.')
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        if not options.get('dry_run'):
            raise CommandError(
                "ajoutez --dry-run : cette commande n'écrit jamais")
        from django.contrib.contenttypes.models import ContentType

        Calepinage = registre.get_model('calepinage', 'Calepinage')
        Attachment = registre.get_model('records', 'Attachment')
        type_calepinage = ContentType.objects.get_for_model(Calepinage)
        qs = (Calepinage.objects.exclude(resultat__isnull=True)
              .select_related('company').order_by('company_id', 'pk'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        ecrire = self.stdout.write
        ecrire('DRY-RUN R3-01 (lecture seule) — aucune écriture')
        ecrire('société | calepinage | document remis | remis le | mode météo '
               '| années de la fenêtre | énergies rangées | calculé le')
        documents, concernes, sans_document = 0, 0, 0
        for calepinage in qs.iterator(chunk_size=200):
            etat = _annee_moyenne.etat_des_energies(calepinage.resultat)
            if etat is None:
                continue
            concernes += 1
            pieces = (Attachment.objects
                      .filter(content_type=type_calepinage,
                              object_id=calepinage.pk,
                              company_id=calepinage.company_id,
                              filename__contains='__v')
                      .order_by('created_at', 'pk'))
            vues = 0
            for piece in pieces:
                vues += 1
                avant = _remis_avant_le_calcul(piece.created_at,
                                               etat['calcule_le'])
                ecrire('%s | %s | %s | %s%s | %s | %d | %s | %s' % (
                    calepinage.company.slug, calepinage.pk, piece.filename,
                    piece.created_at.isoformat(),
                    ' (avant le calcul rangé : mode à la remise inconnu)'
                    if avant else '',
                    etat['mode'] or '—', etat['annees'],
                    LIBELLES_ENERGIES[etat['fenetre_entiere']],
                    etat['calcule_le'] or '—'))
            documents += vues
            sans_document += 0 if vues else 1
        ecrire('%d document(s) remis sur %d calepinage(s) pluriannuel(s) ; '
               '%d calepinage(s) pluriannuel(s) sans document remis.'
               % (documents, concernes, sans_document))
