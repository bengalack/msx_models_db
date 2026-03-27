/** A single grid column definition. */
export interface ColumnDef {
  /** Stable integer ID. Never reassigned or reused. */
  id: number;
  /** Machine-readable key matching IDRegistry.columns. */
  key: string;
  /** Display label shown in the column header. */
  label: string;
  /** ID of the GroupDef this column belongs to. */
  groupId: number;
  /** Data type of values in this column. */
  type: 'string' | 'number' | 'boolean';
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
