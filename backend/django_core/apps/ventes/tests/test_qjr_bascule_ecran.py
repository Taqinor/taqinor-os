# -*- coding: utf-8 -*-
"""QJR93 (M5, bascule 1/5) — L'ÉCRAN passe par ``pipeline.appliquer()``.

CE QUE CE FICHIER EST, ET POURQUOI IL EST ÉCRIT COMME ÇA.

La discipline de bascule (R4-C.7) exige un test GOLDEN qui capture la sortie de
l'ANCIEN chemin, puis la bascule, puis la preuve d'égalité — et la SUPPRESSION
de l'ancien corps dans le MÊME commit. L'ancien corps DISPARAISSANT, le golden
ne peut pas l'APPELER pour se comparer à lui : il porte donc des ATTENTES
DÉRIVÉES, écrites en dur, chacune accompagnée de sa dérivation depuis la
fixture. C'est plus long à lire qu'un ``assertEqual(nouveau, ancien)`` et c'est
volontaire : une attente dérivée à la main survit à la suppression du code
qu'elle décrit, et elle DIT pourquoi le nombre est ce qu'il est.

CE QUI A BASCULÉ. ``atomic`` (création) et ``replace-lines`` (édition)
recopiaient la MÊME paire de gestes : écrire les lignes sous transaction, puis
rafraîchir les quatre études hors transaction. Les deux passent désormais par
``domain/pipeline.appliquer`` — mode ``ecrire`` pour la première moitié, mode
``rafraichir`` pour la seconde. Les frontières de transaction n'ont pas bougé.

CE QUI N'A PAS BASCULÉ, ET C'EST LE POINT LE PLUS IMPORTANT. L'écran ne passe
PAS par l'étape ``composer`` : sa composition lui est FOURNIE par le
commercial, qui a pu taper des prix (``prix_manuel``), forcer des quantités
(``quantite_manuelle``), ajouter des sections et découper ses deux options.
Recomposer depuis le catalogue effacerait ce travail. Il ne passe pas non plus
par l'étape 6 (``ecrire_etude_params``) ni par l'étape 8 (``finaliser``) : ni
l'une ni l'autre ne tournait sur ce chemin, et les faire tourner « puisqu'on y
est » serait un changement de comportement déguisé en refactoring. Les tests
``test_*_n_invente_pas`` ci-dessous verrouillent précisément cette absence.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_bascule_ecran -v 2
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
from apps.ventes.domain.argent import Vue, totaux
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
MOIS = timezone.now().strftime('%Y%m')

ATOMIC = '/api/django/ventes/devis/atomic/'


def _remplacer(devis_id):
    return '/api/django/ventes/devis/%s/replace-lines/' % devis_id


class _BaseEcran(TestCase):
    """La fixture commune aux trois goldens.

    TROIS CHOIX DE FIXTURE, TOUS DÉLIBÉRÉS :

    * des prix RONDS (1 000 / 2 000 / 5 000 MAD) et un taux unique à 20 % :
      la chaîne HT → remise → TVA → TTC se dérive alors à la main sans aucune
      ambiguïté d'arrondi, et une attente écrite en dur reste vérifiable par un
      humain ;
    * des désignations NEUTRES (« Kit commun », « Poste … ») : aucune ne
      contient « panneau », « onduleur réseau », « batterie » ou un wattage, si
      bien qu'aucun classifieur par mots-clés ne les range d'un côté ou de
      l'autre. Le seul découpage en options est celui que la colonne
      ``variante`` DÉCLARE — ce qui rend le panier de chaque option
      déterministe ;
    * un CLIENT et non un lead, et aucune facture : les quatre études n'ont
      alors rien à calculer et n'écrivent rien. ``etude_params`` reste donc
      exactement ce que l'écran a envoyé, ce qui est précisément la propriété
      que les goldens vérifient.
    """

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr93-co', defaults={'nom': 'QJR93 Co'})
        self.user = User.objects.create_user(
            username='qjr93_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR93',
            telephone='+212600000093')
        self.commun = Produit.objects.create(
            company=self.company, nom='Kit commun QJR93', sku='QJR93-COM',
            prix_vente=Decimal('1000'), quantite_stock=100)
        self.poste_a = Produit.objects.create(
            company=self.company, nom='Poste A QJR93', sku='QJR93-A',
            prix_vente=Decimal('2000'), quantite_stock=100)
        self.poste_b = Produit.objects.create(
            company=self.company, nom='Poste B QJR93', sku='QJR93-B',
            prix_vente=Decimal('5000'), quantite_stock=100)

    # ── outillage de lecture, pour que les assertions restent lisibles ──────
    def _lignes(self, devis):
        """Les lignes persistées, réduites à ce qu'un golden doit épingler."""
        return [
            {
                'produit': li.produit_id,
                'designation': li.designation,
                'quantite': Decimal(str(li.quantite)),
                'prix_unitaire': Decimal(str(li.prix_unitaire)),
                'remise': Decimal(str(li.remise)),
                'ordre': li.ordre,
                'variante': li.variante,
                'optionnelle': li.optionnelle,
                'type_ligne': li.type_ligne,
                'quantite_manuelle': li.quantite_manuelle,
                'prix_manuel': li.prix_manuel,
            }
            for li in devis.lignes.order_by('ordre', 'id')
        ]

    def _brut(self, devis):
        vue = totaux(devis, vue=Vue.BRUT)
        return (vue.ht_brut, vue.tva, vue.ttc)

    def _par_option(self, devis, option):
        vue = totaux(devis, vue=Vue.PAR_OPTION, option=option)
        return (vue.ht_brut, vue.remise, vue.ht_net, vue.tva, vue.ttc)


