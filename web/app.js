// ===== DOM Elements =====
const views = document.querySelectorAll('.view');
const tabs = document.querySelectorAll('.nav-links li');
const stagesGrid = document.getElementById('stages-grid');
const subjectsGrid = document.getElementById('subjects-grid');
const stageDetailsTitle = document.getElementById('stage-details-title');

const penStatus = document.getElementById('pen-status');
const storageUsed = document.getElementById('storage-used');
const storageText = document.getElementById('storage-text');
const syncBtn = document.getElementById('sync-btn');
const syncProgress = document.getElementById('sync-progress');
const syncStatusText = document.getElementById('sync-status-text');
const syncSpeed = document.getElementById('sync-speed');

let currentStage = null;
let isSyncing = false;
let globalStagesData = {};
let currentPenDrive = null;
let globalSelectedSubjects = new Map(); // act -> {act, subject}
let res_display_order = [];

// ===== Tab Switching =====
function switchTab(tabId) {
    if(tabId === 'downloads') return; // يتحكم بها القائمة المنسدلة

    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    let targetView = document.getElementById('view-' + tabId);
    let targetBtn  = document.getElementById('tab-' + tabId);

    if(targetView) targetView.classList.add('active');
    if(targetBtn)  targetBtn.classList.add('active');

    if(tabId === 'pen') {
        loadPenContents();
    }
}

// ===== Downloads Dropdown =====
function toggleDownloadsDropdown() {
    let dd = document.getElementById('downloads-dropdown');
    dd.classList.toggle('show');
}

function closeDownloadsDropdown() {
    let dd = document.getElementById('downloads-dropdown');
    if(dd) dd.classList.remove('show');
}

// ===== Search =====
function normalizeArabic(text) {
    if(!text) return "";
    return text.replace(/[أإآا]/g, 'ا')
               .replace(/ة/g, 'ه')
               .replace(/ى/g, 'ي')
               .replace(/ـ/g, '')
               .replace(/َ|ً|ُ|ٌ|ِ|ٍ|ْ|ّ/g, '');
}

function handleSearch() {
    const rawQuery = document.getElementById('search-input').value.toLowerCase();
    const query = normalizeArabic(rawQuery);

    // إصلاح: إذا كان البحث فارغاً، عُد للعرض السابق بدلاً من شاشة فارغة
    if (query === '') {
        if (currentStage) {
            openStage(currentStage);
        } else {
            switchTab('home');
        }
        return;
    }

    switchTab('search');

    const searchGrid = document.getElementById('search-results-grid');
    searchGrid.innerHTML = '';

    let resultCount = 0;

    for(let stageName in globalStagesData) {
        let subjects = globalStagesData[stageName];
        let queryWords = query.split(' ').filter(w => w.trim().length > 0);
        subjects.forEach((subj, index) => {
            let subjectLower = normalizeArabic(subj.subject.toLowerCase());
            let match = queryWords.length === 0 || queryWords.every(word => subjectLower.includes(word));
            if(match) {
                resultCount++;
                let currentId = resultCount;
                let safeName = subj.subject.split('\\').join('-').split('/').join('-').split(':').join('-').trim();
                let isSelected = globalSelectedSubjects.has(subj.act);
                let checkedAttr = isSelected ? 'checked' : '';
                let itemClass = isSelected ? 'subject-item checked' : 'subject-item';

                let isDownloaded = subj.act && typeof downloadedFilesCache !== 'undefined' && downloadedFilesCache[subj.act.trim().toLowerCase()] !== undefined;
                let badgeHtml = isDownloaded ? `<span style="background: rgba(29, 185, 84, 0.15); color: #1DB954; border: 1px solid rgba(29, 185, 84, 0.3); padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 800; margin-right: 8px;">متوفرة بالقلم ✔</span>` : '';

                let corruptedBadge = subj.is_corrupted
                    ? `<span style="background: rgba(255, 149, 0, 0.15); color: #FF9500; border: 1px solid rgba(255, 149, 0, 0.3); padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 800; margin-right: 8px; animation: pulseGlow 2s infinite;">تحديث متاح ✨</span>`
                    : '';

                searchGrid.innerHTML += `
                    <div class="${itemClass}" style="display:flex; align-items:center; justify-content:space-between; width:100%; cursor:pointer; padding: 12px 16px; border-radius: 16px; background: var(--bg-elevated); border: 1px solid rgba(255,255,255,0.05); margin-bottom: 12px;" id="subj-search-${currentId}" onclick="toggleSubject('${subj.act}', 'cb-search-${currentId}', '${subj.subject.replace(/'/g, "\\'")}', ${subj.size_bytes || 0})">
                        <div style="display:flex; align-items:center; flex:1;">
                            <img class="subject-img" src="assets/subjects/${safeName}.png" onerror="this.src='https://ui-avatars.com/api/?name=ملزمة&background=282828&color=1DB954'" style="width: 64px; height: 64px; border-radius: 12px; object-fit: cover;">
                            <div class="subject-info" style="display:flex; flex-direction:column; justify-content:center; margin-right: 16px;">
                                <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">
                                    <div class="subject-title" style="margin-bottom: 0;">${subj.subject.replace(/\s*\/\s*/g, ' - ')} ${corruptedBadge}</div>
                                    <div style="font-size:12px; color:var(--text-subdued); font-weight:800; background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 6px;">${subj.size_mb ? subj.size_mb.toFixed(1) : '0.0'} MB</div>
                                    ${badgeHtml}
                                </div>
                                <div style="font-size:13px; color:var(--text-subdued); font-weight:700;">${stageName}</div>
                            </div>
                        </div>
                        <div style="margin-left: 16px;">
                            <input type="checkbox" class="checkbox-custom" id="cb-search-${currentId}" ${checkedAttr} data-act="${subj.act}" data-subject="${subj.subject}" data-size="${subj.size_bytes || 0}" onclick="event.stopPropagation();" onchange="onSubjectCheckboxChange(this);">
                        </div>
                    </div>
                `;
            }
        });
    }

    if (resultCount === 0) {
        searchGrid.innerHTML = '<p style="color:var(--text-subdued); font-size:16px;">لا توجد نتائج مطابقة لبحثك.</p>';
    }
}

