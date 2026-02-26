(function () {
  "use strict";

  function qs(s) { return document.querySelector(s); }
  function qsa(s) { return document.querySelectorAll(s); }
  function getId(id) { return document.getElementById(id); }

  // تبويبات ASR / TTS
  qsa(".tab[data-tab]").forEach(function (t) {
    t.addEventListener("click", function () {
      qsa(".tab[data-tab]").forEach(function (x) { x.classList.remove("active"); });
      qsa(".panel").forEach(function (p) { p.classList.remove("active"); });
      t.classList.add("active");
      var panel = getId(t.dataset.tab + "-panel");
      if (panel) panel.classList.add("active");
    });
  });

  // مصدر الصوت: ملف / ميكروفون
  qsa(".src-btn").forEach(function (b) {
    b.addEventListener("click", function () {
      qsa(".src-btn").forEach(function (x) { x.classList.remove("active"); });
      b.classList.add("active");
      var fileZone = getId("file-zone"), micZone = getId("mic-zone");
      if (b.dataset.src === "file") {
        if (fileZone) fileZone.classList.remove("hidden");
        if (micZone) micZone.classList.add("hidden");
      } else {
        if (fileZone) fileZone.classList.add("hidden");
        if (micZone) micZone.classList.remove("hidden");
      }
    });
  });

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
  }

  function setText(id, text) {
    var el = getId(id);
    if (el) el.textContent = text || "";
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

  function fetchWithTimeout(url, opts, timeoutMs) {
    var t = Math.max(60000, parseInt(timeoutMs || 900, 10) * 1000);
    var ctrl = new AbortController();
    var id = setTimeout(function () { ctrl.abort(); }, t);
    opts = opts || {};
    opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (r) {
      clearTimeout(id);
      return r;
    }, function (e) {
      clearTimeout(id);
      throw e;
    });
  }

  // إرسال ملف واحد
  getId("btnSend").addEventListener("click", function () {
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
    if (session.email) fd.append("user_email", session.email);

    getId("outText").value = "جاري التحويل...";
    getId("outSummary").value = "";
    getId("outKeywords").value = "";
    getId("dlLinks").innerHTML = "";
    getId("outSegments").textContent = "";

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
        getId("outText").value = data.text || "";
        getId("outSummary").value = data.summary || "";
        getId("outKeywords").value = data.keywords || "";
        var segs = data.segments || [];
        if (segs.length && getId("outSegments")) {
          var s = segs.map(function (x) {
            var spk = x.speaker !== undefined ? " [" + (x.speaker || "?") + "] " : " ";
            return (x.start || 0).toFixed(1) + "s" + spk + (x.text || "");
          }).join("\n");
          getId("outSegments").textContent = s;
        }
        var links = getId("dlLinks");
        links.innerHTML = "";
        var urls = data.download_urls || {};
        if (urls.txt) links.innerHTML += '<a href="' + urls.txt + '" download>تحميل TXT</a> ';
        if (urls.srt) links.innerHTML += '<a href="' + urls.srt + '" download>تحميل SRT</a> ';
        if (urls.vtt) links.innerHTML += '<a href="' + urls.vtt + '" download>تحميل VTT</a> ';
        if (urls.segments) links.innerHTML += '<a href="' + urls.segments + '" download>تحميل segments</a> ';
        if (urls.summary) links.innerHTML += '<a href="' + urls.summary + '" download>تحميل الملخص</a>';
      })
      .catch(function (e) {
        getId("outText").value = "خطأ: " + (e.message || String(e));
      });
  });

  // إرسال عدة ملفات
  getId("btnBatch").addEventListener("click", function () {
    var filesIn = getId("filesIn");
    if (!filesIn || !filesIn.files || filesIn.files.length === 0) {
      getId("outText").value = "يرجى اختيار عدة ملفات.";
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
    if (session.email) fd.append("user_email", session.email);

    getId("outText").value = "جاري تحويل عدة ملفات...";
    getId("outSummary").value = "";
    getId("outKeywords").value = "";
    getId("dlLinks").innerHTML = "";
    getId("outSegments").textContent = "";

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
        getId("outText").value = data.text || "";
        getId("outSummary").value = data.summary || "";
        getId("outKeywords").value = data.keywords || "";
        var segs = data.segments || [];
        if (segs.length) {
          var s = segs.map(function (x) {
            var spk = x.speaker !== undefined ? " [" + (x.speaker || "?") + "] " : " ";
            return (x.start || 0).toFixed(1) + "s" + spk + (x.text || "");
          }).join("\n");
          getId("outSegments").textContent = s;
        }
        var links = getId("dlLinks");
        links.innerHTML = "";
        var urls = data.download_urls || {};
        if (urls.txt) links.innerHTML += '<a href="' + urls.txt + '" download>تحميل TXT</a> ';
        if (urls.srt) links.innerHTML += '<a href="' + urls.srt + '" download>تحميل SRT</a> ';
        if (urls.vtt) links.innerHTML += '<a href="' + urls.vtt + '" download>تحميل VTT</a> ';
        if (urls.segments) links.innerHTML += '<a href="' + urls.segments + '" download>تحميل segments</a> ';
        if (urls.summary) links.innerHTML += '<a href="' + urls.summary + '" download>تحميل الملخص</a>';
      })
      .catch(function (e) {
        getId("outText").value = "خطأ: " + (e.message || String(e));
      });
  });

  // تلخيص النص
  getId("btnSummary").addEventListener("click", function () {
    var text = (getId("outText") && getId("outText").value || "").trim();
    if (!text) {
      getId("outSummary").value = "أدخل نصاً أولاً أو قم بالتحويل الصوتي.";
      return;
    }
    var mode = getId("summaryMode") ? getId("summaryMode").value : "lite";
    var fd = new FormData();
    fd.append("text", text);
    fd.append("summary_mode", mode);
    if (session.email) fd.append("user_email", session.email);
    getId("outSummary").value = "جاري التلخيص...";
    var timeout = getId("timeout") ? getId("timeout").value : 300;
    fetchWithTimeout("/summarize", { method: "POST", headers: getHeaders(), body: fd }, timeout)
      .then(function (r) {
        if (!r.ok) return r.json().then(function (j) { throw new Error(j.detail || j.error || r.statusText); });
        return r.json();
      })
      .then(function (data) {
        getId("outSummary").value = data.summary || "";
        getId("outKeywords").value = data.keywords || "";
        var links = getId("dlLinks");
        var urls = data.download_urls || {};
        if (urls.summary) links.innerHTML += ' <a href="' + urls.summary + '" download>تحميل الملخص</a>';
      })
      .catch(function (e) {
        getId("outSummary").value = "خطأ: " + (e.message || String(e));
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
    getId("enrollOut").textContent = "جاري التسجيل...";
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
})();
