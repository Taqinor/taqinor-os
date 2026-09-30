"""QA-COHERENCE — le moteur, la commande et la tâche nocturne.

Couvre : cycle de vie persistant (nouvelle → vue → résolue), forme JSON
(clés « golden » du contrat de ``audit_coherence --json``), ``--no-persist``
n'écrit rien, un objet qui plante n'arrête pas la passe, isolation
multi-tenant, calcul annulé (le constructeur de document ne laisse aucune
trace), digest des seules nouvelles violations.

Le vrai constructeur de document n'est jamais appelé : il est remplacé par un
constructeur injecté (``constructeur=``) — aucune dépendance réseau/MinIO.
"""
import datetime
import io
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.coherence import moteur
from apps.ventes.coherence.registre import (GRAVITE_CRITIQUE, PORTEE_DEVIS,
                                            REGISTRE, Regle)
from apps.ventes.models import Devis, LigneDevis, ViolationCoherence
from authentication.models import Company

User = get_user_model()
_CTR = [0]
REGLE = 'DOC_ACCEPTE_SANS_DATE'

CLES_JSON = {'companies', 'checked', 'violations', 'new', 'rule_errors',
             'duration_s'}
CLES_VIOLATION = {'rule', 'severity', 'object_type', 'object_id',
                  'reference', 'company', 'message', 'values'}


def _n():
    _CTR[0] += 1
    return _CTR[0]


def _donnees_propres(devis, options):
    return {'discount_pct': 0.0, 'totaux_all': {
        'ht_brut': 10000.0, 'remise': 0.0, 'ht_net': 10000.0, 'tva': 2000.0,
        'ttc': 12000.0, 'tva_par_taux': [
            {'taux': 20.0, 'montant': 2000.0, 'ht_net': 10000.0}]}}