// ===== Download / Sync =====
function startSync() {
    if(!currentPenDrive) {
        showAlert("عذراً", "يرجى توصيل القلم أولاً للبدء بالتحميل!");
        return;
    }

    let btn = document.getElementById('sync-btn');
    if (btn && btn.innerHTML.includes("استئناف")) {
        if (!navigator.onLine) {
            showAlert("انقطاع الإنترنت", "تأكد من اتصالك بالإنترنت أولاً قبل الاستئناف.");
            return;
        }
        window.networkErrorAlertShown = false;
        isSyncing = true;
        resumeAllPaused();
        return;
    }

    if(isSyncing) return;
    isSyncing = true;
    if(btn) {
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.7';
    }

    let selectedFiles = [];
    globalSelectedSubjects.forEach((val, act) => {
        let size = "0.0 MB";
        let sizeB = val.size_bytes || 0;
        for(let stage in globalStagesData) {
            let found = globalStagesData[stage].find(s => s.act === act);
            if(found && found.size_mb) size = found.size_mb.toFixed(1) + " MB";
            if(found && found.size_bytes) sizeB = found.size_bytes;
        }
        selectedFiles.push({"act": act, "subject": val.subject, "size": size, "size_bytes": sizeB});
    });

    if(selectedFiles.length === 0) {
        // إعادة الزر إذا لم يوجد تحديد
        isSyncing = false;
        if(btn) { btn.style.pointerEvents = 'auto'; btn.style.opacity = '1'; }
        showAlert("لا يوجد تحديد", "يرجى تحديد ملزمة واحدة على الأقل للتحديث.");
        return;
    }

    // فلترة الملفات الموجودة والسليمة
    let filesToUpdate = [];
    selectedFiles.forEach(f => {
        let actLower = f.act.toLowerCase();
        let currentSize = downloadedFilesCache[actLower] ? downloadedFilesCache[actLower].size_bytes : 0;
        let requiredBytes = f.size_bytes || 0;

        let isCorrupt = false;
        for(let stage in globalStagesData) {
            let found = globalStagesData[stage].find(s => s.act === f.act);
            if(found && found.is_corrupted) isCorrupt = true;
        }

        if (currentSize === 0 || isCorrupt || (requiredBytes > 0 && requiredBytes > currentSize)) {
            filesToUpdate.push(f);
        }
    });

    if (filesToUpdate.length === 0) {
        isSyncing = false;
        if(btn) { btn.style.pointerEvents = 'auto'; btn.style.opacity = '1'; }
        showAlert("اكتمل مسبقاً", "جميع الملازم المحددة موجودة في القلم ومطابقة بالكامل!");
        return;
    }

    selectedFiles = filesToUpdate;

    // حساب المساحة المطلوبة
    let totalRequiredBytes = 0;
    selectedFiles.forEach(f => {
        let actLower = f.act.toLowerCase();
        let currentSize = downloadedFilesCache[actLower] ? downloadedFilesCache[actLower].size_bytes : 0;
        let requiredBytes = f.size_bytes || 0;
        if (requiredBytes > currentSize) {
            totalRequiredBytes += (requiredBytes - currentSize);
        }
    });

    let requiredWithBuffer = totalRequiredBytes + (50 * 1024 * 1024);

    eel.get_pen_space(currentPenDrive)(function(res) {
        if (res && res.free_bytes !== undefined) {
            if (requiredWithBuffer > res.free_bytes) {
                // إعادة الزر إذا لم تكفِ المساحة
                isSyncing = false;
                if(btn) { btn.style.pointerEvents = 'auto'; btn.style.opacity = '1'; }
                let reqGB = (totalRequiredBytes / (1024**3)).toFixed(2);
                let freeGB = (res.free_bytes / (1024**3)).toFixed(2);
                document.getElementById('space-modal-msg').innerText = `أنت تحاول تحميل ملفات بحجم ${reqGB} GB تقريباً، لكن المساحة الحرة المتبقية في القلم هي ${freeGB} GB فقط.`;
                document.getElementById('space-modal').style.display = 'flex';
                return;
            }
        }
        proceedWithSync(selectedFiles);
    });
}

function proceedWithSync(selectedFiles) {
    // isSyncing تم ضبطها بالفعل في startSync
    window.hasSuccessfulDownloads = false;
    window.hasFailedDownloads = false;
    document.getElementById('sync-btn').classList.add('loading');
    document.getElementById('sync-btn').innerText = "جاري التحديث...";

    // إظهار القائمة المنسدلة
    document.getElementById('downloads-dropdown').classList.add('show');
    document.getElementById('empty-downloads').style.display = 'none';

    let dlList = document.getElementById('downloads-list');
    dlList.innerHTML = '';

    // بناء قائمة التحميل كسلسلة نصية واحدة لتحسين الأداء
    let dlHtml = '';
    selectedFiles.forEach(file => {
        let safeName = file.subject.split('\\').join('-').split('/').join('-').split(':').join('-').trim();
        dlHtml += `
            <div class="dl-item" id="dl-item-${file.act}">
                <img class="dl-item-img" src="assets/subjects/${safeName}.png" onerror="this.src='https://ui-avatars.com/api/?name=ملزمة&background=282828&color=1DB954'">
                <div class="dl-item-content">
                    <div class="dl-item-header">
                        <div class="dl-item-title" id="dl-title-${file.act}">${file.subject} (${file.size})</div>
                        <div class="dl-controls" id="dl-controls-${file.act}">
                            <button class="dl-btn dl-pause" id="dl-pause-${file.act}" onclick="pauseSyncItem('${file.act}')" title="إيقاف مؤقت">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
                            </button>
                            <button class="dl-btn dl-cancel" onclick="cancelSyncItem('${file.act}')" title="إلغاء">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                            </button>
                        </div>
                    </div>
                    <div class="dl-bar-container">
                        <div class="dl-bar-fill" id="dl-progress-fill-${file.act}" style="width: 0%;"></div>
                    </div>
                    <div class="dl-stats">
                        <span id="dl-speed-${file.act}" style="color: var(--brand-color);">--</span>
                        <span id="dl-percentage-${file.act}">0%</span>
                    </div>
                </div>
            </div>
        `;
    });
    dlList.innerHTML = dlHtml;

    // أيقونة الدوران
    document.getElementById('tab-downloads').innerHTML = '<svg class="spinner" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1DB954" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>';

    let syncBtn = document.getElementById('sync-btn');
    if(syncBtn) {
        syncBtn.classList.add('loading');
        syncBtn.innerHTML = 'جاري التحديث... <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 6px;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>';
        syncBtn.style.backgroundColor = "#1DB954";
        syncBtn.style.animation = "pulseGlowBar 2s infinite";
        syncBtn.style.pointerEvents = "none";
    }

    globalSelectedSubjects.clear();

    toggleDashboard(true);

    eel.start_sync(selectedFiles, currentPenDrive)();
}

function pauseSyncItem(act) {
    let title = document.getElementById(`dl-title-${act}`);
    let pauseBtn = document.getElementById(`dl-pause-${act}`);

    if (pauseBtn.classList.contains('paused')) {
        if (!navigator.onLine) {
            showAlert("انقطاع الإنترنت", "تأكد من اتصالك بالإنترنت أولاً قبل الاستئناف.");
            return;
        }
        window.networkErrorAlertShown = false;
        
        toggleDashboard(true);

        // استئناف
        pauseBtn.classList.remove('paused');
        title.innerText = "جاري الاستئناف...";
        pauseBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

        let itemToResume = null;
        if (globalSelectedSubjects && globalSelectedSubjects.has(act)) {
            let val = globalSelectedSubjects.get(act);
            itemToResume = {"act": act, "subject": val.subject, "size_bytes": val.size_bytes || 0};
        } else {
            for(let stage in globalStagesData) {
                let subj = globalStagesData[stage].find(s => s.act === act);
                if (subj) {
                    itemToResume = {"act": act, "subject": subj.subject, "size_bytes": subj.size_bytes || 0};
                    break;
                }
            }
        }

        if (itemToResume) {
            eel.resume_download(itemToResume, currentPenDrive)();
        }

        // التحقق مما إذا تم استئناف جميع الملفات لتحديث الزر الرئيسي
        setTimeout(() => {
            let anyPaused = false;
            document.querySelectorAll('[id^="dl-pause-"]').forEach(pb => {
                if(pb.classList.contains('paused')) anyPaused = true;
            });
            if (!anyPaused) {
                let syncBtn = document.getElementById('sync-btn');
                if (syncBtn && syncBtn.innerHTML.includes("استئناف")) {
                    syncBtn.innerHTML = '<div class="spinner"></div> جاري التحديث...';
                    syncBtn.style.backgroundColor = "rgba(255, 255, 255, 0.1)";
                    syncBtn.classList.add('loading');
                    // لا نعطل الزر هنا في حال أراد إيقاف الكل لاحقاً (رغم أنه غير مدعوم حالياً للإيقاف الشامل)
                    // لكن نجعله كالسابق
                    syncBtn.style.pointerEvents = "none";
                }
            }
        }, 100);
    } else {
        // إيقاف مؤقت
        pauseBtn.classList.add('paused');
        title.innerText = "تم الإيقاف مؤقتاً";
        document.getElementById(`dl-speed-${act}`).innerText = "--";
        pauseBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
        eel.pause_download(act)();
    }
}

function cancelSyncItem(act) {
    let itemDiv = document.getElementById(`dl-item-${act}`);
    if (itemDiv) itemDiv.remove();

    eel.cancel_download(act)();

    checkAllDownloadsFinished();
}

// استقبال إشعار انقطاع الشبكة من Python
eel.expose(showStageDownloadError);
function showStageDownloadError() {
    window.hasFailedDownloads = true;
}

// Global mouse tracking for dynamic toast placement
document.addEventListener('mousedown', (e) => {
    window.lastMouseX = e.clientX;
    window.lastMouseY = e.clientY;
}, true);

