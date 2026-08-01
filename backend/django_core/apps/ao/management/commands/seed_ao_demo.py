"""AOF186 — seed de démonstration « AO FRDISI » (CI e2e + reprise en main).

Constat qui justifie cette commande
-----------------------------------
Les specs e2e et les écrans de dossier exigent un jeu COMPLET — une affaire,
trois bâtiments, des toitures rectangle / L / arc, leurs obstacles, leurs kits,
un bordereau — que RIEN ne crée aujourd'hui : ``seed_ao_kits`` ne couvre que
les kits. Une spec écrite contre des données inexistantes échoue pour une
raison qui n'est PAS le bug qu'elle cherche, et c'est la pire sorte d'échec de
CI : bruyante et sans information.

Les trois règles de cette commande
----------------------------------
1. **Les GOLDENS sont la seule source de vérité géométrique.** Enveloppes,
   obstacles, comptes et engagements sont LUS dans
   ``core/calepinage/golden/frdisi_2026_07_27/*.json`` (AOF183). Recopier ces
   chiffres ici créerait une seconde vérité qui divergerait au premier
   ajustement du moteur — et le seed « prouverait » alors un chiffre faux.
2. **Le seed REFUSE de s'exécuter si les goldens divergent.** Avant d'écrire
   quoi que ce soit, il rejoue le compte de chaque bâtiment avec le moteur et
   exige l'égalité AU MODULE PRÈS avec le compte témoin. Une divergence est une
   ``CommandError`` et RIEN n'est écrit.
3. **Jamais en production par défaut.** Le drapeau ``--confirmer`` est
   obligatoire, et hors ``DEBUG`` la commande exige en plus le réglage explicite
   ``SEED_AO_DEMO_AUTORISE = True``. Un jeu de démonstration qui apparaîtrait
   dans les vraies affaires d'un client serait indéfendable.

**AUCUN COÛT DE REVIENT** n'est semé : ni ``prix_achat``, ni marge, ni
bénéfice. Le bordereau porte des quantités et des prix unitaires de VENTE —
l'économie d'un AO vit derrière ``ao_rentabilite_voir`` (AOF2), et un jeu de
démonstration n'a aucune raison d'y toucher.

    python manage.py seed_ao_demo --company <slug> --confirmer
"""
import io
import json
import os
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

import core.calepinage
from authentication.models import Company

from ...models import (
    BatimentAO, BordereauPrix, LigneBordereau, ObstacleAO, ReleveAO,
    ToitureAO, VarianteCalepinage,
)

#: Racine des goldens FRDISI (AOF183) — la SEULE source géométrique.
#: Le chemin est DÉDUIT de l'emplacement du paquet ``core.calepinage``, jamais
#: compté à la main depuis ce fichier : remonter des dossiers à la main visait
#: ``apps/core/calepinage`` (un cran trop haut, un paquet qui n'existe pas) et
#: rendait le seed injouable. Le paquet sait où il est ; nous le lui demandons.
GOLDEN = os.path.join(
    os.path.dirname(os.path.abspath(core.calepinage.__file__)),
    'golden', 'frdisi_2026_07_27')

#: Référence acheteur de l'affaire de démonstration — clé de déduplication.
#: Le préfixe ``DEMO-`` la rend reconnaissable au premier coup d'œil dans une
#: liste : personne ne doit pouvoir la confondre avec une vraie affaire.
REFERENCE_DEMO = 'DEMO-FRDISI-2026-07-27'

#: Date du relevé témoin (la session AO FRDISI du 27/07/2026).
DATE_RELEVE = date(2026, 7, 27)

#: Bâtiment -> (fichier golden, code, désignation, forme ``ToitureAO``).
BATIMENTS = (
    ('bat_A_aile_L.json', 'A', 'Résidence — aile en L',
     ToitureAO.Forme.FORME_L),
    ('bat_B_arc.json', 'B', 'Résidence — aile courbe', ToitureAO.Forme.ARC),
    ('bat_C_ecole.json', 'C', 'École — toiture rectangulaire',
     ToitureAO.Forme.RECTANGLE),
)

