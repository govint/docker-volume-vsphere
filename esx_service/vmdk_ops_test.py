#!/usr/bin/env python
# Copyright 2016 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
Tests for basic vmdk Operations

'''

import unittest
import sys
import logging
import glob
import os
import os.path

import vmdk_ops
import log_config
import volume_kv
import vsan_policy
import vsan_info
import vmdk_utils

# will do creation/deletion in this folder:
global path

class VolumeNamingTestCase(unittest.TestCase):
    """Unit test for operations with volume names (volume@datastore)"""

    def test_name_parse(self):
        """checks name parsing and error checks
        'volume[@datastore]' -> volume and datastore"""
        testInfo = [
            #  [ full_name. expected_vol_name, expected_datastore_name,  expected_success? ]
            ["MyVolume123_a_.vol@vsanDatastore_11", "MyVolume123_a_.vol", "vsanDatastore_11", True],
            ["a1@x",                            "a1",                  "x",             True],
            ["a1",                              "a1",                  None,            True],
            ["1",                                "1",                 None,             True],
            ["strange-volume-10@vsan:Datastore",  "strange-volume-10",  "vsan:Datastore",     True],
            ["dashes-and stuff !@datastore ok",  "dashes-and stuff !",  "datastore ok",       True],
            ["no-snaps-please-000001@datastore", None,                 None,            False],
            ["TooLong0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789", None, None, False],
            ["Just100Chars0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567",
                           "Just100Chars0123456789012345678901234567890123456789012345678901234567890123456789012345678901234567", None, True],
            ["Volume.123@dots.dot",              "Volume.123",        "dots.dot",       True],
            ["simple_volume",                    "simple_volume",      None,            True],
        ]
        for unit in testInfo:
            full_name, expected_vol_name, expected_ds_name, expected_result = unit
            try:
                vol, ds = vmdk_ops.parse_vol_name(full_name)
                self.assertTrue(expected_result,
                                "Expected volume name parsing to fail for '{0}'".format(full_name))
                self.assertEqual(vol, expected_vol_name, "Vol name mismatch '{0}' expected '{1}'" \
                                                         .format(vol, expected_vol_name))
                self.assertEqual(vol, expected_vol_name, "Datastore name: '{0}' expected: '{1}'" \
                                                         .format(ds, expected_ds_name))
            except vmdk_ops.ValidationError as ex:
                self.assertFalse(expected_result, "Expected vol name parsing to succeed for '{0}'"
                                 .format(full_name))


class VmdkCreateRemoveTestCase(unittest.TestCase):
    """Unit test for VMDK Create and Remove ops"""

    volName = "vol_UnitTest_Create"
    badOpts = {u'policy': u'good', volume_kv.SIZE: u'12unknown', volume_kv.DISK_ALLOCATION_FORMAT: u'5disk'}
    invalid_access_choice = {volume_kv.ACCESS: u'only-read'}
    invalid_access_opt = {u'acess': u'read-write'}
    valid_access_opt = {volume_kv.ACCESS: 'read-only'}
    name = ""
    vm_name = 'test-vm'

    def setUp(self):
        self.name = vmdk_utils.get_vmdk_path(path, self.volName)
        self.policy_names = ['good', 'impossible']
        self.orig_policy_content = ('(("proportionalCapacity" i0) '
                                     '("hostFailuresToTolerate" i0))')
        self.new_policy_content = '(("hostFailuresToTolerate" i0))'
        for n in self.policy_names:
            vsan_policy.create(n, self.orig_policy_content)

    def tearDown(self):
        vmdk_ops.removeVMDK(self.name)
        self.vmdk = None
        for n in self.policy_names:
            vsan_policy.delete(n)

    def testCreateDelete(self):
        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=self.name,
                                  vol_name=self.volName)
        self.assertEqual(err, None, err)
        self.assertEqual(
            os.path.isfile(self.name), True,
            "VMDK {0} is missing after create.".format(self.name))
        err = vmdk_ops.removeVMDK(self.name)
        self.assertEqual(err, None, err)
        self.assertEqual(
            os.path.isfile(self.name), False,
            "VMDK {0} is still present after delete.".format(self.name))

    def testBadOpts(self):
        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=self.name,
                                  vol_name=self.volName,
                                  opts=self.badOpts)
        logging.info(err)
        self.assertNotEqual(err, None, err)

        err = vmdk_ops.removeVMDK(self.name)
        logging.info(err)
        self.assertNotEqual(err, None, err)

    def testAccessOpts(self):
        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=self.name,
                                  vol_name=self.volName,
                                  opts=self.invalid_access_choice)
        logging.info(err)
        self.assertNotEqual(err, None, err)

        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=self.name,
                                  vol_name=self.volName,
                                  opts=self.invalid_access_opt)
        logging.info(err)
        self.assertNotEqual(err, None, err)

        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=self.name,
                                  vol_name=self.volName,
                                  opts=self.valid_access_opt)
        logging.info(err)
        self.assertEqual(err, None, err)

        err = vmdk_ops.removeVMDK(self.name)
        logging.info(err)
        self.assertEqual(err, None, err)
        
    @unittest.skipIf(not vsan_info.get_vsan_datastore(),
                    "VSAN is not found - skipping vsan_info tests")
    def testPolicyUpdate(self):
        path = vsan_info.get_vsan_dockvols_path()
        vmdk_path = vmdk_utils.get_vmdk_path(path, self.volName)
        err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                  vmdk_path=vmdk_path,
                                  vol_name=self.volName,
                                  opts={'vsan-policy-name': 'good'})
        self.assertEqual(err, None, err)
        self.assertEqual(None, vsan_policy.update('good',
                                                  self.new_policy_content))
        # Setting an identical policy returns an error msg
        self.assertNotEqual(None, vsan_policy.update('good',
                                                     self.new_policy_content))

        backup_policy_file = vsan_policy.backup_policy_filename(self.name)
        #Ensure there is no backup policy file
        self.assertFalse(os.path.isfile(backup_policy_file))

        # Fail to update because of a bad policy, and ensure there is no backup
        self.assertNotEqual(None, vsan_policy.update('good', 'blah'))
        self.assertFalse(os.path.isfile(backup_policy_file))


    @unittest.skipIf(not vsan_info.get_vsan_datastore(),
                    "VSAN is not found - skipping vsan_info tests")
    def testPolicy(self):
        # info for testPolicy
        testInfo = [
            #    size     policy   expected success?
            ["2000kb", "good", True, "zeroedthick"],
            ["14000pb", "good", False, "zeroedthick"],
            ["bad size", "good", False, "eagerzeroedthick"],
            ["100mb", "impossible", True, "eagerzeroedthick"],
            ["100mb", "good", True, "thin"],
        ]
        path = vsan_info.get_vsan_dockvols_path()
        i = 0
        for unit in testInfo:
            vol_name = '{0}{1}'.format(self.volName, i)
            vmdk_path = vmdk_utils.get_vmdk_path(path,vol_name)
            i = i+1
            # create a volume with requests size/policy and check vs expected result
            err = vmdk_ops.createVMDK(vm_name=self.vm_name,
                                      vmdk_path=vmdk_path,
                                      vol_name=vol_name,
                                      opts={volume_kv.VSAN_POLICY_NAME: unit[1],
                                            volume_kv.SIZE: unit[0],
                                            volume_kv.DISK_ALLOCATION_FORMAT: unit[3]})
            self.assertEqual(err == None, unit[2], err)

            # clean up should fail if the created should have failed.
            err = vmdk_ops.removeVMDK(vmdk_path)
            self.assertEqual(err == None, unit[2], err)



class ValidationTestCase(unittest.TestCase):
    """ Test validation of -o options on create """

    @unittest.skipIf(not vsan_info.get_vsan_datastore(),
                     "VSAN is not found - skipping vsan_info tests")

    def setUp(self):
        """ Create a bunch of policies """
        self.policy_names = ['name1', 'name2', 'name3']
        self.policy_content = ('(("proportionalCapacity" i50) '
                               '("hostFailuresToTolerate" i0))')
        self.path = vsan_info.get_vsan_datastore().info.url
        for n in self.policy_names:
            result = vsan_policy.create(n, self.policy_content)
            self.assertEquals(None, result,
                              "failed creating policy %s (%s)" % (n, result))

    def tearDown(self):
        for n in self.policy_names:
            try:
                vsan_policy.delete(n)
            except:
                pass

    def test_success(self):
        sizes = ['2gb', '200tb', '200mb', '5kb']
        sizes.extend([s.upper() for s in sizes])

        for s in sizes:
            for p in self.policy_names:
                for d in volume_kv.VALID_ALLOCATION_FORMATS:
                # An exception should not be raised
                    vmdk_ops.validate_opts({volume_kv.SIZE: s, volume_kv.VSAN_POLICY_NAME: p, volume_kv.DISK_ALLOCATION_FORMAT : d},
                                       self.path)
                    vmdk_ops.validate_opts({volume_kv.SIZE: s}, self.path)
                    vmdk_ops.validate_opts({volume_kv.VSAN_POLICY_NAME: p}, self.path)
                    vmdk_ops.validate_opts({volume_kv.DISK_ALLOCATION_FORMAT: d}, self.path)

    def test_failure(self):
        bad = [{volume_kv.SIZE: '2'}, {volume_kv.VSAN_POLICY_NAME: 'bad-policy'},
        {volume_kv.DISK_ALLOCATION_FORMAT: 'thiN'}, {volume_kv.SIZE: 'mb'}, {'bad-option': '4'}, {'bad-option': 'what',
                                                             volume_kv.SIZE: '4mb'}]
        for opts in bad:
            with self.assertRaises(vmdk_ops.ValidationError):
                vmdk_ops.validate_opts(opts, self.path)


if __name__ == '__main__':
    log_config.configure()
    volume_kv.init()

    # Calculate the path
    paths = glob.glob("/vmfs/volumes/[a-zA-Z]*/dockvols")
    if paths:
        # WARNING: for many datastores with dockvols, this picks up the first
        path = paths[0]
    else:
        # create dir in a datastore (just pick first datastore if needed)
        path = glob.glob("/vmfs/volumes/[a-zA-Z]*")[0] + "/dockvols"
        logging.debug("Directory does not exist - creating %s", path)
        os.makedirs(path)

    logging.info("Directory used in test - %s", path)

    try:
        unittest.main()
    except:
        pass
    finally:
        if not paths:
            logging.debug("Directory clean up - removing  %s", path)
            os.removedirs(path)

        # If the unittest failed, re-raise the error
        raise
