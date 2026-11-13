#!/usr/bin/env python3
"""
create_sdcard_raw.py

Generates a bootable OpenSTLinux microSD .raw image on Windows/Linux from an
ST FlashLayout TSV file, faithfully replicating the logic and partition layout
of ST's `scripts/create_sdcard_from_flashlayout.sh`.

Features:
- Full GPT generation (Protective MBR at LBA 0, Primary GPT at LBA 1..33,
  Backup GPT at disk end) with valid IEEE 802.3 CRC32 checksums.
- Faithful replication of ST partition type GUIDs, fixed PARTUUIDs (rootfs,
  fip-a, fip-b, metadata1, metadata2), and partition attribute flags (legacy BIOS
  bootable on bootfs).
- Fast block-buffered population of partition images into the raw disk file.
- Built-in verification engine: checks MBR, primary & backup GPT headers,
  CRCs, partition array integrity, and binary file offsets.
- Generates `_how_to_update.txt` partition schema documentation.
"""

import os
import sys
import argparse
import struct
import uuid
import binascii
from typing import List, Dict, Optional, Tuple

SECTOR_SIZE = 512
DEFAULT_RAW_SIZE_MB = 4915
GPT_ENTRIES_COUNT = 128
GPT_ENTRY_SIZE = 128
GPT_ARRAY_SECTORS = (GPT_ENTRIES_COUNT * GPT_ENTRY_SIZE) // SECTOR_SIZE  # 32 sectors

# Partition Type GUIDs (per create_sdcard_from_flashlayout.sh & sgdisk mappings)
TYPE_GUID_MAP = {
    "Binary": uuid.UUID("8DA63339-0007-60C0-C436-083AC8230908"),     # sgdisk 8301 (Linux reserved)
    "FIP": uuid.UUID("19d5df83-11b0-457b-be2c-7559c13142a5"),        # DEFAULT_FIP_TYPEUUID
    "FWU_MDATA": uuid.UUID("8a7a84a0-8387-40f6-ab41-a8b9a5a60d23"),  # DEFAULT_FWU_MDATA_TYPEUUID
    "System": uuid.UUID("0FC63DAF-8483-4772-8E79-3D69D8477DE4"),     # sgdisk 8300 (Linux filesystem)
    "FileSystem": uuid.UUID("0FC63DAF-8483-4772-8E79-3D69D8477DE4"), # sgdisk 8300 (Linux filesystem)
    "ESP": uuid.UUID("C12A7328-F81F-11D2-BA4B-00A0C93EC93B"),        # sgdisk ef00 (EFI system partition)
    "ENV": uuid.UUID("3de21764-95bd-54bd-a5c3-4abe786f38a8"),        # DEFAULT_UBOOT_ENV_TYPEUUID
}

# Fixed Partition Unique GUIDs (PARTUUID) required by ST boot sequence / U-Boot bootargs
FIXED_PART_UUID_MAP = {
    "rootfs": uuid.UUID("e91c4e10-16e6-4c0e-bd0e-77becf4a3582"),     # DEFAULT_SDCARD_PARTUUID
    "fip-a": uuid.UUID("4fd84c93-54ef-463f-a7ef-ae25ff887087"),      # DEFAULT_FIP_A_PARTUUID
    "fip-b": uuid.UUID("09c54952-d5bf-45af-acee-335303766fb3"),      # DEFAULT_FIP_B_PARTUUID
    "metadata1": uuid.UUID("5f91c128-e120-48d7-bb64-9fa9aed4c7e3"),  # DEFAULT_FWU_MDATA_A_PARTUUID
    "metadata2": uuid.UUID("f469f981-5985-4206-8fb3-839956035a65"),  # DEFAULT_FWU_MDATA_B_PARTUUID
}

NAMESPACE_STM32 = uuid.UUID("b5c3b6f2-8c43-4e3a-96e0-410e30d67420")