class GoldenMonoOption(_BaseEcran):
    """FIXTURE 1 — le devis MONO-OPTION créé par ``atomic``.

    Composition envoyée par l'écran :

        ordre 0 — Kit commun QJR93 ×10 à 1 000,00  → 10 000,00 HT
        ordre 1 — Poste A QJR93    × 1 à 2 000,00  →  2 000,00 HT

    DÉRIVATION DES TOTAUX (taux unique 20 %, aucune remise) :

        ht_brut = 10 000,00 + 2 000,00      = 12 000,00
        remise  = 0 %                        =      0,00
        ht_net  = 12 000,00 − 0,00           = 12 000,00
        tva     = 12 000,00 × 20 / 100       =  2 400,00
        ttc     = 12 000,00 + 2 400,00       = 14 400,00
    """

    def _creer(self):
        return self.api.post(ATOMIC, {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20',
            'lignes': [
                {'produit': self.commun.id, 'quantite': '10',
                 'prix_unitaire': '1000',
                 'designation': 'Kit commun QJR93'},
                {'produit': self.poste_a.id, 'quantite': '1',
                 'prix_unitaire': '2000',
                 'designation': 'Poste A QJR93'},
            ],
        }, format='json')

    def test_golden_lignes_et_totaux(self):
        reponse = self._creer()
        self.assertEqual(reponse.status_code, 201, reponse.content)
        devis = Devis.objects.get(id=reponse.data['id'])

        self.assertEqual(self._lignes(devis), [
            {'produit': self.commun.id, 'designation': 'Kit commun QJR93',
             'quantite': Decimal('10'), 'prix_unitaire': Decimal('1000'),
             'remise': Decimal('0'), 'ordre': 0, 'variante': '',
             'optionnelle': False, 'type_ligne': 'produit',
             'quantite_manuelle': False, 'prix_manuel': False},
            {'produit': self.poste_a.id, 'designation': 'Poste A QJR93',
             'quantite': Decimal('1'), 'prix_unitaire': Decimal('2000'),
             'remise': Decimal('0'), 'ordre': 1, 'variante': '',
             'optionnelle': False, 'type_ligne': 'produit',
             'quantite_manuelle': False, 'prix_manuel': False},
        ])
        # Les trois étages dérivés dans la docstring de la classe.
        self.assertEqual(devis.total_ht, Decimal('12000.00'))
        self.assertEqual(devis.total_tva, Decimal('2400.00'))
        self.assertEqual(devis.total_ttc, Decimal('14400.00'))
        self.assertEqual(self._brut(devis),
                         (Decimal('12000'), Decimal('2400'),
                          Decimal('14400')))

    def test_la_reponse_porte_les_memes_lignes_et_le_meme_argent(self):
        """« Endpoints inchangés à l'octet » — la réponse, pas seulement la
        base."""
        reponse = self._creer()
        self.assertEqual(reponse.status_code, 201, reponse.content)
        self.assertEqual(len(reponse.data['lignes']), 2)
        self.assertEqual(
            [li['designation'] for li in reponse.data['lignes']],
            ['Kit commun QJR93', 'Poste A QJR93'])
        self.assertEqual(Decimal(str(reponse.data['total_ht'])),
                         Decimal('12000.00'))
        self.assertEqual(Decimal(str(reponse.data['total_ttc'])),
                         Decimal('14400.00'))

    def test_atomic_n_invente_pas_d_etude(self):
        """Le mode ``ecrire`` s'arrête à l'étape 5, et le mode ``rafraichir``
        à l'étape 7.

        Les étapes 6 (``ecrire_etude_params``) et 8 (``finaliser``) ne
        tournaient PAS sur ce chemin. Si la bascule les avait embarquées « puisqu'on
        y est », ce devis porterait un ``scenario`` que personne n'a déclaré et
        un ``puissance_kwc`` dérivé de lignes qui ne sont pas des panneaux —
        deux nombres publiés que rien ne soutient (règle fondateur « zéro
        chiffre inventé »)."""
        reponse = self._creer()
        devis = Devis.objects.get(id=reponse.data['id'])
        etude = devis.etude_params or {}
        self.assertNotIn('puissance_kwc', etude)
        self.assertNotIn('scenario', etude)

    def test_un_produit_d_une_autre_societe_annule_tout(self):
        """La transaction est restée AUTOUR de l'écriture des lignes : un
        rollback ne doit laisser NI devis NI ligne."""
        autre = Company.objects.create(slug='qjr93-autre', nom='Autre')
        etranger = Produit.objects.create(
            company=autre, nom='Étranger', sku='QJR93-ETR',
            prix_vente=Decimal('1'), quantite_stock=1)
        reponse = self.api.post(ATOMIC, {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20',
            'lignes': [{'produit': etranger.id, 'quantite': '1',
                        'prix_unitaire': '1'}],
        }, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), 0)
        self.assertEqual(LigneDevis.objects.count(), 0)


