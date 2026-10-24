/**
 * formula_renderer.js
 * Production-grade formula rendering with MathJax fallback chain.
 *
 * For each [[formula:<id>]] placeholder:
 *   1. Fetch FormulaAsset data via POST /api/formulas/batch
 *   2. If MathML available → MathJax.mathml2chtml (priority)
 *   3. If MathML fails but LaTeX available → MathJax.tex2chtml (fallback 1)
 *   4. If both fail or status=fallback_svg → load SVG from /api/formulas/<id>/render.svg (fallback 2)
 *   5. If conversion is pending → show a non-blocking review message
 *   6. If failed → show friendly "[Không thể chuyển đổi công thức]"
 *
 * Security:
 *   - All DOM manipulation via DOM API (createElement, createTextNode, etc.)
 *   - No innerHTML, no Jinja |safe for full text
 *   - SVG via sanitized <img> tag (not inline SVG injection)
 */

window.FormulaRenderer = (function() {
    'use strict';
    var typesetQueue = Promise.resolve();

    /**
     * Convert raw LaTeX quote commands to standard quotes.
     */
    function cleanLatexQuotes(str) {
        if (!str || typeof str !== 'string') return str;
        return str
            .replace(/\\lq\s*\\lq(?:\{\}|\\[ \t]+|\s*)?/g, '“')
            .replace(/\\rq\s*\\rq(?:\{\}|\\[ \t]+)/g, '” ')
            .replace(/\\rq\s*\\rq/g, '”')
            .replace(/\\textquotedblleft(?:\{\}|\\[ \t]+|\s*)?/g, '“')
            .replace(/\\textquotedblright(?:\{\}|\\[ \t]+)/g, '” ')
            .replace(/\\textquotedblright/g, '”')
            .replace(/\\textquotedbl(?:\{\}|\\[ \t]+|\s*)?/g, '"')
            .replace(/\\lq(?:\{\}|\\[ \t]+|\s*)?/g, '‘')
            .replace(/\\rq(?:\{\}|\\[ \t]+)/g, '’ ')
            .replace(/\\rq/g, '’')
            .replace(/\\textquoteleft(?:\{\}|\\[ \t]+|\s*)?/g, '‘')
            .replace(/\\textquoteright(?:\{\}|\\[ \t]+)/g, '’ ')
            .replace(/\\textquoteright/g, '’')
            .replace(/\s+([”’])/g, '$1')
            .replace(/([“‘])\s+/g, '$1')
            .replace(/([”’"])([\p{L}\p{N}])/gu, '$1 $2')
            .replace(/([\p{L}\p{N}])([“‘"])/gu, '$1 $2')
            .replace(/\\[ \t]+/g, ' ');
    }

    /**
     * Main entry: scan for formula and safe local-image placeholders.
     * @param {HTMLElement} rootElement - DOM element to scan (default: document.body)
     * @param {Object} temporaryFormulaMap - Pre-loaded formula data (from import preview)
     */
    function cleanLayoutCommands(text) {
        return text.replace(/^\s*\\immini(?:\s*\[[^\]]*\])?\s*\{\s*/, '').replace(/\\(?:renewcommand|setlength)\s*\{\s*\\(?:arraystretch|tabcolsep|extrarowheight)\s*\}\s*\{[^{}]*\}/g, '')
            .replace(/\\(?:small|footnotesize|scriptsize|tiny|normalsize|large|Large|LARGE|huge|Huge|centering)\b/g, '');
    }

    function renderFormulas(rootElement, temporaryFormulaMap, options) {
        rootElement = rootElement || document.body;
        temporaryFormulaMap = temporaryFormulaMap || {};
        if (window.BankFormulaScheduler && window.BankFormulaScheduler.route(rootElement, temporaryFormulaMap, options || {})) {
            return Promise.resolve();
        }
        // One queue owns both standard TeX and placeholder conversion. A
        // detached detail block is skipped before any MathJax work starts.
        typesetQueue = typesetQueue.catch(function() {}).then(function() {
            if (!rootElement.isConnected) return;
            var ready = window.MathJax && window.MathJax.startup && window.MathJax.startup.promise;
            return Promise.resolve(ready).then(function() {
                if (rootElement.isConnected) return _renderFormulasNow(rootElement, temporaryFormulaMap);
            });
        }).catch(function(err) {
            console.warn('[FormulaRenderer] Render:', err.message);
        });
        return typesetQueue;
    }

    function _renderFormulasNow(rootElement, temporaryFormulaMap) {
        if (!rootElement) rootElement = document.body;
        temporaryFormulaMap = temporaryFormulaMap || {};

        // Restore known visual assets before MathJax encounters TeX-only environments.
        var assets = Object.assign({}, window.FormulaAssetCache || {}, temporaryFormulaMap);
        var restoreWalker = document.createTreeWalker(rootElement, NodeFilter.SHOW_TEXT);
        var restoreNodes = [], restoreNode;
        while ((restoreNode = restoreWalker.nextNode())) {
            if (restoreNode.parentElement?.closest('script,style,textarea,mjx-container')) continue;
            restoreNodes.push(restoreNode);
        }
        restoreNodes.forEach(function(node) {
            var text = node.nodeValue;
            Object.entries(assets).forEach(function(entry) {
                var id = entry[0], asset = entry[1];
                text = text.replace(new RegExp('(?<!\\[)\\[formula:' + id + '\\s*\\](?!\\])', 'g'), '[[formula:' + id + ']]');
                if (Object.prototype.hasOwnProperty.call(temporaryFormulaMap, id) && asset.source_format === 'LaTeXBlock' && asset.source_text) {
                    text = text.split(asset.source_text.trim()).join('[[formula:' + id + ']]');
                }
            });
            node.nodeValue = text;
        });

        // 0. Clean any raw LaTeX quote commands in text nodes across the element
        try {
            var quoteWalker = document.createTreeWalker(
                rootElement,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: function(node) {
                        if (node.parentElement && (
                            node.parentElement.tagName === 'SCRIPT' ||
                            node.parentElement.tagName === 'STYLE' ||
                            node.parentElement.tagName === 'TEXTAREA'
                        )) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        if (node.nodeValue && (
                            node.nodeValue.indexOf('\\rq') !== -1 ||
                            node.nodeValue.indexOf('\\lq') !== -1 ||
                            node.nodeValue.indexOf('\\textquote') !== -1 || node.nodeValue.indexOf('\\immini') !== -1 || /\\(?:renewcommand|setlength|small|footnotesize|scriptsize|tiny|normalsize|large|Large|LARGE|huge|Huge|centering)\b/.test(node.nodeValue)
                        )) {
                            return NodeFilter.FILTER_ACCEPT;
                        }
                        return NodeFilter.FILTER_SKIP;
                    }
                }
            );
            var qNode;
            while ((qNode = quoteWalker.nextNode())) {
                qNode.nodeValue = cleanLayoutCommands(cleanLatexQuotes(qNode.nodeValue));
            }
        } catch (e) {
            console.log('[FormulaRenderer] cleanLatexQuotes error:', e);
        }

        // Imported short-answer keys have no math delimiters. Format only the
        // display copy; preserve the original answer used for grading.
        var answerNodes = Array.from(rootElement.querySelectorAll('[data-latex-answer]'));
        if (rootElement.matches && rootElement.matches('[data-latex-answer]')) answerNodes.unshift(rootElement);
        answerNodes.forEach(function(el) {
            if (el.querySelector('mjx-container')) return;
            var text = el.textContent;
            if (/\\(?:[A-Za-z]+|[{}])/.test(text) && !/\$|\\\(|\[\[formula:/.test(text)) {
                el.textContent = text.split(' | ').map(function(value) {
                    return /\\(?:[A-Za-z]+|[{}])/.test(value) ? '\\(' + value + '\\)' : value;
                }).join(' | ');
            }
        });

        function typesetRoot() {
            // Plain text needs no MathJax scan. Placeholder nodes already
            // contain rendered CHTML; only remaining raw TeX is typeset here.
            if (rootElement.isConnected && window.MathJax && window.MathJax.typesetPromise &&
                /\$|\\\(|\\\[|\\begin\b/.test(rootElement.textContent || '')) {
                return window.MathJax.typesetPromise([rootElement]);
            }
            return Promise.resolve();
        }

        // 2. Find all text nodes containing formula or safe visual placeholders.
        var walker = document.createTreeWalker(
            rootElement,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    if (node.parentElement && (
                        node.parentElement.tagName === 'SCRIPT' ||
                        node.parentElement.tagName === 'STYLE' ||
                        node.parentElement.tagName === 'TEXTAREA'
                    )) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (node.nodeValue && (
                        node.nodeValue.indexOf('[[formula:') !== -1 ||
                        node.nodeValue.indexOf('[[image:/static/uploads/questions/') !== -1
                    )) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_SKIP;
                }
            }
        );

        var textNodes = [];
        var uuidSet = new Set();
        var regex = /\[\[formula:([^\]]+)\]\]/g;
        var hasVisualPlaceholders = false;

        var node;
        while ((node = walker.nextNode())) {
            textNodes.push(node);
            var match;
            while ((match = regex.exec(node.nodeValue)) !== null) {
                uuidSet.add(match[1]);
            }
            if (node.nodeValue.indexOf('[[image:/static/uploads/questions/') !== -1) {
                hasVisualPlaceholders = true;
            }
        }

        if (uuidSet.size === 0 && !hasVisualPlaceholders) return typesetRoot();

        window.FormulaAssetCache = window.FormulaAssetCache || {};
        var uuidsToFetch = [];
        var finalFormulasMap = {};
        // Copy temporaryFormulaMap & sync with global cache
        for (var key in temporaryFormulaMap) {
            if (temporaryFormulaMap.hasOwnProperty(key)) {
                finalFormulasMap[key] = Object.assign({}, temporaryFormulaMap[key], {
                    _temporary: !!window.currentImportSessionId
                });
                window.FormulaAssetCache[key] = finalFormulasMap[key];
            }
        }

        uuidSet.forEach(function(uid) {
            if (!finalFormulasMap[uid]) {
                if (window.FormulaAssetCache[uid]) {
                    finalFormulasMap[uid] = window.FormulaAssetCache[uid];
                } else {
                    uuidsToFetch.push(uid);
                }
            }
        });

        var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
        var csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';

        function proceedToRender() {
            if (!rootElement.isConnected) return Promise.resolve();
            // Replace imported assets first, then scan remaining TeX. This
            // prevents two asynchronous render paths editing the same node.
            _replacePlaceholders(textNodes, finalFormulasMap);
            return typesetRoot();
        }

        if (uuidsToFetch.length > 0) {
            // 3. Fetch missing formula data
            return fetch('/api/formulas/batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ uuids: uuidsToFetch })
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.success && data.formulas) {
                    for (var fid in data.formulas) {
                        if (data.formulas.hasOwnProperty(fid)) {
                            finalFormulasMap[fid] = data.formulas[fid];
                            window.FormulaAssetCache[fid] = data.formulas[fid];
                        }
                    }
                }
            }, function(err) {
                console.error('[FormulaRenderer] Fetch error:', err);
            })
            .then(proceedToRender);
        } else {
            return proceedToRender();
        }
    }

    /**
     * Replace formula placeholders and allowlisted local images.
     */
    function _replacePlaceholders(nodes, formulasMap) {
        nodes.forEach(function(textNode) {
            var parent = textNode.parentNode;
            if (!parent) return;

            var parts = textNode.nodeValue.split(/(\[\[formula:[^\]]+\]\]|\[\[image:\/static\/uploads\/questions\/[A-Za-z0-9._-]+\]\])/);
            if (parts.length <= 1) return;

            var fragment = document.createDocumentFragment();

            parts.forEach(function(part) {
                var match = part.match(/^\[\[formula:([^\]]+)\]\]$/);
                if (match) {
                    var uid = match[1];
                    var fData = formulasMap[uid] || (window.FormulaAssetCache && window.FormulaAssetCache[uid]);
                    var renderedNode = _renderFormula(
                        uid,
                        fData,
                        Object.prototype.hasOwnProperty.call(formulasMap, uid) && !!fData._temporary
                    );
                    fragment.appendChild(renderedNode);
                } else {
                    var imageMatch = part.match(/^\[\[image:(\/static\/uploads\/questions\/[A-Za-z0-9._-]+)\]\]$/);
                    if (imageMatch) {
                        fragment.appendChild(_createDocumentImage(imageMatch[1]));
                    } else if (part) {
                        fragment.appendChild(document.createTextNode(cleanLatexQuotes(part)));
                    }
                }
            });

            parent.replaceChild(fragment, textNode);
        });

        // Direct CHTML conversion adds glyphs to MathJax's adaptive CSS.
        // Reset the document's update state so each batch publishes those
        // styles, while keeping the MathItems tracked for other questions.
        if (window.MathJax && window.MathJax.startup && window.MathJax.startup.document) {
            window.MathJax.startup.document.reset();
            window.MathJax.startup.document.updateDocument();
        }
    }

    function _createDocumentImage(src) {
        var img = document.createElement('img');
        img.src = src;
        img.alt = 'Hình minh họa trong câu hỏi';
        img.loading = 'lazy';
        img.className = 'formula-image';
        return _makeZoomableControl(img, img.alt, function() {
            _openImageLightbox(src, img.alt + ' phóng to');
        });
    }

    /**
     * Render a single formula with the full fallback chain.
     * Returns a DOM node ready for insertion.
     */
    function _renderStructuredTable(data) {
        var wrapper = document.createElement('span');
        wrapper.className = 'tex-table-wrap';
        var table = document.createElement('table');
        table.className = 'tex-data-table';
        table.setAttribute('aria-label', 'Bảng dữ liệu trong câu hỏi');
        var body = document.createElement('tbody');
        (data.rows || []).forEach(function(row) {
            var tr = document.createElement('tr');
            row.forEach(function(cell) {
                var td = document.createElement('td');
                td.colSpan = Math.max(1, Math.min(30, Number(cell.colspan) || 1));
                td.style.textAlign = ({l:'left', c:'center', r:'right'})[cell.align] || 'center';
                var text = String(cell.text || '');
                var pattern = /(\$\$([\s\S]*?)\$\$|\$([^$]+)\$|\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\])/g;
                var last = 0, m;
                while ((m = pattern.exec(text))) {
                    td.appendChild(document.createTextNode(text.slice(last, m.index)));
                    try { td.appendChild(window.MathJax.tex2chtml(m[2] || m[3] || m[4] || m[5], {display:false})); }
                    catch (error) { td.appendChild(document.createTextNode(m[0])); }
                    last = pattern.lastIndex;
                }
                td.appendChild(document.createTextNode(text.slice(last)));
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
        table.appendChild(body); wrapper.appendChild(table);
        return wrapper;
    }

    function _renderFormula(uid, fData, isTemporary) {
        if (!fData) {
            return _createErrorSpan('[Không tìm thấy công thức]');
        }

        if (fData.table && fData.table.version === 1) return _renderStructuredTable(fData.table);
        var conversionStatus = fData.conversion_status || fData.status;
        var verificationStatus = fData.verification_status;
        var renderError = fData.render_error;

        // Status: pending → show any stored preview, otherwise a clear review note.
        if (conversionStatus === 'pending' && !fData.latex && !fData.mathml) {
            if (fData.preview_url) {
                var preview = document.createElement('img');
                preview.src = fData.preview_url;
                preview.alt = 'Bản xem trước công thức';
                preview.className = 'formula-image';
                preview.style.cssText = 'display:inline-block;vertical-align:middle;max-height:45px;max-width:100%;margin:0 4px;';
                preview.title = 'Bản xem trước công thức cần kiểm tra';
                return preview;
            }

            // A static SVG preview saved during import is also exposed through
            // svg_cache_key after the FormulaAsset is persisted.
            if (fData.svg_cache_key && fData.svg_cache_key.indexOf('/static/') === 0) {
                return _createCachedSvgElement(
                    fData.svg_cache_key,
                    verificationStatus,
                    renderError,
                    fData.source_format === 'LaTeXBlock'
                );
            }

            return _createErrorSpan('[Chưa có bản hiển thị công thức]', renderError);
        }

        // Status: failed → show friendly error
        if (conversionStatus === 'failed' && !fData.latex && !fData.mathml) {
            // Older imports may still say "failed" even though a later
            // import generated and cached a usable SVG fallback.
            if (fData.svg_cache_key && fData.svg_cache_key.indexOf('/static/') === 0) {
                return _createCachedSvgElement(
                    fData.svg_cache_key,
                    verificationStatus,
                    renderError,
                    fData.source_format === 'LaTeXBlock'
                );
            }
            if (fData.source_format !== 'LaTeXBlock') {
                return _createErrorSpan('[Không thể chuyển đổi công thức]', renderError);
            }
            return _createRetryError(uid, '[Không thể chuyển đổi công thức]', renderError, isTemporary);
        }

        // Status: fallback_svg → go directly to SVG
        if (conversionStatus === 'fallback_svg') {
            if (fData.svg_cache_key && fData.svg_cache_key.indexOf('/static/') === 0) {
                return _createCachedSvgElement(
                    fData.svg_cache_key,
                    verificationStatus,
                    renderError,
                    fData.source_format === 'LaTeXBlock'
                );
            }
            return _createSvgElement(uid, verificationStatus);
        }

        // Try MathML first (highest priority)
        if (fData.mathml) {
            try {
                var mathNode = window.MathJax.mathml2chtml(fData.mathml);
                return _wrapWithReviewStatus(mathNode, verificationStatus, renderError);
            } catch (e) {
                console.warn('[FormulaRenderer] MathML render failed, trying LaTeX:', e.message);
            }
        }

        // Fallback 1: LaTeX
        if (fData.latex) {
            try {
                var latexNode = window.MathJax.tex2chtml(fData.latex);
                return _wrapWithReviewStatus(latexNode, verificationStatus, renderError);
            } catch (e) {
                console.warn('[FormulaRenderer] LaTeX render failed, trying SVG:', e.message);
            }
        }

        // Fallback 2: SVG from the formula endpoint
        if (fData.svg_cache_key) {
            return _createSvgElement(uid, verificationStatus);
        }

        // Everything failed
        return _createErrorSpan('[Lỗi hiển thị công thức]');
    }

    /**
     * Create SVG fallback element using secure <img> tag.
     */
    function _createSvgElement(uid, verificationStatus) {
        var img = document.createElement('img');
        img.src = '/api/formulas/' + encodeURIComponent(uid) + '/render.svg';
        img.alt = 'Công thức toán';
        img.className = 'formula-svg';
        img.style.cssText = 'display:inline-block;vertical-align:middle;max-height:45px;margin:0 4px;';
        img.onerror = function() {
            var errorSpan = _createErrorSpan('[Lỗi hiển thị công thức]');
            if (img.parentNode) {
                img.parentNode.replaceChild(errorSpan, img);
            }
        };
        return _wrapWithReviewStatus(img, verificationStatus);
    }

    function _createCachedSvgElement(url, verificationStatus, renderError, isBlock) {
        var img = document.createElement('img');
        img.src = url;
        img.alt = 'Công thức toán';
        img.className = isBlock ? 'formula-svg formula-block-svg' : 'formula-svg';
        img.style.cssText = isBlock
            ? 'display:block;width:auto;max-width:100%;height:auto;max-height:600px;object-fit:contain;margin:12px auto;cursor:zoom-in;'
            : 'display:inline-block;vertical-align:middle;max-height:45px;max-width:100%;margin:0 4px;';
        if (isBlock) {
            img.title = 'Nhấn để xem hình ở kích thước lớn';
            img.tabIndex = 0;
            img.setAttribute('role', 'button');
            img.setAttribute('aria-label', 'Phóng to hình công thức');
            img.addEventListener('click', function() { _openBlockSvg(url); });
            img.addEventListener('keydown', function(event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    _openBlockSvg(url);
                }
            });
        }
        img.onerror = function() {
            var errorSpan = _createErrorSpan('[Lỗi hiển thị công thức]');
            if (img.parentNode) img.parentNode.replaceChild(errorSpan, img);
        };
        return _wrapWithReviewStatus(img, verificationStatus, renderError);
    }

    function _makeZoomableControl(element, label, open) {
        element.classList.add('document-image-zoomable');
        element.title = 'Nhấn để xem hình ở kích thước lớn';
        element.tabIndex = 0;
        element.setAttribute('role', 'button');
        element.setAttribute('aria-label', 'Phóng to ' + (label || 'hình ảnh'));
        element.addEventListener('click', open);
        element.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                open();
            }
        });
        return element;
    }

    function _openBlockSvg(url) {
        _openImageLightbox(url, 'Công thức toán phóng to');
    }

    function _openImageLightbox(url, altText) {
        if (!url) return;
        var opener = document.activeElement;
        var dialog = document.createElement('dialog');
        dialog.className = 'formula-svg-lightbox';
        dialog.setAttribute('aria-label', altText || 'Hình ảnh phóng to');

        var heading = document.createElement('div');
        heading.className = 'formula-lightbox-heading';
        var title = document.createElement('h2');
        title.textContent = altText || 'Hình ảnh phóng to';
        var closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'btn btn-secondary btn-sm';
        closeButton.textContent = 'Đóng';
        closeButton.setAttribute('aria-label', 'Đóng hình ảnh phóng to');
        closeButton.autofocus = true;
        heading.appendChild(title);
        heading.appendChild(closeButton);
        dialog.appendChild(heading);

        var enlarged = document.createElement('img');
        enlarged.src = url;
        enlarged.alt = altText || 'Hình ảnh phóng to';
        enlarged.className = 'formula-lightbox-image';
        dialog.appendChild(enlarged);

        closeButton.addEventListener('click', function() { dialog.close(); });
        dialog.addEventListener('click', function(event) {
            if (event.target !== dialog) return;
            var bounds = dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
        });
        dialog.addEventListener('close', function() {
            dialog.remove();
            if (opener && opener.isConnected) opener.focus({preventScroll: true});
        }, {once: true});
        document.body.appendChild(dialog);
        dialog.showModal();
        closeButton.focus({preventScroll: true});
    }

    /**
     * Create a friendly error message span.
     */
    function _createErrorSpan(message, details) {
        var span = document.createElement('span');
        span.className = 'formula-error';
        span.textContent = message;
        if (details) span.title = details;
        return span;
    }

    function _createRetryError(uid, message, details, isTemporary) {
        var wrapper = document.createElement('span');
        wrapper.className = 'formula-retry-wrapper';
        wrapper.appendChild(_createErrorSpan(message, details));

        if (!document.body || document.body.getAttribute('data-can-retry-formulas') !== 'true') {
            return wrapper;
        }

        var retryUrl = '/api/formulas/' + encodeURIComponent(uid) + '/retry';
        if (isTemporary) {
            if (!window.currentImportSessionId) return wrapper;
            retryUrl = '/question-banks/import/'
                + encodeURIComponent(window.currentImportSessionId)
                + '/formulas/' + encodeURIComponent(uid) + '/retry';
        }

        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-secondary btn-sm formula-retry-button';
        button.textContent = 'Thử lại';
        button.addEventListener('click', function() {
            var csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
            var csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';
            button.disabled = true;
            button.textContent = 'Đang thử…';
            fetch(retryUrl, {
                method: 'POST',
                headers: {'X-CSRFToken': csrfToken}
            })
            .then(function(response) {
                return response.json().then(function(data) {
                    return {ok: response.ok, data: data};
                });
            })
            .then(function(result) {
                if (result.data && result.data.formula && wrapper.parentNode) {
                    var rendered = _renderFormula(uid, result.data.formula, !!isTemporary);
                    wrapper.parentNode.replaceChild(rendered, wrapper);
                    return;
                }
                button.disabled = false;
                button.textContent = 'Thử lại';
                if (result.data && result.data.message) wrapper.title = result.data.message;
            })
            .catch(function() {
                button.disabled = false;
                button.textContent = 'Thử lại';
            });
        });
        wrapper.appendChild(button);
        return wrapper;
    }

    /**
     * Wrap a math node with review indicator if needed.
     */
    function _wrapWithReviewStatus(mathNode, verificationStatus, details) {
        if (verificationStatus === 'needs_review') {
            var wrapper = document.createElement('span');
            wrapper.className = 'formula-needs-review';
            wrapper.title = details || 'Công thức cần kiểm tra lại độ chính xác';
            if (mathNode.classList.contains('formula-block-svg')) wrapper.classList.add('formula-block-review');
            wrapper.appendChild(mathNode);
            return wrapper;
        }

        if (!mathNode.classList.contains('formula-block-svg')) {
            mathNode.style.display = 'inline-block';
            mathNode.style.margin = '0 4px';
        }
        return mathNode;
    }

    /**
     * Convert [[formula:<id>]] tokens in text into readable LaTeX math ($...$).
     * Used for edit mode inputs and textareas so teachers see math formulas instead of raw tokens.
     */
    function toEditableLatex(str, formulasMap) {
        if (!str || typeof str !== 'string') return str || '';
        formulasMap = formulasMap || {};
        var globalCache = window.FormulaAssetCache || {};
        return str.replace(/\[\[formula:([^\]]+)\]\]/g, function(match, id) {
            var f = formulasMap[id] || globalCache[id];
            if (f) {
                if (f.latex) {
                    var lx = f.latex.trim();
                    if (!lx.startsWith('$') && !lx.startsWith('\\(') && !lx.startsWith('\\[') && !lx.startsWith('\\begin{')) {
                        return '$' + lx + '$';
                    }
                    return lx;
                }
                if (f.source_text) {
                    var src = f.source_text.trim();
                    if (!src.startsWith('$') && !src.startsWith('\\(') && !src.startsWith('\\[') && !src.startsWith('\\begin{')) {
                        return '$' + src + '$';
                    }
                    return src;
                }
            }
            return match;
        });
    }

    function renderElement(el, formulasMap) {
        if (!el) return;
        renderFormulas(el, formulasMap || {});
    }

    // Public API
    return {
        renderFormulas: renderFormulas,
        renderElement: renderElement,
        openImageLightbox: _openImageLightbox,
        toEditableLatex: toEditableLatex
    };
})();

// Backward compatibility & convenience
window.renderFormulas = window.FormulaRenderer.renderFormulas;
window.toEditableLatex = window.FormulaRenderer.toEditableLatex;

