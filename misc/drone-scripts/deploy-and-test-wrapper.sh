#!/bin/sh
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


# This script sets up the testbed.

usage() {
  echo "$0 <ESX IP> <VM1 IP> <VM2 IP> <Build id>"
  echo "root user will be used for all operations"
  echo "Advisable to setup ssh keys."
  echo "run this script from the root of the repo"
}

if [ $# -lt 3 ]
then
  usage
  exit 1
fi

BUILD_NUMBER=$4

export ESX=$1
export VM1=$2
export VM2=$3

USER=root
. ./misc/scripts/commands.sh
. ./misc/drone-scripts/cleanup.sh
. ./misc/drone-scripts/dump_log.sh

dump_vm_info() {
  set -x
  $SSH $USER@$1 uname -a
  $SSH $USER@$1 docker version
  set +x
}

dump_esx_info() {
  echo
  $SSH $USER@$ESX uname -a
  echo
  $SSH $USER@$ESX vmware -vl
  echo
  $SSH $USER@$ESX df
  echo
  $SSH $USER@$ESX ls -ld /vmfs/volumes/*
  echo
}

dump_logs() {
  log "Info ESX $ESX"
  dump_esx_info $ESX
  log "Info VM1 $VM1"
  dump_vm_info $VM1
  log "Info VM2 $VM2"
  dump_vm_info $VM2
  log "log ESX $ESX"
  dump_log_esx $ESX
  log "Log VM1 $VM1"
  dump_log_vm $VM1
  log "Log VM2 $VM2"
  dump_log_vm $VM2
}

truncate_vm_logs() {
  $SSH $USER@$1 "cat /dev/null > /var/log/docker-volume-vsphere.log"
}

truncate_esx_logs() {
  $SSH $USER@$ESX "cat /dev/null > /var/log/vmware/vmdk_ops.log"
}

log "truncate vm logs"
truncate_vm_logs $VM1
truncate_vm_logs $VM2

log "truncate esx logs"
truncate_esx_logs

log "starting deploy and test"

if make -s deploy-esx deploy-vm testasroot testremote TEST_VOL_NAME=vol.build$BUILD_NUMBER;
then
 dump_logs
 stop_build $VM1 $BUILD_NUMBER
else
  log "Build + Test not successful"
  dump_logs
  stop_build $VM1 $BUILD_NUMBER
  exit 1
fi

if [ $1 == "dump_logs" ]
then
  dump_logs
fi