class GoldenDeuxOptionsDivergentes(_BaseEcran):
    """FIXTURE 2 — les DEUX options, et elles divergent.

    Composition envoyée par l'écran (une ligne COMMUNE, une par option) :

        ordre 0 — Kit commun QJR93 ×1 à 1 000,00  variante ''      → 1 000,00
        ordre 1 — Poste A QJR93    ×1 à 2 000,00  variante 'sans'  → 2 000,00
        ordre 2 — Poste B QJR93    ×1 à 5 000,00  variante 'avec'  → 5 000,00

    DÉRIVATION. La colonne ``variante`` est EXCLUSIVE (L-2OPT / F14) : une
    ligne déclarée ne part jamais dans le panier de l'autre option, et une ligne
    sans déclaration reste commune aux deux. D'où :

        panier « sans »  = commun + Poste A = 1 000 + 2 000 =  3 000,00 HT
                           tva = 3 000 × 20 / 100           =    600,00
                           ttc                              =  3 600,00
        panier « avec »  = commun + Poste B = 1 000 + 5 000 =  6 000,00 HT
                           tva = 6 000 × 20 / 100           =  1 200,00
                           ttc                              =  7 200,00
        vue BRUT (aucun filtre d'option)    = 1+2+5 mille   =  8 000,00 HT

    Et ``Devis.total_*`` suit l'option EFFECTIVE (D9 : avant acceptation,
    l'option AVEC), donc le panier « avec » — JAMAIS la somme des deux, qui
    serait un montant que le client ne paiera jamais.
    """

    def _creer(self):
        return self.api.post(ATOMIC, {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20',
            'lignes': [
                {'produit': self.commun.id, 'quantite': '1',
                 'prix_unitaire': '1000', 'designation': 'Kit commun QJR93'},
                {'produit': self.poste_a.id, 'quantite': '1',
                 'prix_unitaire': '2000', 'designation': 'Poste A QJR93',
                 'variante': 'sans'},
                {'produit': self.poste_b.id, 'quantite': '1',
                 'prix_unitaire': '5000', 'designation': 'Poste B QJR93',
                 'variante': 'avec'},
            ],
        }, format='json')

    def test_golden_la_variante_survit_a_l_enregistrement(self):
        """SANS elle, les deux options redeviendraient une seule (L-2OPT)."""
        reponse = self._creer()
        self.assertEqual(reponse.status_code, 201, reponse.content)
        devis = Devis.objects.get(id=reponse.data['id'])
        self.assertEqual(
            [(li['ordre'], li['variante'], li['prix_unitaire'])
             for li in self._lignes(devis)],
            [(0, '', Decimal('1000')),
             (1, 'sans', Decimal('2000')),
             (2, 'avec', Decimal('5000'))])

    def test_golden_l_argent_de_chaque_option(self):
        reponse = self._creer()
        devis = Devis.objects.get(id=reponse.data['id'])

        self.assertEqual(self._brut(devis),
                         (Decimal('8000'), Decimal('1600'), Decimal('9600')))
        self.assertEqual(
            self._par_option(devis, 'sans_batterie'),
            (Decimal('3000'), Decimal('0'), Decimal('3000'),
             Decimal('600'), Decimal('3600')))
        self.assertEqual(
            self._par_option(devis, 'avec_batterie'),
            (Decimal('6000'), Decimal('0'), Decimal('6000'),
             Decimal('1200'), Decimal('7200')))
        # D9 — l'argent du document suit l'option AVEC, jamais la somme.
        self.assertEqual(devis.total_ht, Decimal('6000.00'))
        self.assertEqual(devis.total_ttc, Decimal('7200.00'))