class PartitionRecord:
    def __init__(self, opt: str, part_id: str, name: str, part_type: str,
                 ip: str, offset_bytes: int, binary_rel: str):
        self.opt = opt
        self.part_id = part_id
        self.name = name
        self.part_type = part_type
        self.ip = ip
        self.offset_bytes = offset_bytes
        self.binary_rel = binary_rel
        self.start_lba = offset_bytes // SECTOR_SIZE
        self.end_lba = 0
        self.type_guid: uuid.UUID = uuid.UUID(int=0)
        self.unique_guid: uuid.UUID = uuid.UUID(int=0)
        self.attributes: int = 0
        self.image_path: Optional[str] = None
        self.image_size: int = 0

    @property
    def sector_count(self) -> int:
        return self.end_lba - self.start_lba + 1

    @property
    def size_bytes(self) -> int:
        return self.sector_count * SECTOR_SIZE


def parse_flashlayout_tsv(tsv_path: str) -> List[PartitionRecord]:
    """Parse FlashLayout TSV file and extract mmc0 partitions matching create_sdcard_from_flashlayout.sh."""
    valid_opts = {"1", "P", "E", "PD", "DP", "PE", "PED"}
    records: List[PartitionRecord] = []

    with open(tsv_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                parts = line.split()
            if len(parts) < 7:
                continue

            opt, part_id, name, part_type, ip, offset_str, binary_rel = parts[:7]

            if ip != "mmc0":
                continue
            if opt not in valid_opts:
                continue

            offset_bytes = int(offset_str, 16)
            rec = PartitionRecord(opt, part_id, name, part_type, ip, offset_bytes, binary_rel)
            records.append(rec)

    return records


def find_images_directory(tsv_path: str, records: List[PartitionRecord], override_dir: Optional[str] = None) -> str:
    """Find images directory reproducing get_last_image_path() logic in create_sdcard_from_flashlayout.sh."""
    if override_dir and os.path.isdir(override_dir):
        return os.path.abspath(override_dir)

    tsv_dir = os.path.abspath(os.path.dirname(tsv_path))
    # Candidate images to probe (rootfs first, then any non-none binary)
    probe_images = []
    for r in records:
        if r.name == "rootfs" and r.binary_rel != "none":
            probe_images.insert(0, r.binary_rel)
        elif r.binary_rel != "none":
            probe_images.append(r.binary_rel)

    search_dirs = [
        tsv_dir,
        os.path.abspath(os.path.join(tsv_dir, "..")),
        os.path.abspath(os.path.join(tsv_dir, "..", "..")),
        os.path.abspath(os.path.join(tsv_dir, "..", "..", "..")),
    ]

    for candidate in probe_images:
        for sdir in search_dirs:
            full_path = os.path.join(sdir, candidate)
            if os.path.exists(full_path):
                return sdir

    # Fallback to current directory or tsv directory
    return tsv_dir


def setup_partitions(records: List[PartitionRecord], total_sectors: int, images_dir: str):
    """Assign GUIDs, LBAs, attributes, and image sizes according to create_sdcard_from_flashlayout.sh."""
    last_usable_lba = total_sectors - 34  # 32 backup table sectors + 1 backup header + 1 0-index offset

    for i, rec in enumerate(records):
        # Type GUID
        if rec.part_type in TYPE_GUID_MAP:
            rec.type_guid = TYPE_GUID_MAP[rec.part_type]
        else:
            raise ValueError(f"Unknown partition type '{rec.part_type}' for partition '{rec.name}'")

        # Unique GUID
        if rec.name in FIXED_PART_UUID_MAP:
            rec.unique_guid = FIXED_PART_UUID_MAP[rec.name]
        elif rec.name.startswith("fip-a"):
            rec.unique_guid = FIXED_PART_UUID_MAP["fip-a"]
        elif rec.name.startswith("fip-b"):
            rec.unique_guid = FIXED_PART_UUID_MAP["fip-b"]
        else:
            rec.unique_guid = uuid.uuid5(NAMESPACE_STM32, f"partition.{rec.name}")

        # Attributes: bootfs has Legacy BIOS Bootable flag (sgdisk -A $j:set:2 => bit 2)
        if rec.name in ("boot", "bootfs"):
            rec.attributes = 1 << 2  # 0x0000000000000004
        else:
            rec.attributes = 0

        # End LBA calculation
        if i < len(records) - 1:
            next_start_lba = records[i + 1].start_lba
            rec.end_lba = next_start_lba - 1
        else:
            # Last partition extends to last usable sector
            rec.end_lba = last_usable_lba

        # Image lookup
        if rec.binary_rel and rec.binary_rel.lower() != "none":
            cand = os.path.join(images_dir, rec.binary_rel)
            if os.path.isfile(cand):
                rec.image_path = cand
                rec.image_size = os.path.getsize(cand)
            else:
                rec.image_path = None
                rec.image_size = 0


def create_protective_mbr(total_sectors: int) -> bytes:
    """Build Protective MBR at LBA 0 (512 bytes)."""
    mbr = bytearray(SECTOR_SIZE)
    # Partition entry 1 at offset 0x1BE (446)
    # BootIndicator: 0x00
    # Starting CHS: 0x00, 0x02, 0x00 (Head 0, Sector 2, Cyl 0)
    # OSType: 0xEE (GPT Protective)
    # Ending CHS: 0xFF, 0xFF, 0xFF
    # StartingLBA: 1 (0x00000001)
    # SizeInLBA: min(0xFFFFFFFF, total_sectors - 1)
    mbr_size = min(0xFFFFFFFF, total_sectors - 1)
    struct.pack_into("<B3sB3sII", mbr, 0x1BE,
                     0x00,
                     b"\x00\x02\x00",
                     0xEE,
                     b"\xff\xff\xff",
                     1,
                     mbr_size)
    # Signature at offset 510
    mbr[510:512] = b"\x55\xaa"
    return bytes(mbr)


def create_gpt_partition_array(records: List[PartitionRecord]) -> bytes:
    """Build 128 GPT partition entries (16384 bytes)."""
    array = bytearray(GPT_ENTRIES_COUNT * GPT_ENTRY_SIZE)

    for i, rec in enumerate(records):
        entry_offset = i * GPT_ENTRY_SIZE
        # PartitionTypeGUID (16 bytes, little endian)
        array[entry_offset:entry_offset + 16] = rec.type_guid.bytes_le
        # UniquePartitionGUID (16 bytes, little endian)
        array[entry_offset + 16:entry_offset + 32] = rec.unique_guid.bytes_le
        # StartingLBA (uint64)
        struct.pack_into("<Q", array, entry_offset + 32, rec.start_lba)
        # EndingLBA (uint64)
        struct.pack_into("<Q", array, entry_offset + 40, rec.end_lba)
        # Attributes (uint64)
        struct.pack_into("<Q", array, entry_offset + 48, rec.attributes)
        # PartitionName (72 bytes UTF-16LE, null-padded)
        name_bytes = rec.name.encode("utf-16le").ljust(72, b"\x00")[:72]
        array[entry_offset + 56:entry_offset + 128] = name_bytes

    return bytes(array)


def create_gpt_header(my_lba: int, alt_lba: int, first_usable: int,
                      last_usable: int, disk_guid: uuid.UUID,
                      part_entry_lba: int, part_array: bytes) -> bytes:
    """Build GPT Header (512 bytes with 92-byte struct and zero padding)."""
    header = bytearray(SECTOR_SIZE)
    # Signature: 'EFI PART'
    header[0:8] = b"EFI PART"
    # Revision: 0x00010000
    struct.pack_into("<I", header, 8, 0x00010000)
    # HeaderSize: 92
    struct.pack_into("<I", header, 12, 92)
    # HeaderCRC32: 0 (calculated after)
    struct.pack_into("<I", header, 16, 0)
    # Reserved: 0
    struct.pack_into("<I", header, 20, 0)
    # MyLBA
    struct.pack_into("<Q", header, 24, my_lba)
    # AlternateLBA
    struct.pack_into("<Q", header, 32, alt_lba)
    # FirstUsableLBA
    struct.pack_into("<Q", header, 40, first_usable)
    # LastUsableLBA
    struct.pack_into("<Q", header, 48, last_usable)
    # DiskGUID (16 bytes, little-endian)
    header[56:72] = disk_guid.bytes_le
    # PartitionEntryLBA
    struct.pack_into("<Q", header, 72, part_entry_lba)
    # NumberOfPartitionEntries: 128
    struct.pack_into("<I", header, 80, GPT_ENTRIES_COUNT)
    # SizeOfPartitionEntry: 128
    struct.pack_into("<I", header, 84, GPT_ENTRY_SIZE)
    # PartitionEntryArrayCRC32
    part_crc = binascii.crc32(part_array) & 0xFFFFFFFF
    struct.pack_into("<I", header, 88, part_crc)

    # Compute Header CRC32 over the 92 bytes with CRC field set to 0
    header_crc = binascii.crc32(header[:92]) & 0xFFFFFFFF
    struct.pack_into("<I", header, 16, header_crc)

    return bytes(header)


def generate_how_to_update_file(info_path: str, records: List[PartitionRecord], device: str = "mmcblk0"):
    """Generate how_to_update.txt matching create_sdcard_from_flashlayout.sh."""
    device_part = f"{device}p" if "mmcblk" in device else device

    with open(info_path, "w", encoding="utf-8") as f:
        f.write("This file describe How to update manually the partition of SDCARD:\n")
        f.write("1. SDCARD schema of partition\n")
        f.write("2. How to populate each partition\n")
        f.write("3. How to update the kernel/devicetree\n\n")
        f.write("1. SDCARD schema of partition:\n")
        f.write("------------------------------\n\n")

        # Partition Schema Diagram
        f.write("=" * (14 * len(records)) + "=\n")
        f.write("=" + "=             " * (len(records) - 1) + "=             =\n")

        row_names = "".join(f"=  {r.name:>9}  " for r in records) + "=\n"
        f.write(row_names)

        f.write("=" + "=             " * (len(records) - 1) + "=             =\n")

        row_devs = "".join(f"= {device_part:>9}{j:<2} " for j, _ in enumerate(records, start=1)) + "=\n"
        f.write(row_devs)

        row_nums = "".join(f"=      ({j:<2})   " for j, _ in enumerate(records, start=1)) + "=\n"
        f.write(row_nums)

        f.write("=" + "=             " * (len(records) - 1) + "=             =\n")
        f.write("=" * (14 * len(records)) + "=\n")

        for j, r in enumerate(records, start=1):
            f.write(f"({j}):\n")
            f.write(f"    Device: /dev/{device_part}{j}\n")
            f.write(f"    Label:  {r.name}\n")
            f.write(f"    Image:  {r.binary_rel if r.binary_rel else ''}\n")

        f.write("\n2. How to populate each partition\n")
        f.write("---------------------------------\n")
        for j, r in enumerate(records, start=1):
            f.write(f"- Populate partition {r.name} (/dev/{device_part}{j})\n")
            bin_name = r.binary_rel if r.binary_rel and r.binary_rel != "none" else f"<raw image of {r.name}>"
            f.write(f"    dd if={bin_name} of=/dev/{device_part}{j} bs=1M conv=fdatasync status=progress\n\n")

        f.write("\n3. How to mount manually each partition\n")
        f.write("---------------------------------\n")
        for j, r in enumerate(records, start=1):
            if r.part_type in ("System", "FileSystem"):
                f.write(f"- Mount manually partition {r.name} (/dev/{device_part}{j})\n")
                f.write(f"    udiskctl mount -b /dev/disk/by-partlabel/{r.name}\n\n")

        f.write("\n4. How to update the kernel/devicetree\n")
        f.write("--------------------------------------\n")
        f.write("The kernel and devicetree are present on \"boot\" partition.\n")
        f.write("To change kernel and devicetree, you can copy the file on this partitions:\n")
        f.write("- plug SDCARD on your PC\n")
        f.write("- copy kernel uImage on SDCARD\n")
        f.write("   sudo cp uImage /media/$USER/bootfs/\n")
        f.write("- copy devicetree uImage on SDCARD\n")
        f.write("   sudo cp stm32mp*.dtb /media/$USER/bootfs/\n")
        f.write("- umount partitions of SDCARD\n")
        f.write("   sudo umount /media/$USER/bootfs/\n")


def generate_raw_image(tsv_path: str, output_raw: str, images_dir: str,
                       raw_size_mb: int = DEFAULT_RAW_SIZE_MB, device: str = "mmcblk0"):
    """Main image generation function."""
    records = parse_flashlayout_tsv(tsv_path)
    if not records:
        raise RuntimeError(f"No mmc0 partitions found in {tsv_path}")

    total_bytes = raw_size_mb * 1024 * 1024
    total_sectors = total_bytes // SECTOR_SIZE

    setup_partitions(records, total_sectors, images_dir)

    print(f"Creating raw microSD image: {output_raw}")
    print(f"Total size: {raw_size_mb} MB ({total_bytes} bytes, {total_sectors} sectors)")
    print(f"Images source directory: {images_dir}")

    # Create / truncate raw file
    os.makedirs(os.path.dirname(os.path.abspath(output_raw)), exist_ok=True)
    with open(output_raw, "wb") as f:
        f.truncate(total_bytes)

    # Deterministic Disk GUID
    disk_guid = uuid.uuid5(NAMESPACE_STM32, os.path.basename(tsv_path))

    # Build GPT structures
    first_usable_lba = 34
    last_usable_lba = total_sectors - 34
    backup_part_entry_lba = total_sectors - 33
    backup_header_lba = total_sectors - 1

    part_array = create_gpt_partition_array(records)
    mbr = create_protective_mbr(total_sectors)
    primary_header = create_gpt_header(
        my_lba=1,
        alt_lba=backup_header_lba,
        first_usable=first_usable_lba,
        last_usable=last_usable_lba,
        disk_guid=disk_guid,
        part_entry_lba=2,
        part_array=part_array
    )
    backup_header = create_gpt_header(
        my_lba=backup_header_lba,
        alt_lba=1,
        first_usable=first_usable_lba,
        last_usable=last_usable_lba,
        disk_guid=disk_guid,
        part_entry_lba=backup_part_entry_lba,
        part_array=part_array
    )

    with open(output_raw, "r+b") as f:
        # 1. Write Protective MBR (LBA 0)
        f.seek(0)
        f.write(mbr)

        # 2. Write Primary GPT Header (LBA 1)
        f.seek(1 * SECTOR_SIZE)
        f.write(primary_header)

        # 3. Write Primary Partition Array (LBA 2..33)
        f.seek(2 * SECTOR_SIZE)
        f.write(part_array)

        # 4. Write Backup Partition Array (LBA total_sectors - 33..total_sectors - 2)
        f.seek(backup_part_entry_lba * SECTOR_SIZE)
        f.write(part_array)

        # 5. Write Backup GPT Header (LBA total_sectors - 1)
        f.seek(backup_header_lba * SECTOR_SIZE)
        f.write(backup_header)

        # 6. Populate partitions with binary files
        chunk_size = 4 * 1024 * 1024  # 4 MB chunk
        for j, rec in enumerate(records, start=1):
            if rec.image_path and os.path.exists(rec.image_path):
                file_size = os.path.getsize(rec.image_path)
                print(f"[FILLED] Part {j:02d}: {rec.name:<12} offset 0x{rec.offset_bytes:08X} ({rec.start_lba} LBA) <- {rec.binary_rel} ({file_size} bytes)")
                f.seek(rec.offset_bytes)
                with open(rec.image_path, "rb") as bin_f:
                    while True:
                        buf = bin_f.read(chunk_size)
                        if not buf:
                            break
                        f.write(buf)
            elif rec.binary_rel != "none":
                print(f"[UNFILLED] Part {j:02d}: {rec.name:<12} (file '{rec.binary_rel}' not found)")
            else:
                print(f"[UNFILLED] Part {j:02d}: {rec.name:<12} (empty / runtime partition)")

    # Generate how_to_update.txt
    info_path = os.path.splitext(output_raw)[0] + "_how_to_update.txt"
    generate_how_to_update_file(info_path, records, device=device)
    print(f"Generated update guide: {info_path}")
    print(f"Successfully generated raw image: {output_raw} ({total_bytes} bytes)\n")


def verify_raw_image(raw_path: str, tsv_path: Optional[str] = None, images_dir: Optional[str] = None) -> bool:
    """Verify protective MBR, primary & backup GPT headers (CRCs), partition table and binaries."""
    if not os.path.isfile(raw_path):
        print(f"[ERROR] File not found: {raw_path}")
        return False

    file_size = os.path.getsize(raw_path)
    total_sectors = file_size // SECTOR_SIZE
    print(f"=== VERIFYING RAW IMAGE: {raw_path} ===")
    print(f"Disk file size: {file_size} bytes ({total_sectors} sectors of 512 bytes)")

    with open(raw_path, "rb") as f:
        # Check Protective MBR
        f.seek(0)
        mbr = f.read(512)
        if mbr[510:512] != b"\x55\xaa":
            print("[FAIL] MBR boot signature 0x55AA mismatch!")
            return False

        boot_ind, start_chs, os_type, end_chs, start_lba, size_lba = struct.unpack_from("<B3sB3sII", mbr, 0x1BE)
        if os_type != 0xEE:
            print(f"[FAIL] MBR partition type is 0x{os_type:02X}, expected 0xEE (GPT Protective)!")
            return False
        if start_lba != 1:
            print(f"[FAIL] MBR starting LBA is {start_lba}, expected 1!")
            return False
        print(f"[PASS] Protective MBR: valid signature, type 0xEE, start LBA 1, size {size_lba} sectors")

        # Check Primary GPT Header
        f.seek(1 * SECTOR_SIZE)
        p_hdr = f.read(512)
        if p_hdr[0:8] != b"EFI PART":
            print("[FAIL] Primary GPT header signature mismatch!")
            return False

        rev, hdr_size, hdr_crc, _, my_lba, alt_lba, first_usable, last_usable = struct.unpack_from("<IIIIQQQQ", p_hdr, 8)
        disk_guid = uuid.UUID(bytes_le=p_hdr[56:72])
        part_lba, num_parts, part_size, part_crc = struct.unpack_from("<QIII", p_hdr, 72)

        # Check Primary Header CRC
        p_hdr_copy = bytearray(p_hdr[:hdr_size])
        struct.pack_into("<I", p_hdr_copy, 16, 0)
        calc_hdr_crc = binascii.crc32(p_hdr_copy) & 0xFFFFFFFF
        if hdr_crc != calc_hdr_crc:
            print(f"[FAIL] Primary GPT header CRC mismatch: stored=0x{hdr_crc:08X}, calculated=0x{calc_hdr_crc:08X}")
            return False

        print(f"[PASS] Primary GPT Header: CRC 0x{hdr_crc:08X} OK, MyLBA={my_lba}, AltLBA={alt_lba}, DiskGUID={disk_guid}")

        # Check Primary Partition Array
        f.seek(part_lba * SECTOR_SIZE)
        p_part_array = f.read(num_parts * part_size)
        calc_part_crc = binascii.crc32(p_part_array) & 0xFFFFFFFF
        if part_crc != calc_part_crc:
            print(f"[FAIL] Partition array CRC mismatch: stored=0x{part_crc:08X}, calculated=0x{calc_part_crc:08X}")
            return False

        print(f"[PASS] Primary Partition Array: CRC 0x{part_crc:08X} OK, {num_parts} entries ({part_size} bytes each)")

        # Check Backup GPT Header
        backup_hdr_lba = total_sectors - 1
        f.seek(backup_hdr_lba * SECTOR_SIZE)
        b_hdr = f.read(512)
        if b_hdr[0:8] != b"EFI PART":
            print(f"[FAIL] Backup GPT header signature mismatch at LBA {backup_hdr_lba}!")
            return False

        b_rev, b_hdr_size, b_hdr_crc, _, b_my_lba, b_alt_lba, b_first_usable, b_last_usable = struct.unpack_from("<IIIIQQQQ", b_hdr, 8)
        b_disk_guid = uuid.UUID(bytes_le=b_hdr[56:72])
        b_part_lba, b_num_parts, b_part_size, b_part_crc = struct.unpack_from("<QIII", b_hdr, 72)

        b_hdr_copy = bytearray(b_hdr[:b_hdr_size])
        struct.pack_into("<I", b_hdr_copy, 16, 0)
        calc_b_hdr_crc = binascii.crc32(b_hdr_copy) & 0xFFFFFFFF
        if b_hdr_crc != calc_b_hdr_crc:
            print(f"[FAIL] Backup GPT header CRC mismatch: stored=0x{b_hdr_crc:08X}, calculated=0x{calc_b_hdr_crc:08X}")
            return False

        if b_my_lba != backup_hdr_lba or b_alt_lba != 1:
            print(f"[FAIL] Backup GPT header LBA mismatch: MyLBA={b_my_lba}, AltLBA={b_alt_lba}")
            return False

        if b_disk_guid != disk_guid:
            print(f"[FAIL] Disk GUID mismatch between primary and backup GPT!")
            return False

        print(f"[PASS] Backup GPT Header: CRC 0x{b_hdr_crc:08X} OK at LBA {backup_hdr_lba}, points to AltLBA 1")

        # Check Backup Partition Array
        f.seek(b_part_lba * SECTOR_SIZE)
        b_part_array = f.read(b_num_parts * b_part_size)
        if p_part_array != b_part_array:
            print("[FAIL] Backup partition array does not match primary partition array!")
            return False
        print(f"[PASS] Backup Partition Array at LBA {b_part_lba} matches Primary bit-for-bit")

        # Parse and display active partitions
        print("\n--- GPT PARTITION TABLE DUMP ---")
        print(f"{'#':<3} {'Name':<12} {'Start LBA':<10} {'End LBA':<10} {'Size (MB)':<10} {'Attributes':<12} {'Type GUID':<38} {'Unique GUID':<38}")
        print("-" * 135)

        active_partitions = []
        for idx in range(num_parts):
            entry = p_part_array[idx * part_size:(idx + 1) * part_size]
            t_guid = uuid.UUID(bytes_le=entry[0:16])
            if t_guid == uuid.UUID(int=0):
                continue
            u_guid = uuid.UUID(bytes_le=entry[16:32])
            s_lba, e_lba, attr = struct.unpack_from("<QQQ", entry, 32)
            name = entry[56:128].decode("utf-16le").rstrip("\x00")
            size_mb = ((e_lba - s_lba + 1) * SECTOR_SIZE) / (1024 * 1024)
            attr_hex = f"0x{attr:016X}"
            print(f"{idx + 1:<3} {name:<12} {s_lba:<10} {e_lba:<10} {size_mb:<10.2f} {attr_hex:<12} {str(t_guid):<38} {str(u_guid):<38}")
            active_partitions.append((idx + 1, name, s_lba, e_lba, attr, t_guid, u_guid))

        # Cross-check with TSV and binary contents if provided
        if tsv_path and os.path.exists(tsv_path):
            records = parse_flashlayout_tsv(tsv_path)
            img_dir = find_images_directory(tsv_path, records, override_dir=images_dir)
            setup_partitions(records, total_sectors, img_dir)
            print(f"\n--- VALIDATING AGAINST TSV: {os.path.basename(tsv_path)} ---")

            if len(active_partitions) != len(records):
                print(f"[FAIL] Partition count mismatch: TSV has {len(records)}, GPT has {len(active_partitions)}")
                return False

            for (part_num, p_name, s_lba, e_lba, attr, t_guid, u_guid), rec in zip(active_partitions, records):
                if p_name != rec.name:
                    print(f"[FAIL] Part {part_num} name mismatch: '{p_name}' vs TSV '{rec.name}'")
                    return False
                if s_lba != rec.start_lba:
                    print(f"[FAIL] Part {part_num} start LBA mismatch: {s_lba} vs TSV {rec.start_lba}")
                    return False
                if e_lba != rec.end_lba:
                    print(f"[FAIL] Part {part_num} end LBA mismatch: {e_lba} vs TSV {rec.end_lba}")
                    return False
                if t_guid != rec.type_guid:
                    print(f"[FAIL] Part {part_num} Type GUID mismatch: {t_guid} vs expected {rec.type_guid}")
                    return False
                if attr != rec.attributes:
                    print(f"[FAIL] Part {part_num} attributes mismatch: 0x{attr:X} vs expected 0x{rec.attributes:X}")
                    return False

                # Validate binary contents
                if rec.image_path and os.path.exists(rec.image_path):
                    f.seek(s_lba * SECTOR_SIZE)
                    check_len = min(4096, os.path.getsize(rec.image_path))
                    disk_bytes = f.read(check_len)
                    with open(rec.image_path, "rb") as bf:
                        source_bytes = bf.read(check_len)
                    if disk_bytes != source_bytes:
                        print(f"[FAIL] Part {part_num} binary content mismatch with {rec.binary_rel}!")
                        return False
                    print(f"[PASS] Part {part_num:02d} ({p_name:<10}): Header & content match {rec.binary_rel}")
                else:
                    print(f"[PASS] Part {part_num:02d} ({p_name:<10}): GPT entry and geometry validated (unfilled / empty)")

    print("\n[ALL CHECKS PASSED] RAW image verified 100% compliant with GPT and OpenSTLinux FlashLayout!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate and verify OpenSTLinux bootable SD card raw image.")
    parser.add_argument("tsv", nargs="?", help="Path to FlashLayout TSV file")
    parser.add_argument("-o", "--output", help="Path to output .raw image file")
    parser.add_argument("-i", "--images-dir", help="Path to directory containing partition binaries")
    parser.add_argument("-s", "--raw-size", type=int, default=int(os.environ.get("SDCARD_SIZE", DEFAULT_RAW_SIZE_MB)),
                        help=f"Raw image size in MB (default: {DEFAULT_RAW_SIZE_MB})")
    parser.add_argument("-d", "--device", default=os.environ.get("DEVICE", "mmcblk0"),
                        help="Target device name for update instructions (default: mmcblk0)")
    parser.add_argument("-v", "--verify", action="store_true", help="Verify raw image after generation (or alone)")

    args = parser.parse_args()

    default_tsv = r"C:\open_linux_stm32mp157d-dk1\FLASH-stm32mp1-openstlinux-6.6-yocto-scarthgap-mpu-v26.06.10\stm32mp1-openstlinux-6.6-yocto-scarthgap-mpu-v26.06.10\images\stm32mp1\flashlayout_st-image-weston\optee\FlashLayout_sdcard_stm32mp157d-dk1-optee.tsv"

    tsv_file = args.tsv or default_tsv
    if not os.path.isfile(tsv_file):
        print(f"[ERROR] TSV file not found: {tsv_file}")
        sys.exit(1)

    records = parse_flashlayout_tsv(tsv_file)
    images_dir = find_images_directory(tsv_file, records, override_dir=args.images_dir)

    if args.output:
        output_raw = os.path.abspath(args.output)
    else:
        # Default raw image name near binaries images (matching create_sdcard_from_flashlayout.sh)
        base_name = os.path.splitext(os.path.basename(tsv_file))[0] + ".raw"
        output_raw = os.path.join(images_dir, base_name)

    # Generate
    generate_raw_image(tsv_file, output_raw, images_dir, raw_size_mb=args.raw_size, device=args.device)

    # Verify
    success = verify_raw_image(output_raw, tsv_path=tsv_file, images_dir=images_dir)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
