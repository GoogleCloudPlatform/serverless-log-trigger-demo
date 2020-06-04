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
import uuid
from google.cloud import firestore
from google.cloud import monitoring_v3

# Use the function project id if there is no other project id passed in
PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
CUSTOM_METRIC_NAME = os.environ.get("CUSTOM_METRIC_NAME", "myapp-trace-metric")
DB_CLIENT = firestore.Client()
APP_COLLECTION = "app"


def get_epoch_time(time_str):
    from datetime import datetime

    utc_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    return (utc_time - datetime(1970, 1, 1)).total_seconds()


def store_data(payload):
    global DB_CLIENT
    time_diff = None

    if not DB_CLIENT:
        DB_CLIENT = firestore.Client()
    transaction = DB_CLIENT.transaction()
    id = payload.get("id")
    doc_ref = DB_CLIENT.collection(APP_COLLECTION).document(id)

    # Make it transactional since we cannot be sure which log entry arrives first
    @firestore.transactional
    def update_in_transaction(transaction, doc_ref, payload):
        time_diff = None

        snapshot = doc_ref.get(transaction=transaction)
        first_timestamp = None
        last_timestamp = None
        first = None
        last = None
        if snapshot.get("first"):
            first_timestamp = snapshot.get("first_timestamp")
            first = snapshot.get("first")
        elif payload.get("first"):
            first_timestamp = payload.get("timestamp")
            first = payload.get("first")

        if snapshot.get("last"):
            last_timestamp = snapshot.get("last_timestamp")
            last = snapshot.get("last")
        elif payload.get("last"):
            last_timestamp = payload.get("timestamp")
            last = payload.get("last")

        if first_timestamp and last_timestamp:
            time_diff = get_epoch_time(last_timestamp) - get_epoch_time(first_timestamp)
        print(time_diff)
        transaction.set(
            doc_ref,
            {
                u"producer": payload.get("producer"),
                u"methodName": payload.get("methodName"),
                u"first_timestamp": first_timestamp,
                u"last_timestamp": last_timestamp,
                u"first": first,
                u"last": last,
            },
        )

        return time_diff

    return update_in_transaction(transaction, doc_ref, payload)


def send_metric(time_difference, method_label):
    client = monitoring_v3.MetricServiceClient()
    project_name = client.project_path(PROJECT_ID)

    series = monitoring_v3.types.TimeSeries()
    series.metric.type = "custom.googleapis.com/" + CUSTOM_METRIC_NAME
    # Available resource types: https://cloud.google.com/monitoring/api/resources
    series.resource.type = "generic_task"
    series.resource.labels["project_id"] = PROJECT_ID
    # Adjust the lable values as needed
    series.resource.labels["location"] = "global"
    series.resource.labels["namespace"] = "default"
    series.resource.labels["job"] = method_label
    series.resource.labels["task_id"] = str(uuid.uuid4())

    point = series.points.add()
    point.value.double_value = time_difference
    now = time.time()
    point.interval.end_time.seconds = int(now)
    point.interval.end_time.nanos = int(
        (now - point.interval.end_time.seconds) * 10 ** 9
    )
    client.create_time_series(project_name, [series])


def process_app_log(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
       event (dict): Event payload.
       context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")

    log_data = json.loads(pubsub_message)
    print(log_data)
    payload = None
    try:
        if "protoPayload" in log_data:
            # If there is a protoPayload, we assume it's an entry from the audit log
            protoPayload = log_data["protoPayload"]
            payload = protoPayload["operation"].copy()
            payload["methodName"] = log_data["methodName"]
            payload["timestamp"] = log_data["timestamp"]

        elif "jsonPayload" in log_data:
            # Assuming the log entry has the fields we need, we just pass it over
            payload = log_data["jsonPayload"]

        if payload:
            time_difference = store_data(payload)
            if time_difference:
                send_metric(time_difference, payload["methodName"])
    except Exception as e:
        print(e)
