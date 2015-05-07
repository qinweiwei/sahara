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

import os
import sys

from keystoneclient.v2_0 import Client as keystone_client
from oslo.config import cfg


possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                                os.pardir,
                                                os.pardir))
if os.path.exists(os.path.join(possible_topdir,
                               'sahara',
                               '__init__.py')):
    sys.path.insert(0, possible_topdir)

cli_opts = [
    cfg.StrOpt('username', default='',
               help='set username'),
    cfg.StrOpt('password', default='',
               help='set password'),
    cfg.StrOpt('tenant', default='',
               help='set tenant'),
]

CONF = cfg.CONF
CONF.import_opt('os_admin_username', 'sahara.main')
CONF.import_opt('os_admin_password', 'sahara.main')
CONF.import_opt('os_admin_tenant_name', 'sahara.main')
CONF.register_cli_opts(cli_opts)


def main():
    dev_conf = os.path.join(possible_topdir,
                            'etc',
                            'sahara',
                            'sahara.conf')
    config_files = None
    if os.path.exists(dev_conf):
        config_files = [dev_conf]

    CONF(sys.argv[1:], project='get_auth_token',
         default_config_files=config_files)

    user = CONF.username or CONF.os_admin_username
    password = CONF.password or CONF.os_admin_password
    tenant = CONF.tenant or CONF.os_admin_tenant_name

    protocol = CONF.os_auth_protocol
    host = CONF.os_auth_host
    port = CONF.os_auth_port

    auth_url = "%s://%s:%s/v2.0/" % (protocol, host, port)

    print "User: %s" % user
    print "Password: %s" % password
    print "Tenant: %s" % tenant
    print "Auth URL: %s" % auth_url

    keystone = keystone_client(
        username=user,
        password=password,
        tenant_name=tenant,
        auth_url=auth_url
    )

    result = keystone.authenticate()

    print "Auth succeed: %s" % result
    print "Auth token: %s" % keystone.auth_token
    print "Tenant [%s] id: %s" % (tenant, keystone.tenant_id)


if __name__ == "__main__":
    main()