#: Provenance MOTEUR -> provenance ``ObstacleAO``. Les deux vocabulaires
#: diffèrent (``RELEVE`` côté moteur, ``MESURE`` côté modèle) : la traduction
#: est EXPLICITE ici, jamais devinée par une coïncidence de nom.
PROVENANCES = {
    'RELEVE': ObstacleAO.Provenance.MESURE,
    'RELEVE_DOUTEUX': ObstacleAO.Provenance.MESURE_DOUTEUX,
    'DECLARE_CLIENT': ObstacleAO.Provenance.DECLARE_CLIENT,
    'PLAN': ObstacleAO.Provenance.PLAN,
    'DEVINE': ObstacleAO.Provenance.DEVINE,
    'ECARTE': ObstacleAO.Provenance.ECARTE,
}

#: Type d'obstacle MOTEUR -> nature ``ObstacleAO``. Les types moteur sans
#: équivalent exact retombent sur ``CAISSON_TECHNIQUE`` (le défaut du modèle).
NATURES = {
    'CAISSON_BETON': ObstacleAO.Nature.CAISSON_TECHNIQUE,
    'CAGE_ESCALIER': ObstacleAO.Nature.CAGE_ESCALIER,
    'EDICULE': ObstacleAO.Nature.EDICULE,
    'SOUCHE': ObstacleAO.Nature.SOUCHE,
    'CLIMATISEUR': ObstacleAO.Nature.GROUPE_CLIM,
    'LANTERNEAU': ObstacleAO.Nature.LANTERNEAU,
    'ACROTERE': ObstacleAO.Nature.ACROTERE,
    'JOINT_DILATATION': ObstacleAO.Nature.JOINT_DILATATION,
    'MURET': ObstacleAO.Nature.MURET,
    'ANTENNE': ObstacleAO.Nature.CAISSON_TECHNIQUE,
    'GARDE_CORPS': ObstacleAO.Nature.MURET,
    'EVACUATION_EU': ObstacleAO.Nature.CHEMIN_CABLES,
    'NATURE_INCONNUE': ObstacleAO.Nature.CAISSON_TECHNIQUE,
}


def charger_golden(nom):
    """Lit un document golden. Absent = ``CommandError`` (jamais un silence)."""
    chemin = os.path.join(GOLDEN, nom)
    if not os.path.exists(chemin):
        raise CommandError(
            'Golden introuvable : %s. Le seed de démonstration se construit '
            'DEPUIS les goldens (AOF183) — il ne recopie aucun chiffre.'
            % chemin)
    with io.open(chemin, encoding='utf-8') as fh:
        return json.load(fh)


def _compte_moteur(document):
    """Rejoue le compte du bâtiment avec le MOTEUR, depuis le golden seul."""
    from core.calepinage.moteur import compter_plan
    from core.calepinage.serialisation import EntreeCalepinage

    entree = EntreeCalepinage.depuis_dict(
        {k: v for k, v in document.items() if k != 'golden'})
    golden = document['golden']

    if 'segments' in golden:
        # Bâtiment en arc : trois segments, chacun son kit et ses obstacles.
        par_repere = {s.repere: s for s in entree.surfaces}
        total = 0
        for segment in golden['segments']:
            kit = [k for k in entree.kits if k.code == segment['kit']][0]
            vises = set(segment['obstacles'])
            obstacles = tuple(o for o in entree.obstacles
                              if o.repere in vises)
            rangees = tuple((y, kit) for y in segment['rangees_retenues'])
            total += compter_plan(par_repere[segment['repere']], rangees,
                                  obstacles).modules
        return total

    kit = entree.parametres.kits[0]
    rangees = tuple((y, kit) for y in golden['rangees_retenues'])
    return compter_plan(entree.surfaces[0], rangees, entree.obstacles).modules


def verifier_goldens():
    """Rejoue les 3 comptes. Rend ``[(fichier, compte)]`` ou LÈVE.

    C'est la porte du seed : tant que le moteur ne redonne pas le compte
    témoin AU MODULE PRÈS, rien n'est écrit. Un seed qui figerait un chiffre
    faux serait pire que pas de seed du tout — l'argument de vente de ce
    moteur EST la preuve.
    """
    verifies = []
    for fichier, _code, _designation, _forme in BATIMENTS:
        document = charger_golden(fichier)
        temoin = document['golden']['compte_temoin']
        obtenu = _compte_moteur(document)
        if obtenu != temoin:
            raise CommandError(
                'DIVERGENCE sur %s : le moteur compte %d module(s), le golden '
                'en atteste %d. Le seed de démonstration REFUSE de figer un '
                'chiffre faux — corrigez la réconciliation (AOF183) avant de '
                'rejouer.' % (fichier, obtenu, temoin))
        verifies.append((fichier, obtenu))
    return verifies


