"""Server-side display snapshot renderer.

Faithfully replicates the composited display output from display.html using Pillow.
Produces 1920x1080 (or target_aspect_ratio) PNG snapshots showing exactly how an
image or group would appear on the photo frame display.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


# ---------------------------------------------------------------------------
# Helpers ported from display.html JS
# ---------------------------------------------------------------------------

def parse_aspect_ratio(ratio_str):
    """Parse '16:9' → (16, 9) and compute screen dimensions at 1080p scale."""
    try:
        w, h = ratio_str.split(':')
        w, h = int(w), int(h)
    except (ValueError, AttributeError):
        w, h = 16, 9
    # Scale so the larger dimension is 1920 or 1080
    if w >= h:
        screen_w = 1920
        screen_h = round(1920 * h / w)
    else:
        screen_h = 1080
        screen_w = round(1080 * w / h)
    return screen_w, screen_h


def hex_to_rgb(hex_color):
    """'#ff00aa' or '#f0a' → (255, 0, 170)."""
    h = (hex_color or '#ffffff').lstrip('#')
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) != 6:
        return (255, 255, 255)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def get_bevel_colors(mat_hex):
    """Port of getBevelColors — derive inner gradient alpha from luminance.

    Returns inner_alpha (float). Outer is always 0.0 (transparent).
    """
    r, g, b = hex_to_rgb(mat_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return 0.30 if luminance < 0.5 else 0.20


def get_grid_layout(count):
    """Port of getGridLayout."""
    if count <= 3:
        return count, 1
    cols = _ceil_sqrt(count)
    rows = -(-count // cols)  # ceil division
    return cols, rows


def _ceil_sqrt(n):
    import math
    return math.ceil(math.sqrt(n))


def calculate_mat_padding(img_w, img_h, effect_space, screen_w, screen_h):
    """Port of calculateMatPadding.

    Returns (photo_w, photo_h) — the pixel size the photo should be rendered at.
    """
    if not img_w or not img_h:
        return 0, 0

    img_ratio = img_w / img_h
    effect2 = (effect_space or 0) * 2
    is_portrait = img_h > img_w

    if is_portrait:
        max_photo_h = min(screen_h * 0.80, screen_h - effect2)
        max_photo_w = min(screen_w - effect2, screen_w * 0.95)
    else:
        max_photo_w = min(screen_w * 0.80, screen_w - effect2)
        max_photo_h = min(screen_h - effect2, screen_h * 0.95)

    if max_photo_w <= 0 or max_photo_h <= 0:
        return 0, 0

    if img_ratio > max_photo_w / max_photo_h:
        photo_w = max_photo_w
        photo_h = max_photo_w / img_ratio
    else:
        photo_h = max_photo_h
        photo_w = max_photo_h * img_ratio

    return round(photo_w), round(photo_h)


# ---------------------------------------------------------------------------
# Effect drawing
# ---------------------------------------------------------------------------

def draw_bevel(image, bevel_width, mat_color):
    """Wrap *image* in a bevel frame. Returns a new RGBA image.

    Ports wrapInBevel: four gradient trapezoid strips around the image,
    plus a subtle inner shadow.
    """
    bw = bevel_width
    if bw <= 0:
        return image.convert('RGBA')

    img = image.convert('RGBA')
    iw, ih = img.size
    fw, fh = iw + 2 * bw, ih + 2 * bw

    mat_rgb = hex_to_rgb(mat_color)
    inner_alpha = get_bevel_colors(mat_color)

    # Start with mat-colored background
    frame = Image.new('RGBA', (fw, fh), mat_rgb + (255,))
    # Paste photo in centre
    frame.paste(img, (bw, bw), img)

    # Draw four gradient strips as overlays
    overlay = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))

    # Each strip: define polygon, then fill with a gradient from outer (alpha=0)
    # to inner (alpha=inner_alpha) in the direction perpendicular to the image edge.
    strips = [
        # top strip
        {'poly': [(0, 0), (fw, 0), (fw - bw, bw), (bw, bw)], 'direction': 'down'},
        # bottom strip
        {'poly': [(bw, fh - bw), (fw - bw, fh - bw), (fw, fh), (0, fh)], 'direction': 'up'},
        # left strip
        {'poly': [(0, 0), (bw, bw), (bw, fh - bw), (0, fh)], 'direction': 'right'},
        # right strip
        {'poly': [(fw - bw, bw), (fw, 0), (fw, fh), (fw - bw, fh - bw)], 'direction': 'left'},
    ]

    for strip in strips:
        _draw_gradient_strip(overlay, strip['poly'], strip['direction'],
                             bw, fw, fh, inner_alpha)

    frame = Image.alpha_composite(frame, overlay)

    # Subtle inner shadow (::after pseudo-element: inset 0 1px 2px rgba(0,0,0,0.08))
    shadow_overlay = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))
    # Create a small dark rectangle at the inner edge, blur it, then mask to inner area
    inner_rect = Image.new('L', (iw, ih), 0)
    # Thin dark line at top of image area
    draw = ImageDraw.Draw(inner_rect)
    draw.rectangle([0, 0, iw - 1, 2], fill=int(255 * 0.08))
    inner_rect = inner_rect.filter(ImageFilter.GaussianBlur(radius=1))
    shadow_layer = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))
    # Convert alpha mask to RGBA shadow
    shadow_img = Image.new('RGBA', (iw, ih), (0, 0, 0, 0))
    shadow_img.putalpha(inner_rect)
    shadow_layer.paste(shadow_img, (bw, bw), shadow_img)
    frame = Image.alpha_composite(frame, shadow_layer)

    return frame


def _draw_gradient_strip(overlay, poly, direction, bw, fw, fh, inner_alpha):
    """Draw a single gradient trapezoid strip onto overlay."""
    if bw <= 0:
        return

    # Create a mask for the polygon shape
    mask = Image.new('L', (fw, fh), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(poly, fill=255)

    # Create the gradient (alpha ramp from 0 at outer edge to inner_alpha at inner edge)
    gradient = Image.new('L', (fw, fh), 0)

    if direction == 'down':
        # Top strip: row 0 = 0 alpha, row bw = inner_alpha
        for y in range(bw):
            alpha = int(255 * inner_alpha * y / bw)
            ImageDraw.Draw(gradient).line([(0, y), (fw - 1, y)], fill=alpha)
    elif direction == 'up':
        # Bottom strip: row fh-bw = inner_alpha, row fh = 0
        for y in range(bw):
            alpha = int(255 * inner_alpha * (bw - y) / bw)
            row = fh - bw + y
            ImageDraw.Draw(gradient).line([(0, row), (fw - 1, row)], fill=alpha)
    elif direction == 'right':
        # Left strip: col 0 = 0 alpha, col bw = inner_alpha
        for x in range(bw):
            alpha = int(255 * inner_alpha * x / bw)
            ImageDraw.Draw(gradient).line([(x, 0), (x, fh - 1)], fill=alpha)
    elif direction == 'left':
        # Right strip: col fw-bw = inner_alpha, col fw = 0
        for x in range(bw):
            alpha = int(255 * inner_alpha * (bw - x) / bw)
            col = fw - bw + x
            ImageDraw.Draw(gradient).line([(col, 0), (col, fh - 1)], fill=alpha)

    # Combine: gradient masked to the polygon shape, as black with variable alpha
    strip = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))
    # The strip is black (shadow) with alpha = gradient * mask
    combined_alpha = Image.new('L', (fw, fh), 0)
    # Multiply gradient and mask pixel-by-pixel
    from PIL import ImageChops
    combined_alpha = ImageChops.multiply(gradient, mask)
    strip.putalpha(combined_alpha)
    # Composite onto overlay
    overlay.paste(Image.alpha_composite(
        Image.new('RGBA', (fw, fh), (0, 0, 0, 0)),
        strip
    ), (0, 0))
    # Actually we need to composite onto the existing overlay
    # Re-do: composite strip onto overlay in-place
    temp = Image.alpha_composite(overlay, strip)
    overlay.paste(temp)


def draw_shadow(image, shadow_size):
    """Wrap *image* in a drop shadow. Returns a new RGBA image.

    Ports getShadowStyle: 0 {yOffset}px {blur}px {spread}px rgba(0,0,0,0.35)
    """
    if shadow_size <= 0:
        return image.convert('RGBA')

    img = image.convert('RGBA')
    iw, ih = img.size

    blur = shadow_size * 2
    spread = round(shadow_size * 0.5)
    y_offset = round(shadow_size * 0.5)

    # Padding around the image to fit the shadow
    pad = int(blur + spread + abs(y_offset)) + 4
    canvas_w = iw + 2 * pad
    canvas_h = ih + 2 * pad

    # Shadow: a dark rectangle the size of image + spread, offset, blurred
    shadow = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_rect = Image.new('L', (iw + 2 * spread, ih + 2 * spread), int(255 * 0.35))
    shadow_rgba = Image.new('RGBA', shadow_rect.size, (0, 0, 0, 0))
    shadow_rgba.putalpha(shadow_rect)

    sx = pad - spread
    sy = pad - spread + y_offset
    shadow.paste(shadow_rgba, (sx, sy), shadow_rgba)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur / 2))

    # Composite image on top of shadow
    shadow.paste(img, (pad, pad), img)
    return shadow, pad  # return pad so caller can account for it


def apply_effect(image, effect_size, mat_color, border_effect):
    """Apply bevel or shadow to an image. Returns (RGBA image, padding).

    Padding is 0 for bevel (bevel is part of the frame), or the shadow pad.
    """
    if effect_size <= 0:
        return image.convert('RGBA'), 0

    if border_effect == 'shadow':
        result, pad = draw_shadow(image, effect_size)
        return result, pad
    else:
        return draw_bevel(image, effect_size, mat_color), 0


# ---------------------------------------------------------------------------
# Texture overlays
# ---------------------------------------------------------------------------

def create_texture_tile(finish):
    """Create a small repeating tile matching the JS SVG texture patterns.

    Returns (PIL Image RGBA, opacity) or (None, 0) for 'flat'.
    """
    if finish == 'eggshell':
        # 4x4 tile with small dots
        tile = Image.new('RGBA', (4, 4), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        # Approximate the SVG circles as single pixels at the circle centres
        for cx, cy in [(1, 1), (3, 3), (3, 0), (0, 2)]:
            draw.point((cx, cy), fill=(136, 136, 136, 255))
        return tile, 0.05
    elif finish == 'linen':
        # 8x8 tile with grid lines
        tile = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        # Horizontal lines at y=0, y=4
        for y in (0, 4):
            draw.line([(0, y), (7, y)], fill=(136, 136, 136, 255))
        # Vertical lines at x=0, x=4
        for x in (0, 4):
            draw.line([(x, 0), (x, 7)], fill=(136, 136, 136, 255))
        return tile, 0.08
    elif finish == 'suede':
        # 6x6 tile with scattered dots
        tile = Image.new('RGBA', (6, 6), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        for cx, cy in [(1, 1), (4, 3), (2, 5), (5, 1)]:
            draw.point((cx, cy), fill=(136, 136, 136, 255))
        return tile, 0.06
    elif finish == 'silk':
        # 10x10 tile with diagonal lines
        tile = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        draw.line([(0, 9), (9, 0)], fill=(136, 136, 136, 255))
        draw.line([(0, 1), (1, 0)], fill=(136, 136, 136, 200))
        draw.line([(8, 9), (9, 8)], fill=(136, 136, 136, 200))
        return tile, 0.06
    return None, 0


def apply_texture(canvas, finish):
    """Apply a tiled texture overlay to the entire canvas."""
    tile, opacity = create_texture_tile(finish)
    if tile is None or opacity <= 0:
        return canvas

    cw, ch = canvas.size
    tw, th = tile.size

    # Create full-size tiled texture
    texture = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    for y in range(0, ch, th):
        for x in range(0, cw, tw):
            texture.paste(tile, (x, y))

    # Apply at the specified opacity
    alpha = texture.split()[3]
    alpha = alpha.point(lambda a: int(a * opacity))
    texture.putalpha(alpha)

    return Image.alpha_composite(canvas.convert('RGBA'), texture)


# ---------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------

def load_photo(upload_folder, filename):
    """Load an uploaded photo, applying EXIF rotation."""
    filepath = Path(upload_folder) / filename
    if not filepath.exists():
        return None
    img = Image.open(filepath)
    img = ImageOps.exif_transpose(img)
    return img


def crop_image(img, crop):
    """Apply normalized crop rect {x, y, w, h} to a PIL image."""
    if not crop:
        return img
    w, h = img.size
    left = round(crop['x'] * w)
    top = round(crop['y'] * h)
    right = round((crop['x'] + crop['w']) * w)
    bottom = round((crop['y'] + crop['h']) * h)
    return img.crop((left, top, right, bottom))


# ---------------------------------------------------------------------------
# Single slide rendering
# ---------------------------------------------------------------------------

def render_single_slide(img_data, settings, upload_folder, screen_size):
    """Render a single-image slide. Returns an RGBA PIL Image at screen_size."""
    screen_w, screen_h = screen_size
    mat_color = img_data.get('mat_color') or settings.get('mat_color', '#ffffff')
    mat_finish = img_data.get('mat_finish') or settings.get('mat_finish', 'flat')
    effect_size = img_data.get('bevel_width') if img_data.get('bevel_width') is not None else settings.get('bevel_width', 4)
    border_effect = img_data.get('border_effect') or settings.get('border_effect', 'bevel')
    scale = img_data.get('scale', 1.0) or 1.0
    crop_data = img_data.get('crop')
    fit_mode = settings.get('fit_mode', 'contain')

    photo = load_photo(upload_folder, img_data['filename'])
    if photo is None:
        return _blank_canvas(screen_w, screen_h, mat_color, mat_finish)

    orig_w, orig_h = photo.size

    # Create canvas with mat background
    canvas = Image.new('RGBA', (screen_w, screen_h), hex_to_rgb(mat_color) + (255,))

    if fit_mode == 'cover':
        # Full-screen cover mode — no mat visible
        photo = photo.convert('RGBA')
        photo = ImageOps.fit(photo, (screen_w, screen_h), Image.Resampling.LANCZOS)
        effected, pad = apply_effect(photo, effect_size, mat_color, border_effect)
        _center_paste(canvas, effected, pad)
    else:
        # Contain mode — photo within mat
        effect_space = round(effect_size * 2) if border_effect == 'shadow' else effect_size
        if crop_data:
            img_w = orig_w * crop_data['w'] * scale
            img_h = orig_h * crop_data['h'] * scale
        else:
            img_w = orig_w * scale
            img_h = orig_h * scale

        photo_w, photo_h = calculate_mat_padding(img_w, img_h, effect_space,
                                                  screen_w, screen_h)
        if photo_w <= 0 or photo_h <= 0:
            return apply_texture(canvas, mat_finish)

        if crop_data:
            cropped = crop_image(photo, crop_data)
            cropped = cropped.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            effected, pad = apply_effect(cropped, effect_size, mat_color, border_effect)
        else:
            scaled = photo.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            effected, pad = apply_effect(scaled, effect_size, mat_color, border_effect)

        _center_paste(canvas, effected, pad)

    return apply_texture(canvas, mat_finish)


def _center_paste(canvas, element, shadow_pad=0):
    """Paste element centered on canvas, accounting for shadow padding."""
    cw, ch = canvas.size
    ew, eh = element.size
    x = (cw - ew) // 2
    y = (ch - eh) // 2
    element = element.convert('RGBA')
    canvas.paste(element, (x, y), element)


def _blank_canvas(w, h, mat_color, mat_finish):
    """Return an empty mat canvas (used when image file is missing)."""
    canvas = Image.new('RGBA', (w, h), hex_to_rgb(mat_color) + (255,))
    return apply_texture(canvas, mat_finish)


# ---------------------------------------------------------------------------
# Group slide rendering
# ---------------------------------------------------------------------------

def render_group_slide(slide, settings, upload_folder, screen_size):
    """Render a group slide (2+ images). Returns an RGBA PIL Image at screen_size."""
    screen_w, screen_h = screen_size
    images = slide['images']
    count = len(images)
    mat_color = slide.get('mat_color') or settings.get('mat_color', '#ffffff')
    # Groups use first image's finish or global setting
    mat_finish = images[0].get('mat_finish') or settings.get('mat_finish', 'flat')

    canvas = Image.new('RGBA', (screen_w, screen_h), hex_to_rgb(mat_color) + (255,))

    if count <= 3:
        _render_group_row(canvas, images, settings, upload_folder, mat_color,
                          screen_w, screen_h)
    else:
        _render_group_grid(canvas, images, settings, upload_folder, mat_color,
                           screen_w, screen_h)

    return apply_texture(canvas, mat_finish)


def _render_group_row(canvas, images, settings, upload_folder, mat_color,
                      screen_w, screen_h):
    """Render 1-3 images in a row with matched heights (flex space-evenly).

    Ports the count <= 3 branch of showSlide.
    """
    count = len(images)

    img_infos = []
    for img_data in images:
        raw_ar = (img_data.get('width') or 1) / (img_data.get('height') or 1)
        crop = img_data.get('crop')
        ar = raw_ar * crop['w'] / crop['h'] if crop else raw_ar
        effect_size = img_data.get('bevel_width') if img_data.get('bevel_width') is not None else settings.get('bevel_width', 4)
        border_effect = img_data.get('border_effect') or settings.get('border_effect', 'bevel')
        img_infos.append({
            'filename': img_data['filename'],
            'ar': ar,
            'scale': img_data.get('scale', 1.0) or 1.0,
            'crop': crop,
            'effect_size': effect_size,
            'border_effect': border_effect,
        })

    total_width_at_unit = sum(i['ar'] * i['scale'] for i in img_infos)
    max_scale = max(i['scale'] for i in img_infos)

    gap_fraction = 0.05
    total_gap_fraction = gap_fraction * (count + 1)

    total_effect_w = sum(
        2 * (i['effect_size'] * 2 if i['border_effect'] == 'shadow' else i['effect_size'])
        for i in img_infos
    )
    max_effect = max(
        i['effect_size'] * 2 if i['border_effect'] == 'shadow' else i['effect_size']
        for i in img_infos
    )

    usable_w = screen_w * (1 - total_gap_fraction) - total_effect_w
    usable_h = screen_h * 0.85 - 2 * max_effect

    base_height = min(usable_h / max_scale, usable_w / total_width_at_unit)

    # Compute each element's dimensions
    elements = []
    for info in img_infos:
        h = base_height * info['scale']
        w = h * info['ar']

        photo = load_photo(upload_folder, info['filename'])
        if photo is None:
            continue

        if info['crop']:
            cropped = crop_image(photo, info['crop'])
            scaled = cropped.resize((round(w), round(h)), Image.Resampling.LANCZOS)
        else:
            scaled = photo.resize((round(w), round(h)), Image.Resampling.LANCZOS)

        effected, pad = apply_effect(scaled, info['effect_size'], mat_color,
                                     info['border_effect'])
        elements.append((effected, pad))

    if not elements:
        return

    # Space-evenly layout: N+1 equal gaps
    total_elem_w = sum(e[0].size[0] for e in elements)
    total_gap = screen_w - total_elem_w
    gap = total_gap / (len(elements) + 1) if len(elements) + 1 > 0 else 0

    x = gap
    for elem, pad in elements:
        ew, eh = elem.size
        y = (screen_h - eh) / 2
        elem = elem.convert('RGBA')
        canvas.paste(elem, (round(x), round(y)), elem)
        x += ew + gap


def _render_group_grid(canvas, images, settings, upload_folder, mat_color,
                       screen_w, screen_h):
    """Render 4+ images in a grid (CSS grid equivalent).

    Ports the count >= 4 branch of showSlide.
    """
    count = len(images)
    cols, rows = get_grid_layout(count)

    gap_frac = 0.04
    cell_w = screen_w * (1 - gap_frac * (cols + 1)) / cols
    cell_h = screen_h * (1 - gap_frac * (rows + 1)) / rows

    # Compute gap sizes for space-evenly positioning
    gap_x = screen_w * gap_frac
    gap_y = screen_h * gap_frac

    for idx, img_data in enumerate(images):
        col = idx % cols
        row = idx // cols

        crop = img_data.get('crop')
        effect_size = img_data.get('bevel_width') if img_data.get('bevel_width') is not None else settings.get('bevel_width', 4)
        border_effect = img_data.get('border_effect') or settings.get('border_effect', 'bevel')
        effect_space = effect_size * 2 if border_effect == 'shadow' else effect_size
        usable_cell_w = cell_w - 2 * effect_space
        usable_cell_h = cell_h - 2 * effect_space

        photo = load_photo(upload_folder, img_data['filename'])
        if photo is None:
            continue

        orig_w = img_data.get('width') or photo.size[0]
        orig_h = img_data.get('height') or photo.size[1]

        if crop:
            raw_ar = (orig_w or 1) / (orig_h or 1)
            crop_ar = raw_ar * crop['w'] / crop['h']
            if crop_ar > usable_cell_w / usable_cell_h:
                dw = usable_cell_w
                dh = dw / crop_ar
            else:
                dh = usable_cell_h
                dw = dh * crop_ar

            cropped = crop_image(photo, crop)
            scaled = cropped.resize((round(dw), round(dh)), Image.Resampling.LANCZOS)
        else:
            img_ar = (orig_w or 1) / (orig_h or 1)
            if img_ar > usable_cell_w / usable_cell_h:
                dw = usable_cell_w
                dh = dw / img_ar
            else:
                dh = usable_cell_h
                dw = dh * img_ar
            scaled = photo.resize((round(dw), round(dh)), Image.Resampling.LANCZOS)

        effected, pad = apply_effect(scaled, effect_size, mat_color, border_effect)

        # Position: centre of each cell
        cell_cx = gap_x + col * (cell_w + gap_x) + cell_w / 2
        cell_cy = gap_y + row * (cell_h + gap_y) + cell_h / 2
        ew, eh = effected.size
        x = round(cell_cx - ew / 2)
        y = round(cell_cy - eh / 2)

        effected = effected.convert('RGBA')
        canvas.paste(effected, (x, y), effected)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_snapshot(filename, gallery, settings, upload_folder, snapshot_folder):
    """Render and save a display snapshot for a single image.

    Returns the output path, or None if the image couldn't be rendered.
    """
    img_meta = gallery.get('images', {}).get(filename)
    if not img_meta:
        return None

    screen_w, screen_h = parse_aspect_ratio(settings.get('target_aspect_ratio', '16:9'))

    img_data = {
        'filename': filename,
        'width': img_meta.get('width'),
        'height': img_meta.get('height'),
        'mat_color': img_meta.get('mat_color'),
        'mat_finish': img_meta.get('mat_finish'),
        'bevel_width': img_meta.get('bevel_width'),
        'border_effect': img_meta.get('border_effect'),
        'scale': img_meta.get('scale', 1.0),
        'crop': img_meta.get('crop'),
    }

    result = render_single_slide(img_data, settings, upload_folder, (screen_w, screen_h))
    if result is None:
        return None

    snapshot_folder = Path(snapshot_folder)
    snapshot_folder.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_folder / f'{filename}.display.png'
    result.convert('RGB').save(out_path, 'PNG')
    return out_path


def render_group_snapshot(group_id, gallery, settings, upload_folder, snapshot_folder):
    """Render and save a display snapshot for a group slide.

    Returns the output path, or None on failure.
    """
    groups = gallery.get('groups', {})
    group = groups.get(group_id)
    if not group:
        return None

    images_meta = gallery.get('images', {})
    screen_w, screen_h = parse_aspect_ratio(settings.get('target_aspect_ratio', '16:9'))

    scales = group.get('scales', {})
    group_images = []
    for fname in group.get('images', []):
        meta = images_meta.get(fname)
        if not meta:
            continue
        entry = {
            'filename': fname,
            'width': meta.get('width'),
            'height': meta.get('height'),
            'mat_color': meta.get('mat_color'),
            'mat_finish': meta.get('mat_finish'),
            'bevel_width': meta.get('bevel_width'),
            'border_effect': meta.get('border_effect'),
            'scale': scales.get(fname, 1.0),
            'crop': meta.get('crop'),
        }
        group_images.append(entry)

    if len(group_images) < 2:
        return None

    slide = {
        'type': 'group',
        'group_id': group_id,
        'images': group_images,
        'mat_color': group.get('mat_color'),
    }

    result = render_group_slide(slide, settings, upload_folder, (screen_w, screen_h))
    if result is None:
        return None

    snapshot_folder = Path(snapshot_folder)
    snapshot_folder.mkdir(parents=True, exist_ok=True)
    out_path = snapshot_folder / f'{group_id}.display.png'
    result.convert('RGB').save(out_path, 'PNG')
    return out_path


def delete_snapshot(filename, snapshot_folder):
    """Delete a snapshot file for a single image."""
    path = Path(snapshot_folder) / f'{filename}.display.png'
    path.unlink(missing_ok=True)


def delete_group_snapshot(group_id, snapshot_folder):
    """Delete a snapshot file for a group."""
    path = Path(snapshot_folder) / f'{group_id}.display.png'
    path.unlink(missing_ok=True)


def get_groups_containing(filename, gallery):
    """Return list of group_ids that contain the given filename."""
    groups = gallery.get('groups', {})
    return [gid for gid, g in groups.items()
            if filename in g.get('images', [])]


def backfill_snapshots(gallery, settings, upload_folder, snapshot_folder):
    """Generate missing snapshots for all enabled images and groups.

    Returns count of snapshots generated.
    """
    snapshot_folder = Path(snapshot_folder)
    snapshot_folder.mkdir(parents=True, exist_ok=True)
    count = 0

    # Single images
    grouped_filenames = set()
    for group in gallery.get('groups', {}).values():
        grouped_filenames.update(group.get('images', []))

    for filename, meta in gallery.get('images', {}).items():
        if not meta.get('enabled', True):
            continue
        if filename in grouped_filenames:
            continue
        out_path = snapshot_folder / f'{filename}.display.png'
        if not out_path.exists():
            if render_snapshot(filename, gallery, settings, upload_folder, snapshot_folder):
                count += 1

    # Groups
    for group_id in gallery.get('groups', {}):
        out_path = snapshot_folder / f'{group_id}.display.png'
        if not out_path.exists():
            if render_group_snapshot(group_id, gallery, settings, upload_folder,
                                     snapshot_folder):
                count += 1

    return count


def regenerate_all_snapshots(gallery, settings, upload_folder, snapshot_folder):
    """Re-render ALL snapshots (used when global settings change).

    Returns count of snapshots generated.
    """
    snapshot_folder = Path(snapshot_folder)
    snapshot_folder.mkdir(parents=True, exist_ok=True)
    count = 0

    grouped_filenames = set()
    for group in gallery.get('groups', {}).values():
        grouped_filenames.update(group.get('images', []))

    for filename, meta in gallery.get('images', {}).items():
        if not meta.get('enabled', True):
            continue
        if filename in grouped_filenames:
            continue
        if render_snapshot(filename, gallery, settings, upload_folder, snapshot_folder):
            count += 1

    for group_id in gallery.get('groups', {}):
        if render_group_snapshot(group_id, gallery, settings, upload_folder,
                                 snapshot_folder):
            count += 1

    return count
