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
import ast
from google.cloud import firestore
from google.cloud import monitoring_v3

# Use the function project id if there is no other project id passed in
PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
IS_SAVE_TO_FIRESTORE = os.environ.get("IS_SAVE_TO_FIRESTORE", "false")
CUSTOM_METRIC_PREFIX = os.environ.get("CUSTOM_METRIC_PREFIX", "my-product")
DB_CLIENT = firestore.Client()
MONITORING_CLIENT = monitoring_v3.MetricServiceClient()
APP_COLLECTION = "app"


def store_data(product):
    global DB_CLIENT

    if not DB_CLIENT:
        DB_CLIENT = firestore.Client()

    doc_ref = DB_CLIENT.collection(APP_COLLECTION).document(product)
    doc_ref.set(
        {
            u"recomended_times": firestore.Increment(1),
        }, merge=True
    )

def send_metric(product):
    global MONITORING_CLIENT
    if not MONITORING_CLIENT:
        MONITORING_CLIENT = monitoring_v3.MetricServiceClient()

    project_name = MONITORING_CLIENT.project_path(PROJECT_ID)

    series = monitoring_v3.types.TimeSeries()
    series.metric.type = f"custom.googleapis.com/{CUSTOM_METRIC_PREFIX}-{product}"
    # Available resource types: https://cloud.google.com/monitoring/api/resources
    series.resource.type = "generic_task"
    series.resource.labels["project_id"] = PROJECT_ID
    # Adjust the lable values as needed
    series.resource.labels["location"] = "global"
    series.resource.labels["namespace"] = "default"
    series.resource.labels["job"] = "app-" + product
    series.resource.labels["task_id"] = str(uuid.uuid4())

    point = series.points.add()
    point.value.int64_value = 1
    now = time.time()
    point.interval.end_time.seconds = int(now)
    point.interval.end_time.nanos = int(
        (now - point.interval.end_time.seconds) * 10 ** 9
    )
    MONITORING_CLIENT.create_time_series(project_name, [series])


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
        if "jsonPayload" in log_data:
            jsonPayload = log_data["jsonPayload"]
            payload_msg = jsonPayload["message"]

        if payload_msg:
            # typical message in log is :
            # "[Recv ListRecommendations] product_ids=[u'66VCHSJNUP', ..., u'1YMWWN1N4O']"
            product_str = payload_msg.replace("[Recv ListRecommendations] product_ids=", "")
            product_list = ast.literal_eval(product_str)
            for p in product_list:
                # send the metric to Cloud Monitoring
                # if you send too much data simultaneously you may encounter '429 Quota exceedd'
                # if that happens, you could save the data to a database first, then aggregate 
                # the data and write the metric
                send_metric(p)

                # store the total recommended numbers of the products into Firestore
                if IS_SAVE_TO_FIRESTORE.lower() in ("yes", "true", "t", "1"):
                    store_data(p)
                          
    except Exception as e:
        print(e)
