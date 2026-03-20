# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
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
# limitations under the License

# description: cloud-agent service
# processname: cloud-agent

$VERSION="1.3.0-SNAPSHOT"
$HASH="testhash"

switch ($($args[0])){
  "--version" {
    echo "$VERSION"
    exit 0
  }
  "--hash" {
    echo "$HASH"
    exit 0
  }
}

# Handle spaces in command line arguments properly
$quoted_args=@()

ForEach ($arg in $args)
{
  if($arg.Contains(' '))
  {
    $arg = """" + $arg + """"
  }
  $quoted_args = $quoted_args + @($arg)
}

$args = $quoted_args

$cloud_AGENT="cloud-agent"
$cloud_SVC_NAME = "Cloud Agent"
$current_directory = (Get-Item -Path ".\" -Verbose).FullName
#environment variables used in python, check if they exists, otherwise set them to $current_directory
#and pass to child python process
$Env:PYTHONPATH="$current_directory\sbin;$($Env:PYTHONPATH)"
$Env:PYTHON = "python.exe"

$cloud_LOG_DIR="\var\log\cloud-agent"
$OUTFILE_STDOUT=Join-Path -path $cloud_LOG_DIR -childpath "cloud-agent.stdout"
$OUTFILE_STDERR=Join-Path -path $cloud_LOG_DIR -childpath "cloud-agent.stderr"
$LOGFILE=Join-Path -path $cloud_LOG_DIR -childpath "cloud-agent.log"
$cloud_AGENT_PY_SCRIPT=Join-Path -path $PSScriptRoot -childpath "sbin\service_wrapper.py"
if($cloud_AGENT_PY_SCRIPT.Contains(' '))
{
  $cloud_AGENT_PY_SCRIPT = """" + $cloud_AGENT_PY_SCRIPT + """"
}

$OK=1
$NOTOK=0

$retcode=0

function _exit($code)
{
  $host.SetShouldExit($code)
  exit $code
}

function _detect_python()
{
  if(![boolean]$(Get-Command $Env:PYTHON -ErrorAction SilentlyContinue))
  {
    echo "ERROR: Can not find python.exe in PATH. Add python executable to PATH and try again."
    _exit(1)
  }
}

function _echo([switch]$off)
{
  if($off)
  {
    try
    {
      stop-transcript|out-null
    }
    catch [System.InvalidOperationException]
    {}
  }
  else
  {
    try
    {
      start-transcript|out-null
    }
    catch [System.InvalidOperationException]
    {}
  }
}

Function _pstart_brief($cmd_args)
{
  #start python with -u to make stdout and stderr unbuffered
  $arguments = @("-u",$cloud_AGENT_PY_SCRIPT) + $cmd_args

  $psi = New-Object System.Diagnostics.ProcessStartInfo

  $psi.RedirectStandardError = $True
  $psi.RedirectStandardOutput = $True

  $psi.UseShellExecute = $False

  $psi.FileName = $Env:PYTHON
  $psi.Arguments = $arguments
  #$psi.WindowStyle = WindowStyle.Hidden

  $process = [Diagnostics.Process]::Start($psi)

  $process.WaitForExit()

  Write-Output $process.StandardOutput.ReadToEnd()
}

Function _start($cmd_args)
{
  echo "Starting $cloud_SVC_NAME..."
  _echo -off

  _pstart_brief($cmd_args)

  $cnt = 0
  do
  {
    Start-Sleep -Milliseconds 250
    $svc = Get-Service -Name $cloud_SVC_NAME
    $cnt += 1
    if ($cnt -eq 120)
    {
      echo "$cloud_SVC_NAME still starting...".
      return
    }
  }
  until($svc.status -eq "Running")

  echo "$cloud_SVC_NAME is running"
}

Function _pstart($cmd_args)
{
  New-Item -ItemType Directory -Force -Path $cloud_LOG_DIR | Out-Null
  $arguments = @($cloud_AGENT_PY_SCRIPT) + $cmd_args
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo.UseShellExecute = $false
  $p.StartInfo.FileName = $Env:PYTHON
  $p.StartInfo.Arguments = $arguments
  [void]$p.Start();

  echo "Verifying $cloud_AGENT process status..."
  if (!$p){
    echo "ERROR: $cloud_AGENT start failed"
    $host.SetShouldExit(-1)
    exit
  }
  echo "Agent log at: $LOGFILE"

  $p.WaitForExit()
}

Function _pstart_ioredir($cmd_args)
{
  New-Item -ItemType Directory -Force -Path $cloud_LOG_DIR | Out-Null

  #start python with -u to make stdout and stderr unbuffered
  $arguments = @("-u",$cloud_AGENT_PY_SCRIPT) + $cmd_args
  $process = Start-Process -FilePath $Env:PYTHON -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardError $OUTFILE_STDERR -RedirectStandardOutput $OUTFILE_STDOUT -PassThru
  echo "Verifying $cloud_AGENT process status..."
  if (!$process){
    echo "ERROR: $cloud_AGENT start failed"
    $host.SetShouldExit(-1)
    exit
  }
  echo "Agent stdout at: $OUTFILE_STDOUT"
  echo "Agent stderr at: $OUTFILE_STDERR"
  echo "Agent log at: $LOGFILE"

  $process.WaitForExit()
}

Function _stop($cmd_args){
  echo "Stopping $cloud_SVC_NAME..."

  _pstart_brief($cmd_args)

  $cnt = 0
  do
  {
    Start-Sleep -Milliseconds 250
    $svc = Get-Service -Name $cloud_SVC_NAME
    $cnt += 1
    if ($cnt -eq 40)
    {
      echo "$cloud_SVC_NAME still stopping...".
      return
    }
  }
  until($svc.status -eq "Stopped")

  echo "$cloud_SVC_NAME is stopped"
}

Function _status($cmd_args){
  echo "Getting $cloud_SVC_NAME status..."

  _pstart_brief($cmd_args)
}

# check for python before any action
_detect_python
switch ($($args[0])){
  "start"
  {
    _start $args
  }
  "debug"
  {
    echo "Starting cloud-agent"
    _pstart_ioredir $args
    echo "Cloud Agent finished"
  }
  "stop" {_stop $args}
  "restart"
  {
    _stop @("stop")
    _start @("start")
  }
  "status" {_status $args}
  "setup"
  {
    echo "Installing cloud-agent"
    _pstart $args
    echo "Cloud Agent installation finished"
  }
  default
  {
    echo "Usage: cloud-agent {start|stop|restart|setup|status} [options]"
    echo "Use cloud-agent <action> --help to get details on options available."
    echo "Or, simply invoke cloud-agent.py --help to print the options."
    $retcode=1
  }
}

$host.SetShouldExit($retcode)
exit
