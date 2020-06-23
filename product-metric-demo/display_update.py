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

import threading
import time
import os
from google.cloud import firestore_v1

db = firestore_v1.Client()

# Create an Event for notifying main thread.
callback_done = threading.Event()

# Create a callback on_snapshot function to capture changes
def on_snapshot(doc_snapshot, changes, read_time):
    os.system('clear')
    for doc in doc_snapshot:    
        print(f'Product id: {doc.id} {doc.to_dict()}')
        
    callback_done.set()

doc_ref = db.collection(u'app')

# Watch the document
doc_watch = doc_ref.on_snapshot(on_snapshot)

while True:
    time.sleep(1)