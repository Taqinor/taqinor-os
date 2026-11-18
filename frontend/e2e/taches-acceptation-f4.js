// Aides de l'ACCEPTATION EN DIRECT « Tâches », fusion 4 (TCH142, TCH172 — `e2e/acceptation/tch3.spec.js`).
// Complète `taches-acceptation.js` (fusion 2 : scénario, connexion `demo_taches`, vues) et `taches-acceptation-f3.js`
// (fusion 3 : captures) sans les recopier. Ce module ne fait que :
//   - poser par le HARNAIS (shell Django des specs, jamais le semis) ce que l'ERP doit contenir pour un oracle : les
//     droits du rôle de TEST de `demo_taches` (le semis le remet à ses quatre droits à chaque passage), un lead de
//     démonstration dont `demo_taches` est responsable, un devis « envoyé » de ce lead ;
//   - accepter ce devis par la VRAIE route de `ventes` (`POST ventes/devis/{id}/accepter/`, client DRF sous l'horloge du
//     scénario : le signal `devis_accepted` part du service `accept_devis`), annuler l'acceptation par le service de
//     `ventes` (`annuler_acceptation`, qui émet `devis_acceptation_annulee`) ;
//   - lire les suggestions de l'ERP du compte en base (statut et clé : ce que l'écran ne montre pas).
// Aucune donnée n'est écrite avant le semis de l'étape : chaque aide suppose `scenario()` déjà joué.
import { expect } from '@playwright/test'
import { py } from './acceptation/_django.js'
import { lire, liste } from './taches-acceptation.js'

/** Le compte `demo_taches` vu par le shell Django : `u` (utilisateur) et `soc` (sa société). */
export const DEMO = "u = U.objects.get(username='demo_taches'); soc = u.company_id\n"

/** Ajoute `codes` au rôle de TEST de `demo_taches` (union, idempotent) ; rend les droits du rôle. */
export function accorder(...codes) {
  return py(`${DEMO}r = u.role
r.permissions = sorted(set(r.permissions or []) | set(${JSON.stringify(codes)}))
r.save(update_fields=['permissions'])
sortie(r.permissions)`)
}

/** Le lead de démonstration n° `n` de la société de `demo_taches` (« Lead de démonstration », puis « … 2 »…),
 *  `demo_taches` responsable, et son client : `{lead, client}`. Un lead n'a qu'UNE vente en vigueur (ventes refuse
 *  d'accepter un second devis du même lead) : deux devis acceptés = deux leads. Retrouvé s'il existe déjà (le semis
 *  efface les leads de la société de démonstration à chaque passage). */
export function leadDeDemo(n = 1) {
  const email = `lead-demo-f4-${n}@accept.test`
  const nom = n === 1 ? 'de démonstration' : `de démonstration ${n}`
  return py(`${DEMO}from django.apps import apps as registre
Lead = registre.get_model('crm', 'Lead'); Client = registre.get_model('crm', 'Client')
client = Client.objects.filter(company_id=soc, email='${email}').first() or Client.objects.create(
    company_id=soc, email='${email}', nom='${nom}', prenom='Lead')
lead = Lead.objects.filter(company_id=soc, email='${email}', owner=u).first() or Lead.objects.create(
    company_id=soc, email='${email}', nom='${nom}', prenom='Lead', owner=u, client=client)
sortie({'lead': lead.pk, 'client': client.pk})`)
}

/** Un devis « envoyé » du lead (créé par `demo_taches`) : `{id, reference}`. */
export function devisEnvoye({ lead, client }) {
  return py(`${DEMO}import time
from decimal import Decimal
from django.apps import apps as registre
Devis = registre.get_model('ventes', 'Devis')
d = Devis.objects.create(company_id=soc, reference='DEV-ACC-F4-%d' % (time.time_ns() // 1000 % 10**9), client_id=${client},
    lead_id=${lead}, created_by=u, taux_tva=Decimal('20'), statut='envoye')
sortie({'id': d.pk, 'reference': d.reference})`)
}

/** Accepte le devis par la VRAIE route de `ventes`, en `demo_taches`, à l'instant `iso` (UTC = Maroc). */
export async function accepterDevis(id, iso) {
  const r = await py(`code, corps = a_l_heure('${iso}', 'post', '/api/django/ventes/devis/${id}/accepter/',
    {'nom': 'Lead de démonstration'}, username='demo_taches')
sortie({'code': code, 'statut': (corps or {}).get('statut'), 'detail': (corps or {}).get('detail')})`)
  expect(r.code, `acceptation du devis ${id} : ${JSON.stringify(r)}`).toBe(200)
  expect(r.statut).toBe('accepte')
  return r
}

/** Annule l'acceptation du devis par le service de `ventes` (émet `devis_acceptation_annulee`) ; rend le statut. */
export function annulerAcceptation(id, iso) {
  return py(`${DEMO}from django.apps import apps as registre
from django.utils.dateparse import parse_datetime
from apps.ventes.domain.cycle_vie import annuler_acceptation
d = registre.get_model('ventes', 'Devis').objects.get(pk=${id}, company_id=soc)
with mock.patch('django.utils.timezone.now', return_value=parse_datetime('${iso}')):
    annuler_acceptation(devis=d, user=u, motif='acceptation en direct TCH142')
d.refresh_from_db()
sortie(d.statut)`)
}

/** Les suggestions de l'ERP de `demo_taches`, en base (toutes, dans l'ordre de création). */
export function suggestionsEnBase() {
  return py(`${DEMO}from apps.taches.models.erp import SuggestionTache
sortie([dict(id=s.pk, cle=s.cle, statut=s.statut, titre=s.titre_propose, tache=s.tache_id)
        for s in SuggestionTache.objects.filter(company_id=soc, proprietaire=u).order_by('pk')])`)
}

/** Tous les projets du compte (toutes pages). */
export async function tousLesProjets(p) {
  const tous = []
  for (let page = 1; ; page += 1) {
    const corps = await lire(p, 'projets/', { page: String(page) })
    tous.push(...liste(corps))
    if (!corps.next) return tous
  }
}

/** Le projet du compte qui porte exactement ce nom. */
export async function projetNomme(p, nom) {
  const trouves = (await tousLesProjets(p)).filter((x) => x.nom === nom)
  expect(trouves, `un seul projet « ${nom} »`).toHaveLength(1)
  return trouves[0]
}
