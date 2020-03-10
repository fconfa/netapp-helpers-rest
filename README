# netapp-helpers-rest

Script to execute common NetApp functions related to snapshot management by connecting to the storage via the new REST API.
This is a complete rewrite of previous netapp-helpers-cli script.

## description

This script covers only some NetApp operations and options so your mileage may vary.

Supported operations are:

*  Taking the snapshot of a NetApp volume
*  Listing volume snapshots
*  Deleting existing snapshot for a volume
*  Rotating volume snapshots
*  Renaming snapshot
*  Create volume clone from existing snapshot
*  Splitting a clone from its parent volume
*  Deleting a clone volume
*  Mapping/unmapping a LUN to a specific initiator group

See comments in the scripts for further info.

#### syntax

```
na_helpers_rest.py --snapcreate --vol <volume_name> --base_name <base_name>
na_helpers_rest.py --snapdelete --vol <volume_name> --snap <snapshot_name>
na_helpers_rest.py --snaplist --vol <volume_name>
na_helpers_rest.py --snaprotate --vol <volume_name> --retention <number_of_snapshots>
na_helpers_rest.py --snaprename --vol <volume_name> --snap <snapshot_name> --new_name <snapshot_new_name>
na_helpers_rest.py --clonecreate --vol <volume> --snap <snapshot_name> --clone <clone_name>
na_helpers_rest.py --clonesplit --clone <clone_name>
na_helpers_rest.py --clonedelete --clone <clone_name>
na_helpers_rest.py --lunmap --vol <volume> --lun <lun_path> --igroup <ig_name>
na_helpers_rest.py --lununmap --vol <volume> --lun <lun_path> --igroup <ig_name>
```

#### examples

See `test.sh` for examples of using this tool.

## requirements

*  python3
*  netapp_ontap python module (pip install netapp_ontap)
*  NetApp ONTAP 9.6+
*  SVM user with required permissions (login via certs is not yet supported)
*  HTTPS network connection to the SVM
