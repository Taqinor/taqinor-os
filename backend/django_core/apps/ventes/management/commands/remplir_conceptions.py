"""ADEV141 (D-ACAL-97) — remplir les conceptions des leads existants, LISTE D'ABORD.

Sans option, la commande LISTE (règle du 21/11 : une réparation de données ne
se fait qu'après la liste montrée) : pour chaque lead, société par société,
son marché, l'option que le moteur retiendrait, ou son refus nommé — calculé
par le moteur unique (``conception/moteur.py::calculer_conception``, aucune
écriture ; le tout dans une transaction annulée d'office). Rien n'est écrit.

``--appliquer`` range la conception de chaque lead situé (ville ou GPS : un
lead sans lieu reste un refus listé, jamais rangé) par l'écrivain unique
(``conception/service.py::relancer``, origine ``remplissage``) : une empreinte
égale n'écrit rien, donc une seconde exécution ne change rien. Aucun devis
n'est lu en écriture : le moteur ne lit aucun devis, ``relancer`` n'en écrit
aucun. Un lead d'une société n'est jamais lu pour une autre (la société est
celle du lead, filtrée à la requête).

Un lead qui a déjà une version courante n'est pas recalculé (relecture E3 M2 :
une version née d'une pose serait refaite sans son toit). ``--appliquer`` exige
``--company`` ; la liste ouvre un point de sauvegarde par lead.

``--ecarts`` (ADEV151, LECTURE SEULE) : pour chaque lead à toit tracé, la production
et l'économie que le moteur range AUJOURD'HUI (niveau 14) contre celles du niveau 15
(production de la simulation de la pose, ADEV149 ; pose ajustée souveraine, ADEV150),
écart en kWh et en %, taille, puis ses devis : un brouillon jamais envoyé « changera »,
un devis envoyé ou accepté est listé en lecture seule (il ne change jamais). Le niveau
15 n'est forcé que dans ce processus. Relecture E6 M3 : UNE transaction annulée PAR LEAD
(jamais une transaction autour du passage : aucun verrou de calepinage tenu pendant les
appels au service météo) ; le devis en mémoire du moteur porte lui aussi le niveau 15
(``moteur._devis_neuf``) ; la colonne « actuel » est la conception RANGÉE quand elle existe
(désignations comprises), calculée seulement sinon ; la simulation de la pose tourne ici
(commande, jamais une requête) et son écriture est annulée avec le lead. RIEN n'est écrit
(ni conception, ni devis, ni calepinage) — le cache météo du processus, lui, reste. Liste à
montrer au fondateur AVANT de rendre le niveau 15 courant (ACAL1001). ``--limite N`` :
N leads listés au plus ; ``--lead <id>`` : ce lead seul ; une ligne de progression toutes
les 10 leads sur la sortie d'erreur.

    python manage.py remplir_conceptions [--company <id>] [--appliquer]   (--appliquer : --company requis)
    python manage.py remplir_conceptions --ecarts [--company <id>] [--limite N] [--lead <id>]
"""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

DECLENCHEUR = {'origine': 'remplissage', 'champs': []}
#: Relecture E6 M3 — une ligne de progression (sortie d'erreur) tous les N leads examinés.
PROGRESSION_TOUS = 10


def _leads(company):
    """Les leads vivants de ``company`` (référence par chaîne : aucun import
    du modèle du CRM)."""
    from django.apps import apps
    return apps.get_model('crm', 'Lead').objects.filter(company=company).order_by('pk')


def _leads_deja_ranges(company):
    """Les leads de ``company`` qui ont déjà une version courante."""
    from apps.ventes.models import ConceptionLead
    return set(ConceptionLead.objects.filter(company=company, courante=True, lead__isnull=False)
               .values_list('lead_id', flat=True))


def _ligne(lead, resultat):
    if resultat.etat == 'refus':
        refus = resultat.refus or {}
        return f'  lead #{lead.pk} [{resultat.marche}] REFUS {refus.get("code")} ({refus.get("champ")}) : ' \
               f'{refus.get("message")}'
    return f'  lead #{lead.pk} [{resultat.marche}] option retenue : {resultat.option_retenue}'