def _decimal(valeur):
    return None if valeur is None else Decimal(str(valeur))


def _contour_de(surface):
    """Contour local [x, y] en mètres, quelle que soit la forme de surface."""
    if surface.get('type') == 'polygone':
        return [list(p) for p in surface.get('contour', ())]
    if surface.get('type') == 'rectangle':
        longueur = float(surface.get('longueur_m', 0.0))
        largeur = float(surface.get('largeur_m', 0.0))
        return [[0.0, 0.0], [longueur, 0.0], [longueur, largeur],
                [0.0, largeur]]
    # Arc : la géométrie utile est le rayon + la largeur de bande, pas un
    # contour. On laisse le contour VIDE plutôt que d'en inventer un faux.
    return []


class Command(BaseCommand):
    help = ("Sème l'affaire de démonstration « AO FRDISI » DEPUIS les goldens "
            '(AOF183). Rejouable sans doublon ; refuse si les goldens '
            'divergent ; jamais en production par défaut.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company',
            help='Slug de la société cible (défaut : la première société).')
        parser.add_argument(
            '--confirmer', action='store_true',
            help='OBLIGATOIRE — confirme la création du jeu de démonstration.')

    def handle(self, *args, **options):
        if not options.get('confirmer'):
            raise CommandError(
                'Ajoutez --confirmer : cette commande crée un jeu de '
                'DÉMONSTRATION, elle ne doit jamais partir par accident.')
        if not settings.DEBUG and not getattr(
                settings, 'SEED_AO_DEMO_AUTORISE', False):
            raise CommandError(
                'Hors DEBUG, le seed de démonstration exige le réglage '
                'explicite SEED_AO_DEMO_AUTORISE = True. Une affaire de '
                "démonstration dans les vraies affaires d'un client serait "
                'indéfendable.')

        # PORTE : les goldens d'abord, l'écriture ensuite (jamais l'inverse).
        verifies = verifier_goldens()
        for fichier, compte in verifies:
            self.stdout.write('golden %s : %d modules — vérifié'
                              % (fichier, compte))

        company = self._company(options.get('company'))
        rapport = semer(company)
        self.stdout.write(self.style.SUCCESS(
            'Affaire de démonstration %s : %d bâtiment(s), %d toiture(s), '
            '%d obstacle(s), %d variante(s) — %s'
            % (REFERENCE_DEMO, rapport['batiments'], rapport['toitures'],
               rapport['obstacles'], rapport['variantes'],
               'créée' if rapport['creee'] else 'déjà présente, mise à jour')))

    def _company(self, slug):
        if slug:
            try:
                return Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError('Société inconnue : %s' % slug)
        company = Company.objects.order_by('id').first()
        if company is None:
            raise CommandError('Aucune société en base.')
        return company


