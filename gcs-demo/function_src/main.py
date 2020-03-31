# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os
import time

PROJECT_ID = os.environ.get("PROJECT_ID")
NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL")
MONITOR_TYPES = [
    "storage.buckets.create",
    "storage.buckets.update",
    "storage.setIamPermissions",
]
WHITE_LISTS = []
for n, v in os.environ.items():
    name = n.upper()
    if name.startswith("BUCKET_WHITE_LIST"):
        WHITE_LISTS = map(str.strip, v.split(","))


def process_bucket_audit_log(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
       event (dict): Event payload.
       context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")

    log_data = json.loads(pubsub_message)
    payload = log_data["protoPayload"]

    if (
        payload["serviceName"] == "storage.googleapis.com"
        and payload["methodName"] in MONITOR_TYPES
    ):

        bucket_name = payload["resourceName"].split("/")[-1]
        if bucket_name in WHITE_LISTS:
            print(f"Bucket {bucket_name} is in the whitelist. Skip...")
            return

        violations = []
        policy_data = payload["serviceData"]["policyDelta"]["bindingDeltas"]
        for item in policy_data:
            if item["action"] == "ADD" and (
                item["member"] == "allUsers" or item["member"] == "allAuthenticatedUsers"
            ):
                violations.append(item)

        if violations:
            print(f"Total violations for this API call: {violations}")
            make_bucket_private(bucket_name)
            if NOTIFICATION_EMAIL:
                actor = payload["authenticationInfo"]["principalEmail"]
                send_email(NOTIFICATION_EMAIL, bucket_name, actor)


def make_bucket_private(bucket_name):
    from google.cloud import storage

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    policy = bucket.get_iam_policy()
    print(f"{bucket_name} policy bindings: {policy.bindings}")
    for b in policy.bindings:
        if  "allUsers" in b["members"] or "allAuthenticatedUsers" in b["members"]:
            print("Remove:")
            print(b)
            policy.bindings.remove(b)
    bucket.set_iam_policy(policy)
    print(f"Bucket {bucket_name} has the new policy bindings: {policy.bindings}")


SENDER = os.environ.get("NOTIFICATION_SENDER", "No Reply<noreply@example.com>")
SUBJECT = os.environ.get("NOTIFICATION_SUBJECT", "Bucket violation detected")


def send_email(recipent, name, actor):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    from google.cloud import secretmanager

    # https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
    # Also make sure the Cloud Function service account has permission to read the
    # secret
    client = secretmanager.SecretManagerServiceClient()
    name = client.secret_version_path(PROJECT_ID, "sendgrid-apikey", "latest")
    response = client.access_secret_version(name)
    sendgrid_apikey = response.payload.data.decode("UTF-8")

    BODY_HTML = f"""<html>
    <head></head>
    <body>
      <h2><p>The storage bucket ({name}) changed by {actor} violates 
      the curent secruity policy. </p>
      <p>It has been correct. Please check the activity logs for details.</p>
      <p>Thank you!</p></h2>
    </body>
    </html>
                """
    message = Mail(
        from_email=SENDER, to_emails=recipent, subject=SUBJECT, html_content=BODY_HTML,
    )
    try:
        sg = SendGridAPIClient(sendgrid_apikey)
        response = sg.send(message)
        print(f"Email request sent. Status code: {response.status_code}")
    except Exception as e:
        print(e)
