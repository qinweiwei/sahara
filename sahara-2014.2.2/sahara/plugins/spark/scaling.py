# Copyright (c) 2014 Hoang Do, Phuc Vo, P. Michiardi, D. Venzano
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

from oslo.utils import timeutils
import six

from sahara import context
from sahara.i18n import _
from sahara.plugins.general import exceptions as ex
from sahara.plugins.general import utils
from sahara.plugins.spark import config_helper as c_helper
from sahara.plugins.spark import run_scripts as run
from sahara.utils import remote


def decommission_sl(master, inst_to_be_deleted, survived_inst):
    if survived_inst is not None:
        slavenames = []
        for slave in survived_inst:
            slavenames.append(slave.hostname())
        slaves_content = c_helper.generate_spark_slaves_configs(slavenames)
    else:
        slaves_content = "\n"

    cluster = master.node_group.cluster
    sp_home = c_helper.get_config_value("Spark", "Spark home", cluster)
    r_master = remote.get_remote(master)
    run.stop_spark(r_master, sp_home)

    # write new slave file to master
    files = {os.path.join(sp_home, 'conf/slaves'): slaves_content}
    r_master.write_files_to(files)

    # write new slaves file to each survived slave as well
    for i in survived_inst:
        with remote.get_remote(i) as r:
            r.write_files_to(files)

    run.start_spark_master(r_master, sp_home)


def decommission_dn(nn, inst_to_be_deleted, survived_inst):
    with remote.get_remote(nn) as r:
        r.write_file_to('/etc/hadoop/dn.excl',
                        utils.generate_fqdn_host_names(
                            inst_to_be_deleted))
        run.refresh_nodes(remote.get_remote(nn), "dfsadmin")
        context.sleep(3)

        timeout = c_helper.get_decommissioning_timeout(
            nn.node_group.cluster)
        s_time = timeutils.utcnow()
        all_found = False

        while timeutils.delta_seconds(s_time, timeutils.utcnow()) < timeout:
            cmd = r.execute_command(
                "sudo -u hdfs hadoop dfsadmin -report")
            all_found = True
            datanodes_info = parse_dfs_report(cmd[1])
            for i in inst_to_be_deleted:
                for dn in datanodes_info:
                    if (dn["Name"].startswith(i.internal_ip)) and (
                            dn["Decommission Status"] != "Decommissioned"):
                        all_found = False
                        break

            if all_found:
                r.write_files_to({'/etc/hadoop/dn.incl':
                                 utils.
                                 generate_fqdn_host_names(survived_inst),
                                  '/etc/hadoop/dn.excl': "",
                                  })
                break
            context.sleep(3)

        if not all_found:
            ex.DecommissionError(
                _("Cannot finish decommission of cluster %(cluster)s in "
                  "%(seconds)d seconds") %
                {"cluster": nn.node_group.cluster,
                 "seconds": timeout})


def parse_dfs_report(cmd_output):
    report = cmd_output.rstrip().split(os.linesep)
    array = []
    started = False
    for line in report:
        if started:
            array.append(line)
        if line.startswith("Datanodes available"):
            started = True

    res = []
    datanode_info = {}
    for i in six.moves.xrange(0, len(array)):
        if array[i]:
            idx = str.find(array[i], ':')
            name = array[i][0:idx]
            value = array[i][idx + 2:]
            datanode_info[name.strip()] = value.strip()
        if not array[i] and datanode_info:
            res.append(datanode_info)
            datanode_info = {}
    if datanode_info:
        res.append(datanode_info)
    return res