eel.expose(notify_pen_error);
function notify_pen_error(act) {
    window.hasFailedDownloads = true;
    
    // تبديل زر الإيقاف المؤقت إلى "متوقف"
    let pauseBtn = document.getElementById(`dl-pause-${act}`);
    if(pauseBtn) {
        pauseBtn.classList.add('paused');
        pauseBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    }
    let title = document.getElementById(`dl-title-${act}`);
    if(title) title.innerText = "فصل القلم - موقوف";

    let syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.innerHTML = "استئناف التحديث";
        syncBtn.style.backgroundColor = "#FF9500";
        syncBtn.classList.remove('loading');
        syncBtn.style.animation = "none";
        syncBtn.style.pointerEvents = "auto";
        syncBtn.style.opacity = "1";
    }
}

eel.expose(notify_network_error);
function notify_network_error(act) {
    window.hasFailedDownloads = true;
    
    // تبديل زر الإيقاف المؤقت إلى "متوقف"
    let pauseBtn = document.getElementById(`dl-pause-${act}`);
    if(pauseBtn) {
        pauseBtn.classList.add('paused');
        pauseBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    }
    let title = document.getElementById(`dl-title-${act}`);
    if(title) title.innerText = "انقطع الاتصال - موقوف";

    let syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.innerHTML = "استئناف التحديث";
        syncBtn.style.backgroundColor = "#FF9500";
        syncBtn.classList.remove('loading');
        syncBtn.style.animation = "none";
        syncBtn.style.pointerEvents = "auto";
        syncBtn.style.opacity = "1";
    }

    // إصلاح #2: لا نمسح globalSelectedSubjects عند انقطاع الشبكة
    // حتى لا يضطر المستخدم لإعادة التحديد يدوياً بعد استعادة الاتصال
    // التحديد يبقى كما هو ليتمكن من الضغط على زر الاستئناف مباشرة
    if (!window.networkErrorAlertShown) {
        window.networkErrorAlertShown = true;
        showAlert("انقطاع الإنترنت", "انقطع الاتصال بالإنترنت، يرجى التحقق من الشبكة للمواصلة. يمكنك استئناف التحميل لاحقاً.");
        setTimeout(() => { window.networkErrorAlertShown = false; }, 10000);
    }
}

function resumeAllPaused() {
    let syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.classList.add('loading');
        syncBtn.innerHTML = 'جاري التحديث... <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 6px;"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>';
        syncBtn.style.backgroundColor = "#1DB954";
        syncBtn.style.animation = "pulseGlowBar 2s infinite";
        syncBtn.style.pointerEvents = "none";
    }

    toggleDashboard(true);
    let dropdown = document.getElementById('downloads-dropdown');
    if (dropdown) dropdown.classList.add('show');

    document.querySelectorAll('[id^="dl-pause-"]').forEach(pauseBtn => {
        if (pauseBtn.classList.contains('paused')) {
            let act = pauseBtn.id.replace('dl-pause-', '');
            pauseSyncItem(act);
        }
    });
}

// إصلاح #5 (JS): استقبال إشعار فصل القلم أثناء نقل الملف
eel.expose(show_pen_disconnected);
function show_pen_disconnected() {
    showAlert(
        "تم فصل القلم",
        "تم فصل القلم، يرجى إعادة ربطه لنقل الملفات. سيتم استئناف النقل تلقائياً بمجرد إعادة التوصيل."
    );
    document.querySelectorAll('.dl-item-title').forEach(el => {
        if(!el.innerText.includes('اكتمل') && !el.innerText.includes('فشل')) {
            el.innerText = "جاري انتظار إعادة توصيل القلم...";
        }
    });

    let penTextEl = document.getElementById('pen-text');
    if (penTextEl) {
        penTextEl.innerText = "القلم غير متصل";
        penTextEl.style.color = "#FF3B30";
        penTextEl.style.animation = "pulseRedText 2s infinite";
    }
    let penStatusEl = document.getElementById('pen-status');
    if (penStatusEl) {
        penStatusEl.style.background = "rgba(0,0,0,0.5)";
        penStatusEl.style.border = "1px solid transparent";
    }
}

eel.expose(show_pen_reconnected);
function show_pen_reconnected(driveLetter) {
    let penTextEl = document.getElementById('pen-text');
    if (penTextEl) {
        penTextEl.innerText = "القلم متصل";
        penTextEl.style.color = "#1DB954";
        penTextEl.style.animation = "pulseGreenText 2s infinite";
    }
    let penStatusEl = document.getElementById('pen-status');
    if (penStatusEl) {
        penStatusEl.style.background = "rgba(29, 185, 84, 0.1)";
        penStatusEl.style.border = "1px solid rgba(29, 185, 84, 0.3)";
    }
    let modal = document.getElementById('alert-modal');
    if (modal && modal.style.display === 'flex') {
        let title = document.getElementById('alert-title');
        if (title && title.innerText === "تم فصل القلم") {
            modal.style.display = 'none';
        }
    }
}

eel.expose(sync_batch_complete);
function sync_batch_complete() {
    // يُستدعى مرة واحدة فقط من Python بعد انتهاء جميع الملفات
    let result = resetDownloadButton();

    // إخفاء القائمة داخلياً ولكن لا نغلق القائمة المنسدلة إلا بعد ضغط "موافق"
    setTimeout(() => {
        // لا تمسح القائمة إذا كانت هناك فشل في التنزيلات، لكي يتمكن المستخدم من استئنافها
        if (!result.hadFailure) {
            let dlList = document.getElementById('downloads-list');
            if (dlList) dlList.innerHTML = '';

            let emptyEl = document.getElementById('empty-downloads');
            if (emptyEl) emptyEl.style.display = 'block';
        }
    }, 2500);
}

function checkAllDownloadsFinished() {
    let dlList = document.getElementById('downloads-list');
    if (dlList && dlList.children.length === 0) {
        document.getElementById('empty-downloads').style.display = 'block';
        window.hasFailedDownloads = false;
        resetDownloadButton();
    }
}

