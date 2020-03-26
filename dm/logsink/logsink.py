# Copyright 2018 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" This template creates a logsink (logging sink). """


def create_pubsub(context, logsink_name):
    """ Create the pubsub destination. """

    properties = context.properties
    project_id = properties.get('destinationProject', properties.get('project', context.env['project']))

    dest_properties = []
    if 'pubsubProperties' in context.properties:
        dest_prop = context.properties['pubsubProperties']
        dest_prop['name'] = context.properties['destinationName']
        dest_prop['project'] = project_id
        access_control = dest_prop.get('accessControl', [])
        access_control.append(
            {
                'role': 'roles/pubsub.admin',
                'members': ['$(ref.' + logsink_name + '.writerIdentity)']
            }
        )

        dest_prop['accessControl'] = access_control
        dest_properties = [
            {
                'name': '{}-pubsub'.format(context.env['name']),
                'type': 'pubsub.py',
                'properties': dest_prop
            },
            {
                'name': '{}-iam-member-pub-sub-policy'.format(context.env['name']),
                'type': 'iam_member.py',
                'properties':
                    {
                        'projectId': project_id,
                        'dependsOn': [logsink_name],
                        'roles': [{
                            'role': 'roles/pubsub.admin',
                            'members': ['$(ref.{}.writerIdentity)'.format(logsink_name)]
                        }]
                    }
            }
        ]

    return dest_properties

def generate_config(context):
    """ Entry point for the deployment resources. """

    properties = context.properties
    name = properties.get('name', context.env['name'])
    project_id = properties.get('project', context.env['project'])

    properties = {
        'name': name,
        'uniqueWriterIdentity': context.properties['uniqueWriterIdentity'],
        'sink': name,
    }

    if 'orgId' in context.properties:
        source_id = str(context.properties.get('orgId'))
        source_type = 'organizations'
        properties['organization'] = str(source_id)
    elif 'billingAccountId' in context.properties:
        source_id = context.properties.get('billingAccountId')
        source_type = 'billingAccounts'
        del properties['sink']
    elif 'folderId' in context.properties:
        source_id = str(context.properties.get('folderId'))
        source_type = 'folders'
        properties['folder'] = str(source_id)
    elif 'projectId' in context.properties:
        source_id = context.properties.get('projectId')
        source_type = 'projects'

    properties['parent'] = '{}/{}'.format(source_type, source_id)

    dest_properties = []
    if context.properties['destinationType'] == 'pubsub':
        dest_properties = create_pubsub(context, name)
        destination = 'pubsub.googleapis.com/projects/{}/topics/{}'.format(
            project_id,
            context.properties['destinationName']
        )

    properties['destination'] = destination

    sink_filter = context.properties.get('filter')
    if sink_filter:
        properties['filter'] = sink_filter

    # https://cloud.google.com/logging/docs/reference/v2/rest/v2/folders.sinks
    # https://cloud.google.com/logging/docs/reference/v2/rest/v2/billingAccounts.sinks
    # https://cloud.google.com/logging/docs/reference/v2/rest/v2/projects.sinks
    # https://cloud.google.com/logging/docs/reference/v2/rest/v2/organizations.sinks
    base_type = 'gcp-types/logging-v2:'
    resource = {
        'name': context.env['name'],
        'type': base_type + source_type + '.sinks',
        'properties': properties
    }
    resources = [resource]

    if dest_properties:
        resources.extend(dest_properties)

    return {
        'resources':
            resources,
        'outputs':
            [
                {
                    'name': 'writerIdentity',
                    'value': '$(ref.{}.writerIdentity)'.format(context.env['name'])
                }
            ]
    }
