/**
 * ClimaAperto — trigger-worker.js
 *
 * GitHub non garantisce l'orario dei workflow schedulati (`on: schedule`) sui repository
 * pubblici. Questo Worker usa i Cron Trigger di Cloudflare (affidabili) per avviare i
 * workflow tramite l'API di GitHub (evento workflow_dispatch).
 *
 * Due Cron Trigger, da impostare nella dashboard Cloudflare (Impostazioni -> Eventi trigger):
 *   "ogni 10 minuti"   (espressione: asterisco/10 nei minuti) -> aggiorna-incendi.yml
 *   "20 7,13 * * *"     -> aggiorna-clima.yml  (temperatura vs normale, alle 07:20
 *                        e 13:20 UTC: la seconda esecuzione serve se al mattino mancava
 *                        ancora l'analisi delle 18 UTC del giorno prima)
 * Il Worker sceglie il workflow in base all'espressione cron che lo ha svegliato.
 *
 * Richiede il secret GITHUB_TOKEN: token fine-grained con "Actions: Read and write"
 * limitato a questo repository.
 */

const PROPRIETARIO = "emanuelc89";
const REPOSITORY = "climaaperto";
const WORKFLOW_PER_CRON = {
  "*/10 * * * *": "aggiorna-incendi.yml",
  "20 7,13 * * *": "aggiorna-clima.yml",
};

export default {
  async scheduled(event, env, ctx) {
    const workflow = WORKFLOW_PER_CRON[event.cron] ?? "aggiorna-incendi.yml";
    const url = `https://api.github.com/repos/${PROPRIETARIO}/${REPOSITORY}/actions/workflows/${workflow}/dispatches`;

    const risposta = await fetch(url, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "User-Agent": "climaaperto-trigger-worker",
      },
      body: JSON.stringify({ ref: "main" }),
    });

    if (!risposta.ok) {
      console.log(`Errore nel richiamare ${workflow}:`, risposta.status, await risposta.text());
    } else {
      console.log(`Avviato ${workflow} (cron ${event.cron})`);
    }
  },
};
