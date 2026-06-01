# Simulator Feature Fixes - TODO

## Remaining Items (from docs review)

### 5. DOM: Size bars and Last Trade indicator
- Add visual size bars (proportional width) to DOM bid/ask levels
- Add a "last trade" marker showing where the most recent fill occurred

### 6. Tooltip popups - use themed dark popups
- All title/tooltip attributes currently show browser default yellow popups
- Replace with custom dark-themed tooltip (position:absolute, dark bg, orange border)

### 7. Gann Fan drawing tool
- Currently renders as a rectangle with lines
- Should draw radiating lines from anchor point at Gann angles (1x1, 2x1, 3x1, 4x1, 1x2, 1x3, 1x4)
- Needs proper angle calculation based on price/time ratio

### 8. Channel tool - independent skewing
- Currently only horizontal
- Should allow dragging each endpoint independently to create angled/skewed channels
- Two parallel lines where each can be tilted

### 9. Right-click property editor for drawings
- Right-clicking a drawing should open a small popup/modal
- Properties: color, line width, line style (solid/dashed/dotted), delete
- Currently no right-click behavior on drawings

### 10. Ctrl+scroll zoom price axis
- Currently Ctrl+scroll zooms time axis (same as regular scroll)
- Should zoom the price (Y) axis instead
- Regular scroll = time axis zoom, Ctrl+scroll = price axis zoom

### 11. Loading spinner when loading saved session
- When clicking a saved session card, show the chart overlay spinner
- The session regeneration takes time (fetches from server)
- Currently no visual feedback during load
