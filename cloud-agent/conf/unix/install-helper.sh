# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information rega4rding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


##################################################################
#                      AGENT INSTALL HELPER                      #
##################################################################

# WARNING. Please keep the script POSIX compliant and don't use bash extensions

cloud_UNIT="cloud-agent"
ACTION=$1
cloud_AGENT_ROOT_DIR="/usr/lib/${cloud_UNIT}"
cloud_SERVER_ROOT_DIR="/usr/lib/cloud-server"
COMMON_DIR="${cloud_AGENT_ROOT_DIR}/lib/cloud_commons"
RESOURCE_MANAGEMENT_DIR="${cloud_AGENT_ROOT_DIR}/lib/resource_management"
JINJA_DIR="${cloud_AGENT_ROOT_DIR}/lib/cloud_jinja2"
SIMPLEJSON_DIR="${cloud_AGENT_ROOT_DIR}/lib/cloud_simplejson"
OLD_OLD_COMMON_DIR="${cloud_AGENT_ROOT_DIR}/lib/common_functions"
cloud_AGENT="${cloud_AGENT_ROOT_DIR}/lib/cloud_agent"
PYTHON_WRAPER_TARGET="/usr/bin/cloud-python-wrap"
cloud_AGENT_VAR="/var/lib/${cloud_UNIT}"
cloud_AGENT_BINARY="/etc/init.d/${cloud_UNIT}"
cloud_AGENT_BINARY_SYMLINK="/usr/sbin/${cloud_UNIT}"
cloud_ENV_RPMSAVE="/var/lib/${cloud_UNIT}/cloud-env.sh.rpmsave"
cloud_HELPER="/var/lib/cloud-agent/install-helper.sh.orig"

LOG_FILE=/dev/null

CLEANUP_MODULES="resource_management;cloud_commons;cloud_agent;cloud_ws4py;cloud_stomp;cloud_jinja2;cloud_simplejson"

OLD_COMMON_DIR="/usr/lib/python2.6/site-packages/cloud_commons"
OLD_RESOURCE_MANAGEMENT_DIR="/usr/lib/python2.6/site-packages/resource_management"
OLD_JINJA_DIR="/usr/lib/python2.6/site-packages/cloud_jinja2"
OLD_SIMPLEJSON_DIR="/usr/lib/python2.6/site-packages/cloud_simplejson"
OLD_cloud_AGENT_DIR="/usr/lib/python2.6/site-packages/cloud_agent"


resolve_log_file(){
 local log_dir=/var/log/${cloud_UNIT}
 local log_file="${log_dir}/${cloud_UNIT}-pkgmgr.log"

 if [ ! -d "${log_dir}" ]; then
   mkdir "${log_dir}" 1>/dev/null 2>&1
 fi

 if [ -d "${log_dir}" ]; then
   touch ${log_file} 1>/dev/null 2>&1
   if [ -f "${log_file}" ]; then
    LOG_FILE="${log_file}"
   fi
 fi

 echo "--> Install-helper custom action log started at $(date '+%d/%m/%y %H:%M') for '${ACTION}'" 1>>${LOG_FILE} 2>&1
}

clean_pyc_files(){
  # cleaning old *.pyc files
  local lib_dir="${cloud_AGENT_ROOT_DIR}/lib"

  echo ${CLEANUP_MODULES} | tr ';' '\n' | while read item; do
    local item="${lib_dir}/${item}"
    echo "Cleaning pyc files from ${item}..."
    if [ -d "${item}" ]; then
      find ${item:?} -name *.pyc -exec rm {} \; 1>>${LOG_FILE} 2>&1
    else
      echo "Skipping ${item} pyc cleaning, as package not existing"
    fi
  done
}

remove_cloud_unit_dir(){
  # removing empty dirs, which left after cleaning pyc files

  find "${cloud_AGENT_ROOT_DIR}" -type d | tac | while read item; do
    echo "Removing empty dir ${item}..."
    rmdir --ignore-fail-on-non-empty ${item} 1>/dev/null 2>&1
  done

  rm -rf ${cloud_HELPER}
  find "${cloud_AGENT_VAR}" -type d | tac | while read item; do
    echo "Removing empty dir ${item}..."
    rmdir --ignore-fail-on-non-empty ${item} 1>/dev/null 2>&1
  done
}

remove_autostart(){
  which chkconfig
  if [ "$?" -eq 0 ] ; then
    chkconfig --list | grep cloud-server && chkconfig --del cloud-agent
  fi
  which update-rc.d
  if [ "$?" -eq 0 ] ; then
    update-rc.d -f cloud-agent remove
  fi
}

install_autostart(){
  which chkconfig 1>>${LOG_FILE} 2>&1
  if [ "$?" -eq 0 ] ; then
    chkconfig --add cloud-agent
  fi
  which update-rc.d 1>>${LOG_FILE} 2>&1
  if [ "$?" -eq 0 ] ; then
    update-rc.d cloud-agent defaults
  fi
}

locate_python(){
  local python_binaries="/usr/bin/python;/usr/bin/python3;/usr/bin/python3.9"

  echo ${python_binaries}| tr ';' '\n' | while read python_binary; do
    ${python_binary} -c "import sys ; ver = sys.version_info ; sys.exit(not (ver >= (3,0)))" 1>>${LOG_FILE} 2>/dev/null

    if [ $? -eq 0 ]; then
      echo "${python_binary}"
      break
    fi
  done
}

