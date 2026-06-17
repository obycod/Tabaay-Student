import os
import re

# Patch app.js
app_js_path = r"c:\Users\asus\OneDrive\Desktop\main\web\app.js"
with open(app_js_path, "r", encoding="utf-8") as f:
    app_js = f.read()

app_js_patch = """
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
"""

if "eel.sync_images_background()" not in app_js:
    app_js = app_js.replace('document.addEventListener("DOMContentLoaded", () => {', app_js_patch)
    with open(app_js_path, "w", encoding="utf-8") as f:
        f.write(app_js)
    print("app.js patched.")

# Patch index.html
index_html_path = r"c:\Users\asus\OneDrive\Desktop\main\web\index.html"
with open(index_html_path, "r", encoding="utf-8") as f:
    index_html = f.read()

update_modal_html = """
    <!-- Update Modal -->
    <div id="update-modal"
        style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.95); 
        z-index: 10000; align-items: center; justify-content: center; backdrop-filter: blur(10px);">
        <div style="background: var(--bg-elevated); padding: 40px; border-radius: 24px; border: 1px solid rgba(29,185,84,0.3); width: 100%; max-width: 500px; text-align: center;">
            <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="#1DB954" stroke-width="2" style="margin-bottom: 20px; animation: spin 2s linear infinite;">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 2a10 10 0 0 1 10 10"></path>
            </svg>
            <style>@keyframes spin { 100% { transform: rotate(360deg); } }</style>
            <h2 id="update-title" style="color: white; margin-bottom: 10px; font-family: 'Tajawal', sans-serif;">جاري تحديث النظام...</h2>
            <p style="color: var(--text-subdued); margin-bottom: 20px; font-family: 'Tajawal', sans-serif;">يوجد إصدار جديد، جاري التحميل يرجى عدم إغلاق البرنامج.</p>
            <div style="width: 100%; background: rgba(255,255,255,0.1); border-radius: 10px; height: 10px; overflow: hidden; margin-bottom: 10px;">
                <div id="update-progress-bar" style="width: 0%; height: 100%; background: #1DB954; transition: width 0.3s;"></div>
            </div>
            <p id="update-progress-text" style="color: #1DB954; font-weight: bold; font-family: 'Tajawal', sans-serif;">0%</p>
        </div>
    </div>
</body>
"""

if 'id="update-modal"' not in index_html:
    index_html = index_html.replace("</body>", update_modal_html)
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print("index.html patched.")
