"""Python script with helpers methods for common NetApp functions based on the new REST API

Requirements:
    - python3
    - netapp_ontap module (pip)
    - NetApp ONTAP 9.6+
    - SVM user with required permissions (login via certs is not yet supported)
    - HTTPS network connection to the SVM

20191015 francesco confalonieri
"""

import time
import logging
import sys, os
import argparse

from netapp_ontap import config, HostConnection, NetAppRestError, utils
from netapp_ontap.resources import Volume, Snapshot, Lun, LunMap

args = None
logger = None


''' Prepare connection to the vserver
    TODO: suspport certificates
'''
def prepare_connection(vserver_ip, username, password):
    global config, args
    try:
        config.CONNECTION = HostConnection(vserver_ip, username=username, password=password, verify=False)
        if args.debug:
            print("Enabling debug on NetApp REST API interface")
            utils.DEBUG = 1
        return True
    except Exception as e:
        print("Error: connection to vserver {:s} failed: {:s}".format(vserver_ip, e))
        return False

'''Returns a Volume object given the volume name'''
def get_volume(volume_name):
    return(Volume.find(name=volume_name))

'''Returns a Snapshot obj given Volume object and snapshot name'''
def get_snapshot(volume,snapshot_name):
    return(Snapshot.find(volume.uuid, name=snapshot_name))

'''Returns lun mapping info for a lun'''
def get_lunmap(lun_path, igroup, svm_name):
    return(LunMap.find({ "lun": { "name": lun_path }, "igroup": { "name": igroup }, "svm": { "name": svm_name } }))

''' Creates a snapshot of a volume
    snapshot name format is: {basename}_{unixtime}
'''
def create_snapshot(volume, basename):
    snapshot = None
    if volume and basename:
        seq=int(time.time())
        snapshot = Snapshot.from_dict({
            'name': '%s_%d' % (basename, seq),
            'volume': volume.to_dict(),
        })
        snapshot.post()
    return snapshot

''' Deletes a snapshot '''
def delete_snapshot(snapshot):
    try:
        res = snapshot.delete()
        return True
    except Exception:
        return False

''' Rename a snapshot '''
def snapshot_rename(snapshot, new_name):
    if snapshot and new_name:
        try:
            snapshot.name = new_name
            snapshot.patch()
            return True
        except Exception as e:
            return False
    return False

''' Get all snapshots for a volume '''
def get_snapshot_list(volume):
    result = Snapshot.get_collection(volume.uuid, name="*")
    lst = list(result)
    lst.reverse()  # sort from more to least recent
    return lst

''' Clone a flexvol from a snapshot'''
def clone_create(volume, snapshot, svmname, clone_name):
    try:
        clone = Volume.from_dict({
            "name": clone_name,
            "clone": {
                "parent_volume":   { "uuid": volume.uuid },
                "parent_snapshot": { "uuid": snapshot.uuid },
                "is_flexclone": True,
            },
            "svm": { "name": svmname }
        })
        clone.post()
        return clone
    except Exception as e:
        #print('Error: Cannot create volume clone: {:s}'.format(str(e)))
        return False

''' Splits clone volume from parent '''
def clone_split(clone):
    try:
        clone.clone.split_initiated = True
        res = clone.patch()
        if res.is_job:
            print("Waiting for the operation to complete in background...", end=' ')
            res.poll()
            print('done.')
        return True
    except Exception as e:
        #print('Error: Cannot split clone volume {:s} from parent: {:s}'.format(clone.name,str(e)))
        return False

''' Deletes a clone volume '''
def clone_delete(clone):
    try:
        clone.get()
        clone.delete()
        return True
    except Exception as e:
        print('<DEBUG> Error in clone_delete(): {:s}'.format(e))
        return False

''' Map LUN '''
def lun_map(lun_path, ig, svm_name):
    try:
        mapping = LunMap.from_dict({
            "lun": { "name": lun_path },
            "igroup": { "name": ig },
            "svm": { "name": svm_name }
        })
        response = mapping.post()
        if not response.is_err:
            return True
    except Exception as e:
        if 'LUN already mapped to this group' in str(e):
            return True

        print('<DEBUG> Cannot mount lun: {:s}'.format(str(e)))
        return False
    
    return False

def lun_unmap(lun_path, ig, svm_name):
    try:
        mapping = LunMap.find({"lun": { "name": lun_path }, "igroup": { "name": ig }})
        response = mapping.delete()
        if not response.is_err:
            return True
    except Exception as e:
        print('<DEBUG> Cannot mount lun: {:s}'.format(str(e)))
        return False

    return False


#----------------------------------------------------------------------------

