#!/bin/sh

if [ x$1 != x ]
then
  echo  $1
  cd /patrol/Patrol3
  . /patrol/Patrol3/patrolrc.sh

  TARGET_IP=$1
  WARN_VALUE=2000000
  count=1
  while [ $count -le 2 ]
  do
    PatrolCli "user patrol "-------"" "connect ${TARGET_IP} 3181" "execpsl \"set(\\\"/PROCPRES/PatrolAgent/PROCPPMem/value\\\",${WARN_VALUE});\""
    count=$((count+1))
  done
  exit 0
else
  echo "null"
  exit 255
fi
