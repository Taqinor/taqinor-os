"""APDF20 (C-APDF-006) — à l'envoi, l'ENSEMBLE des textes contractuels du
devis (``DocumentTemplates.as_doc_texts`` fusionné au défaut du moteur : CGV,
titre, garanties, bon pour accord, validité…) et ``DocumentTemplates.version``
sont gelés dans UNE entrée ``doc_texts_geles`` de ``clauses_appliquees`` —
même quand la société n'a rien personnalisé (les défauts sont gelés).

Contrat figé ici (lu par APDF14, builder) :
``{'type': 'doc_texts_geles', 'textes': {<DEVIS_TEXT_KEYS>}, 'version': int}``.
L'entrée ``cgv_gelees`` existante est conservée (compatibilité).

Rejoue les sondes PCGV-2 / PCGV-2b : avant, seulement ``cgv_gelees`` (et rien
du tout pour une société sans puces). Test-du-test : retirer l'écriture de
``doc_texts_geles`` dans ``figer_clauses_devis`` ⇒
``test_gel_complet_avec_version`` échoue. Source réelle, aucun mock.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.parametres.models_documents import DEVIS_TEXT_KEYS, DocumentTemplates
from apps.ventes.domain.envoi import TYPE_DOC_TEXTS_GELES
from apps.ventes.models import Devis
from apps.ventes.quote_engine.generate_devis_premium import DEFAULT_DOC_TEXTS
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

PUCES_A = ['CGV-A acompte {acompte} % à la commande', 'CGV-A solde']


def _gel(devis):
    gels = [c for c in (devis.clauses_appliquees or [])
            if isinstance(c, dict) and c.get('type') == TYPE_DOC_TEXTS_GELES]
    return gels[0] if len(gels) == 1 else gels or None


class GelTextesEnvoiTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, statut=None):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 5kW', '1', '9000'),
        ], reference=f'DEV-{timezone.now():%Y%m}-20{self.n:02d}')
        if statut:
            Devis.objects.filter(pk=devis.pk).update(statut=statut)
            devis.refresh_from_db()
        return devis

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        return devis

    def test_gel_complet_avec_version(self):
        modeles = DocumentTemplates.get(company=self.company)
        modeles.cgv_titre = 'TITRE-A'
        modeles.bpa_mention = 'BPA-A'
        modeles.garantie_detail = 'GARANTIE-A'
        modeles.cgv_bullets = PUCES_A
        modeles.version = 7
        modeles.save()
        devis = self._envoyer(self._devis())
        gel = _gel(devis)
        self.assertIsInstance(gel, dict, devis.clauses_appliquees)
        self.assertEqual(set(gel), {'type', 'textes', 'version'})
        self.assertEqual(gel['version'], 7)
        self.assertEqual(set(gel['textes']), set(DEVIS_TEXT_KEYS))
        self.assertEqual(gel['textes']['cgv_titre'], 'TITRE-A')
        self.assertEqual(gel['textes']['bpa_mention'], 'BPA-A')
        self.assertEqual(gel['textes']['garantie_detail'], 'GARANTIE-A')
        self.assertEqual(gel['textes']['cgv_bullets'], PUCES_A)
        # Les clés non personnalisées portent le défaut du moteur.
        self.assertEqual(gel['textes']['bpa_titre'],
                         DEFAULT_DOC_TEXTS['bpa_titre'])
        # L'entrée historique ``cgv_gelees`` est conservée (compatibilité).
        self.assertTrue(any(
            isinstance(c, dict) and c.get('type') == 'cgv_gelees'
            for c in devis.clauses_appliquees))
        # CLAUSE PERSISTANCE — éditer les modèles ensuite ne change rien.
        modeles.cgv_titre = 'TITRE-B'
        modeles.version = 8
        modeles.save()
        devis.refresh_from_db()
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')
        self.assertEqual(_gel(devis)['version'], 7)

    def test_gel_defaut_sans_personnalisation(self):
        devis = self._envoyer(self._devis())
        gel = _gel(devis)
        self.assertIsInstance(gel, dict, devis.clauses_appliquees)
        attendus = {cle: DEFAULT_DOC_TEXTS.get(cle, '')
                    for cle in DEVIS_TEXT_KEYS}
        self.assertEqual(gel['textes'], attendus)
        self.assertEqual(
            gel['version'], DocumentTemplates.get(company=self.company).version)

    def test_correction_sur_place_regele(self):
        """Un envoyé d'avant ce gel (aucune entrée) reçoit le gel à sa
        correction sur place ; une seconde correction, après édition des
        modèles, ne le change pas."""
        modeles = DocumentTemplates.get(company=self.company)
        modeles.cgv_titre = 'TITRE-A'
        modeles.save()
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self.assertIsNone(_gel(devis))
        api = APIClient()
        api.force_authenticate(self.user)
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                      {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')
        modeles.cgv_titre = 'TITRE-B'
        modeles.save()
        r = api.patch(f'/api/django/ventes/devis/{devis.id}/',
                      {'remise_globale': '4'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(_gel(devis)['textes']['cgv_titre'], 'TITRE-A')