function resetDownloadButton() {
    // إصلاح #2: حفظ قيمة isSyncing قبل تصفيرها للتحقق منها لاحقاً
    let wasActuallySyncing = isSyncing;
    // إصلاح: يجب حفظ هذه القيم لأننا نقوم بتصفيرها قبل استخدامها بالأسفل
    let hadSuccess = window.hasSuccessfulDownloads;
    let hadFailure = window.hasFailedDownloads;

    // إعادة أيقونة التحميل
    try {
        let tabDl = document.getElementById('tab-downloads');
        if (tabDl) tabDl.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg><div id="dl-active-indicator" class="download-active-indicator" style="display: none;"></div>';
    } catch(e) {}

    // إعادة ضبط isSyncing فقط - لا نمسح globalSelectedSubjects هنا
    // إصلاح #2: globalSelectedSubjects تُمسح فقط عند النجاح الكامل، ليس هنا
    isSyncing = false;
    window.hasSuccessfulDownloads = false;
    window.hasFailedDownloads = false;

    // إعادة ضبط الزر
    try {
        let syncBtn = document.getElementById('sync-btn');
        if(syncBtn) {
            syncBtn.classList.remove('loading');
            syncBtn.style.animation = "none";
            syncBtn.style.pointerEvents = "auto";
            syncBtn.style.opacity = "1";

            if (hadFailure) {
                syncBtn.innerHTML = "استئناف التحديث";
                syncBtn.style.backgroundColor = "#FF9500";
            } else {
                syncBtn.innerHTML = "بدء التحديث";
                syncBtn.style.backgroundColor = "";
            }

            // ضمان إضافي بعد 100ms
            setTimeout(() => {
                syncBtn.classList.remove('loading');
                syncBtn.style.animation = "none";
                syncBtn.style.pointerEvents = "auto";
                syncBtn.style.opacity = "1";
                if (hadFailure) {
                    syncBtn.innerHTML = "استئناف التحديث";
                    syncBtn.style.backgroundColor = "#FF9500";
                } else {
                    syncBtn.innerHTML = "بدء التحديث";
                    syncBtn.style.backgroundColor = "";
                }
            }, 100);
        }
    } catch(e) { console.error("Error resetting btn:", e); }

    // عرض رسائل النجاح/الفشل إذا كان هناك تحديث فعلي
    if (wasActuallySyncing) {
        if (hadSuccess && !hadFailure) {
            try { playSuccessSound(); } catch(e){}
            // إظهار نافذة النجاح مع الأنيميشن والصوت
            showSuccessModal();
            // إصلاح #2: مسح globalSelectedSubjects فقط عند النجاح الكامل
            globalSelectedSubjects.clear();
            // إصلاح #4: تحديث الواجهة فوراً لتعكس حالة القلم الحقيقية
            try { checkDownloadedStages(); } catch(e) {}
            try { loadPenContents(); } catch(e) {}
            // إصلاح #4: إذا كانت مرحلة مفتوحة، أعد عرضها لتحديث حالة التحديد فيها
            if (currentStage && document.getElementById('view-stage-details') &&
                document.getElementById('view-stage-details').classList.contains('active')) {
                try { openStage(currentStage); } catch(e) {}
            }
        } else if (hadSuccess && hadFailure) {
            try { playSuccessSound(); } catch(e){}
            try { showAlert("تحديث غير مكتمل", "تم تحديث بعض الملازم بنجاح، ولكن فشل تحديث البعض الآخر."); } catch(e){}
            // لا نمسح التحديد هنا: يترك المستخدم يعيد المحاولة بالملفات الفاشلة
            try { checkDownloadedStages(); } catch(e) {}
            try { loadPenContents(); } catch(e) {}
            if (currentStage && document.getElementById('view-stage-details') &&
                document.getElementById('view-stage-details').classList.contains('active')) {
                try { openStage(currentStage); } catch(e) {}
            }
        } else {
            // فشل كلي أو إلغاء - لا نمسح التحديد حتى يتمكن من المحاولة مجدداً
        }
    }

    try { toggleDashboard(false); } catch(e) {}
    try { eel.set_syncing_false()(); } catch(e) {}

    return { hadSuccess, hadFailure };
}

function toggleDashboard(isSyncingNow) {
    let dlView = document.getElementById('global-dl-view');

    if (isSyncingNow) {
        if(dlView) {
            dlView.style.opacity = '1';
            dlView.style.pointerEvents = 'auto';
        }
    } else {
        if(dlView) {
            dlView.style.opacity = '0';
            dlView.style.pointerEvents = 'none';
        }
    }
}

// ===== Eel Exposed Functions (Called from Python) =====

eel.expose(update_pen_status);
function update_pen_status(isConnected, driveLetter) {
    if(isConnected) {
        if(currentPenDrive === driveLetter) return;
        currentPenDrive = driveLetter;
        document.getElementById('pen-text').innerText = "القلم متصل";
        document.getElementById('pen-text').style.color = "#1DB954";
        document.getElementById('pen-text').style.animation = "pulseGreenText 2s infinite";
        document.getElementById('pen-status').style.background = "rgba(29, 185, 84, 0.1)";
        document.getElementById('pen-status').style.border = "1px solid rgba(29, 185, 84, 0.3)";

        eel.get_pen_space(currentPenDrive)(function(res) {
            if (res && res.total_gb > 0) {
                document.getElementById('pen-space-container').style.display = 'flex';
                document.getElementById('pen-space-text').innerText = res.used_gb + " / " + res.total_gb + " GB";

                let pct = Math.round((res.used_gb / res.total_gb) * 100);
                document.getElementById('pen-space-pct').innerText = pct + "%";
                document.getElementById('pen-space-circle').setAttribute('stroke-dasharray', pct + ', 100');

                let circleColor = "#1DB954";
                if (pct > 90) circleColor = "#FF3B30";
                else if (pct > 70) circleColor = "#FF9500";
                document.getElementById('pen-space-circle').setAttribute('stroke', circleColor);
            }
        });

        if (Object.keys(globalStagesData).length > 0) {
            checkDownloadedStages().then(() => {
                renderStagesGrid();
            });
        }
        if (document.getElementById('view-pen').classList.contains('active')) {
            loadPenContents();
        }
    } else {
        if(currentPenDrive === null) return;
        currentPenDrive = null;
        let penTextEl = document.getElementById('pen-text');
        if (penTextEl) {
            penTextEl.innerText = "القلم غير متصل";
            penTextEl.style.color = "#FF3B30";
            penTextEl.style.animation = "pulseRedText 2s infinite";
        }
        let penStatusEl = document.getElementById('pen-status');
        if (penStatusEl) {
            penStatusEl.style.background = "rgba(0,0,0,0.5)";
            penStatusEl.style.border = "1px solid transparent";
        }

        let penSpaceEl = document.getElementById('pen-space-container');
        if (penSpaceEl) penSpaceEl.style.display = 'none';

        let penGridEl = document.getElementById('pen-grid');
        if (penGridEl) penGridEl.innerHTML = '<p style="color:var(--text-subdued);">يرجى إدخال القلم أولاً.</p>';

        downloadedFilesCache = {};
        stageStatus = {};
        globalSelectedSubjects.clear();

        if (Object.keys(globalStagesData).length > 0) {
            renderStagesGrid();
        }

        // إصلاح: التحقق من التبويب النشط عبر DOM
        if (document.getElementById('view-stage-details') && document.getElementById('view-stage-details').classList.contains('active') && currentStage) {
            openStage(currentStage);
        }
    }
}

eel.expose(update_progress);
function update_progress(act, percent, text, speed) {
    let fill  = document.getElementById(`dl-progress-fill-${act}`);
    let title = document.getElementById(`dl-title-${act}`);
    let pct   = document.getElementById(`dl-percentage-${act}`);
    let spd   = document.getElementById(`dl-speed-${act}`);

    if(!fill) return;

    fill.style.width = percent + "%";
    title.innerText = text;
    pct.innerText = percent + "%";
    if (speed) spd.innerText = speed;
}

eel.expose(start_usb_sync);
function start_usb_sync(act) {
    let fill = document.getElementById(`dl-progress-fill-${act}`);
    let title = document.getElementById(`dl-title-${act}`);
    if (fill) {
        fill.classList.add('usb-syncing');
    }
    if (title) {
        title.innerText = "جاري المزامنة مع القلم...";
    }
}

eel.expose(item_finished);
function item_finished(act, success, message) {
    let fill     = document.getElementById(`dl-progress-fill-${act}`);
    let title    = document.getElementById(`dl-title-${act}`);
    let pct      = document.getElementById(`dl-percentage-${act}`);
    let spd      = document.getElementById(`dl-speed-${act}`);
    let controls = document.getElementById(`dl-controls-${act}`);

    if(!fill) return;

    if(controls) controls.style.display = 'none';

    if(success) {
        window.hasSuccessfulDownloads = true;
        title.innerText = "اكتمل التحديث بنجاح!";
        fill.style.width = "100%";
        pct.innerText = "100%";
        spd.innerText = "مكتمل";
        setTimeout(() => {
            let itemDiv = document.getElementById(`dl-item-${act}`);
            if (itemDiv) itemDiv.remove();
            checkAllDownloadsFinished();
            if (document.getElementById('view-pen') && document.getElementById('view-pen').classList.contains('active')) {
                loadPenContents();
            }
        }, 3000);
    } else {
        if (message !== "cancelled") window.hasFailedDownloads = true;
        title.innerText = message === "cancelled" ? "تم الإلغاء" : ("فشل: " + message);
        fill.style.backgroundColor = "#FF3B30";
        spd.innerText = "فشل";
        
        // لا نحذف العنصر إذا فشل التنزيل حتى يتمكن المستخدم من رؤيته أو استئنافه
        if (message === "cancelled") {
            setTimeout(() => {
                let itemDiv = document.getElementById(`dl-item-${act}`);
                if (itemDiv) itemDiv.remove();
                checkAllDownloadsFinished();
            }, 2000);
        } else {
            // نتحقق من انتهاء جميع التنزيلات دون حذف العنصر
            checkAllDownloadsFinished();
        }
    }
}

