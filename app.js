
const API_BASE = "https://ai-job-analyse.onrender.com";

const state = {
  profile: JSON.parse(localStorage.getItem("jobmatch_profile") || "null"),
  jobs: [],
  applied: JSON.parse(localStorage.getItem("jobmatch_applied") || "[]")
};

const els = {
  pageTitle: document.getElementById("pageTitle"),
  pageSubtitle: document.getElementById("pageSubtitle"),
  resumeStatus: document.getElementById("resumeStatus"),
  matchedCount: document.getElementById("matchedCount"),
  strongCount: document.getElementById("strongCount"),
  appliedCount: document.getElementById("appliedCount"),
  dashboardJobs: document.getElementById("dashboardJobs"),
  jobsList: document.getElementById("jobsList"),
  appliedJobs: document.getElementById("appliedJobs"),
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
  dashboard: ["Dashboard", "Upload your resume and view only matching jobs."],
  resume: ["Resume", "Your extracted candidate profile."],
  jobs: ["Matched Jobs", "Only jobs that pass the resume and filter rules."],
  applied: ["Applied", "Jobs you marked as applied."]
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

function updateStats() {
  const filtered = getFilteredJobs();
  els.resumeStatus.textContent = state.profile ? "Ready" : "Not uploaded";
  els.matchedCount.textContent = filtered.length;
  els.strongCount.textContent = filtered.filter(j => j.match >= 90).length;
  els.appliedCount.textContent = state.applied.length;
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

function getFilteredJobs() {
  const hours = Number(els.timeFilter.value);
  const minMatch = Number(els.matchFilter.value);
  const type = els.typeFilter.value;
  const visa = els.visaFilter.value;
  const work = els.workFilter.value;

  return state.jobs.filter(job => {
    const typeOk = type === "all" || (job.types || []).includes(type);
    const visaOk = visa === "all" || (job.visas || []).includes(visa) || (job.visas || []).includes("Any");
    const workOk = work === "all" || job.work_model === work;
    return job.age_hours <= hours && job.match >= minMatch && typeOk && visaOk && workOk && !job.blocked;
  });
}

function renderAll() {
  const filtered = getFilteredJobs();
  renderJobs(filtered.slice(0, 5), els.dashboardJobs);
  renderJobs(filtered, els.jobsList);

  const appliedJobs = state.jobs.filter(j => state.applied.includes(j.id));
  renderJobs(appliedJobs, els.appliedJobs, true);

  updateStats();
  updateProfile();
}

function renderJobs(jobs, target, appliedView = false) {
  target.innerHTML = "";

  if (!jobs.length) {
    target.innerHTML = `<div class="empty-state">No matching jobs found for the selected filters.</div>`;
    return;
  }

  jobs.forEach(job => {
    const template = document.getElementById("jobCardTemplate").content.cloneNode(true);
    template.querySelector(".source-badge").textContent = job.source || "Job Source";
    template.querySelector(".job-title").textContent = job.title;
    template.querySelector(".job-company").textContent = job.company || "Unknown company";
    template.querySelector(".match-badge").textContent = `${job.match}%`;

    template.querySelector(".job-location").textContent = job.location || "USA";
    template.querySelector(".job-model").textContent = job.work_model || "Not stated";
    template.querySelector(".job-type").textContent = (job.types || []).join(" / ") || "Not stated";
    template.querySelector(".job-visa").textContent = (job.visas || []).join(" / ") || "Visa not stated";
    template.querySelector(".job-posted").textContent = postedLabel(job.age_hours);

    const skills = template.querySelector(".skills-row");
    (job.matched_skills || []).slice(0, 10).forEach(skill => {
      const chip = document.createElement("span");
      chip.className = "skill-chip";
      chip.textContent = skill;
      skills.appendChild(chip);
    });

    const hard = template.querySelector(".hard-filter");
    hard.textContent = job.reason || "Strong match";
    if (job.warning) hard.classList.add("warn");
    if (job.blocked) hard.classList.add("block");

    const applyLink = template.querySelector(".apply-link");
    applyLink.href = job.url || "#";

    const markBtn = template.querySelector(".mark-applied");
    const alreadyApplied = state.applied.includes(job.id);
    markBtn.textContent = alreadyApplied ? "Applied ✓" : "Mark Applied";
    markBtn.disabled = alreadyApplied;

    markBtn.addEventListener("click", () => {
      if (!state.applied.includes(job.id)) {
        state.applied.push(job.id);
        localStorage.setItem("jobmatch_applied", JSON.stringify(state.applied));
        renderAll();
      }
    });

    if (appliedView) {
      markBtn.style.display = "none";
    }

    target.appendChild(template);
  });
}

function postedLabel(hours) {
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min ago`;
  return `${Math.round(hours)} hr${hours >= 1.5 ? "s" : ""} ago`;
}

async function uploadResume(file) {
  els.uploadMessage.textContent = "Uploading and analyzing resume…";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/resume/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error(await res.text());
    state.profile = await res.json();
    localStorage.setItem("jobmatch_profile", JSON.stringify(state.profile));
    els.uploadMessage.textContent = "Resume analyzed successfully.";
    await refreshJobs();
  } catch (err) {
    els.uploadMessage.textContent = `Upload failed: ${err.message}`;
  }

  renderAll();
}

async function refreshJobs() {
  els.refreshBtn.disabled = true;
  els.refreshBtn.textContent = "Refreshing…";

  try {
    const params = new URLSearchParams({
      hours: els.timeFilter.value,
      min_match: els.matchFilter.value
    });

    const res = await fetch(`${API_BASE}/api/jobs?${params.toString()}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.jobs = data.jobs || [];
  } catch (err) {
    console.error(err);
  } finally {
    els.refreshBtn.disabled = false;
    els.refreshBtn.textContent = "Refresh Jobs";
  }

  renderAll();
}

els.resumeFile.addEventListener("change", e => {
  const file = e.target.files[0];
  if (file) uploadResume(file);
});

els.refreshBtn.addEventListener("click", refreshJobs);
[els.timeFilter, els.matchFilter, els.typeFilter, els.visaFilter, els.workFilter]
  .forEach(el => el.addEventListener("change", renderAll));

updateProfile();
refreshJobs();
