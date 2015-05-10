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

import testtools

from sahara.utils import ssh_remote


class TestEscapeQuotes(testtools.TestCase):
    def test_escape_quotes(self):
        s = ssh_remote._escape_quotes('echo "\\"Hello, world!\\""')
        self.assertEqual(s, r'echo \"\\\"Hello, world!\\\"\"')
