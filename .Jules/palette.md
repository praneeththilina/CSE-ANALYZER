## 2025-05-18 - Tkinter Event Binding Chaining for Tooltips
**Learning:** In Tkinter components, binding hover events (`<Enter>`, `<Leave>`) without `add="+"` overwrites existing bindings on the widget, causing attached components like `ToolTip` to fail to open.
**Action:** Always specify `add="+"` when adding event listeners to shared widget components so multiple handlers (e.g., hover color transitions and tooltips) can chain cleanly.
