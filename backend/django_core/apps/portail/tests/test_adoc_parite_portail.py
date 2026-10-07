"""ADOC148 — garde de classe « parité portail » (self-service CLIENT).

Constats C-ADOC-046 (compteur « Devis en attente » 2 pour 1 ligne, sonde #87),
C-ADOC-047 (chantier annulé : détail HTTP 500, sonde #88), C-ADOC-058
(document obsolète téléchargé 200, sonde #101) : une page portail servait un
objet que la liste cachait, ou un compteur ne matchait pas sa liste.

Invariants balayés, sur les ViewSets RÉELS du routeur portail :

* tout id ABSENT de la liste d'une surface ``mes-*`` répond 404 (jamais 500,
  jamais servi) sur ``retrieve`` et sur chaque action ``detail=True`` en GET ;
* les compteurs du tableau de bord égalent les longueurs des listes
  correspondantes.

La table des surfaces est CONSTRUITE depuis ``apps.portail.urls.router`` :
toute nouvelle surface ``mes-*`` gardée par ``IsPortalClientUser`` entre dans
le balayage sans édition de ce test. Les ids sondés sont TOUS les objets hors
périmètre créés ici (toutes surfaces confondues) + un id inexistant, moins
les ids de la liste de la surface. Seul MinIO est simulé.
Hors périmètre : surfaces fournisseur/partenaire (GATED ADOC149).

Run :
    python manage.py test apps.portail.tests.test_adoc_parite_portail -v2
"""
import datetime
import itertools
import re
from decimal import Decimal
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ged.models import (
    LIFECYCLE_OBSOLETE, AclGed, Cabinet, Document, DocumentVersion, Folder,
)
from apps.installations.models import Installation, Livraison
from apps.portail.models import DemandeTicketPortail
from apps.portail.services import provisionner_compte_portail_client
from apps.portail.urls import router
from apps.records.models import Attachment
from apps.roles.permissions import IsPortalClientUser
from apps.sav.models import ContratMaintenance
from apps.facturation.models import Facture
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)
RACINE = '/api/django/portail/'
TABLEAU = f'{RACINE}client/tableau-de-bord/'
ID_INEXISTANT = 10 ** 8
#: Surfaces connues à la création du test : chacune DOIT porter au moins une
#: ligne visible (sanité des fixtures). Une surface nouvelle est balayée
#: quand même (invariant 404), sans exigence de ligne.
SURFACES_CONNUES = {
    'mes-devis', 'mes-factures', 'mes-livraisons', 'mes-chantiers',
    'mes-documents', 'mes-demandes-sav', 'mes-contrats-maintenance',
}


def surfaces_client():
    """(préfixe, viewset) de chaque surface ``mes-*`` self-service CLIENT du
    routeur portail."""
    out = []
    for prefix, viewset, _basename in router.registry:
        if not prefix.startswith('mes-'):
            continue
        if IsPortalClientUser not in tuple(
                getattr(viewset, 'permission_classes', ()) or ()):
            continue
        out.append((prefix, viewset))
    return out


def routes_detail_get(viewset, pk, autre_id):
    """URLs relatives (après ``<prefix>/``) de ``retrieve`` et de chaque
    action ``detail=True`` acceptant GET, pour l'id ``pk``."""
    routes = []
    if hasattr(viewset, 'retrieve'):
        routes.append(f'{pk}/')
    for act in viewset.get_extra_actions():
        if not act.detail or 'get' not in act.mapping:
            continue
        chemin = re.sub(r'\(\?P<\w+>[^)]*\)', str(autre_id), act.url_path)
        routes.append(f'{pk}/{chemin}/')
    return routes


class PariteePortailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc148-{n}', defaults={'nom': f'ADOC148 {n}'})
        self.client_a = Client.objects.create(
            company=self.co, nom='Alpha', prenom=f'ADOC148-A-{n}',
            email=f'adoc148-a-{n}@example.invalid')
        self.client_b = Client.objects.create(
            company=self.co, nom='Beta', prenom=f'ADOC148-B-{n}',
            email=f'adoc148-b-{n}@example.invalid')
        user, _ = provisionner_compte_portail_client(
            self.co, self.client_a.id)
        user.must_change_password = False
        user.save(update_fields=['must_change_password'])
        self.api = APIClient()
        self.api.force_authenticate(user=user)
        self.hors_perimetre = []
        self._fixtures(n)

    def _cacher(self, *objets):
        self.hors_perimetre.extend(o.pk for o in objets)

    def _fixtures(self, n):
        a, b, co = self.client_a, self.client_b, self.co
        # Devis : visible (envoyé) ; V1 remplacée, brouillon, autre client.
        Devis.objects.create(
            company=co, reference=f'DEV-148-A-{n}', client=a,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'))
        self._cacher(
            Devis.objects.create(
                company=co, reference=f'DEV-148-V1-{n}', client=a,
                statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
                is_active=False),
            Devis.objects.create(
                company=co, reference=f'DEV-148-BR-{n}', client=a,
                statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20')),
            Devis.objects.create(
                company=co, reference=f'DEV-148-B-{n}', client=b,
                statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20')))
        # Factures : visible (émise) ; brouillon, autre client.

        def facture(ref, client, statut):
            return Facture.objects.create(
                company=co, reference=ref, client=client, statut=statut,
                montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                montant_ttc=Decimal('1200'), taux_tva=Decimal('20'))
        facture(f'FAC-148-A-{n}', a, Facture.Statut.EMISE)
        self._cacher(
            facture(f'FAC-148-BR-{n}', a, Facture.Statut.BROUILLON),
            facture(f'FAC-148-B-{n}', b, Facture.Statut.EMISE))
        # Chantiers : visible ; annulé, autre client.
        chantier_a = Installation.objects.create(
            company=co, reference=f'CH-148-A-{n}', client=a)
        chantier_annule = Installation.objects.create(
            company=co, reference=f'CH-148-X-{n}', client=a, annule=True)
        chantier_b = Installation.objects.create(
            company=co, reference=f'CH-148-B-{n}', client=b)
        self._cacher(chantier_annule, chantier_b)
        ct = ContentType.objects.get_for_model(Installation)
        self.photo_cachee = Attachment.objects.create(
            company=co, content_type=ct, object_id=chantier_annule.id,
            file_key=f'attachments/adoc148-{n}.jpg', filename='p.jpg',
            size=10, mime='image/jpeg', phase='avant')
        self._cacher(self.photo_cachee)
        # Livraisons : visible (son chantier) ; autre client.
        Livraison.objects.create(
            company=co, installation=chantier_a, reference=f'LIV-148-A-{n}')
        self._cacher(Livraison.objects.create(
            company=co, installation=chantier_b,
            reference=f'LIV-148-B-{n}'))
        # Documents GED partagés : visible ; obsolète, autre client.
        cabinet = Cabinet.objects.create(company=co, nom=f'Cab-148-{n}')
        folder = Folder.objects.create(
            company=co, cabinet=cabinet, nom=f'Dossier-148-{n}')

        def document(nom, client, **extra):
            doc = Document.objects.create(
                company=co, folder=folder, nom=nom, **extra)
            AclGed.objects.create(company=co, document=doc, client=client)
            DocumentVersion.objects.create(
                company=co, document=doc, version=1,
                file_key=f'ged/{co.id}/{doc.id}-v1.pdf', filename='v1.pdf',
                size=100, mime='application/pdf')
            return doc
        document('Visible', a)
        self._cacher(
            document('Obsolète', a, statut=LIFECYCLE_OBSOLETE),
            document('Voisin', b))
        # Demandes SAV : visible ; autre client.
        DemandeTicketPortail.objects.create(
            company=co, client_id=a.id, sujet='À moi')
        self._cacher(DemandeTicketPortail.objects.create(
            company=co, client_id=b.id, sujet='Au voisin'))
        # Contrats de maintenance : visible ; autre client.

        def contrat(client):
            return ContratMaintenance.objects.create(
                company=co, client=client,
                periodicite=ContratMaintenance.Periodicite.ANNUEL,
                date_debut=datetime.date(2026, 1, 1), actif=True,
                visites_incluses_an=2, deplacements_inclus_an=1,
                pieces_couvertes_pct=50)
        contrat(a)
        self._cacher(contrat(b))

    def _liste(self, prefix):
        res = self.api.get(f'{RACINE}{prefix}/')
        self.assertEqual(res.status_code, 200,
                         f'{prefix} liste : {res.status_code}')
        return res.json()['results']

    def test_table_des_surfaces_construite_depuis_le_routeur(self):
        prefixes = {p for p, _v in surfaces_client()}
        self.assertTrue(SURFACES_CONNUES <= prefixes,
                        SURFACES_CONNUES - prefixes)

    @patch('apps.records.storage.fetch_attachment',
           return_value=(b'\xff\xd8\xff contenu', None))
    def test_absent_de_la_liste_404_partout(self, _minio):
        echecs = []
        for prefix, viewset in surfaces_client():
            lignes = self._liste(prefix)
            if prefix in SURFACES_CONNUES:
                self.assertTrue(lignes, f'{prefix} : aucune ligne visible')
            visibles = {ligne['id'] for ligne in lignes}
            sondes = (set(self.hors_perimetre) | {ID_INEXISTANT}) - visibles
            for pk in sorted(sondes):
                for route in routes_detail_get(
                        viewset, pk, self.photo_cachee.pk):
                    url = f'{RACINE}{prefix}/{route}'
                    code = self.api.get(url).status_code
                    if code != 404:
                        echecs.append(f'{url} -> {code}')
        self.assertEqual(echecs, [], 'servi ou 500 hors liste')

    def test_compteurs_du_tableau_de_bord_egalent_les_listes(self):
        tableau = self.api.get(TABLEAU)
        self.assertEqual(tableau.status_code, 200, tableau.content)
        cartes = tableau.json()
        devis = self._liste('mes-devis')
        factures = self._liste('mes-factures')
        self.assertEqual(
            cartes['devis_en_attente'],
            len([d for d in devis if d['statut'] == 'envoye']))
        self.assertEqual(
            cartes['factures_impayees'],
            len([f for f in factures
                 if f['statut'] in ('emise', 'en_retard')]))
        self.assertEqual(cartes['devis_en_attente'], 1)
        self.assertEqual(cartes['factures_impayees'], 1)

    def test_tableau_de_bord_ignore_un_chantier_hors_liste(self):
        visibles = {c['id'] for c in self._liste('mes-chantiers')}
        for pk in self.hors_perimetre:
            if pk in visibles:
                continue
            res = self.api.get(TABLEAU, {'chantier': pk})
            self.assertEqual(res.status_code, 200, res.content)
            self.assertIsNone(res.json()['prochain_jalon'])