do_install(){
  if [ -d "/etc/cloud-agent/conf.save" ]; then
    cp -f /etc/cloud-agent/conf.save/* /etc/cloud-agent/conf
    mv /etc/cloud-agent/conf.save /etc/cloud-agent/conf_$(date '+%d_%m_%y_%H_%M').save
  fi

  # these symlinks (or directories) where created in cloud releases prior to cloud-2.6.2. Do clean up.   
  rm -rf "${OLD_COMMON_DIR}" "${OLD_RESOURCE_MANAGEMENT_DIR}" "${OLD_JINJA_DIR}" "${OLD_SIMPLEJSON_DIR}" "${OLD_OLD_COMMON_DIR}" "${OLD_cloud_AGENT_DIR}"

  # setting up /usr/sbin/cloud-agent symlink
  rm -f "${cloud_AGENT_BINARY_SYMLINK}"
  ln -s "${cloud_AGENT_BINARY}" "${cloud_AGENT_BINARY_SYMLINK}"

  # on nano Ubuntu, when umask=027 those folders are created without 'x' bit for 'others'.
  # which causes failures when hadoop users try to access tmp_dir
  chmod a+x ${cloud_AGENT_VAR}

  chmod 1777 ${cloud_AGENT_VAR}/tmp
  chmod 700 ${cloud_AGENT_VAR}/keys
  chmod 700 ${cloud_AGENT_VAR}/data

  install_autostart 1>>${LOG_FILE} 2>&1

  # remove old python wrapper
  rm -f "${PYTHON_WRAPER_TARGET}"

  local cloud_python=$(locate_python)
  local bak=/etc/cloud-agent/conf/cloud-agent.ini.old
  local orig=/etc/cloud-agent/conf/cloud-agent.ini
  local upgrade_agent_configs_script=/var/lib/cloud-agent/upgrade_agent_configs.py

  if [ -z "${cloud_python}" ] ; then
    >&2 echo "Cannot detect python for Cloud to use. Please manually set ${PYTHON_WRAPER_TARGET} link to point to correct python binary"
    >&2 echo "Cannot upgrade agent configs because python for Cloud is not configured. The old config file is saved as ${bak} . Execution of ${upgrade_agent_configs_script} was skipped."
  else
    ln -s "${cloud_python}" "${PYTHON_WRAPER_TARGET}"

    if [ -f ${bak} ]; then
      if [ -f "${upgrade_agent_configs_script}" ]; then
        ${upgrade_agent_configs_script}
      fi
      mv ${bak} ${bak}_$(date '+%d_%m_%y_%H_%M').save
    fi
  fi

  if [ -f "${cloud_ENV_RPMSAVE}" ] ; then
    PYTHON_PATH_LINE="export PYTHONPATH=${cloud_AGENT_ROOT_DIR}/lib:\$\{PYTHONPATH\}"
    grep "^${PYTHON_PATH_LINE}\$" "${cloud_ENV_RPMSAVE}" >>${LOG_FILE}
    if [ $? -ne 0 ] ; then
      echo -e "\n${PYTHON_PATH_LINE}" 1>>${cloud_ENV_RPMSAVE}
    fi
  fi
}

copy_helper(){
  cp -f /var/lib/cloud-agent/install-helper.sh ${cloud_HELPER} 1>/dev/null 2>&1
}

do_remove(){
  /usr/sbin/cloud-agent stop 1>>${LOG_FILE} 2>&1

  rm -f "${cloud_AGENT_BINARY_SYMLINK}" 1>>${LOG_FILE} 2>&1

  if [ -d "/etc/cloud-agent/conf.save" ]; then
    mv /etc/cloud-agent/conf.save /etc/cloud-agent/conf_$(date '+%d_%m_%y_%H_%M').save
  fi
  # first step / label: config_backup
  cp -rf /etc/cloud-agent/conf /etc/cloud-agent/conf.save

  remove_autostart 1>>${LOG_FILE} 2>&1
  copy_helper 1>>${LOG_FILE} 2>&1
}

do_cleanup(){
  # do_cleanup is a function, which called after do_remove stage and is supposed to be save place to
  # remove obsolete files generated by application activity

  clean_pyc_files 1>>${LOG_FILE} 2>&1

  # second step / label: config_backup
  rm -rf /etc/cloud-agent/conf

  if [ ! -d "${cloud_SERVER_ROOT_DIR}" ]; then
    echo "Removing ${PYTHON_WRAPER_TARGET} ..." 1>>${LOG_FILE} 2>&1
    rm -f ${PYTHON_WRAPER_TARGET} 1>>${LOG_FILE} 2>&1
  fi

  remove_cloud_unit_dir 1>>${LOG_FILE} 2>&1
}

do_upgrade(){
  do_install
}

do_backup(){
  # ToDo: find a way to move backup logic here from preinstall.sh and preinst scripts
  # ToDo: general problem is that still no files are installed on step, when backup is supposed to be done
  echo ""
}

resolve_log_file

case "${ACTION}" in
  install)
    do_install
    ;;
  remove)
    do_remove
    ;;
  upgrade)
    do_upgrade
    ;;
  cleanup)
    do_cleanup
    ;;
  *)
    echo "Wrong command given"
    ;;
esac