class Command(BaseCommand):
    help = ("Liste (par défaut) ou range (--appliquer) la conception du moteur unique de chaque lead "
            "existant, société par société. Aucun devis n'est modifié.")

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--appliquer', action='store_true')
        parser.add_argument('--ecarts', action='store_true',
                            help='ADEV151 : production actuelle contre production de la pose (lecture seule).')
        parser.add_argument('--limite', type=int, default=None, help='--ecarts : N leads listés au plus.')
        parser.add_argument('--lead', type=int, default=None, help='--ecarts : ce lead seul.')

    def handle(self, *args, **opts):
        from authentication.models import Company

        if opts['appliquer'] and not opts['company']:
            # Relecture E3 M2 — une écriture se fait société par société, nommée.
            raise CommandError('--appliquer exige --company <id> : une société à la fois.')
        societes = Company.objects.order_by('pk')
        if opts['company']:
            societes = societes.filter(pk=opts['company'])
        for company in societes:
            self.stdout.write(f'Société #{company.pk} {company.nom}')
            if opts['ecarts']:
                self._ecarts(company, limite=opts['limite'], lead_id=opts['lead'])
            elif opts['appliquer']:
                self._appliquer(company)
            else:
                self._lister(company)

    def _lister(self, company):
        from apps.ventes.conception.moteur import calculer_conception

        completes = refus = erreurs = 0
        with transaction.atomic():
            for lead in _leads(company).iterator():
                try:
                    with transaction.atomic():  # relecture E3 M2 : une erreur de base reste à ce lead
                        resultat = calculer_conception(lead, company)
                except Exception as exc:  # noqa: BLE001 — lead illisible signalé (D-ENF22-BLE001)
                    logger.warning('remplir_conceptions : lead #%s illisible', lead.pk, exc_info=True)
                    erreurs += 1
                    self.stdout.write(f'  lead #{lead.pk} : calcul impossible ({type(exc).__name__})')
                    continue
                completes += resultat.etat != 'refus'
                refus += resultat.etat == 'refus'
                self.stdout.write(_ligne(lead, resultat))
            transaction.set_rollback(True)  # garantie : la liste n'écrit rien
        self.stdout.write(f'  LISTE : {completes} conception(s) complète(s), {refus} refus, {erreurs} erreur(s) '
                          '— rien n\'est écrit ; relancer avec --appliquer pour ranger.')

    def _appliquer(self, company):
        from types import SimpleNamespace

        from apps.ventes.conception.moteur import refus_localisation
        from apps.ventes.conception.service import relancer
        from apps.ventes.selectors_calepinage import pose_du_lead

        ecrites = inchangees = sans_lieu = erreurs = 0
        deja = _leads_deja_ranges(company)
        for lead in _leads(company).iterator():
            if refus_localisation(lead) is not None:  # listé comme refus : rien à ranger sans lieu
                sans_lieu += 1
                continue
            if lead.pk in deja:
                # Relecture E3 M2 — un REMPLISSAGE, pas un rafraîchissement : une
                # version courante (peut-être née d'une pose) n'est pas refaite
                # sans son toit ; le filet de la lecture la tient à jour.
                inchangees += 1
                continue
            try:
                # Relecture E3 M2 (suite) — une pose DÉJÀ enregistrée sur le
                # calepinage ouvert du lead entre dans ce premier calcul, comme
                # pour un événement ``pose_enregistree`` (jamais émis pour les
                # poses d'avant le moteur unique).
                calepinage_id, empreinte_pose = pose_du_lead(company, lead.pk)
                toit = (SimpleNamespace(empreinte=empreinte_pose, plafond_panneaux=None)
                        if empreinte_pose else None)
                relance = relancer(lead, company=company, declencheur=dict(DECLENCHEUR),
                                   toit=toit, calepinage_id=calepinage_id)
            except Exception as exc:  # noqa: BLE001 — un lead en échec n'arrête pas le remplissage (D-ENF22-BLE001)
                logger.warning('remplir_conceptions : lead #%s non rangé', lead.pk, exc_info=True)
                erreurs += 1
                self.stdout.write(f'  lead #{lead.pk} : non rangé ({type(exc).__name__})')
                continue
            ecrites += relance.ecrite
            inchangees += not relance.ecrite
        self.stdout.write(f'  APPLIQUÉ : {ecrites} version(s) rangée(s), {inchangees} inchangée(s), '
                          f'{sans_lieu} sans ville ni GPS (non rangés), {erreurs} erreur(s).')

    def _ecarts(self, company, *, limite=None, lead_id=None):
        """ADEV151 — la liste des écarts de production des brouillons (lecture seule) ;
        relecture E6 M3 : une transaction annulée PAR LEAD."""
        from apps.ventes.selectors_calepinage import pose_du_lead

        leads = _leads(company)
        if lead_id:
            leads = leads.filter(pk=lead_id)
        listes = examines = 0
        for lead in leads.iterator():
            if limite is not None and listes >= limite:
                break
            examines += 1
            if examines % PROGRESSION_TOUS == 0:
                self.stderr.write(f'  … {examines} lead(s) examiné(s), {listes} listé(s)')
            calepinage_id, empreinte_pose = pose_du_lead(company, lead.pk)
            if not calepinage_id:
                continue  # sans toit tracé : ADEV154 (--ecarts-sans-toit)
            try:
                with transaction.atomic():
                    lignes = _lignes_ecart(lead, calepinage_id, *_actuel_et_pose(
                        lead, company, calepinage_id, empreinte_pose))
                    transaction.set_rollback(True)  # garantie : ce lead n'écrit rien
            except Exception as exc:  # noqa: BLE001 — un lead illisible est dit, la liste continue (D-ENF22-BLE001)
                logger.warning('remplir_conceptions --ecarts : lead #%s illisible', lead.pk, exc_info=True)
                self.stdout.write(f'  lead #{lead.pk} : calcul impossible ({type(exc).__name__})')
                continue
            listes += 1
            for ligne in lignes:
                self.stdout.write(ligne)
        self.stdout.write(f'  ÉCARTS : {listes} lead(s) à toit tracé listé(s) — rien n\'est écrit ; le niveau 15 '
                          'n\'est rendu courant qu\'après lecture de cette liste par le fondateur (ACAL1001).')


