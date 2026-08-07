"""VAO7 — seed du catalogue des sources de veille (idempotent, ADDITIF).

Ce fichier est **le seul endroit du module** où une URL de portail est écrite
en clair : elle est semée EN BASE, et le reste du code (collecteur compris) la
lit depuis ``SourceVeille.url_base``. Une garde de test le vérifie
(``tests/test_sources.py::AucuneUrlEnDurTests``).

Rejouable sans doublon : une source déjà présente (appariée par
``(company, code)``) est laissée STRICTEMENT intacte — un libellé, une
cadence ou un interrupteur ``actif`` réglé par le fondateur survit à un
re-seed. Aucune suppression, aucune réécriture.

Ce que le seed active, et ce qu'il n'active pas
-----------------------------------------------
* Les **portes humaines** (saisie manuelle, tuyau partenaire, import de
  fichier) sont créées ACTIVES : elles n'interrogent rien, elles reçoivent.
* Le **portail officiel** est créé **INACTIF**. Le collecteur naît désarmé
  (règle #5 : le fichier de risque ``tos_risk/marchespublics_gov_ma.md``
  porte une ligne d'approbation fondateur VIDE) — activer cette source est un
  acte manuel, jamais un effet de bord de seed.
* Les **sources de phase 2** (portails sectoriels EEP, agrégateurs
  commerciaux) sont créées INACTIVES : elles documentent la carte des sources
  pour que l'extension suivante n'ait pas à toucher le collecteur.

Lancer ::

    python manage.py seed_veille_sources                       # toutes sociétés
    python manage.py seed_veille_sources --company taqinor-demo  # une seule
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.veille_ao.models import SourceVeille, TypeSource

# (code, libellé, type, url_base, actif, notes)
#
# Les URL ne figurent que là où l'hôte est CONNU et vérifié ; ailleurs le
# champ reste vide — on ne devine pas une adresse.
SOURCES = [
    # ── Portes humaines : phase 1, actives (elles reçoivent, n'interrogent rien)
    ('saisie_manuelle', 'Saisie manuelle', TypeSource.SAISIE_MANUELLE, '',
     True,
     "Un avis saisi à la main depuis un chantier ou un appel. Porte "
     "toujours ouverte."),
    ('tuyau_partenaire', 'Tuyau partenaire', TypeSource.TUYAU_PARTENAIRE, '',
     True,
     "La porte MANUELLE : consultations privées, AO restreints, invitations "
     "directes. C'est la seule porte qui aurait capté l'avis FRDISI, qui n'a "
     "jamais été publié nulle part."),
    ('import_fichier', 'Import de fichier', TypeSource.IMPORT_CSV, '', True,
     "Fichier d'avis fourni par un agrégateur, un portail sectoriel ou une "
     "alerte e-mail officielle."),

    # ── Portail officiel : phase 1 mais DÉSARMÉ (règle #5)
    ('pmmp', 'Portail Marocain des Marchés Publics (PMMP)',
     TypeSource.PORTAIL_OFFICIEL, 'https://www.marchespublics.gov.ma', False,
     "État, collectivités territoriales, établissements publics, bons de "
     "commande et ONEE Branche Eau. CRÉÉE INACTIVE : la collecte automatique "
     "est gouvernée par la règle #5 (fichier de risque "
     "tos_risk/marchespublics_gov_ma.md, ligne d'approbation fondateur "
     "vide). L'activer est un acte manuel."),

    # ── Phase 2 : portails sectoriels (EEP sous loi 69-00, hors décret)
    ('masen', 'MASEN', TypeSource.PORTAIL_SECTORIEL,
     'https://etendering.masen.ma', False,
     "Phase 2 — même logiciel Atexo que le PMMP."),
    ('cdg', 'CDG (Safakat)', TypeSource.PORTAIL_SECTORIEL,
     'https://safakat.cdg.ma', False,
     "Phase 2 — même logiciel Atexo que le PMMP."),
    ('onee_electricite', 'ONEE — Branche Électricité',
     TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),
    ('ocp', 'Groupe OCP', TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),
    ('adm', 'Autoroutes du Maroc (ADM)', TypeSource.PORTAIL_SECTORIEL, '',
     False, "Phase 2 — adresse du portail à renseigner avant activation."),
    ('marsa_maroc', 'Marsa Maroc', TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),
    ('onda', 'ONDA', TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),
    ('oncf', 'ONCF', TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),
    ('srm', 'Sociétés régionales multiservices (SRM)',
     TypeSource.PORTAIL_SECTORIEL, '', False,
     "Phase 2 — adresse du portail à renseigner avant activation."),

    # ── Phase 2 : agrégateurs commerciaux (abonnements payants)
    ('datao', 'Datao', TypeSource.AGREGATEUR, '', False,
     "Phase 2 — abonnement payant, décision fondateur. Valeur unique : les "
     "marchés privés et la recherche au niveau des lignes de bordereau."),
    ('lesoffres', 'lesoffres.ma', TypeSource.AGREGATEUR, '', False,
     "Phase 2 — abonnement payant, décision fondateur."),
    ('marche_facile', 'Marché Facile', TypeSource.AGREGATEUR, '', False,
     "Phase 2 — offre gratuite, à évaluer."),
]


def seed_sources_pour_societe(company):
    """Sème les sources connues pour UNE société (idempotent, additif).

    Renvoie le nombre de sources RÉELLEMENT créées. Une source existante
    (appariée par ``(company, code)``) n'est ni modifiée ni supprimée.
    """
    existants = set(
        SourceVeille.objects.filter(company=company)
        .values_list('code', flat=True))
    crees = 0
    for code, libelle, type_source, url_base, actif, notes in SOURCES:
        if code in existants:
            continue
        SourceVeille.objects.create(
            company=company, code=code, libelle=libelle,
            type_source=type_source, url_base=url_base, actif=actif,
            notes=notes)
        crees += 1
    return crees


class Command(BaseCommand):
    help = (
        "Sème le catalogue des sources de veille appels d'offres "
        "(idempotent, additif : ne touche jamais une source existante)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à semer (défaut : toutes).")

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        if slug:
            try:
                societes = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Société « {slug} » introuvable.")
        else:
            societes = list(Company.objects.all())

        if not societes:
            self.stdout.write(self.style.WARNING(
                'Aucune société à semer — rien fait.'))
            return

        total = sum(seed_sources_pour_societe(co) for co in societes)
        self.stdout.write(self.style.SUCCESS(
            f'Sources de veille semées pour {len(societes)} société(s) : '
            f'{total} source(s) créée(s) ; les sources existantes sont '
            'restées intactes.'))
