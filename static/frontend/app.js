(function () {
  "use strict";

  function qs(s) { return document.querySelector(s); }
  function qsa(s) { return document.querySelectorAll(s); }
  function getId(id) { return document.getElementById(id); }

  function setZoneVisible(id, visible) {
    var el = getId(id);
    if (el) el.classList.toggle("hidden", !visible);
  }

  function updateTtsEngineUi() {
    var engineEl = getId("ttsEngine");
    if (engineEl) engineEl.value = "habibi";
    var voiceEl = getId("ttsVoice");
    if (voiceEl) {
      var v = voiceEl.value || "";
      if (v !== "habibi_unified" && v !== "habibi_specialized") {
        voiceEl.value = "habibi_unified";
      }
    }
    var hint = getId("ttsAccountHint");
    if (hint) {
      var email = (session && session.email) || "";
      hint.textContent = email
        ? ("البصمات مرتبطة بحسابك: " + email)
        : "سجّل الدخول من تبويب الحساب لاستخدام البصمات.";
    }
    var emailEl = getId("ttsUserEmail");
    if (emailEl && session && session.email) emailEl.value = session.email;
  }

  function setTtsSpeed(value) {
    var speedEl = getId("ttsSpeed");
    var speedValueEl = getId("speedValue");
    if (!speedEl) return;
    var n = parseFloat(value);
    if (isNaN(n)) return;
    n = Math.max(0.25, Math.min(2, n));
    speedEl.value = String(n);
    if (speedValueEl) speedValueEl.textContent = n.toFixed(1);
    qsa(".tts-speed-preset").forEach(function (btn) {
      var s = parseFloat(btn.getAttribute("data-speed") || "");
      btn.classList.toggle("active", Math.abs(s - n) < 0.001);
    });
  }

  function syncTtsChunkLabel() {
    var chunkEl = getId("ttsMaxChunk");
    var labelEl = getId("ttsChunkValue");
    if (chunkEl && labelEl) labelEl.textContent = String(chunkEl.value || "120");
  }

  function refreshTtsEngineStatus() {
    var statusEl = getId("ttsEngineStatus");
    if (!statusEl) return;
    var h = getHeaders();
    fetchWithTimeout(API.tts.voices, { method: "GET", headers: h }, 30)
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        var engines = data.engines || [];
        if (!engines.length) {
          statusEl.textContent = "";
          return;
        }
        statusEl.textContent = engines.map(function (e) {
          return (e.engine || "?") + ": " + (e.ready ? "جاهز" : (e.status || "غير جاهز"));
        }).join(" | ");
      })
      .catch(function () {
        statusEl.textContent = "";
      });
  }

  // Canonical API routes (feature-prefixed)
  var API = {
    asr: {
      transcribe: "/asr/transcribe",
      job: "/asr/job",
      download: "/asr/download",
      enrolledSpeakers: "/asr/enrolled-speakers",
      enrollSpeaker: "/asr/enroll-speaker",
      deleteSpeaker: "/asr/delete-speaker",
      speakerFiles: "/asr/speaker-files",
      speakerFile: "/asr/speaker-file",
      liveStart: "/asr/live/start",
      liveChunk: "/asr/live/chunk",
      liveFinalize: "/asr/live/finalize",
      liveSaveAudio: "/asr/live/save-audio",
      liveSession: "/asr/live/session",
      liveWarmup: "/asr/live/warmup",
    },
    nlp: {
      summarize: "/nlp/summarize",
    },
    tts: {
      root: "/tts",
      voices: "/tts/voices",
      voiceSamples: "/tts/voice-samples",
      voiceSample: "/tts/voice-sample",
      voiceFile: "/tts/voice-file",
      suggestDialect: "/tts/suggest-dialect",
      inspectVoice: "/tts/voice-sample/inspect",
      transcribeRef: "/tts/voice-sample/transcribe-ref",
    },
    download: "/download",
  };

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
    var prev = (qs(".src-btn.active") && qs(".src-btn.active").dataset.src) || "file";
    if (prev === "mic" && srcName !== "mic" && typeof window._liveAsrDismissIfAny === "function") {
      window._liveAsrDismissIfAny();
    }
    qsa(".src-btn").forEach(function (x) { x.classList.remove("active"); });
    var srcBtn = qs('.src-btn[data-src="' + srcName + '"]');
    if (srcBtn) srcBtn.classList.add("active");
    var micZone = getId("mic-zone"), filesZone = getId("files-zone");
    if (srcName === "file") {
      if (filesZone) filesZone.classList.remove("hidden");
      if (micZone) micZone.classList.add("hidden");
      var batch = getId("asrBatchActions");
      if (batch) batch.classList.remove("hidden");
    } else {
      if (filesZone) filesZone.classList.add("hidden");
      if (micZone) micZone.classList.remove("hidden");
      var batchMic = getId("asrBatchActions");
      if (batchMic) batchMic.classList.add("hidden");
      var filesIn = getId("filesIn");
      if (filesIn) {
        filesIn.value = "";
        updateMultiFilesStatus();
      }
      if (typeof window._liveAsrWarmup === "function") window._liveAsrWarmup();
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
        "apiKey", "timeout", "whisperMode", "enhance", "enhanceLevel", "punctuate", "maxSpeakers", "enrollThreshold",
        "deviceSel", "computeSel", "ttsEngine", "ttsUserEmail", "ttsText", "ttsVoice",
        "ttsSpeed", "ttsSeed", "ttsDialect", "ttsRefText", "ttsVoiceFilesList", "ttsMaxChunk",
        "spkName", "spkList", "spkFilesList",
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
      ["dlLinks", "ttsDl"].forEach(function (id) {
        var el = getId(id);
        if (!el) return;
        // لا نستعيد أزرار تحميل الملخص القديمة — زر اللوحة يكفي
        var tmp = document.createElement("div");
        tmp.innerHTML = html[id] == null ? "" : String(html[id]);
        Array.prototype.slice.call(tmp.querySelectorAll("button")).forEach(function (btn) {
          if ((btn.textContent || "").trim() === "تحميل الملخص") btn.remove();
        });
        el.innerHTML = tmp.innerHTML || "";
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
      if (speedSliderEl) setTtsSpeed(speedSliderEl.value || "1");
      syncTtsChunkLabel();
      updateTtsEngineUi();

      var restoredSummary = getId("outSummary");
      var restoredKeywords = getId("outKeywords");
      setSummaryText(restoredSummary ? restoredSummary.value : "");
      setKeywordsText(restoredKeywords ? restoredKeywords.value : "");
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
  updateTtsEngineUi();
  refreshTtsEngineStatus();

  var ttsEngineEl = getId("ttsEngine");
  if (ttsEngineEl) {
    ttsEngineEl.addEventListener("change", function () {
      updateTtsEngineUi();
      queueUIStateSave();
    });
  }

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
    if (typeof window._liveAsrPurgeBeacon === "function") window._liveAsrPurgeBeacon();
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") saveUIState();
  });

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
        label.textContent = count === 1 ? ("تم اختيار ملف: " + first) : ("تم اختيار " + count + " ملفات");
      }
      if (status) {
        status.textContent = count === 1 ? "جاهز للمعالجة" : ("أول ملف: " + first + " | العدد: " + count);
        status.classList.remove("hidden");
      }
      filesInput.classList.add("selected-files");
      if (clearBtn) clearBtn.classList.remove("hidden");
      return;
    }
    if (label) label.textContent = "اختر ملفًا صوتيًا أو أكثر";
    if (status) {
      status.textContent = "";
      status.classList.add("hidden");
    }
    filesInput.classList.remove("selected-files");
    if (clearBtn) clearBtn.classList.add("hidden");
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

  function isLoggedIn() {
    return !!(session && session.token && session.email);
  }

  function requireLogin(message) {
    if (isLoggedIn()) return true;
    if (message) alert(message);
    return false;
  }

  var PROTECTED_CONTROL_IDS = [
    "btnSend", "btnSummary", "micBtn", "btnTts", "btnEnroll", "spkMicBtn",
    "btnRefreshSpeakers", "btnDeleteSpeaker", "btnTtsUploadVoices",
    "btnTtsRefreshVoices", "btnTtsDeleteVoice", "filesIn",
    "btnLiveSaveAudio", "btnLiveDismissAudio"
  ];

  function syncAuthGates() {
    var loggedIn = isLoggedIn();
    var banner = getId("loginGateBanner");
    if (banner) banner.classList.toggle("hidden", loggedIn);
    PROTECTED_CONTROL_IDS.forEach(function (id) {
      var el = getId(id);
      if (el) el.disabled = !loggedIn;
    });
    if (!loggedIn) {
      if (pendingPollTimers.transcribe) clearPendingJob("transcribe");
      if (pendingPollTimers.summary) clearPendingJob("summary");
    } else {
      refreshTtsVoiceSamples();
    }
  }

  function revokeBlobSrc(el) {
    if (!el || !el.src) return;
    try {
      if (String(el.src).indexOf("blob:") === 0) URL.revokeObjectURL(el.src);
    } catch (_) {}
  }

  function normalizeApiUrl(url) {
    if (!url) return url;
    var raw = String(url).trim();
    if (!raw) return raw;
    if (raw.charAt(0) === "/" && raw.charAt(1) !== "/") return raw;
    try {
      var parsed = new URL(raw, window.location.origin);
      return parsed.pathname + parsed.search + (parsed.hash || "");
    } catch (_) {
      return raw;
    }
  }

  function loadAuthenticatedMedia(url, fallbackName) {
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    return fetchWithTimeout(normalizeApiUrl(url), { method: "GET", headers: getHeaders() }, timeout)
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error(j.detail || j.error || r.statusText);
          });
        }
        var dispo = r.headers.get("Content-Disposition") || "";
        var match = /filename="?([^";]+)"?/i.exec(dispo);
        return r.blob().then(function (blob) {
          return {
            blob: blob,
            objectUrl: URL.createObjectURL(blob),
            filename: (match && match[1]) || fallbackName || "download",
          };
        });
      });
  }

  function triggerAuthenticatedDownload(url, fallbackName) {
    if (!requireLogin(ACCOUNT_MESSAGES.needLoginFirst)) return;
    loadAuthenticatedMedia(url, fallbackName)
      .then(function (res) {
        var a = document.createElement("a");
        a.href = res.objectUrl;
        a.download = res.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(res.objectUrl); }, 0);
      })
      .catch(function (e) {
        alert("فشل التحميل: " + (e.message || String(e)));
      });
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
    if (typeof updateTtsEngineUi === "function") updateTtsEngineUi();
    syncAuthGates();
    queueUIStateSave();
    if (session.token && session.email && typeof window._liveAsrWarmup === "function") {
      window._liveAsrWarmup();
    }
  }

  function setText(id, text) {
    var el = getId(id);
    if (el) el.textContent = text || "";
    queueUIStateSave();
  }

  function jsonRequest(url, method, body, timeoutSec) {
    var headers = getHeaders();
    headers["Content-Type"] = "application/json";
    var effectiveTimeout = (timeoutSec == null || timeoutSec === "") ? (getId("timeout") ? getId("timeout").value : 300) : timeoutSec;
    return fetchWithTimeout(url, {
      method: method,
      headers: headers,
      body: body ? JSON.stringify(body) : undefined,
    }, effectiveTimeout)
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
    // 0 means unlimited timeout (no client-side abort).
    if (isFinite(parsed) && parsed === 0) return 0;
    if (!isFinite(parsed) || parsed < 0) parsed = parseInt(fallbackSec, 10);
    if (!isFinite(parsed) || parsed <= 0) parsed = 900;
    return parsed;
  }

  function fetchWithTimeout(url, opts, timeoutMs) {
    var sec = resolveTimeoutSeconds(timeoutMs, 900);
    opts = opts || {};
    var ctrl = null;
    var id = null;
    if (sec > 0) {
      var t = Math.max(60000, sec * 1000);
      ctrl = new AbortController();
      id = setTimeout(function () { ctrl.abort(); }, t);
      opts.signal = ctrl.signal;
    }
    return fetch(url, opts).then(function (r) {
      if (id) clearTimeout(id);
      return r;
    }, function (e) {
      if (id) clearTimeout(id);
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
    if (urls.txt || urls.srt || urls.vtt || urls.summary || urls.segments || urls.wav) return urls;
    var out = {};
    if (data && data.txt_path) out.txt = API.asr.download + "?path=" + encodeURIComponent(data.txt_path);
    if (data && data.srt_path) out.srt = API.asr.download + "?path=" + encodeURIComponent(data.srt_path);
    if (data && data.vtt_path) out.vtt = API.asr.download + "?path=" + encodeURIComponent(data.vtt_path);
    if (data && data.summary_path) out.summary = API.asr.download + "?path=" + encodeURIComponent(data.summary_path);
    if (data && data.segments_path) out.segments = API.asr.download + "?path=" + encodeURIComponent(data.segments_path);
    if (data && data.wav_path) out.wav = API.asr.download + "?path=" + encodeURIComponent(data.wav_path);
    return out;
  }

  function renderDownloadLinks(urls, clearFirst) {
    var links = getId("dlLinks");
    if (!links) return;
    if (clearFirst) links.innerHTML = "";
    urls = urls || {};
    function addBtn(url, label, fallbackName) {
      if (!url) return;
      // تجنّب تكرار نفس الزر عند استدعاءات متتالية بدون clearFirst
      var existing = links.querySelectorAll("button");
      for (var i = 0; i < existing.length; i++) {
        if ((existing[i].textContent || "").trim() === label) return;
      }
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-secondary";
      btn.textContent = label;
      btn.addEventListener("click", function () {
        triggerAuthenticatedDownload(url, fallbackName);
      });
      links.appendChild(btn);
      links.appendChild(document.createTextNode(" "));
    }
    addBtn(urls.txt, "تحميل TXT", "transcript.txt");
    addBtn(urls.srt, "تحميل SRT", "transcript.srt");
    addBtn(urls.vtt, "تحميل VTT", "transcript.vtt");
    addBtn(urls.segments, "تحميل segments", "segments.json");
    addBtn(urls.wav, "تحميل WAV", "recording.wav");
    // زر تحميل الملخص موجود داخل لوحة المحضر — لا نكرره هنا
  }

  function applyTranscribeResult(data) {
    getId("outText").value = data.text || "";
    setSummaryText(data.summary || "");
    setKeywordsText(data.keywords || "");
    var segs = data.segments || [];
    if (getId("outSegments")) getId("outSegments").textContent = segText(segs);
    renderDownloadLinks(buildDownloadUrls(data), true);
    queueUIStateSave();
  }

  function applySummaryResult(data) {
    setSummaryText(data.summary || "");
    setKeywordsText(data.keywords || "");
    renderDownloadLinks(buildDownloadUrls(data), false);
    queueUIStateSave();
  }

  var ASR_MESSAGES = {
    processingBg: "المعالجة مستمرة...",
    jobFailed: "فشل تنفيذ المهمة.",
    errorPrefix: "خطأ: ",
    restoreTranscribe: "تمت استعادة مهمة التحويل بعد التحديث...",
    loadingDefault: "جاري التحويل...",
    loadingMic: "جاري تحويل التسجيل...",
    loadingFiles: "جاري تحويل الملفات...",
    queuedTranscribe: "تم إرسال مهمة التحويل للخلفية. يمكنك تحديث الصفحة ولن تنقطع العملية.",
    errNeedMic: "يرجى تسجيل صوت أولًا.",
    errNeedInput: "يرجى اختيار ملف/ملفات صوتية، أو التسجيل من الميكروفون.",
    errMicUseLive: "مصدر الميكروفون يحوّل مباشرة أثناء التسجيل. اضغط «بدء التسجيل» ثم أوقف عند الانتهاء.",
    sending: "جاري الإرسال...",
    micReady: "جاهز للتسجيل — التحويل يظهر أثناء الكلام",
    micLive: "جارٍ التفريغ…",
    micFinalizing: "جاري إنهاء التفريغ...",
    micDiarizing: "جاري تمييز المتكلمين وإنهاء التفريغ...",
    micDone: "انتهى التسجيل. استمع للمعاينة ثم احفظ أو تجاهل.",
    micUnsupported: "هذا المتصفح لا يدعم التسجيل من الميكروفون.",
    micRecording: "جاري التسجيل شبه-الحي... اضغط «إيقاف التسجيل» عند الانتهاء.",
    micAccessFailed: "فشل الوصول للميكروفون: ",
    liveSaveOk: "تم حفظ الصوت على الخادم.",
    liveDismissed: "تم تجاهل الصوت (حُذف من الخادم ولم يُحفظ).",
    liveNeedLogin: "يلزم تسجيل الدخول للتسجيل شبه-الحي.",
    liveStartFailed: "فشل بدء جلسة التسجيل الحي: ",
    liveChunkFailed: "تعذّر تحديث النص الحي: ",
    liveSaveFailed: "فشل حفظ الصوت: ",
    liveWarming: "جاري تجهيز نموذج التفريغ…",
    liveWarmOk: "جاهز للتسجيل — التحويل يظهر أثناء الكلام",
    liveSoftStop: "توقف التسجيل بسبب انقطاع الشبكة. النص الظاهر محفوظ محلياً — يمكنك الحفظ أو التجاهل بعد إنهاء الجلسة إن وُجدت.",
    liveRetrying: "جارٍ إعادة المحاولة…",
  };

  var SUMMARY_MESSAGES = {
    needText: "أدخل نصًا أولًا أو قم بالتحويل الصوتي.",
    loading: "جاري التلخيص بـ Jais-2…",
    busy: "جاري التلخيص...",
    queued: "تم إرسال التلخيص للخلفية. يمكنك تحديث الصفحة ولن تنقطع العملية.",
    bgProcessing: "التلخيص مستمر...",
    restore: "تمت استعادة مهمة التلخيص بعد التحديث...",
    errorPrefix: "خطأ: "
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatInlineMarkdown(escapedLine) {
    return escapedLine
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|\s)\*(?!\s)(.+?)(?!\s)\*(?=\s|$|[.,،])/g, "$1<em>$2</em>");
  }

  function renderSummaryHtml(text) {
    var raw = String(text || "").trim();
    if (!raw) return "";
    // أزل التكرار الحرفي لنفس الفقرة (يحصل أحياناً عند النسخ/الاستعادة)
    var chunks = raw.split(/\n{2,}/).map(function (c) { return c.trim(); }).filter(Boolean);
    var deduped = [];
    chunks.forEach(function (c) {
      if (!deduped.length || deduped[deduped.length - 1] !== c) deduped.push(c);
    });
    raw = deduped.join("\n\n");

    var lines = raw.split(/\r?\n/);
    var html = [];
    var inList = false;
    var lastPara = "";

    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }

    lines.forEach(function (line) {
      var trimmed = line.trim();
      if (!trimmed) {
        closeList();
        return;
      }
      var heading = trimmed.match(/^\*\*(.+?)\*\*:?\s*$/) || trimmed.match(/^#{1,3}\s+(.+)$/);
      if (heading) {
        closeList();
        lastPara = "";
        html.push('<div class="sum-section"><h5 class="sum-heading">' + escapeHtml(heading[1].replace(/:$/, "")) + "</h5></div>");
        return;
      }
      var bullet = trimmed.match(/^([*•\-–]|\d+[.)])\s+(.+)$/);
      if (bullet) {
        if (!inList) {
          html.push('<ul class="sum-list">');
          inList = true;
        }
        html.push("<li>" + formatInlineMarkdown(escapeHtml(bullet[2])) + "</li>");
        lastPara = "";
        return;
      }
      closeList();
      if (trimmed === lastPara) return;
      lastPara = trimmed;
      html.push('<p class="sum-p">' + formatInlineMarkdown(escapeHtml(trimmed)) + "</p>");
    });
    closeList();
    return html.join("");
  }

  function updateSummaryDownloadBtn() {
    var btn = getId("btnDownloadSummary");
    if (!btn) return;
    var text = (getId("outSummary") && getId("outSummary").value || "").trim();
    var isStatusOnly = !!(getId("summaryStatus") && !getId("summaryStatus").classList.contains("hidden"));
    btn.disabled = !text || isStatusOnly;
  }

  function renderSummaryView(text) {
    var view = getId("summaryView");
    if (!view) return;
    var html = renderSummaryHtml(text);
    if (!html) {
      view.innerHTML = "";
      view.classList.add("is-empty");
    } else {
      view.innerHTML = html;
      view.classList.remove("is-empty");
    }
  }

  function renderKeywordChips(keywords) {
    var wrap = getId("keywordsChips");
    var block = document.querySelector(".keywords-block");
    var hidden = getId("outKeywords");
    var raw = keywords == null ? "" : String(keywords);
    if (hidden) hidden.value = raw;
    if (!wrap) return;
    wrap.innerHTML = "";
    var stop = {
      هو: 1, هي: 1, ان: 1, بانه: 1, اليوم: 1, كلام: 1, موضوعنا: 1,
      بتحويل: 1, اللي: 1, الي: 1, هذا: 1, هذه: 1, على: 1, من: 1, في: 1,
      مع: 1, عن: 1, ما: 1, لا: 1, لم: 1, إن: 1, أن: 1, نبدا: 1, سنبدا: 1,
      بسم: 1, الله: 1, الرحمن: 1, الرحيم: 1, الاساسي: 1, البرنامج: 1,
      تفريغه: 1, نريد: 1, الناس: 1, ناس: 1, يجب: 1, جميع: 1, تسجيل: 1,
      اختبار: 1, تفريغ: 1, تلخيص: 1, سيرفر: 1, السيرفر: 1, ادخال: 1,
      اخري: 1, اخرى: 1, والاخري: 1, واختبار: 1, بالتسجيل: 1, وادخال: 1
    };
    function stripClitics(kw) {
      var n = String(kw || "");
      if (n.charAt(0) === "و" && n.length > 4) n = n.slice(1);
      if (n.indexOf("بال") === 0 && n.length > 5) return n.slice(3);
      if (n.indexOf("ال") === 0 && n.length > 4) n = n.slice(2);
      return n;
    }
    var chips = String(raw)
      .split(/[,،]/)
      .map(function (part) { return part.trim(); })
      .map(stripClitics)
      .filter(function (kw) { return kw && kw.length >= 4 && !stop[kw]; });
    // أزل التكرار بعد التطبيع
    chips = chips.filter(function (kw, i) { return chips.indexOf(kw) === i; });
    chips.forEach(function (kw) {
      var chip = document.createElement("span");
      chip.className = "keyword-chip";
      chip.textContent = kw;
      wrap.appendChild(chip);
    });
    if (block) block.classList.toggle("hidden", chips.length < 3);
  }

  function setSummaryText(text, opts) {
    opts = opts || {};
    var raw = text == null ? "" : String(text);
    var el = getId("outSummary");
    if (el) el.value = raw;
    var statusEl = getId("summaryStatus");
    if (statusEl) {
      if (opts.isStatus) {
        statusEl.textContent = raw;
        statusEl.classList.remove("hidden");
        statusEl.classList.toggle("is-error", !!opts.isError);
        statusEl.classList.toggle("is-busy", !!opts.isBusy);
        renderSummaryView("");
      } else {
        statusEl.textContent = "";
        statusEl.classList.add("hidden");
        statusEl.classList.remove("is-error", "is-busy");
        renderSummaryView(raw);
      }
    } else {
      renderSummaryView(opts.isStatus ? "" : raw);
    }
    updateSummaryDownloadBtn();
  }

  function setKeywordsText(keywords) {
    renderKeywordChips(keywords || "");
  }

  function formatJobStatusLabel(status) {
    var value = String(status || "").toLowerCase();
    if (value === "queued") return "قيد الانتظار";
    if (value === "running") return "قيد المعالجة";
    if (value === "done") return "مكتمل";
    if (value === "failed") return "فشل";
    return value || "-";
  }

  var TTS_MESSAGES = {
    needUserLogin: "أدخل بريد المستخدم أو سجّل الدخول أولاً.",
    needUser: "أدخل بريد المستخدم أولًا.",
    needVoiceFiles: "اختر ملفًا واحدًا أو أكثر.",
    uploadingVoices: "جاري رفع البصمات...",
    loadedVoicesPrefix: "تم تحميل ",
    loadedVoicesSuffix: " بصمة.",
    uploadedFilesPrefix: "تم رفع ",
    uploadedFilesSuffix: " ملف.",
    needVoiceSelection: "حدّد البريد وملف البصمة أولًا.",
    deletedVoicePrefix: "تم حذف البصمة: ",
    needTtsText: "أدخل نصًا أولًا.",
    generating: "جاري توليد الصوت...",
    errorPrefix: "خطأ: "
  };

  var SPEAKERS_MESSAGES = {
    needName: "الرجاء إدخال اسم المتكلم.",
    needAudioSample: "الرجاء رفع ملفات صوتية أو تسجيل مقطع.",
    enrolling: "جاري التسجيل...",
    enrollBusy: "جاري التسجيل...",
    enrolled: "تم التسجيل.",
    warningSuffix: " (تحذير)",
    errorPrefix: "خطأ: ",
    micStopped: "تم إيقاف التسجيل. يمكنك تسجيل البصمة.",
    micUnsupported: "المتصفح لا يدعم الميكروفون.",
    micRecording: "جاري التسجيل...",
    micAccessFailed: "فشل الوصول للميكروفون: ",
    needSelectedSpeaker: "الرجاء تحديد متحدث من القائمة.",
    deleted: "تم الحذف."
  };

  var ACCOUNT_MESSAGES = {
    needRegisterFields: "الرجاء إدخال البريد وكلمة المرور والاسم الكامل.",
    registering: "جاري إنشاء الحساب...",
    registerSuccess: "تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن.",
    needLoginFields: "الرجاء إدخال البريد وكلمة المرور.",
    loggingIn: "جاري تسجيل الدخول...",
    loginSuccess: "تم تسجيل الدخول بنجاح.",
    noLoggedInUser: "لا يوجد مستخدم مسجل دخول.",
    logoutSuccess: "تم تسجيل الخروج.",
    needLoginFirst: "الرجاء تسجيل الدخول أولًا.",
    profileLoading: "جاري تحميل الملف...",
    profileLoaded: "تم تحميل الملف الشخصي.",
    profileSaving: "جاري حفظ التعديلات...",
    profileSaved: "تم حفظ الملف الشخصي.",
    dashboardLoading: "جاري تحديث الإحصائيات...",
    dashboardUpdated: "تم تحديث لوحة التحكم.",
    errorPrefix: "خطأ: "
  };

  function normalizeJobPollUrl(url, jobId) {
    if (!jobId) return API.asr.job + "/";
    if (!url) return API.asr.job + "/" + encodeURIComponent(jobId);
    try {
      var parsed = new URL(url, window.location.origin);
      return parsed.pathname + parsed.search;
    } catch (_) {
      if (String(url).charAt(0) === "/") return url;
      return API.asr.job + "/" + encodeURIComponent(jobId);
    }
  }

  function pollJob(kind, info) {
    if (!info || !info.job_id) return;
    if (pendingPollTimers[kind]) clearTimeout(pendingPollTimers[kind]);
    var pollUrl = normalizeJobPollUrl(info.poll_url, info.job_id);
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    var pollFailures = 0;

    var tick = function () {
      fetchWithTimeout(pollUrl, { method: "GET", headers: getHeaders() }, timeout)
        .then(function (r) {
          return r.json().then(function (data) {
            if (!r.ok) throw new Error((data && (data.detail || data.error)) || r.statusText);
            return data;
          });
        })
        .then(function (job) {
          pollFailures = 0;
          var status = (job && job.status) ? String(job.status).toLowerCase() : "";
          if (status === "queued" || status === "running") {
            if (kind === "transcribe") {
              getId("outText").value = ASR_MESSAGES.processingBg + " (" + formatJobStatusLabel(status) + ")";
            } else if (kind === "summary") {
              setSummaryText(SUMMARY_MESSAGES.bgProcessing + " (" + formatJobStatusLabel(status) + ")", { isStatus: true, isBusy: true });
            }
            queueUIStateSave();
            pendingPollTimers[kind] = setTimeout(tick, 2000);
            return;
          }

          if (status === "done") {
            var result = (job && job.result) ? job.result : {};
            if (kind === "transcribe") {
              if (!(result.text || "").trim() && result.error) {
                getId("outText").value = ASR_MESSAGES.errorPrefix + result.error;
              } else {
                applyTranscribeResult(result);
              }
            }
            if (kind === "summary") applySummaryResult(result);
            clearPendingJob(kind);
            return;
          }

          if (status === "error") {
            var failedMsg = (job && (job.error || job.detail)) || ASR_MESSAGES.jobFailed;
            if (kind === "transcribe") getId("outText").value = ASR_MESSAGES.errorPrefix + failedMsg;
            if (kind === "summary") setSummaryText(SUMMARY_MESSAGES.errorPrefix + failedMsg, { isStatus: true, isError: true });
            clearPendingJob(kind);
            queueUIStateSave();
            return;
          }

          var errMsg = (job && (job.error || job.detail)) || ASR_MESSAGES.jobFailed;
          if (kind === "transcribe") getId("outText").value = ASR_MESSAGES.errorPrefix + errMsg;
          if (kind === "summary") setSummaryText(SUMMARY_MESSAGES.errorPrefix + errMsg, { isStatus: true, isError: true });
          clearPendingJob(kind);
          queueUIStateSave();
        })
        .catch(function (e) {
          pollFailures += 1;
          if (pollFailures >= 12) {
            var failMsg = (e && e.message) ? e.message : ASR_MESSAGES.jobFailed;
            if (kind === "transcribe") getId("outText").value = ASR_MESSAGES.errorPrefix + failMsg;
            if (kind === "summary") setSummaryText(SUMMARY_MESSAGES.errorPrefix + failMsg, { isStatus: true, isError: true });
            clearPendingJob(kind);
            queueUIStateSave();
            return;
          }
          pendingPollTimers[kind] = setTimeout(tick, 2500);
        });
    };

    tick();
  }

  function resumePendingJobs() {
    if (!isLoggedIn()) return;
    var jobs = getPendingJobs();
    if (jobs.transcribe && jobs.transcribe.job_id) {
      getId("outText").value = ASR_MESSAGES.restoreTranscribe;
      pollJob("transcribe", jobs.transcribe);
    }
    if (jobs.summary && jobs.summary.job_id) {
      setSummaryText(SUMMARY_MESSAGES.restore, { isStatus: true, isBusy: true });
      pollJob("summary", jobs.summary);
    }
    queueUIStateSave();
  }

  function appendTranscribeOptions(fd) {
    var whisperModeEl = getId("whisperMode");
    var enhanceEl = getId("enhance");
    var enhanceLevelEl = getId("enhanceLevel");
    fd.append("model_name", "heavy");
    fd.append("whisper_mode", whisperModeEl ? whisperModeEl.value : "normal");
    fd.append("enhance", (enhanceEl && enhanceEl.value !== "off") ? "true" : "false");
    fd.append("enhance_mode", enhanceEl ? (enhanceEl.value || "off") : "off");
    fd.append("enhance_level", enhanceLevelEl ? enhanceLevelEl.value : "medium");
    fd.append("punctuate", (getId("punctuate") && getId("punctuate").checked) ? "true" : "false");
    fd.append("diarize", getId("diarize").checked ? "true" : "false");
    fd.append("auto_k", getId("autoK").checked ? "true" : "false");
    fd.append("max_speakers", getId("maxSpeakers") ? getId("maxSpeakers").value : "2");
    fd.append("enroll_threshold", getId("enrollThreshold") ? getId("enrollThreshold").value : "0.65");
    fd.append("device_sel", getId("deviceSel") ? getId("deviceSel").value : "auto");
    fd.append("compute_sel", getId("computeSel") ? getId("computeSel").value : "auto");
    fd.append("async_mode", "true");
    fd.append("user_email", session.email);
  }

  function sendTranscribeRequest(fd) {
    if (!requireLogin(ACCOUNT_MESSAGES.needLoginFirst)) {
      getId("outText").value = ACCOUNT_MESSAGES.needLoginFirst;
      return Promise.resolve();
    }
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    return fetchWithTimeout(API.asr.transcribe, {
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
            poll_url: normalizeJobPollUrl(data.poll_url, data.job_id),
          });
          getId("outText").value = ASR_MESSAGES.processingBg + " (" + formatJobStatusLabel(data.status) + ")";
          queueUIStateSave();
          pollJob("transcribe", getPendingJobs().transcribe);
          return;
        }
        applyTranscribeResult(data || {});
      })
      .catch(function (e) {
        getId("outText").value = ASR_MESSAGES.errorPrefix + (e.message || String(e));
      });
  }

  function resetTranscribeOutput(loadingText) {
    getId("outText").value = loadingText || ASR_MESSAGES.loadingDefault;
    setSummaryText("");
    setKeywordsText("");
    getId("dlLinks").innerHTML = "";
    getId("outSegments").textContent = "";
  }

  function buildTranscribeFormData() {
    var src = qs(".src-btn.active");
    var filesIn = getId("filesIn");
    var fd = new FormData();

    if (src && src.dataset.src === "mic") {
      // Mic uses pseudo-live ASR; no separate batch upload unless a leftover blob exists for advanced re-run.
      return { error: ASR_MESSAGES.errMicUseLive };
    }

    var multiErr = validateAudioFilesList(filesIn && filesIn.files, 1);
    if (!multiErr && filesIn && filesIn.files && filesIn.files.length > 0) {
      for (var i = 0; i < filesIn.files.length; i++) fd.append("files", filesIn.files[i]);
      appendTranscribeOptions(fd);
      return {
        formData: fd,
        loadingText: ASR_MESSAGES.loadingFiles,
      };
    }

    return { error: ASR_MESSAGES.errNeedInput };
  }

  // إرسال (ملف واحد / عدة ملفات / تسجيل)
  getId("btnSend").addEventListener("click", function () {
    var btnSend = getId("btnSend");
    var build = buildTranscribeFormData();
    if (build.error) {
      getId("outText").value = build.error;
      return;
    }
    resetTranscribeOutput(build.loadingText);
    setButtonBusy(btnSend, true, ASR_MESSAGES.sending);

    sendTranscribeRequest(build.formData)
      .finally(function () {
        setButtonBusy(btnSend, false);
      });
  });

  // تلخيص النص
  getId("btnSummary").addEventListener("click", function () {
    if (!requireLogin(ACCOUNT_MESSAGES.needLoginFirst)) {
      setSummaryText(ACCOUNT_MESSAGES.needLoginFirst, { isStatus: true, isError: true });
      return;
    }
    var btnSummary = getId("btnSummary");
    var text = (getId("outText") && getId("outText").value || "").trim();
    if (!text) {
      setSummaryText(SUMMARY_MESSAGES.needText, { isStatus: true, isError: true });
      return;
    }
    var mode = "jais";
    var fd = new FormData();
    fd.append("text", text);
    fd.append("summary_mode", mode);
    fd.append("async_mode", "true");
    fd.append("user_email", session.email);
    setSummaryText(SUMMARY_MESSAGES.loading, { isStatus: true, isBusy: true });
    setButtonBusy(btnSummary, true, SUMMARY_MESSAGES.busy);
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(API.nlp.summarize, { method: "POST", headers: getHeaders(), body: fd }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        if (data && data.job_id && (data.status === "queued" || data.status === "running")) {
          setPendingJob("summary", {
            job_id: data.job_id,
            poll_url: normalizeJobPollUrl(data.poll_url, data.job_id),
          });
          setSummaryText(SUMMARY_MESSAGES.queued, { isStatus: true, isBusy: true });
          queueUIStateSave();
          pollJob("summary", getPendingJobs().summary);
          return;
        }
        applySummaryResult(data || {});
      })
      .catch(function (e) {
        setSummaryText(SUMMARY_MESSAGES.errorPrefix + (e.message || String(e)), { isStatus: true, isError: true });
      })
      .finally(function () {
        setButtonBusy(btnSummary, false);
      });
  });

  var btnDownloadSummary = getId("btnDownloadSummary");
  if (btnDownloadSummary) {
    btnDownloadSummary.addEventListener("click", function () {
      var text = (getId("outSummary") && getId("outSummary").value || "").trim();
      if (!text) return;
      var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "nabra-summary.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
    });
  }

  // تسجيل الميكروفون — شبه-حي (timeslice + /asr/live/*)
  var LIVE_TIMESLICE_MS = 2500;
  var LIVE_CHUNK_FAIL_SOFT_STOP = 3;
  var mediaRecorder = null;
  var recordedChunks = [];
  var liveSessionId = null;
  var liveChunkBusy = false;
  var liveChunkQueued = false;
  var liveStopping = false;
  var livePreviewUrl = null;
  var liveChunkFailStreak = 0;
  var liveLastDurationSec = 0;
  var liveWarmupInFlight = null;
  var liveWarmupDone = false;

  function liveMimeType() {
    if (typeof MediaRecorder === "undefined") return "audio/webm";
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) return "audio/webm;codecs=opus";
    if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
    return "";
  }

  function setMicStatusBusy(busy, text) {
    var status = getId("micStatus");
    if (!status) return;
    if (typeof text === "string") status.textContent = text;
    status.classList.toggle("live-status-busy", !!busy);
  }

  function formatLiveDuration(sec) {
    var s = Math.max(0, Math.round(Number(sec) || 0));
    var m = Math.floor(s / 60);
    var r = s % 60;
    return m + ":" + (r < 10 ? "0" : "") + r;
  }

  function hideLiveAudioBar() {
    var bar = getId("liveAudioBar");
    if (bar) bar.classList.add("hidden");
    var st = getId("liveAudioStatus");
    if (st) st.textContent = "";
    var dur = getId("liveDurationLabel");
    if (dur) dur.textContent = "";
    var audio = getId("livePreviewAudio");
    if (audio) {
      audio.removeAttribute("src");
      audio.load();
    }
    if (livePreviewUrl) {
      try { URL.revokeObjectURL(livePreviewUrl); } catch (e) {}
      livePreviewUrl = null;
    }
  }

  function showLiveAudioBar(blob, durationSec) {
    var bar = getId("liveAudioBar");
    if (!bar) return;
    bar.classList.remove("hidden");
    var audio = getId("livePreviewAudio");
    if (audio && blob) {
      if (livePreviewUrl) {
        try { URL.revokeObjectURL(livePreviewUrl); } catch (e) {}
      }
      livePreviewUrl = URL.createObjectURL(blob);
      audio.src = livePreviewUrl;
    }
    var dur = getId("liveDurationLabel");
    var sec = durationSec != null ? durationSec : liveLastDurationSec;
    if (dur) {
      dur.textContent = sec > 0
        ? ("المدة: " + formatLiveDuration(sec))
        : "";
    }
    var st = getId("liveAudioStatus");
    if (st) st.textContent = "";
  }

  function deleteLiveSession(sid) {
    if (!sid) return Promise.resolve();
    var email = (session && session.email) || "";
    var url = API.asr.liveSession
      + "?session_id=" + encodeURIComponent(sid)
      + "&user_email=" + encodeURIComponent(email);
    return fetch(url, { method: "DELETE", headers: getHeaders(), keepalive: true })
      .catch(function () { /* ignore */ });
  }

  function purgeLiveSessionLocal() {
    var sid = liveSessionId;
    liveSessionId = null;
    liveChunkBusy = false;
    liveChunkQueued = false;
    liveStopping = false;
    liveChunkFailStreak = 0;
    recordedChunks = [];
    window._lastRecordedBlob = null;
    setMicStatusBusy(false);
    hideLiveAudioBar();
    var saveBtn = getId("btnLiveSaveAudio");
    if (saveBtn) {
      saveBtn.disabled = false;
      delete saveBtn.dataset.saved;
    }
    return sid;
  }

  window._liveAsrPurgeBeacon = function () {
    var sid = liveSessionId;
    if (!sid) return;
    var email = (session && session.email) || "";
    var url = API.asr.liveSession
      + "?session_id=" + encodeURIComponent(sid)
      + "&user_email=" + encodeURIComponent(email);
    try {
      fetch(url, { method: "DELETE", headers: getHeaders(), keepalive: true });
    } catch (e) {}
    liveSessionId = null;
  };

  window._liveAsrDismissIfAny = function () {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      try { mediaRecorder.stop(); } catch (e) {}
    }
    var sid = purgeLiveSessionLocal();
    var btn = getId("micBtn");
    if (btn) {
      btn.textContent = "بدء التسجيل";
      btn.classList.add("btn-primary");
      btn.classList.remove("btn-secondary");
    }
    setMicStatusBusy(false, ASR_MESSAGES.micReady);
    if (sid) deleteLiveSession(sid);
  };

  window._liveAsrWarmup = function () {
    if (!isLoggedIn() || liveWarmupDone) return liveWarmupInFlight || Promise.resolve();
    if (liveWarmupInFlight) return liveWarmupInFlight;
    var fd = new FormData();
    fd.append("user_email", session.email || "");
    var deviceEl = getId("deviceSel");
    var computeEl = getId("computeSel");
    var deviceVal = deviceEl ? deviceEl.value : "auto";
    var computeVal = computeEl ? computeEl.value : "auto";
    if (deviceVal && deviceVal !== "auto") fd.append("device", deviceVal);
    if (computeVal && computeVal !== "auto") fd.append("compute", computeVal);
    var src = qs(".src-btn.active");
    var onMic = src && src.dataset.src === "mic";
    if (onMic) setMicStatusBusy(true, ASR_MESSAGES.liveWarming);
    liveWarmupInFlight = fetchWithTimeout(API.asr.liveWarmup, {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    }, 180)
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText || "warmup failed");
        return r.json();
      })
      .then(function () {
        liveWarmupDone = true;
        if (onMic && !(mediaRecorder && mediaRecorder.state === "recording")) {
          setMicStatusBusy(false, ASR_MESSAGES.liveWarmOk);
        }
      })
      .catch(function () {
        if (onMic && !(mediaRecorder && mediaRecorder.state === "recording")) {
          setMicStatusBusy(false, ASR_MESSAGES.micReady);
        }
      })
      .finally(function () {
        liveWarmupInFlight = null;
      });
    return liveWarmupInFlight;
  };

  function liveCumulativeBlob() {
    var mime = liveMimeType() || "audio/webm";
    return new Blob(recordedChunks, { type: mime.split(";")[0] || "audio/webm" });
  }

  function softStopLiveRecording(reasonText) {
    liveStopping = true;
    liveChunkQueued = false;
    var btn = getId("micBtn");
    if (mediaRecorder && mediaRecorder.state === "recording") {
      try { mediaRecorder.stop(); } catch (e) {}
    }
    if (btn) {
      btn.textContent = "بدء التسجيل";
      btn.classList.add("btn-primary");
      btn.classList.remove("btn-secondary");
    }
    setMicStatusBusy(false, reasonText || ASR_MESSAGES.liveSoftStop);
    var st = getId("liveAudioStatus");
    if (st) st.textContent = reasonText || ASR_MESSAGES.liveSoftStop;
  }

  function postLiveChunkOnce(blob, isRetry) {
    var fd = new FormData();
    fd.append("session_id", liveSessionId);
    fd.append("user_email", session.email || "");
    fd.append("audio", blob, "live.webm");
    if (isRetry) setMicStatusBusy(true, ASR_MESSAGES.liveRetrying);
    else setMicStatusBusy(true, ASR_MESSAGES.micLive);
    return fetchWithTimeout(API.asr.liveChunk, {
      method: "POST",
      headers: getHeaders(),
      body: fd,
    }, 120)
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (j) {
            throw new Error(j.detail || j.error || r.statusText);
          }).catch(function (e) {
            if (e && e.message) throw e;
            throw new Error(r.statusText || "chunk failed");
          });
        }
        return r.json();
      });
  }

  function postLiveChunk() {
    // Only one in-flight request; when busy, mark that the latest blob should run next.
    if (!liveSessionId || liveStopping) return Promise.resolve();
    if (liveChunkBusy) {
      liveChunkQueued = true;
      return Promise.resolve();
    }
    if (!recordedChunks.length) return Promise.resolve();
    liveChunkBusy = true;
    liveChunkQueued = false;
    var blob = liveCumulativeBlob();
    if (!blob.size) {
      liveChunkBusy = false;
      return Promise.resolve();
    }

    return postLiveChunkOnce(blob, false)
      .catch(function (e) {
        if (liveStopping || !liveSessionId) throw e;
        var retryBlob = liveCumulativeBlob();
        if (!retryBlob.size) throw e;
        return postLiveChunkOnce(retryBlob, true);
      })
      .then(function (data) {
        liveChunkFailStreak = 0;
        if (data && typeof data.text === "string") {
          getId("outText").value = data.text;
        }
        if (data && data.duration_sec != null) liveLastDurationSec = Number(data.duration_sec) || liveLastDurationSec;
        if (!liveStopping) setMicStatusBusy(true, ASR_MESSAGES.micLive);
      })
      .catch(function (e) {
        liveChunkFailStreak += 1;
        setMicStatusBusy(false, ASR_MESSAGES.liveChunkFailed + (e.message || String(e)));
        if (liveChunkFailStreak >= LIVE_CHUNK_FAIL_SOFT_STOP) {
          softStopLiveRecording(ASR_MESSAGES.liveSoftStop);
        }
      })
      .finally(function () {
        liveChunkBusy = false;
        if (liveChunkQueued && !liveStopping && liveSessionId) {
          postLiveChunk();
        } else if (!liveStopping && mediaRecorder && mediaRecorder.state === "recording") {
          setMicStatusBusy(true, ASR_MESSAGES.micRecording);
        } else if (!liveStopping) {
          setMicStatusBusy(false);
        }
      });
  }

  function finalizeLiveSession(blob) {
    if (!liveSessionId) {
      setMicStatusBusy(false, ASR_MESSAGES.micReady);
      return Promise.resolve();
    }
    var wantDiarize = getId("diarize") ? !!getId("diarize").checked : true;
    setMicStatusBusy(true, wantDiarize ? ASR_MESSAGES.micDiarizing : ASR_MESSAGES.micFinalizing);
    var sid = liveSessionId;
    var chain = Promise.resolve();
    if (blob && blob.size) {
      var fdChunk = new FormData();
      fdChunk.append("session_id", sid);
      fdChunk.append("user_email", session.email || "");
      fdChunk.append("audio", blob, "live.webm");
      chain = fetchWithTimeout(API.asr.liveChunk, {
        method: "POST",
        headers: getHeaders(),
        body: fdChunk,
      }, 180).then(function (r) {
        if (!r.ok) return null;
        return r.json().catch(function () { return null; });
      }).then(function (data) {
        if (data && typeof data.text === "string") getId("outText").value = data.text;
        if (data && data.duration_sec != null) liveLastDurationSec = Number(data.duration_sec) || liveLastDurationSec;
      }).catch(function () { /* finalize still runs */ });
    }
    return chain.then(function () {
      var fd = new FormData();
      fd.append("session_id", sid);
      fd.append("user_email", session.email || "");
      fd.append("diarize", wantDiarize ? "true" : "false");
      fd.append("auto_k", getId("autoK") && getId("autoK").checked ? "true" : "false");
      fd.append("max_speakers", getId("maxSpeakers") ? getId("maxSpeakers").value : "2");
      fd.append("enroll_threshold", getId("enrollThreshold") ? getId("enrollThreshold").value : "0.65");
      var timeoutEl = getId("timeout");
      var finTimeout = timeoutEl ? Number(timeoutEl.value) : 900;
      if (!isFinite(finTimeout) || finTimeout < 0) finTimeout = 900;
      if (finTimeout === 0) finTimeout = 3600;
      finTimeout = Math.max(finTimeout, wantDiarize ? 300 : 120);
      return fetchWithTimeout(API.asr.liveFinalize, {
        method: "POST",
        headers: getHeaders(),
        body: fd,
      }, finTimeout);
    }).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (j) {
          throw new Error(j.detail || j.error || r.statusText);
        });
      }
      return r.json();
    }).then(function (data) {
      if (data && typeof data.text === "string") getId("outText").value = data.text;
      if (data && data.duration_sec != null) liveLastDurationSec = Number(data.duration_sec) || liveLastDurationSec;
      if (data && Array.isArray(data.segments) && data.segments.length && getId("outSegments")) {
        getId("outSegments").textContent = segText(data.segments);
      }
      window._lastRecordedBlob = blob || null;
      showLiveAudioBar(blob, liveLastDurationSec);
      setMicStatusBusy(false, ASR_MESSAGES.micDone);
    }).catch(function (e) {
      setMicStatusBusy(false, ASR_MESSAGES.errorPrefix + (e.message || String(e)));
      showLiveAudioBar(blob, liveLastDurationSec);
    });
  }

  getId("micBtn").addEventListener("click", function () {
    var btn = getId("micBtn");
    if (mediaRecorder && mediaRecorder.state === "recording") {
      liveStopping = true;
      liveChunkQueued = false;
      mediaRecorder.stop();
      btn.textContent = "بدء التسجيل";
      btn.classList.add("btn-primary");
      btn.classList.remove("btn-secondary");
      var wantDiarizeStop = getId("diarize") ? !!getId("diarize").checked : true;
      setMicStatusBusy(true, wantDiarizeStop ? ASR_MESSAGES.micDiarizing : ASR_MESSAGES.micFinalizing);
      return;
    }
    if (!requireLogin(ASR_MESSAGES.liveNeedLogin)) {
      setMicStatusBusy(false, ASR_MESSAGES.liveNeedLogin);
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
      setMicStatusBusy(false, ASR_MESSAGES.micUnsupported);
      return;
    }

    var prevSid = purgeLiveSessionLocal();
    if (prevSid) deleteLiveSession(prevSid);

    var mime = liveMimeType();
    window._liveAsrWarmup();
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        var fd = new FormData();
        fd.append("user_email", session.email || "");
        var whisperModeEl = getId("whisperMode");
        var deviceEl = getId("deviceSel");
        var computeEl = getId("computeSel");
        fd.append("whisper_mode", whisperModeEl ? whisperModeEl.value : "normal");
        var deviceVal = deviceEl ? deviceEl.value : "auto";
        var computeVal = computeEl ? computeEl.value : "auto";
        if (deviceVal && deviceVal !== "auto") fd.append("device", deviceVal);
        if (computeVal && computeVal !== "auto") fd.append("compute", computeVal);
        return fetchWithTimeout(API.asr.liveStart, {
          method: "POST",
          headers: getHeaders(),
          body: fd,
        }, 30).then(function (r) {
          if (!r.ok) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            return r.json().then(function (j) {
              throw new Error(j.detail || j.error || r.statusText);
            });
          }
          return r.json().then(function (data) {
            return { stream: stream, data: data };
          });
        });
      })
      .then(function (pack) {
        var stream = pack.stream;
        liveSessionId = pack.data && pack.data.session_id;
        if (!liveSessionId) {
          stream.getTracks().forEach(function (t) { t.stop(); });
          throw new Error("missing session_id");
        }
        recordedChunks = [];
        liveStopping = false;
        liveChunkFailStreak = 0;
        liveLastDurationSec = 0;
        hideLiveAudioBar();
        getId("outText").value = "";
        setSummaryText("");
        setKeywordsText("");
        getId("dlLinks").innerHTML = "";
        getId("outSegments").textContent = "";

        var opts = mime ? { mimeType: mime } : undefined;
        try {
          mediaRecorder = opts ? new MediaRecorder(stream, opts) : new MediaRecorder(stream);
        } catch (e) {
          mediaRecorder = new MediaRecorder(stream);
        }
        mediaRecorder.ondataavailable = function (e) {
          if (e.data && e.data.size) recordedChunks.push(e.data);
          // Throttle: skip starting a new upload while one is in flight; queue latest only.
          if (!liveStopping) postLiveChunk();
        };
        mediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          var blob = liveCumulativeBlob();
          window._lastRecordedBlob = blob;
          var waitBusy = function (n) {
            if (!liveChunkBusy || n <= 0) return finalizeLiveSession(blob);
            return new Promise(function (resolve) {
              setTimeout(function () { resolve(waitBusy(n - 1)); }, 200);
            });
          };
          waitBusy(25);
        };
        mediaRecorder.start(LIVE_TIMESLICE_MS);
        btn.textContent = "إيقاف التسجيل";
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
        setMicStatusBusy(true, ASR_MESSAGES.micRecording);
      })
      .catch(function (e) {
        liveSessionId = null;
        var msg = ASR_MESSAGES.micAccessFailed + (e.message || String(e));
        if (String(e.message || "").indexOf("session") >= 0 || String(e.message || "").indexOf("live") >= 0) {
          msg = ASR_MESSAGES.liveStartFailed + (e.message || String(e));
        }
        setMicStatusBusy(false, msg);
      });
  });

  var btnLiveSave = getId("btnLiveSaveAudio");
  if (btnLiveSave) {
    btnLiveSave.addEventListener("click", function () {
      if (!liveSessionId) return;
      if (!requireLogin(ASR_MESSAGES.liveNeedLogin)) return;
      var st = getId("liveAudioStatus");
      setButtonBusy(btnLiveSave, true, "جاري الحفظ...");
      var fd = new FormData();
      fd.append("session_id", liveSessionId);
      fd.append("user_email", session.email || "");
      fetchWithTimeout(API.asr.liveSaveAudio, {
        method: "POST",
        headers: getHeaders(),
        body: fd,
      }, 60)
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (j) {
              throw new Error(j.detail || j.error || r.statusText);
            });
          }
          return r.json();
        })
        .then(function (data) {
          if (st) st.textContent = ASR_MESSAGES.liveSaveOk;
          if (data && data.download_url) {
            var links = getId("dlLinks");
            if (links) {
              var a = document.createElement("a");
              a.href = data.download_url;
              a.textContent = "تحميل التسجيل المحفوظ";
              a.target = "_blank";
              a.rel = "noopener";
              links.appendChild(a);
            }
          }
          setMicStatusBusy(false, ASR_MESSAGES.liveSaveOk);
          btnLiveSave.dataset.saved = "1";
        })
        .catch(function (e) {
          if (st) st.textContent = ASR_MESSAGES.liveSaveFailed + (e.message || String(e));
        })
        .finally(function () {
          setButtonBusy(btnLiveSave, false);
          if (btnLiveSave.dataset.saved === "1") btnLiveSave.disabled = true;
        });
    });
  }

  var btnLiveDismiss = getId("btnLiveDismissAudio");
  if (btnLiveDismiss) {
    btnLiveDismiss.addEventListener("click", function () {
      var sid = purgeLiveSessionLocal();
      if (sid) deleteLiveSession(sid);
      setMicStatusBusy(false, ASR_MESSAGES.liveDismissed);
      var saveBtn = getId("btnLiveSaveAudio");
      if (saveBtn) saveBtn.disabled = false;
    });
  }

  // Warm Whisper after restore if already on mic / logged in
  if (isLoggedIn()) {
    var activeSrc = qs(".src-btn.active");
    if (activeSrc && activeSrc.dataset.src === "mic") window._liveAsrWarmup();
  }

  // عرض قيمة السرعة + إعدادات Habibi
  var speedSlider = getId("ttsSpeed");
  if (speedSlider) {
    speedSlider.addEventListener("input", function () {
      setTtsSpeed(speedSlider.value);
    });
    setTtsSpeed(speedSlider.value);
  }
  var chunkSlider = getId("ttsMaxChunk");
  if (chunkSlider) {
    chunkSlider.addEventListener("input", syncTtsChunkLabel);
    syncTtsChunkLabel();
  }
  qsa(".tts-speed-preset").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTtsSpeed(btn.getAttribute("data-speed"));
    });
  });

  // TTS
  function getTtsUserEmail() {
    var ttsUserEmail = (getId("ttsUserEmail") && getId("ttsUserEmail").value || "").trim();
    return ttsUserEmail || session.email || "";
  }

  function getSpeakersUserEmail() {
    return session.email || "";
  }

  function withSpeakersUserQuery(path) {
    var userEmail = getSpeakersUserEmail();
    if (!userEmail) return path;
    var sep = path.indexOf("?") >= 0 ? "&" : "?";
    return path + sep + "user_email=" + encodeURIComponent(userEmail);
  }

  function refreshTtsVoiceSamples() {
    var statusEl = getId("ttsVoiceStatus");
    var listEl = getId("ttsVoiceFilesList");
    var userEmail = getTtsUserEmail();
    if (!listEl) return;
    listEl.innerHTML = '<option value="">— اختر ملف بصمة —</option>';
    if (!userEmail) {
      if (statusEl) statusEl.textContent = TTS_MESSAGES.needUserLogin;
      return;
    }
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(API.tts.voiceSamples + "?user_email=" + encodeURIComponent(userEmail), {
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
          var info = [];
          if (item.size_bytes) info.push(item.size_bytes + " bytes");
          if (item.has_ref_text) info.push("ref_text");
          opt.textContent = name + (info.length ? " (" + info.join(" · ") + ")" : "");
          if (item.ref_text) opt.setAttribute("data-ref-text", item.ref_text);
          if (item.has_ref_text) opt.setAttribute("data-has-ref", "1");
          listEl.appendChild(opt);
        });
        if (statusEl) statusEl.textContent = TTS_MESSAGES.loadedVoicesPrefix + files.length + TTS_MESSAGES.loadedVoicesSuffix;
        if (listEl.value) inspectSelectedTtsVoice();
      })
      .catch(function (e) {
        if (statusEl) statusEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
      });
  }

  var _dialectSuggestTimer = null;
  var _dialectUserLocked = false;

  function formatVoiceWarnings(warnings) {
    if (!warnings || !warnings.length) return "";
    return warnings.map(function (w) {
      var prefix = w.level === "error" ? "⛔" : "⚠️";
      return prefix + " " + (w.message || w.code || "");
    }).join("\n");
  }

  function suggestTtsDialect(applyIfUnk) {
    var textEl = getId("ttsText");
    var dialectEl = getId("ttsDialect");
    var hintEl = getId("ttsDialectHint");
    var text = (textEl && textEl.value || "").trim();
    if (!text || !dialectEl) {
      if (hintEl) hintEl.textContent = "";
      return Promise.resolve(null);
    }
    var current = (dialectEl.value || "UNK").trim().toUpperCase();
    var h = getHeaders();
    h["Content-Type"] = "application/json";
    return fetchWithTimeout(API.tts.suggestDialect, {
      method: "POST",
      headers: h,
      body: JSON.stringify({ text: text, current: current }),
    }, 30)
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || d.error || r.statusText); return d; }); })
      .then(function (data) {
        var suggested = (data.suggested || "UNK").toUpperCase();
        var reason = data.reason || "";
        if (hintEl) {
          hintEl.textContent = suggested && suggested !== "UNK"
            ? ("اقتراح: " + suggested + (reason ? " — " + reason : ""))
            : (reason || "");
        }
        if (applyIfUnk && data.apply_recommended && !_dialectUserLocked && current === "UNK" && suggested && suggested !== "UNK") {
          dialectEl.value = suggested;
        }
        return data;
      })
      .catch(function () {
        if (hintEl) hintEl.textContent = "";
        return null;
      });
  }

  function scheduleDialectSuggest() {
    if (_dialectSuggestTimer) clearTimeout(_dialectSuggestTimer);
    _dialectSuggestTimer = setTimeout(function () {
      suggestTtsDialect(true);
    }, 450);
  }

  function inspectSelectedTtsVoice() {
    var checkEl = getId("ttsVoiceCheck");
    var listEl = getId("ttsVoiceFilesList");
    var refEl = getId("ttsRefText");
    var userEmail = getTtsUserEmail();
    var speakerRef = (listEl && listEl.value || "").trim();
    if (!checkEl) return Promise.resolve(null);
    if (!userEmail || !speakerRef) {
      checkEl.textContent = "";
      return Promise.resolve(null);
    }
    var formRef = (refEl && refEl.value || "").trim();
    var selectedOpt = listEl.options[listEl.selectedIndex];
    if (refEl && !formRef && selectedOpt && selectedOpt.getAttribute("data-ref-text")) {
      refEl.value = selectedOpt.getAttribute("data-ref-text") || "";
      formRef = refEl.value.trim();
    }
    checkEl.textContent = "فحص البصمة…";
    var h = getHeaders();
    h["Content-Type"] = "application/json";
    return fetchWithTimeout(API.tts.inspectVoice, {
      method: "POST",
      headers: h,
      body: JSON.stringify({
        user_email: userEmail,
        speaker_ref: speakerRef,
        ref_text: formRef || undefined,
      }),
    }, 60)
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || d.error || r.statusText); return d; }); })
      .then(function (data) {
        var lines = [];
        if (data.duration_sec != null) {
          lines.push("المدة: " + Number(data.duration_sec).toFixed(1) + "s (مثالي 3–10s)");
        }
        if (data.saved_ref_text && refEl && !(refEl.value || "").trim()) {
          refEl.value = data.saved_ref_text;
        }
        var warnText = formatVoiceWarnings(data.warnings);
        if (warnText) lines.push(warnText);
        else lines.push("✅ البصمة جاهزة");
        checkEl.textContent = lines.join("\n");
        checkEl.dataset.blocking = data.blocking ? "1" : "0";
        return data;
      })
      .catch(function (e) {
        checkEl.textContent = "تعذّر فحص البصمة: " + (e.message || String(e));
        checkEl.dataset.blocking = "0";
        return null;
      });
  }

  function extractRefTextFromVoice() {
    var statusEl = getId("ttsVoiceStatus");
    var checkEl = getId("ttsVoiceCheck");
    var listEl = getId("ttsVoiceFilesList");
    var refEl = getId("ttsRefText");
    var btn = getId("btnTtsExtractRef");
    var userEmail = getTtsUserEmail();
    var speakerRef = (listEl && listEl.value || "").trim();
    if (!userEmail) {
      if (statusEl) statusEl.textContent = TTS_MESSAGES.needUser;
      return;
    }
    if (!speakerRef) {
      if (statusEl) statusEl.textContent = "اختر بصمة أولاً ثم استخرج ref_text.";
      return;
    }
    setButtonBusy(btn, true, "جاري الاستخراج…");
    if (checkEl) checkEl.textContent = "استخراج النص من البصمة عبر Whisper…";
    var h = getHeaders();
    h["Content-Type"] = "application/json";
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(API.tts.transcribeRef, {
      method: "POST",
      headers: h,
      body: JSON.stringify({ user_email: userEmail, speaker_ref: speakerRef, save: true }),
    }, timeout)
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.detail || d.error || d.message || r.statusText); return d; }); })
      .then(function (data) {
        if (refEl) refEl.value = data.ref_text || "";
        if (statusEl) statusEl.textContent = "تم استخراج ref_text وحفظه مع البصمة.";
        return inspectSelectedTtsVoice();
      })
      .catch(function (e) {
        if (statusEl) statusEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
        if (checkEl) checkEl.textContent = "";
      })
      .finally(function () {
        setButtonBusy(btn, false);
      });
  }

  var btnTtsRefreshVoices = getId("btnTtsRefreshVoices");
  if (btnTtsRefreshVoices) {
    btnTtsRefreshVoices.addEventListener("click", refreshTtsVoiceSamples);
  }

  var btnTtsExtractRef = getId("btnTtsExtractRef");
  if (btnTtsExtractRef) {
    btnTtsExtractRef.addEventListener("click", extractRefTextFromVoice);
  }

  var ttsTextEl = getId("ttsText");
  if (ttsTextEl) {
    ttsTextEl.addEventListener("input", scheduleDialectSuggest);
  }
  var ttsDialectEl = getId("ttsDialect");
  if (ttsDialectEl) {
    ttsDialectEl.addEventListener("change", function () {
      _dialectUserLocked = (ttsDialectEl.value || "UNK").toUpperCase() !== "UNK";
      suggestTtsDialect(false);
    });
  }
  var ttsVoiceListEl = getId("ttsVoiceFilesList");
  if (ttsVoiceListEl) {
    ttsVoiceListEl.addEventListener("change", function () {
      inspectSelectedTtsVoice();
    });
  }
  var ttsRefTextEl = getId("ttsRefText");
  if (ttsRefTextEl) {
    ttsRefTextEl.addEventListener("change", function () {
      if ((getId("ttsVoiceFilesList") || {}).value) inspectSelectedTtsVoice();
    });
  }

  var btnTtsUploadVoices = getId("btnTtsUploadVoices");
  if (btnTtsUploadVoices) {
    btnTtsUploadVoices.addEventListener("click", function () {
      var statusEl = getId("ttsVoiceStatus");
      var filesEl = getId("ttsVoiceFiles");
      var userEmail = getTtsUserEmail();
      if (!userEmail) {
        if (statusEl) statusEl.textContent = TTS_MESSAGES.needUser;
        return;
      }
      if (!filesEl || !filesEl.files || filesEl.files.length === 0) {
        if (statusEl) statusEl.textContent = TTS_MESSAGES.needVoiceFiles;
        return;
      }
      var refTextEl = getId("ttsRefText");
      var refTextValue = (refTextEl && refTextEl.value || "").trim();
      var fd = new FormData();
      fd.append("user_email", userEmail);
      if (refTextValue) fd.append("default_ref_text", refTextValue);
      for (var i = 0; i < filesEl.files.length; i++) fd.append("files", filesEl.files[i]);
      if (statusEl) statusEl.textContent = TTS_MESSAGES.uploadingVoices;
      var timeout = getId("timeout") ? getId("timeout").value : 300;
      fetchWithTimeout(API.tts.voiceSamples, {
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
          if (statusEl) statusEl.textContent = TTS_MESSAGES.uploadedFilesPrefix + (data.count || 0) + TTS_MESSAGES.uploadedFilesSuffix;
          refreshTtsVoiceSamples();
          filesEl.value = "";
        })
        .catch(function (e) {
          if (statusEl) statusEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
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
        if (statusEl) statusEl.textContent = TTS_MESSAGES.needVoiceSelection;
        return;
      }
      var timeout = getId("timeout") ? getId("timeout").value : 300;
      var url = API.tts.voiceSample + "?user_email=" + encodeURIComponent(userEmail) + "&file=" + encodeURIComponent(selectedFile);
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
          if (statusEl) statusEl.textContent = TTS_MESSAGES.deletedVoicePrefix + selectedFile;
          refreshTtsVoiceSamples();
          var voiceAudio = getId("ttsVoiceAudio");
          if (voiceAudio) voiceAudio.removeAttribute("src");
        })
        .catch(function (e) {
          if (statusEl) statusEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
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
      var url = API.tts.voiceFile + "?user_email=" + encodeURIComponent(userEmail) + "&file=" + encodeURIComponent(file);
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
    if (!requireLogin(ACCOUNT_MESSAGES.needLoginFirst)) return;
    var btnTts = getId("btnTts");
    var textEl = getId("ttsText"), text = (textEl && textEl.value || "").trim();
    if (!text) {
      var errEl0 = getId("ttsError");
      errEl0.textContent = TTS_MESSAGES.needTtsText;
      errEl0.classList.remove("hidden");
      return;
    }

    function runTtsRequest() {
      var voice = getId("ttsVoice").value || "habibi_unified";
      var engine = "habibi";
      var speed = parseFloat(getId("ttsSpeed").value) || 1;
      var dialect = (getId("ttsDialect") && getId("ttsDialect").value || "UNK").trim().toUpperCase();
      var refText = (getId("ttsRefText") && getId("ttsRefText").value || "").trim();
      var speakerRef = (getId("ttsVoiceFilesList") && getId("ttsVoiceFilesList").value || "").trim();
      var userEmailForTts = getTtsUserEmail();

      var errEl = getId("ttsError");
      errEl.classList.add("hidden");
      var audioEl = getId("ttsAudio");
      var dlEl = getId("ttsDl");
      var metaEl = getId("ttsMeta");
      dlEl.innerHTML = "";
      if (metaEl) metaEl.textContent = "";

      if (!speakerRef) {
        errEl.textContent = "اختر بصمة صوتية لـ Habibi أو ارفع عينة أولاً.";
        errEl.classList.remove("hidden");
        return;
      }
      if (!refText) {
        errEl.textContent = "اكتب ref_text المطابق لنص البصمة فقط (أو استخرجه عبر ASR).";
        errEl.classList.remove("hidden");
        return;
      }

      var body = { text: text, voice: voice, speed: speed, engine: engine, diacritize: false };
      if (userEmailForTts) body.user_email = userEmailForTts;
      body.speaker_ref = speakerRef;
      body.ref_text = refText;
      if (dialect) body.dialect = dialect;
      var chunkEl = getId("ttsMaxChunk");
      if (chunkEl && chunkEl.value) {
        var chunkN = parseInt(chunkEl.value, 10);
        if (!isNaN(chunkN)) body.max_chunk_chars = chunkN;
      }

      var h = getHeaders();
      h["Content-Type"] = "application/json";

      var timeout = getId("timeout") ? getId("timeout").value : 300;
      if (String(timeout).trim() !== "0") {
        var ttsTimeoutNum = parseInt(String(timeout), 10);
        if (!isNaN(ttsTimeoutNum) && ttsTimeoutNum > 0 && ttsTimeoutNum < 1800) timeout = 1800;
      }
      setButtonBusy(btnTts, true, TTS_MESSAGES.generating);
      fetchWithTimeout(API.tts.root, { method: "POST", headers: h, body: JSON.stringify(body) }, timeout)
        .then(function (r) {
          if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
          return r.json();
        })
        .then(function (data) {
          var done = Promise.resolve();
          if (data.download_url) {
            done = loadAuthenticatedMedia(data.download_url, "tts.wav").then(function (res) {
              revokeBlobSrc(audioEl);
              audioEl.src = res.objectUrl;
              dlEl.innerHTML = "";
              var dlBtn = document.createElement("button");
              dlBtn.type = "button";
              dlBtn.className = "btn btn-secondary";
              dlBtn.textContent = "تحميل الصوت";
              dlBtn.addEventListener("click", function () {
                var a = document.createElement("a");
                a.href = res.objectUrl;
                a.download = res.filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
              });
              dlEl.appendChild(dlBtn);
            });
          }
          return done.then(function () {
            if (metaEl) {
              metaEl.textContent = [
                "engine_used: " + (data.engine_used || "-"),
                "requested_voice: " + (data.requested_voice || "-"),
                "resolved_voice: " + (data.resolved_voice || "-"),
                "speaker_ref: " + (data.speaker_ref || "-"),
                "dialect: " + (data.dialect || "-"),
                "fallback_used: " + (data.fallback_used ? "yes" : "no"),
                "arabic_detected: " + (data.arabic_detected ? "yes" : "no"),
                "diacritize: " + (data.diacritize ? "yes" : "no"),
                "max_chunk_chars: " + (data.max_chunk_chars != null ? data.max_chunk_chars : "-"),
              ].join("\n");
            }
          });
        })
        .catch(function (e) {
          errEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
          errEl.classList.remove("hidden");
        })
        .finally(function () {
          setButtonBusy(btnTts, false);
        });
    }

    var enginePre = "habibi";
    var speakerPre = (getId("ttsVoiceFilesList") && getId("ttsVoiceFilesList").value || "").trim();
    var needsHabibiCheck = !!speakerPre;

    setButtonBusy(btnTts, true, "تحضير…");
    suggestTtsDialect(true)
      .catch(function () { return null; })
      .then(function () {
        if (!needsHabibiCheck) return null;
        return inspectSelectedTtsVoice();
      })
      .then(function (inspect) {
        setButtonBusy(btnTts, false);
        if (!inspect) {
          runTtsRequest();
          return;
        }
        var errEl = getId("ttsError");
        if (inspect.blocking) {
          errEl.textContent = "أصلح مشاكل البصمة قبل التوليد:\n" + formatVoiceWarnings(inspect.warnings);
          errEl.classList.remove("hidden");
          return;
        }
        var warns = (inspect.warnings || []).filter(function (w) { return w.level === "warn"; });
        if (warns.length) {
          var ok = window.confirm(
            "تحذيرات على البصمة:\n" + formatVoiceWarnings(warns) + "\n\nالمتابعة بالتوليد؟"
          );
          if (!ok) return;
        }
        runTtsRequest();
      })
      .catch(function (e) {
        setButtonBusy(btnTts, false);
        var errEl = getId("ttsError");
        errEl.textContent = TTS_MESSAGES.errorPrefix + (e.message || String(e));
        errEl.classList.remove("hidden");
      });
  });

  // ——— بصمات الصوت والمتحدثون ———
  var spkMediaRecorder = null, spkRecordedChunks = [];
  function refreshSpeakersList() {
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(withSpeakersUserQuery(API.asr.enrolledSpeakers), { method: "GET", headers: getHeaders() }, timeout)
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

  function uniqueSpkRecordingFilename() {
    var now = new Date();
    function pad(n) { return String(n).padStart(2, "0"); }
    return "spk_" + now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) + "_" +
      pad(now.getHours()) + pad(now.getMinutes()) + pad(now.getSeconds()) + ".webm";
  }

  getId("btnEnroll").addEventListener("click", function () {
    var btnEnroll = getId("btnEnroll");
    var name = (getId("spkName") && getId("spkName").value || "").trim();
    if (!name) {
      getId("enrollOut").textContent = SPEAKERS_MESSAGES.needName;
      return;
    }
    if (!getSpeakersUserEmail()) {
      getId("enrollOut").textContent = "سجّل الدخول أولاً — بصمة «محمد» تُحفظ لحسابك فقط وليست مشتركة.";
      return;
    }
    var fd = new FormData();
    fd.append("name", name);
    fd.append("user_email", getSpeakersUserEmail());
    var filesIn = getId("spkFiles");
    var hasFile = false;
    if (filesIn && filesIn.files) {
      for (var i = 0; i < filesIn.files.length; i++) {
        fd.append("files", filesIn.files[i]);
        hasFile = true;
      }
    }
    if (window._lastSpkRecordedBlob) {
      fd.append(
        "files",
        window._lastSpkRecordedBlob,
        window._lastSpkRecordingName || uniqueSpkRecordingFilename()
      );
      hasFile = true;
    }
    if (!hasFile) {
      getId("enrollOut").textContent = SPEAKERS_MESSAGES.needAudioSample;
      return;
    }
    if (filesIn && filesIn.files && filesIn.files.length) {
      var enrollErr = validateAudioFilesList(filesIn.files, 1);
      if (enrollErr) {
        getId("enrollOut").textContent = enrollErr;
        return;
      }
    }
    getId("enrollOut").textContent = SPEAKERS_MESSAGES.enrolling;
    setButtonBusy(btnEnroll, true, SPEAKERS_MESSAGES.enrollBusy);
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(API.asr.enrollSpeaker, { method: "POST", headers: getHeaders(), body: fd }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.message || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        getId("enrollOut").textContent = (data.message || SPEAKERS_MESSAGES.enrolled) + (data.success ? "" : SPEAKERS_MESSAGES.warningSuffix);
        window._lastSpkRecordedBlob = null;
        window._lastSpkRecordingName = null;
        if (getId("spkMicStatus")) getId("spkMicStatus").textContent = "";
        if (getId("spkFiles")) getId("spkFiles").value = "";
        refreshSpeakersList();
        var spkList = getId("spkList");
        if (spkList && name) spkList.value = name;
        if (spkList) spkList.dispatchEvent(new Event("change"));
      })
      .catch(function (e) {
        getId("enrollOut").textContent = SPEAKERS_MESSAGES.errorPrefix + (e.message || String(e));
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
      if (window._lastSpkRecordingName) {
        status.textContent = "تم حفظ المقطع: " + window._lastSpkRecordingName + " — اضغط «تسجيل/تحديث البصمة».";
      } else {
        status.textContent = SPEAKERS_MESSAGES.micStopped;
      }
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status.textContent = SPEAKERS_MESSAGES.micUnsupported;
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        spkRecordedChunks = [];
        spkMediaRecorder = new MediaRecorder(stream);
        spkMediaRecorder.ondataavailable = function (e) { if (e.data.size) spkRecordedChunks.push(e.data); };
        spkMediaRecorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          window._lastSpkRecordingName = uniqueSpkRecordingFilename();
          window._lastSpkRecordedBlob = new Blob(spkRecordedChunks, { type: "audio/webm" });
        };
        spkMediaRecorder.start();
        btn.textContent = "إيقاف التسجيل";
        status.textContent = SPEAKERS_MESSAGES.micRecording;
      })
      .catch(function (e) {
        status.textContent = SPEAKERS_MESSAGES.micAccessFailed + (e.message || String(e));
      });
  });

  getId("btnRefreshSpeakers").addEventListener("click", function () { refreshSpeakersList(); });

  getId("btnDeleteSpeaker").addEventListener("click", function () {
    var name = (getId("spkList") && getId("spkList").value || "").trim();
    if (!name) {
      getId("enrollOut").textContent = SPEAKERS_MESSAGES.needSelectedSpeaker;
      return;
    }
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout(withSpeakersUserQuery(API.asr.deleteSpeaker + "?name=" + encodeURIComponent(name)), { method: "DELETE", headers: getHeaders() }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.message || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        getId("enrollOut").textContent = data.message || SPEAKERS_MESSAGES.deleted;
        refreshSpeakersList();
        getId("spkFilesList").innerHTML = "<option value=\"\">— اختر —</option>";
        getId("spkAudio").removeAttribute("src");
      })
      .catch(function (e) {
        getId("enrollOut").textContent = SPEAKERS_MESSAGES.errorPrefix + (e.message || String(e));
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
    fetchWithTimeout(withSpeakersUserQuery(API.asr.speakerFiles + "?name=" + encodeURIComponent(name)), { method: "GET", headers: getHeaders() }, timeout)
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
    var url = withSpeakersUserQuery(API.asr.speakerFile + "?name=" + encodeURIComponent(name) + "&file=" + encodeURIComponent(file));
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
  if (isLoggedIn()) {
    fetch(API.tts.voices, { headers: getHeaders() })
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
  }

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
        setText("authStatus", ACCOUNT_MESSAGES.needRegisterFields);
        return;
      }
      setText("authStatus", ACCOUNT_MESSAGES.registering);
      jsonRequest("/auth/register", "POST", {
        email: email,
        password: password,
        full_name: fullName,
      }).then(function () {
        setText("authStatus", ACCOUNT_MESSAGES.registerSuccess);
      }).catch(function (e) {
        setText("authStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
      });
    });
  }

  if (btnLogin) {
    btnLogin.addEventListener("click", function () {
      var email = (getId("authEmail") && getId("authEmail").value || "").trim();
      var password = (getId("authPassword") && getId("authPassword").value || "").trim();
      if (!email || !password) {
        setText("authStatus", ACCOUNT_MESSAGES.needLoginFields);
        return;
      }
      setText("authStatus", ACCOUNT_MESSAGES.loggingIn);
      jsonRequest("/auth/login", "POST", {
        email: email,
        password: password,
      }).then(function (data) {
        var userEmail = data.email || email;
        setSession(userEmail, data.access_token || "");
        setText("authStatus", ACCOUNT_MESSAGES.loginSuccess);
        if (getId("authFullName") && data.full_name) {
          getId("authFullName").value = data.full_name;
        }
      }).catch(function (e) {
        setText("authStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
      });
    });
  }

  if (btnLogout) {
    btnLogout.addEventListener("click", function () {
      if (!session.email) {
        setText("authStatus", ACCOUNT_MESSAGES.noLoggedInUser);
        return;
      }
      fetchWithTimeout("/auth/logout", {
        method: "POST",
        headers: getHeaders(),
      }, getId("timeout") ? getId("timeout").value : 300)
        .then(function () {
          setSession("", "");
          setText("authStatus", ACCOUNT_MESSAGES.logoutSuccess);
          setText("profileStatus", "");
          setText("dashStatus", "");
        })
        .catch(function (e) {
          setText("authStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
        });
    });
  }

  // ——— الملف الشخصي ———
  var btnLoadProfile = getId("btnLoadProfile");
  var btnSaveProfile = getId("btnSaveProfile");

  function loadProfile() {
    if (!session.email) {
      setText("profileStatus", ACCOUNT_MESSAGES.needLoginFirst);
      return;
    }
    setText("profileStatus", ACCOUNT_MESSAGES.profileLoading);
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
        setText("profileStatus", ACCOUNT_MESSAGES.profileLoaded);
      })
      .catch(function (e) {
        setText("profileStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
      });
  }

  if (btnLoadProfile) {
    btnLoadProfile.addEventListener("click", loadProfile);
  }

  if (btnSaveProfile) {
    btnSaveProfile.addEventListener("click", function () {
      if (!session.email) {
        setText("profileStatus", ACCOUNT_MESSAGES.needLoginFirst);
        return;
      }
      setText("profileStatus", ACCOUNT_MESSAGES.profileSaving);
      jsonRequest("/users/me", "PUT", {
        full_name: (getId("profileFullName") && getId("profileFullName").value || "").trim(),
        bio: (getId("profileBio") && getId("profileBio").value || "").trim(),
        avatar_url: (getId("profileAvatar") && getId("profileAvatar").value || "").trim(),
      }).then(function () {
        setText("profileStatus", ACCOUNT_MESSAGES.profileSaved);
      }).catch(function (e) {
        setText("profileStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
      });
    });
  }

  // ——— لوحة التحكم ———
  var btnRefreshDashboard = getId("btnRefreshDashboard");

  function refreshDashboard() {
    if (!session.email) {
      setText("dashStatus", ACCOUNT_MESSAGES.needLoginFirst);
      return;
    }
    setText("dashStatus", ACCOUNT_MESSAGES.dashboardLoading);
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
      setText("dashStatus", ACCOUNT_MESSAGES.dashboardUpdated);
    }).catch(function (e) {
      setText("dashStatus", ACCOUNT_MESSAGES.errorPrefix + (e.message || String(e)));
    });
  }

  if (btnRefreshDashboard) {
    btnRefreshDashboard.addEventListener("click", refreshDashboard);
  }

  setSession(session.email, session.token);
  resumePendingJobs();
  queueUIStateSave();
})();