@transaction.atomic
def semer(company):
    """Sème (ou remet à jour) l'affaire de démonstration. IDEMPOTENT.

    Toutes les clés de rapprochement sont métier — référence acheteur, code de
    bâtiment, code de planche, repère d'obstacle — jamais un identifiant
    technique : c'est ce qui rend un ré-import sans doublon possible.
    """
    from ...services import creer_appel_offre_depuis_avis

    documents = [(f, c, d, forme, charger_golden(f))
                 for f, c, d, forme in BATIMENTS]
    engagement_total = sum(doc['golden']['engagement']
                           for _f, _c, _d, _forme, doc in documents)

    appel_offre, creee = creer_appel_offre_depuis_avis(company, {
        'reference_acheteur': REFERENCE_DEMO,
        'objet': 'DÉMONSTRATION — centrale photovoltaïque en toiture '
                 '(3 bâtiments)',
        'acheteur': 'Acheteur de démonstration',
        'maitre_ouvrage': 'Maître d\'ouvrage de démonstration',
        'lot': 'Lot unique',
    })
    if appel_offre.engagement_modules != engagement_total:
        appel_offre.engagement_modules = engagement_total
        appel_offre.save(update_fields=['engagement_modules'])

    releve, _ = ReleveAO.objects.get_or_create(
        company=company, appel_offre=appel_offre, date_visite=DATE_RELEVE,
        defaults={'contradictoire': True,
                  'conditions': 'Relevé de démonstration (jeu figé AOF186).'})

    compteurs = {'batiments': 0, 'toitures': 0, 'obstacles': 0,
                 'variantes': 0}
    for _fichier, code, designation, forme, document in documents:
        golden = document['golden']
        batiment, _ = BatimentAO.objects.update_or_create(
            company=company, appel_offre=appel_offre, code=code,
            defaults={'designation': designation,
                      'engagement_modules': golden['engagement']})
        compteurs['batiments'] += 1

        surface = document['surfaces'][0]
        toiture, _ = ToitureAO.objects.update_or_create(
            company=company, batiment=batiment,
            code_document='DEMO-%s' % code,
            defaults={
                'designation': designation,
                'forme': forme,
                'contour_local_m': _contour_de(surface),
                'rayon_ext_m': _decimal(surface.get('rayon_ext_m')),
                'largeur_m': _decimal(surface.get('largeur_m')),
            })
        compteurs['toitures'] += 1

        for brut in document['obstacles']:
            ObstacleAO.objects.update_or_create(
                company=company, toiture=toiture, repere=brut['repere'],
                defaults={
                    'nature': NATURES.get(
                        brut.get('type_obstacle'),
                        ObstacleAO.Nature.CAISSON_TECHNIQUE),
                    'provenance': PROVENANCES.get(
                        brut.get('provenance'),
                        ObstacleAO.Provenance.MESURE),
                    'rect_x0_m': _decimal(brut['x0']),
                    'rect_x1_m': _decimal(brut['x1']),
                    'rect_y0_m': _decimal(brut['y0']),
                    'rect_y1_m': _decimal(brut['y1']),
                    'hauteur_m': _decimal(brut.get('hauteur_m')),
                    'degagement_m': _decimal(brut.get('degagement_m'))
                    or Decimal('0.30'),
                    'regle_degagement': (brut.get('regle_appliquee')
                                         or '')[:255],
                    'releve': releve,
                    'actif': True,
                })
            compteurs['obstacles'] += 1

        VarianteCalepinage.objects.update_or_create(
            company=company, toiture=toiture, nom='Variante retenue (démo)',
            defaults={
                'appel_offre': appel_offre,
                'role': VarianteCalepinage.Role.RETENUE,
                'statut': VarianteCalepinage.Statut.CALCULEE,
                'est_retenue': True,
                'resultat': {'total_modules': golden['compte_temoin']},
                'preuve': {
                    'total_retenu': golden['compte_temoin'],
                    'total_optimal': golden['compte_temoin'],
                    'source': 'golden FRDISI 2026-07-27 (AOF183)',
                },
                'justification': golden.get('commentaire', ''),
            })
        compteurs['variantes'] += 1

    _semer_bordereau(company, appel_offre, documents)
    compteurs['creee'] = creee
    return compteurs


def _semer_bordereau(company, appel_offre, documents):
    """Bordereau de démonstration — quantités ENGAGÉES, aucun coût de revient.

    Les prix unitaires sont des prix de VENTE symboliques : le bordereau remis
    à un maître d'ouvrage n'a jamais porté autre chose. Aucun ``prix_achat``,
    aucune marge, aucun bénéfice n'entre ici (règle produit gravée).
    """
    bordereau, _ = BordereauPrix.objects.get_or_create(
        company=company, appel_offre=appel_offre,
        intitule='Bordereau des prix — DÉMONSTRATION')
    for numero, (_f, code, _d, _forme, document) in enumerate(documents, 1):
        LigneBordereau.objects.update_or_create(
            company=company, bordereau=bordereau,
            designation='Bâtiment %s — fourniture et pose de modules PV'
                        % code,
            defaults={
                'numero': numero,
                # La quantité EST l'engagement du golden — jamais un chiffre
                # tapé ici : c'est l'invariant « quantités du bordereau =
                # engagements portés sur les planches ».
                'quantite': Decimal(str(document['golden']['engagement'])),
                'unite': 'U',
                # Prix de VENTE symbolique. Aucun prix_achat, aucune marge,
                # aucun bénéfice : l'économie vit derrière ao_rentabilite_voir.
                'prix_unitaire': Decimal('2500.00'),
            })
    return bordereau