class GoldenDevisRemise(_BaseEcran):
    """FIXTURE 3 — le devis REMISÉ, réécrit par ``replace-lines``.

    Composition envoyée par l'écran (remise globale 10 % sur le devis, et une
    remise de LIGNE de 25 % sur le second poste) :

        ordre 0 — Kit commun QJR93 ×10 à 1 000,00 remise  0 % → 10 000,00
        ordre 1 — Poste A QJR93    × 1 à 2 000,00 remise 25 % →  1 500,00

    DÉRIVATION (la remise de ligne entre dans le HT BRUT, la remise globale
    s'applique ensuite — ``_canonical_totaux``, arrondi au centime à chaque
    étage) :

        ht_brut = 10 000,00 + (2 000,00 × 0,75)  = 11 500,00
        remise  = 11 500,00 × 10 / 100           =  1 150,00
        ht_net  = 11 500,00 − 1 150,00           = 10 350,00
        tva     = 10 350,00 × 20 / 100           =  2 070,00
        ttc     = 10 350,00 + 2 070,00           = 12 420,00
    """

    def _devis_existant(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-QJR9301',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'),
            created_by=self.user,
            # L'étude que l'ÉCRAN a déclarée. Le mode ``ecrire`` n'en est pas
            # propriétaire : il ne doit ni la relire ni la réécrire.
            etude_params={'scenario': 'Sans batterie'})
        LigneDevis.objects.create(
            devis=devis, produit=self.commun, designation='Ancienne ligne',
            quantite=Decimal('1'), prix_unitaire=Decimal('999'),
            remise=Decimal('0'))
        return devis

    def test_golden_lignes_et_totaux(self):
        devis = self._devis_existant()
        reponse = self.api.post(_remplacer(devis.id), {
            'lignes': [
                {'produit': self.commun.id, 'quantite': '10',
                 'prix_unitaire': '1000', 'designation': 'Kit commun QJR93'},
                {'produit': self.poste_a.id, 'quantite': '1',
                 'prix_unitaire': '2000', 'remise': '25',
                 'designation': 'Poste A QJR93'},
            ],
        }, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        devis.refresh_from_db()

        self.assertEqual(self._lignes(devis), [
            {'produit': self.commun.id, 'designation': 'Kit commun QJR93',
             'quantite': Decimal('10'), 'prix_unitaire': Decimal('1000'),
             'remise': Decimal('0'), 'ordre': 0, 'variante': '',
             'optionnelle': False, 'type_ligne': 'produit',
             'quantite_manuelle': False, 'prix_manuel': False},
            {'produit': self.poste_a.id, 'designation': 'Poste A QJR93',
             'quantite': Decimal('1'), 'prix_unitaire': Decimal('2000'),
             'remise': Decimal('25'), 'ordre': 1, 'variante': '',
             'optionnelle': False, 'type_ligne': 'produit',
             'quantite_manuelle': False, 'prix_manuel': False},
        ])
        self.assertEqual(devis.total_ht, Decimal('10350.00'))
        self.assertEqual(devis.total_tva, Decimal('2070.00'))
        self.assertEqual(devis.total_ttc, Decimal('12420.00'))
        # La réponse porte le MÊME argent que la base (inchangée à l'octet).
        self.assertEqual(Decimal(str(reponse.data['total_ttc'])),
                         Decimal('12420.00'))

    def test_la_saisie_manuelle_du_commercial_fait_l_aller_retour(self):
        """D12 / QJR59 — le prix tapé et la quantité forcée sont SOUVERAINS.

        C'est la propriété qui interdisait de faire passer l'écran par l'étape
        ``composer`` : une recomposition depuis le catalogue effacerait ces deux
        marqueurs, et le prix négocié redeviendrait réécrivable au premier
        rafraîchissement."""
        devis = self._devis_existant()
        reponse = self.api.post(_remplacer(devis.id), {
            'lignes': [
                {'produit': self.commun.id, 'quantite': '7',
                 'prix_unitaire': '888', 'designation': 'Prix négocié QJR93',
                 'quantite_manuelle': True, 'prix_manuel': True},
            ],
        }, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        ligne = devis.lignes.get()
        self.assertEqual(ligne.designation, 'Prix négocié QJR93')
        self.assertEqual(Decimal(str(ligne.quantite)), Decimal('7'))
        self.assertEqual(Decimal(str(ligne.prix_unitaire)), Decimal('888'))
        self.assertTrue(ligne.quantite_manuelle)
        self.assertTrue(ligne.prix_manuel)

    def test_replace_lines_ne_touche_pas_l_etude_de_l_ecran(self):
        """Ni l'étape 6 ni l'étape 8 ne tournent : le ``scenario`` déclaré
        survit, et aucun ``puissance_kwc`` n'apparaît."""
        devis = self._devis_existant()
        self.api.post(_remplacer(devis.id), {
            'lignes': [{'produit': self.commun.id, 'quantite': '1',
                        'prix_unitaire': '1000'}],
        }, format='json')
        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertEqual(etude.get('scenario'), 'Sans batterie')
        self.assertNotIn('puissance_kwc', etude)

    def test_un_produit_inconnu_preserve_les_lignes_d_origine(self):
        """La transaction n'a pas bougé : un échec rend le devis intact."""
        devis = self._devis_existant()
        reponse = self.api.post(_remplacer(devis.id), {
            'lignes': [{'produit': 999999, 'quantite': '1',
                        'prix_unitaire': '1'}],
        }, format='json')
        self.assertEqual(reponse.status_code, 400)
        devis.refresh_from_db()
        self.assertEqual(devis.lignes.count(), 1)
        self.assertEqual(devis.lignes.get().designation, 'Ancienne ligne')

    def test_un_devis_fige_refuse_toujours_le_remplacement(self):
        """PV15 — la garde de statut vit AVANT le pipeline et n'a pas bougé."""
        devis = self._devis_existant()
        devis.statut = Devis.Statut.ACCEPTE
        devis.save(update_fields=['statut'])
        reponse = self.api.post(_remplacer(devis.id), {
            'lignes': [{'produit': self.commun.id, 'quantite': '1',
                        'prix_unitaire': '1000'}],
        }, format='json')
        self.assertEqual(reponse.status_code, 409)
        self.assertEqual(devis.lignes.get().designation, 'Ancienne ligne')


class BasculePerformUpdate(_BaseEcran):
    """QJR94 (M5, bascule 2/5) — un PATCH rafraîchit LES QUATRE études.

    LE TROU QUE CECI BOUCHE, et pourquoi il coûte cher. ``perform_update``
    n'appelait que DEUX des quatre rafraîchisseurs (le bloc horaire et le
    tableau de dimensionnement). Les deux autres — les profils comparatifs et
    la CONCEPTION ÉLECTRIQUE — se périmaient donc à chaque PATCH touchant
    ``etude_params``. La conception électrique est la seule des quatre à
    n'être jamais recalculée à la lecture : elle PERSISTE ce qu'on lui a
    écrit. Le client voyait donc, sur sa page proposition, un schéma unifilaire
    décrivant une composition que le devis ne vend plus.

    CHANGEMENT DE COMPORTEMENT ASSUMÉ (R4-C.5), et c'en est bien un : deux
    études de plus tournent après chaque PATCH. ``force=True``, lui, est
    CONSERVÉ — la raison qui l'imposait aux deux premières (un PATCH change des
    grandeurs qu'aucune lecture de lignes ne voit) vaut à l'identique pour les
    deux autres.

    POURQUOI UN TEST À ESPIONS ET NON UN TEST DE CONTENU. Ce qui a changé est
    QUELLES études repartent, pas ce qu'elles calculent — et chacune des quatre
    a déjà ses propres tests de contenu. Épingler ici les quatre APPELS (et leur
    ``force``) dit exactement ce que la bascule a changé, sans dépendre d'une
    fixture résidentielle complète dont la moindre dérive rendrait ce test
    illisible pour la mauvaise raison.
    """

    def _espionner_les_quatre(self):
        """Remplace les quatre rafraîchisseurs par des espions ; rend leur
        journal ``[(nom, force), …]`` dans l'ordre d'appel."""
        from apps.ventes import electrical_service, profils_comparatifs
        from apps.ventes.domain import etudes

        journal = []
        cibles = [
            (etudes, 'rafraichir_etude_horaire_devis'),
            (etudes, 'rafraichir_dimensionnement_devis'),
            (profils_comparatifs, 'rafraichir_profils_comparatifs_devis'),
            (electrical_service, 'rafraichir_conception_electrique_devis'),
        ]
        anciens = [(mod, nom, getattr(mod, nom)) for mod, nom in cibles]

        def _restaurer():
            for mod, nom, valeur in anciens:
                setattr(mod, nom, valeur)

        def _espion(nom):
            def _appel(devis, force=False, **_):
                journal.append((nom, force))
                return None
            return _appel

        for mod, nom in cibles:
            setattr(mod, nom, _espion(nom))
        self.addCleanup(_restaurer)
        return journal

    def test_un_patch_rafraichit_les_quatre_etudes(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-QJR9402',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)
        journal = self._espionner_les_quatre()

        # Passe Fable M5a — ``etude_params`` est READ-ONLY depuis QJR67 : le
        # PATCHer décrirait une écriture devenue impossible. Le dispatch des
        # quatre études est inconditionnel sur tout PATCH accepté ; on exerce
        # donc un champ ENCORE écrivable.
        reponse = self.api.patch(
            '/api/django/ventes/devis/%s/' % devis.id,
            {'note': 'QJR94 — un PATCH quelconque rafraîchit les 4 études'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)

        # LES QUATRE, dans l'ordre de ``rafraichir_etudes_du_devis`` (L-1V) :
        # le dimensionnement après le bloc horaire, les profils après le
        # dimensionnement (ils réutilisent le tableau qui vient d'être
        # calculé), la conception électrique en dernier.
        self.assertEqual(
            [nom for nom, _ in journal],
            ['rafraichir_etude_horaire_devis',
             'rafraichir_dimensionnement_devis',
             'rafraichir_profils_comparatifs_devis',
             'rafraichir_conception_electrique_devis'])
        # ``force=True`` conservé pour les trois qui l'acceptent ; la conception
        # électrique n'a pas de ``force`` (idempotente par empreinte) et reçoit
        # donc le défaut.
        self.assertEqual(
            dict(journal[:3]),
            {'rafraichir_etude_horaire_devis': True,
             'rafraichir_dimensionnement_devis': True,
             'rafraichir_profils_comparatifs_devis': True})

    def test_un_devis_fige_ne_declenche_aucune_etude(self):
        """YDOCF2 — la garde du devis figé vit AVANT le pipeline et n'a pas
        bougé : un PATCH refusé ne doit rien rafraîchir du tout."""
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-QJR9403',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), created_by=self.user)
        journal = self._espionner_les_quatre()

        reponse = self.api.patch(
            '/api/django/ventes/devis/%s/' % devis.id,
            {'note': 'interdit'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertEqual(journal, [])