def _actuel_et_pose(lead, company, calepinage_id, empreinte_pose):
    """``(actuel, pose)`` d'un lead à toit tracé : la conception RANGÉE courante (sinon
    calculée au niveau courant, désignations comprises) contre le niveau 15 (pose simulée
    ICI, jamais dans une requête), désignations comprises."""
    from types import SimpleNamespace

    from apps.ventes.conception.moteur import calculer_conception
    from apps.ventes.conception.porte_calepinage import contexte_de_pose, designations_du_calepinage
    from apps.ventes.models import ConceptionLead

    toit = SimpleNamespace(empreinte=empreinte_pose, plafond_panneaux=None) if empreinte_pose else None
    designes = designations_du_calepinage(company, calepinage_id) or None
    rangee = ConceptionLead.objects.filter(company=company, lead=lead, courante=True).first()
    actuel = (SimpleNamespace(etat=rangee.etat, refus=rangee.refus, valeurs=rangee.valeurs,
                              option_retenue=rangee.option_retenue or None) if rangee is not None
              else calculer_conception(lead, company, toit=toit, calepinage_id=calepinage_id, imposes=designes,
                                       souple=designes is not None))
    with _niveau_pose_reelle(), contexte_de_pose(simuler=True):
        pose = calculer_conception(lead, company, toit=toit, calepinage_id=calepinage_id, imposes=designes,
                                   souple=designes is not None)
    return actuel, pose


def _niveau_pose_reelle():
    """Le niveau de règles 15 (``REGLES_POSE_REELLE_2111``) forcé DANS CE PROCESSUS le
    temps d'un calcul de liste, jamais rendu courant ailleurs."""
    from contextlib import contextmanager

    from apps.ventes.domain import regles_calcul as RC

    @contextmanager
    def forcer():
        courant = RC.REGLES_COURANTES
        RC.REGLES_COURANTES = RC.REGLES_POSE_REELLE_2111
        try:
            yield
        finally:
            RC.REGLES_COURANTES = courant
    return forcer()


def _valeur(resultat, cle):
    retenue = (resultat.valeurs or {}).get(resultat.option_retenue) or {}
    return (retenue.get(cle) or {}).get('valeur'), (retenue.get(cle) or {}).get('source')


def _nombre(valeur):
    return '—' if valeur is None else f'{valeur:,.0f}'.replace(',', ' ')


def _lignes_ecart(lead, calepinage_id, actuel, pose):
    """Les lignes d'UN lead : production / économie / taille actuelles contre pose, puis
    ses devis (brouillon : changera ; envoyé ou accepté : lecture seule)."""
    from apps.ventes.models import Devis

    if actuel.etat == 'refus' or pose.etat == 'refus':
        refus = (actuel.refus if actuel.etat == 'refus' else pose.refus) or {}
        return [f'  lead #{lead.pk} (calepinage #{calepinage_id}) : REFUS {refus.get("code")} — '
                f'{refus.get("message")}']
    (prod_a, _), (prod_p, source) = _valeur(actuel, 'production_annuelle'), _valeur(pose, 'production_annuelle')
    eco_a, eco_p = _valeur(actuel, 'economies_annuelles')[0], _valeur(pose, 'economies_annuelles')[0]
    nb_a, nb_p = _valeur(actuel, 'nb_panneaux')[0], _valeur(pose, 'nb_panneaux')[0]
    if prod_a is not None and prod_p is not None:
        ecart = prod_p - prod_a
        pct = f'{ecart / prod_a * 100:+.1f} %' if prod_a else '—'
        texte_ecart = f'{ecart:+,.0f} kWh ({pct})'.replace(',', ' ')
    else:
        texte_ecart = '—'
    change = (prod_a, eco_a, nb_a) != (prod_p, eco_p, nb_p)
    lignes = [f'  lead #{lead.pk} (calepinage #{calepinage_id}) : production {_nombre(prod_a)} → {_nombre(prod_p)} '
              f'kWh/an (écart {texte_ecart}{"" if source == "pose" else ", simulation de la pose non faite"}) ; '
              f'économie {_nombre(eco_a)} → {_nombre(eco_p)} MAD/an ; taille {nb_a} → {nb_p} panneaux']
    for devis in Devis.objects.filter(company=lead.company_id, lead=lead, is_active=True).order_by('pk'):
        if devis.statut == 'brouillon':
            lignes.append(f'    {devis.reference} brouillon jamais envoyé — changera : {"oui" if change else "non"}')
        else:
            lignes.append(f'    {devis.reference} {devis.statut} — lecture seule : ne changera jamais')
    return lignes
