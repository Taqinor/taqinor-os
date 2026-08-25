"""L-2OPT — le tag d'option d'une ligne SURVIT à l'enregistrement du devis.

LE TROU QUE CECI FERME. La fonctionnalité « deux optimiseurs » (chaque option
Sans/Avec batterie porte SON dimensionnement, donc potentiellement un nombre de
panneaux différent) repose entièrement sur ``LigneDevis.variante``
('' commune | 'sans' | 'avec'). L'écran générateur fusionnait bien les deux
kits (``fusionnerVariantes``, solar.js) et envoyait le tag sur chaque ligne,
mais ``DevisViewSet._replace_lines_atomic`` — le SEUL chemin d'écriture de cet
écran, aussi bien à la création (``POST /devis/atomic/``) qu'à l'édition
(``POST /devis/<id>/replace-lines/``) — recréait chaque ligne SANS le kwarg
``variante``. Toutes les lignes retombaient au défaut ``''`` : le devis
rechargé n'avait plus aucune option, et tout l'aval (badges de l'écran,
comparatif du PDF, cartes par option de la page publique) lisait un devis
mono-option.

Les tests ci-dessous sont ROUGES sans le kwarg ``variante`` dans
``_replace_lines_atomic`` et verts avec.

Le dernier test verrouille l'invariant de non-régression : une charge utile
d'hier (aucune clé ``variante``) écrit toujours des lignes communes.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class L2optVariantePersistanceApiTests(TestCase):
    """Le tag ``variante`` traverse les deux chemins d'écriture du générateur."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='l2opt-var-co', defaults={'nom': 'L2OPT Variante Co'})
        self.user = User.objects.create_user(
            username='l2opt_var_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='L2OPT',
            telephone='+212600000771')
        # Un kit fusionné minimal : les panneaux divergent entre les deux
        # options (22 sans / 26 avec), l'onduleur est commun, la batterie
        # n'appartient qu'à l'option AVEC.
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='L2OPT-PV',
            prix_vente=Decimal('1000'), quantite_stock=500)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride', sku='L2OPT-OND',
            prix_vente=Decimal('12000'), quantite_stock=50)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie 16 kWh', sku='L2OPT-BAT',
            prix_vente=Decimal('40000'), quantite_stock=50)

    def _lignes_fusionnees(self):
        """La charge utile que l'écran envoie quand les deux optimums
        divergent (cf. ``lignesPayload`` de DevisGenerator.jsx)."""
        return [
            {'produit': self.panneau.id, 'designation': 'Panneau 550W',
             'quantite': '22', 'prix_unitaire': '1000', 'taux_tva': '10',
             'type_ligne': 'produit', 'ordre': 0, 'variante': 'sans'},
            {'produit': self.panneau.id, 'designation': 'Panneau 550W',
             'quantite': '26', 'prix_unitaire': '1000', 'taux_tva': '10',
             'type_ligne': 'produit', 'ordre': 1, 'variante': 'avec'},
            {'produit': self.onduleur.id, 'designation': 'Onduleur hybride',
             'quantite': '1', 'prix_unitaire': '12000', 'taux_tva': '20',
             'type_ligne': 'produit', 'ordre': 2, 'variante': ''},
            {'produit': self.batterie.id, 'designation': 'Batterie 16 kWh',
             'quantite': '1', 'prix_unitaire': '40000', 'taux_tva': '20',
             'type_ligne': 'produit', 'ordre': 3, 'variante': 'avec'},
        ]

    def _devis_brouillon(self, suffixe):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{suffixe}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur, designation='Ancienne',
            quantite=Decimal('1'), prix_unitaire=Decimal('12000'),
            remise=Decimal('0'))
        return devis

    # ── Création (POST /devis/atomic/) ──────────────────────────────────────
    def test_atomic_persiste_la_variante_de_chaque_ligne(self):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'mode_installation': 'residentiel',
            'lignes': self._lignes_fusionnees(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        devis = Devis.objects.get(id=resp.data['id'])
        par_ordre = {li.ordre: li for li in devis.lignes.all()}
        self.assertEqual(par_ordre[0].variante, 'sans')
        self.assertEqual(par_ordre[1].variante, 'avec')
        self.assertEqual(par_ordre[2].variante, '')
        self.assertEqual(par_ordre[3].variante, 'avec')

    def test_atomic_les_deux_options_gardent_des_nombres_de_panneaux_distincts(
            self):
        """Le CŒUR de la fonctionnalité : après enregistrement, l'option SANS
        et l'option AVEC comptent des panneaux DIFFÉRENTS (22 vs 26).

        Règle de lecture (``services`` : lignes ``''`` + celles de l'option)."""
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20', 'mode_installation': 'residentiel',
            'lignes': self._lignes_fusionnees(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        devis = Devis.objects.get(id=resp.data['id'])
        panneaux = [li for li in devis.lignes.all()
                    if li.produit_id == self.panneau.id]

        def total(option):
            return sum(int(li.quantite or 0) for li in panneaux
                       if (li.variante or '') in ('', option))

        self.assertEqual(total('sans'), 22)
        self.assertEqual(total('avec'), 26)
        self.assertNotEqual(
            total('sans'), total('avec'),
            'Les deux optimiseurs doivent rester distincts après '
            'enregistrement — sinon le devis est retombé mono-option.')

    # ── Édition (POST /devis/<id>/replace-lines/) ───────────────────────────
    def test_replace_lines_persiste_la_variante_de_chaque_ligne(self):
        devis = self._devis_brouillon('L2OPT01')
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': self._lignes_fusionnees()}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        par_ordre = {li.ordre: li for li in devis.lignes.all()}
        self.assertEqual(
            [par_ordre[i].variante for i in range(4)],
            ['sans', 'avec', '', 'avec'])

    def test_replace_lines_survit_a_un_aller_retour_de_lecture(self):
        """Le devis RELU par l'API porte bien les tags — c'est exactement ce
        que l'écran d'édition recharge (``d.lignes[].variante``)."""
        devis = self._devis_brouillon('L2OPT02')
        self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': self._lignes_fusionnees()}, format='json')
        relu = self.api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(relu.status_code, 200, relu.content)
        lignes = sorted(relu.data['lignes'], key=lambda li: li['ordre'])
        self.assertEqual([li['variante'] for li in lignes],
                         ['sans', 'avec', '', 'avec'])

    def test_reouvrir_puis_reenregistrer_ne_perd_pas_les_options(self):
        """LE PIRE SYMPTÔME : un devis DÉJÀ varianté (composé côté serveur par
        ``build_devis_auto``/``build_devis_from_layout``, qui eux persistent
        bien le tag) était SILENCIEUSEMENT ramené à mono-option dès qu'on le
        rouvrait dans le générateur et qu'on le ré-enregistrait."""
        devis = self._devis_brouillon('L2OPT05')
        devis.lignes.all().delete()
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 550W',
            quantite=Decimal('22'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0, variante='sans')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 550W',
            quantite=Decimal('26'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=1, variante='avec')
        # L'écran recharge, ne touche à rien, et ré-enregistre à l'identique.
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': self._lignes_fusionnees()}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            sorted(li.variante for li in devis.lignes.all()),
            ['', 'avec', 'avec', 'sans'])

    # ── Non-régression ──────────────────────────────────────────────────────
    def test_charge_utile_sans_cle_variante_reste_commune(self):
        """Un appelant d'hier (aucune clé ``variante``) écrit des lignes
        communes — comportement historique strictement inchangé."""
        devis = self._devis_brouillon('L2OPT03')
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': [
                {'produit': self.panneau.id, 'quantite': '10',
                 'prix_unitaire': '1000'},
                {'produit': self.onduleur.id, 'quantite': '1',
                 'prix_unitaire': '12000'},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            {li.variante for li in devis.lignes.all()}, {''})

    def test_variante_inconnue_retombe_sur_commune_sans_erreur(self):
        """Un tag mal formé ne casse JAMAIS l'enregistrement du devis : la
        ligne est simplement commune."""
        devis = self._devis_brouillon('L2OPT04')
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': [
                {'produit': self.panneau.id, 'quantite': '10',
                 'prix_unitaire': '1000', 'variante': 'peut-etre'},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(devis.lignes.get().variante, '')