def main():
    global args, logger

    parser = argparse.ArgumentParser(description='Facilities for working with NetApp Snapshots using REST API')

    # commands
    parser.add_argument('--snaplist', dest='cmd', action='store_const', const='SL', help='List all snapshots for a given volume')
    parser.add_argument('--snapcreate', dest='cmd', action='store_const', const='SC', help='Create snapshot of a given volume')
    parser.add_argument('--snapdelete', dest='cmd', action='store_const', const='SD', help='Delete snapshot')
    parser.add_argument('--snaprotate', dest='cmd', action='store_const', const='SR', help='Rotate snapshots in a volume')
    parser.add_argument('--snaprename', dest='cmd', action='store_const', const='SN', help='Rename a snapshot')
    parser.add_argument('--clonecreate', dest='cmd', action='store_const', const='CC', help='Create a clone volume from a snapshot')
    parser.add_argument('--clonesplit', dest='cmd', action='store_const', const='CS', help='Splits clone volume from parent')
    parser.add_argument('--clonedelete', dest='cmd', action='store_const', const='CD', help='Delete a clone volume')
    parser.add_argument('--lunmap', dest='cmd', action='store_const', const='LM', help='Map LUN to host')
    parser.add_argument('--lununmap', dest='cmd', action='store_const', const='LU', help='Unmap LUN from host')

    # connection relatec
    parser.add_argument('--na ', dest='vserver_ip', action='store', help='IP or hostname of NetApp vserver (SVM)')
    parser.add_argument('--user ', dest='vserver_username', action='store', help='Username for connecting to the vserver (SVM)')
    parser.add_argument('--pass ', dest='vserver_password', action='store', help='Password for connecting to the vserver (SVM)')

    # parameters
    parser.add_argument('--vol', dest='volname', action='store', help='Name of the volume')
    parser.add_argument('--snap', dest='snapname', action='store', help='Name of the snapshot')
    parser.add_argument('--clone', dest='clonename', action='store', help='Name of the clone volume')
    parser.add_argument('--lun', dest='lunname', action='store', help='Name of the LUN')
    parser.add_argument('--igroup', dest='igroup', action='store', help='Name of the LUN')
    parser.add_argument('--base_name', dest='basename', action='store', help='Base name for the snapshot')
    parser.add_argument('--new_name', dest='newname', action='store', help='New name for the snapshot')
    parser.add_argument('--retention', action='store', help='Number of snapshots to keep')

    parser.add_argument('--debug', action='store_true', help='Enable debug')    
    args = parser.parse_args()

    # Configure logging
    if args.debug:
        logLevel = logging.DEBUG
        #FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
        #logging.basicConfig(level=logLevel, format=FORMAT)

    logger = logging.getLogger()

    # List snapshots
    if args.cmd == 'SL':

        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                volume = get_volume(args.volname)
                if volume:
                    print("Volume: {}\n".format(volume.name))

                    snaplist = get_snapshot_list(volume)
                    if len(snaplist) > 0:
                        print("%s snapshots found" % len(snaplist))
                        separator = '-' * 50
                        print(separator)
                        print('{:<24s}{}'.format('Snapshot name','Creation time'))
                        print(separator)
                        for snap in snaplist:
                            snap.get()
                            print("{:<24s}{:%Y-%m-%d %H:%M:%S+00:00}".format(snap.name, snap.create_time))
                        print(separator)
                    else:
                        print("No snapshots found")
                else:
                    print("Error: Unable to find volume with name '{}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)

    # Create snapshot
    elif args.cmd == 'SC':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                volume = get_volume(args.volname)
                if volume:
                    if args.basename:
                        try:
                            # Create snapshot
                            snapshot = create_snapshot(volume, args.basename)
                            if snapshot:
                                print("Snapshot '{}' created for volume {}".format(snapshot.name, volume.name))
                            else:
                                print("Error: Unable to find snapshot with name '{}'".format(args.snapname))
                                return(103)
                        except Exception as e:
                            print("Error: Cannot create snapshot for volume {:s}: {:s}".format(volume.name, str(e)))
                            return(102)
                    else:
                        print("Please specify base name for the snapshot with --base_name")
                        return(1)

                else:
                    print("Error: Unable to find volume with name '{}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)

    # Rotate snapshot
    elif args.cmd == 'SR':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                if not args.retention:
                    print("Please specify retention with --retention")
                    return(1)

                volume = get_volume(args.volname)
                if volume:
                    snaplist = get_snapshot_list(volume)
                    if len(snaplist) > int(args.retention):
                        deleted_count = 0
                        for i in range(int(args.retention), len(snaplist)):
                            snapshot = snaplist[i]
                            if delete_snapshot(snapshot):
                                deleted_count += 1
                                logger.debug('Deleted snapshot %s', snaplist[i].name)
                        print("{:d} snapshots deleted".format(deleted_count))
                    else:
                        print("No snapshots to rotate (%s found)" % len(snaplist))
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)

    # Rename snapshot
    elif args.cmd == 'SN':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                if not args.newname:
                    print("Please specify new snapshot name with --new_name")
                    return(1)

                volume = get_volume(args.volname)
                if volume:
                    if args.snapname:
                        snapshot = get_snapshot(volume, args.snapname)
                        if snapshot:
                            original_name=snapshot.name
                            if snapshot_rename(snapshot, args.newname):
                                print("Successfully renamed snapshot {:s} to {:s}".format(original_name, snapshot.name))
                            else:
                                print('Error: Cannot rename snapshot {:s}'.format(snapshot.name))
                        else:
                            print("Error: Unable to find snapshot {:s}".format(args.snapname))
                            return(103)
                    else:
                        print("Please specify snapshot name with --snap")
                        return(1)
                else:
                    print("Error: Unable to find volume {:s}".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)


    # Create CLONE
    elif args.cmd == 'CC':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                if not args.clonename:
                    print("Please specify name of clone volume with --clone")
                    return(1)

                volume = get_volume(args.volname)
                if volume:
                    if args.snapname:
                        snapshot = get_snapshot(volume, args.snapname)
                        if snapshot:
                            # Clone volume
                            clone_name = args.clonename
                            clone = clone_create(volume, snapshot, volume.svm.name, clone_name)
                            if clone:
                                print("Successfully cloned volume {:s} to {:s} from snapshot {:s}".format(volume.name, clone.name, snapshot.name))
                            else:
                                print("Error: Cannot create clone of volume {:s} from snapshot {:s}: {:s}".format(volume.name, snapshot.name, str(e)))
                                return(102)
                        else:
                            print("Error: Unable to find snapshot with name '{:s}'".format(args.snapname))
                            return(103)
                    else:
                        print("Please specify source snapshot name with --snap")
                        return(1)
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify volume with --vol")
                return(1)

    # Delete clone volume
    elif args.cmd == 'CD':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                volume = get_volume(args.volname)
                if volume:
                    try:
                        # WARNING! This will delete the volume without you to offline it first, and also will delete all mappings
                        volume.delete()
                        print("Successfully deleted volume {:s}".format(volume.name))
                    except Exception as e:
                        print('Error: Cannot delete volume {:s}: {:s}'.format(volume.name, e))
                        return(156)
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify volume with --vol")
                return(1)
    
    # Split clone
    elif args.cmd == 'CS':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.clonename:
                clone = get_volume(args.clonename)
                if clone:
                    print("Splitting volume clone {:s}".format(clone.name))
                    if clone_split(clone):
                        print('Successfully splitted clone volume {:s} from parent.'.format(clone.name))
                    else:
                        print('Error: Cannot split clone volume {:s} from parent.'.format(clone.name))
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target clone volume with --clone")
                return(1)

    # Map lun
    elif args.cmd == 'LM':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                if not args.lunname:
                    print("Please specify name of clone volume with --clone")
                    return(1)
                if not args.igroup:
                    print("Please specify name of initiator group with --igroup")
                    return(1)

                clone = get_volume(args.volname)
                if clone:
                    lun_path = '/vol/{:s}/{:s}'.format(clone.name, args.lunname)
                    mapping = get_lunmap(lun_path, args.igroup, volume.svm.name)
                    if mapping:
                        print("Lun {:s} already mapped to igroup {:s} with lun id {:d}".format(lun_path, args.igroup, mapping.logical_unit_number))
                    else:
                        if lun_map(lun_path, args.igroup, volume.svm.name):
                            print("Successfully mapped lun {:s} to igroup {:s}.".format(lun_path, args.igroup))
                        else:
                            print("Error: Unable to map LUN to initiator group.")
                            return(106)
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)

    # Unmap lun
    elif args.cmd == 'LU':
        if prepare_connection(args.vserver_ip, args.vserver_username, args.vserver_password):

            if args.volname:
                if not args.lunname:
                    print("Please specify name of clone volume with --clone")
                    return(1)
                if not args.igroup:
                    print("Please specify name of initiator group with --igroup")
                    return(1)

                clone = get_volume(args.volname)
                if clone:
                    lun_path = '/vol/{:s}/{:s}'.format(clone.name, args.lunname)
                    mapping = get_lunmap(lun_path, args.igroup, volume.svm.name)
                    if not mapping:
                        print('No mapping to remove.')
                    else:
                        if lun_unmap(lun_path, args.igroup, volume.svm.name):
                            print("Successfully unmapped lun {:s} from igroup {:s}".format(lun_path, args.igroup))
                        else:
                            print("Error: Unable to unmap LUN from initiator group.")
                            return(106)
                else:
                    print("Error: Unable to find volume with name '{:s}'".format(args.volname))
                    return(103)
            else:
                print("Please specify target volume with --vol")
                return(1)

    else:
        print("Invalid command given.")
        return(1)

    return(0)

if __name__ == "__main__":
    exit(main())