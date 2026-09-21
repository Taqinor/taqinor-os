"""COMPTA6 — Génère le dossier de contrôle CGNC prêt à valider (fiduciaire).

Produit, pour une société, le DOSSIER que le fiduciaire / expert-comptable
humain relit avant la validation LÉGALE finale du plan et du format CGNC :

* le plan comptable réel (classes 1 à 8) structuré ;
* le barème CGNC de référence ;
* un rapport de contrôle de cohérence (classe/numéro, sens, comptes usuels
  manquants, comptes désactivés encore mouvementés) ;
* une synthèse chiffrée ;
* la liste EXPLICITE de ce qui reste à la charge du fiduciaire humain.

La commande NE modifie AUCUNE donnée (lecture seule) et est idempotente : deux
exécutions successives sur un plan inchangé donnent le même dossier. Elle est
scopée société et ne contient aucun prix d'achat / marge.

Exemples ::

    python manage.py compta_cgnc_dossier --company acme
    python manage.py compta_cgnc_dossier --company acme --format json \
        --output dossier_cgnc_acme.json
    python manage.py compta_cgnc_dossier --all --format text
"""
import json

from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.compta import services


class Command(BaseCommand):
    help = (
        "Génère le dossier de contrôle CGNC (prêt à valider par un fiduciaire) "
        "d'une société : plan comptable, référentiel, contrôles de cohérence "
        "et synthèse. Lecture seule, ne modifie rien.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company',
            help="Slug de la société (obligatoire sauf avec --all).")
        parser.add_argument(
            '--all', dest='all', action='store_true',
            help="Génère le dossier pour toutes les sociétés.")
        parser.add_argument(
            '--format', dest='format', choices=('text', 'json'),
            default='text', help="Format de sortie (défaut : text).")
        parser.add_argument(
            '--output', dest='output',
            help="Fichier de sortie (défaut : stdout).")

    def handle(self, *args, **options):
        slug = options.get('company')
        do_all = options.get('all')
        fmt = options.get('format')
        output = options.get('output')

        if not slug and not do_all:
            raise CommandError("Précisez --company <slug> ou --all.")

        if do_all:
            companies = list(Company.objects.order_by('slug'))
            if not companies:
                raise CommandError("Aucune société en base.")
        else:
            company = Company.objects.filter(slug=slug).first()
            if company is None:
                raise CommandError(f"Société inconnue : « {slug} ».")
            companies = [company]

        dossiers = [
            services.construire_dossier_cgnc(company) for company in companies
        ]

        if fmt == 'json':
            payload = dossiers if do_all else dossiers[0]
            rendu = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            rendu = '\n\n'.join(self._render_text(d) for d in dossiers)

        if output:
            with open(output, 'w', encoding='utf-8') as fh:
                fh.write(rendu)
                if not rendu.endswith('\n'):
                    fh.write('\n')
            self.stdout.write(self.style.SUCCESS(
                f"Dossier CGNC écrit dans {output} "
                f"({len(companies)} société(s))."))
        else:
            self.stdout.write(rendu)

    def _render_text(self, dossier):
        """Rendu texte lisible d'un dossier (revue rapide par le fiduciaire)."""
        s = dossier['synthese']
        lignes = []
        lignes.append('=' * 72)
        lignes.append(f"DOSSIER DE CONTRÔLE CGNC — {s['company']} "
                      f"({s['company_slug']})")
        lignes.append(f"Généré le : {s['genere_le']}")
        lignes.append('=' * 72)
        lignes.append('')

        lignes.append('SYNTHÈSE')
        lignes.append('-' * 72)
        lignes.append(f"  Comptes au plan            : {s['nb_comptes']}")
        lignes.append(
            "  Couverture barème CGNC     : "
            f"{s['reference_cgnc_couverte']}/{s['reference_cgnc_totale']}")
        par_sev = s['anomalies_par_severite']
        lignes.append(
            f"  Anomalies                  : {s['nb_anomalies']} "
            f"(bloquant {par_sev.get('bloquant', 0)}, "
            f"avertissement {par_sev.get('avertissement', 0)}, "
            f"info {par_sev.get('info', 0)})")
        etat = ('PRÊT à transmettre au fiduciaire'
                if s['pret_a_transmettre']
                else 'À CORRIGER avant transmission (anomalies bloquantes)')
        lignes.append(f"  État                       : {etat}")
        lignes.append('')

        lignes.append('PLAN COMPTABLE PAR CLASSE')
        lignes.append('-' * 72)
        for classe in sorted(dossier['plan_comptable']):
            bucket = dossier['plan_comptable'][classe]
            nb = len(bucket['comptes'])
            lignes.append(f"  Classe {classe} — {bucket['libelle']} "
                          f"({nb} compte(s))")
            for compte in bucket['comptes']:
                flags = []
                if compte['est_tiers']:
                    flags.append('tiers')
                if compte['lettrable']:
                    flags.append('lettrable')
                if not compte['actif']:
                    flags.append('INACTIF')
                suffixe = f" [{', '.join(flags)}]" if flags else ''
                lignes.append(
                    f"      {compte['numero']:<8} {compte['intitule']}{suffixe}")
        lignes.append('')

        lignes.append('CONTRÔLES DE COHÉRENCE')
        lignes.append('-' * 72)
        if not dossier['controles']:
            lignes.append("  Aucune anomalie détectée.")
        else:
            for anomalie in dossier['controles']:
                lignes.append(
                    f"  [{anomalie['severite'].upper()}] "
                    f"{anomalie['message']}")
        lignes.append('')

        lignes.append('À VALIDER PAR LE FIDUCIAIRE (étape humaine restante)')
        lignes.append('-' * 72)
        for item in dossier['a_valider_fiduciaire']:
            lignes.append(f"  - {item}")

        return '\n'.join(lignes)
