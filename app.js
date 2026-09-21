const API_BASE = "https://ai-job-analyse.onrender.com";

const state = {
  profile: JSON.parse(localStorage.getItem("jdmatch_profile") || "null"),
  jds: []
};

const els = {
  pageTitle: document.getElementById("pageTitle"),
  pageSubtitle: document.getElementById("pageSubtitle"),
  resumeStatus: document.getElementById("resumeStatus"),
  matchedCount: document.getElementById("matchedCount"),
  strongCount: document.getElementById("strongCount"),
  dashboardJds: document.getElementById("dashboardJds"),
  jdsList: document.getElementById("jdsList"),
  resumeFile: document.getElementById("resumeFile"),
  uploadMessage: document.getElementById("uploadMessage"),
  refreshBtn: document.getElementById("refreshBtn"),
  profileEmpty: document.getElementById("profileEmpty"),
  profileCard: document.getElementById("profileCard"),
  profileName: document.getElementById("profileName"),
  profileYears: document.getElementById("profileYears"),
  profileRole: document.getElementById("profileRole"),
  profileSkills: document.getElementById("profileSkills"),
  timeFilter: document.getElementById("timeFilter"),
  matchFilter: document.getElementById("matchFilter"),
  typeFilter: document.getElementById("typeFilter"),
  visaFilter: document.getElementById("visaFilter"),
  workFilter: document.getElementById("workFilter")
};

const viewMeta = {
  dashboard: ["Dashboard", "Upload your resume and view only matching recruiter JD posts."],
  resume: ["Resume", "Your extracted candidate profile."],
  jds: ["Matched JDs", "Fresh recruiter JD posts matched to your resume."]
};

document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => showView(btn.dataset.view));
});

function showView(view) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById(`${view}View`).classList.add("active");
  els.pageTitle.textContent = viewMeta[view][0];
  els.pageSubtitle.textContent = viewMeta[view][1];
}

function getFilteredJds() {
  const hours = Number(els.timeFilter.value);
  const minMatch = Number(els.matchFilter.value);
  const type = els.typeFilter.value;
  const visa = els.visaFilter.value;
  const work = els.workFilter.value;

  return state.jds.filter(jd => {
    const typeOk = type === "all" || (jd.types || []).includes(type);
    const visaOk = visa === "all" || (jd.visas || []).includes(visa) || (jd.visas || []).includes("Any");
    const workOk = work === "all" || jd.work_model === work || jd.work_model === "Not stated";
    return jd.age_hours <= hours && jd.match >= minMatch && typeOk && visaOk && workOk && !jd.blocked;
  });
}

function updateStats() {
  const filtered = getFilteredJds();
  els.resumeStatus.textContent = state.profile ? "Ready" : "Not uploaded";
  els.matchedCount.textContent = filtered.length;
  els.strongCount.textContent = filtered.filter(j => j.match >= 90).length;
}

function updateProfile() {
  if (!state.profile) {
    els.profileEmpty.classList.remove("hidden");
    els.profileCard.classList.add("hidden");
    return;
  }
  els.profileEmpty.classList.add("hidden");
  els.profileCard.classList.remove("hidden");
  els.profileName.textContent = state.profile.name || "Candidate";
  els.profileYears.textContent = state.profile.years ? `${state.profile.years}+ years` : "Not detected";
  els.profileRole.textContent = state.profile.primary_role || "Software Engineer";
  els.profileSkills.innerHTML = "";
  (state.profile.skills || []).forEach(skill => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = skill;
    els.profileSkills.appendChild(chip);
  });
}

function renderAll() {
  const filtered = getFilteredJds();
  renderJds(filtered.slice(0, 6), els.dashboardJds);
  renderJds(filtered, els.jdsList);
  updateStats();
  updateProfile();
}

function renderJds(jds, target) {
  target.innerHTML = "";
  if (!jds.length) {
    target.innerHTML = `<div class="empty-state">No matching JDs found. If live search is not configured yet, add SERPER_API_KEY on Render.</div>`;
    return;
  }

  jds.forEach(jd => {
    const template = document.getElementById("jdCardTemplate").content.cloneNode(true);
    template.querySelector(".job-title").textContent = jd.title || "LinkedIn recruiter post";
    template.querySelector(".job-company").textContent = jd.company || "Recruiter / company not identified";
    template.querySelector(".match-badge").textContent = `${jd.match}%`;
    template.querySelector(".job-location").textContent = jd.location || "Location not stated";
    template.querySelector(".job-model").textContent = jd.work_model || "Not stated";
    template.querySelector(".job-type").textContent = (jd.types || []).join(" / ") || "Type not stated";
    template.querySelector(".job-visa").textContent = (jd.visas || []).join(" / ") || "Visa not stated";
    template.querySelector(".job-posted").textContent = jd.posted_label || "Recent";

    const skills = template.querySelector(".skills-row");
    (jd.matched_skills || []).slice(0, 12).forEach(skill => {
      const chip = document.createElement("span");
      chip.className = "skill-chip";
      chip.textContent = skill;
      skills.appendChild(chip);
    });

    template.querySelector(".jd-snippet").textContent = jd.snippet || "Open the LinkedIn post to view the JD.";
    template.querySelector(".recruiter-row").textContent = jd.email ? `Recruiter email: ${jd.email}` : "Recruiter email: not visible in search snippet";

    const hard = template.querySelector(".hard-filter");
    hard.textContent = jd.reason || "Preliminary strong match";
    if (jd.warning) hard.classList.add("warn");
    if (jd.blocked) hard.classList.add("block");

    template.querySelector(".post-link").href = jd.url || "#";
    target.appendChild(template);
  });
}

async function uploadResume(file) {
  els.uploadMessage.textContent = "Uploading and analyzing resume…";
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch(`${API_BASE}/api/resume/upload`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(await res.text());
    state.profile = await res.json();
    localStorage.setItem("jdmatch_profile", JSON.stringify(state.profile));
    els.uploadMessage.textContent = "Resume analyzed successfully.";
    await refreshJds();
  } catch (err) {
    els.uploadMessage.textContent = `Upload failed: ${err.message}`;
  }
  renderAll();
}

async function refreshJds() {
  els.refreshBtn.disabled = true;
  els.refreshBtn.textContent = "Refreshing…";
  try {
    const params = new URLSearchParams({
      hours: els.timeFilter.value,
      min_match: els.matchFilter.value
    });
    const res = await fetch(`${API_BASE}/api/jds?${params.toString()}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.jds = data.jds || [];
  } catch (err) {
    console.error(err);
    state.jds = [];
  } finally {
    els.refreshBtn.disabled = false;
    els.refreshBtn.textContent = "Refresh JDs";
  }
  renderAll();
}

els.resumeFile.addEventListener("change", e => {
  const file = e.target.files[0];
  if (file) uploadResume(file);
});
els.refreshBtn.addEventListener("click", refreshJds);
[els.timeFilter, els.matchFilter, els.typeFilter, els.visaFilter, els.workFilter]
  .forEach(el => el.addEventListener("change", renderAll));

updateProfile();
refreshJds();
