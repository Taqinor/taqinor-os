"""AUD316 / AUD317 — TEST DE PARITÉ des cascades de statut.

Ce module est une GARDE SÉMANTIQUE, pas un épinglage de lignes : il déclare
les CHEMINS d'écriture réels et asserte que chacun produit le MÊME jeu
d'effets observables. Il échoue le jour où un quatrième chemin réapparaît avec
sa propre demi-cascade — c'est exactement ce qui s'était produit :

* `avancer-etape` (l'écran de timeline poussé par le produit) n'appelait ni
  `verifier_gate_acompte_planification` (YSERV1), ni `chantier_receptionne`
  (YSERV4 → enquête NPS compta, proposition de contrat d'entretien sav,
  baseline monitoring), ni `notifier_reception_solde_a_facturer` (YSERV7), ni
  la note de chatter « Chantier réceptionné… » (absente aussi de
  `mise-en-service`) ;
* la création par l'événement `devis_accepted` n'appelait jamais
  `activity.log_creation`, contrairement aux deux chemins API.

Run :
    python manage.py test apps.installations.tests_parite_cascade -v2
"""
import ast
import itertools
import pathlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.models import (
    HandoverPack, Installation, JalonProjet, StageModele, StockReservation,
)
from apps.installations.services import seed_stages
from apps.stock.models import EmplacementStock, Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'parite-co-{n}', defaults={'nom': f'Parité Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CascadeReceptionPariteTests(TestCase):
    """Les trois chemins arrivant à RECEPTIONNE produisent les MÊMES effets."""

    #: (nom, callable(test, installation) -> réponse HTTP)
    CHEMINS_RECEPTION = ('patch', 'mise_en_service', 'avancer_etape')

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'parite-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)
        EmplacementStock.objects.create(company=self.company, nom='Dépôt')
        # Étapes amorcées pour les TROIS chemins (parité stricte : le
        # pointeur `etape` doit s'aligner partout). Gates rendus consultatifs
        # pour n'exercer QUE la cascade d'effets, pas les exigences CH2.
        seed_stages(self.company)
        StageModele.objects.filter(company=self.company).update(bloquant=False)

    # ── Fabrique d'un chantier prêt à être réceptionné ──────────────────────
    def _chantier(self):
        n = next(_seq)
        produit = Produit.objects.create(
            company=self.company, nom=f'Panneau {n}',
            prix_vente=Decimal('100'), quantite_stock=20)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'parite-{self.company.id}-{n}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client', stage='SIGNED')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PARITE-{n}', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('4'), prix_unitaire=Decimal('100'))
        inst = Installation.objects.create(
            company=self.company, client=client, devis=devis,
            reference=f'CHT-PARITE-{n}',
            statut=Installation.Statut.INSTALLE,
            bom=[{'produit_id': produit.id, 'designation': produit.nom,
                  'quantite': 4}])
        from apps.installations.services import seed_reservations
        seed_reservations(inst)
        return inst

    # ── Les trois chemins ───────────────────────────────────────────────────
    def _via_patch(self, inst):
        return self.api.patch(
            f'{BASE}/{inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')

    def _via_mise_en_service(self, inst):
        return self.api.post(
            f'{BASE}/{inst.id}/mise-en-service/', {}, format='json')

    def _via_avancer_etape(self, inst):
        # L'étape « remise_client » porte `statut_legacy = RECEPTIONNE`.
        return self.api.post(
            f'{BASE}/{inst.id}/avancer-etape/',
            {'etape': 'remise_client'}, format='json')

    def _executer(self, chemin, inst):
        return getattr(self, f'_via_{chemin}')(inst)

    # ── Le jeu d'effets observables, identique pour les trois ───────────────
    def _assert_cascade_complete(self, inst, chemin):
        inst.refresh_from_db()
        canon = Installation.canonical_statut(inst.statut)
        self.assertEqual(canon, Installation.Statut.RECEPTIONNE, chemin)
        # N6/N7 — jalon horodaté.
        self.assertIsNotNone(inst.date_reception, f'{chemin} : date_reception')
        # FG70 — au moins un équipement de parc créé (via apps.sav.services).
        from apps.sav.models import Equipement
        self.assertTrue(
            Equipement.objects.filter(installation=inst).exists(),
            f'{chemin} : parc FG70')
        # CH4 — pack de remise persisté.
        self.assertTrue(
            HandoverPack.objects.filter(installation=inst).exists(),
            f'{chemin} : HandoverPack CH4')
        # YSERV7 — jalon RECEPTION atteint (rappel de facturation du solde).
        jalon = JalonProjet.objects.filter(
            installation=inst, phase=JalonProjet.Phase.RECEPTION).first()
        self.assertIsNotNone(jalon, f'{chemin} : JalonProjet YSERV7')
        self.assertTrue(jalon.atteint, f'{chemin} : jalon atteint')
        # YSERV4 → compta : enquête NPS créée par l'abonné de l'événement.
        from apps.compta.models import EnqueteNPS
        self.assertTrue(
            EnqueteNPS.objects.filter(chantier_id=inst.id).exists(),
            f'{chemin} : enquête NPS (compta)')
        # YSERV4 → sav : activité « Proposer le contrat d'entretien ».
        from apps.records.models import Activity
        self.assertTrue(
            Activity.objects.filter(
                company=self.company,
                note__contains=f'[yserv10:{inst.id}]').exists(),
            f'{chemin} : proposition de contrat d’entretien (sav)')
        # Note de chatter « Chantier réceptionné… ».
        notes = [a.body or '' for a in inst.activites.all()]
        self.assertTrue(
            any('réceptionné' in n.lower() for n in notes),
            f'{chemin} : note de chatter — {notes}')
        # Pointeur d'étape aligné sur le statut hérité.
        self.assertIsNotNone(inst.etape_id, f'{chemin} : étape alignée')
        self.assertEqual(
            Installation.canonical_statut(inst.etape.statut_legacy),
            Installation.Statut.RECEPTIONNE, f'{chemin} : étape cohérente')
        # N14 — état des réservations, comparé ENTRE chemins (l'arrivée à
        # RECEPTIONNE ne consomme rien : c'est « Installé » qui consomme et
        # « Clôturé » qui libère — ce qui compte ici est que les trois chemins
        # laissent le stock dans le MÊME état).
        return {
            'reservations_actives': StockReservation.objects.filter(
                installation=inst, active=True, consomme=False).count(),
            'reservations_consommees': StockReservation.objects.filter(
                installation=inst, consomme=True).count(),
            'jalons_reception': JalonProjet.objects.filter(
                installation=inst,
                phase=JalonProjet.Phase.RECEPTION).count(),
            'packs': HandoverPack.objects.filter(installation=inst).count(),
        }

    def test_parite_des_trois_chemins_de_reception(self):
        """DOIT ÉCHOUER avant AUD316 sur `avancer_etape` (5 assertions) et
        `mise_en_service` (2 assertions)."""
        empreintes = {}
        for chemin in self.CHEMINS_RECEPTION:
            with self.subTest(chemin=chemin):
                inst = self._chantier()
                reponse = self._executer(chemin, inst)
                self.assertIn(
                    reponse.status_code, (200, 201),
                    f'{chemin} : {getattr(reponse, "data", None)}')
                empreintes[chemin] = self._assert_cascade_complete(
                    inst, chemin)
        # PARITÉ STRICTE : les trois chemins laissent le MÊME état observable.
        valeurs = list(empreintes.values())
        for chemin, empreinte in empreintes.items():
            self.assertEqual(empreinte, valeurs[0],
                             f'{chemin} diverge : {empreintes}')


