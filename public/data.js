// MSX Models DB — seed data (hand-curated, approximate specs)
// Generated: 2026-03-27
// This file is copied to docs/data.js by Vite on each build.
// The scraper (python -m scraper) overwrites docs/data.js with accurate data.
//
// values[] column order matches src/columns.ts COLUMNS array (IDs 1–29):
//  0  manufacturer       1  model              2  year
//  3  region             4  standard           5  form_factor
//  6  main_ram_kb        7  vram_kb            8  rom_kb
//  9  mapper             10 vdp                11 max_resolution
//  12 max_colors         13 max_sprites        14 psg
//  15 fm_chip            16 audio_channels     17 floppy_drives
//  18 cartridge_slots    19 tape_interface     20 other_storage
//  21 cpu                22 cpu_speed_mhz      23 sub_cpu
//  24 keyboard_layout    25 built_in_software  26 connectivity
//  27 openmsx_id         28 fpga_support

window.MSX_DATA = {
  version: 1,
  generated: "2026-03-27",
  groups: [
    { id: 0, key: "identity",  label: "Identity",     order: 0 },
    { id: 1, key: "memory",    label: "Memory",        order: 1 },
    { id: 2, key: "video",     label: "Video",         order: 2 },
    { id: 3, key: "audio",     label: "Audio",         order: 3 },
    { id: 4, key: "media",     label: "Media",         order: 4 },
    { id: 5, key: "cpu",       label: "CPU/Chipsets",  order: 5 },
    { id: 6, key: "other",     label: "Other",         order: 6 },
    { id: 7, key: "emulation", label: "Emulation",     order: 7 }
  ],
  columns: [
    { id:  1, key: "manufacturer",     label: "Manufacturer",       groupId: 0, type: "string" },
    { id:  2, key: "model",            label: "Model",              groupId: 0, type: "string", linkable: true },
    { id:  3, key: "year",             label: "Year",               groupId: 0, type: "number" },
    { id:  4, key: "region",           label: "Region",             groupId: 0, type: "string" },
    { id:  5, key: "standard",         label: "MSX Standard",       groupId: 0, type: "string" },
    { id:  6, key: "form_factor",      label: "Form Factor",        groupId: 0, type: "string" },
    { id:  7, key: "main_ram_kb",      label: "Main RAM (KB)",      shortLabel: "Main RAM",      tooltip: "Main RAM (KB)",      groupId: 1, type: "number" },
    { id:  8, key: "vram_kb",          label: "VRAM (KB)",          shortLabel: "VRAM",           tooltip: "VRAM (KB)",          groupId: 1, type: "number" },
    { id:  9, key: "rom_kb",           label: "ROM/BIOS (KB)",      shortLabel: "ROM/ BIOS",      tooltip: "ROM/BIOS (KB)",      groupId: 1, type: "number" },
    { id: 10, key: "mapper",           label: "Mapper",             groupId: 1, type: "string" },
    { id: 11, key: "vdp",              label: "VDP",                groupId: 2, type: "string" },
    { id: 12, key: "max_resolution",   label: "Max Resolution",     shortLabel: "Max Res",        tooltip: "Max Resolution",     groupId: 2, type: "string" },
    { id: 13, key: "max_colors",       label: "Max Colors",         shortLabel: "Max Clrs",       tooltip: "Max Colors",         groupId: 2, type: "number" },
    { id: 14, key: "max_sprites",      label: "Max Sprites",        shortLabel: "Max Sprt",       tooltip: "Max Sprites",        groupId: 2, type: "number" },
    { id: 15, key: "psg",              label: "PSG",                groupId: 3, type: "string" },
    { id: 16, key: "fm_chip",          label: "FM Chip",            groupId: 3, type: "string" },
    { id: 17, key: "audio_channels",   label: "Audio Channels",     shortLabel: "PSG Chnls",      tooltip: "PSG Channels",       groupId: 3, type: "number" },
    { id: 18, key: "floppy_drives",    label: "Floppy Drive(s)",    shortLabel: "Floppy Drv",     tooltip: "Floppy Drive(s)",    groupId: 4, type: "string" },
    { id: 19, key: "cartridge_slots",  label: "Cartridge Slots",    shortLabel: "Cart Slots",     tooltip: "Cartridge Slots",    groupId: 4, type: "number" },
    { id: 20, key: "tape_interface",   label: "Tape Interface",     shortLabel: "Tape I/F",       tooltip: "Tape Interface",     groupId: 4, type: "string" },
    { id: 21, key: "other_storage",    label: "Other Storage",      shortLabel: "Other Stor",     tooltip: "Other Storage",      groupId: 4, type: "string" },
    { id: 22, key: "cpu",              label: "CPU",                groupId: 5, type: "string" },
    { id: 23, key: "cpu_speed_mhz",    label: "CPU Speed (MHz)",    shortLabel: "CPU MHz",        tooltip: "CPU Speed (MHz)",    groupId: 5, type: "number" },
    { id: 24, key: "sub_cpu",          label: "Sub-CPU",            groupId: 5, type: "string" },
    { id: 25, key: "keyboard_layout",  label: "Keyboard Layout",    shortLabel: "KB Layout",      tooltip: "Keyboard Layout",    groupId: 6, type: "string" },
    { id: 26, key: "built_in_software",label: "Built-in Software",  shortLabel: "Built-in SW",   tooltip: "Built-in Software",  groupId: 6, type: "string" },
    { id: 27, key: "connectivity",     label: "Connectivity/Ports", shortLabel: "Conn/ Ports",    tooltip: "Connectivity/Ports", groupId: 6, type: "string" },
    { id: 28, key: "openmsx_id",       label: "openMSX Machine ID", shortLabel: "openMSX ID",     tooltip: "openMSX Machine ID", groupId: 7, type: "string" },
    { id: 29, key: "fpga_support",     label: "FPGA/MiSTer Support",shortLabel: "FPGA/ MiSTer",  tooltip: "FPGA/MiSTer Support",groupId: 7, type: "string" }
  ],
  models: [
    // id=1  Sony HB-75P (MSX2, Europe, 1985)
    // values[]: manufacturer, model, year, region, standard, form_factor,
    //           main_ram_kb, vram_kb, rom_kb, mapper,
    //           vdp, max_resolution, max_colors, max_sprites,
    //           psg, fm_chip, audio_channels,
    //           floppy_drives, cartridge_slots, tape_interface, other_storage,
    //           cpu, cpu_speed_mhz, sub_cpu,
    //           keyboard_layout, built_in_software, connectivity,
    //           openmsx_id, fpga_support
    { id: 1, links: { model: "https://www.msx.org/wiki/Sony_HB-75P" }, values: [
      "Sony", "HB-75P", 1985, "Europe", "MSX2", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9938", "512×424", 512, 32,
      "AY-3-8910", null, 3,
      null, 2, "Yes", null,
      "Z80A", 3.58, null,
      "QWERTY", null, "RGB, Composite, RF",
      "Sony_HB-75P", null
    ]},
    // id=2  Philips VG-8235/00 (MSX2, Netherlands, 1985)
    { id: 2, links: { model: "https://www.msx.org/wiki/Philips_VG-8235" }, values: [
      "Philips", "VG-8235/00", 1985, "Netherlands", "MSX2", "Desktop",
      128, 128, 48, "ASCII 16K",
      "V9938", "512×424", 512, 32,
      "AY-3-8910", null, 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "QWERTY", null, "RGB, Composite, RF",
      "Philips_VG-8235", null
    ]},
    // id=3  Panasonic FS-A1 (MSX2, Japan, 1986)
    { id: 3, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1" }, values: [
      "Panasonic", "FS-A1", 1986, "Japan", "MSX2", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9938", "512×424", 512, 32,
      "AY-3-8910", null, 3,
      null, 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Panasonic_FS-A1", null
    ]},
    // id=4  Panasonic FS-A1F (MSX2, Japan, 1987)
    { id: 4, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1F" }, values: [
      "Panasonic", "FS-A1F", 1987, "Japan", "MSX2", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9938", "512×424", 512, 32,
      "AY-3-8910", null, 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Panasonic_FS-A1F", null
    ]},
    // id=5  Toshiba HX-33 (MSX2, Japan, 1986)
    { id: 5, links: { model: "https://www.msx.org/wiki/Toshiba_HX-33" }, values: [
      "Toshiba", "HX-33", 1986, "Japan", "MSX2", "Desktop",
      128, 128, 48, "ASCII 16K",
      "V9938", "512×424", 512, 32,
      "AY-3-8910", null, 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Toshiba_HX-33", null
    ]},
    // id=6  Sony HB-F1XDJ (MSX2+, Japan, 1988)
    { id: 6, links: { model: "https://www.msx.org/wiki/Sony_HB-F1XDJ" }, values: [
      "Sony", "HB-F1XDJ", 1988, "Japan", "MSX2+", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9958", "512×424", 19268, 32,
      "AY-3-8910", "YM2413 (OPLL)", 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Sony_HB-F1XDJ", null
    ]},
    // id=7  Panasonic FS-A1WX (MSX2+, Japan, 1988)
    { id: 7, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1WX" }, values: [
      "Panasonic", "FS-A1WX", 1988, "Japan", "MSX2+", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9958", "512×424", 19268, 32,
      "AY-3-8910", "YM2413 (OPLL)", 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Panasonic_FS-A1WX", null
    ]},
    // id=8  Panasonic FS-A1WSX (MSX2+, Japan, 1989)
    { id: 8, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1WSX" }, values: [
      "Panasonic", "FS-A1WSX", 1989, "Japan", "MSX2+", "Desktop",
      64, 128, 48, "ASCII 16K",
      "V9958", "512×424", 19268, 32,
      "AY-3-8910", "YM2413 (OPLL)", 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "Z80A", 3.58, null,
      "JIS", null, "RGB, Composite, RF",
      "Panasonic_FS-A1WSX", null
    ]},
    // id=9  Panasonic FS-A1ST (turboR, Japan, 1990)
    { id: 9, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1ST" }, values: [
      "Panasonic", "FS-A1ST", 1990, "Japan", "turboR", "Desktop",
      256, 128, 48, "ASCII 16K",
      "V9958", "512×424", 19268, 32,
      "AY-3-8910", "YM2413 (OPLL)", 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "R800", 7.16, "Z80A (compatibility)",
      "JIS", null, "RGB, Composite, RF",
      "Panasonic_FS-A1ST", null
    ]},
    // id=10  Panasonic FS-A1GT (turboR, Japan, 1991)
    { id: 10, links: { model: "https://www.msx.org/wiki/Panasonic_FS-A1GT" }, values: [
      "Panasonic", "FS-A1GT", 1991, "Japan", "turboR", "Desktop",
      512, 128, 48, "ASCII 16K",
      "V9958", "512×424", 19268, 32,
      "AY-3-8910", "YM2413 (OPLL)", 3,
      "1× 3.5\" DD", 2, "Yes", null,
      "R800", 7.16, "Z80A (compatibility)",
      "JIS", "MIDI interface", "RGB, Composite, RF, MIDI",
      "Panasonic_FS-A1GT", null
    ]}
  ]
};
