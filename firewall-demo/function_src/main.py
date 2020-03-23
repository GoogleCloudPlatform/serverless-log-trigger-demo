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
import ipaddress
import json
import os
import time

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

PROJECT_ID = os.environ.get("PROJECT_ID")
NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL")
MONITOR_TYPES = [
    "compute.firewalls.patch",
    "compute.firewalls.insert",
    "compute.firewalls.update",
]
WHITE_LISTS = []
for n, v in os.environ.items():
    name = n.upper()
    if name.startswith("FIREWALL_WHITE_LIST"):
        # Format: protocol:CIDR:ports
        parts = v.split(":")
        if len(parts) == 2:
            parts.append(["0-65535"])
        else:
            WHITE_LISTS.append(
                {
                    "protocol": parts[0],
                    "net": ipaddress.IPv4Network(parts[1]),
                    "ports": parts[2].split(","),
                }
            )


def process_firewall_log(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
       event (dict): Event payload.
       context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")

    log_data = json.loads(pubsub_message)
    payload = log_data["jsonPayload"]
    if (
        payload["resource"]["type"] == "firewall"
        and payload["event_type"] == "GCE_OPERATION_DONE"
        and payload["event_subtype"] in MONITOR_TYPES
    ):

        firewall_name = payload["resource"]["name"]
        actor = str(payload["actor"])

        # Build a representation of the Cloud Compute API.
        # Disable caching to avoid bogus error messages
        compute = discovery.build("compute", "v1", cache_discovery=False, cache=None)

        result = (
            compute.firewalls()
            .get(project=PROJECT_ID, firewall=firewall_name)
            .execute()
        )

        print(f"Firewall rule ({firewall_name}) details:")
        print(result)

        if result["direction"] != "INGRESS":
            print("Only ingress rules are checked. Exit.")
            return

        if is_invalid_firewall_rule(result):
            delete_firewall_rule(compute, firewall_name)
            if NOTIFICATION_EMAIL:
                send_email(NOTIFICATION_EMAIL, firewall_name, actor)

    else:
        print(f"Ignore event type:{payload['event_subtype']}")


def check_ports(white_ports, source_ports):
    for sp in source_ports:
        for wp in white_ports:
            if sp == wp:
                break
            if "-" in wp:
                (start, end) = wp.split("-")
                sp_int = int(sp)
                if sp_int >= int(start) and sp_int <= int(end):
                    break
        else:
            return False
    return True


def is_valid_item(white_item, source_subnet, proto_ports):
    source_proto = proto_ports.get(white_item["protocol"])
    if (
        source_proto
        and white_item["net"].supernet_of(source_subnet)
        and check_ports(white_item["ports"], proto_ports.get(white_item["protocol"]))
    ):
        return True
    return False


def is_invalid_firewall_rule(firewall_data):
    # Firewall "allowed" field example:
    # "[{'IPProtocol': 'tcp', 'ports': ['22', '3389', '8000', '8081']}]"
    proto_ports = {}
    for i in firewall_data["allowed"]:
        proto_ports[i["IPProtocol"]] = i.get("ports", "0-66535")

    for source_range in firewall_data["sourceRanges"]:
        source_subnet = ipaddress.IPv4Network(source_range)
        # Need 0.0.0.0/0 here since the ipaddress lib
        # doesn't consider it as a legit public network
        if source_range == "0.0.0.0/0" or not source_subnet.is_private:
            if any([is_valid_item(x, source_subnet, proto_ports) for x in WHITE_LISTS]):
                print(f"Valid IP range {source_range} for the protocols and ports")
            else:
                print(f"Invalid IP range {source_range} for the protocols and ports")
                return True

    return False


def delete_firewall_rule(compute, name):
    result = compute.firewalls().delete(project=PROJECT_ID, firewall=name).execute()
    wait_for_operation(compute, result["name"])
    print(f"Firewall rule {name} has been deleted")


def wait_for_operation(compute, operation_name):
    print("Waiting for operation to finish...")
    while True:
        result = (
            compute.globalOperations()
            .get(project=PROJECT_ID, operation=operation_name)
            .execute()
        )
        if result["status"] == "DONE":
            print("deletiong is done.")
            if "error" in result:
                raise Exception(result["error"])
            return True

        time.sleep(1)


SENDER = os.environ.get("NOTIFICATION_SENDER", "No Reply<noreply@example.com>")
SUBJECT = os.environ.get("NOTIFICATION_SUBJECT", "Firewall violation detected")


def send_email(recipent, firewall_name, actor):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    from google.cloud import secretmanager

    # https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
    # Also make sure the Cloud Function service account has permissio to read the
    # secret
    client = secretmanager.SecretManagerServiceClient()
    name = client.secret_version_path(PROJECT_ID, "sendgrid-apikey", "latest")
    response = client.access_secret_version(name)
    sendgrid_apikey = response.payload.data.decode("UTF-8")

    BODY_HTML = f"""<html>
    <head></head>
    <body>
      <h2><p>The firewall rule({firewall_name}) changed by {actor} violates 
      the curent secruity policy. </p>
      <p>Therefore, it has been removed.</p>
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
