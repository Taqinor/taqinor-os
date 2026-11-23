"""ACAL895 (D-ACAL-42) — semer trois MODÈLES d'exemple dans la bibliothèque.

Trois calepinages ``exemple=True`` (villa à toit incliné, toit plat est-ouest,
champ au sol), marqués modèles, sans lead, client, devis ni utilisateur créé,
jamais comptés dans la liste, les KPI ni l'API publique. Les documents sont de
vrais ``roof_layout_v2`` (contour + pans) committés dans ``exemples/``.

IDEMPOTENT (clé : société + titre + ``exemple``) et DRY-RUN PAR DÉFAUT : la
production ne reçoit ces lignes que sur un geste explicite (``--apply``),
jamais au déploiement.

ACAL1349 (D-ACAL-82) — ``--apply`` remplit aussi les réglages VIDES de la
société avec le profil de départ (jamais une saisie écrasée) puis simule
chaque modèle créé : son étape Résultats est alors complète. Le mode et la
fenêtre météo restent un choix de la société, et la simulation a besoin d'un
module et d'un onduleur du catalogue : à défaut, la simulation est REFUSÉE et
dite (« simulation non faite »), le modèle reste semé.

    python manage.py semer_exemples_calepinage --societe <id>
    python manage.py semer_exemples_calepinage --societe <id> --apply
"""
from __future__ import annotations

import json
import pathlib

from django.core.management.base import BaseCommand, CommandError

EXEMPLES = pathlib.Path(__file__).resolve().parents[2] / 'exemples'

#: (fichier du document, titre affiché dans la bibliothèque)
MODELES = (
    ('residentiel_pan_sud_15.json', 'Exemple — villa à toit incliné'),
    ('ci_toit_plat_est_ouest_chassis.json',
     'Exemple — toit plat est-ouest (commerce)'),
    ('champ_sol_sud.json', 'Exemple — champ au sol'),
)


class Command(BaseCommand):
    help = ("ACAL895 — sème trois modèles d'exemple dans la bibliothèque "
            "d'une société. Dry-run par défaut ; --apply écrit, ET remplit "
            "les réglages de simulation encore vides de la société.")

    #: Dit au dry-run ce que ``--apply`` écrit EN PLUS des modèles (ACAL1349).
    ANNONCE_REGLAGES = (
        "Avec --apply : les réglages de simulation encore VIDES de la société "
        "sont remplis par le profil de départ (pertes comprises) ; aucune "
        "saisie n'est écrasée.")

    #: Le client météo et le matériel de la simulation : ``None`` = ceux de
    #: production (PVGIS, catalogue de la société) ; les tests les posent.
    client_pvgis = None
    materiel = None

    def add_arguments(self, parser):
        parser.add_argument('--societe', type=int, required=True,
                            help="Identifiant de la société.")
        parser.add_argument('--apply', action='store_true',
                            help='Écrit réellement (sinon : liste seule).')

    def handle(self, *args, **options):
        from django.db import transaction

        from authentication.models import Company

        from ...models import Calepinage
        from ...services.layout import enregistrer_layout
        from ...services.modeles import marquer_modele

        company = Company.objects.filter(pk=options['societe']).first()
        if company is None:
            raise CommandError(
                "Société introuvable : %s." % options['societe'])
        appliquer = options['apply']
        crees = 0
        for fichier, titre in MODELES:
            existe = Calepinage.objects.filter(
                company=company, titre=titre, exemple=True).exists()
            if existe:
                self.stdout.write('%s → déjà présent' % titre)
                continue
            self.stdout.write('%s → %s' % (
                titre, 'créé' if appliquer else 'à créer (dry-run)'))
            crees += 1
            if not appliquer:
                continue
            document = json.loads(
                (EXEMPLES / fichier).read_text(encoding='utf-8'))
            with transaction.atomic():
                calepinage = Calepinage.objects.create(
                    company=company, titre=titre, exemple=True)
                enregistrer_layout(calepinage, document,
                                   libelle="Modèle d'exemple")
                marquer_modele(calepinage)
            self._simuler(calepinage, company)
        self.stdout.write('%s modèle(s) %s.' % (
            crees, 'créés' if appliquer else 'à créer (dry-run)'))
        if crees and not appliquer:
            self.stdout.write(self.ANNONCE_REGLAGES)

    def _simuler(self, calepinage, company):
        """ACAL1349 — profil de départ sur les réglages vides, puis simulation
        publiée ; un refus ou un PVGIS injoignable est dit, jamais avalé."""
        from ...services.profil_depart import appliquer_profil
        from ...services.pvgis_serie import PvgisIndisponible
        from ...services.simulation import (
            SimulationRefusee, simuler_calepinage)

        appliquer_profil(company, user=None)
        try:
            simuler_calepinage(calepinage, client=self.client_pvgis,
                               materiel=self.materiel)
        except (SimulationRefusee, PvgisIndisponible) as refus:
            self.stdout.write('%s → simulation non faite : %s' % (
                calepinage.titre, refus))
        else:
            self.stdout.write('%s → simulation publiée' % calepinage.titre)
