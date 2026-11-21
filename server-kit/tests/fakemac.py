"""A synthetic Mac for the tests: `diskutil`, `ioreg` and `system_profiler` output shaped like macOS 27's real output
(field names checked read-only on the build Mac, 2026-11-06), with made-up drives, serials and UUIDs.

Disks: internal disk0 (+ APFS container disk3), three external data drives (APFS LaCie, exFAT T7, a USB drive whose
bridge reports no serial), a disk image, and the new USB SSD `disk9`.
"""
import copy
import json
import plistlib

EFI = 'C12A7328-F81F-11D2-BA4B-00A0C93EC93B'


def usb_device(serial, *bsd):
    """An IOUSBHostDevice subtree: device -> interface -> SCSI -> block driver -> IOMedia whole disk -> partitions."""
    media = {'IOObjectClass': 'IOMedia', 'BSD Name': bsd[0], 'Whole': True,
             'IORegistryEntryChildren': [{'IOObjectClass': 'IOGUIDPartitionScheme', 'IORegistryEntryChildren': [
                 {'IOObjectClass': 'IOMedia', 'BSD Name': b, 'Whole': False} for b in bsd[1:]]}]}
    dev = {'IOObjectClass': 'IOUSBHostDevice', 'idVendor': 1234, 'idProduct': 5678, 'locationID': 1,
           'IORegistryEntryChildren': [{'IOObjectClass': 'IOUSBHostInterface', 'IORegistryEntryChildren': [
               {'IOObjectClass': 'IOSCSIPeripheralDeviceType00', 'IORegistryEntryChildren': [
                   {'IOObjectClass': 'IOBlockStorageDriver', 'IORegistryEntryChildren': [media]}]}]}]}
    if serial:
        dev['USB Serial Number'] = serial; dev['kUSBSerialNumberString'] = serial
    return dev