eel.expose(sync_finished);
function sync_finished(success, message) {
    // احتياطي - المنطق الرئيسي في sync_batch_complete
}

eel.expose(update_global_progress);
function update_global_progress(pct, sizes_str, speed_str, eta_str, history) {
    document.getElementById('g-dl-pct').innerText = pct + '%';
    document.getElementById('g-dl-sizes').innerText = sizes_str;
    document.getElementById('g-dl-speed').innerText = speed_str;
    document.getElementById('g-dl-eta').innerText = eta_str;
    document.getElementById('g-dl-progress-fill').style.width = pct + '%';
}

// ===== Load Data =====
async function loadRealData() {
    let stagesGrid = document.getElementById('stages-grid');
    stagesGrid.innerHTML = '<p style="color:var(--text-subdued); font-size:16px;">جاري جلب المراحل من السيرفر...</p>';

    await eel.check_pen()();

    let res = await eel.fetch_stages()();
    if(res && res.stages_data && Object.keys(res.stages_data).length > 0) {
        globalStagesData = res.stages_data;
        res_display_order = res.display_order;
        renderStagesGrid();
        checkDownloadedStages();
    }
}

eel.expose(silently_update_stages);
async function silently_update_stages(res) {
    if(res && res.stages_data && Object.keys(res.stages_data).length > 0) {
        globalStagesData = res.stages_data;
        res_display_order = res.display_order;
        await checkDownloadedStages();
        await renderStagesGrid();

        if (currentStage && document.getElementById('view-stage-details') && document.getElementById('view-stage-details').classList.contains('active')) {
            openStage(currentStage);
        }

        console.log("تم تحديث المراحل بصمت من السيرفر.");
    }
}

let stageStatus = {};
let downloadedFilesCache = {};

async function checkDownloadedStages() {
    stageStatus = {};
    if(currentPenDrive) {
        let acts = await eel.get_downloaded_acts(currentPenDrive)();
        downloadedFilesCache = {};
        if (Array.isArray(acts)) {
            for (let f of acts) {
                if (f.act) {
                    downloadedFilesCache[f.act.trim().toLowerCase()] = {
                        size_bytes: f.size_bytes,
                        is_tmp: f.is_tmp || false
                    };
                }
            }
        }

        for(let stage in globalStagesData) {
            let subjects = globalStagesData[stage];
            let total = subjects.length;
            let downloaded = 0;
            let corrupted = 0;
            let missingList = [];
            let corruptedList = [];

            for(let subj of subjects) {
                if(subj.act) {
                    let actLower = subj.act.trim().toLowerCase();
                    if (downloadedFilesCache[actLower] !== undefined) {
                        let fileData = downloadedFilesCache[actLower];
                        let actualSize = fileData.size_bytes;
                        let isTmp = fileData.is_tmp;
                        let expectedSize = subj.size_bytes || 0;
                        // السماح بفارق 5% لتجنب اعتبار الملفات المكتملة تالفة بسبب تحديث السيرفر بدون تحديث sizes.json
                        if (isTmp || (expectedSize > 0 && actualSize < (expectedSize * 0.95))) {
                            corrupted++;
                            subj.is_corrupted = true;
                            corruptedList.push(subj.subject);
                            // إصلاح: إزالة التحديد التلقائي للملفات التالفة من هنا
                            // التحديد يحدث فقط عند فتح المرحلة يدوياً في openStage
                        } else {
                            subj.is_corrupted = false;
                        }
                        downloaded++;
                    } else {
                        subj.is_corrupted = false;
                        missingList.push(subj.subject);
                    }
                }
            }

            let status = 'none';
            if (corrupted > 0) status = 'corrupted';
            else if (total > 0 && downloaded === total) status = 'complete';
            else if (downloaded > 0) status = 'partial';

            stageStatus[stage] = {
                downloaded: downloaded,
                total: total,
                corrupted: corrupted,
                status: status,
                missingList: missingList,
                corruptedList: corruptedList
            };
        }
    }

    if (Object.keys(globalStagesData).length > 0) {
        renderStagesGrid();
    }
}

let isRenderingStages = false;
let pendingRender = false;

async function renderStagesGrid() {
    if (isRenderingStages) {
        pendingRender = true;
        return;
    }
    isRenderingStages = true;

    try {
        let newHtml = '';
        res_display_order.forEach(stage => {
            if(globalStagesData[stage]) {
                let safeName = stage.split('\\').join('-').split('/').join('-').split(':').join('-').trim();
                let glowStyle = '';
                let subtitle = '';

                let st = stageStatus[stage];
                let totalSubjects = globalStagesData[stage].length;

                if (st && st.status === 'corrupted') {
                    glowStyle = 'box-shadow: 0 0 15px rgba(255, 59, 48, 0.4); border: 1px solid rgba(255, 59, 48, 0.6);';
                    subtitle = `<p style="font-size: 13px; color: #FF3B30; text-align: center; font-weight: 700; margin: 0;">مكتملة ${st.total - st.corrupted} - تالفة ${st.corrupted}</p>`;
                } else if (st && st.status === 'complete') {
                    glowStyle = 'box-shadow: 0 0 15px rgba(29, 185, 84, 0.4); border: 1px solid rgba(29, 185, 84, 0.6);';
                    subtitle = `<p style="font-size: 13px; color: #1DB954; text-align: center; font-weight: 700; margin: 0;">مكتملة ${st.total}</p>`;
                } else if (st && st.status === 'partial') {
                    glowStyle = 'box-shadow: 0 0 15px rgba(255, 149, 0, 0.4); border: 1px solid rgba(255, 149, 0, 0.6);';
                    let missing = st.total - st.downloaded;
                    subtitle = `<p style="font-size: 13px; color: #FF9500; text-align: center; font-weight: 700; margin: 0;">مكتملة ${st.downloaded} - نقص ${missing}</p>`;
                } else {
                    subtitle = `<p style="font-size: 13px; color: var(--text-subdued); text-align: center; font-weight: 700; margin: 0;">نقص ${totalSubjects}</p>`;
                }

                newHtml += `
                    <div class="card" onclick="handleStageClick('${stage}')" style="${glowStyle} position: relative;">
                        <div class="img-container">
                            <img src="assets/covers/${safeName}.png" onerror="this.src='https://ui-avatars.com/api/?name=${safeName}&background=282828&color=1DB954'">
                        </div>
                        <h3 style="font-size: 18px; font-weight: 800; text-align: center; margin-bottom: 4px;">${stage}</h3>
                        ${subtitle}
                    </div>
                `;
            }
        });

        let stagesGrid = document.getElementById('stages-grid');
        if (stagesGrid.innerHTML !== newHtml) {
            stagesGrid.innerHTML = newHtml;
            let grid = document.getElementById('stages-grid');
            grid.addEventListener('wheel', (evt) => {
                evt.preventDefault();
                grid.scrollLeft += evt.deltaY;
            });
        }
    } finally {
        isRenderingStages = false;
        if (pendingRender) {
            pendingRender = false;
            renderStagesGrid();
        }
    }
}

let stageClickTimers = {};
function handleStageClick(stageName) {
    openStage(stageName);
}


