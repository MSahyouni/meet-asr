(function () {
  "use strict";

  function qs(s) { return document.querySelector(s); }
  function qsa(s) { return document.querySelectorAll(s); }
  function getId(id) { return document.getElementById(id); }

  var UI_STATE_KEY = "meetasr_ui_state_v1";
  var uiSaveTimer = null;

  function setActiveTab(tabName) {
    if (!tabName) return;
    qsa(".tab[data-tab]").forEach(function (x) { x.classList.remove("active"); });
    qsa(".panel").forEach(function (p) { p.classList.remove("active"); });
    var tabBtn = qs('.tab[data-tab="' + tabName + '"]');
    if (tabBtn) tabBtn.classList.add("active");
    var panel = getId(tabName + "-panel");
    if (panel) panel.classList.add("active");
  }

  function setActiveSource(srcName) {
    if (!srcName) return;
    qsa(".src-btn").forEach(function (x) { x.classList.remove("active"); });
    var srcBtn = qs('.src-btn[data-src="' + srcName + '"]');
    if (srcBtn) srcBtn.classList.add("active");
    var fileZone = getId("file-zone"), micZone = getId("mic-zone");
    if (srcName === "file") {
      if (fileZone) fileZone.classList.remove("hidden");
      if (micZone) micZone.classList.add("hidden");
    } else {
      if (fileZone) fileZone.classList.add("hidden");
      if (micZone) micZone.classList.remove("hidden");
    }
  }

  function queueUIStateSave() {
    if (uiSaveTimer) clearTimeout(uiSaveTimer);
    uiSaveTimer = setTimeout(function () {
      uiSaveTimer = null;
      saveUIState();
    }, 50);
  }

  function saveUIState() {
    try {
      var state = {
        activeTab: (qs(".tab.active[data-tab]") && qs(".tab.active[data-tab]").dataset.tab) || "asr",
        activeSource: (qs(".src-btn.active") && qs(".src-btn.active").dataset.src) || "file",
        values: {},
        checks: {},
        texts: {},
        html: {},
        media: {},
      };

      [
        "apiKey", "timeout", "whisperMode", "enhance", "enhanceLevel", "maxSpeakers", "enrollThreshold",
        "deviceSel", "computeSel", "summaryMode", "ttsEngine", "ttsUserEmail", "ttsText", "ttsVoice",
        "ttsSpeed", "ttsSeed", "ttsVoiceFilesList", "spkName", "spkList", "spkFilesList",
        "authEmail", "authFullName", "profileFullName", "profileBio", "profileAvatar"
      ].forEach(function (id) {
        var el = getId(id);
        if (el) state.values[id] = el.value;
      });

      ["diarize", "autoK"].forEach(function (id) {
        var el = getId(id);
        if (el) state.checks[id] = !!el.checked;
      });

      [
        "micStatus", "outSegments", "enrollOut", "spkMicStatus", "ttsVoiceStatus", "ttsMeta", "authStatus",
        "profileStatus", "dashStatus", "dashSummary", "dashOverview", "ttsError"
      ].forEach(function (id) {
        var el = getId(id);
        if (el) state.texts[id] = el.textContent || "";
      });

      ["outText", "outSummary", "outKeywords"].forEach(function (id) {
        var el = getId(id);
        if (el) state.values[id] = (typeof el.value !== "undefined") ? el.value : (el.textContent || "");
      });

      ["dlLinks", "ttsDl"].forEach(function (id) {
        var el = getId(id);
        if (el) state.html[id] = el.innerHTML || "";
      });

      var ttsErrorEl = getId("ttsError");
      if (ttsErrorEl) state.ttsErrorHidden = ttsErrorEl.classList.contains("hidden");

      ["ttsAudio", "spkAudio", "ttsVoiceAudio"].forEach(function (id) {
        var el = getId(id);
        if (el && el.src && el.src.indexOf("blob:") !== 0) state.media[id] = el.src;
      });

      localStorage.setItem(UI_STATE_KEY, JSON.stringify(state));
    } catch (_) {}
  }

  function restoreUIState() {
    var raw = localStorage.getItem(UI_STATE_KEY);
    if (!raw) return;
    try {
      var state = JSON.parse(raw);
      if (!state || typeof state !== "object") return;

      if (state.activeTab) setActiveTab(state.activeTab);
      if (state.activeSource) setActiveSource(state.activeSource);

      var values = state.values || {};
      Object.keys(values).forEach(function (id) {
        var el = getId(id);
        if (!el) return;
        if (typeof el.value !== "undefined") el.value = values[id] == null ? "" : String(values[id]);
      });

      var checks = state.checks || {};
      Object.keys(checks).forEach(function (id) {
        var el = getId(id);
        if (el) el.checked = !!checks[id];
      });

      var texts = state.texts || {};
      Object.keys(texts).forEach(function (id) {
        var el = getId(id);
        if (el) el.textContent = texts[id] == null ? "" : String(texts[id]);
      });

      var html = state.html || {};
      Object.keys(html).forEach(function (id) {
        var el = getId(id);
        if (el) el.innerHTML = html[id] == null ? "" : String(html[id]);
      });

      var ttsErrorEl = getId("ttsError");
      if (ttsErrorEl && typeof state.ttsErrorHidden !== "undefined") {
        if (state.ttsErrorHidden) ttsErrorEl.classList.add("hidden");
        else ttsErrorEl.classList.remove("hidden");
      }

      var media = state.media || {};
      Object.keys(media).forEach(function (id) {
        var el = getId(id);
        var src = media[id];
        if (el && src) el.src = src;
      });

      var speedSliderEl = getId("ttsSpeed");
      var speedValueEl = getId("speedValue");
      if (speedSliderEl && speedValueEl) {
        speedValueEl.textContent = parseFloat(speedSliderEl.value || "1").toFixed(1);
      }
    } catch (_) {}
  }

  // تبويبات ASR / TTS
  qsa(".tab[data-tab]").forEach(function (t) {
    t.addEventListener("click", function () {
      setActiveTab(t.dataset.tab);
      queueUIStateSave();
    });
  });

  // مصدر الصوت: ملف / ميكروفون
  qsa(".src-btn").forEach(function (b) {
    b.addEventListener("click", function () {
      setActiveSource(b.dataset.src || "file");
      queueUIStateSave();
    });
  });

  restoreUIState();

  document.addEventListener("input", function (e) {
    var t = e && e.target;
    if (!t || !t.id || t.type === "file") return;
    queueUIStateSave();
  });

  document.addEventListener("change", function (e) {
    var t = e && e.target;
    if (!t || !t.id || t.type === "file") return;
    queueUIStateSave();
  });

  window.addEventListener("beforeunload", function () {
    saveUIState();
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") saveUIState();
  });

  function updateSingleFileLabel() {
    var fileInput = getId("fileIn");
    var label = getId("fileInLabel");
    var clearBtn = getId("btnClearFileIn");
    if (!fileInput || !label) return;
    if (fileInput.files && fileInput.files.length > 0) {
      label.textContent = fileInput.files[0].name || "تم اختيار ملف صوتي";
      label.classList.add("selected");
      if (clearBtn) clearBtn.classList.remove("hidden");
      return;
    }
    label.textContent = "اختر ملف صوتي واحد";
    label.classList.remove("selected");
    if (clearBtn) clearBtn.classList.add("hidden");
  }

  function updateMultiFilesStatus() {
    var filesInput = getId("filesIn");
    var label = getId("filesInLabel");
    var status = getId("filesInStatus");
    var clearBtn = getId("btnClearFilesIn");
    if (!filesInput) return;
    var count = filesInput.files ? filesInput.files.length : 0;
    if (count > 0) {
      var first = filesInput.files[0] ? (filesInput.files[0].name || "") : "";
      if (label) {
        label.textContent = count === 1 ? ("ملف مرفوع: " + first) : ("ملفات مرفوعة: " + count);
      }
      if (status) {
        status.textContent = count === 1 ? first : ("أول ملف: " + first + " — العدد: " + count);
        status.classList.remove("hidden");
      }
      filesInput.classList.add("selected-files");
      if (clearBtn) clearBtn.classList.remove("hidden");
      return;
    }
    if (label) label.textContent = "رفع عدة ملفات";
    if (status) {
      status.textContent = "";
      status.classList.add("hidden");
    }
    filesInput.classList.remove("selected-files");
    if (clearBtn) clearBtn.classList.add("hidden");
  }

  var fileInEl = getId("fileIn");
  if (fileInEl) {
    fileInEl.addEventListener("change", updateSingleFileLabel);
    updateSingleFileLabel();
  }

  var btnClearFileIn = getId("btnClearFileIn");
  if (btnClearFileIn && fileInEl) {
    btnClearFileIn.addEventListener("click", function () {
      fileInEl.value = "";
      updateSingleFileLabel();
      queueUIStateSave();
    });
  }

  var filesInEl = getId("filesIn");
  if (filesInEl) {
    filesInEl.addEventListener("change", function () {
      updateMultiFilesStatus();
      queueUIStateSave();
    });
    updateMultiFilesStatus();
  }

  var btnClearFilesIn = getId("btnClearFilesIn");
  if (btnClearFilesIn && filesInEl) {
    btnClearFilesIn.addEventListener("click", function () {
      filesInEl.value = "";
      updateMultiFilesStatus();
      queueUIStateSave();
    });
  }

  function getHeaders() {
    var h = { "Accept": "application/json" };
    var key = getId("apiKey");
    if (key && key.value && key.value.trim()) h["X-API-Key"] = key.value.trim();
    if (session && session.token) h["Authorization"] = "Bearer " + session.token;
    return h;
  }

  var session = {
    email: localStorage.getItem("meetasr_email") || "",
    token: localStorage.getItem("meetasr_token") || "",
  };

  function setSession(email, token) {
    session.email = email || "";
    session.token = token || "";
    if (session.email) localStorage.setItem("meetasr_email", session.email);
    else localStorage.removeItem("meetasr_email");
    if (session.token) localStorage.setItem("meetasr_token", session.token);
    else localStorage.removeItem("meetasr_token");
    var profileEmail = getId("profileEmail");
    var dashEmail = getId("dashEmail");
    var ttsUserEmail = getId("ttsUserEmail");
    if (profileEmail) profileEmail.value = session.email;
    if (dashEmail) dashEmail.value = session.email;
    if (ttsUserEmail && session.email) ttsUserEmail.value = session.email;
    queueUIStateSave();
  }

  function setText(id, text) {
    var el = getId(id);
    if (el) el.textContent = text || "";
    queueUIStateSave();
  }

  function jsonRequest(url, method, body, timeoutSec) {
    var headers = getHeaders();
    headers["Content-Type"] = "application/json";
    return fetchWithTimeout(url, {
      method: method,
      headers: headers,
      body: body ? JSON.stringify(body) : undefined,
    }, timeoutSec || (getId("timeout") ? getId("timeout").value : 300))
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) {
          if (!r.ok) {
            throw new Error(data.detail || data.error || r.statusText);
          }
          return data;
        });
      });
  }

  function normalizeDigits(value) {
    return String(value == null ? "" : value)
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 1632); })
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 1776); });
  }

  function resolveTimeoutSeconds(timeoutSec, fallbackSec) {
    var raw = normalizeDigits(timeoutSec);
    var parsed = parseInt(raw, 10);
    if (!isFinite(parsed) || parsed <= 0) parsed = parseInt(fallbackSec, 10);
    if (!isFinite(parsed) || parsed <= 0) parsed = 900;
    return parsed;
  }

  function fetchWithTimeout(url, opts, timeoutMs) {
    var sec = resolveTimeoutSeconds(timeoutMs, 900);
    var t = Math.max(60000, sec * 1000);
    var ctrl = new AbortController();
    var id = setTimeout(function () { ctrl.abort(); }, t);
    opts = opts || {};
    opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (r) {
      clearTimeout(id);
      return r;
    }, function (e) {
      clearTimeout(id);
      if (e && e.name === "AbortError") {
        throw new Error("انتهت مهلة الطلب. زِد قيمة timeout ثم أعد المحاولة.");
      }
      throw e;
    });
  }

  function setButtonBusy(btnOrId, busy, busyText) {
    var btn = (typeof btnOrId === "string") ? getId(btnOrId) : btnOrId;
    if (!btn) return;
    if (busy) {
      if (!btn.dataset.originalText) btn.dataset.originalText = btn.textContent;
      if (busyText) btn.textContent = busyText;
      btn.disabled = true;
      btn.classList.add("loading");
      return;
    }
    btn.disabled = false;
    btn.classList.remove("loading");
    if (btn.dataset.originalText) btn.textContent = btn.dataset.originalText;
  }

  function isAudioFileLike(file) {
    if (!file) return false;
    var type = String(file.type || "").toLowerCase();
    if (type.indexOf("audio/") === 0) return true;
    var n = String(file.name || "").toLowerCase();
    return /\.(wav|mp3|m4a|mp4|webm|3gp|ogg|flac|aac|opus)$/i.test(n);
  }

  function validateAudioFilesList(fileList, minCount) {
    var files = fileList || [];
    if (!files.length || files.length < (minCount || 1)) return "يرجى اختيار ملف صوتي صالح.";
    for (var i = 0; i < files.length; i++) {
      if (!isAudioFileLike(files[i])) {
        return "بعض الملفات ليست صوتية مدعومة.";
      }
    }
    return "";
  }

  function setupDropZone(zoneId, inputId, onFilesSet) {
    var zone = getId(zoneId);
    var input = getId(inputId);
    if (!zone || !input) return;

    ["dragenter", "dragover"].forEach(function (evName) {
      zone.addEventListener(evName, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.add("drag-over");
      });
    });

    ["dragleave", "dragend", "drop"].forEach(function (evName) {
      zone.addEventListener(evName, function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove("drag-over");
      });
    });

    zone.addEventListener("drop", function (e) {
      if (!e.dataTransfer || !e.dataTransfer.files || !e.dataTransfer.files.length) return;
      try {
        input.files = e.dataTransfer.files;
      } catch (_) {
        return;
      }
      input.dispatchEvent(new Event("change", { bubbles: true }));
      if (typeof onFilesSet === "function") onFilesSet();
    });
  }

  setupDropZone("file-zone", "fileIn", function () {
    updateSingleFileLabel();
    queueUIStateSave();
  });

  setupDropZone("files-zone", "filesIn", function () {
    updateMultiFilesStatus();
    queueUIStateSave();
  });

  var PENDING_JOBS_KEY = "meetasr_pending_jobs_v1";
  var pendingPollTimers = {};

  function getPendingJobs() {
    try {
      var raw = localStorage.getItem(PENDING_JOBS_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function setPendingJob(kind, info) {
    var jobs = getPendingJobs();
    if (info) jobs[kind] = info;
    else delete jobs[kind];
    localStorage.setItem(PENDING_JOBS_KEY, JSON.stringify(jobs));
  }

  function clearPendingJob(kind) {
    if (pendingPollTimers[kind]) {
      clearTimeout(pendingPollTimers[kind]);
      delete pendingPollTimers[kind];
    }
    setPendingJob(kind, null);
  }

  function segText(segments) {
    var segs = Array.isArray(segments) ? segments : [];
    return segs.map(function (x) {
      var spk = x && x.speaker !== undefined ? " [" + ((x.speaker || "?")) + "] " : " ";
      var start = (x && typeof x.start === "number") ? x.start : 0;
      return start.toFixed(1) + "s" + spk + ((x && x.text) || "");
    }).join("\n");
  }

  function buildDownloadUrls(data) {
    var urls = (data && data.download_urls) ? data.download_urls : {};
    if (urls.txt || urls.srt || urls.vtt || urls.summary || urls.segments) return urls;
    var out = {};
    if (data && data.txt_path) out.txt = "/download?path=" + encodeURIComponent(data.txt_path);
    if (data && data.srt_path) out.srt = "/download?path=" + encodeURIComponent(data.srt_path);
    if (data && data.vtt_path) out.vtt = "/download?path=" + encodeURIComponent(data.vtt_path);
    if (data && data.summary_path) out.summary = "/download?path=" + encodeURIComponent(data.summary_path);
    if (data && data.segments_path) out.segments = "/download?path=" + encodeURIComponent(data.segments_path);
    return out;
  }

  function renderDownloadLinks(urls, clearFirst) {
    var links = getId("dlLinks");
    if (!links) return;
    if (clearFirst) links.innerHTML = "";
    urls = urls || {};
    if (urls.txt) links.innerHTML += '<a href="' + urls.txt + '" download>تحميل TXT</a> ';
    if (urls.srt) links.innerHTML += '<a href="' + urls.srt + '" download>تحميل SRT</a> ';
    if (urls.vtt) links.innerHTML += '<a href="' + urls.vtt + '" download>تحميل VTT</a> ';
    if (urls.segments) links.innerHTML += '<a href="' + urls.segments + '" download>تحميل segments</a> ';
    if (urls.summary) links.innerHTML += '<a href="' + urls.summary + '" download>تحميل الملخص</a>';
  }

  function applyTranscribeResult(data) {
    getId("outText").value = data.text || "";
    getId("outSummary").value = data.summary || "";
    getId("outKeywords").value = data.keywords || "";
    var segs = data.segments || [];
    if (getId("outSegments")) getId("outSegments").textContent = segText(segs);
    renderDownloadLinks(buildDownloadUrls(data), true);
    queueUIStateSave();
  }

  function applySummaryResult(data) {
    getId("outSummary").value = data.summary || "";
    getId("outKeywords").value = data.keywords || "";
    renderDownloadLinks(buildDownloadUrls(data), false);
    queueUIStateSave();
  }

  function pollJob(kind, info) {
    if (!info || !info.job_id) return;
    if (pendingPollTimers[kind]) clearTimeout(pendingPollTimers[kind]);
    var pollUrl = info.poll_url || ("/job/" + encodeURIComponent(info.job_id));
    var timeout = getId("timeout") ? getId("timeout").value : 300;

    var tick = function () {
      fetchWithTimeout(pollUrl, { method: "GET", headers: getHeaders() }, timeout)
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error((data && (data.detail || data.error)) || r.statusText);
            return data;
          });
        })
        .then(function (job) {
          var status = (job && job.status) ? String(job.status).toLowerCase() : "";
          if (status === "queued" || status === "running") {
            if (kind === "transcribe") {
              getId("outText").value = "المعالجة مستمرة في الخلفية... (" + status + ")";
            } else if (kind === "summary") {
              getId("outSummary").value = "التلخيص مستمر في الخلفية... (" + status + ")";
            }
            queueUIStateSave();
            pendingPollTimers[kind] = setTimeout(tick, 2000);
            return;
          }

          if (status === "done") {
            var result = (job && job.result) ? job.result : {};
            if (kind === "transcribe") applyTranscribeResult(result);
            if (kind === "summary") applySummaryResult(result);
            clearPendingJob(kind);
            return;
          }

          var errMsg = (job && (job.error || job.detail)) || "فشل تنفيذ المهمة.";
          if (kind === "transcribe") getId("outText").value = "خطأ: " + errMsg;
          if (kind === "summary") getId("outSummary").value = "خطأ: " + errMsg;
          clearPendingJob(kind);
          queueUIStateSave();
        })
        .catch(function () {
          pendingPollTimers[kind] = setTimeout(tick, 2500);
        });
    };

    tick();
  }

  function resumePendingJobs() {
    var jobs = getPendingJobs();
    if (jobs.transcribe && jobs.transcribe.job_id) {
      getId("outText").value = "تم استعادة مهمة التحويل بعد التحديث...";
      pollJob("transcribe", jobs.transcribe);
    }
    if (jobs.summary && jobs.summary.job_id) {
      getId("outSummary").value = "تم استعادة مهمة التلخيص بعد التحديث...";
      pollJob("summary", jobs.summary);
    }
    queueUIStateSave();
  }

  // إرسال ملف واحد
  getId("btnSend").addEventListener("click", function () {
    var btnSend = getId("btnSend");
    var src = qs(".src-btn.active");
    var fileIn = getId("fileIn"), micZone = getId("mic-zone");
    var fd = new FormData();
    var file = null;
    if (src && src.dataset.src === "mic") {
      var recBlob = window._lastRecordedBlob;
      if (!recBlob) {
        getId("outText").value = "يرجى تسجيل صوت أولاً.";
        return;
      }
      fd.append("file", recBlob, "recording.webm");
    } else if (fileIn && fileIn.files && fileIn.files[0]) {
      var fileErr = validateAudioFilesList(fileIn.files, 1);
      if (fileErr) {
        getId("outText").value = fileErr;
        return;
      }
      fd.append("file", fileIn.files[0]);
    } else {
      getId("outText").value = "يرجى اختيار ملف أو تسجيل صوت.";
      return;
    }
    var whisperModeEl = getId("whisperMode");
    var enhanceEl = getId("enhance");
    var enhanceLevelEl = getId("enhanceLevel");
    fd.append("model_name", "heavy");
    fd.append("whisper_mode", whisperModeEl ? whisperModeEl.value : "normal");
    fd.append("enhance", (enhanceEl && enhanceEl.value !== "off") ? "true" : "false");
    fd.append("enhance_mode", enhanceEl ? (enhanceEl.value || "off") : "off");
    fd.append("enhance_level", enhanceLevelEl ? enhanceLevelEl.value : "medium");
    fd.append("diarize", getId("diarize").checked ? "true" : "false");
    fd.append("auto_k", getId("autoK").checked ? "true" : "false");
    fd.append("max_speakers", getId("maxSpeakers") ? getId("maxSpeakers").value : "2");
    fd.append("enroll_threshold", getId("enrollThreshold") ? getId("enrollThreshold").value : "0.65");
    fd.append("device_sel", getId("deviceSel") ? getId("deviceSel").value : "auto");
    fd.append("compute_sel", getId("computeSel") ? getId("computeSel").value : "auto");
    fd.append("async_mode", "true");
    if (session.email) fd.append("user_email", session.email);

    getId("outText").value = "جاري التحويل...";
    getId("outSummary").value = "";
    getId("outKeywords").value = "";
    getId("dlLinks").innerHTML = "";
    getId("outSegments").textContent = "";
  setButtonBusy(btnSend, true, "جاري الإرسال...");

    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/transcribe", {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (data && data.job_id && (data.status === "queued" || data.status === "running")) {
          setPendingJob("transcribe", {
            job_id: data.job_id,
            poll_url: data.poll_url || ("/job/" + encodeURIComponent(data.job_id)),
          });
          getId("outText").value = "تم إرسال المهمة للخلفية. يمكنك تحديث الصفحة ولن تنقطع العملية.";
          queueUIStateSave();
          pollJob("transcribe", getPendingJobs().transcribe);
          return;
        }
        applyTranscribeResult(data || {});
      })
      .catch(function (e) {
        getId("outText").value = "خطأ: " + (e.message || String(e));
      })
      .finally(function () {
        setButtonBusy(btnSend, false);
      });
  });

  // إرسال عدة ملفات
  getId("btnBatch").addEventListener("click", function () {
    var btnBatch = getId("btnBatch");
    var filesIn = getId("filesIn");
    var batchErr = validateAudioFilesList(filesIn && filesIn.files, 1);
    if (batchErr) {
      getId("outText").value = "يرجى اختيار عدة ملفات صوتية صالحة.";
      return;
    }
    var fd = new FormData();
    for (var i = 0; i < filesIn.files.length; i++) fd.append("files", filesIn.files[i]);
    var whisperModeEl = getId("whisperMode");
    var enhanceEl = getId("enhance");
    var enhanceLevelEl = getId("enhanceLevel");
    fd.append("model_name", "heavy");
    fd.append("whisper_mode", whisperModeEl ? whisperModeEl.value : "normal");
    fd.append("enhance", (enhanceEl && enhanceEl.value !== "off") ? "true" : "false");
    fd.append("enhance_mode", enhanceEl ? (enhanceEl.value || "off") : "off");
    fd.append("enhance_level", enhanceLevelEl ? enhanceLevelEl.value : "medium");
    fd.append("diarize", getId("diarize").checked ? "true" : "false");
    fd.append("auto_k", getId("autoK").checked ? "true" : "false");
    fd.append("max_speakers", getId("maxSpeakers") ? getId("maxSpeakers").value : "2");
    fd.append("enroll_threshold", getId("enrollThreshold") ? getId("enrollThreshold").value : "0.65");
    fd.append("device_sel", getId("deviceSel") ? getId("deviceSel").value : "auto");
    fd.append("compute_sel", getId("computeSel") ? getId("computeSel").value : "auto");
    fd.append("async_mode", "true");
    if (session.email) fd.append("user_email", session.email);

    getId("outText").value = "جاري تحويل عدة ملفات...";
    getId("outSummary").value = "";
    getId("outKeywords").value = "";
    getId("dlLinks").innerHTML = "";
    getId("outSegments").textContent = "";
    setButtonBusy(btnBatch, true, "جاري إرسال الدفعة...");

    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/transcribe-batch", {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (data && data.job_id && (data.status === "queued" || data.status === "running")) {
          setPendingJob("transcribe", {
            job_id: data.job_id,
            poll_url: data.poll_url || ("/job/" + encodeURIComponent(data.job_id)),
          });
          getId("outText").value = "تم إرسال مهمة الدفعة للخلفية. يمكنك تحديث الصفحة ولن تنقطع العملية.";
          queueUIStateSave();
          pollJob("transcribe", getPendingJobs().transcribe);
          return;
        }
        applyTranscribeResult(data || {});
      })
      .catch(function (e) {
        getId("outText").value = "خطأ: " + (e.message || String(e));
      })
      .finally(function () {
        setButtonBusy(btnBatch, false);
      });
  });

  // تلخيص النص
  getId("btnSummary").addEventListener("click", function () {
    var btnSummary = getId("btnSummary");
    var text = (getId("outText") && getId("outText").value || "").trim();
    if (!text) {
      getId("outSummary").value = "أدخل نصاً أولاً أو قم بالتحويل الصوتي.";
      return;
    }
    var mode = getId("summaryMode") ? getId("summaryMode").value : "ultra";
    var fd = new FormData();
    fd.append("text", text);
    fd.append("summary_mode", mode);
    fd.append("async_mode", "true");
    if (session.email) fd.append("user_email", session.email);
    getId("outSummary").value = "جاري التلخيص...";
    setButtonBusy(btnSummary, true, "جاري التلخيص...");
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/summarize", { method: "POST", headers: getHeaders(), body: fd }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (data && data.job_id && (data.status === "queued" || data.status === "running")) {
          setPendingJob("summary", {
            job_id: data.job_id,
            poll_url: data.poll_url || ("/job/" + encodeURIComponent(data.job_id)),
          });
          getId("outSummary").value = "تم إرسال التلخيص للخلفية. يمكنك تحديث الصفحة ولن تنقطع العملية.";
          queueUIStateSave();
          pollJob("summary", getPendingJobs().summary);
          return;
        }
        applySummaryResult(data || {});
      })
      .catch(function (e) {
        getId("outSummary").value = "خطأ: " + (e.message || String(e));
      })
      .finally(function () {
        setButtonBusy(btnSummary, false);
      });
  });

  // تسجيل الميكروفون
  var mediaRecorder = null, recordedChunks = [];
  getId("micBtn").addEventListener("click", function () {
    var btn = getId("micBtn"), status = getId("micStatus");
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      btn.textContent = "بدء التسجيل";
      status.textContent = "توقف. اضغط 'إرسال ملف واحد' لتحويل الصوت.";
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = "المتصفح لا يدعم تسجيل الميكروفون.";
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        recordedChunks = [];
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = function (e) { if (e.data.size) recordedChunks.push(e.data); };
        mediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          window._lastRecordedBlob = new Blob(recordedChunks, { type: "audio/webm" });
        };
        mediaRecorder.start();
        btn.textContent = "إيقاف التسجيل";
        status.textContent = "جاري التسجيل...";
      })
      .catch(function (e) {
        status.textContent = "فشل الوصول للميكروفون: " + (e.message || String(e));
      });
  });

  // عرض قيمة السرعة ديناميكياً
  var speedSlider = getId("ttsSpeed");
  var speedValue = getId("speedValue");
  if (speedSlider && speedValue) {
    speedSlider.addEventListener("input", function () {
      speedValue.textContent = parseFloat(speedSlider.value).toFixed(1);
    });
  }

  // TTS
  function getTtsUserEmail() {
    var ttsUserEmail = (getId("ttsUserEmail") && getId("ttsUserEmail").value || "").trim();
    return ttsUserEmail || session.email || "";
  }

  function refreshTtsVoiceSamples() {
    var statusEl = getId("ttsVoiceStatus");
    var listEl = getId("ttsVoiceFilesList");
    var userEmail = getTtsUserEmail();
    if (!listEl) return;
    listEl.innerHTML = '<option value="">— اختر ملف بصمة —</option>';
    if (!userEmail) {
      if (statusEl) statusEl.textContent = "أدخل بريد المستخدم أو سجّل الدخول أولاً.";
      return;
    }
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/tts/voice-samples?user_email=" + encodeURIComponent(userEmail), {
      method: "GET",
      headers: getHeaders(),
    }, timeout)
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) throw new Error(data.detail || data.error || r.statusText);
          return data;
        });
      })
      .then(function (data) {
        var files = (data && data.files) ? data.files : [];
        files.forEach(function (item) {
          var name = (item && item.name) ? item.name : "";
          if (!name) return;
          var opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name + (item.size_bytes ? " (" + item.size_bytes + " bytes)" : "");
          listEl.appendChild(opt);
        });
        if (statusEl) statusEl.textContent = "تم تحميل " + files.length + " بصمة.";
      })
      .catch(function (e) {
        if (statusEl) statusEl.textContent = "خطأ: " + (e.message || String(e));
      });
  }

  var btnTtsRefreshVoices = getId("btnTtsRefreshVoices");
  if (btnTtsRefreshVoices) {
    btnTtsRefreshVoices.addEventListener("click", refreshTtsVoiceSamples);
  }

  var btnTtsUploadVoices = getId("btnTtsUploadVoices");
  if (btnTtsUploadVoices) {
    btnTtsUploadVoices.addEventListener("click", function () {
      var statusEl = getId("ttsVoiceStatus");
      var filesEl = getId("ttsVoiceFiles");
      var userEmail = getTtsUserEmail();
      if (!userEmail) {
        if (statusEl) statusEl.textContent = "أدخل بريد المستخدم أولاً.";
        return;
      }
      if (!filesEl || !filesEl.files || filesEl.files.length === 0) {
        if (statusEl) statusEl.textContent = "اختر ملفًا واحدًا أو أكثر.";
        return;
      }
      var fd = new FormData();
      fd.append("user_email", userEmail);
      for (var i = 0; i < filesEl.files.length; i++) fd.append("files", filesEl.files[i]);
      if (statusEl) statusEl.textContent = "جاري رفع البصمات...";
      var timeout = getId("timeout") ? getId("timeout").value : 300;
      fetchWithTimeout("/tts/voice-samples", {
        method: "POST",
        headers: getHeaders(),
        body: fd,
      }, timeout)
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error(data.detail || data.error || r.statusText);
            return data;
          });
        })
        .then(function (data) {
          if (statusEl) statusEl.textContent = "تم رفع " + (data.count || 0) + " ملف.";
          refreshTtsVoiceSamples();
          filesEl.value = "";
        })
        .catch(function (e) {
          if (statusEl) statusEl.textContent = "خطأ: " + (e.message || String(e));
        });
    });
  }

  var btnTtsDeleteVoice = getId("btnTtsDeleteVoice");
  if (btnTtsDeleteVoice) {
    btnTtsDeleteVoice.addEventListener("click", function () {
      var statusEl = getId("ttsVoiceStatus");
      var userEmail = getTtsUserEmail();
      var selectedFile = (getId("ttsVoiceFilesList") && getId("ttsVoiceFilesList").value || "").trim();
      if (!userEmail || !selectedFile) {
        if (statusEl) statusEl.textContent = "حدّد البريد وملف البصمة أولاً.";
        return;
      }
      var timeout = getId("timeout") ? getId("timeout").value : 300;
      var url = "/tts/voice-sample?user_email=" + encodeURIComponent(userEmail) + "&file=" + encodeURIComponent(selectedFile);
      fetchWithTimeout(url, {
        method: "DELETE",
        headers: getHeaders(),
      }, timeout)
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error(data.detail || data.error || r.statusText);
            return data;
          });
        })
        .then(function () {
          if (statusEl) statusEl.textContent = "تم حذف البصمة: " + selectedFile;
          refreshTtsVoiceSamples();
          var voiceAudio = getId("ttsVoiceAudio");
          if (voiceAudio) voiceAudio.removeAttribute("src");
        })
        .catch(function (e) {
          if (statusEl) statusEl.textContent = "خطأ: " + (e.message || String(e));
        });
    });
  }

  var ttsVoiceFilesList = getId("ttsVoiceFilesList");
  if (ttsVoiceFilesList) {
    ttsVoiceFilesList.addEventListener("change", function () {
      var userEmail = getTtsUserEmail();
      var file = (ttsVoiceFilesList.value || "").trim();
      var audioEl = getId("ttsVoiceAudio");
      if (!userEmail || !file || !audioEl) {
        if (audioEl) audioEl.removeAttribute("src");
        return;
      }
      var url = "/tts/voice-file?user_email=" + encodeURIComponent(userEmail) + "&file=" + encodeURIComponent(file);
      fetch(url, { headers: getHeaders() })
        .then(function (r) {
          if (!r.ok) throw new Error(r.statusText);
          return r.blob();
        })
        .then(function (blob) {
          var prev = audioEl.src;
          if (prev && prev.indexOf("blob:") === 0) URL.revokeObjectURL(prev);
          audioEl.src = URL.createObjectURL(blob);
        })
        .catch(function () {
          audioEl.removeAttribute("src");
        });
    });
  }

  var ttsUserEmailEl = getId("ttsUserEmail");
  if (ttsUserEmailEl) {
    ttsUserEmailEl.addEventListener("change", refreshTtsVoiceSamples);
  }

  getId("btnTts").addEventListener("click", function () {
    var btnTts = getId("btnTts");
    var textEl = getId("ttsText"), text = (textEl && textEl.value || "").trim();
    if (!text) {
      var errEl = getId("ttsError");
      errEl.textContent = "أدخل نصاً أولاً.";
      errEl.classList.remove("hidden");
      return;
    }
    var voice = getId("ttsVoice").value || "ar_mms";
    var engine = (getId("ttsEngine") && getId("ttsEngine").value || "auto").trim();
    var speed = parseFloat(getId("ttsSpeed").value) || 1;
    var seedEl = getId("ttsSeed");
    var seed = seedEl && seedEl.value ? parseInt(seedEl.value, 10) : undefined;
    var speakerRef = (getId("ttsVoiceFilesList") && getId("ttsVoiceFilesList").value || "").trim();
    var userEmailForTts = getTtsUserEmail();
    if (isNaN(seed)) seed = undefined;

    var errEl = getId("ttsError");
    errEl.classList.add("hidden");
    var audioEl = getId("ttsAudio");
    var dlEl = getId("ttsDl");
    var metaEl = getId("ttsMeta");
    dlEl.innerHTML = "";
    if (metaEl) metaEl.textContent = "";

    var body = { text: text, voice: voice, speed: speed, engine: engine || "auto" };
    if (userEmailForTts) body.user_email = userEmailForTts;
    if (seed != null) body.seed = seed;
    if (speakerRef) body.speaker_ref = speakerRef;

    var h = getHeaders();
    h["Content-Type"] = "application/json";

    var timeout = getId("timeout") ? getId("timeout").value : 300;
    setButtonBusy(btnTts, true, "جاري توليد الصوت...");
    fetchWithTimeout("/tts", { method: "POST", headers: h, body: JSON.stringify(body) }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (data.download_url) {
          audioEl.src = data.download_url;
          dlEl.innerHTML = '<a href="' + data.download_url + '" download="tts.wav">تحميل الصوت</a>';
        }
        if (metaEl) {
          var meta = [
            "engine_used: " + (data.engine_used || "-"),
            "requested_voice: " + (data.requested_voice || "-"),
            "resolved_voice: " + (data.resolved_voice || "-"),
            "speaker_ref: " + (data.speaker_ref || "-"),
            "fallback_used: " + (data.fallback_used ? "yes" : "no"),
            "arabic_detected: " + (data.arabic_detected ? "yes" : "no")
          ].join("\n");
          metaEl.textContent = meta;
        }
      })
      .catch(function (e) {
        errEl.textContent = "خطأ: " + (e.message || String(e));
        errEl.classList.remove("hidden");
      })
      .finally(function () {
        setButtonBusy(btnTts, false);
      });
  });

  // ——— بصمات الصوت والمتحدثون ———
  var spkMediaRecorder = null, spkRecordedChunks = [];
  function refreshSpeakersList() {
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/enrolled-speakers", { method: "GET", headers: getHeaders() }, timeout)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var sel = getId("spkList");
        if (!sel) return;
        var list = (data && data.speakers) ? data.speakers : [];
        var cur = sel.value;
        sel.innerHTML = '<option value="">— اختر —</option>';
        list.forEach(function (n) {
          var opt = document.createElement("option");
          opt.value = n;
          opt.textContent = n;
          sel.appendChild(opt);
        });
        if (cur && list.indexOf(cur) >= 0) sel.value = cur;
      })
      .catch(function () {});
  }

  getId("btnEnroll").addEventListener("click", function () {
    var btnEnroll = getId("btnEnroll");
    var name = (getId("spkName") && getId("spkName").value || "").trim();
    if (!name) {
      getId("enrollOut").textContent = "الرجاء إدخال اسم المتكلم.";
      return;
    }
    var fd = new FormData();
    fd.append("name", name);
    var filesIn = getId("spkFiles");
    var hasFile = false;
    if (filesIn && filesIn.files) {
      for (var i = 0; i < filesIn.files.length; i++) {
        fd.append("files", filesIn.files[i]);
        hasFile = true;
      }
    }
    if (window._lastSpkRecordedBlob) {
      fd.append("files", window._lastSpkRecordedBlob, "spk_recording.webm");
      hasFile = true;
    }
    if (!hasFile) {
      getId("enrollOut").textContent = "الرجاء رفع ملفات صوتية أو تسجيل مقطع.";
      return;
    }
    if (filesIn && filesIn.files && filesIn.files.length) {
      var enrollErr = validateAudioFilesList(filesIn.files, 1);
      if (enrollErr) {
        getId("enrollOut").textContent = enrollErr;
        return;
      }
    }
    getId("enrollOut").textContent = "جاري التسجيل...";
    setButtonBusy(btnEnroll, true, "جاري التسجيل...");
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/enroll-speaker", { method: "POST", headers: getHeaders(), body: fd }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.message || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        getId("enrollOut").textContent = (data.message || "تم التسجيل.") + (data.success ? "" : " (تحذير)");
        refreshSpeakersList();
      })
      .catch(function (e) {
        getId("enrollOut").textContent = "خطأ: " + (e.message || String(e));
      })
      .finally(function () {
        setButtonBusy(btnEnroll, false);
      });
  });

  getId("spkMicBtn").addEventListener("click", function () {
    var btn = getId("spkMicBtn"), status = getId("spkMicStatus");
    if (spkMediaRecorder && spkMediaRecorder.state === "recording") {
      spkMediaRecorder.stop();
      btn.textContent = "تسجيل مقطع من الميكروفون";
      status.textContent = "توقف. يمكنك تسجيل البصمة.";
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = "المتصفح لا يدعم الميكروفون.";
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        spkRecordedChunks = [];
        spkMediaRecorder = new MediaRecorder(stream);
        spkMediaRecorder.ondataavailable = function (e) { if (e.data.size) spkRecordedChunks.push(e.data); };
        spkMediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          window._lastSpkRecordedBlob = new Blob(spkRecordedChunks, { type: "audio/webm" });
        };
        spkMediaRecorder.start();
        btn.textContent = "إيقاف التسجيل";
        status.textContent = "جاري التسجيل...";
      })
      .catch(function (e) {
        status.textContent = "فشل الوصول للميكروفون: " + (e.message || String(e));
      });
  });

  getId("btnRefreshSpeakers").addEventListener("click", function () { refreshSpeakersList(); });

  getId("btnDeleteSpeaker").addEventListener("click", function () {
    var name = (getId("spkList") && getId("spkList").value || "").trim();
    if (!name) {
      getId("enrollOut").textContent = "الرجاء تحديد متحدث من القائمة.";
      return;
    }
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/delete-speaker?name=" + encodeURIComponent(name), { method: "DELETE", headers: getHeaders() }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.message || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        getId("enrollOut").textContent = data.message || "تم الحذف.";
        refreshSpeakersList();
        getId("spkFilesList").innerHTML = "<option value=\"\">— اختر —</option>";
        getId("spkAudio").removeAttribute("src");
      })
      .catch(function (e) {
        getId("enrollOut").textContent = "خطأ: " + (e.message || String(e));
      });
  });

  getId("spkList").addEventListener("change", function () {
    var name = (getId("spkList") && getId("spkList").value || "").trim();
    var filesSel = getId("spkFilesList");
    var audioEl = getId("spkAudio");
    filesSel.innerHTML = "<option value=\"\">— اختر —</option>";
    audioEl.removeAttribute("src");
    if (!name) return;
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/speaker-files?name=" + encodeURIComponent(name), { method: "GET", headers: getHeaders() }, timeout)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var files = (data && data.files) ? data.files : [];
        files.forEach(function (f) {
          var opt = document.createElement("option");
          opt.value = f;
          opt.textContent = f;
          filesSel.appendChild(opt);
        });
      })
      .catch(function () {});
  });

  getId("spkFilesList").addEventListener("change", function () {
    var name = (getId("spkList") && getId("spkList").value || "").trim();
    var file = (getId("spkFilesList") && getId("spkFilesList").value || "").trim();
    var audioEl = getId("spkAudio");
    if (!name || !file) {
      audioEl.removeAttribute("src");
      return;
    }
    var url = "/speaker-file?name=" + encodeURIComponent(name) + "&file=" + encodeURIComponent(file);
    // استخدام fetch مع الرأس ليدعم مفتاح API ثم blob URL للتشغيل
    fetch(url, { headers: getHeaders() })
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.blob();
      })
      .then(function (blob) {
        var prev = audioEl.src;
        if (prev && prev.indexOf("blob:") === 0) URL.revokeObjectURL(prev);
        audioEl.src = URL.createObjectURL(blob);
      })
      .catch(function () {
        audioEl.removeAttribute("src");
      });
  });

  // تحميل قائمة أصوات TTS من API
  fetch("/tts/voices", { headers: getHeaders() })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (data && data.voices && data.voices.length) {
        var sel = getId("ttsVoice");
        if (sel) {
          var cur = sel.value;
          sel.innerHTML = "";
          data.voices.forEach(function (v) {
            var opt = document.createElement("option");
            opt.value = v;
            opt.textContent = v;
            sel.appendChild(opt);
          });
          if (cur && data.voices.indexOf(cur) >= 0) sel.value = cur;
        }
      }
    })
    .catch(function () {});

  refreshTtsVoiceSamples();

  // ——— الحساب (تسجيل/دخول/خروج) ———
  var btnRegister = getId("btnRegister");
  var btnLogin = getId("btnLogin");
  var btnLogout = getId("btnLogout");

  if (btnRegister) {
    btnRegister.addEventListener("click", function () {
      var email = (getId("authEmail") && getId("authEmail").value || "").trim();
      var password = (getId("authPassword") && getId("authPassword").value || "").trim();
      var fullName = (getId("authFullName") && getId("authFullName").value || "").trim();
      if (!email || !password || !fullName) {
        setText("authStatus", "الرجاء إدخال البريد وكلمة المرور والاسم الكامل.");
        return;
      }
      setText("authStatus", "جاري إنشاء الحساب...");
      jsonRequest("/auth/register", "POST", {
        email: email,
        password: password,
        full_name: fullName,
      }).then(function () {
        setText("authStatus", "تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن.");
      }).catch(function (e) {
        setText("authStatus", "خطأ: " + (e.message || String(e)));
      });
    });
  }

  if (btnLogin) {
    btnLogin.addEventListener("click", function () {
      var email = (getId("authEmail") && getId("authEmail").value || "").trim();
      var password = (getId("authPassword") && getId("authPassword").value || "").trim();
      if (!email || !password) {
        setText("authStatus", "الرجاء إدخال البريد وكلمة المرور.");
        return;
      }
      setText("authStatus", "جاري تسجيل الدخول...");
      jsonRequest("/auth/login", "POST", {
        email: email,
        password: password,
      }).then(function (data) {
        var userEmail = data.email || email;
        setSession(userEmail, data.access_token || "");
        setText("authStatus", "تم تسجيل الدخول بنجاح.");
        if (getId("authFullName") && data.full_name) {
          getId("authFullName").value = data.full_name;
        }
      }).catch(function (e) {
        setText("authStatus", "خطأ: " + (e.message || String(e)));
      });
    });
  }

  if (btnLogout) {
    btnLogout.addEventListener("click", function () {
      if (!session.email) {
        setText("authStatus", "لا يوجد مستخدم مسجل دخول.");
        return;
      }
      fetchWithTimeout("/auth/logout", {
        method: "POST",
        headers: getHeaders(),
      }, getId("timeout") ? getId("timeout").value : 300)
        .then(function () {
          setSession("", "");
          setText("authStatus", "تم تسجيل الخروج.");
          setText("profileStatus", "");
          setText("dashStatus", "");
        })
        .catch(function (e) {
          setText("authStatus", "خطأ: " + (e.message || String(e)));
        });
    });
  }

  // ——— الملف الشخصي ———
  var btnLoadProfile = getId("btnLoadProfile");
  var btnSaveProfile = getId("btnSaveProfile");

  function loadProfile() {
    if (!session.email) {
      setText("profileStatus", "الرجاء تسجيل الدخول أولاً.");
      return;
    }
    setText("profileStatus", "جاري تحميل الملف...");
    fetchWithTimeout("/users/me", {
      method: "GET",
      headers: getHeaders(),
    }, getId("timeout") ? getId("timeout").value : 300)
      .then(function (r) {
        return r.json().then(function (data) {
          if (!r.ok) throw new Error(data.detail || r.statusText);
          return data;
        });
      })
      .then(function (data) {
        if (getId("profileFullName")) getId("profileFullName").value = data.full_name || "";
        if (getId("profileBio")) getId("profileBio").value = data.bio || "";
        if (getId("profileAvatar")) getId("profileAvatar").value = data.avatar_url || "";
        setText("profileStatus", "تم تحميل الملف الشخصي.");
      })
      .catch(function (e) {
        setText("profileStatus", "خطأ: " + (e.message || String(e)));
      });
  }

  if (btnLoadProfile) {
    btnLoadProfile.addEventListener("click", loadProfile);
  }

  if (btnSaveProfile) {
    btnSaveProfile.addEventListener("click", function () {
      if (!session.email) {
        setText("profileStatus", "الرجاء تسجيل الدخول أولاً.");
        return;
      }
      setText("profileStatus", "جاري حفظ التعديلات...");
      jsonRequest("/users/me", "PUT", {
        full_name: (getId("profileFullName") && getId("profileFullName").value || "").trim(),
        bio: (getId("profileBio") && getId("profileBio").value || "").trim(),
        avatar_url: (getId("profileAvatar") && getId("profileAvatar").value || "").trim(),
      }).then(function () {
        setText("profileStatus", "تم حفظ الملف الشخصي.");
      }).catch(function (e) {
        setText("profileStatus", "خطأ: " + (e.message || String(e)));
      });
    });
  }

  // ——— لوحة التحكم ———
  var btnRefreshDashboard = getId("btnRefreshDashboard");

  function refreshDashboard() {
    if (!session.email) {
      setText("dashStatus", "الرجاء تسجيل الدخول أولاً.");
      return;
    }
    setText("dashStatus", "جاري تحديث الإحصائيات...");
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    Promise.all([
      fetchWithTimeout("/dashboard/my-summary", { method: "GET", headers: getHeaders() }, timeout)
        .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || r.statusText); return d; }); }),
      fetchWithTimeout("/dashboard/my-usage", { method: "GET", headers: getHeaders() }, timeout)
        .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || r.statusText); return d; }); })
    ]).then(function (res) {
      var summary = res[0], usage = Array.isArray(res[1]) ? res[1] : [];
      var totalCalls = usage.reduce(function (acc, item) { return acc + (item.total_calls || 0); }, 0);
      var asrCalls = usage.reduce(function (acc, item) { return acc + (item.asr_calls || 0); }, 0);
      var ttsCalls = usage.reduce(function (acc, item) { return acc + (item.tts_calls || 0); }, 0);
      var nlpCalls = usage.reduce(function (acc, item) { return acc + (item.nlp_calls || 0); }, 0);
      var summaryText = [
        "المستخدم: " + (summary.user_email || "-"),
        "وظائف ASR: " + ((summary.jobs && summary.jobs.asr) || 0),
        "وظائف TTS: " + ((summary.jobs && summary.jobs.tts) || 0),
        "وظائف NLP: " + ((summary.jobs && summary.jobs.nlp) || 0),
        "المكالمات هذا الشهر: " + (summary.api_calls_this_month || 0),
        "حد المكالمات: " + (summary.api_calls_limit == null ? "غير محدود" : summary.api_calls_limit),
        "حالة النظام: " + (summary.system_health || "-"),
      ].join("\n");
      var overviewText = [
        "إجمالي نداءات API (آخر فترة): " + totalCalls,
        "نداءات ASR: " + asrCalls,
        "نداءات TTS: " + ttsCalls,
        "نداءات NLP: " + nlpCalls,
        "عدد الأيام في التقرير: " + usage.length,
      ].join("\n");
      if (getId("dashSummary")) getId("dashSummary").textContent = summaryText;
      if (getId("dashOverview")) getId("dashOverview").textContent = overviewText;
      setText("dashStatus", "تم تحديث لوحة التحكم.");
    }).catch(function (e) {
      setText("dashStatus", "خطأ: " + (e.message || String(e)));
    });
  }

  if (btnRefreshDashboard) {
    btnRefreshDashboard.addEventListener("click", refreshDashboard);
  }

  setSession(session.email, session.token);
  resumePendingJobs();
  queueUIStateSave();
})();
