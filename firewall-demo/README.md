
### Enable needed service APIs:

```bash
# Enable the Deployment Manager API if it's not enabled:
  gcloud services enable deploymentmanager.googleapis.com

# Enable pubsub API:
  gcloud services enable pubsub.googleapis.com

# Enable Cloud Build API:
  gcloud services enable cloudbuild.googleapis.com

# Enable Resource Manager API:
  gcloud services enable cloudresourcemanager.googleapis.com

# Enable Cloud Functions API:
  gcloud services enable cloudfunctions.googleapis.com
```

### Grant permissions to servicre accounts

```bash
  PROJECT=$(gcloud config get-value project)
  PROJECT_NUMBER=$(gcloud projects list --filter="$PROJECT" --format="value(PROJECT_NUMBER)")
  PROJECT_ID=$(gcloud projects list --filter="$PROJECT" --format="value(PROJECT_ID)")
  # grant owner role to deployment manager
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT_NUMBER}@cloudservices.gserviceaccount.com --role roles/owner
  # grant invoker role to service account
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com --role roles/cloudfunctions.invoker
  # grant secret accessor role to service account
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com --role roles/secretmanager.secretAccessor
```

### Deploy the cloud function:

```bash
# set project id in the config file
sed -i -e "s/REPLACE_ME_PROJECT_ID/$PROJECT/" logging_func.yaml
# deploy
gcloud deployment-manager deployments create log-demo --config logging_func.yaml
```

### Enable email notification:

1. Add Sendgrid API key to Secret Manager:

```bash
# Type y if asked to enable the service
gcloud secrets create secret-id sendgrid-apikey --replication-policy="automatic"
```

2. Add the API key value. 

You can create a data file and run:
```bash
gcloud secrets versions add "sendgrid-apikey" --data-file="/path/to/apikey_file"
```
Or
```bash
echo -n "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" | \
    gcloud secrets versions add "sendgrid-apikey" --data-file=-
```
Ref: https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#secretmanager-add-secret-version-cli
