# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

import sahara.exceptions as ex
from sahara.i18n import _
import sahara.plugins.base as plugin_base
import sahara.service.api as api
from sahara.service import ops
import sahara.service.validations.base as b
import sahara.service.validations.cluster_templates as cl_t

#CONF = cfg.CONF
CLUSTER_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_transient": {
            "type": "boolean"
        }
    },
    "additionalProperties": False,
    "anyOf": [
        {
            "required": ["is_transient"]
        }
    ]

}

def check_cluster_update(data, cluster_id, **kwargs):
    cluster = api.get_cluster(id=cluster_id)
    
    if cluster.status != 'Active':
        raise ex.InvalidException(
            _("Cluster cannot be scaled not in 'Active' status. "
              "Cluster status: %s") % cluster.status)
    if cluster.is_transient == data['is_transient']:
        raise ex.InvalidException(
            _(" The is_transient is same , so do not need to update"))

