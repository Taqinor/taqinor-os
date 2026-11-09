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

    def test_share_link_expose_le_bloc_gamme(self):
        source, _ = self._paire('DEV-GAM-025')
        resp = self.api.post(
            f'/api/django/ventes/devis/{source.id}/share-link/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['gamme']['envoi'], GAMME_ENVOI_LES_DEUX)
        self.assertEqual(resp.data['gamme']['recommandee'], 'Essentielle')
