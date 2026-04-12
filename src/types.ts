/** A single grid column definition. */
export interface ColumnDef {
  /** Stable integer ID. Never reassigned or reused. */
  id: number;
  /** Machine-readable key matching IDRegistry.columns. */
  key: string;
  /** Display label shown in the column header. */
  label: string;
  /** Short display name for the column header (allows 2-line wrap). Falls back to `label`. */
  shortLabel?: string;
  /** Tooltip text on hover. Falls back to `label`. */
  tooltip?: string;
  /** ID of the GroupDef this column belongs to. */
  groupId: number;
  /** Data type of values in this column. */
  type: 'string' | 'number' | 'boolean';
  /** When true, cells in this column may render as hyperlinks (see ModelRecord.links). */
  linkable?: boolean;
  /** When set (> 0), cell values longer than this limit are clipped to (limit-1) chars + '…'. */
  truncateLimit?: number;
  /** When true, cells in this column render with a tinted background and bold font weight. */
  shaded?: boolean;
}

/** A collapsible group of columns. */
export interface GroupDef {
  /** Stable integer ID (0–7). */
  id: number;
  /** Machine-readable key. */
  key: string;
  /** Display label shown in the group header. */
  label: string;
  /** Render order (ascending). */
  order: number;
}

/** One row in the grid — one MSX model. */
export interface ModelRecord {
  /** Stable integer ID. Never reassigned or reused. */
  id: number;
  /**
   * Field values, positionally aligned with MSXData.columns[].
   * null means the value is unknown or not applicable.
   */
  values: (string | number | boolean | null)[];
  /**
   * Optional hyperlink URLs for linkable columns, keyed by column key.
   * Only present for models that have a known URL for that column.
   */
  links?: Record<string, string>;
}

/** The full dataset consumed by the web page at load time. */
export interface MSXData {
  /** Schema version integer. Increment on breaking schema changes. */
  version: number;
  /** ISO date string (YYYY-MM-DD) of when this file was generated. */
  generated: string;
  /** All column definitions, in display order. */
  columns: ColumnDef[];
  /** All group definitions. */
  groups: GroupDef[];
  /** All model records. Each model's values[] aligns with columns[]. */
  models: ModelRecord[];
  /**
   * Slot map LUT: maps each abbreviation to its full tooltip string.
   * Keyed by abbr (e.g. "MAIN", "SUB", "~"). Absent in legacy data files.
   */
  slotmap_lut?: Record<string, string>;
  /** Optional default view configuration. Undefined = show all, no sort, no filters. */
  defaultView?: DefaultViewConfig;
}

/** A saved view state applied when no URL hash is present. */
export interface DefaultViewConfig {
  /** Column ID to sort by, or null for no sort. */
  sortColumnId: number | null;
  /** Sort direction. */
  sortDirection: 'asc' | 'desc';
  /** Column IDs to hide by default. */
  hiddenColumnIds: number[];
  /** Group IDs to collapse by default. */
  collapsedGroupIds: number[];
}

/**
 * Full view state captured from the grid at any point in time.
 * All IDs are stable integer IDs (column IDs, model IDs, group IDs).
 * Suitable for binary encoding into a URL hash.
 */
export interface ViewState {
  /** Column ID to sort by, or null for no sort. */
  sortColumnId: number | null;
  /** Sort direction. Relevant only when sortColumnId is non-null. */
  sortDirection: 'asc' | 'desc';
  /** Group IDs that are currently collapsed. */
  collapsedGroupIds: Set<number>;
  /** Column IDs that are currently hidden. */
  hiddenColumnIds: Set<number>;
  /** Model IDs whose rows are currently hidden. */
  hiddenRowIds: Set<number>;
  /**
   * Active filters keyed by column ID.
   * Empty map = no filters.
   */
  filters: Map<number, string>;
  /**
   * Selected cells as "modelId:columnId" strings.
   * Column ID is the stable ColumnDef.id (not a positional index).
   */
  selectedCells: Set<string>;
}

/**
 * ID registry — used by the scraper, not shipped to the browser.
 * Documented here for TypeScript consumers (e.g. registry tests).
 */
export interface IDRegistry {
  /** Registry format version. */
  version: number;
  /**
   * Map of natural key → stable model ID.
   * Natural key format: "<manufacturer>|<model>" (lowercase, trimmed).
   */
  models: Record<string, number>;
  /** Model IDs that have been retired (model removed from the dataset). */
  retired_models: number[];
  /** Next model ID to assign (always > max assigned model ID). */
  next_model_id: number;
  /**
   * Map of column key → stable column ID.
   * Column keys are fixed; assigned once and never changed.
   */
  columns: Record<string, number>;
  /** Next column ID to assign (always > max assigned column ID). */
  next_column_id: number;
}

declare global {
  interface Window {
    MSX_DATA: MSXData;
  }
}
