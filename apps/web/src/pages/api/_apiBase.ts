/**
 * Base de l'API ERP des proxys same-origin (ENF19 : une seule copie, partagée avec `_proxy.ts`) :
 * PUBLIC_API_BASE runtime (cf.env) OU build, sinon https://api.taqinor.ma.
 */
import * as cf from 'cloudflare:workers';

const API_BASE_PAR_DEFAUT = 'https://api.taqinor.ma';

export function resolveApiBase(): string {
  const runtimeEnv = (cf.env ?? {}) as { PUBLIC_API_BASE?: string };
  const depuisRuntime = runtimeEnv.PUBLIC_API_BASE?.trim();
  const depuisBuild = (import.meta.env.PUBLIC_API_BASE as string | undefined)?.trim();
  return depuisRuntime || depuisBuild || API_BASE_PAR_DEFAUT;
}
