"""Exporte un instantané ANONYMISÉ d'une société (QA de nuit réaliste).

LECTURE SEULE sur la base source : toutes les lectures se font dans une
transaction ANNULÉE à la fin (et, sur PostgreSQL hors transaction englobante,
déclarée ``READ ONLY`` — toute écriture accidentelle échouerait). Rien n'est
jamais sauvegardé.

Graphe exporté (une société, FK cohérentes) : réglages de PRIX de la société
(Tarification & ROI en entier + repères de prix du profil — TVA, tarif ONEE,
productible, remises… — jamais son identité, son RIB ni sa sécurité : sans eux
la société cible tarife avec les barèmes par défaut et les chiffres dérivent de
la production), catégories, fournisseurs,
produits (catalogue, ``courbe_pompe``, ``prix_achat`` compris — usage interne
du générateur), clients, leads (profil énergie, factures, distributeur, toit,
relevé), devis + lignes + ``etude_params``, bons de commande, factures +
lignes, avoirs + lignes, paiements, chantiers + interventions. Politique champ
par champ : ``authentication/anonymise.py`` (KEEP / SCRAMBLE / SCRUB / GPS /
DROP, fail-closed — un champ texte inconnu est brouillé).

Deux valeurs réelles différentes ne partagent jamais un faux (identifiants,
e-mails, téléphones, noms… : sinon un index unique rejette des lignes à
l'import) ; la même valeur redonne toujours le même faux.

Le fichier reste CONFIDENTIEL (montants réels, prix d'achat) : jamais commité
(``var/anon/`` et ``*.anon.json.gz`` sont ignorés par git), jamais envoyé
ailleurs, les anciens instantanés sont supprimés. Aucune valeur n'est
imprimée : seulement des comptes.

Run (sur le serveur, voir docs/qa-explorer.md « Données réalistes anonymisées ») :
  python manage.py qa_export_anonymise --company <slug> --out - > latest.anon.json.gz
  python manage.py qa_export_anonymise --company <slug> --out /tmp/x.anon.json.gz \
      [--since 2026-01-01] [--limit 200]
"""
import datetime
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from authentication import anonymise


class Command(BaseCommand):
    help = ("Exporte un instantané anonymisé (identités brouillées, montants/"
            "études/lignes/statuts gardés) d'UNE société — lecture seule.")

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True,
                            help='Slug de la société source.')
        parser.add_argument('--out', required=True,
                            help="Fichier '*.anon.json.gz' (hors du code "
                                 "source, ou sous var/anon/), ou '-' pour "
                                 'stdout.')
        parser.add_argument('--since', default=None,
                            help='YYYY-MM-DD : documents créés depuis cette '
                                 'date (le catalogue est toujours complet).')
        parser.add_argument('--limit', type=int, default=None,
                            help='Au plus N documents les plus récents par '
                                 'type (leads, devis, factures…).')

    def _log(self, msg):
        # Jamais sur stdout : avec --out -, stdout porte le fichier binaire.
        if self._verbosity >= 1:
            self.stderr.write(msg)

    def handle(self, *args, **options):
        from authentication.models import Company

        self._verbosity = options.get('verbosity', 1)
        out = options['out']
        problem = anonymise.check_out_path(out)
        if problem:
            raise CommandError(problem)
        since = None
        if options.get('since'):
            try:
                since = datetime.date.fromisoformat(options['since'])
            except ValueError as exc:
                raise CommandError('--since attend YYYY-MM-DD.') from exc
        limit = options.get('limit')
        if limit is not None and limit <= 0:
            raise CommandError('--limit doit être > 0.')

        company = Company.objects.filter(slug=options['company']).first()
        if company is None:
            raise CommandError(
                "Société inconnue (slug). Liste des slugs : "
                "python manage.py shell -c \"from authentication.models import "
                "Company; print(list(Company.objects.values_list('slug', "
                "flat=True)))\"")

        outer_atomic = connection.in_atomic_block
        payload = None
        scrambler = anonymise.Scrambler()
        with transaction.atomic():
            if connection.vendor == 'postgresql' and not outer_atomic:
                with connection.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
            payload = anonymise.build_export(company, since=since, limit=limit,
                                             scrambler=scrambler)
            # Lecture seule : on annule TOUJOURS, même si rien n'a été écrit.
            transaction.set_rollback(True)

        size = anonymise.write_snapshot(payload, out, sys.stdout.buffer
                                        if out == '-' else None)
        total = sum(payload['counts'].values())
        self._log(f'qa_export_anonymise : {total} lignes, {size} octets '
                  '(CONFIDENTIEL — jamais commité, jamais transmis).')
        for label, n in payload['counts'].items():
            self._log(f'  {label}: {n}')
        # Un faux ne partage jamais sa valeur avec une autre, sauf dans un champ
        # trop court pour l'unicité : on le DIT (comptes par genre, jamais une
        # valeur) — l'import les rapportera par nom de contrainte.
        for kind, n in sorted(scrambler.exhausted.items()):
            self._log(f'  ATTENTION : {n} faux « {kind} » non uniques (champ '
                      "trop court pour garantir l'unicité).")
