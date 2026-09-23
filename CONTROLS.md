# Sprite Drawer Controls

> **Mac users:** wherever this guide says **Ctrl**, press **Cmd** (⌘) instead.

## Create a new sprite

1. Click **File → New…** (or press **Ctrl+N**).
2. Type a **Width** and **Height** in pixels (for example 32 × 32), then click **OK**.
3. Draw! Left-click paints with your main color; right-click paints with your second color.
4. Save with **File → Save** (**Ctrl+S**). Sprites save as **PNG** files, ready
   for Unity, into the project's **`sprites`** folder unless you pick another.

To keep working on a sprite later, use **File → Open…** (**Ctrl+O**) and pick
its PNG (Open also starts in the `sprites` folder).

## Add an underlay (trace over a photo)

An underlay is a photo shown *under* your pixels so you can trace it. It is
never saved into your sprite.

1. In the **Trace Underlay** panel on the right, click **Load Photo…**
   (or press **Ctrl+R**). It opens the project's **`src_img`** folder, so
   putting your photos there saves hunting. iPhone photos (HEIC), JPG, PNG,
   and PDF all work.
2. The photo is automatically fitted to your sprite. Adjust it with:
   - **Photo opacity**: how see-through the photo is.
   - **Scale**: make the photo bigger or smaller.
   - **Offset X / Offset Y**: slide the photo left/right and up/down.
   - **Sprite opacity**: fade your own pixels so the photo shows through.
   - **Fit to Canvas**: snap the photo back to fit the sprite.
   - **Show underlay**: turn the photo on and off. **Clear** removes it.
3. Press **U** (Underlay Pick) and click a pixel to grab the photo's color
   there, then press **P** and paint with it.

When you save, the photo setup is remembered in a `.sprite.json` file next to
your PNG. Keep the two files together, and don't move or rename the photo.

## Drawing tools

| Key | Tool |
|---|---|
| **P** | Pencil |
| **E** | Eraser |
| **F** | Fill (paint bucket) |
| **L** | Line |
| **R** | Rectangle |
| **Shift+R** | Filled rectangle |
| **O** | Ellipse (circle) |
| **Shift+O** | Filled ellipse |
| **I** | Eyedropper (grab a color from your sprite) |
| **U** | Underlay Pick (grab a color from the photo) |

The **Size** box under the tools sets the pencil/eraser thickness.

## Colors

- Click the big color squares in the **Colors** panel to open a color wheel.
- Left-click a palette swatch to set your main color; right-click to set your second color.
- Type a hex code (like `#FF8800`) into the hex box for an exact color.
- **X** swaps your main and second colors.

## Moving around

| Control | Action |
|---|---|
| **Ctrl + mouse wheel** (Mac: **Cmd + two-finger scroll**) | Zoom in/out |
| **Ctrl + plus** / **Ctrl + minus** | Zoom in/out |
| **Ctrl+0** | Fit the sprite to the window |
| Hold **Space** and drag, or drag with the **middle mouse button** | Move the view |

## View

| Key | Action |
|---|---|
| **G** | Cycle the background: grid → checkerboard → plain gray |
| **Tab** | Preview: see only your sprite, as it will look in a game |
| **H** | Hide/show your drawn pixels (to see the photo clearly) |

## Undo and editing

| Key | Action |
|---|---|
| **Ctrl+Z** | Undo |
| **Ctrl+Shift+Z** | Redo |
| **Ctrl+Shift+K** | Clear the whole canvas |