function openStage(stageName) {
    // إصلاح: لا نمسح التحديدات عند فتح مرحلة جديدة
    // يبقى تحديد المراحل الأخرى سليماً حتى يتمكن المستخدم من اختيار مواد من مراحل متعددة
    currentStage = stageName;
    stageDetailsTitle.innerText = `${stageName}`;
    switchTab('stage-details');

    let subjects = globalStagesData[stageName];
    subjectsGrid.innerHTML = '';

    if(!subjects) return;

    // بناء HTML كسلسلة واحدة لتحسين الأداء
    let html = '';

    subjects.forEach((subj, index) => {
        let safeName = subj.subject.split('\\').join('-').split('/').join('-').split(':').join('-').trim();

        // التحديد التلقائي: يحدد الملازم الموجودة في القلم فقط إذا لم تكن محددة مسبقاً
        // لا نعيد تحديدها إذا كانت محددة (يحافظ على حالة التحديد اليدوي)
        let actLower = subj.act.trim().toLowerCase();
        let isDownloaded = typeof downloadedFilesCache !== 'undefined' && downloadedFilesCache[actLower] !== undefined;
        let isCorrupted = subj.is_corrupted;
        
        let isLocked = isDownloaded && !isCorrupted;

        // نضيف للتحديد التلقائي إذا كانت موجودة في القلم ومكتملة
        if (isDownloaded && !globalSelectedSubjects.has(subj.act)) {
            globalSelectedSubjects.set(subj.act, {act: subj.act, subject: subj.subject, size_bytes: subj.size_bytes || 0});
        }

        let isSelected = globalSelectedSubjects.has(subj.act);
        let checkedAttr = isSelected ? 'checked' : '';
        let disabledAttr = isLocked ? 'disabled' : '';
        let cursorStyle = isLocked ? 'cursor:default; opacity: 0.8;' : 'cursor:pointer;';
        let itemClass = isSelected ? 'subject-item checked' : 'subject-item';

        let corruptedBadge = isCorrupted
            ? `<span style="background: rgba(255, 149, 0, 0.15); color: #FF9500; border: 1px solid rgba(255, 149, 0, 0.3); padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 800; margin-right: 8px; animation: pulseGlow 2s infinite;">تحديث متاح ✨</span>`
            : '';

        let badgeHtml = isDownloaded ? `<span style="background: rgba(29, 185, 84, 0.15); color: #1DB954; border: 1px solid rgba(29, 185, 84, 0.3); padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 800; margin-right: 8px;">متوفرة بالقلم ✔</span>` : '';

        html += `
            <div class="${itemClass}" style="display:flex; align-items:center; justify-content:space-between; width:100%; ${cursorStyle} padding: 12px 16px; border-radius: 16px; background: var(--bg-elevated); border: 1px solid rgba(255,255,255,0.05); margin-bottom: 12px;" id="subj-${index}" onclick="toggleSubject('${subj.act}', 'cb-${index}', '${subj.subject.replace(/'/g, "\\'")}', ${subj.size_bytes || 0})">
                <div style="display:flex; align-items:center; flex:1;">
                    <img class="subject-img" src="assets/subjects/${safeName}.png" onerror="this.src='https://ui-avatars.com/api/?name=ملزمة&background=282828&color=1DB954'" style="width: 64px; height: 64px; border-radius: 12px; object-fit: cover;">
                    <div class="subject-info" style="display:flex; flex-direction:column; justify-content:center; margin-right: 16px;">
                        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px;">
                            <div class="subject-title" style="margin-bottom: 0;">${subj.subject.replace(/\s*\/\s*/g, ' - ')} ${corruptedBadge}</div>
                            <div style="font-size:12px; color:var(--text-subdued); font-weight:800; background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 6px;">${subj.size_mb ? subj.size_mb.toFixed(1) : '0.0'} MB</div>
                            ${badgeHtml}
                        </div>
                        <div style="font-size:13px; color:var(--text-subdued); font-weight:700;">${stageName}</div>
                    </div>
                </div>
                <div style="margin-left: 16px;">
                    <input type="checkbox" class="checkbox-custom" id="cb-${index}" ${checkedAttr} ${disabledAttr} data-act="${subj.act}" data-subject="${subj.subject.replace(/'/g, "\\'")}" data-size="${subj.size_bytes || 0}" onclick="event.stopPropagation();" onchange="onSubjectCheckboxChange(this);">
                </div>
            </div>
        `;
    });

    // حقن HTML مرة واحدة
    subjectsGrid.innerHTML = html;
}

function toggleSubject(act, cbId, subjName, sizeB = 0) {
    if (isSyncing) {
        showToast("يرجى الانتظار حتى يكتمل التحديث ⏳", "error");
        return;
    }

    let cb = document.getElementById(cbId);
    if (!cb) return;
    
    if (cb.disabled) {
        showToast("هذه المادة متوفرة مسبقاً ومكتملة في القلم ✔", "info");
        return;
    }

    let itemDiv = document.getElementById(cbId.replace('cb-', 'subj-'));
    
    // Toggle the checkbox visually
    cb.checked = !cb.checked;

    if (cb.checked) {
        globalSelectedSubjects.set(act, {act: act, subject: subjName, size_bytes: sizeB});
        if(itemDiv) itemDiv.classList.add('checked');
    } else {
        globalSelectedSubjects.delete(act);
        if(itemDiv) itemDiv.classList.remove('checked');
    }
}

function onSubjectCheckboxChange(cb) {
    if (cb.disabled) {
        cb.checked = true; // Force it to remain checked
        showToast("هذه المادة متوفرة مسبقاً ومكتملة في القلم ✔", "info");
        return;
    }
    
    if (isSyncing) {
        cb.checked = !cb.checked;
        showToast("يرجى الانتظار حتى يكتمل التحديث ⏳", "error");
        return;
    }

    let act = cb.getAttribute('data-act');
    let subjName = cb.getAttribute('data-subject');
    let sizeB = parseInt(cb.getAttribute('data-size') || "0");
    let itemDiv = document.getElementById(cb.id.replace('cb-', 'subj-'));

    if (cb.checked) {
        globalSelectedSubjects.set(act, {act: act, subject: subjName, size_bytes: sizeB});
        if(itemDiv) itemDiv.classList.add('checked');
    } else {
        globalSelectedSubjects.delete(act);
        if(itemDiv) itemDiv.classList.remove('checked');
    }
}

let isAllSelected = false;
function toggleSelectAll() {
    if (isSyncing) {
        showToast("يرجى الانتظار حتى يكتمل التحديث ⏳", "error");
        return;
    }

    isAllSelected = !isAllSelected;
    let checkboxes = document.querySelectorAll('#subjects-grid .checkbox-custom');
    let selectBtn = document.querySelector('.select-all-btn');

    checkboxes.forEach(cb => {
        if (cb.disabled) return; // لا نلغي تحديد المواد المقفلة المكتملة
        
        cb.checked = isAllSelected;
        let item = cb.closest('.subject-item');
        let act = cb.getAttribute('data-act');
        let subj = cb.getAttribute('data-subject');
        let sizeB = parseInt(cb.getAttribute('data-size') || "0");

        if(isAllSelected) {
            item.classList.add('checked');
            globalSelectedSubjects.set(act, {act: act, subject: subj, size_bytes: sizeB});
        } else {
            item.classList.remove('checked');
            globalSelectedSubjects.delete(act);
        }
    });

    if(isAllSelected) {
        selectBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg> إلغاء التحديد';
        selectBtn.style.color = "var(--text-base)";
        selectBtn.style.borderColor = "var(--text-base)";
    } else {
        selectBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg> تحديد الكل';
        selectBtn.style.color = "var(--text-subdued)";
        selectBtn.style.borderColor = "var(--text-subdued)";
    }
}

