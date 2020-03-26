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
import six
import time
import uuid
from google.cloud import translate_v2 as translate
from google.cloud import monitoring_v3

# Use the function project id if there is no other project id passed in
PROJECT_ID = os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
TARGET_LANGUAGE = os.environ.get("TARGET_LANGUAGE", "en")
SEARCH_PHRASE = os.environ.get("SEARCH_PHRASE", "Execution error").upper()
CUSTOM_METRIC_NAME = os.environ.get("CUSTOM_METRIC_NAME", "my-error-metric")
TRANSLATE_CLIENT = translate.Client()


def translate_message(text):
    global TRANSLATE_CLIENT
    if not TRANSLATE_CLIENT:
        TRANSLATE_CLIENT = translate.Client()

    if isinstance(text, six.binary_type):
        text = text.decode("utf-8")

    result = TRANSLATE_CLIENT.translate(text, target_language=TARGET_LANGUAGE)

    print(result)
    return result["translatedText"]


def send_metric():
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
    series.resource.labels["job"] = "From cloud function job"
    series.resource.labels["task_id"] = str(uuid.uuid4())

    point = series.points.add()
    point.value.int64_value = 1
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
    message = ""
    if "jsonPayload" in log_data:
        message = log_data["jsonPayload"].get("message")
    else:
        message = log_data["textPayload"].get("textPayload")

    target_message = ""
    if message:
        target_message = translate_message(message)
        print(target_message)
        if SEARCH_PHRASE in target_message.upper():
            send_metric()