class CreationChatterPariteTests(TestCase):
    """AUD316 — la création journalise au chatter sur les TROIS chemins."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'parite-cre-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')

    def _devis(self):
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'parite-cre-{self.company.id}-{n}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client', stage='SIGNED')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-PC-{n}', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))

    def test_le_chemin_evenementiel_journalise_la_creation(self):
        """ROUGE avant AUD316 : `receivers._creer_chantier_on_devis_accepted`
        n'appelait jamais `activity.log_creation`."""
        from apps.installations.receivers import (
            _creer_chantier_on_devis_accepted,
        )
        devis = self._devis()
        # Le signal `devis_accepted` porte `ancien_statut` (contrat partagé
        # avec les abonnés crm/contrats) : l'appel direct doit le fournir.
        _creer_chantier_on_devis_accepted(
            sender=None, devis=devis, user=self.user,
            ancien_statut=Devis.Statut.ENVOYE)
        inst = Installation.objects.get(devis=devis)
        self.assertTrue(
            inst.activites.filter(kind='creation').exists(),
            'aucune ligne « Chantier créé » sur le chemin événementiel')

    def test_le_bouton_creer_depuis_devis_ne_double_pas_la_ligne(self):
        devis = self._devis()
        api = auth(self.user)
        r = api.post(f'{BASE}/creer-depuis-devis/',
                     {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        inst = Installation.objects.get(devis=devis)
        self.assertEqual(inst.activites.filter(kind='creation').count(), 1)


class CascadeTerminaisonInterventionPariteTests(TestCase):
    """AUD317 — les chemins de TERMINAISON d'une intervention convergent.

    `Intervention.statut` avait 5 chemins d'écriture, dont un seul complet.
    `create` écrivait `statut` librement (contournant la garde F8 et
    n'émettant jamais `intervention_completed` — ticket SAV laissé OUVERT) et
    la synchro terrain hors-ligne n'avait AUCUN op_type capable de clôturer
    (statut figé sur « Sur site » à jamais)."""

    CHEMINS_TERMINAISON = ('patch', 'create', 'field_sync')

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'parite-iv-{next(_seq)}', password='x',
            company=self.company, role_legacy='admin')
        self.api = auth(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference=f'CHT-IV-{next(_seq)}',
            statut=Installation.Statut.EN_COURS)

    def _ticket(self):
        from apps.sav.models import Ticket
        n = next(_seq)
        # `sav.Ticket` n'a pas de champ `titre` (le libellé du problème est
        # `description`) et son `client` est obligatoire (FK PROTECT).
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'parite-iv-{self.company.id}-{n}@example.invalid')
        return Ticket.objects.create(
            company=self.company, reference=f'TIC-{n}', client=client,
            description='Panne onduleur', statut=Ticket.Statut.EN_COURS)

    def _via_patch(self, ticket):
        from apps.installations.models import Intervention
        iv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.user)
        r = self.api.patch(
            f'/api/django/installations/interventions/{iv.id}/',
            {'statut': Intervention.Statut.VALIDEE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return iv

    def _via_create(self, ticket):
        from apps.installations.models import Intervention
        from apps.installations.models_field import InterventionPreparation
        # AUD317 — la création ne pose plus un statut librement : le service
        # canonique applique les gardes, et F5 refuse de quitter « À
        # préparer » sans « Tout est chargé » (qui ne peut exister qu'APRÈS
        # la création). Le chemin « create » suit donc le flux produit :
        # créer, confirmer la préparation, puis terminer par le canon.
        r = self.api.post(
            '/api/django/installations/interventions/',
            {'installation': self.inst.id, 'ticket': ticket.id,
             'type_intervention': Intervention.Type.DEPANNAGE},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        iv = Intervention.objects.get(pk=r.data['id'])
        prep, _ = InterventionPreparation.objects.get_or_create(
            intervention=iv, defaults={'company': self.company})
        prep.tout_charge = True
        prep.save(update_fields=['tout_charge'])
        r2 = self.api.patch(
            f'/api/django/installations/interventions/{iv.id}/',
            {'statut': Intervention.Statut.VALIDEE}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        return iv

    def _via_field_sync(self, ticket):
        from apps.installations.models import Intervention
        iv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.user)
        r = self.api.post(
            '/api/django/installations/sync/',
            {'ops': [{'client_op_id': f'op-fin-{next(_seq)}',
                      'op_type': 'intervention.terminer',
                      'payload': {'intervention': iv.id,
                                  'statut': Intervention.Statut.VALIDEE}}]},
            format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(r.data['applied'], 1, r.data)
        return iv

    def _assert_terminaison_complete(self, iv, ticket, chemin):
        from apps.installations.models import Intervention
        from apps.sav.models import Ticket
        iv.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(iv.statut, Intervention.Statut.VALIDEE, chemin)
        self.assertIsNotNone(iv.date_realisee, f'{chemin} : date_realisee')
        self.assertEqual(ticket.statut, Ticket.Statut.RESOLU,
                         f'{chemin} : ticket SAV (YSERV2)')
        self.assertTrue(iv.lien_rapport_token,
                        f'{chemin} : jeton compte-rendu (ZFSM2)')
        notes = [a.body or '' for a in self.inst.activites.all()]
        self.assertTrue(
            any('Intervention' in n for n in notes),
            f'{chemin} : note au chatter du chantier — {notes}')

    def test_parite_des_chemins_de_terminaison(self):
        """DOIT ÉCHOUER avant AUD317 sur `create` et `field_sync`."""
        for chemin in self.CHEMINS_TERMINAISON:
            with self.subTest(chemin=chemin):
                ticket = self._ticket()
                iv = getattr(self, f'_via_{chemin}')(ticket)
                self._assert_terminaison_complete(iv, ticket, chemin)

    def test_annulation_de_chantier_laisse_le_statut_fige_par_decision(self):
        """AUD317 — DÉCISION EXPLICITE, pas un oubli : `annuler_interventions_
        ouvertes` pose `annulee=True` et NE TERMINE PAS l'intervention.

        Une intervention annulée n'a pas été réalisée : la basculer
        « Terminée » la ferait entrer dans les statistiques de réalisation,
        déclencherait la facturation ZFSM4 et résoudrait le ticket SAV lié.
        Changer ce choix impose de changer CE test."""
        from apps.installations.models import Intervention
        from apps.installations.services import (
            annuler_interventions_ouvertes,
        )
        from apps.sav.models import Ticket
        ticket = self._ticket()
        iv = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.user)

        nb = annuler_interventions_ouvertes(self.inst, self.user)

        self.assertEqual(nb, 1)
        iv.refresh_from_db()
        ticket.refresh_from_db()
        self.assertTrue(iv.annulee, 'le drapeau orthogonal est posé')
        self.assertEqual(iv.statut, Intervention.Statut.SUR_SITE,
                         'le statut reste FIGÉ — décision documentée')
        self.assertIsNone(iv.date_realisee)
        self.assertEqual(ticket.statut, Ticket.Statut.EN_COURS,
                         'le ticket SAV ne se résout pas sur une annulation')


class PointDEcritureUniqueTests(TestCase):
    """AUD316 — GARDE AST : `Installation.statut` ne s'écrit QUE dans le
    service unique. Une vue qui recommencerait à poser le statut « à la main »
    (et donc à ré-inventer une demi-cascade) fait échouer ce test."""

    #: Fichiers scannés — ceux qui portent le flux chantier.
    FICHIERS = (
        'views/installation.py',
        'services.py',
    )
    #: SEULE fonction autorisée à écrire `Installation.statut`.
    FONCTION_AUTORISEE = 'changer_statut_chantier'
    #: Noms de variables tenant une Installation dans ce code.
    NOMS_INSTALLATION = {'inst', 'installation', 'chantier'}

    def _ecritures_statut(self, chemin):
        """(fonction, ligne) de chaque écriture de `<installation>.statut`."""
        source = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(source)
        trouvees = []

        class Visiteur(ast.NodeVisitor):
            def __init__(self):
                self.pile = []

            def _visit_fn(self, node):
                self.pile.append(node.name)
                self.generic_visit(node)
                self.pile.pop()

            visit_FunctionDef = _visit_fn
            visit_AsyncFunctionDef = _visit_fn

            def visit_Assign(self, node):
                for cible in node.targets:
                    if (isinstance(cible, ast.Attribute)
                            and cible.attr == 'statut'
                            and isinstance(cible.value, ast.Name)
                            and cible.value.id in (
                                PointDEcritureUniqueTests.NOMS_INSTALLATION)):
                        trouvees.append(
                            (self.pile[-1] if self.pile else '<module>',
                             node.lineno))
                self.generic_visit(node)

        Visiteur().visit(arbre)
        return trouvees

    def _saves_avec_statut(self, chemin):
        """(fonction, ligne) de chaque `save(update_fields=[... 'statut' ...])`
        sur une Installation."""
        source = chemin.read_text(encoding='utf-8')
        arbre = ast.parse(source)
        trouvees = []

        class Visiteur(ast.NodeVisitor):
            def __init__(self):
                self.pile = []

            def _visit_fn(self, node):
                self.pile.append(node.name)
                self.generic_visit(node)
                self.pile.pop()

            visit_FunctionDef = _visit_fn
            visit_AsyncFunctionDef = _visit_fn

            def visit_Call(self, node):
                fn = node.func
                if (isinstance(fn, ast.Attribute) and fn.attr == 'save'
                        and isinstance(fn.value, ast.Name)
                        and fn.value.id in (
                            PointDEcritureUniqueTests.NOMS_INSTALLATION)):
                    for kw in node.keywords:
                        if kw.arg != 'update_fields':
                            continue
                        if not isinstance(kw.value, (ast.List, ast.Tuple)):
                            continue
                        for elt in kw.value.elts:
                            if (isinstance(elt, ast.Constant)
                                    and elt.value == 'statut'):
                                trouvees.append(
                                    (self.pile[-1] if self.pile
                                     else '<module>', node.lineno))
                self.generic_visit(node)

        Visiteur().visit(arbre)
        return trouvees

    def test_une_seule_fonction_ecrit_installation_statut(self):
        racine = pathlib.Path(__file__).resolve().parent
        fautives = []
        for rel in self.FICHIERS:
            chemin = racine / rel
            for fonction, ligne in self._ecritures_statut(chemin):
                if fonction != self.FONCTION_AUTORISEE:
                    fautives.append(f'{rel}:{ligne} dans {fonction}()')
        self.assertEqual(
            fautives, [],
            "Installation.statut ne doit s'écrire QUE dans "
            f"services.{self.FONCTION_AUTORISEE}() — trouvé : {fautives}")

    def test_aucun_save_update_fields_statut_hors_du_service(self):
        racine = pathlib.Path(__file__).resolve().parent
        fautives = []
        for rel in self.FICHIERS:
            chemin = racine / rel
            for fonction, ligne in self._saves_avec_statut(chemin):
                if fonction != self.FONCTION_AUTORISEE:
                    fautives.append(f'{rel}:{ligne} dans {fonction}()')
        self.assertEqual(
            fautives, [],
            "save(update_fields=[...'statut'...]) sur une Installation ne doit "
            f"exister QUE dans services.{self.FONCTION_AUTORISEE}() — "
            f"trouvé : {fautives}")

    def test_une_seule_fonction_ecrit_intervention_statut(self):
        """AUD317 — même garde, côté intervention."""
        racine = pathlib.Path(__file__).resolve().parent
        noms_origine = PointDEcritureUniqueTests.NOMS_INSTALLATION
        PointDEcritureUniqueTests.NOMS_INSTALLATION = {
            'interv', 'iv', 'intervention'}
        try:
            fautives = []
            for rel in ('views/intervention.py', 'field_sync.py',
                        'services.py'):
                for fonction, ligne in self._ecritures_statut(racine / rel):
                    if fonction != 'changer_statut_intervention':
                        fautives.append(f'{rel}:{ligne} dans {fonction}()')
        finally:
            PointDEcritureUniqueTests.NOMS_INSTALLATION = noms_origine
        self.assertEqual(
            fautives, [],
            "Intervention.statut ne doit s'écrire QUE dans "
            f"services.changer_statut_intervention() — trouvé : {fautives}")
