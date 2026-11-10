"""GAMMES — 2. Mode d'envoi (à la carte).

Partie 2 sur 8 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

Décision fondateur 2026-08-18 couverte ici : ENVOI À LA CARTE — « les_deux »
(DÉFAUT) expose la gamme sœur au lien client ; « seule » n'en laisse RIEN
franchir la frontière publique.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_envoi -v 2
"""
from apps.ventes.services import (
    GAMME_ENVOI_LES_DEUX, GAMME_ENVOI_SEULE, gamme_envoi, gamme_soeur,
    regler_envoi_gamme,
)
from apps.ventes.tests._gammes_offre_common import GammeBase, make_devis


class TestModeEnvoi(GammeBase):

    def test_defaut_les_deux(self):
        """DÉFAUT fondateur : les deux gammes (comme l'axe batterie)."""
        source, soeur = self._paire('DEV-GAM-020')
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_LES_DEUX)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_LES_DEUX)

    def test_regler_seule_ecrit_des_deux_cotes(self):
        source, soeur = self._paire('DEV-GAM-021')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_SEULE)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_SEULE)

    def test_mode_invalide_est_ignore(self):
        source, _ = self._paire('DEV-GAM-022')
        regler_envoi_gamme(source, 'nimporte_quoi')
        source.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_LES_DEUX)

    def test_devis_sans_gamme_inchange(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-023')
        regler_envoi_gamme(d, GAMME_ENVOI_SEULE)
        d.refresh_from_db()
        self.assertEqual(d.etude_params or {}, {})
        self.assertIsNone(gamme_soeur(d))

    def test_envoi_whatsapp_pose_le_mode(self):
        source, soeur = self._paire('DEV-GAM-024')
        self.client_obj.telephone = '+212611000020'
        self.client_obj.save(update_fields=['telephone'])
        resp = self.api.post(
            f'/api/django/ventes/devis/{source.id}/whatsapp/',
            {'gamme_envoi': GAMME_ENVOI_SEULE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual(gamme_envoi(source), GAMME_ENVOI_SEULE)
        self.assertEqual(gamme_envoi(soeur), GAMME_ENVOI_SEULE)

    def test_les_deux_envoie_aussi_la_soeur(self):
        """ADVS49 (D-ADVS-VER5-1 = envoyer_les_deux) — envoi « les deux » : la
        sœur passe envoyée avec un lien vivant, la page client sert son jeton ;
        un renvoi ne frappe aucun second lien ; « seule » : sœur brouillon."""
        from apps.ventes.models import Devis, ShareLink
        from apps.ventes.public.payload_variantes import _gammes_public
        source, soeur = self._paire('DEV-GAM-026')
        url = f'/api/django/ventes/devis/{source.id}/share-link/'
        corps = {'envoi': True, 'gamme_envoi': GAMME_ENVOI_LES_DEUX}
        self.assertEqual(self.api.post(url, corps, format='json').status_code, 200)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual((source.statut, soeur.statut), (Devis.Statut.ENVOYE, Devis.Statut.ENVOYE))
        jeton = ShareLink.objects.get(devis=soeur).token
        self.assertIn(str(jeton), _gammes_public(source)['soeur']['proposition_path'])
        self.assertEqual(self.api.post(url, corps, format='json').status_code, 200)
        self.assertEqual(ShareLink.objects.filter(devis=soeur).count(), 1)
        seule, soeur_seule = self._paire('DEV-GAM-027')
        resp = self.api.post(f'/api/django/ventes/devis/{seule.id}/share-link/',
                             {'envoi': True, 'gamme_envoi': GAMME_ENVOI_SEULE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        soeur_seule.refresh_from_db()
        self.assertEqual(soeur_seule.statut, Devis.Statut.BROUILLON)

    def test_les_deux_soeur_creee_apres_envoi(self):
        """ADVS50 — source DÉJÀ envoyée, gamme créée ensuite : le renvoi « les
        deux » passe la sœur envoyée (lien vivant, servie au comparatif) sans
        re-tamponner la source ; « seule » : sœur brouillon ; remise de la
        sœur refusée (T17) : 409, sœur brouillon."""
        from decimal import Decimal
        from apps.parametres.models import CompanyProfile
        from apps.ventes.models import Devis, ShareLink
        from apps.ventes.public.payload_variantes import _gammes_public
        from apps.ventes.tests._gammes_offre_common import add_ligne

        def source_envoyee(ref):
            src = make_devis(self.company, self.user, self.client_obj, ref)
            add_ligne(src, self.panneau, qty='10')
            url = f'/api/django/ventes/devis/{src.id}/share-link/'
            self.assertEqual(self.api.post(url, {'envoi': True}, format='json').status_code, 200)
            r = self.api.post(f'/api/django/ventes/devis/{src.id}/dupliquer-variante-gamme/',
                              {'nom': 'Premium'}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            src.refresh_from_db()
            return src, Devis.objects.get(pk=r.data['gamme']['id']), url

        source, soeur, url = source_envoyee('DEV-GAM-050')
        envoi_avant = source.date_envoi
        corps = {'envoi': True, 'gamme_envoi': GAMME_ENVOI_LES_DEUX}
        resp = self.api.post(url, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        source.refresh_from_db()
        soeur.refresh_from_db()
        self.assertEqual((source.statut, soeur.statut), (Devis.Statut.ENVOYE, Devis.Statut.ENVOYE))
        self.assertEqual(source.date_envoi, envoi_avant)
        jeton = ShareLink.objects.get(devis=soeur).token
        self.assertIn(str(jeton), _gammes_public(source)['soeur']['proposition_path'])
        self.assertEqual(self.api.post(url, corps, format='json').status_code, 200)
        self.assertEqual(ShareLink.objects.filter(devis=soeur).count(), 1)
        _, soeur_seule, url_seule = source_envoyee('DEV-GAM-051')
        self.assertEqual(self.api.post(url_seule, {'envoi': True, 'gamme_envoi': GAMME_ENVOI_SEULE},
                                       format='json').status_code, 200)
        soeur_seule.refresh_from_db()
        self.assertEqual(soeur_seule.statut, Devis.Statut.BROUILLON)
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        _, soeur_remise, url_remise = source_envoyee('DEV-GAM-052')
        Devis.objects.filter(pk=soeur_remise.pk).update(remise_globale=Decimal('30'))
        self.assertEqual(self.api.post(url_remise, corps, format='json').status_code, 409)
        soeur_remise.refresh_from_db()
        self.assertEqual(soeur_remise.statut, Devis.Statut.BROUILLON)
        self.assertFalse(ShareLink.objects.filter(devis=soeur_remise).exists())

    def test_share_link_expose_le_bloc_gamme(self):
        source, _ = self._paire('DEV-GAM-025')
        resp = self.api.post(
            f'/api/django/ventes/devis/{source.id}/share-link/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['gamme']['envoi'], GAMME_ENVOI_LES_DEUX)
        self.assertEqual(resp.data['gamme']['recommandee'], 'Essentielle')