class FakeMac:
    def __init__(self, new_drive_files=None, mounts=None):
        m = mounts or {}
        self.whole = {
            'disk0': dict(BusProtocol='Apple Fabric', Internal=True, VirtualOrPhysical='Unknown', TotalSize=2001111162880,
                          MediaName='APPLE SSD AP2048Z', Content='GUID_partition_scheme'),
            'disk3': dict(BusProtocol='Apple Fabric', Internal=True, VirtualOrPhysical='Virtual', TotalSize=1995165736960,
                          MediaName='AppleAPFSMedia', APFSContainerReference='disk3', Content='EF57347C-0000-11AA-AA11-00306543ECAC'),
            'disk4': dict(BusProtocol='USB', Internal=False, VirtualOrPhysical='Physical', TotalSize=14000519643136,
                          MediaName='LaCie d2 Professional', Content='GUID_partition_scheme'),
            'disk5': dict(BusProtocol='USB', Internal=False, VirtualOrPhysical='Virtual', TotalSize=14000309874688,
                          MediaName='AppleAPFSMedia', APFSContainerReference='disk5', Content='EF57347C-0000-11AA-AA11-00306543ECAC'),
            'disk6': dict(BusProtocol='USB', Internal=False, VirtualOrPhysical='Physical', TotalSize=2000398934016,
                          MediaName='Samsung PSSD T7', Content='FDisk_partition_scheme'),
            'disk7': dict(BusProtocol='USB', Internal=False, VirtualOrPhysical='Physical', TotalSize=4000787030016,
                          MediaName='External USB 3.0', Content='GUID_partition_scheme'),
            'disk8': dict(BusProtocol='Disk Image', Internal=False, VirtualOrPhysical='Virtual', TotalSize=19096703488,
                          MediaName='Apple disk image', Content='GUID_partition_scheme'),
            'disk9': dict(BusProtocol='USB', Internal=False, VirtualOrPhysical='Physical', TotalSize=2000398934016,
                          MediaName='CT2000X10SSD9', Content='FDisk_partition_scheme'),
        }
        self.parts = {
            'disk0': [dict(DeviceIdentifier='disk0s2', Content='Apple_APFS', Size=1995165736960, DiskUUID='0A0A0A0A-0000-4000-8000-000000000002')],
            'disk3': [dict(DeviceIdentifier='disk3s1', VolumeName='Macintosh HD', MountPoint='/', VolumeUUID='3A000000-0000-4000-8000-000000000001',
                           DiskUUID='3A000000-0000-4000-8000-0000000000D1', Size=11000000000, FilesystemType='apfs'),
                      dict(DeviceIdentifier='disk3s5', VolumeName='Data', MountPoint='/System/Volumes/Data', FilesystemType='apfs',
                           VolumeUUID='3A000000-0000-4000-8000-000000000005', DiskUUID='3A000000-0000-4000-8000-0000000000D5', Size=1500000000000)],
            'disk4': [dict(DeviceIdentifier='disk4s1', Content='EFI', VolumeName='EFI', Size=209715200, DiskUUID='4A000000-0000-4000-8000-0000000000E1',
                           VolumeUUID='4A000000-0000-4000-8000-0000000000F1', FilesystemType='msdos'),
                      dict(DeviceIdentifier='disk4s2', Content='Apple_APFS', Size=14000309874688, DiskUUID='4A000000-0000-4000-8000-000000000002')],
            'disk5': [dict(DeviceIdentifier='disk5s1', VolumeName='Photos', MountPoint=m.get('disk5s1', '/Volumes/Photos'), FilesystemType='apfs',
                           VolumeUUID='5A000000-0000-4000-8000-000000000001', DiskUUID='5A000000-0000-4000-8000-0000000000D1', Size=9000000000000)],
            'disk6': [dict(DeviceIdentifier='disk6s1', Content='Windows_NTFS', VolumeName='T7', MountPoint=m.get('disk6s1', '/Volumes/T7'),
                           FilesystemType='exfat', VolumeUUID='6A000000-0000-4000-8000-000000000001', DiskUUID='6A000000-01', Size=2000397885440)],
            'disk7': [dict(DeviceIdentifier='disk7s2', Content='Apple_HFS', VolumeName='Archive', MountPoint=m.get('disk7s2', '/Volumes/Archive'),
                           FilesystemType='hfs', VolumeUUID='7A000000-0000-4000-8000-000000000002', DiskUUID='7A000000-0000-4000-8000-0000000000D2', Size=4000000000000)],
            'disk8': [dict(DeviceIdentifier='disk8s1', Content='Apple_HFS', VolumeName='Installer', MountPoint='/Volumes/Installer', FilesystemType='hfs',
                           VolumeUUID='8A000000-0000-4000-8000-000000000001', Size=19000000000)],
            'disk9': [dict(DeviceIdentifier='disk9s1', Content='Windows_NTFS', VolumeName='X10', MountPoint=m.get('disk9s1', '/Volumes/X10'),
                           FilesystemType='exfat', VolumeUUID='9A000000-0000-4000-8000-000000000001', DiskUUID='9A000000-01', Size=2000397885440)],
        }
        self.stores = {'disk3': 'disk0s2', 'disk5': 'disk4s2'}
        self.usb = [usb_device('NAA1B2C3', 'disk4', 'disk4s1', 'disk4s2'), usb_device('S6WXNS0T123456A', 'disk6', 'disk6s1'),
                    usb_device('', 'disk7', 'disk7s2'), usb_device('2345E6F7A8B9', 'disk9', 'disk9s1')]
        self.calls = []
        self.tm = []  # Time Machine destination mount points

    # -- what the real tools would print
    def list_plist(self):
        entries = []
        for dev in sorted(self.whole, key=lambda x: int(x[4:])):
            e = {'DeviceIdentifier': dev, 'Content': self.whole[dev].get('Content', ''), 'Size': self.whole[dev]['TotalSize'],
                 'OSInternal': False}
            key = 'APFSVolumes' if dev in self.stores else 'Partitions'
            e[key] = [{k: v for k, v in p.items() if k != 'FilesystemType'} for p in self.parts.get(dev, [])]
            if dev in self.stores:
                e['APFSPhysicalStores'] = [{'DeviceIdentifier': self.stores[dev]}]
            entries.append(e)
        return {'AllDisksAndPartitions': entries, 'WholeDisks': sorted(self.whole), 'AllDisks': []}

    def info_plist(self, dev):
        if dev in self.whole:
            d = dict(self.whole[dev], DeviceIdentifier=dev, WholeDisk=True)
            if dev in self.stores:
                d['APFSPhysicalStores'] = [{'APFSPhysicalStore': self.stores[dev]}]
            return d
        for plist in self.parts.values():
            for p in plist:
                if p['DeviceIdentifier'] == dev:
                    return dict(p, WholeDisk=False, TotalSize=p.get('Size', 0))
        raise KeyError(dev)

    def run(self, argv):
        self.calls.append(list(argv))
        if argv[:3] == ['diskutil', 'list', '-plist']:
            return plistlib.dumps(self.list_plist())
        if argv[:3] == ['diskutil', 'info', '-plist']:
            return plistlib.dumps(self.info_plist(argv[3]))
        if argv[0] == 'ioreg':
            return plistlib.dumps(copy.deepcopy(self.usb) if argv[-1] == 'IOUSBHostDevice' else [])
        if argv[:3] == ['tmutil', 'destinationinfo', '-X']:
            if not self.tm:  # macOS 27 with no destination: exit 0 and an empty dict (seen read-only on the build Mac, 2026-11-06)
                return plistlib.dumps({})
            return plistlib.dumps({'Destinations': [{'Name': 'TM', 'Kind': 'Local', 'MountPoint': m} for m in self.tm]})
        if argv[0] == 'system_profiler':
            return json.dumps({'SPNVMeDataType': []}).encode()
        raise AssertionError('unexpected command ' + repr(argv))

    # -- what `diskutil partitionDisk disk9 MBR FAT32 TURINBOOT 12G ExFAT TURINDATA R` would leave behind
    def partition(self, dev, boot_mount, data_mount):
        n = int(dev[4:])
        self.parts[dev] = [
            dict(DeviceIdentifier=dev + 's1', Content='DOS_FAT_32', VolumeName='TURINBOOT', MountPoint=boot_mount, FilesystemType='msdos',
                 VolumeUUID=f'B{n:07d}-0000-4000-8000-00000000B001', DiskUUID=f'B{n:07d}-01', Size=12000000000),
            dict(DeviceIdentifier=dev + 's2', Content='Windows_NTFS', VolumeName='TURINDATA', MountPoint=data_mount, FilesystemType='exfat',
                 VolumeUUID=f'D{n:07d}-0000-4000-8000-00000000D002', DiskUUID=f'D{n:07d}-02', Size=1988000000000)]