class _Base(TestCase):
    def societe(self):
        company = Company.objects.create(nom=f'Coh Moteur {_n()}',
                                         slug=f'coh-moteur-{_n()}')
        user = User.objects.create_user(
            username=f'cohm_{_n()}', password='x', role_legacy='responsable',
            company=company)
        client = Client.objects.create(
            company=company, nom='Coh', prenom='M',
            telephone=f'+2126110{_n():05d}')
        produit = Produit.objects.create(
            company=company, nom='Kit', sku=f'COHM-{_n()}',
            prix_vente=Decimal('10000'), quantite_stock=10)
        return company, user, client, produit

    def devis(self, company, user, client, produit, *, date_acceptation=None):
        d = Devis.objects.create(
            company=company, created_by=user, client=client,
            reference=f'DEV-COHM-{_n()}', statut=Devis.Statut.ACCEPTE,
            date_acceptation=date_acceptation, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=d, produit=produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        return d


class TestCycleDeVie(_Base):
    def test_nouvelle_puis_vue_puis_resolue(self):
        company, user, client, produit = self.societe()
        d = self.devis(company, user, client, produit)

        r1 = moteur.run_audit(company=company, rules=[REGLE])
        self.assertEqual(len(r1.new), 1)
        ligne = ViolationCoherence.objects.get(company=company)
        self.assertEqual(ligne.rule_id, REGLE)
        self.assertEqual(ligne.object_id, d.pk)
        self.assertIsNone(ligne.resolved_at)
        premier = ligne.first_seen

        r2 = moteur.run_audit(company=company, rules=[REGLE])
        self.assertEqual(len(r2.violations), 1)
        self.assertEqual(r2.new, [])
        ligne.refresh_from_db()
        self.assertEqual(ligne.first_seen, premier)
        self.assertGreaterEqual(ligne.last_seen, premier)
        self.assertIsNone(ligne.resolved_at)

        Devis.objects.filter(pk=d.pk).update(
            date_acceptation=datetime.date(2026, 9, 10))
        r3 = moteur.run_audit(company=company, rules=[REGLE])
        self.assertEqual(r3.violations, [])
        self.assertEqual(r3.resolved, 1)
        ligne.refresh_from_db()
        self.assertIsNotNone(ligne.resolved_at)
        self.assertEqual(ViolationCoherence.objects.count(), 1)

        # Réapparition : de nouveau une NOUVELLE violation, même ligne.
        Devis.objects.filter(pk=d.pk).update(date_acceptation=None)
        r4 = moteur.run_audit(company=company, rules=[REGLE])
        self.assertEqual(len(r4.new), 1)
        ligne.refresh_from_db()
        self.assertIsNone(ligne.resolved_at)
        self.assertEqual(ViolationCoherence.objects.count(), 1)

    def test_regle_non_executee_ne_resout_rien(self):
        company, user, client, produit = self.societe()
        self.devis(company, user, client, produit)
        moteur.run_audit(company=company, rules=[REGLE])
        moteur.run_audit(company=company, rules=['DOC_VALIDITE_AVANT_CREATION'])
        self.assertIsNone(
            ViolationCoherence.objects.get(company=company).resolved_at)


class TestCommandeJson(_Base):
    def _json(self, *args):
        out = io.StringIO()
        call_command('audit_coherence', *args, stdout=out)
        return json.loads(out.getvalue())

    def test_forme_golden_et_no_persist(self):
        company, user, client, produit = self.societe()
        d = self.devis(company, user, client, produit)
        data = self._json('--company', company.slug, '--json', '--no-persist',
                          '--rules', REGLE)
        self.assertEqual(set(data), CLES_JSON)
        self.assertEqual(data['companies'], [company.slug])
        self.assertEqual(data['checked'], {'devis': 1})
        self.assertEqual(len(data['violations']), 1)
        v = data['violations'][0]
        self.assertEqual(set(v), CLES_VIOLATION)
        self.assertEqual((v['rule'], v['object_id'], v['company']),
                         (REGLE, d.pk, company.slug))
        self.assertEqual(data['new'], data['violations'])
        self.assertEqual(data['rule_errors'], [])
        self.assertIsInstance(data['duration_s'], float)
        self.assertEqual(ViolationCoherence.objects.count(), 0)

    def test_persist_puis_new_vide(self):
        company, user, client, produit = self.societe()
        self.devis(company, user, client, produit)
        args = ('--company', company.slug, '--json', '--rules', REGLE)
        self.assertEqual(len(self._json(*args)['new']), 1)
        second = self._json(*args)
        self.assertEqual(len(second['violations']), 1)
        self.assertEqual(second['new'], [])


class TestIsolation(_Base):
    def test_objet_qui_plante_n_arrete_pas_la_passe(self):
        company, user, client, produit = self.societe()
        casse = self.devis(company, user, client, produit)
        sain = self.devis(company, user, client, produit)

        def plante(r, devis, ctx):
            if devis.pk == casse.pk:
                raise RuntimeError('boum')
            return []

        REGISTRE['TEST_PLANTE'] = Regle(
            id='TEST_PLANTE', libelle='test', gravite=GRAVITE_CRITIQUE,
            portee=PORTEE_DEVIS, check=plante, actif_par_defaut=False)

        def constructeur(devis, options):
            if devis.pk == casse.pk:
                raise ValueError('rendu impossible')
            return _donnees_propres(devis, options)
        try:
            rep = moteur.run_audit(
                company=company, persist=False, constructeur=constructeur,
                rules=['TEST_PLANTE', 'DOC_TOTAUX_IMPRIMES', REGLE])
        finally:
            REGISTRE.pop('TEST_PLANTE', None)
        erreurs = {(e['rule'], e['object_id']) for e in rep.rule_errors}
        self.assertIn(('TEST_PLANTE', casse.pk), erreurs)
        self.assertIn((moteur.REGLE_RENDU, casse.pk), erreurs)
        self.assertNotIn(('TEST_PLANTE', sain.pk), erreurs)
        # Les deux devis restent audités par la règle saine.
        self.assertEqual({v.object_id for v in rep.violations
                          if v.regle == REGLE}, {casse.pk, sain.pk})
        self.assertEqual(rep.checked['devis'], 2)

    def test_erreur_ne_resout_pas_la_violation_passee(self):
        company, user, client, produit = self.societe()
        d = self.devis(company, user, client, produit)
        moteur.run_audit(company=company, rules=[REGLE])

        def plante(r, devis, ctx):
            raise RuntimeError('boum')
        with mock.patch.dict(REGISTRE, {REGLE: Regle(
                id=REGLE, libelle='x', gravite=GRAVITE_CRITIQUE,
                portee=PORTEE_DEVIS, check=plante)}):
            rep = moteur.run_audit(company=company, rules=[REGLE])
        self.assertEqual(rep.resolved, 0)
        self.assertEqual(rep.rule_errors[0]['object_id'], d.pk)
        self.assertIsNone(
            ViolationCoherence.objects.get(company=company).resolved_at)

    def test_calcul_annule_rien_ne_survit(self):
        company, user, client, produit = self.societe()
        d = self.devis(company, user, client, produit,
                       date_acceptation=datetime.date(2026, 9, 10))

        def constructeur_qui_ecrit(devis, options):
            Devis.objects.filter(pk=devis.pk).update(note='ÉCRIT PAR LE RENDU')
            return _donnees_propres(devis, options)
        moteur.run_audit(company=company, constructeur=constructeur_qui_ecrit,
                         rules=['DOC_TOTAUX_IMPRIMES'])
        d.refresh_from_db()
        self.assertNotEqual(d.note, 'ÉCRIT PAR LE RENDU')

    def test_tenant_isolation(self):
        a = self.societe()
        b = self.societe()
        self.devis(*a)
        db = self.devis(*b)
        rep = moteur.run_audit(company=a[0], rules=[REGLE])
        self.assertEqual(rep.companies, [a[0].slug])
        self.assertEqual({v.company_id for v in rep.violations}, {a[0].pk})
        self.assertNotIn(db.pk, {v.object_id for v in rep.violations})
        self.assertFalse(
            ViolationCoherence.objects.filter(company=b[0]).exists())
        data = rep.as_json()
        self.assertEqual({v['company'] for v in data['violations']},
                         {a[0].slug})


class TestNotification(_Base):
    def test_digest_nouvelles_seulement(self):
        from apps.ventes.coherence.notification import (
            notifier_nouvelles_violations)
        from authentication.models import CustomUser
        company, user, client, produit = self.societe()
        d = self.devis(company, user, client, produit)
        admin = User.objects.create_user(
            username=f'cohadm_{_n()}', password='x', role_legacy='admin',
            company=company)
        rep = moteur.run_audit(company=company, rules=[REGLE])
        with mock.patch.object(
                CustomUser, 'admins_actifs_qs',
                staticmethod(lambda c: User.objects.filter(pk=admin.pk))), \
                mock.patch('apps.notifications.services.notify') as notify:
            self.assertEqual(notifier_nouvelles_violations(rep), 1)
        notify.assert_called_once()
        args, kwargs = notify.call_args
        self.assertEqual(args[0], admin)
        self.assertEqual(args[1], 'digest')
        self.assertIn(d.reference, kwargs['body'])
        self.assertIn(REGLE, kwargs['body'])
        self.assertEqual(kwargs['company'], company)

    def test_tache_sans_nouveaute_ne_notifie_pas(self):
        from apps.ventes.tasks import audit_coherence_nuit
        vide = moteur.AuditReport()
        with mock.patch('apps.ventes.coherence.moteur.run_audit',
                        return_value=vide), \
                mock.patch('apps.ventes.coherence.notification.'
                           'notifier_nouvelles_violations') as notif:
            resume = audit_coherence_nuit()
        notif.assert_not_called()
        self.assertEqual(resume['new'], 0)
        self.assertEqual(resume['notifications'], 0)
