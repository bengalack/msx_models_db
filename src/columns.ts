import type { ColumnDef, GroupDef } from './types.js';

export const GROUPS: GroupDef[] = [
  { id: 0, key: 'identity',  label: 'Identity',     order: 0 },
  { id: 1, key: 'memory',    label: 'Memory',        order: 1 },
  { id: 2, key: 'video',     label: 'Video',         order: 2 },
  { id: 3, key: 'audio',     label: 'Audio',         order: 3 },
  { id: 4, key: 'media',     label: 'Media',         order: 4 },
  { id: 5, key: 'cpu',       label: 'CPU/Chipsets',  order: 5 },
  { id: 6, key: 'other',     label: 'Other',         order: 6 },
  { id: 7, key: 'emulation', label: 'Emulation',     order: 7 },
];

export const COLUMNS: ColumnDef[] = [
  // Identity (groupId: 0)
  { id:  1, key: 'manufacturer',    label: 'Manufacturer',       groupId: 0, type: 'string' },
  { id:  2, key: 'model',           label: 'Model',              groupId: 0, type: 'string' },
  { id:  3, key: 'year',            label: 'Year',               groupId: 0, type: 'number' },
  { id:  4, key: 'region',          label: 'Region/Market',      groupId: 0, type: 'string' },
  { id:  5, key: 'standard',        label: 'MSX Standard',       groupId: 0, type: 'string' },
  { id:  6, key: 'form_factor',     label: 'Form Factor',        groupId: 0, type: 'string' },
  // Memory (groupId: 1)
  { id:  7, key: 'main_ram_kb',     label: 'Main RAM (KB)',      groupId: 1, type: 'number' },
  { id:  8, key: 'vram_kb',         label: 'VRAM (KB)',          groupId: 1, type: 'number' },
  { id:  9, key: 'rom_kb',          label: 'ROM/BIOS (KB)',      groupId: 1, type: 'number' },
  { id: 10, key: 'mapper',          label: 'Mapper',             groupId: 1, type: 'string' },
  // Video (groupId: 2)
  { id: 11, key: 'vdp',             label: 'VDP',                groupId: 2, type: 'string' },
  { id: 12, key: 'max_resolution',  label: 'Max Resolution',     groupId: 2, type: 'string' },
  { id: 13, key: 'max_colors',      label: 'Max Colors',         groupId: 2, type: 'number' },
  { id: 14, key: 'max_sprites',     label: 'Max Sprites',        groupId: 2, type: 'number' },
  // Audio (groupId: 3)
  { id: 15, key: 'psg',             label: 'PSG',                groupId: 3, type: 'string' },
  { id: 16, key: 'fm_chip',         label: 'FM Chip',            groupId: 3, type: 'string' },
  { id: 17, key: 'audio_channels',  label: 'Audio Channels',     groupId: 3, type: 'number' },
  // Media (groupId: 4)
  { id: 18, key: 'floppy_drives',   label: 'Floppy Drive(s)',    groupId: 4, type: 'string' },
  { id: 19, key: 'cartridge_slots', label: 'Cartridge Slots',    groupId: 4, type: 'number' },
  { id: 20, key: 'tape_interface',  label: 'Tape Interface',     groupId: 4, type: 'string' },
  { id: 21, key: 'other_storage',   label: 'Other Storage',      groupId: 4, type: 'string' },
  // CPU/Chipsets (groupId: 5)
  { id: 22, key: 'cpu',             label: 'CPU',                groupId: 5, type: 'string' },
  { id: 23, key: 'cpu_speed_mhz',   label: 'CPU Speed (MHz)',    groupId: 5, type: 'number' },
  { id: 24, key: 'sub_cpu',         label: 'Sub-CPU',            groupId: 5, type: 'string' },
  // Other (groupId: 6)
  { id: 25, key: 'keyboard_layout', label: 'Keyboard Layout',    groupId: 6, type: 'string' },
  { id: 26, key: 'built_in_software', label: 'Built-in Software', groupId: 6, type: 'string' },
  { id: 27, key: 'connectivity',    label: 'Connectivity/Ports', groupId: 6, type: 'string' },
  // Emulation (groupId: 7)
  { id: 28, key: 'openmsx_id',      label: 'openMSX Machine ID', groupId: 7, type: 'string' },
  { id: 29, key: 'fpga_support',    label: 'FPGA/MiSTer Support', groupId: 7, type: 'string' },
];
