"""L-VAR / PACT10 (ordre fondateur, 24/08/2026) — `variantes_servables`.

La page publique doit pouvoir proposer le sélecteur « quelle version du devis
télécharger ? » INDÉPENDAMMENT de ``nb_options``. Les deux clés ne disent pas
la même chose :

  * ``option_totals.nb_options`` — ce que CE document publie ;
  * ``variantes_servables``     — ce que les LIGNES du devis peuvent livrer.

Elles divergent légitimement sur le devis de production DEV-202608-0023, que la
resynchronisation 3D a rétréci à un scénario stocké mono (« Avec batterie »)
alors que ses lignes portent toujours réseau + hybride + batterie : il sert
``nb_options = 1`` ET ``variantes_servables = ['sans', 'avec']``. Sans cette
clé, la page ne pouvait plus offrir aucun choix au client.

Le contrat (forme figée, lue par les DEUX moitiés) vit dans
``apps/ventes/contract_samples/variantes_servables.json`` — ce module vérifie
que le serveur le respecte, sinon l'exemple pourrirait dans son coin.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_variantes_servables_contrat -v 2
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options

User = get_user_model()

ECHANTILLON = (Path(__file__).resolve().parents[1]
               / 'contract_samples' / 'variantes_servables.json')

PANNEAU = ('Panneau Canadian Solar 550W', '10', '1400')
ONDULEUR_RESEAU = ('Onduleur réseau Deye 8kW', '1', '14000')
ONDULEUR_HYBRIDE = ('Onduleur hybride Deye 8kW', '1', '16000')
BATTERIE = ('Batterie lithium Deye 5kWh', '1', '22000')


class _Base(TestCase):
    def _devis(self, slug, lignes, scenario=None):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        client_obj = Client.objects.create(
            company=company, nom=f'Client {slug}',
            email=f'{slug}@ex.com', telephone='+212600000011')
        devis = Devis.objects.create(
            company=company, reference=f'DEV-VS-{slug[-6:].upper()}',
            client=client_obj, statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), mode_installation='residentiel',
            etude_params=({'scenario': scenario} if scenario else {}))
        for designation, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=designation,
                sku=f'{uuid.uuid4().hex[:10]}', prix_vente=Decimal(pu),
                prix_achat=Decimal('1'), quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=designation,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        link = ShareLink.objects.create(
            company=company, devis=devis, token=str(uuid.uuid4()))
        return devis, link

    def _payload(self, link):
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()


class ChargeUtilePubliqueTests(_Base):
    def test_devis_a_deux_options_declarees(self):
        _devis, link = self._devis(
            f'vs-deux-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario='Les deux (Sans + Avec)')
        payload = self._payload(link)
        self.assertEqual(payload['variantes_servables'], ['sans', 'avec'])
        self.assertEqual(payload['option_totals']['nb_options'], 2)

    def test_devis_retreci_par_la_resync_reste_a_deux_variantes(self):
        """LE cas DEV-202608-0023 : une seule option publiée, deux variantes
        téléchargeables. C'est exactement la divergence que la clé existe pour
        rendre lisible par la page."""
        _devis, link = self._devis(
            f'vs-retreci-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario='Avec batterie')
        payload = self._payload(link)
        self.assertEqual(payload['option_totals']['nb_options'], 1)
        self.assertEqual(payload['variantes_servables'], ['sans', 'avec'])

    def test_devis_mono_avec_batterie(self):
        """Aucun onduleur réseau en lignes : l'option « sans » n'est pas
        livrable, la page ne doit donc pas la proposer."""
        _devis, link = self._devis(
            f'vs-monoavec-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario='Avec batterie')
        payload = self._payload(link)
        self.assertEqual(payload['variantes_servables'], ['avec'])

    def test_devis_mono_reseau(self):
        _devis, link = self._devis(
            f'vs-monoreseau-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU], scenario='Sans batterie')
        payload = self._payload(link)
        self.assertEqual(payload['variantes_servables'], ['sans'])

    def test_la_cle_est_toujours_presente_et_sans_aucun_montant(self):
        """RULE #4 — deux jetons de texte, jamais un chiffre."""
        for lignes, scenario in (
                ([PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
                 'Les deux (Sans + Avec)'),
                ([PANNEAU, ONDULEUR_RESEAU], None)):
            _devis, link = self._devis(
                f'vs-forme-{uuid.uuid4().hex[:6]}', lignes, scenario)
            payload = self._payload(link)
            self.assertIn('variantes_servables', payload)
            valeur = payload['variantes_servables']
            self.assertIsInstance(valeur, list)
            self.assertTrue(valeur)
            self.assertTrue(set(valeur) <= {'sans', 'avec'}, valeur)
            for jeton in valeur:
                self.assertIsInstance(jeton, str)


class ContratPartageTests(_Base):
    """PACT10 — l'exemple committé DOIT être la forme que le serveur sert."""

    def test_l_echantillon_de_contrat_decrit_bien_la_reponse(self):
        document = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.assertEqual(document['exemple']['variantes_servables'],
                         ['sans', 'avec'])

        _devis, link = self._devis(
            f'vs-contrat-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario='Les deux (Sans + Avec)')
        payload = self._payload(link)
        self.assertEqual(payload['variantes_servables'],
                         document['exemple']['variantes_servables'])
        # Les variantes d'ÉTAT du contrat sont, elles aussi, des états réels.
        self.assertEqual(
            document['exemple_mono_avec_batterie']['variantes_servables'],
            ['avec'])
        self.assertEqual(
            document['exemple_mono_reseau']['variantes_servables'], ['sans'])


class MoteurTests(_Base):
    """La clé vient du MOTEUR (``build_quote_data``) : aucune seconde règle de
    reconnaissance côté vue."""

    def test_l_artefact_pv86_ne_declare_qu_une_variante(self):
        """Deux onduleurs en lignes NON optionnelles et AUCUN scénario stocké :
        un ÉTAT DE DONNÉES, pas une alternative commerciale. Le repli PV86 l'a
        ramené à UNE présentation — la clé doit le refléter, sinon la page
        offrirait un choix que le moteur refuse ensuite d'honorer."""
        devis, _link = self._devis(
            f'vs-artefact-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario=None)
        data = build_quote_data(devis, clean_pdf_options({}))
        self.assertEqual(data['variantes_servables'], ['avec'])

    def test_la_variante_demandee_ne_change_pas_la_liste(self):
        """``variantes_servables`` décrit le DEVIS, jamais le rendu demandé :
        les trois variantes rendent la même liste."""
        devis, _link = self._devis(
            f'vs-stable-{uuid.uuid4().hex[:6]}',
            [PANNEAU, ONDULEUR_RESEAU, ONDULEUR_HYBRIDE, BATTERIE],
            scenario='Avec batterie')
        for valeur in (None, 'sans', 'avec', 'les_deux'):
            brut = {} if valeur is None else {'variante_option': valeur}
            data = build_quote_data(devis, clean_pdf_options(brut))
            self.assertEqual(data['variantes_servables'], ['sans', 'avec'],
                             valeur)
