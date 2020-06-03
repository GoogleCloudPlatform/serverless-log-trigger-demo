
### Overview
In this example, a change made to a Cloud Storage bucket triggers a cloud function via Pub/Sub. If the change makes the bucket open to the public for read/write and the bucket is not in a whitelist(defined in an environment variable), the function removes the IAM policy and make the bucket private.

_Note: You can setup Pub/Sub notification for object changes in a bucket. However, bucket policy changes are only logged in the audit logs._

Optionally, you can configure [Sendgrid](https://sendgrid.com/) to send an email notification to your email address.

Please review the code for details.

You can follow the instructions below in your cloud shell to test it.

### Enable needed service APIs:

```bash
# Enable the Deployment Manager API if it's not enabled:
  gcloud services enable deploymentmanager.googleapis.com

# Enable Pub/Sub API:
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
  PROJECT_NUMBER=$(gcloud projects list --filter="PROJECT_ID=$PROJECT" --format="value(PROJECT_NUMBER)")
  # grant owner role to deployment manager
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT_NUMBER}@cloudservices.gserviceaccount.com --role roles/owner
  # grant invoker role to service account
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT}@appspot.gserviceaccount.com --role roles/cloudfunctions.invoker
  # grant secret accessor role to service account
  gcloud projects add-iam-policy-binding $PROJECT --member serviceAccount:${PROJECT}@appspot.gserviceaccount.com --role roles/secretmanager.secretAccessor
```

### Deploy the cloud function:

```bash
# set project id in the config file
sed -e "s/REPLACE_ME_PROJECT_ID/$PROJECT/" logging_func.yaml > gcs_logging_func.yaml
# deploy
gcloud deployment-manager deployments create gcs-log-demo --config gcs_logging_func.yaml
```

Alternatively, you can use [Terraform](https://www.terraform.io/) to deploy the function. The `main.tf` file is a Terraform configuration example you can use.


### Verify the result

If you make your testing bucket to public, you will see the public access is gone in a few seconds.

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

NOTIFICATION_SUBJECT(Optional): Email subject. The default is __Bucket violation detected__

NOTIFICATION_SENDER(Optional): Email sender. The default is __No Reply<noreply@example.com>__

You can update the deployment manager config file and update your deployment. Alternatively, you can add them via the Cloud Function console or run a command like the following:

```bash
gcloud functions deploy --update-env-vars=NOTIFICATION_EMAIL=bob@example.com,NOTIFICATION_SUBJECT='Test email',NOTIFICATION_SENDER='noreply<noreply@example.com>' logging-function
```