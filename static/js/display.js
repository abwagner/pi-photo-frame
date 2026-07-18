let slides = [];      // Array of {type, images, mat_color, group_id?}
        let settings = {};
        let currentIndex = 0;
        let isPaused = false;
        let lastServerIndex = -1;
        let currentSlideEl = null;
        let previousSlideEl = null;

        const imageWrapper = document.getElementById('image-wrapper');
        const loadingEl = document.getElementById('loading');

        // Initial load
        loadData();

        // Poll server for slideshow state every 1 second
        setInterval(pollDisplayState, 1000);

        // Poll for slide list / settings changes every 5 seconds
        setInterval(checkForUpdates, 5000);

        async function loadData() {
            try {
                const response = await fetch('/api/images');
                const data = await response.json();

                settings = data.settings;
                applySettings();

                slides = data.slides || [];

                if (slides.length > 0) {
                    loadingEl.style.display = 'none';
                    // Get initial index from server state
                    const stateResp = await fetch('/api/display/state');
                    const state = await stateResp.json();
                    currentIndex = state.index;
                    lastServerIndex = state.index;
                    isPaused = state.paused;
                    showSlide(currentIndex);
                } else {
                    showNoImages();
                }
            } catch (err) {
                console.error('Failed to load data:', err);
                loadingEl.innerHTML = '<div class="no-images"><h2>Connection Error</h2><p>Unable to connect to server</p></div>';
            }
        }

        async function pollDisplayState() {
            try {
                const resp = await fetch('/api/display/state');
                const state = await resp.json();
                isPaused = state.paused;
                if (state.index !== lastServerIndex && state.total > 0) {
                    lastServerIndex = state.index;
                    currentIndex = state.index;
                    showSlide(currentIndex);
                }
            } catch (err) {
                // Silent — will retry on next poll
            }
        }

        async function checkForUpdates() {
            try {
                const response = await fetch('/api/settings');
                const newSettings = await response.json();

                if (JSON.stringify(newSettings) !== JSON.stringify(settings)) {
                    settings = newSettings;
                    applySettings();
                }

                // Check for slide list changes (new uploads, deletes, reorder)
                const imgResponse = await fetch('/api/images');
                const imgData = await imgResponse.json();
                const newSlides = imgData.slides || [];
                const newSlidesJson = JSON.stringify(newSlides);

                if (newSlidesJson !== JSON.stringify(slides)) {
                    const oldKeys = slides.map(s => s.type === 'group' ? s.group_id : s.images[0]?.filename);
                    const newKeys = newSlides.map(s => s.type === 'group' ? s.group_id : s.images[0]?.filename);
                    const structureChanged = JSON.stringify(newKeys) !== JSON.stringify(oldKeys);
                    slides = newSlides;

                    if (slides.length === 0) {
                        showNoImages();
                    } else if (structureChanged && loadingEl.style.display !== 'none') {
                        loadingEl.style.display = 'none';
                        showSlide(currentIndex);
                    } else {
                        // Metadata changed (crop, scale, mat_color, etc.) — re-render current slide
                        showSlide(currentIndex);
                    }
                }
            } catch (err) {
                console.error('Update check failed:', err);
            }
        }

        function applySettings() {
            document.body.style.setProperty('--mat-color', settings.mat_color);
            document.body.style.setProperty('--transition-duration', settings.transition_duration + 's');

            // Apply mat texture class
            document.body.classList.remove('mat-eggshell', 'mat-linen', 'mat-suede', 'mat-silk');
            const finish = settings.mat_finish || 'flat';
            if (finish !== 'flat') {
                document.body.classList.add('mat-' + finish);
            }
        }

        function getBevelColors(matHex) {
            let hex = matHex.replace('#', '');
            if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
            const innerAlpha = luminance < 0.5 ? 0.30 : 0.20;
            return { outer: 'rgba(0,0,0,0.00)', inner: `rgba(0,0,0,${innerAlpha})` };
        }

        // Returns per-edge colors for the lit bevel using light-source sliders.
        // intensity: 0-100, v: 0=top-lit/100=bottom-lit, h: 0=left-lit/100=right-lit
        function getBevelColorsLit(intensity, v, h) {
            const i = intensity / 100;
            // vFactor: +1 at v=0 (top lit), 0 at v=50 (neutral), -1 at v=100 (bottom lit)
            const vf = (50 - v) / 50;
            const hf = (50 - h) / 50;
            function edge(factor) {
                const a = +(Math.abs(factor) * i).toFixed(3);
                if (a < 0.005) return 'transparent';
                return factor > 0 ? `rgba(255,255,255,${a})` : `rgba(0,0,0,${a})`;
            }
            return { top: edge(vf), bottom: edge(-vf), left: edge(hf), right: edge(-hf) };
        }

        function getShadowStyle(size) {
            const blur = size * 2;
            const spread = Math.round(size * 0.5);
            const yOffset = Math.round(size * 0.5);
            return `0 ${yOffset}px ${blur}px ${spread}px rgba(0,0,0,0.35)`;
        }

        function wrapInShadow(imgEl, shadowSize) {
            const wrapper = document.createElement('div');
            wrapper.className = 'mat-shadow';
            imgEl.style.boxShadow = getShadowStyle(shadowSize);
            wrapper.appendChild(imgEl);
            return wrapper;
        }

        function wrapInEffect(imgEl, effectSize, matColor, borderEffect) {
            if (effectSize <= 0) return imgEl;
            if (borderEffect === 'shadow') {
                return wrapInShadow(imgEl, effectSize);
            }
            return wrapInBevel(imgEl, effectSize, matColor, borderEffect);
        }

        function wrapInBevel(imgEl, bevelWidth, matColor, bevelStyle) {
            const wrapper = document.createElement('div');
            wrapper.className = 'mat-bevel';
            wrapper.style.setProperty('--bevel-w', bevelWidth + 'px');
            wrapper.style.setProperty('--bevel-mat', matColor);
            // Round element dimensions to integers so bevel strips always meet the edge cleanly
            const elW = parseFloat(imgEl.style.width);
            const elH = parseFloat(imgEl.style.height);
            if (!isNaN(elW)) imgEl.style.width  = Math.round(elW) + 'px';
            if (!isNaN(elH)) imgEl.style.height = Math.round(elH) + 'px';
            wrapper.appendChild(imgEl);
            const w = bevelWidth + 'px';
            if (bevelStyle === 'bevel-lit') {
                // Rectangular strips avoid outer-corner overlap/blowout.
                // Left/right are inset by bevel-width so they don't share corner pixels with top/bottom.
                const litI = settings.bevel_lit_intensity ?? 50;
                const litV = settings.bevel_lit_v ?? 15;
                const litH = settings.bevel_lit_h ?? 15;
                const colors = getBevelColorsLit(litI, litV, litH);
                const strips = [
                    { pos: `top:0;left:0;right:0;height:${w}`,             grad: 'to bottom', from: colors.top,    to: 'transparent' },
                    { pos: `bottom:0;left:0;right:0;height:${w}`,           grad: 'to top',    from: colors.bottom, to: 'transparent' },
                    { pos: `top:${w};left:0;bottom:${w};width:${w}`,       grad: 'to right',  from: colors.left,   to: 'transparent' },
                    { pos: `top:${w};right:0;bottom:${w};width:${w}`,      grad: 'to left',   from: colors.right,  to: 'transparent' },
                ];
                strips.forEach(({ pos, grad, from, to }) => {
                    const el = document.createElement('div');
                    el.style.cssText = `position:absolute;${pos};background:linear-gradient(${grad},${from},${to});pointer-events:none;z-index:1;`;
                    wrapper.appendChild(el);
                });
            } else {
                // Classic: uniform dark inward shadow on all four sides
                const bevelColors = getBevelColors(matColor);
                wrapper.style.setProperty('--bevel-outer', bevelColors.outer);
                wrapper.style.setProperty('--bevel-inner', bevelColors.inner);
                const strips = [
                    { pos: `top:0;left:0;right:0;height:${w}`,    clip: `polygon(0 0,100% 0,calc(100% - ${w}) 100%,${w} 100%)`,     grad: 'to bottom' },
                    { pos: `bottom:0;left:0;right:0;height:${w}`, clip: `polygon(${w} 0,calc(100% - ${w}) 0,100% 100%,0 100%)`,     grad: 'to top'    },
                    { pos: `top:0;left:0;bottom:0;width:${w}`,    clip: `polygon(0 0,100% ${w},100% calc(100% - ${w}),0 100%)`,     grad: 'to right'  },
                    { pos: `top:0;right:0;bottom:0;width:${w}`,   clip: `polygon(0 ${w},100% 0,100% 100%,0 calc(100% - ${w}))`,     grad: 'to left'   },
                ];
                strips.forEach(({ pos, clip, grad }) => {
                    const el = document.createElement('div');
                    el.style.cssText = `position:absolute;${pos};clip-path:${clip};background:linear-gradient(${grad},var(--bevel-outer),var(--bevel-inner));pointer-events:none;z-index:1;`;
                    wrapper.appendChild(el);
                });
            }
            return wrapper;
        }

        function showSlide(index) {
            if (slides.length === 0) return;

            const slide = slides[index];
            const matColor = slide.mat_color || settings.mat_color;
            document.body.style.setProperty('--mat-color', matColor);

            // Determine effect settings for this slide
            const slideEffectSize = slide.images[0].bevel_width ?? settings.bevel_width ?? 4;
            const slideBorderEffect = slide.images[0].border_effect ?? settings.border_effect ?? 'bevel';
            const slideFinish = slide.images[0].mat_finish ?? settings.mat_finish ?? 'flat';

            // Apply per-slide texture override
            document.body.classList.remove('mat-eggshell', 'mat-linen', 'mat-suede', 'mat-silk');
            if (slideFinish !== 'flat') {
                document.body.classList.add('mat-' + slideFinish);
            }

            // Calculate mat padding based on slide content (effect-aware)
            const container = document.querySelector('.frame-container');
            let photoW = 0, photoH = 0;
            if (slide.type === 'single') {
                const imgData = slide.images[0];
                const scale = imgData.scale || 1.0;
                const crop = imgData.crop;
                const effectSpace = slideBorderEffect === 'shadow' ? Math.round(slideEffectSize * 2) : slideEffectSize;
                const imgW = crop ? imgData.width * crop.w * scale : imgData.width * scale;
                const imgH = crop ? imgData.height * crop.h * scale : imgData.height * scale;
                const result = calculateMatPadding(imgW, imgH, effectSpace);
                container.style.setProperty('--mat-padding-vertical', result.vertical);
                container.style.setProperty('--mat-padding-horizontal', result.horizontal);
                photoW = result.photoW;
                photoH = result.photoH;
            } else {
                // For groups, no mat padding - space-evenly handles all spacing
                container.style.setProperty('--mat-padding-vertical', '0');
                container.style.setProperty('--mat-padding-horizontal', '0');
            }

            // Create slide element
            const slideEl = document.createElement('div');
            slideEl.className = 'slide';

            if (slide.type === 'single') {
                const imgData = slide.images[0];
                const crop = imgData.crop;

                if (settings.fit_mode === 'cover') {
                    const img = document.createElement('img');
                    img.src = '/uploads/' + imgData.filename;
                    img.alt = imgData.filename;
                    img.className = 'cover';
                    slideEl.appendChild(wrapInEffect(img, slideEffectSize, matColor, slideBorderEffect));
                } else if (crop && photoW > 0 && photoH > 0) {
                    // Cropped: container with overflow hidden
                    const cropContainer = document.createElement('div');
                    cropContainer.style.width = photoW + 'px';
                    cropContainer.style.height = photoH + 'px';
                    cropContainer.style.overflow = 'hidden';
                    cropContainer.style.lineHeight = '0';

                    const img = document.createElement('img');
                    img.src = '/uploads/' + imgData.filename;
                    img.alt = imgData.filename;
                    const fullW = photoW / crop.w;
                    const fullH = photoH / crop.h;
                    img.style.width = fullW + 'px';
                    img.style.height = fullH + 'px';
                    img.style.marginLeft = (-crop.x * fullW) + 'px';
                    img.style.marginTop = (-crop.y * fullH) + 'px';
                    img.style.display = 'block';
                    img.style.maxWidth = 'none';
                    img.style.maxHeight = 'none';

                    cropContainer.appendChild(img);
                    slideEl.appendChild(wrapInEffect(cropContainer, slideEffectSize, matColor, slideBorderEffect));
                } else {
                    const img = document.createElement('img');
                    img.src = '/uploads/' + imgData.filename;
                    img.alt = imgData.filename;
                    if (photoW > 0 && photoH > 0) {
                        img.style.width = photoW + 'px';
                        img.style.height = photoH + 'px';
                    }
                    slideEl.appendChild(wrapInEffect(img, slideEffectSize, matColor, slideBorderEffect));
                }
            } else {
                // Group slide - create grid layout
                const count = slide.images.length;
                const layout = getGridLayout(count);
                const gridEl = document.createElement('div');

                if (count <= 3) {
                    // Row layout with explicit pixel sizes for matched heights
                    gridEl.className = 'slide-grid';
                    const containerW = window.innerWidth;
                    const containerH = window.innerHeight;

                    const imgInfos = slide.images.map((imgData, i) => {
                        const rawAr = (imgData.width || 1) / (imgData.height || 1);
                        const crop = imgData.crop;
                        const ar = crop ? rawAr * crop.w / crop.h : rawAr;
                        return {
                            filename: imgData.filename,
                            ar,
                            scale: imgData.scale || 1.0,
                            crop,
                            effectSize: slide.images[i].bevel_width ?? settings.bevel_width ?? 4,
                            borderEffect: slide.images[i].border_effect ?? settings.border_effect ?? 'bevel'
                        };
                    });

                    // At base height h=1, each image width = ar * scale
                    const totalWidthAtUnitHeight = imgInfos.reduce((sum, info) => sum + info.ar * info.scale, 0);
                    const maxScale = Math.max(...imgInfos.map(i => i.scale));
                    // Reserve space for N+1 equal gaps (space-evenly) — each gap ~5% of container
                    const gapFraction = 0.05;
                    const totalGapFraction = gapFraction * (count + 1);
                    // Subtract effect space from usable area
                    const totalEffectW = imgInfos.reduce((sum, info) => {
                        const space = info.borderEffect === 'shadow' ? info.effectSize * 2 : info.effectSize;
                        return sum + 2 * space;
                    }, 0);
                    const maxEffect = Math.max(...imgInfos.map(i => i.borderEffect === 'shadow' ? i.effectSize * 2 : i.effectSize));
                    const usableW = containerW * (1 - totalGapFraction) - totalEffectW;
                    const usableH = containerH * 0.85 - 2 * maxEffect;
                    // Base height: largest h such that total width fits and tallest image fits
                    const baseHeight = Math.min(usableH / maxScale, usableW / totalWidthAtUnitHeight);

                    imgInfos.forEach((info, i) => {
                        const h = baseHeight * info.scale;
                        const w = h * info.ar;
                        let node;
                        if (info.crop) {
                            const cropContainer = document.createElement('div');
                            cropContainer.style.width = w + 'px';
                            cropContainer.style.height = h + 'px';
                            cropContainer.style.overflow = 'hidden';
                            cropContainer.style.lineHeight = '0';
                            cropContainer.style.flexShrink = '0';
                            const img = document.createElement('img');
                            img.src = '/uploads/' + info.filename;
                            img.alt = info.filename;
                            const fullW = w / info.crop.w;
                            const fullH = h / info.crop.h;
                            img.style.width = fullW + 'px';
                            img.style.height = fullH + 'px';
                            img.style.marginLeft = (-info.crop.x * fullW) + 'px';
                            img.style.marginTop = (-info.crop.y * fullH) + 'px';
                            img.style.display = 'block';
                            img.style.maxWidth = 'none';
                            img.style.maxHeight = 'none';
                            cropContainer.appendChild(img);
                            node = wrapInEffect(cropContainer, info.effectSize, matColor, info.borderEffect);
                        } else {
                            const img = document.createElement('img');
                            img.src = '/uploads/' + info.filename;
                            img.alt = info.filename;
                            img.style.width = w + 'px';
                            img.style.height = h + 'px';
                            img.style.maxWidth = 'none';
                            img.style.maxHeight = 'none';
                            img.style.flexShrink = '0';
                            node = wrapInEffect(img, info.effectSize, matColor, info.borderEffect);
                        }
                        gridEl.appendChild(node);
                    });
                } else {
                    // Grid layout — use explicit pixel sizes so crop containers have real dimensions
                    gridEl.className = 'slide-grid grid-layout';
                    gridEl.style.gridTemplateColumns = `repeat(${layout.cols}, 1fr)`;
                    gridEl.style.gridTemplateRows = `repeat(${layout.rows}, 1fr)`;
                    const gridW = window.innerWidth;
                    const gridH = window.innerHeight;
                    const gapFrac = 0.04;
                    const cellW = gridW * (1 - gapFrac * (layout.cols + 1)) / layout.cols;
                    const cellH = gridH * (1 - gapFrac * (layout.rows + 1)) / layout.rows;

                    slide.images.forEach(imgData => {
                        const crop = imgData.crop;
                        const imgEffectSize = imgData.bevel_width ?? settings.bevel_width ?? 4;
                        const imgBorderEffect = imgData.border_effect ?? settings.border_effect ?? 'bevel';
                        const effectSpace = imgBorderEffect === 'shadow' ? imgEffectSize * 2 : imgEffectSize;
                        const usableCellW = cellW - 2 * effectSpace;
                        const usableCellH = cellH - 2 * effectSpace;
                        let node;
                        if (crop) {
                            const rawAr = (imgData.width || 1) / (imgData.height || 1);
                            const cropAr = rawAr * crop.w / crop.h;
                            let dW, dH;
                            if (cropAr > usableCellW / usableCellH) {
                                dW = usableCellW;
                                dH = dW / cropAr;
                            } else {
                                dH = usableCellH;
                                dW = dH * cropAr;
                            }
                            const cropContainer = document.createElement('div');
                            cropContainer.style.width = dW + 'px';
                            cropContainer.style.height = dH + 'px';
                            cropContainer.style.overflow = 'hidden';
                            cropContainer.style.lineHeight = '0';
                            const img = document.createElement('img');
                            img.src = '/uploads/' + imgData.filename;
                            img.alt = imgData.filename;
                            const fullW = dW / crop.w;
                            const fullH = dH / crop.h;
                            img.style.width = fullW + 'px';
                            img.style.height = fullH + 'px';
                            img.style.marginLeft = (-crop.x * fullW) + 'px';
                            img.style.marginTop = (-crop.y * fullH) + 'px';
                            img.style.display = 'block';
                            img.style.maxWidth = 'none';
                            img.style.maxHeight = 'none';
                            cropContainer.appendChild(img);
                            node = wrapInEffect(cropContainer, imgEffectSize, matColor, imgBorderEffect);
                        } else {
                            const img = document.createElement('img');
                            img.src = '/uploads/' + imgData.filename;
                            img.alt = imgData.filename;
                            const imgAr = (imgData.width || 1) / (imgData.height || 1);
                            let dW, dH;
                            if (imgAr > usableCellW / usableCellH) {
                                dW = usableCellW;
                                dH = dW / imgAr;
                            } else {
                                dH = usableCellH;
                                dW = dH * imgAr;
                            }
                            img.style.width = dW + 'px';
                            img.style.height = dH + 'px';
                            img.style.maxWidth = 'none';
                            img.style.maxHeight = 'none';
                            node = wrapInEffect(img, imgEffectSize, matColor, imgBorderEffect);
                        }
                        gridEl.appendChild(node);
                    });
                }
                slideEl.appendChild(gridEl);
            }

            // Wait for all images to load before transitioning
            const allImgs = slideEl.querySelectorAll('img');
            let loadedCount = 0;
            const totalImgs = allImgs.length;

            const onAllLoaded = () => {
                // Remove old previous
                if (previousSlideEl) {
                    previousSlideEl.remove();
                }

                // Current becomes previous
                if (currentSlideEl) {
                    currentSlideEl.classList.remove('active');
                    currentSlideEl.classList.add('previous');
                    previousSlideEl = currentSlideEl;

                    setTimeout(() => {
                        if (previousSlideEl && previousSlideEl.parentNode) {
                            previousSlideEl.remove();
                        }
                    }, settings.transition_duration * 1000 + 100);
                }

                // New becomes current
                imageWrapper.appendChild(slideEl);
                slideEl.offsetHeight; // Force reflow
                slideEl.classList.add('active');
                currentSlideEl = slideEl;
            };

            const onImgLoad = () => {
                loadedCount++;
                if (loadedCount >= totalImgs) {
                    onAllLoaded();
                }
            };

            const onImgError = (e) => {
                console.error('Failed to load image:', e.target.src);
                loadedCount++;
                if (loadedCount >= totalImgs) {
                    // If all failed, skip; if some loaded, show anyway
                    if (loadedCount === totalImgs && slideEl.querySelectorAll('img[src]').length === 0) {
                        nextSlide();
                    } else {
                        onAllLoaded();
                    }
                }
            };

            allImgs.forEach(img => {
                img.onload = onImgLoad;
                img.onerror = onImgError;
            });

            // Fallback if no images
            if (totalImgs === 0) {
                nextSlide();
            }
        }

        function getGridLayout(count) {
            if (count <= 3) return { cols: count, rows: 1 };
            const cols = Math.ceil(Math.sqrt(count));
            const rows = Math.ceil(count / cols);
            return { cols, rows };
        }

        function showNoImages() {
            loadingEl.innerHTML = `
                <div class="no-images">
                    <h2>No Photos</h2>
                    <p>Upload photos at:<br><strong>http://${location.hostname}:5000/upload</strong></p>
                </div>
            `;
            loadingEl.style.display = 'block';
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        async function sendControl(action) {
            try {
                const resp = await fetch('/api/display/control', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({action})
                });
                if (resp.ok) {
                    const state = await resp.json();
                    lastServerIndex = state.index;
                    currentIndex = state.index;
                    isPaused = state.paused;
                    showSlide(currentIndex);
                } else {
                    console.error('Control API returned', resp.status, await resp.text());
                }
            } catch (err) {
                console.error('Control fetch failed:', err);
            }
        }

        function nextSlide() {
            // Rely on server response to update index so all displays stay in sync
            sendControl('next');
        }
        function previousSlide() {
            sendControl('prev');
        }
        function togglePause() {
            isPaused = !isPaused;
            sendControl(isPaused ? 'pause' : 'play');
        }

        function calculateMatPadding(imgWidth, imgHeight, effectSpace) {
            if (!imgWidth || !imgHeight) {
                return { vertical: '10%', horizontal: '10%', photoW: 0, photoH: 0 };
            }

            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            const imgRatio = imgWidth / imgHeight;
            const effect2 = (effectSpace || 0) * 2;
            const isPortrait = imgHeight > imgWidth;

            // Default: 80% of the constraining dimension based on orientation
            // Portrait images: 80% of screen height
            // Landscape images: 80% of screen width
            let maxPhotoW, maxPhotoH;
            if (isPortrait) {
                maxPhotoH = Math.min(screenHeight * 0.80, screenHeight - effect2);
                maxPhotoW = Math.min(screenWidth - effect2, screenWidth * 0.95);
            } else {
                maxPhotoW = Math.min(screenWidth * 0.80, screenWidth - effect2);
                maxPhotoH = Math.min(screenHeight - effect2, screenHeight * 0.95);
            }

            if (maxPhotoW <= 0 || maxPhotoH <= 0) {
                return { vertical: '10%', horizontal: '10%', photoW: 0, photoH: 0 };
            }

            // Fit photo within constraints maintaining aspect ratio
            let photoW, photoH;
            if (imgRatio > maxPhotoW / maxPhotoH) {
                photoW = maxPhotoW;
                photoH = maxPhotoW / imgRatio;
            } else {
                photoH = maxPhotoH;
                photoW = maxPhotoH * imgRatio;
            }

            // Total = photo + effect space
            const totalW = photoW + effect2;
            const totalH = photoH + effect2;

            // Mat = remaining space
            const horizontalMat = Math.max(0, (screenWidth - totalW) / 2);
            const verticalMat = Math.max(0, (screenHeight - totalH) / 2);

            const hPadding = (horizontalMat / screenWidth * 100).toFixed(2) + '%';
            const vPadding = (verticalMat / screenHeight * 100).toFixed(2) + '%';

            return { vertical: vPadding, horizontal: hPadding, photoW: Math.round(photoW), photoH: Math.round(photoH) };
        }

        // Show controls on mouse move, auto-hide after 3 seconds
        (function() {
            const controls = document.querySelector('.controls');
            let hideTimer = null;
            document.addEventListener('mousemove', () => {
                controls.classList.add('visible');
                document.body.style.cursor = 'default';
                clearTimeout(hideTimer);
                hideTimer = setTimeout(() => {
                    controls.classList.remove('visible');
                    document.body.style.cursor = 'none';
                }, 3000);
            });
            // Hide cursor initially
            document.body.style.cursor = 'none';
        })();

        // Keyboard controls
        document.addEventListener('keydown', (e) => {
            switch (e.key) {
                case 'ArrowLeft':
                    previousSlide();
                    break;
                case 'ArrowRight':
                case ' ':
                    nextSlide();
                    break;
                case 'p':
                    togglePause();
                    break;
            }
        });
