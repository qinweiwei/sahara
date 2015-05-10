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

import flask
from oslo.config import cfg
import six
import stevedore
from werkzeug import exceptions as werkzeug_exceptions

from sahara.api import acl
from sahara.api.middleware import auth_valid
from sahara.api.middleware import log_exchange
from sahara.api import v10 as api_v10
from sahara.api import v11 as api_v11
from sahara import config
from sahara import context
from sahara.i18n import _LI
from sahara.i18n import _LW
from sahara.openstack.common import log
from sahara.plugins import base as plugins_base
from sahara.service import api as service_api
from sahara.service.edp import api as edp_api
from sahara.service import ops as service_ops
from sahara.service import periodic
from sahara.utils import api as api_utils
from sahara.utils import remote
from sahara.utils import rpc as messaging


LOG = log.getLogger(__name__)


opts = [
    cfg.StrOpt('os_region_name',
               help='Region name used to get services endpoints.'),
    cfg.StrOpt('infrastructure_engine',
               default='direct',
               help='An engine which will be used to provision '
                    'infrastructure for Hadoop cluster.'),
    cfg.StrOpt('remote',
               default='ssh',
               help='A method for Sahara to execute commands '
                    'on VMs.')
]

CONF = cfg.CONF
CONF.register_opts(opts)


def setup_common(possible_topdir, service_name):
    dev_conf = os.path.join(possible_topdir,
                            'etc',
                            'sahara',
                            'sahara.conf')
    config_files = None
    if os.path.exists(dev_conf):
        config_files = [dev_conf]

    config.parse_configs(config_files)
    log.setup("sahara")

    LOG.info(_LI('Starting Sahara %s'), service_name)

    messaging.setup()

    if service_name != 'all-in-one':
        LOG.warn(
            _LW("Distributed mode is in the alpha state, it's recommended to "
                "use all-in-one mode by running 'sahara-all' binary."))

    plugins_base.setup_plugins()


def setup_sahara_api(mode):
    ops = _get_ops_driver(mode)

    service_api.setup_service_api(ops)
    edp_api.setup_edp_api(ops)


def setup_sahara_engine():
    periodic.setup()

    engine = _get_infrastructure_engine()
    service_ops.setup_ops(engine)

    remote_driver = _get_remote_driver()
    remote.setup_remote(remote_driver, engine)


def make_app():
    """App builder (wsgi)

    Entry point for Sahara REST API server
    """
    app = flask.Flask('sahara.api')

    @app.route('/', methods=['GET'])
    def version_list():
        context.set_ctx(None)
        return api_utils.render({
            "versions": [
                {"id": "v1.0", "status": "CURRENT"}
            ]
        })

    @app.teardown_request
    def teardown_request(_ex=None):
        context.set_ctx(None)

    app.register_blueprint(api_v10.rest, url_prefix='/v1.0')
    app.register_blueprint(api_v10.rest, url_prefix='/v1.1')
    app.register_blueprint(api_v11.rest, url_prefix='/v1.1')

    def make_json_error(ex):
        status_code = (ex.code
                       if isinstance(ex, werkzeug_exceptions.HTTPException)
                       else 500)
        description = (ex.description
                       if isinstance(ex, werkzeug_exceptions.HTTPException)
                       else str(ex))
        return api_utils.render({'error': status_code,
                                 'error_message': description},
                                status=status_code)

    for code in six.iterkeys(werkzeug_exceptions.default_exceptions):
        app.error_handler_spec[None][code] = make_json_error

    if CONF.debug and not CONF.log_exchange:
        LOG.debug('Logging of request/response exchange could be enabled using'
                  ' flag --log-exchange')

    if CONF.log_exchange:
        app.wsgi_app = log_exchange.LogExchange.factory(CONF)(app.wsgi_app)

    app.wsgi_app = auth_valid.wrap(app.wsgi_app)
    app.wsgi_app = acl.wrap(app.wsgi_app, CONF)

    return app


def _load_driver(namespace, name):
    extension_manager = stevedore.DriverManager(
        namespace=namespace,
        name=name,
        invoke_on_load=True
    )

    return extension_manager.driver


def _get_infrastructure_engine():
    """Import and return one of sahara.service.*_engine.py modules."""

    LOG.info(_LI("Loading '%s' infrastructure engine"),
             CONF.infrastructure_engine)

    return _load_driver('sahara.infrastructure.engine',
                        CONF.infrastructure_engine)


def _get_remote_driver():
    LOG.info(_LI("Loading '%s' remote"), CONF.remote)

    return _load_driver('sahara.remote', CONF.remote)


def _get_ops_driver(driver_name):
    LOG.info(_LI("Loading '%s' ops"), driver_name)

    return _load_driver('sahara.run.mode', driver_name)
