## 2025-05-19 - Keyboard Navigation and Focus Trapping in Tkinter Autocomplete Dropdowns
**Learning:** For Tkinter entry components with popup suggestion listboxes, binding `<Down>` and `<Escape>` keys with explicit focus transfer (`focus_set()`) and returning `"break"` prevents unhandled key propagation and enables full keyboard accessibility without mouse interaction.
**Action:** Always bind `<Down>` on entry inputs to focus suggestion listboxes and `<Escape>` on both entry and listbox widgets to dismiss popups cleanly.

## 2025-05-18 - Tkinter Event Binding Chaining for Tooltips
**Learning:** In Tkinter components, binding hover events (`<Enter>`, `<Leave>`) without `add="+"` overwrites existing bindings on the widget, causing attached components like `ToolTip` to fail to open.
**Action:** Always specify `add="+"` when adding event listeners to shared widget components so multiple handlers (e.g., hover color transitions and tooltips) can chain cleanly.
