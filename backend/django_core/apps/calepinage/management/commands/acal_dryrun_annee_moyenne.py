"""R3-01 / R3-17 (Q2) — ACAL1252 (D-ACAL-64 = lister_et_montrer) — DRY-RUN :
les simulations RANGÉES et les documents déjà REMIS dont les énergies sont
publiées sur la fenêtre ENTIÈRE (mode météo pluriannuel, somme de N années
au lieu de leur moyenne), à montrer au fondateur AVANT toute re-simulation.

La sélection est ``services/annee_moyenne.py::lister_pluriannuels`` (pure) ;
cette commande ne fait que LIRE les entrées et imprimer ses deux listes :

* concernés — ``fenêtre entière`` prouvée par la trace : N rangé
  (``production.total.annees_fenetre`` > 1) et arrivée de la cascade ≈ N ×
  P50. Énergie rangée et énergie ÷ N côte à côte ;
* indéterminés — la trace ne permet pas de le dire (N non rangé, P50 ou
  cascade absents, document remis avant le calcul rangé) : jamais deviné.

Sources lues : ``Calepinage.resultat``, ``CalepinageVariante.resultat`` et
les versions remises (``records.Attachment`` rattachées au calepinage, nom
``<code>__v<NNN>__<langue>[__<empreinte>].<ext>``, ``views/remise_document.py``).
Aucun nom de client, titre, téléphone, e-mail, adresse ni GPS n'est lu ni
imprimé : identifiants seulement.

LECTURE SEULE : aucun ``save``/``update``/``delete``, aucune tâche de fond,
aucun ``get_or_create`` (le type de contenu est LU, jamais créé), aucun
fichier écrit sauf ``--sortie``. Jouable dans une transaction en lecture
seule.

    python manage.py acal_dryrun_annee_moyenne --dry-run [--company <id|slug>]
        [--json] [--sortie <chemin>]
"""
from __future__ import annotations

import json

from django.apps import apps as registre
from django.core.management.base import BaseCommand, CommandError

from apps.calepinage.services import annee_moyenne as _annee_moyenne

ENTETE = 'DRY-RUN R3-01 (lecture seule) — aucune écriture'
COLONNES = ('société | calepinage | objet | document remis | date | mode météo '
            '| années de la fenêtre | énergie rangée kWh | énergie ÷ N kWh '
            '| P50 rangé kWh | motif')


def _documents_par_calepinage(ids, company_id=None):
    """``{(calepinage_id, company_id): [{nom, remis_le}]}`` — LECTURE des
    versions remises. Le type de contenu est LU (``filter``), jamais créé
    (``get_for_model`` ferait un ``get_or_create``)."""
    ContentType = registre.get_model('contenttypes', 'ContentType')
    Attachment = registre.get_model('records', 'Attachment')
    type_calepinage = ContentType.objects.filter(
        app_label='calepinage', model='calepinage').first()
    documents = {}
    if type_calepinage is None or not ids:
        return documents
    qs = Attachment.objects.filter(content_type=type_calepinage,
                                   object_id__in=list(ids),
                                   filename__contains='__v')
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    for object_id, cie, nom, remis_le in qs.order_by(
            'created_at', 'pk').values_list('object_id', 'company_id',
                                            'filename', 'created_at'):
        documents.setdefault((object_id, cie), []).append(
            {'nom': nom, 'remis_le': remis_le})
    return documents


