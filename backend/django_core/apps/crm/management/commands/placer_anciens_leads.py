"""MRY30 — Place les ANCIENS leads dans les cadences du moteur de relances.

Le moteur ne démarre que sur les leads qui ARRIVENT : sans cette commande, le
portefeuille déjà présent — plusieurs centaines de dossiers, dont les 930
leads du miroir Odoo — resterait sans aucune cadence. Décision fondateur du
06/09/2026 : « tous les anciens leads non Froid sont traités ; le moteur
décide à quelle étape des six appels chacun se trouve ».

Toute la décision vit dans ``crm.services.placer_anciens_leads`` (le même
service que l'endpoint ``POST leads/placement-cadences/``) : cette commande
n'est qu'une PORTE, jamais une seconde logique qui divergerait de l'écran.

DRY-RUN PAR DÉFAUT. Rien n'est écrit sans ``--apply`` — et l'aperçu n'est pas
une estimation : il partage le CALCUL de l'application (mêmes décisions, mêmes
créneaux, mêmes dates), donc ce qu'il affiche est exactement ce que ``--apply``
fera.

    python manage.py placer_anciens_leads [--company <slug|id>] [--apply]
                                          [--limite N]

``--apply`` place PAR LOTS de ``--limite`` leads (défaut 40) et RECOMMENCE
jusqu'à ce qu'il ne reste rien, une ligne de progression par lot. Écrire 277
dossiers d'un seul trait dépassait le délai du navigateur côté écran (deux 499
le 07/09/2026) ; la commande suit la même découpe pour rester interruptible et
reprenable — chaque lot est acquis, le suivant repart de l'état réel.

``--company`` est FACULTATIF quand l'installation ne compte qu'UNE société :
l'exiger là où il n'y a aucun choix à faire n'ajoute qu'une occasion de se
tromper. Dès qu'il y en a deux, il redevient obligatoire — placer des
centaines de leads dans la mauvaise société ne se défait pas d'un clic.
"""
from django.core.management.base import BaseCommand, CommandError

#: Lignes d'aperçu imprimées (le rapport en porte 20 au plus, cf. contrat).
APERCU_MAX = 20


class Command(BaseCommand):
    help = ('MRY30 — Place les anciens leads dans les cadences de relance '
            '(dry-run par défaut).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Slug ou id de la société cible (facultatif si une seule).')
        parser.add_argument(
            '--apply', action='store_true',
            help='Écrit réellement (sinon : aperçu, aucune écriture).')
        parser.add_argument(
            '--limite', dest='limite', type=int, default=None,
            help='Leads placés par lot (1..200, défaut 40).')

    def handle(self, *args, **options):
        from apps.crm.services import (
            PLACEMENT_LOT_DEFAUT, PLACEMENT_LOT_MAX, placer_anciens_leads)

        company = _resoudre_company(options.get('company'))
        apply = bool(options.get('apply'))
        limite = options.get('limite')
        limite = PLACEMENT_LOT_DEFAUT if limite is None else limite
        if not 1 <= limite <= PLACEMENT_LOT_MAX:
            raise CommandError(
                f'--limite doit être entre 1 et {PLACEMENT_LOT_MAX} '
                f'(reçu {limite}).')

        if not apply:
            self._imprimer(
                placer_anciens_leads(company, None, apply=False,
                                     limite=limite),
                apply=False, company=company)
            return

        # Les lots s'enchaînent jusqu'à `restants == 0`. Le rapport de
        # SYNTHÈSE est celui du PREMIER lot : lui seul décrit le portefeuille
        # entier (`par_etape`, `apercu`, `reveils_jusqu_au`) — après le
        # dernier lot il ne reste, par construction, plus rien à décrire.
        synthese = None
        applique = erreurs = 0
        lot = 0
        while True:
            lot += 1
            rapport = placer_anciens_leads(company, None, apply=True,
                                           limite=limite)
            synthese = synthese or dict(rapport)
            applique += rapport['applique']
            erreurs += rapport['erreurs']
            self.stdout.write(
                f'Lot {lot} : {rapport["applique"]} placé(s), '
                f'{rapport["erreurs"]} en échec — '
                f'restants {rapport["restants"]}.')
            if rapport['restants'] <= 0:
                break
            if rapport['applique'] == 0:
                # Un lot qui ne place RIEN ne placera rien de plus au tour
                # suivant : boucler serait infini. On s'arrête en le disant.
                self.stdout.write(self.style.WARNING(
                    'Lot sans progression : arrêt (voir les journaux).'))
                break
        synthese.update(applique=applique, erreurs=erreurs,
                        restants=rapport['restants'])
        self._imprimer(synthese, apply=True, company=company)

    def _imprimer(self, rapport, *, apply, company):
        prefixe = '' if apply else '[aperçu] '
        ecrire = self.stdout.write
        ecrire(f'{prefixe}Société : {company.slug or company.pk}')
        ecrire(f'{prefixe}Candidats : {rapport["total_candidats"]} — '
               f'à placer : {rapport["a_placer"]}')
        ignores = rapport['ignores']
        ecrire(f'{prefixe}Ignorés : déjà en cadence '
               f'{ignores["deja_en_cadence"]}, devis accepté non signé '
               f'{ignores["devis_accepte_non_signe"]}')

        if rapport['par_etape']:
            ecrire(f'{prefixe}Par décision :')
            for bloc in rapport['par_etape']:
                ecrire(f'{prefixe}  {bloc["nombre"]:>5}  {bloc["code"]:<24} '
                       f'({bloc["cadence"]}) — {bloc["libelle"]}')
        if rapport['reveils_jusqu_au']:
            ecrire(f'{prefixe}Réveils étalés jusqu\'au '
                   f'{rapport["reveils_jusqu_au"]}.')

        if rapport['apercu']:
            ecrire(f'{prefixe}Aperçu ({len(rapport["apercu"])} premiers, '
                   'les plus récents d\'abord) :')
            for ligne in rapport['apercu'][:APERCU_MAX]:
                ecrire(f'{prefixe}  #{ligne["lead"]} {ligne["nom"]} '
                       f'[{ligne["stage_libelle"]}] — {ligne["jours"]} j — '
                       f'{ligne["code"]} → « {ligne["prochaine_touche"]} » '
                       f'{ligne["prochaine_le"] or "—"}')

        if rapport['erreurs']:
            ecrire(self.style.WARNING(
                f'{prefixe}{rapport["erreurs"]} lead(s) en échec — voir les '
                'journaux (les autres ont bien été traités).'))
        if apply:
            ecrire(self.style.SUCCESS(
                f'{rapport["applique"]} lead(s) placé(s).'))
        else:
            ecrire(self.style.WARNING(
                'Aperçu — AUCUNE écriture. Relancer avec --apply.'))


def _resoudre_company(brut):
    """Société cible : celle nommée, ou l'UNIQUE société de l'installation."""
    from authentication.models import Company

    if brut in (None, ''):
        societes = list(Company.objects.order_by('pk')[:2])
        if len(societes) == 1:
            return societes[0]
        if not societes:
            raise CommandError('Aucune société en base.')
        raise CommandError(
            '--company est obligatoire : plusieurs sociétés existent '
            '(slug ou id attendu).')
    company = Company.objects.filter(slug=brut).first()
    if company is None and str(brut).isdigit():
        company = Company.objects.filter(pk=int(brut)).first()
    if company is None:
        raise CommandError(
            f'Société introuvable : {brut!r} (slug ou id attendu).')
    return company
