/**
 * Tests for the Share button in the toolbar.
 *
 * The Share button (fa-arrow-up-from-bracket icon) copies the current URL to
 * the clipboard. A toast pill appears below the button for 3 seconds.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { buildToolbar } from '../../src/toolbar.js';

const TOAST_DURATION_MS = 3000;

// Helper: build a toolbar with all no-op callbacks
function makeToolbar(onShare: () => void = () => {}) {
  return buildToolbar(
    () => {}, // onFiltersToggle
    () => {}, // onColsToggle
    () => {}, // onResetView
    () => {}, // onHeadersCopyToggle
    onShare,  // onShare  ← new param (5th)
    () => {}, // onHelpToggle
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe('Share button', () => {
  it('renders a button containing the fa-arrow-up-from-bracket icon', () => {
    // No timers involved — DOM-only assertion, no vi.useFakeTimers() needed
    const { element } = makeToolbar();
    const icon = element.querySelector('i.fa-arrow-up-from-bracket');
    expect(icon).not.toBeNull();
  });

  it('calls onShare when the share button is clicked', () => {
    vi.useFakeTimers();
    const onShare = vi.fn();
    const { shareBtn } = makeToolbar(onShare);
    shareBtn.click();
    expect(onShare).toHaveBeenCalledOnce();
  });

  it('adds share-toast--visible to the toast immediately on click', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(true);
  });

  it('removes share-toast--visible from the toast after 3000 ms', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    vi.advanceTimersByTime(TOAST_DURATION_MS);
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(false);
  });

  it('toast is still visible at 2999 ms', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    vi.advanceTimersByTime(TOAST_DURATION_MS - 1);
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(true);
  });
});