// ===== Pen Contents =====
async function loadPenContents() {
    let penGrid = document.getElementById('pen-grid');
    if(!currentPenDrive) {
        penGrid.innerHTML = '<p style="color:#FF3B30; font-size:16px;">يرجى توصيل القلم لعرض محتوياته.</p>';
        return;
    }

    penGrid.innerHTML = '<p style="color:var(--text-subdued); font-size:16px;">جاري القراءة...</p>';

    let files = await eel.get_pen_contents(currentPenDrive)();

    penGrid.innerHTML = '';

    if(files.length === 0) {
        penGrid.innerHTML = '<p style="color:var(--text-subdued); font-size:16px;">القلم فارغ. لا توجد ملازم.</p>';
        return;
    }

    let groupedFiles = {};
    let unknownStageFiles = [];

    files.forEach(f => {
        let foundStage = null;
        for(let stage in globalStagesData) {
            if(globalStagesData[stage].find(s => s.act === f.act)) {
                foundStage = stage;
                break;
            }
        }

        if (foundStage) {
            if (!groupedFiles[foundStage]) groupedFiles[foundStage] = [];
            groupedFiles[foundStage].push(f);
        } else {
            unknownStageFiles.push(f);
        }
    });

    let html = '';

    function renderGroup(stageName, stageFiles) {
        if(stageFiles.length === 0) return '';
        let groupHtml = `<div style="margin-bottom: 32px; width: 100%;" id="pen-stage-${stageName.replace(/\s+/g, '-')}">`;

        // Stage Header
        groupHtml += `
            <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 12px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <div style="width: 4px; height: 24px; background: var(--brand-color); border-radius: 4px;"></div>
                    <h3 style="color: var(--text-base); font-size: 20px; font-weight: 800; margin: 0;">${stageName}</h3>
                    <span style="background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 700; color: var(--text-subdued);">${stageFiles.length} ملازم</span>
                </div>
                <button class="nav-btn" style="background: rgba(255, 59, 48, 0.1); color: #FF3B30; border: 1px solid rgba(255, 59, 48, 0.3); padding: 6px 16px; border-radius: 12px; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s;" onclick="deleteStageFromPen('${stageName}')" onmouseover="this.style.background='rgba(255, 59, 48, 0.2)'" onmouseout="this.style.background='rgba(255, 59, 48, 0.1)'">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-left: 6px;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg> حذف المرحلة
                </button>
            </div>
        `;

        // Subjects Grid
        groupHtml += `<div class="grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">`;

        stageFiles.forEach((f, index) => {
            let safeName = f.subject.split('\\').join('-').split('/').join('-').split(':').join('-').trim();
            let actStr = f.act ? f.act.replace(/'/g, "\\'") : '';

            let displaySize = f.size_mb;
            if (displaySize === 0) {
                for(let stg in globalStagesData) {
                    let s = globalStagesData[stg].find(x => x.act === f.act);
                    if (s && s.size_mb) { displaySize = s.size_mb; break; }
                }
            }

            groupHtml += `
                <div class="subject-item" style="position:relative; overflow:hidden; padding: 12px 16px; border-radius: 16px; background: var(--bg-elevated); border: 1px solid rgba(255,255,255,0.05); display: flex; align-items: center; gap: 16px; transition: all 0.2s;" id="pen-item-${f.act}">
                    <img class="subject-img" src="assets/subjects/${safeName}.png" onerror="this.src='https://ui-avatars.com/api/?name=ملزمة&background=282828&color=1DB954'" style="width: 56px; height: 56px; border-radius: 10px; object-fit: cover;">
                    <div class="subject-info" style="flex: 1;">
                        <div class="subject-title" style="white-space: normal; line-height: 1.4; font-size: 14px; font-weight: 700; color: var(--text-base); margin-bottom: 6px;">${f.subject.replace(/\s*\/\s*/g, ' - ')}</div>
                        <div style="font-size:12px; color:var(--text-subdued); font-weight:800; background: rgba(255,255,255,0.05); display: inline-block; padding: 2px 8px; border-radius: 6px;">${displaySize.toFixed(1)} MB</div>
                    </div>
                    
                    <!-- Delete Button embedded in card -->
                    <button class="nav-btn" style="background: rgba(255, 59, 48, 0.05); color: #FF3B30; border: none; padding: 10px; border-radius: 50%; cursor: pointer; transition: all 0.2s; flex-shrink: 0;" onclick="deleteFromPen('${actStr}', '${f.subject.replace(/'/g, "\\'")}')" onmouseover="this.style.background='rgba(255, 59, 48, 0.15)'" onmouseout="this.style.background='rgba(255, 59, 48, 0.05)'" title="حذف الملزمة">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            `;
        });

        groupHtml += `</div></div>`;
        return groupHtml;
    }

    if (typeof res_display_order !== 'undefined') {
        res_display_order.forEach(stage => {
            if (groupedFiles[stage]) {
                html += renderGroup(stage, groupedFiles[stage]);
            }
        });
    } else {
        for(let stage in groupedFiles) {
            html += renderGroup(stage, groupedFiles[stage]);
        }
    }

    html += renderGroup("ملازم أخرى", unknownStageFiles);

    penGrid.innerHTML = html;
}

// ===== Alert / Confirm =====
function showAlert(title, message) {
    try { playErrorSound(); } catch(e) {}
    document.getElementById('alert-title').innerText = title;
    document.getElementById('alert-msg').innerText = message;
    document.getElementById('alert-modal').style.display = 'flex';
}

function closeAlertModal() {
    document.getElementById('alert-modal').style.display = 'none';
}

// ===== Storage Details Modal =====
async function showStorageModal() {
    if(!currentPenDrive) return;
    
    let res = await eel.get_pen_space(currentPenDrive)();
    if (res && res.total_gb > 0) {
        let pct = Math.round((res.used_gb / res.total_gb) * 100);
        document.getElementById('modal-storage-pct').innerText = pct + "%";
        
        let circleColor = "#1DB954";
        if (pct > 90) circleColor = "#FF3B30";
        else if (pct > 70) circleColor = "#FF9500";
        
        document.getElementById('modal-storage-circle').setAttribute('stroke', circleColor);
        // Reset animation
        document.getElementById('modal-storage-circle').setAttribute('stroke-dasharray', '0, 100');
        
        let free_gb = (res.total_gb - res.used_gb).toFixed(1);

        document.getElementById('modal-storage-total').innerText = res.total_gb + " GB";
        document.getElementById('modal-storage-free').innerText = free_gb + " GB";
        
        let freeColor = free_gb < 1.0 ? "#FF3B30" : "#1DB954";
        document.getElementById('modal-storage-free').style.color = freeColor;
        
        document.getElementById('storage-modal').style.display = 'flex';
        
        // Trigger animation shortly after opening
        setTimeout(() => {
            document.getElementById('modal-storage-circle').setAttribute('stroke-dasharray', pct + ', 100');
        }, 50);
    }
}

function closeStorageModal() {
    document.getElementById('storage-modal').style.display = 'none';
}

function showSuccessModal() {
    document.getElementById('success-modal').style.display = 'flex';
    closeDownloadsDropdown();
}

function closeSuccessModal() {
    document.getElementById('success-modal').style.display = 'none';
    closeDownloadsDropdown();
}

function showConfirm(title, message, yesCallback) {
    document.getElementById('confirm-title').innerText = title;
    document.getElementById('confirm-msg').innerText = message;
    let yesBtn = document.getElementById('confirm-yes-btn');
    yesBtn.onclick = function() {
        document.getElementById('confirm-modal').style.display = 'none';
        yesCallback();
    };
    document.getElementById('confirm-modal').style.display = 'flex';
}

// Toast بسيط للإشعارات السريعة
function showToast(message, type = 'info') {
    let existing = document.getElementById('app-toast');
    if(existing) existing.remove();

    let toast = document.createElement('div');
    toast.id = 'app-toast';
    
    let posCss = `bottom: 130px; left: 50%; transform: translateX(-50%);`;
    if (window.lastMouseX && window.lastMouseY) {
        let y = Math.max(20, window.lastMouseY - 60);
        posCss = `top: ${y}px; left: ${window.lastMouseX}px; transform: translateX(-50%);`;
        window.lastMouseX = null;
        window.lastMouseY = null;
    }

    toast.style.cssText = `
        position: fixed; ${posCss}
        background: var(--bg-elevated);
        color: var(--text-base); padding: 12px 24px; border-radius: 12px;
        font-size: 14px; font-weight: 700; z-index: 99999;
        border: 1px solid rgba(255,255,255,0.05);
        border-bottom: 3px solid ${type === 'error' ? '#FF3B30' : '#1DB954'};
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        animation: fadeIn 0.3s ease;
        display: flex; align-items: center; gap: 12px;
    `;
    let icon = type === 'error' ? '⚠️' : '✅';
    toast.innerHTML = `<span style="font-size:18px;">${icon}</span> <span>${message}</span>`;
    
    document.body.appendChild(toast);
    setTimeout(() => { if(toast) toast.remove(); }, 3500);
}

// ===== Delete from Pen =====
function deleteFromPen(act, subjectName) {
    showConfirm("تأكيد الحذف", `هل أنت متأكد من حذف (${subjectName}) من القلم لتفريغ المساحة؟`, async function() {
        let itemEl = document.getElementById(`pen-item-${act}`);
        if(itemEl) {
            itemEl.style.transition = "all 0.5s ease";
            itemEl.style.transform = "translateX(100%)";
            itemEl.style.opacity = "0";
        }
        let success = await eel.delete_pen_file(currentPenDrive, act)();

        if(success) {
            globalSelectedSubjects.delete(act);
            setTimeout(() => {
                if(itemEl) {
                    let parentGrid = itemEl.closest('.grid');
                    let stageGroup = itemEl.closest('[id^="pen-stage-"]');
                    itemEl.remove();
                    if(parentGrid && parentGrid.children.length === 0 && stageGroup) {
                        stageGroup.style.transition = "all 0.5s ease";
                        stageGroup.style.opacity = "0";
                        setTimeout(() => stageGroup.remove(), 500);
                    }
                }
                eel.get_pen_space(currentPenDrive)(function(res) {
                    if (res && res.total_gb > 0) {
                        let pct = Math.round((res.used_gb / res.total_gb) * 100);
                        document.getElementById('pen-space-text').innerText = res.used_gb + " / " + res.total_gb + " GB";
                        document.getElementById('pen-space-pct').innerText = pct + "%";
                        document.getElementById('pen-space-circle').setAttribute('stroke-dasharray', pct + ', 100');
                        let circleColor = "#1DB954";
                        if (pct > 90) circleColor = "#FF3B30";
                        else if (pct > 70) circleColor = "#FF9500";
                        document.getElementById('pen-space-circle').setAttribute('stroke', circleColor);
                    }
                });
                checkDownloadedStages();
            }, 500);
        } else {
            showAlert("خطأ", "حدث خطأ أثناء محاولة حذف الملف.");
            if(itemEl) {
                itemEl.style.transform = "translateX(0)";
                itemEl.style.opacity = "1";
            }
        }
    });
}

// ===== Delete Stage from Pen =====
function deleteStageFromPen(stageName) {
    showConfirm("تحذير: حذف مرحلة", `هل أنت متأكد من حذف جميع ملازم مرحلة (${stageName}) من القلم؟ لا يمكن التراجع عن هذه العملية!`, async function() {
        let stageFiles = [];
        if (globalStagesData[stageName]) {
            stageFiles = globalStagesData[stageName];
        }

        let stageDiv = document.getElementById(`pen-stage-${stageName.replace(/\s+/g, '-')}`);

        // انيميشن ناعم مطابق لحذف الملف الفردي
        if(stageDiv) {
            stageDiv.style.transition = "all 0.5s ease";
            stageDiv.style.transform = "translateX(100%)";
            stageDiv.style.opacity = "0";
            stageDiv.style.overflow = "hidden";
        }

        if (stageFiles.length === 0 && stageName === "ملازم أخرى") {
            let allFiles = await eel.get_pen_contents(currentPenDrive)();
            allFiles.forEach(f => {
                let found = false;
                for(let stg in globalStagesData) {
                    if(globalStagesData[stg].find(s => s.act === f.act)) found = true;
                }
                if(!found) stageFiles.push(f);
            });
        }

        for (let f of stageFiles) {
            if(f.act) {
                await eel.delete_pen_file(currentPenDrive, f.act)();
                globalSelectedSubjects.delete(f.act);
            }
        }

        setTimeout(() => {
            if(stageDiv) stageDiv.remove();
            eel.get_pen_space(currentPenDrive)(function(res) {
                if (res && res.total_gb > 0) {
                    let pct = Math.round((res.used_gb / res.total_gb) * 100);
                    document.getElementById('pen-space-text').innerText = res.used_gb + " / " + res.total_gb + " GB";
                    document.getElementById('pen-space-pct').innerText = pct + "%";
                    document.getElementById('pen-space-circle').setAttribute('stroke-dasharray', pct + ', 100');
                    let circleColor = "#1DB954";
                    if (pct > 90) circleColor = "#FF3B30";
                    else if (pct > 70) circleColor = "#FF9500";
                    document.getElementById('pen-space-circle').setAttribute('stroke', circleColor);
                }
            });
            checkDownloadedStages();
        }, 500);
    });
}

// ===== Exit / Minimize =====
function closeApp() {
    window.close();
    setTimeout(() => {
        eel.close_app()();
    }, 500);
}

function minimizeApp() {
    try {
        eel.minimize_app()();
    } catch(e) {
        console.warn("minimize_app not available:", e);
    }
}

// ===== Success Sound =====
function playSuccessSound() {
    try {
        let ctx = new (window.AudioContext || window.webkitAudioContext)();
        let osc = ctx.createOscillator();
        let gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, ctx.currentTime);
        osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.1);
        osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.2);
        osc.frequency.setValueAtTime(1046.50, ctx.currentTime + 0.3);

        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.05);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.5);

        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.5);
    } catch(e) {}
}

