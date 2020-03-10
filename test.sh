#!/bin/bash
#===========================================================
# Example workflow - Automating backup of NetApp snapshot
#===========================================================

#-------------------
# User variables
#-------------------

# NetApp IP address or hostname. Used for HTTPS connections.
NA_IP=<REDACTED>

# NetApp vserver username and password
NA_USER=<REDACTED>
NA_PASS=<REDACTED>

# Name of the volume
VOLUME_NAME=ppz_qlik_data

# Name of the LUN to map
LUN_NAME=data01

# Name of NetApp initiator group for mapping the LUN to the host
LUN_IG=ppz_backup

# Base name for the snapshot. The final name is built using this value and concatenatig the unix time value
SNAPSHOT_BASENAME=snap

# Snapshot name suffix after succesfull backup.
BACKUP_SUFFIX=.backup


#-------------------
# System variables
#-------------------

PY_BIN=python3
SCRIPT_ARGS="--na $NA_IP --user $NA_USER --pass $NA_PASS"
CMD="${PY_BIN} na_helpers_rest.py ${SCRIPT_ARGS}"

#-------------------
# START
#-------------------

echo '-----------------------------------------------------'

echo '1) Create snap for volume'
$CMD --snaplist --vol $VOLUME_NAME
$CMD --snapcreate --vol $VOLUME_NAME --base_name $SNAPSHOT_BASENAME
$CMD --snaplist --vol $VOLUME_NAME

echo '-----------------------------------------------------'

echo '2) rotate snapshots'
$CMD --snaprotate --vol $VOLUME_NAME --retention 5
$CMD --snaplist --vol $VOLUME_NAME

echo '-----------------------------------------------------'

echo '3) create clone out of latest snapshot'
last_snap=`$CMD --snaplist --vol $VOLUME_NAME|egrep ^${SNAPSHOT_BASENAME}|grep -v ${BACKUP_SUFFIX}|head -1|cut -d' ' -f1`
$CMD --clonecreate --vol $VOLUME_NAME --snap $last_snap --clone ${VOLUME_NAME}_clone

echo '-----------------------------------------------------'

echo '4) split clone and map to backup host'
$CMD --clonesplit --clone ${VOLUME_NAME}_clone
$CMD --lunmap --vol $VOLUME_NAME --lun $LUN_NAME --igroup $LUN_IG

echo '-----------------------------------------------------'

# echo '5) rescan, mount, run backup, unmount'

echo '6) unmap clone from backup host'
$CMD --lununmap --vol ${VOLUME_NAME}_clone --lun $LUN_NAME --igroup $LUN_IG

echo '-----------------------------------------------------'

echo '7) rename source snapshot'
$CMD --snaplist --vol $VOLUME_NAME
$CMD --snaprename --vol $VOLUME_NAME --snap $last_snap --new_name ${last_snap}${BACKUP_SUFFIX}
$CMD --snaplist --vol $VOLUME_NAME

echo '-----------------------------------------------------'

echo '8) rotate snapshots'
$CMD --snaprotate --vol $VOLUME_NAME --retention 5
$CMD --snaplist --vol $VOLUME_NAME

echo '-----------------------------------------------------'

echo '9) destroy clone volume'
$CMD --clonedelete --vol ${VOLUME_NAME}_clone

echo '-----------------------------------------------------'
echo done.
