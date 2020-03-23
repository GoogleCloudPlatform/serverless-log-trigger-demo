
### Overview
This example demonstrates how a GCP network firewall rule change triggers a cloud function via pubsub and the function validates the rule.

The cloud function takes a list of whitelisted rules from the environment variables. If a firewall rule is created or updated that has any violation, it would be deleted automatically in near real time (within seconds).


Optionally, you can configure [Sendgrid](https://sendgrid.com/) to send an email notification to your email address.

Please review the code for details.

You can follow the instructions below in your cloud shell to test it.

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

### Grant permissions to service accounts

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

### Verify the result

The default whitelist rules from the environment variables are:

FIREWALL_WHITE_LIST1: "tcp:0.0.0.0/0:80,443"

FIREWALL_WHITE_LIST2: "udp:0.0.0.0/0"

You can create a new firewall rule with a violation such as opening the port 20 for 0.0.0.0/0. You will see the rule will be removed shortly.

### Enable email notification:

1. Add Sendgrid API key to Secret Manager:

```bash
# Type y if asked to enable the service
gcloud secrets create sendgrid-apikey --replication-policy="automatic"
```

2. Add the API key value. 

You can create a data file and run:
```bash
gcloud secrets versions add "sendgrid-apikey" --data-file="/path/to/apikey_file"
```
Or
```bash
echo -n "your sendgrid api key" | \
    gcloud secrets versions add "sendgrid-apikey" --data-file=-
```
Ref: https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#secretmanager-add-secret-version-cli

3. Add environment variables:

NOTIFICATION_EMAIL(Required): Email address for the notification

NOTIFICATION_SUBJECT(Optional): Email subject. The default is __Firewall violation detected__

NOTIFICATION_SENDER(Optional): Email sender. The default is __No Reply<noreply@example.com>__

You can update the deployment manager config file and update your deployment. Alternatively, you can add them via the Cloud Function console or run the following command:

```bash
gcloud functions deploy --update-env-vars=NOTIFICATION_EMAIL=shen.xiang@gmail.com,NOTIFICATION_SUBJECT='Test email',NOTIFICATION_SENDER='Reply<noreply@example.com>' logging-function
```

### License

Apache 2.0 - See [LICENSE](LICENSE) for more information.