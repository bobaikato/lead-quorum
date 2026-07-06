# Deploying to Cloud Run

Three services from one image: two A2A readers and the web orchestrator. Commands below
are the standard Cloud Run path; cross-check flags against the codelab's deploy section
if anything moved.

## 0. Prereqs

- A GCP project with billing enabled, `gcloud` authenticated, and:

```bash
export PROJECT=<your-project-id>
export REGION=us-central1
gcloud config set project $PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com
```

- The Gemini API key is passed as an env var. For anything beyond a demo, put it in
  Secret Manager and use `--set-secrets` instead of `--set-env-vars`.

## 1. Deploy the two reader services

```bash
gcloud run deploy lq-enrichment \
  --source . --region $REGION --allow-unauthenticated \
  --set-env-vars SERVICE=a2a,AGENT=enrichment,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_API_KEY=<key>

gcloud run deploy lq-rederive \
  --source . --region $REGION --allow-unauthenticated \
  --set-env-vars SERVICE=a2a,AGENT=rederive,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_API_KEY=<key>
```

Grab each service URL, then update BOTH with their own public URL so the A2A agent card
advertises the reachable address:

```bash
ENRICH_URL=$(gcloud run services describe lq-enrichment --region $REGION --format='value(status.url)')
REDERIVE_URL=$(gcloud run services describe lq-rederive --region $REGION --format='value(status.url)')

gcloud run services update lq-enrichment --region $REGION --set-env-vars PUBLIC_URL=$ENRICH_URL
gcloud run services update lq-rederive  --region $REGION --set-env-vars PUBLIC_URL=$REDERIVE_URL
```

Sanity check: `curl $ENRICH_URL/.well-known/agent-card.json` should return the card with
the public URL in it.

## 2. Deploy the web orchestrator

```bash
gcloud run deploy lq-web \
  --source . --region $REGION --allow-unauthenticated \
  --set-env-vars SERVICE=web,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_API_KEY=<key>,ENRICHMENT_CARD_URL=$ENRICH_URL/.well-known/agent-card.json,REDERIVE_CARD_URL=$REDERIVE_URL/.well-known/agent-card.json
```

Open the `lq-web` URL: paste notes, get the verdict. The orchestrator talks to the two
readers over A2A across services, which you can verify in each reader's request logs.

## 3. Notes

- `--allow-unauthenticated` keeps the demo simple. Hardening step one is IAM
  service-to-service auth between web and the readers.
- Free-tier Gemini keys are rate-limited; if the readers start returning 429 under load,
  that is quota, not the deploy.
- Teardown: `gcloud run services delete lq-enrichment lq-rederive lq-web --region $REGION`.