def _entrees(company_id=None):
    """Les entrées de ``lister_pluriannuels`` — lectures seules."""
    Calepinage = registre.get_model('calepinage', 'Calepinage')
    Variante = registre.get_model('calepinage', 'CalepinageVariante')
    calepinages = Calepinage.objects.exclude(resultat__isnull=True)
    variantes = Variante.objects.exclude(resultat__isnull=True)
    if company_id is not None:
        calepinages = calepinages.filter(company_id=company_id)
        variantes = variantes.filter(company_id=company_id)
    lignes = list(calepinages.order_by('company_id', 'pk').values_list(
        'pk', 'company_id', 'resultat'))
    documents = _documents_par_calepinage([pk for pk, _c, _r in lignes],
                                          company_id)
    for pk, cie, resultat in lignes:
        yield {'company_id': cie, 'calepinage_id': pk, 'objet': 'calepinage',
               'objet_id': pk, 'resultat': resultat,
               'documents': documents.get((pk, cie), [])}
    for pk, cie, calepinage_id, resultat in variantes.order_by(
            'company_id', 'calepinage_id', 'pk').values_list(
            'pk', 'company_id', 'calepinage_id', 'resultat'):
        yield {'company_id': cie, 'calepinage_id': calepinage_id,
               'objet': 'variante', 'objet_id': pk, 'resultat': resultat,
               'documents': []}


def _ligne(r):
    return ' | '.join('—' if v in (None, '') else str(v) for v in (
        r['company_id'], r['calepinage_id'],
        '%s %s' % (r['objet'], r['objet_id']), r['document'], r['date'],
        r['mode'], r['annees'], r['energie_rangee_kwh'],
        r['energie_par_an_kwh'], r['p50_kwh'], r['motif']))


def _texte(releve):
    c = releve['comptes']
    return '\n'.join(
        [ENTETE, '',
         'CONCERNÉS — énergies rangées sur la fenêtre entière (× N)',
         COLONNES]
        + [_ligne(r) for r in releve['concernes']]
        + ['', 'INDÉTERMINÉS — la trace ne permet pas de le dire', COLONNES]
        + [_ligne(r) for r in releve['indetermines']]
        + ['', '%d résultat(s) rangé(s) lu(s) ; %d concerné(s) ; %d '
           'indéterminé(s) ; %d ligne(s) concernée(s) dont %d document(s) '
           'remis ; %d ligne(s) indéterminée(s).' % (
               c['lus'], c[_annee_moyenne.CONCERNE],
               c[_annee_moyenne.INDETERMINE], len(releve['concernes']),
               sum(1 for r in releve['concernes'] if r['document']),
               len(releve['indetermines']))])


def _societe(valeur):
    """L'identifiant de société de ``--company`` (id, ou slug LU)."""
    if not valeur:
        return None
    if str(valeur).isdigit():
        return int(valeur)
    Company = registre.get_model('authentication', 'Company')
    company_id = (Company.objects.filter(slug=valeur)
                  .values_list('pk', flat=True).first())
    if company_id is None:
        raise CommandError('société inconnue : %s' % valeur)
    return company_id


class Command(BaseCommand):
    help = ('ACAL1252 — liste (lecture seule) les simulations rangées et '
            'documents remis dont les énergies sont la somme des N années.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Obligatoire : la commande ne fait que lire.')
        parser.add_argument(
            '--company', default=None,
            help='Identifiant (ou slug) de société ; défaut : toutes.')
        parser.add_argument('--json', action='store_true',
                            help='Imprime le relevé en JSON.')
        parser.add_argument('--sortie', default=None,
                            help='Écrit le relevé dans ce fichier (seule '
                                 'écriture possible, sur disque).')

    def handle(self, *args, **options):
        if not options.get('dry_run'):
            raise CommandError(
                "ajoutez --dry-run : cette commande n'écrit jamais")
        releve = _annee_moyenne.lister_pluriannuels(
            _entrees(_societe(options.get('company'))))
        if options.get('json'):
            texte = json.dumps(releve, ensure_ascii=False, indent=2,
                               default=str)
        else:
            texte = _texte(releve)
        if options.get('sortie'):
            with open(options['sortie'], 'w', encoding='utf-8') as fichier:
                fichier.write(texte + '\n')
            self.stdout.write('relevé écrit dans %s' % options['sortie'])
        else:
            self.stdout.write(texte)