// ===== Error Sound =====
function playErrorSound() {
    try {
        let ctx = new (window.AudioContext || window.webkitAudioContext)();
        let osc = ctx.createOscillator();
        let gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(300, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.3);

        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.2, ctx.currentTime + 0.05);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.3);

        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.3);
    } catch(e) {}
}

// ===== Wi-Fi Status Update =====
function updateWifiStatus() {
    let wifiBtn = document.getElementById('wifi-status');
    if (!wifiBtn) return;
    
    if (navigator.onLine) {
        wifiBtn.style.color = '#1DB954';
        wifiBtn.title = 'متصل بالإنترنت';
        wifiBtn.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"></path><path d="M1.42 9a16 16 0 0 1 21.16 0"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>';
    } else {
        wifiBtn.style.color = '#FF3B30';
        wifiBtn.title = 'لا يوجد اتصال بالإنترنت';
        wifiBtn.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"></line><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"></path><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"></path><path d="M10.71 5.05A16 16 0 0 1 22.58 9"></path><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>';
    }
}

window.addEventListener('online', updateWifiStatus);
window.addEventListener('offline', updateWifiStatus);

// ===== Start =====

eel.expose(update_app_progress);
function update_app_progress(percent) {
    let p = Math.floor(percent);
    let bar = document.getElementById('update-progress-bar');
    let text = document.getElementById('update-progress-text');
    if(bar) bar.style.width = p + '%';
    if(text) text.innerText = p + '%';
}

eel.expose(app_update_failed);
function app_update_failed() {
    let title = document.getElementById('update-title');
    let bar = document.getElementById('update-progress-bar');
    let text = document.getElementById('update-progress-text');
    if(title) { title.innerText = "فشل التحديث!"; title.style.color = "#FF3B30"; }
    if(bar) bar.style.background = "#FF3B30";
    if(text) text.innerText = "حدث خطأ أثناء تحميل التحديث. سيتم الاستمرار بالنسخة الحالية.";
    setTimeout(() => {
        document.getElementById('update-modal').style.display = 'none';
        updateWifiStatus();
        loadRealData();
    }, 5000);
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        eel.sync_images_background()();
        let updateData = await eel.check_app_update()();
        if (updateData && updateData.update_available) {
            document.getElementById('update-modal').style.display = 'flex';
            eel.apply_app_update(updateData.link)();
            return;
        }
    } catch(e) {}

    updateWifiStatus();
    loadRealData();

    // فحص القلم كل 3 ثوانٍ
    setInterval(() => {
        if (!isSyncing) {
            eel.check_pen()();
        }
    }, 3000);
});

// ===== Click Sound =====
function playClickSound() {
    try {
        let ctx = new (window.AudioContext || window.webkitAudioContext)();
        let osc = ctx.createOscillator();
        let gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.05);
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.08, ctx.currentTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.05);
    } catch(e) {}
}

document.addEventListener('mousedown', (e) => {
    if (e.target.closest('button') || e.target.closest('.card') || e.target.closest('.subject-item') || e.target.closest('.nav-btn') || e.target.closest('li')) {
        playClickSound();
    }
});
