/**
 * Faux ERP du bout en bout (YBW56) — vrai serveur HTTP local, qui joue le
 * récepteur `POST /api/django/crm/webhooks/demande-rdv/` (YBW51) selon le
 * CONTRAT partagé (`src/contract_samples/demande_rdv_site.json`) :
 *  - clé `X-Site-Cle` connue, signature `t=,v1=` vérifiée (±300 s, HMAC du
 *    corps BRUT) — par un vérificateur indépendant du code du site ;
 *  - clés du corps ⊂ champs du contrat, aucune clé `refus` ni `company*` ;
 *  - idempotence sur `idempotency_key` DU CORPS (jamais l'en-tête) : un seul
 *    lead par clé, rejeu → 200 `deja_recu`.
 * Les constantes sont lues par `playwright.config.ts` (variables du Worker).
 */
import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { fileURLToPath } from 'node:url';

export const PORT_FAUX_ERP = 4391;
export const CHEMIN_FAUX_ERP = '/api/django/crm/webhooks/demande-rdv/';
export const URL_FAUX_ERP = `http://127.0.0.1:${PORT_FAUX_ERP}${CHEMIN_FAUX_ERP}`;
export const CLE_E2E = 'cle-e2e';
/** Secret de TEST seulement (jamais un secret réel). */
export const SECRET_E2E = 'e2e0'.repeat(16);

const CONTRAT = JSON.parse(readFileSync(fileURLToPath(new URL('../src/contract_samples/demande_rdv_site.json', import.meta.url)), 'utf-8')) as {
  champs: Record<string, unknown>;
  refus: string[];
};

export interface Requete {
  entetes: Record<string, string | string[] | undefined>;
  corps: string;
  statut: number;
  motif: string;
}

export interface FauxErp {
  url: string;
  requetes: Requete[];
  leads: Map<string, number>;
  fermer(): Promise<void>;
}

function verifier(entetes: http.IncomingHttpHeaders, corps: string): { statut: number; motif: string; reponse: unknown; leadCle?: string } {
  if (entetes['x-site-cle'] !== CLE_E2E) return { statut: 401, motif: 'cle', reponse: { detail: 'Non autorisé.' } };
  const m = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(String(entetes['x-signature'] ?? ''));
  const maintenant = Math.floor(Date.now() / 1000);
  if (!m || Math.abs(maintenant - Number(m[1])) > 300) return { statut: 401, motif: 'signature', reponse: { detail: 'Non autorisé.' } };
  const attendu = createHmac('sha256', SECRET_E2E).update(`${m[1]}.${corps}`).digest('hex');
  if (attendu !== m[2]) return { statut: 401, motif: 'signature', reponse: { detail: 'Non autorisé.' } };
  let donnees: Record<string, unknown>;
  try {
    donnees = JSON.parse(corps);
  } catch {
    return { statut: 400, motif: 'json', reponse: { detail: 'JSON invalide.' } };
  }
  const refus = Object.keys(donnees).filter((k) => CONTRAT.refus.includes(k) || k.toLowerCase().startsWith('company'));
  if (refus.length) return { statut: 400, motif: 'refus', reponse: { refus } };
  const horsContrat = Object.keys(donnees).filter((k) => !(k in CONTRAT.champs));
  if (horsContrat.length) return { statut: 400, motif: `hors contrat : ${horsContrat.join(',')}`, reponse: {} };
  const cle = donnees.idempotency_key;
  if (typeof cle !== 'string' || !cle) return { statut: 400, motif: 'idempotency_key', reponse: {} };
  return { statut: 201, motif: 'ok', reponse: {}, leadCle: cle };
}

export function demarrerFauxErp(): Promise<FauxErp> {
  const requetes: Requete[] = [];
  const leads = new Map<string, number>();
  const serveur = http.createServer((req, res) => {
    let corps = '';
    req.setEncoding('utf8');
    req.on('data', (c: string) => (corps += c));
    req.on('end', () => {
      if (req.method !== 'POST' || req.url !== CHEMIN_FAUX_ERP) {
        res.writeHead(404).end();
        return;
      }
      const v = verifier(req.headers, corps);
      let { statut, reponse } = v;
      if (v.leadCle) {
        const existant = leads.get(v.leadCle);
        if (existant !== undefined) {
          statut = 200;
          reponse = { id: existant, statut: 'deja_recu' };
        } else {
          const id = leads.size + 1;
          leads.set(v.leadCle, id);
          reponse = { id, statut: 'recu' };
        }
      }
      requetes.push({ entetes: { ...req.headers }, corps, statut, motif: v.motif });
      res.writeHead(statut, { 'content-type': 'application/json' }).end(JSON.stringify(reponse));
    });
  });
  return new Promise((resoudre, rejeter) => {
    serveur.once('error', rejeter);
    serveur.listen(PORT_FAUX_ERP, '127.0.0.1', () => {
      const port = (serveur.address() as AddressInfo).port;
      resoudre({
        url: `http://127.0.0.1:${port}${CHEMIN_FAUX_ERP}`,
        requetes,
        leads,
        fermer: () => new Promise((r) => serveur.close(() => r())),
      });
    });
  });
}
