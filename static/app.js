/* ============================================================
   AQMD Rule Finder — Frontend JavaScript
   ============================================================ */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────
  let currentQuery = '';
  let currentOffset = 0;
  let currentTotal = 0;
  let allResults   = [];
  const PAGE_SIZE  = 20;
  let currentSort  = 'relevance';
  let sseSource    = null;

  // ── DOM refs ───────────────────────────────────────────
  const searchInput    = document.getElementById('search-input');
  const searchBtn      = document.getElementById('search-btn');
  const clearBtn       = document.getElementById('clear-btn');
  const resultsSection = document.getElementById('results-section');
  const resultsList    = document.getElementById('results-list');
  const resultsSummary = document.getElementById('results-summary');
  const emptyState     = document.getElementById('empty-state');
  const emptyQuery     = document.getElementById('empty-query');
  const welcomeState   = document.getElementById('welcome-state');
  const progressSection= document.getElementById('progress-section');
  const progressBar    = document.getElementById('progress-bar');
  const progressMsg    = document.getElementById('progress-message');
  const progressDetail = document.getElementById('progress-detail');
  const progressIcon   = document.getElementById('progress-phase-icon');
  const statusBadge    = document.getElementById('status-badge');
  const statusText     = document.getElementById('status-text');
  const refreshBtn     = document.getElementById('refresh-btn');
  const sortSelect     = document.getElementById('sort-select');
  const loadMoreWrap   = document.getElementById('load-more-wrap');
  const loadMoreBtn    = document.getElementById('load-more-btn');
  const statsBar       = document.getElementById('stats-bar');
  const statsRules     = document.getElementById('stats-rules-count');
  const statsPages     = document.getElementById('stats-pages-count');
  const statsUpdated   = document.getElementById('stats-updated');
  const pdfModal       = document.getElementById('pdf-modal');
  const pdfIframe      = document.getElementById('pdf-iframe');
  const pdfModalTitle  = document.getElementById('pdf-modal-title');
  const pdfModalSub    = document.getElementById('pdf-modal-subtitle');
  const pdfOpenExt     = document.getElementById('pdf-open-external');
  const pdfClose       = document.getElementById('pdf-modal-close');
  const pdfBackdrop    = document.getElementById('pdf-modal-backdrop');

  // ── SSE progress stream ────────────────────────────────
  function startProgressStream() {
    if (sseSource) sseSource.close();
    sseSource = new EventSource('/api/progress/stream');

    sseSource.onmessage = function (evt) {
      const data = JSON.parse(evt.data);
      updateProgress(data);
    };

    sseSource.onerror = function () {
      // SSE dropped — fall back to polling
      sseSource.close();
      sseSource = null;
      setTimeout(pollStatus, 3000);
    };
  }

  function pollStatus() {
    fetch('/api/status')
      .then(r => r.json())
      .then(data => {
        updateProgress(data);
        if (data.phase === 'downloading' || data.phase === 'scanning') {
          setTimeout(pollStatus, 2000);
        }
      })
      .catch(() => setTimeout(pollStatus, 5000));
  }

  function updateProgress(data) {
    const phase = data.phase || 'idle';
    const indexed = data.indexed_rules || 0;
    const total   = data.total_rules   || 0;
    const pages   = data.total_pages   || 0;
    const message = data.message || '';

    // Status badge
    statusBadge.className = 'status-badge';
    if (phase === 'done') {
      statusBadge.classList.add('status-ready');
      statusText.textContent = `${indexed} rules ready`;
    } else if (phase === 'error') {
      statusBadge.classList.add('status-error');
      statusText.textContent = 'Error';
    } else if (phase === 'idle') {
      statusBadge.classList.add('status-loading');
      statusText.textContent = 'Starting…';
    } else {
      statusBadge.classList.add('status-indexing');
      statusText.textContent = phase === 'scanning' ? 'Scanning…' : `Indexing ${indexed}/${total}`;
    }

    // Progress bar section
    const isActive = phase === 'scanning' || phase === 'downloading';
    progressSection.style.display = isActive ? 'block' : 'none';

    if (isActive) {
      progressMsg.textContent = message;
      if (phase === 'downloading' && total > 0) {
        const pct = Math.round((data.current / total) * 100);
        progressBar.style.width = pct + '%';
        progressDetail.textContent = `${data.current} of ${total} rules processed`;
        progressIcon.textContent = '📥';
      } else {
        progressBar.style.width = '30%';
        progressDetail.textContent = '';
        progressIcon.textContent = '🔍';
      }
    }

    // Stats bar on welcome screen
    if (indexed > 0) {
      statsBar.style.display = 'flex';
      statsRules.textContent = `${indexed.toLocaleString()} rules indexed`;
      statsPages.textContent = `${pages.toLocaleString()} pages searchable`;
      statsUpdated.textContent = data.last_update ? `Updated ${data.last_update}` : '';
    }
  }

  // ── Search ─────────────────────────────────────────────
  function doSearch(query, reset) {
    query = query.trim();
    if (!query) return;

    if (reset) {
      currentOffset = 0;
      allResults = [];
    }

    currentQuery = query;
    searchInput.value = query;
    clearBtn.style.display = 'block';
    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching…';

    const params = new URLSearchParams({
      q: query,
      limit: PAGE_SIZE,
      offset: currentOffset,
    });

    fetch('/api/search?' + params)
      .then(r => r.json())
      .then(data => {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
        currentTotal = data.total;
        allResults = allResults.concat(data.results || []);
        renderResults(query, data.total, reset);
      })
      .catch(err => {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
        console.error('Search error:', err);
        showError('Search failed. Please try again.');
      });
  }

  function renderResults(query, total, reset) {
    welcomeState.style.display = 'none';
    emptyState.style.display   = 'none';

    if (allResults.length === 0) {
      resultsSection.style.display = 'none';
      emptyState.style.display = 'block';
      emptyQuery.textContent = query;
      return;
    }

    resultsSection.style.display = 'block';
    if (reset) resultsList.innerHTML = '';

    resultsSummary.textContent =
      total === 1 ? '1 rule matches' : `${total.toLocaleString()} matches across ${allResults.length} rules`;

    // Sort
    let sorted = [...allResults];
    if (currentSort === 'regulation') {
      sorted.sort((a, b) => a.regulation_num.localeCompare(b.regulation_num) || a.rule_number.localeCompare(b.rule_number));
    } else if (currentSort === 'rule_number') {
      sorted.sort((a, b) => {
        const na = parseFloat(a.rule_number) || 0;
        const nb = parseFloat(b.rule_number) || 0;
        return na - nb;
      });
    }

    if (reset) resultsList.innerHTML = '';
    sorted.slice(reset ? 0 : sorted.length - allResults.length).forEach(rule => {
      resultsList.appendChild(buildRuleCard(rule));
    });

    loadMoreWrap.style.display = (currentOffset + PAGE_SIZE < total) ? 'block' : 'none';
  }

  function buildRuleCard(rule) {
    const card = document.createElement('div');
    card.className = 'rule-card';

    const localPdfUrl = rule.local_filename
      ? `/pdf/${encodeURIComponent(rule.local_filename)}`
      : null;
    const externalUrl = rule.pdf_url;
    const openUrl = localPdfUrl || externalUrl;

    const matches = rule.matches || [];
    const matchCount = matches.length;

    card.innerHTML = `
      <div class="rule-card-header">
        <span class="rule-badge">Rule ${escHtml(rule.rule_number)}</span>
        <div class="rule-meta">
          <div class="rule-title">${escHtml(rule.title)}</div>
          <div class="rule-regulation">
            Regulation <strong>${escHtml(rule.regulation_num)}</strong>
            &mdash; ${escHtml(rule.regulation_name || '')}
          </div>
          ${rule.amendment_date
            ? `<div class="rule-amendment">Last amended: ${escHtml(rule.amendment_date)}</div>`
            : ''}
        </div>
        <div class="rule-card-actions">
          <button class="btn btn-primary btn-sm open-pdf-btn"
            data-url="${escAttr(openUrl)}"
            data-page="1"
            data-title="${escAttr(`Rule ${rule.rule_number}: ${rule.title}`)}"
            data-sub="${escAttr(`Regulation ${rule.regulation_num} — ${rule.regulation_name || ''}`)}"
            data-ext="${escAttr(externalUrl)}">
            &#128196; View Rule
          </button>
        </div>
      </div>
      <div class="rule-matches">
        ${matches.slice(0, 3).map((m, idx) => `
          <div class="match-item open-pdf-btn"
            data-url="${escAttr(openUrl)}"
            data-page="${m.page}"
            data-title="${escAttr(`Rule ${rule.rule_number}: ${rule.title}`)}"
            data-sub="${escAttr(`Regulation ${rule.regulation_num} — ${rule.regulation_name || ''} — Page ${m.page}`)}"
            data-ext="${escAttr(externalUrl + '#page=' + m.page)}">
            <div class="match-page-label">Page ${m.page}</div>
            <div class="match-excerpt">${m.excerpt}</div>
          </div>
        `).join('')}
        ${matchCount > 3
          ? `<div class="match-count-note">+ ${matchCount - 3} more matching passage${matchCount - 3 > 1 ? 's' : ''} in this rule</div>`
          : ''}
      </div>
    `;

    // Bind PDF open events
    card.querySelectorAll('.open-pdf-btn').forEach(btn => {
      btn.addEventListener('click', function () {
        openPdf(
          this.dataset.url,
          parseInt(this.dataset.page) || 1,
          this.dataset.title,
          this.dataset.sub,
          this.dataset.ext
        );
      });
    });

    return card;
  }

  // ── PDF Viewer ─────────────────────────────────────────
  function openPdf(url, page, title, subtitle, externalUrl) {
    const urlWithPage = url + (url.includes('#') ? '' : `#page=${page}`);
    pdfIframe.src = urlWithPage;
    pdfModalTitle.textContent = title;
    pdfModalSub.textContent = subtitle;
    pdfOpenExt.href = externalUrl || urlWithPage;
    pdfModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function closePdf() {
    pdfModal.style.display = 'none';
    pdfIframe.src = '';
    document.body.style.overflow = '';
  }

  pdfClose.addEventListener('click', closePdf);
  pdfBackdrop.addEventListener('click', closePdf);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && pdfModal.style.display !== 'none') closePdf();
  });

  // ── Refresh ────────────────────────────────────────────
  refreshBtn.addEventListener('click', function () {
    refreshBtn.disabled = true;
    refreshBtn.textContent = 'Checking…';
    fetch('/api/refresh', { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '&#8635; Check for Updates';
        if (!sseSource) startProgressStream();
      })
      .catch(() => {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '&#8635; Check for Updates';
      });
  });

  // ── Hint chips ─────────────────────────────────────────
  document.querySelectorAll('.hint-chip').forEach(chip => {
    chip.addEventListener('click', function () {
      doSearch(this.dataset.query, true);
    });
  });

  // ── Sort ───────────────────────────────────────────────
  sortSelect.addEventListener('change', function () {
    currentSort = this.value;
    if (currentQuery) renderResults(currentQuery, currentTotal, true);
  });

  // ── Load more ──────────────────────────────────────────
  loadMoreBtn.addEventListener('click', function () {
    currentOffset += PAGE_SIZE;
    doSearch(currentQuery, false);
  });

  // ── Input events ───────────────────────────────────────
  searchInput.addEventListener('input', function () {
    clearBtn.style.display = this.value ? 'block' : 'none';
  });

  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') doSearch(this.value, true);
  });

  searchBtn.addEventListener('click', function () {
    doSearch(searchInput.value, true);
  });

  clearBtn.addEventListener('click', function () {
    searchInput.value = '';
    clearBtn.style.display = 'none';
    currentQuery = '';
    allResults = [];
    resultsSection.style.display = 'none';
    emptyState.style.display = 'none';
    welcomeState.style.display = 'block';
    searchInput.focus();
  });

  // ── Helpers ────────────────────────────────────────────
  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escAttr(str) {
    return String(str || '').replace(/"/g, '&quot;');
  }

  function showError(msg) {
    statusBadge.className = 'status-badge status-error';
    statusText.textContent = msg;
  }

  // ── Init ───────────────────────────────────────────────
  startProgressStream();
  searchInput.focus();

})();
