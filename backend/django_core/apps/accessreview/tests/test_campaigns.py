"""NTSEC19 — Tests campagnes de revue d'accès + attestation manager.

Garanties : le lancement génère un item par compte du périmètre, un manager
atteste ou révoque, une révocation retire le rôle, tout scopé société.
"""
from types import SimpleNamespace

from apps.roles.models import Role
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import UserFactory

from apps.accessreview.models import AccessReviewCampaign, AccessReviewItem
from apps.accessreview.serializers import AccessReviewItemSerializer
from apps.accessreview.services import generate_items


class AccessReviewTests(TenantAPITestCase):
    BASE = '/api/django/accessreview/campaigns/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_create_generates_items_for_each_user(self):
        UserFactory(company=self.company, username='m1')
        UserFactory(company=self.company, username='m2')
        r = self._admin().post(
            self.BASE, {'nom': 'Q3 review', 'perimetre': 'all'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        campaign = AccessReviewCampaign.objects.get()
        # Un item par compte actif de la société (au moins m1, m2, l'admin…).
        self.assertGreaterEqual(campaign.items.count(), 3)
        self.assertEqual(
            campaign.items.filter(company=self.company).count(),
            campaign.items.count())

    def test_perimetre_role_reference_illisible_perimetre_vide(self):
        # api-fuzz-full 24/10 : ``perimetre_ref`` est un texte libre au schéma ;
        # une référence de rôle illisible (ou hors entier 32 bits) ne désigne
        # aucun rôle -> campagne créée (201) sans item, jamais un 400.
        for ref in ('\x88î=á', 'abc', '²', '9' * 30):
            with self.subTest(ref=ref):
                r = self._admin().post(
                    self.BASE, {'nom': 'R', 'perimetre': 'role',
                                'perimetre_ref': ref}, format='json')
                self.assertEqual(r.status_code, 201, r.content)
                campagne = AccessReviewCampaign.objects.get(pk=r.json()['id'])
                self.assertEqual(campagne.items.count(), 0)

    def test_textes_stricts_pas_de_nombre_converti(self):
        # CI #997 fuzz : ``perimetre_ref: 0`` était converti en « 0 » (201).
        for champ in ('perimetre_ref', 'nom'):
            with self.subTest(champ=champ):
                r = self._admin().post(
                    self.BASE, {'nom': 'Q4', 'perimetre': 'all', champ: 0},
                    format='json')
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(champ, r.json())
        self.assertFalse(AccessReviewCampaign.objects.exists())

    def test_modification_complete_textes_stricts_et_listes_paginees(self):
        # ERR-ENF11-FUZZ-ACCESSREVIEW — la MODIFICATION complète suit la même
        # règle que la création (un nombre n'est pas converti en texte) et les
        # deux listes refusent un ``page_size`` qui n'est pas UN entier.
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        api = self._admin()
        r = api.put(
            f'{self.BASE}{campaign.id}/',
            {'nom': 'c', 'perimetre': 'all', 'perimetre_ref': 0},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('perimetre_ref', r.json())
        campaign.refresh_from_db()
        self.assertEqual(campaign.perimetre_ref, '')
        for liste in (self.BASE, '/api/django/accessreview/sod-rules/'):
            for requete in ('?page_size=null', '?page_size=null&page_size=null'):
                r = api.get(liste + requete)
                self.assertEqual(r.status_code, 400, (liste, r.content))
            self.assertEqual(api.get(liste).status_code, 200)

    def test_non_admin_forbidden(self):
        r = self.client_as().post(self.BASE, {'nom': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_items_scoped_to_company(self):
        UserFactory(company=self.other_company, username='foreigner')
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        users = set(campaign.items.values_list('user__username', flat=True))
        self.assertNotIn('foreigner', users)

    def test_attester_revoke_removes_role(self):
        role = Role.objects.create(company=self.company, nom='Compta')
        member = UserFactory(
            company=self.company, username='rev', role=role)
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        item = AccessReviewItem.objects.get(campagne=campaign, user=member)
        r = self._admin().post(
            f'{self.BASE}{campaign.id}/attester/',
            {'item': item.id, 'decision': 'revoque',
             'commentaire': 'plus besoin'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        member.refresh_from_db()
        self.assertEqual(member.role.nom, 'Utilisateur')  # APFS47 — jamais « aucun rôle »
        item.refresh_from_db()
        self.assertEqual(item.decision, 'revoque')
        self.assertIsNotNone(item.reviewer_id)
        self.assertIsNotNone(item.decided_at)

    def test_revoquer_le_proprietaire_protege_ou_le_dernier_refuse(self):
        """APUB4 (C-APUB-002) — la révocation passe la garde de rang de
        l'écran Comptes : fondateur protégé puis dernier propriétaire 403,
        rien d'écrit ; un Commercial reste révocable (200, « Utilisateur »)."""
        from apps.roles import permissions_registre as registre
        from authentication.role_tiers import CODE_RANG_CIBLE, MESSAGES_REFUS_GESTION
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(registre.DIRECTEUR_PERMISSIONS))
        commercial = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(registre.COMMERCIAL_PERMISSIONS))
        fondateur = UserFactory(company=self.company, username='apub4-f',
                                role=directeur, is_protected=True)
        d2 = UserFactory(company=self.company, username='apub4-d2', role=directeur)
        com = UserFactory(company=self.company, username='apub4-c', role=commercial)
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        api = self.client_as(user=d2)
        url = f'{self.BASE}{campaign.id}/attester/'

        def revoquer(cible):
            item = AccessReviewItem.objects.get(campagne=campaign, user=cible)
            return item, api.post(url, {'item': item.id, 'decision': 'revoque'},
                                  format='json')
        item, r = revoquer(fondateur)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(r.json()['detail'], MESSAGES_REFUS_GESTION[CODE_RANG_CIBLE])
        CustomUser.objects.filter(pk=fondateur.pk).update(is_active=False)
        item_d2, r = revoquer(d2)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertIn('dernier propriétaire', r.json()['detail'])
        for it, user in ((item, fondateur), (item_d2, d2)):
            it.refresh_from_db()
            user.refresh_from_db()
            self.assertEqual((it.decision, user.role_id), ('en_attente', directeur.pk))
        _, r = revoquer(com)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['user_nom'], 'apub4-c')
        com.refresh_from_db()
        self.assertEqual(com.role.nom, 'Utilisateur')

    def test_attester_maintien_keeps_role(self):
        role = Role.objects.create(company=self.company, nom='Compta')
        member = UserFactory(
            company=self.company, username='keep', role=role)
        campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        generate_items(campaign)
        item = AccessReviewItem.objects.get(campagne=campaign, user=member)
        r = self._admin().post(
            f'{self.BASE}{campaign.id}/attester/',
            {'item': item.id, 'decision': 'maintenu'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        member.refresh_from_db()
        self.assertEqual(member.role_id, role.id)

    def test_cannot_attest_foreign_item(self):
        other_campaign = AccessReviewCampaign.objects.create(
            company=self.other_company, nom='c', perimetre='all')
        member = UserFactory(company=self.other_company, username='fm')
        foreign_item = AccessReviewItem.objects.create(
            company=self.other_company, campagne=other_campaign, user=member)
        my_campaign = AccessReviewCampaign.objects.create(
            company=self.company, nom='mine', perimetre='all')
        r = self._admin().post(
            f'{self.BASE}{my_campaign.id}/attester/',
            {'item': foreign_item.id, 'decision': 'revoque'}, format='json')
        # ENF11 : même refus qu'un item inconnu (409), rien sur l'autre société.
        self.assertEqual(r.status_code, 409)

    def test_enf11_attester_corps_invalide_400_pas_500(self):
        """ENF11 — decision objet / item non entier ou hors bornes = 400."""
        c = AccessReviewCampaign.objects.create(
            company=self.company, nom='c', perimetre='all')
        for corps in ({'item': 0, 'decision': {}},
                      {'item': 'abc', 'decision': 'maintenu'},
                      {'item': 10 ** 30, 'decision': 'maintenu'},
                      {'item': 1, 'decision': 'maintenu', 'commentaire': 5}):
            r = self._admin().post(
                f'{self.BASE}{c.id}/attester/', corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))
        r = self._admin().post(f'{self.BASE}{c.id}/attester/', [1], format='json')
        self.assertEqual(r.status_code, 400)
        r = self._admin().post(
            f'{self.BASE}{c.id}/attester/',
            {'item': 999999, 'decision': 'maintenu'}, format='json')
        self.assertEqual(r.status_code, 409)  # ENF11 : la campagne existe

    def test_enf17_item_fk_bornees_societe(self):
        """ENF17 — campagne / compte d'une autre société = id absent (400)."""
        ctx = {'request': SimpleNamespace(user=self.user)}
        mine = AccessReviewCampaign.objects.create(
            company=self.company, nom='m', perimetre='all')
        other = AccessReviewCampaign.objects.create(
            company=self.other_company, nom='o', perimetre='all')
        for champ, propre, etranger in (
                ('campagne', mine, other), ('user', self.user, self.other_user)):
            with self.subTest(champ=champ):
                ser = AccessReviewItemSerializer(
                    data={champ: etranger.pk}, partial=True, context=ctx)
                self.assertFalse(ser.is_valid())
                self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
                champ_lie = AccessReviewItemSerializer(context=ctx).fields[champ]
                self.assertEqual(champ_lie.to_internal_value(propre.pk), propre)
