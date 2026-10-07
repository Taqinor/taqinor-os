"""AANA13 (C-AANA-042, décision D-AANA-3) — en mode ``creer``, un doublon se
détecte par le MÊME rapprochement contact que le mode ``maj`` : e-mail OU
téléphone normalisé, pour les leads et pour les clients.

Rouge figé par l'audit (05/10) : lead existant (a@x.ma, 0612345678) ; import
``creer`` de ``B,b@x.ma,+212 612345678`` → ``created=1`` (``_doublon_lead``
ne regardait le téléphone que SANS e-mail, et seulement à l'identique) ; et
``created=1`` aussi avec le téléphone strictement identique."""
from apps.crm.models import Client, Lead

from .tests import ImportBase


class TestDoublonsContactLeads(ImportBase):
    def setUp(self):
        super().setUp()
        Lead.objects.create(company=self.company, nom='A', email='a@x.ma',
                            telephone='0612345678')

    def _commit(self, contenu, target='leads'):
        resp = self.api.post('/api/django/imports/commit/', {
            'file': self._csv(contenu), 'target': target,
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_meme_telephone_autre_email(self):
        avant = Lead.objects.filter(company=self.company).count()
        data = self._commit('Nom,Email,Telephone\nB,b@x.ma,+212 612345678\n')
        self.assertEqual(data['created'], 0, data)
        self.assertEqual(len(data['skipped']), 1, data)
        self.assertIn('doublon', data['skipped'][0]['raison'])
        self.assertEqual(
            Lead.objects.filter(company=self.company).count(), avant)

    def test_meme_telephone_identique_autre_email(self):
        data = self._commit('Nom,Email,Telephone\nB,b@x.ma,0612345678\n')
        self.assertEqual(data['created'], 0, data)

    def test_email_casse_differente(self):
        data = self._commit('Nom,Email\nB,A@X.MA\n')
        self.assertEqual(data['created'], 0, data)

    def test_apercu_annonce_l_ignorance(self):
        resp = self.api.post('/api/django/imports/dry-run/', {
            'file': self._csv('Nom,Email,Telephone\nB,b@x.ma,+212 612345678\n'),
            'target': 'leads',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['resume']['ignoree'], 1, resp.data)
        self.assertEqual(resp.data['resume']['creation'], 0, resp.data)

    def test_contact_nouveau_toujours_cree(self):
        data = self._commit('Nom,Email,Telephone\nC,c@x.ma,0699999999\n')
        self.assertEqual(data['created'], 1, data)


class TestDoublonsContactClients(ImportBase):
    def setUp(self):
        super().setUp()
        Client.objects.create(company=self.company, nom='A', email='a@x.ma',
                              telephone='0612345678')

    def test_meme_telephone_autre_email(self):
        resp = self.api.post('/api/django/imports/commit/', {
            'file': self._csv('Nom,Email,Telephone\nB,b@x.ma,+212 612345678\n'),
            'target': 'clients',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 0, resp.data)
        self.assertEqual(resp.data['skipped'][0]['raison'],
                         'doublon (téléphone existe)')
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_doublon_email_nomme_l_email(self):
        resp = self.api.post('/api/django/imports/commit/', {
            'file': self._csv('Nom,Email,Telephone\nB,a@x.ma,0700000000\n'),
            'target': 'clients',
        }, format='multipart')
        self.assertEqual(resp.data['created'], 0, resp.data)
        self.assertEqual(resp.data['skipped'][0]['raison'],
                         'doublon (email existe)')
