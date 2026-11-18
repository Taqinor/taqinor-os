// Config Playwright de la machine cloud — À COPIER (non versionnée) dans <worktree>/frontend/ :
// reprend la config du dépôt telle quelle et ne change que deux choses propres à cette machine :
//   1. le navigateur : le Chromium préinstallé (/opt/pw-browsers/chromium), car la version de
//      @playwright/test du dépôt attend un build qui n'est pas téléchargeable ici ;
//   2. le serveur : la pile (vite preview + Django) est lancée par /opt/taches-cloud/pile.sh, jamais par Playwright.
import base from './playwright.config.js'

const executablePath = '/opt/pw-browsers/chromium'
export default {
  ...base,
  webServer: undefined,
  projects: (base.projects || []).map((p) => ({
    ...p,
    use: { ...(p.use || {}), launchOptions: { ...((p.use || {}).launchOptions || {}), executablePath } },
  })),
}
